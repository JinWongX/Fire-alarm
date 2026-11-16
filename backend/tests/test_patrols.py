"""巡检模块单测：创建任务、录结果 normal/abnormal、summary done_rate。"""
import pytest


def _create_patrol(client, headers, dev, area_id):
    return client.post(
        "/api/patrols",
        json={"device_id": dev["id"], "area_id": area_id, "scheduled_date": "2026-09-26"},
        headers=headers["maintenance"],
    )


def test_create_patrol(client, headers, device_in_area0):
    dev = device_in_area0
    r = _create_patrol(client, headers, dev, dev["area_id"])
    assert r.status_code == 201
    assert r.json()["status"] == "pending"


def test_submit_normal_result(client, headers, device_in_area0):
    dev = device_in_area0
    pid = _create_patrol(client, headers, dev, dev["area_id"]).json()["id"]
    r = client.post(f"/api/patrols/{pid}/result", json={"status": "normal", "result": "运行正常"}, headers=headers["maintenance"])
    assert r.status_code == 200
    assert r.json()["status"] == "normal"
    assert r.json()["patrol_time"] is not None
    # 设备保持 normal
    assert client.get(f"/api/devices/{dev['id']}", headers=headers["duty"]).json()["status"] == "normal"


def test_submit_abnormal_creates_repair_and_fault(client, headers, new_device):
    dev = new_device()
    pid = _create_patrol(client, headers, dev, dev["area_id"]).json()["id"]
    r = client.post(
        f"/api/patrols/{pid}/result",
        json={"status": "abnormal", "result": "探测器故障", "suggest": "需更换"},
        headers=headers["maintenance"],
    )
    assert r.status_code == 200
    assert r.json()["status"] == "abnormal"
    # 设备置 fault
    assert client.get(f"/api/devices/{dev['id']}", headers=headers["duty"]).json()["status"] == "fault"
    # 自动生成维修单
    repairs = client.get("/api/repairs", headers=headers["maintenance"]).json()
    assert any(x["patrol_id"] == pid for x in repairs)


def test_submit_abnormal_dedup_with_active_repair(client, headers, device_in_area0):
    """设备已有 pending/in_progress 维修单时，异常巡检不再新建重复单（复用该单）。"""
    dev = device_in_area0
    # 种子已为设备生成一张 in_progress 维修单
    before = [x for x in client.get("/api/repairs", headers=headers["maintenance"]).json() if x["device_id"] == dev["id"] and x["status"] in ("pending", "in_progress")]
    assert before, "前置：设备应存在活动维修单"
    active_id = before[0]["id"]
    pid = _create_patrol(client, headers, dev, dev["area_id"]).json()["id"]
    r = client.post(
        f"/api/patrols/{pid}/result",
        json={"status": "abnormal", "result": "再次异常", "suggest": "复查"},
        headers=headers["maintenance"],
    )
    assert r.status_code == 200
    after = [x for x in client.get("/api/repairs", headers=headers["maintenance"]).json() if x["device_id"] == dev["id"] and x["status"] in ("pending", "in_progress")]
    # 不新建重复单，仍只有同一张活动维修单
    assert len(after) == 1
    assert after[0]["id"] == active_id
    assert all(x["id"] == active_id for x in after)


def test_invalid_result_400(client, headers, device_in_area0):
    dev = device_in_area0
    pid = _create_patrol(client, headers, dev, dev["area_id"]).json()["id"]
    r = client.post(f"/api/patrols/{pid}/result", json={"status": "bogus"}, headers=headers["maintenance"])
    assert r.status_code == 400


def test_submit_nonexistent_404(client, headers):
    assert client.post("/api/patrols/999999/result", json={"status": "normal"}, headers=headers["maintenance"]).status_code == 404


def test_duty_create_patrol_403(client, headers, device_in_area0):
    dev = device_in_area0
    r = client.post("/api/patrols", json={"device_id": dev["id"], "area_id": dev["area_id"]}, headers=headers["duty"])
    assert r.status_code == 403


def test_summary_done_rate(client, headers, device_in_area0):
    dev = device_in_area0
    pid = _create_patrol(client, headers, dev, dev["area_id"]).json()["id"]
    client.post(f"/api/patrols/{pid}/result", json={"status": "normal"}, headers=headers["maintenance"])
    r = client.get("/api/patrols/summary", headers=headers["maintenance"])
    assert r.status_code == 200
    body = r.json()
    assert "total" in body and "done" in body and "done_rate" in body
    assert body["total"] > 0
    assert body["done"] >= 1
    assert 0 <= body["done_rate"] <= 100


