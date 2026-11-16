"""处置单模块单测：创建、追加 records、close 闭环。"""
def _new_real_alarm(client, headers, dev_id):
    sim = client.post(
        "/api/alarms/simulate",
        json={"device_id": dev_id, "fire_type": "ordinary"},
        headers=headers["duty"],
    ).json()
    return client.post(
        f"/api/alarms/{sim['alarm']['id']}/confirm",
        json={"result": "true"},
        headers=headers["duty"],
    )


def test_create_emergency_and_confirm_link(client, headers, device_in_area0):
    resp = _new_real_alarm(client, headers, device_in_area0["id"])
    assert resp.status_code == 200
    em = resp.json()["emergency"]
    assert em["status"] == "active"
    body = client.get(f"/api/emergencies/{em['id']}", headers=headers["duty"])
    assert body.status_code == 200
    assert body.json()["alarm"] is not None


def test_add_record(client, headers, device_in_area0):
    em = _new_real_alarm(client, headers, device_in_area0["id"]).json()["emergency"]
    r = client.post(
        f"/api/emergencies/{em['id']}/records",
        json={"time": "2026-09-25 10:00", "content": "现场确认", "person": "值班员"},
        headers=headers["duty"],
    )
    assert r.status_code == 200
    assert r.json()["content"] == "现场确认"

    detail = client.get(f"/api/emergencies/{em['id']}", headers=headers["duty"]).json()
    assert len(detail["records"]) == 1
    assert detail["records"][0]["person"] == "值班员"


def test_close_emergency(client, headers, device_in_area0):
    em = _new_real_alarm(client, headers, device_in_area0["id"]).json()["emergency"]
    r = client.post(f"/api/emergencies/{em['id']}/close", json={"result": "火已扑灭"}, headers=headers["duty"])
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "closed"
    assert body["result"] == "火已扑灭"
    assert body["closed_by"] == "duty"
    assert body["closed_at"] is not None


def test_full_lifecycle(client, headers, device_in_area0):
    em = _new_real_alarm(client, headers, device_in_area0["id"]).json()["emergency"]
    client.post(f"/api/emergencies/{em['id']}/records", json={"time": "t1", "content": "记录1"}, headers=headers["duty"])
    client.post(f"/api/emergencies/{em['id']}/close", json={"result": "处置完毕"}, headers=headers["duty"])
    detail = client.get(f"/api/emergencies/{em['id']}", headers=headers["duty"]).json()
    assert detail["status"] == "closed"
    assert len(detail["records"]) >= 1


def test_emergency_nonexistent_404(client, headers):
    assert client.get("/api/emergencies/999999", headers=headers["duty"]).status_code == 404
    assert client.post("/api/emergencies/999999/records", json={"time": "t", "content": "c"}, headers=headers["duty"]).status_code == 404
    assert client.post("/api/emergencies/999999/close", json={"result": "x"}, headers=headers["duty"]).status_code == 404


def test_maintenance_create_403(client, headers):
    assert client.post("/api/emergencies", json={"title": "越权"}, headers=headers["maintenance"]).status_code == 403


def test_list_emergencies(client, headers, device_in_area0):
    _new_real_alarm(client, headers, device_in_area0["id"])
    ems = client.get("/api/emergencies", headers=headers["duty"])
    assert ems.status_code == 200
    assert len(ems.json()) >= 1


def test_create_emergency_direct(client, headers, device_in_area0):
    """处置单也可由值班员/主管直接创建（不依赖报警确认）。"""
    r = client.post("/api/emergencies", json={"title": "直接创建处置单"}, headers=headers["duty"])
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "active"
    assert body["title"] == "直接创建处置单"
    got = client.get(f"/api/emergencies/{body['id']}", headers=headers["duty"]).json()
    assert got["records"] == []


def test_create_emergency_duplicate_alarm_409(client, headers, db_session):
    """同一报警重复建处置单撞唯一索引 -> 409（AL-05）。"""
    from app.models import Emergency
    db_session.add(Emergency(alarm_id=999999, title="并发处置单", status="active"))
    r = client.post("/api/emergencies", json={"alarm_id": 999999, "title": "重复处置单"}, headers=headers["duty"])
    assert r.status_code == 409
    assert "处置单" in r.json()["detail"]