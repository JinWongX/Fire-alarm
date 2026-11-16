"""报警模块单测：simulate（产生报警+自动联动）、列表与状态过滤、confirm 分支。"""
import pytest


def _new_pending(client, headers, device_id, fire_type="ordinary", scene="测试报警"):
    return client.post(
        "/api/alarms/simulate",
        json={"device_id": device_id, "fire_type": fire_type, "scene": scene},
        headers=headers["duty"],
    )


def test_simulate_creates_alarm_and_auto_linkage(client, headers, device_in_area0):
    dev = device_in_area0
    r = _new_pending(client, headers, dev["id"], fire_type="ordinary")
    assert r.status_code == 200
    body = r.json()
    assert body["alarm"]["status"] == "pending"
    assert body["alarm"]["device_id"] == dev["id"]
    assert body["alarm"]["fire_type"] == "ordinary"
    # 命中种子普通火灾预案 -> 自动联动
    lr = body["linkage_run"]
    assert lr is not None
    assert lr["status"] == "success"
    assert lr["trigger_type"] == "auto"
    # 设备被置为 alarm
    assert client.get(f"/api/devices/{dev['id']}", headers=headers["duty"]).json()["status"] == "alarm"


def test_simulate_device_not_found_404(client, headers):
    r = client.post(
        "/api/alarms/simulate", json={"device_id": 999999, "fire_type": "ordinary"}, headers=headers["duty"]
    )
    assert r.status_code == 404


def test_simulate_invalid_fire_type_400(client, headers, device_in_area0):
    r = client.post(
        "/api/alarms/simulate", json={"device_id": device_in_area0["id"], "fire_type": "bogus"}, headers=headers["duty"]
    )
    assert r.status_code == 400


def test_simulate_fire_type_other(client, headers, device_in_area0):
    """契约：simulate 允许 fire_type=other（与预案枚举对齐）。"""
    r = client.post(
        "/api/alarms/simulate", json={"device_id": device_in_area0["id"], "fire_type": "other"}, headers=headers["duty"]
    )
    assert r.status_code == 200
    body = r.json()
    assert body["alarm"]["fire_type"] == "other"
    assert body["alarm"]["status"] == "pending"


def test_list_alarms_and_status_filter(client, headers, device_in_area0):
    dev = device_in_area0
    a1 = _new_pending(client, headers, dev["id"]).json()["alarm"]["id"]
    r = _new_pending(client, headers, dev["id"]).json()["alarm"]
    a2 = r["id"]
    client.post(f"/api/alarms/{a1}/confirm", json={"result": "false", "false_reason": "误触"}, headers=headers["duty"])

    all_list = client.get("/api/alarms", params={"page_size": 10}, headers=headers["duty"])
    assert all_list.status_code == 200
    assert all_list.json()["total"] >= 2

    pending = client.get("/api/alarms", params={"status": "pending"}, headers=headers["duty"]).json()
    assert all(x["status"] == "pending" for x in pending["items"])

    confirmed = client.get("/api/alarms", params={"status": "confirmed_false"}, headers=headers["duty"]).json()
    assert any(x["id"] == a1 for x in confirmed["items"])
    # 最新在前
    ids = [x["id"] for x in all_list.json()["items"]]
    assert ids == sorted(ids, reverse=True)


def test_confirm_false_without_reason_400(client, headers, device_in_area0):
    aid = _new_pending(client, headers, device_in_area0["id"]).json()["alarm"]["id"]
    r = client.post(f"/api/alarms/{aid}/confirm", json={"result": "false"}, headers=headers["duty"])
    assert r.status_code == 400
    assert "误报原因" in r.json()["detail"]


def test_confirm_invalid_result_400(client, headers, device_in_area0):
    aid = _new_pending(client, headers, device_in_area0["id"]).json()["alarm"]["id"]
    r = client.post(f"/api/alarms/{aid}/confirm", json={"result": "maybe"}, headers=headers["duty"])
    assert r.status_code == 400