def test_summary_empty_no_div0(client, db_session, headers):
    """空巡检数据时 done_rate=0.0 且不抛除零错误。"""
    from app.models import Patrol
    db_session.query(Patrol).delete()
    db_session.commit()
    r = client.get("/api/patrols/summary", headers=headers["maintenance"])
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert r.json()["done_rate"] == 0.0


def test_submit_abnormal_without_description_400(client, headers, device_in_area0):
    """异常巡检必须填写 result 或 suggest。"""
    dev = device_in_area0
    pid = _create_patrol(client, headers, dev, dev["area_id"]).json()["id"]
    r = client.post(f"/api/patrols/{pid}/result", json={"status": "abnormal"}, headers=headers["maintenance"])
    assert r.status_code == 400
    assert "异常说明" in r.json()["detail"]


def test_overdue_computed_in_list(client, headers, device_in_area0):
    """scheduled_date < 今天 且 pending -> overdue=True；未来日期 -> False。"""
    dev = device_in_area0
    past = client.post(
        "/api/patrols",
        json={"device_id": dev["id"], "area_id": dev["area_id"], "scheduled_date": "2000-01-01"},
        headers=headers["maintenance"],
    ).json()
    future = client.post(
        "/api/patrols",
        json={"device_id": dev["id"], "area_id": dev["area_id"], "scheduled_date": "2099-12-31"},
        headers=headers["maintenance"],
    ).json()
    items = {p["id"]: p for p in client.get("/api/patrols", headers=headers["maintenance"]).json()}
    assert items[past["id"]]["overdue"] is True
    assert items[future["id"]]["overdue"] is False


def test_overdue_count_in_summary(client, headers, device_in_area0):
    """summary 返回 overdue 计数（过去 pending 未完成）。"""
    dev = device_in_area0
    client.post(
        "/api/patrols",
        json={"device_id": dev["id"], "area_id": dev["area_id"], "scheduled_date": "2000-01-01"},
        headers=headers["maintenance"],
    )
    body = client.get("/api/patrols/summary", headers=headers["maintenance"]).json()
    assert body["overdue"] >= 1


def test_is_overdue_guard_for_weird_date():
    """scheduled_date 类型异常时不抛错、按非逾期处理。"""
    from app.routers.patrols import _is_overdue
    from types import SimpleNamespace
    assert _is_overdue(SimpleNamespace(status="pending", scheduled_date=123)) is False
    assert _is_overdue(SimpleNamespace(status="done", scheduled_date="2000-01-01")) is False
    assert _is_overdue(SimpleNamespace(status="pending", scheduled_date=None)) is False


# ---------- AL-11：巡检提交状态机守卫 ----------
def test_submit_same_result_idempotent(client, headers, device_in_area0):
    dev = device_in_area0
    pid = _create_patrol(client, headers, dev, dev["area_id"]).json()["id"]
    first = client.post(f"/api/patrols/{pid}/result", json={"status": "normal", "result": "正常"}, headers=headers["maintenance"])
    second = client.post(f"/api/patrols/{pid}/result", json={"status": "normal", "result": "正常"}, headers=headers["maintenance"])
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["status"] == "normal"


def test_submit_changed_result_409(client, headers, device_in_area0):
    dev = device_in_area0
    pid = _create_patrol(client, headers, dev, dev["area_id"]).json()["id"]
    client.post(f"/api/patrols/{pid}/result", json={"status": "normal"}, headers=headers["maintenance"])
    r = client.post(f"/api/patrols/{pid}/result", json={"status": "abnormal", "result": "改判"}, headers=headers["maintenance"])
    assert r.status_code == 409


# ---------- AL-06：并发撞唯一 patrol_id 的 IntegrityError 兜底 ----------
def test_submit_result_unique_conflict_reuses_existing(db_session, client, headers, new_device):
    from app.routers.patrols import submit_result
    from app.schemas import PatrolResult
    from app.models import Patrol, Repair
    from types import SimpleNamespace

    dev = new_device()
    patrol = Patrol(device_id=dev["id"], area_id=dev["area_id"], status="pending", scheduled_date="2026-09-26")
    db_session.add(patrol)
    db_session.commit()
    # 预置一张 patrol_id 指向该巡检、但设备不同的维修单（模拟并发方已插入）
    existing = Repair(patrol_id=patrol.id, device_id=0, title="并发维修单", creator="维保员", status="pending")
    db_session.add(existing)
    db_session.commit()

    result = submit_result(
        patrol.id,
        PatrolResult(status="abnormal", result="并发异常", suggest="说明"),
        db_session,
        SimpleNamespace(username="maintain", id=2),
    )
    assert result.status == "abnormal"
    repairs = db_session.query(Repair).filter(Repair.patrol_id == patrol.id).all()
    assert len(repairs) == 1
    db_session.refresh(patrol)
    assert patrol.status == "abnormal"