"""维修模块单测：start、finish（设备恢复 normal）、重复单 409、越权 403。"""
import time


def _fresh_device(client, headers):
    """创建一台无活跃维修单的设备，规避种子 in_progress 维修单的 409 冲突。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    r = client.post(
        "/api/devices",
        json={"device_no": f"RP-{time.time_ns()}", "name": "维修测试设备", "device_type": "smoke", "area_id": area["id"]},
        headers=headers["supervisor"],
    )
    r.raise_for_status()
    return r.json()


def _new_repair(client, headers, dev_id):
    return client.post(
        "/api/repairs",
        json={"device_id": dev_id, "title": "设备故障维修", "description": "需要更换零件"},
        headers=headers["maintenance"],
    )


def test_create_and_start_repair(client, headers):
    dev = _fresh_device(client, headers)
    rp = _new_repair(client, headers, dev["id"])
    assert rp.status_code == 201
    assert rp.json()["status"] == "pending"

    start = client.post(f"/api/repairs/{rp.json()['id']}/start", headers=headers["maintenance"])
    assert start.status_code == 200
    assert start.json()["status"] == "in_progress"


def test_duplicate_active_repair_409(client, headers):
    """同一设备已存在 pending/in_progress 维修单时新建返回 409。"""
    dev = _fresh_device(client, headers)
    assert _new_repair(client, headers, dev["id"]).status_code == 201
    dup = _new_repair(client, headers, dev["id"])
    assert dup.status_code == 409
    assert "已有" in dup.json()["detail"]


def test_finish_repair_restores_device(client, headers):
    """维修完成 -> 设备恢复 normal。"""
    dev = _fresh_device(client, headers)
    rp = _new_repair(client, headers, dev["id"]).json()
    assert client.post(f"/api/repairs/{rp['id']}/start", headers=headers["maintenance"]).status_code == 200
    finish = client.post(f"/api/repairs/{rp['id']}/finish", json={"result": "已修复"}, headers=headers["maintenance"])
    assert finish.status_code == 200
    assert finish.json()["status"] == "done"
    assert finish.json()["closed_at"] is not None
    assert client.get(f"/api/devices/{dev['id']}", headers=headers["duty"]).json()["status"] == "normal"


def test_start_finish_nonexistent_404(client, headers):
    assert client.post("/api/repairs/999999/start", headers=headers["maintenance"]).status_code == 404
    assert client.post("/api/repairs/999999/finish", json={"result": "x"}, headers=headers["maintenance"]).status_code == 404


def test_duty_start_repair_403(client, headers):
    dev = _fresh_device(client, headers)
    rp = _new_repair(client, headers, dev["id"]).json()
    assert client.post(f"/api/repairs/{rp['id']}/start", headers=headers["duty"]).status_code == 403


def test_list_repairs(client, headers):
    dev = _fresh_device(client, headers)
    _new_repair(client, headers, dev["id"])
    r = client.get("/api/repairs", headers=headers["maintenance"])
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_create_repair_nonexistent_device_404(client, headers):
    r = client.post(
        "/api/repairs",
        json={"device_id": 999999, "title": "孤儿维修"},
        headers=headers["maintenance"],
    )
    assert r.status_code == 404


# ---------- AL-11：维修状态机守卫 ----------
def test_start_in_progress_repair_409(client, headers):
    dev = _fresh_device(client, headers)
    rp = _new_repair(client, headers, dev["id"]).json()
    assert client.post(f"/api/repairs/{rp['id']}/start", headers=headers["maintenance"]).status_code == 200
    r = client.post(f"/api/repairs/{rp['id']}/start", headers=headers["maintenance"])
    assert r.status_code == 409
    assert "不允许启动" in r.json()["detail"]


def test_finish_pending_repair_409(client, headers):
    dev = _fresh_device(client, headers)
    rp = _new_repair(client, headers, dev["id"]).json()
    r = client.post(f"/api/repairs/{rp['id']}/finish", json={"result": "直接完成"}, headers=headers["maintenance"])
    assert r.status_code == 409
    assert "不允许完成" in r.json()["detail"]


def test_finish_done_repair_409(client, headers):
    dev = _fresh_device(client, headers)
    rp = _new_repair(client, headers, dev["id"]).json()
    client.post(f"/api/repairs/{rp['id']}/start", headers=headers["maintenance"])
    assert client.post(f"/api/repairs/{rp['id']}/finish", json={"result": "已完成"}, headers=headers["maintenance"]).status_code == 200
    r = client.post(f"/api/repairs/{rp['id']}/finish", json={"result": "再次完成"}, headers=headers["maintenance"])
    assert r.status_code == 409


# ---------- AL-06：repairs.patrol_id 唯一索引冲突 409 ----------
def test_create_repair_duplicate_patrol_id_409(client, headers, db_session):
    from app.models import Patrol, Repair
    dev = _fresh_device(client, headers)
    patrol = Patrol(device_id=dev["id"], area_id=dev["area_id"], status="pending")
    db_session.add(patrol)
    db_session.commit()
    # 已有一张其他设备的维修单占用该 patrol_id（模拟并发方已插入）
    db_session.add(Repair(patrol_id=patrol.id, device_id=0, title="已占用", status="pending"))
    db_session.commit()
    r = client.post(
        "/api/repairs",
        json={"device_id": dev["id"], "title": "重复关联", "patrol_id": patrol.id},
        headers=headers["maintenance"],
    )
    assert r.status_code == 409
    assert "维修单" in r.json()["detail"]