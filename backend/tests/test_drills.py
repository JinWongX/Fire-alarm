"""演练模块单测：CRUD、finish（score/evaluate/summary）、权限。"""
def _create(client, headers):
    return client.post(
        "/api/drills",
        json={"title": "季度疏散演练", "drill_type": "疏散演练", "organizer": "消防主管", "participants": "全体员工"},
        headers=headers["supervisor"],
    )


def test_create_drill(client, headers):
    r = _create(client, headers)
    assert r.status_code == 201
    assert r.json()["status"] == "planned"


def test_drill_update(client, headers):
    did = _create(client, headers).json()["id"]
    r = client.put(f"/api/drills/{did}", json={"participants": "200人", "process": "疏散并清点"}, headers=headers["supervisor"])
    assert r.status_code == 200
    assert r.json()["participants"] == "200人"


def test_drill_finish(client, headers):
    did = _create(client, headers).json()["id"]
    r = client.post(
        f"/api/drills/{did}/finish",
        json={"score": 95, "evaluate": "反应迅速", "summary": "达成目标"},
        headers=headers["supervisor"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["score"] == 95
    assert body["evaluate"] == "反应迅速"
    assert body["summary"] == "达成目标"


def test_drill_delete(client, headers):
    did = _create(client, headers).json()["id"]
    r = client.delete(f"/api/drills/{did}", headers=headers["supervisor"])
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_drill_list(client, headers):
    _create(client, headers)
    r = client.get("/api/drills", headers=headers["duty"])
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_drill_nonexistent_404(client, headers):
    assert client.put("/api/drills/999999", json={"title": "x"}, headers=headers["supervisor"]).status_code == 404
    assert client.delete("/api/drills/999999", headers=headers["supervisor"]).status_code == 404
    assert client.post("/api/drills/999999/finish", json={"score": 90}, headers=headers["supervisor"]).status_code == 404


def test_non_supervisor_forbidden_403(client, headers):
    for role in ("duty", "maintenance"):
        assert client.post("/api/drills", json={"title": "x"}, headers=headers[role]).status_code == 403, role
    did = _create(client, headers).json()["id"]
    assert client.delete(f"/api/drills/{did}", headers=headers["duty"]).status_code == 403


def test_drill_duration_field(client, headers):
    """演练 duration(分钟, int, 可空) 创建/更新/返回。"""
    r = client.post(
        "/api/drills",
        json={"title": "时长演练", "duration": 45},
        headers=headers["supervisor"],
    )
    assert r.status_code == 201
    assert r.json()["duration"] == 45
    did = r.json()["id"]
    upd = client.put(f"/api/drills/{did}", json={"duration": 60}, headers=headers["supervisor"])
    assert upd.status_code == 200
    assert upd.json()["duration"] == 60


def test_drill_finish_score_out_of_range_400(client, headers):
    did = _create(client, headers).json()["id"]
    for bad in (-1, 101, 250):
        r = client.post(f"/api/drills/{did}/finish", json={"score": bad}, headers=headers["supervisor"])
        assert r.status_code == 400, bad
    ok = client.post(f"/api/drills/{did}/finish", json={"score": 100}, headers=headers["supervisor"])
    assert ok.status_code == 200
    assert ok.json()["score"] == 100