def test_confirm_false_with_reason(client, headers, device_in_area0):
    dev = device_in_area0
    aid = _new_pending(client, headers, dev["id"]).json()["alarm"]["id"]
    r = client.post(
        f"/api/alarms/{aid}/confirm",
        json={"result": "false", "false_reason": "烟雾误触"},
        headers=headers["duty"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["alarm"]["status"] == "confirmed_false"
    assert body["alarm"]["false_reason"] == "烟雾误触"
    assert body["emergency"] is None
    # 设备恢复 normal
    assert client.get(f"/api/devices/{dev['id']}", headers=headers["duty"]).json()["status"] == "normal"


def test_confirm_true_builds_emergency(client, headers, device_in_area0):
    dev = device_in_area0
    aid = _new_pending(client, headers, dev["id"]).json()["alarm"]["id"]
    r = client.post(f"/api/alarms/{aid}/confirm", json={"result": "true"}, headers=headers["duty"])
    assert r.status_code == 200
    body = r.json()
    assert body["alarm"]["status"] == "confirmed_real"
    assert body["emergency"] is not None
    assert body["emergency"]["status"] == "active"


def test_confirm_true_duplicate_single_emergency(client, headers, device_in_area0):
    """同一报警重复确认真实只生成一张处置单（修复：多张处置单缺陷）。"""
    dev = device_in_area0
    aid = _new_pending(client, headers, dev["id"]).json()["alarm"]["id"]
    first = client.post(f"/api/alarms/{aid}/confirm", json={"result": "true"}, headers=headers["duty"]).json()
    second = client.post(f"/api/alarms/{aid}/confirm", json={"result": "true"}, headers=headers["duty"]).json()
    assert first["emergency"]["id"] == second["emergency"]["id"]
    ems = client.get("/api/emergencies", headers=headers["duty"]).json()
    linked = [e for e in ems if e["alarm_id"] == aid]
    assert len(linked) == 1


def test_confirm_nonexistent_404(client, headers):
    r = client.post("/api/alarms/999999/confirm", json={"result": "true"}, headers=headers["duty"])
    assert r.status_code == 404


def test_maintenance_confirm_403(client, headers, device_in_area0):
    aid = _new_pending(client, headers, device_in_area0["id"]).json()["alarm"]["id"]
    r = client.post(f"/api/alarms/{aid}/confirm", json={"result": "true"}, headers=headers["maintenance"])
    assert r.status_code == 403


def test_alarm_device_relation(client, headers, device_in_area0):
    dev = device_in_area0
    aid = _new_pending(client, headers, dev["id"]).json()["alarm"]["id"]
    detail = client.get("/api/alarms", params={"status": "pending"}, headers=headers["duty"]).json()
    item = next(x for x in detail["items"] if x["id"] == aid)
    assert item["device"]["id"] == dev["id"]


# ---------- AL-10：已确认报警的状态守卫（幂等 / 改判 409） ----------
def test_confirm_false_idempotent(client, headers, device_in_area0):
    aid = _new_pending(client, headers, device_in_area0["id"]).json()["alarm"]["id"]
    first = client.post(f"/api/alarms/{aid}/confirm", json={"result": "false", "false_reason": "误触"}, headers=headers["duty"])
    second = client.post(f"/api/alarms/{aid}/confirm", json={"result": "false", "false_reason": "误触"}, headers=headers["duty"])
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["alarm"]["status"] == "confirmed_false"
    assert second.json()["emergency"] is None


def test_confirm_real_then_false_409(client, headers, device_in_area0):
    aid = _new_pending(client, headers, device_in_area0["id"]).json()["alarm"]["id"]
    client.post(f"/api/alarms/{aid}/confirm", json={"result": "true"}, headers=headers["duty"])
    r = client.post(f"/api/alarms/{aid}/confirm", json={"result": "false", "false_reason": "改判"}, headers=headers["duty"])
    assert r.status_code == 409
    assert "改判" in r.json()["detail"]


def test_confirm_false_then_true_409(client, headers, device_in_area0):
    aid = _new_pending(client, headers, device_in_area0["id"]).json()["alarm"]["id"]
    client.post(f"/api/alarms/{aid}/confirm", json={"result": "false", "false_reason": "误触"}, headers=headers["duty"])
    r = client.post(f"/api/alarms/{aid}/confirm", json={"result": "true"}, headers=headers["duty"])
    assert r.status_code == 409


def test_confirm_real_idempotent_without_emergency(client, headers, db_session):
    """confirmed_real 但无处置单的异常数据：重复确认真实幂等返回（防御分支）。"""
    from app.models import Alarm, utcnow
    dev = client.get("/api/devices", params={"page_size": 1}, headers=headers["duty"]).json()["items"][0]
    alarm = Alarm(device_id=dev["id"], fire_type="ordinary", status="confirmed_real", confirm_by="duty", confirm_at=utcnow())
    db_session.add(alarm)
    db_session.commit()
    r = client.post(f"/api/alarms/{alarm.id}/confirm", json={"result": "true"}, headers=headers["duty"])
    assert r.status_code == 200
    assert r.json()["alarm"]["status"] == "confirmed_real"
    assert r.json()["emergency"] is None


def test_confirm_true_reuses_preexisting_emergency(client, headers, device_in_area0, db_session):
    """确认前已有处置单时复用，不重复新建（AL-05 幂等）。"""
    from app.models import Emergency, utcnow
    aid = _new_pending(client, headers, device_in_area0["id"]).json()["alarm"]["id"]
    em = Emergency(alarm_id=aid, title="预置处置单", status="active", start_at=utcnow())
    db_session.add(em)
    db_session.commit()
    r = client.post(f"/api/alarms/{aid}/confirm", json={"result": "true"}, headers=headers["duty"])
    assert r.status_code == 200
    assert r.json()["emergency"]["id"] == em.id
    ems = client.get("/api/emergencies", headers=headers["duty"]).json()
    assert len([e for e in ems if e["alarm_id"] == aid]) == 1


# ---------- AL-09：现场描述落库 ----------
def test_confirm_true_saves_scene(client, headers, device_in_area0):
    aid = _new_pending(client, headers, device_in_area0["id"], scene="原有场景").json()["alarm"]["id"]
    r = client.post(f"/api/alarms/{aid}/confirm", json={"result": "true", "scene": "现场浓烟"}, headers=headers["duty"])
    assert r.status_code == 200
    assert r.json()["alarm"]["scene"] == "现场浓烟"


def test_confirm_true_scene_not_overwritten_when_empty(client, headers, device_in_area0):
    aid = _new_pending(client, headers, device_in_area0["id"], scene="原有场景").json()["alarm"]["id"]
    r = client.post(f"/api/alarms/{aid}/confirm", json={"result": "true", "scene": ""}, headers=headers["duty"])
    assert r.status_code == 200
    assert r.json()["alarm"]["scene"] == "原有场景"


# ---------- AL-05：并发撞唯一处置单的 IntegrityError 兜底 ----------
def test_confirm_true_integrity_error_fallback(db_session, client, headers, device_in_area0):
    """插入处置单撞唯一索引时回查既有单复用（模拟并发）；覆盖 scene 空/非空两分支。"""
    from app.routers.alarms import confirm_alarm
    from app.schemas import AlarmConfirm
    from app.models import Alarm, Emergency
    from sqlalchemy.exc import IntegrityError
    from types import SimpleNamespace

    def run_once(scene):
        dev = device_in_area0
        alarm = Alarm(device_id=dev["id"], fire_type="ordinary", status="pending", scene=None)
        db_session.add(alarm)
        db_session.commit()
        aid = alarm.id
        existing = Emergency(alarm_id=aid, title="并发处置单", status="active")
        db_session.add(existing)
        db_session.commit()

        real_query = db_session.query
        real_commit = db_session.commit
        state = {"q": 0, "c": 0}

        class _EmptyQuery:
            def filter(self, *a, **k):
                return self

            def first(self):
                return None

        def flaky_query(model):
            if model is Emergency:
                state["q"] += 1
                if state["q"] == 1:
                    return _EmptyQuery()
            return real_query(model)

        def flaky_commit():
            state["c"] += 1
            if state["c"] == 1:
                raise IntegrityError("INSERT INTO emergencies", {}, Exception("UNIQUE constraint failed"))
            real_commit()

        db_session.query = flaky_query
        db_session.commit = flaky_commit
        try:
            result = confirm_alarm(
                aid, AlarmConfirm(result="true", scene=scene), db_session, SimpleNamespace(username="duty", id=1)
            )
        finally:
            db_session.query = real_query
            db_session.commit = real_commit
        db_session.expire_all()
        return result, existing, aid

    r1, e1, a1 = run_once("并发现场")
    assert r1["emergency"]["id"] == e1.id
    db_session.query(Emergency).filter(Emergency.alarm_id == a1).delete()
    db_session.query(Alarm).filter(Alarm.id == a1).delete()
    db_session.commit()

    r2, e2, a2 = run_once("")
    assert r2["emergency"]["id"] == e2.id
    assert r2["alarm"].scene is None
    assert db_session.query(Emergency).filter(Emergency.alarm_id == a2).count() == 1
    db_session.query(Alarm).filter(Alarm.id == a2).delete()
    db_session.query(Emergency).filter(Emergency.alarm_id == a2).delete()
    db_session.commit()