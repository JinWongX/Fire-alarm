"""区域模块单测。"""
def test_list_areas(client, headers):
    r = client.get("/api/areas", headers=headers["duty"])
    assert r.status_code == 200
    areas = r.json()
    assert len(areas) == 6
    assert all({"id", "name"} <= set(a) for a in areas)
    assert client.get("/api/areas", headers=headers["supervisor"]).status_code == 200
    assert client.get("/api/areas", headers=headers["maintenance"]).status_code == 200


def test_list_areas_requires_auth(client):
    assert client.get("/api/areas").status_code == 401