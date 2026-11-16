"""预案模块单测：CRUD、actions 结构、权限（非主管-403）。"""
import pytest

ACTIONS = [
    {"action_type": "smoke_exhaust", "action_name": "启动排烟风机"},
    {"action_type": "fire_door", "action_name": "关闭防火门"},
]


def _create(client, headers, area, **overrides):
    payload = {
        "name": "测试预案",
        "area_id": area["id"],
        "fire_type": "ordinary",
        "actions": ACTIONS,
        "enabled": True,
        **overrides,
    }
    return client.post("/api/plans", json=payload, headers=headers["supervisor"])


def test_list_actions_structure(client, headers):
    r = client.get("/api/plans/actions", headers=headers["duty"])
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert {"smoke_exhaust", "fire_door", "emergency_light", "broadcast"} <= set(r.json())


def test_create_plan_with_actions(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]  # 该区域无种子预案
    r = _create(client, headers, area)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "测试预案"
    assert len(body["actions"]) == 2
    assert body["enabled"] is True
    assert body["actions"][0]["action_type"] == "smoke_exhaust"


def test_plan_crud(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    pid = _create(client, headers, area).json()["id"]

    assert client.get("/api/plans", headers=headers["duty"]).status_code == 200

    upd = client.put(
        f"/api/plans/{pid}",
        json={"name": "改后预案", "enabled": False},
        headers=headers["supervisor"],
    )
    assert upd.status_code == 200
    assert upd.json()["name"] == "改后预案"
    assert upd.json()["enabled"] is False

    deleted = client.delete(f"/api/plans/{pid}", headers=headers["supervisor"])
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True


def test_plan_update_actions_array(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    pid = _create(client, headers, area).json()["id"]
    upd = client.put(
        f"/api/plans/{pid}",
        json={"actions": [{"action_type": "broadcast", "action_name": "启动广播"}]},
        headers=headers["supervisor"],
    )
    assert upd.status_code == 200
    assert upd.json()["actions"] == [{"action_type": "broadcast", "action_name": "启动广播"}]


def test_plan_nonexistent_404(client, headers):
    assert client.put("/api/plans/999999", json={"name": "x"}, headers=headers["supervisor"]).status_code == 404
    assert client.delete("/api/plans/999999", headers=headers["supervisor"]).status_code == 404


def test_non_supervisor_forbidden_403(client, headers, area0):
    free_area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    for role in ("duty", "maintenance"):
        r = client.post("/api/plans", json={"name": "x", "area_id": area0["id"]}, headers=headers[role])
        assert r.status_code == 403, role

    # 非主管更新/删除
    pid = _create(client, headers, free_area).json()["id"]
    assert client.put(f"/api/plans/{pid}", json={"name": "x"}, headers=headers["duty"]).status_code == 403
    assert client.delete(f"/api/plans/{pid}", headers=headers["maintenance"]).status_code == 403


def test_plan_area_fire_type_unique_409(client, headers):
    """同一区域同一火灾类型只允许一条预案。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    assert _create(client, headers, area).status_code == 201
    dup = _create(client, headers, area, name="重复预案")
    assert dup.status_code == 409
    assert "已存在" in dup.json()["detail"]
    # 不同火灾类型可共存
    r = _create(client, headers, area, name="电气预案", fire_type="electrical")
    assert r.status_code == 201


def test_plan_fire_type_other_enum(client, headers):
    """火灾类型枚举新增 other。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    r = _create(client, headers, area, fire_type="other")
    assert r.status_code == 201
    assert r.json()["fire_type"] == "other"


def test_plan_min_one_action_400(client, headers):
    """预案至少需要一条联动动作，否则 400。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    r = client.post(
        "/api/plans",
        json={"name": "空动作预案", "area_id": area["id"], "fire_type": "oil", "actions": []},
        headers=headers["supervisor"],
    )
    assert r.status_code == 400
    assert "至少需要" in r.json()["detail"]


def test_plan_created_by_is_current_user(client, headers, db_session):
    from app.models import User
    admin = db_session.query(User).filter(User.username == "admin").first()
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    plan = _create(client, headers, area).json()
    assert plan["created_by"] == admin.id


def test_plan_invalid_fire_type_400(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    r = client.post(
        "/api/plans",
        json={"name": "坏类型", "area_id": area["id"], "fire_type": "bogus", "actions": ACTIONS},
        headers=headers["supervisor"],
    )
    assert r.status_code == 400
    assert "火灾类型" in r.json()["detail"]


def test_plan_action_missing_fields_400(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    r = client.post(
        "/api/plans",
        json={"name": "缺字段动作", "area_id": area["id"], "actions": [{"action_type": "", "action_name": "x"}]},
        headers=headers["supervisor"],
    )
    assert r.status_code == 400
    assert "action_type" in r.json()["detail"]


def test_update_plan_to_conflicting_unique_409(client, headers):
    """把预案改为已有区域+火灾类型组合时返回 409。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    _create(client, headers, area, name="第一预案", fire_type="ordinary")
    second = _create(client, headers, area, name="第二预案", fire_type="oil").json()
    r = client.put(
        f"/api/plans/{second['id']}",
        json={"fire_type": "ordinary"},
        headers=headers["supervisor"],
    )
    assert r.status_code == 409


def test_check_unique_none_fire_type_returns(db_session):
    """_check_unique 对 fire_type=None 直接返回（不查库）。"""
    from app.routers.plans import _check_unique
    _check_unique(db_session, 1, None)


def test_plan_invalid_action_type_400(client, headers):
    """联动动作类型必须在 ACTION_TYPES 内（AL-29）。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    r = client.post(
        "/api/plans",
        json={"name": "坏动作", "area_id": area["id"], "actions": [{"action_type": "teleport", "action_name": "瞬移"}]},
        headers=headers["supervisor"],
    )
    assert r.status_code == 400
    assert "动作类型" in r.json()["detail"]


def test_create_plan_integrity_error_409(db_session, client, headers):
    """并发撞唯一索引（事务内预置冲突）转 409 而非 500（AL-07）。"""
    from app.models import Plan
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    db_session.add(Plan(name="并发冲突预案", area_id=area["id"], fire_type="ordinary", actions=[]))
    r = client.post(
        "/api/plans",
        json={"name": "新预案", "area_id": area["id"], "fire_type": "ordinary", "actions": ACTIONS},
        headers=headers["supervisor"],
    )
    assert r.status_code == 409
    assert "已存在" in r.json()["detail"]
    # 回滚后不残留半成品
    assert db_session.query(Plan).filter(Plan.name == "新预案").count() == 0


def test_update_plan_integrity_error_409(db_session, client, headers):
    """更新撞唯一索引转 409（AL-07）。"""
    from app.models import Plan
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    p1 = _create(client, headers, area, name="P1", fire_type="oil").json()
    # 事务内预置"并发方未提交"的冲突预案：预查不可见，提交时撞唯一索引
    db_session.add(Plan(name="并发冲突预案", area_id=area["id"], fire_type="electrical", actions=[]))
    r = client.put(f"/api/plans/{p1['id']}", json={"fire_type": "electrical"}, headers=headers["supervisor"])
    assert r.status_code == 409
    # 更新未生效：p1 仍为 oil；预置冲突行随回滚消失
    plans = {p["id"]: p for p in client.get("/api/plans", headers=headers["duty"]).json()}
    assert plans[p1["id"]]["fire_type"] == "oil"
    assert db_session.query(Plan).filter(Plan.name == "并发冲突预案").count() == 0


def test_delete_plan_with_run_409(client, headers):
    """有联动执行记录的预案禁止删除（AL-08）。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    pid = client.post(
        "/api/plans",
        json={"name": "执行过的预案", "area_id": area["id"], "fire_type": "ordinary", "actions": [{"action_type": "broadcast", "action_name": "广播"}]},
        headers=headers["supervisor"],
    ).json()["id"]
    client.post(f"/api/plans/{pid}/execute", headers=headers["duty"])
    r = client.delete(f"/api/plans/{pid}", headers=headers["supervisor"])
    assert r.status_code == 409
    assert "联动执行记录" in r.json()["detail"]