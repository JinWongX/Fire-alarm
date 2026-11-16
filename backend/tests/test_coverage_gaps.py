"""覆盖缺口补测：逐一切中基线 term-missing 中的 12 处 partial 分支与 schemas 的 None 分支。

覆盖映射：
  - devices.py 108->107    更新时某字段显式置 None（循环跳过 etattr）
  - schemas.py      61      _strip_not_blank(None) 直接返回
  - drills.py  42->41      更新时字段置 None；76->78 finish 无 score
  - alarms.py 100->102     确认误报但报警对应设备已不存在
  - plans.py  109->108     更新预案字段置 None
  - repairs.py 81->85 / 83->85  finish 无 device_id / 设备行已删
  - users.py  61->60       更新用户字段置 None
  - patrols.py 91->100 / 113->116  无设备异常巡检；111->113 复用带 patrol_id 的维修单
"""
import pytest


# ---------- schemas._strip_not_blank 的 None / 空白 / 正常 三态 ----------
def test_strip_not_blank_none_and_blank():
    from app.schemas import _strip_not_blank
    assert _strip_not_blank(None) is None
    with pytest.raises(ValueError):
        _strip_not_blank("   ")
    assert _strip_not_blank("设备名称") == "设备名称"


# ---------- devices.py 108->107 + schemas.py 61（name 置 None） ----------
def test_update_device_with_none_fields(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    r = client.post(
        "/api/devices",
        json={"device_no": "NONE-DEV", "name": "置空设备", "device_type": "smoke", "area_id": area["id"]},
        headers=headers["supervisor"],
    )
    did = r.json()["id"]
    # name=None 触达 _strip_not_blank 的 None 分支；remark/area_id=None 覆盖更新循环的跳过路径
    r2 = client.put(
        f"/api/devices/{did}",
        json={"name": None, "remark": None, "area_id": None},
        headers=headers["supervisor"],
    )
    assert r2.status_code == 200
    assert r2.json()["name"] == "置空设备"


# ---------- drills.py 42->41（更新字段置 None） ----------
def test_update_drill_none_field(client, headers):
    did = client.post("/api/drills", json={"title": "置空演练"}, headers=headers["supervisor"]).json()["id"]
    r = client.put(f"/api/drills/{did}", json={"participants": None}, headers=headers["supervisor"])
    assert r.status_code == 200


# ---------- drills.py 76->78（finish 不带 score） ----------
def test_drill_finish_without_score(client, headers):
    did = client.post("/api/drills", json={"title": "无评分演练"}, headers=headers["supervisor"]).json()["id"]
    r = client.post(
        f"/api/drills/{did}/finish",
        json={"evaluate": "表现良好", "summary": "完成"},
        headers=headers["supervisor"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["score"] is None
    assert body["evaluate"] == "表现良好"


# ---------- alarms.py 100->102（确认误报但设备已不存在） ----------
def test_confirm_false_with_missing_device(client, headers, db_session):
    from app.models import Alarm
    alarm = Alarm(device_id=999999, fire_type="ordinary", status="pending", scene="孤儿报警")
    db_session.add(alarm)
    db_session.commit()
    aid = alarm.id
    r = client.post(
        f"/api/alarms/{aid}/confirm",
        json={"result": "false", "false_reason": "对应设备已删除"},
        headers=headers["duty"],
    )
    assert r.status_code == 200
    assert r.json()["alarm"]["status"] == "confirmed_false"
    assert r.json()["emergency"] is None


# ---------- plans.py 109->108（更新预案字段置 None） ----------
def test_update_plan_none_field(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    pid = client.post(
        "/api/plans",
        json={
            "name": "置空预案",
            "area_id": area["id"],
            "actions": [{"action_type": "fire_door", "action_name": "关闭防火门"}],
        },
        headers=headers["supervisor"],
    ).json()["id"]
    r = client.put(f"/api/plans/{pid}", json={"enabled": None}, headers=headers["supervisor"])
    assert r.status_code == 200
    # enabled 置 None 时更新循环跳过，保持创建时的 True
    assert r.json()["enabled"] is True


# ---------- repairs.py 81->85（finish 无有效 device_id，device_id=0 为 falsy 且 int 合法） ----------
def test_finish_repair_without_device(client, headers, db_session):
    from app.models import Repair
    rp = Repair(device_id=0, title="无设备维修", creator="维保员", status="in_progress")
    db_session.add(rp)
    db_session.commit()
    r = client.post(f"/api/repairs/{rp.id}/finish", json={"result": "已处理"}, headers=headers["maintenance"])
    assert r.status_code == 200
    assert r.json()["status"] == "done"


# ---------- repairs.py 83->85（finish 设备行已删） ----------
def test_finish_repair_missing_device_row(client, headers, db_session):
    from app.models import Repair
    rp = Repair(device_id=999999, title="设备已删", creator="维保员", status="in_progress")
    db_session.add(rp)
    db_session.commit()
    r = client.post(f"/api/repairs/{rp.id}/finish", json={"result": "已处理"}, headers=headers["maintenance"])
    assert r.status_code == 200
    assert r.json()["status"] == "done"


# ---------- users.py 61->60（更新用户字段置 None） ----------
def test_update_user_none_field(client, headers):
    uid = client.post(
        "/api/users",
        json={"username": "noneuser", "password": "x", "role": "duty"},
        headers=headers["supervisor"],
    ).json()["id"]
    r = client.put(f"/api/users/{uid}", json={"real_name": None, "is_active": None}, headers=headers["supervisor"])
    assert r.status_code == 200
    assert r.json()["real_name"] is None


# ---------- patrols.py 91->100 与 113->116（无设备异常巡检） ----------
def test_submit_abnormal_patrol_without_device(client, headers):
    pid = client.post(
        "/api/patrols",
        json={"scheduled_date": "2026-09-26"},
        headers=headers["maintenance"],
    ).json()["id"]
    r = client.post(
        f"/api/patrols/{pid}/result",
        json={"status": "abnormal", "result": "无设备巡检异常"},
        headers=headers["maintenance"],
    )
    assert r.status_code == 200
    assert r.json()["status"] == "abnormal"


# ---------- patrols.py 111->113（复用带 patrol_id 的已有维修单） ----------
def test_submit_abnormal_reuses_repair_with_patrol_id(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    dev = client.post(
        "/api/devices",
        json={"device_no": "PAT-LINK", "name": "联动设备", "device_type": "smoke", "area_id": area["id"]},
        headers=headers["supervisor"],
    ).json()
    # 先建一张带 patrol_id 的在修维修单
    p1 = client.post(
        "/api/patrols",
        json={"device_id": dev["id"], "area_id": area["id"]},
        headers=headers["maintenance"],
    ).json()
    rp = client.post(
        "/api/repairs",
        json={"device_id": dev["id"], "title": "带关联维修单", "patrol_id": p1["id"]},
        headers=headers["maintenance"],
    ).json()
    client.post(f"/api/repairs/{rp['id']}/start", headers=headers["maintenance"])
    # 再对同一设备提交异常 -> 命中已有维修单（其 patrol_id 为真值）
    p2 = client.post(
        "/api/patrols",
        json={"device_id": dev["id"], "area_id": area["id"]},
        headers=headers["maintenance"],
    ).json()
    r = client.post(
        f"/api/patrols/{p2['id']}/result",
        json={"status": "abnormal", "result": "再次异常"},
        headers=headers["maintenance"],
    )
    assert r.status_code == 200
    assert r.json()["status"] == "abnormal"