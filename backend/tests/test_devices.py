"""设备模块单测：增删改查、分页边界、过滤、枚举/重复/不存在/删除守卫。"""
import pytest


def _create(client, headers, **overrides):
    payload = {
        "device_no": "D-CRUD-001",
        "name": "CRUD烟感",
        "device_type": "smoke",
        "area_id": None,
        **overrides,
    }
    return client.post("/api/devices", json=payload, headers=headers["supervisor"])


def test_create_device_normal(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    r = _create(client, headers, area_id=area["id"])
    assert r.status_code == 201
    body = r.json()
    assert body["device_no"] == "D-CRUD-001"
    assert body["status"] == "normal"
    assert body["device_type"] == "smoke"
    assert body["area_id"] == area["id"]


def test_crud_roundtrip(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    created = _create(client, headers, area_id=area["id"]).json()
    did = created["id"]

    got = client.get(f"/api/devices/{did}", headers=headers["duty"])
    assert got.status_code == 200
    assert got.json()["id"] == did

    upd = client.put(f"/api/devices/{did}", json={"name": "改后名称"}, headers=headers["supervisor"])
    assert upd.status_code == 200
    assert upd.json()["name"] == "改后名称"

    status_upd = client.put(f"/api/devices/{did}/status", json={"status": "masked"}, headers=headers["supervisor"])
    assert status_upd.status_code == 200
    assert status_upd.json()["status"] == "masked"

    deleted = client.delete(f"/api/devices/{did}", headers=headers["supervisor"])
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    gone = client.get(f"/api/devices/{did}", headers=headers["duty"])
    assert gone.status_code == 404


def test_pagination_boundaries(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    for i in range(25):
        _create(client, headers, device_no=f"D-PG-{i:03d}", name=f"设备{i}", area_id=area["id"])

    r1 = client.get("/api/devices", params={"page": 1, "page_size": 10}, headers=headers["duty"])
    r2 = client.get("/api/devices", params={"page": 2, "page_size": 10}, headers=headers["duty"])
    r3 = client.get("/api/devices", params={"page": 3, "page_size": 10}, headers=headers["duty"])
    j1, j2, j3 = r1.json(), r2.json(), r3.json()
    assert len(j1["items"]) == 10 and len(j2["items"]) == 10 and len(j3["items"]) > 0
    ids1 = {x["id"] for x in j1["items"]}
    assert not ids1.intersection(x["id"] for x in j2["items"])

    # 超尾页返回空但不 500
    r_last = client.get("/api/devices", params={"page": 999, "page_size": 10}, headers=headers["duty"])
    assert r_last.status_code == 200 and r_last.json()["items"] == []

    # page_size=0 / 负值边界：不 500
    r0 = client.get("/api/devices", params={"page": 1, "page_size": 0}, headers=headers["duty"])
    rneg = client.get("/api/devices", params={"page": -1, "page_size": -1}, headers=headers["duty"])
    assert r0.status_code == 200
    assert rneg.status_code == 200


def test_filter_by_type_status_area(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    _create(client, headers, device_no="D-F-001", device_type="temp", area_id=area["id"], x=1, y=1)

    r_type = client.get("/api/devices", params={"device_type": "temp"}, headers=headers["duty"])
    assert r_type.status_code == 200 and r_type.json()["total"] >= 1
    assert all(x["device_type"] == "temp" for x in r_type.json()["items"])

    r_status = client.get("/api/devices", params={"status": "alarm"}, headers=headers["duty"])
    assert r_status.status_code == 200

    r_area = client.get("/api/devices", params={"area_id": area["id"], "page_size": 200}, headers=headers["duty"])
    assert r_area.status_code == 200 and r_area.json()["total"] > 0
    assert all(x["area_id"] == area["id"] for x in r_area.json()["items"])


def test_invalid_enum_400(client, headers):
    r = _create(client, headers, device_no="D-BADTYPE", device_type="bogus")
    assert r.status_code == 400

    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    dev = _create(client, headers, area_id=area["id"]).json()
    r_status = client.put(f"/api/devices/{dev['id']}/status", json={"status": "bogus"}, headers=headers["supervisor"])
    assert r_status.status_code == 400


def test_duplicate_device_no_400(client, headers):
    _create(client, headers, device_no="D-DUP")
    r = _create(client, headers, device_no="D-DUP")
    assert r.status_code == 400
    assert "已存在" in r.json()["detail"]


def test_get_nonexistent_404(client, headers):
    r = client.get("/api/devices/999999", headers=headers["duty"])
    assert r.status_code == 404
    r2 = client.put("/api/devices/999999", json={"name": "x"}, headers=headers["supervisor"])
    assert r2.status_code == 404


def test_delete_device_with_alarm_409(client, headers):
    """带报警设备禁止物理删除（修复：避免 500/孤儿数据）。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    dev = _create(client, headers, area_id=area["id"]).json()
    client.post(
        "/api/alarms/simulate",
        json={"device_id": dev["id"], "fire_type": "ordinary", "scene": "删除守卫"},
        headers=headers["duty"],
    )
    r = client.delete(f"/api/devices/{dev['id']}", headers=headers["supervisor"])
    assert r.status_code == 409
    # 设备仍存在
    assert client.get(f"/api/devices/{dev['id']}", headers=headers["duty"]).status_code == 200


def test_list_requires_auth_401(client):
    assert client.get("/api/devices").status_code == 401


def test_create_device_invalid_area_400(client, headers):
    """设备 area_id 必须存在于 areas 表。"""
    r = _create(client, headers, device_no="D-BADAREA", area_id=999999)
    assert r.status_code == 400
    assert "区域" in r.json()["detail"]


def test_update_device_invalid_area_400(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    dev = _create(client, headers, area_id=area["id"]).json()
    r = client.put(f"/api/devices/{dev['id']}", json={"area_id": 999999}, headers=headers["supervisor"])
    assert r.status_code == 400


def test_update_device_invalid_type_400(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    dev = _create(client, headers, area_id=area["id"]).json()
    r = client.put(f"/api/devices/{dev['id']}", json={"device_type": "bogus"}, headers=headers["supervisor"])
    assert r.status_code == 400


def test_status_and_delete_nonexistent_404(client, headers):
    assert client.put("/api/devices/999999/status", json={"status": "normal"}, headers=headers["supervisor"]).status_code == 404
    assert client.delete("/api/devices/999999", headers=headers["supervisor"]).status_code == 404


def test_create_device_coordinate_bounds_400(client, headers):
    """坐标必须落在 0<=x,y<=100，越界应被拒。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    r_high = _create(client, headers, device_no="D-OVR1", area_id=area["id"], x=99999.0, y=99999.0)
    assert r_high.status_code in (400, 422)
    r_neg = _create(client, headers, device_no="D-OVR2", area_id=area["id"], x=-1, y=-1)
    assert r_neg.status_code in (400, 422)
    r_ok = _create(client, headers, device_no="D-OVR3", area_id=area["id"], x=0, y=100)
    assert r_ok.status_code == 201


def test_update_device_coordinate_bounds_400(client, headers):
    """更新坐标越界同样被拒。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    dev = _create(client, headers, area_id=area["id"]).json()
    r = client.put(f"/api/devices/{dev['id']}", json={"x": 101, "y": 120}, headers=headers["supervisor"])
    assert r.status_code in (400, 422)


def test_device_no_too_long_400(client, headers):
    """device_no 超长(>64)应被拒。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    long_no = "X" * 300
    r = _create(client, headers, device_no=long_no, area_id=area["id"])
    assert r.status_code in (400, 422)


def test_device_blank_name_400(client, headers):
    """name 为空串或纯空白应被拒。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    assert _create(client, headers, device_no="D-EM1", name="", area_id=area["id"]).status_code in (400, 422)
    assert _create(client, headers, device_no="D-EM2", name="   ", area_id=area["id"]).status_code in (400, 422)
    assert _create(client, headers, device_no="D-BDN", name="", device_type="smoke").status_code in (400, 422)


def test_update_device_status_field(client, headers):
    """DeviceUpdate 支持直接修改 status（编辑抽屉生效）。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    dev = _create(client, headers, area_id=area["id"]).json()
    assert dev["status"] == "normal"
    r = client.put(f"/api/devices/{dev['id']}", json={"status": "masked"}, headers=headers["supervisor"])
    assert r.status_code == 200
    assert r.json()["status"] == "masked"
    r_bad = client.put(f"/api/devices/{dev['id']}", json={"status": "bogus"}, headers=headers["supervisor"])
    assert r_bad.status_code == 400
    assert client.get(f"/api/devices/{dev['id']}", headers=headers["duty"]).json()["status"] == "masked"


# ---------- keyword 模糊匹配（name / device_no / area.name） ----------
def test_keyword_search_name(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    _create(client, headers, device_no="KW-001", name="走廊烟感", area_id=area["id"])
    _create(client, headers, device_no="KW-002", name="楼道烟感", area_id=area["id"])
    r = client.get("/api/devices", params={"keyword": "走廊"}, headers=headers["duty"])
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert all("走廊" in x["name"] for x in body["items"])


def test_keyword_search_device_no_and_area(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    _create(client, headers, device_no="SN-2026-01", name="关键字设备", area_id=area["id"])
    r_no = client.get("/api/devices", params={"keyword": "SN-2026"}, headers=headers["duty"])
    assert r_no.status_code == 200
    assert r_no.json()["total"] >= 1
    assert all("SN-2026" in x["device_no"] for x in r_no.json()["items"])
    r_area = client.get("/api/devices", params={"keyword": area["name"]}, headers=headers["duty"])
    assert r_area.status_code == 200
    assert r_area.json()["total"] >= 1
    assert all(x["area_id"] == area["id"] for x in r_area.json()["items"])
    # 分页仍生效
    r_page = client.get("/api/devices", params={"keyword": area["name"], "page_size": 2}, headers=headers["duty"])
    assert r_page.status_code == 200
    assert len(r_page.json()["items"]) <= 2
    assert r_page.json()["total"] >= 1


# ---------- 删除守卫：关联巡检 / 维修记录 ----------
def test_delete_device_with_patrol_409(client, headers, db_session):
    from app.models import Patrol
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    dev = _create(client, headers, area_id=area["id"]).json()
    db_session.add(Patrol(device_id=dev["id"], area_id=area["id"], status="pending"))
    db_session.commit()
    r = client.delete(f"/api/devices/{dev['id']}", headers=headers["supervisor"])
    assert r.status_code == 409
    assert "巡检或维修" in r.json()["detail"]


def test_delete_device_with_repair_409(client, headers, db_session):
    from app.models import Repair
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    dev = _create(client, headers, area_id=area["id"]).json()
    db_session.add(Repair(device_id=dev["id"], title="关联维修", status="pending"))
    db_session.commit()
    r = client.delete(f"/api/devices/{dev['id']}", headers=headers["supervisor"])
    assert r.status_code == 409
    assert "巡检或维修" in r.json()["detail"]