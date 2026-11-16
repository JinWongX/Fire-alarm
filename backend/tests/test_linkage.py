"""联动模块单测：自动联动、手动执行、run 详情含 results。"""
def test_auto_linkage_after_simulate(client, headers, device_in_area0):
    """自动联动：simulate 触发 area0 ordinary -> run+4 条动作且成功。"""
    dev = device_in_area0
    r = client.post(
        "/api/alarms/simulate",
        json={"device_id": dev["id"], "fire_type": "ordinary", "scene": "联动"},
        headers=headers["duty"],
    )
    body = r.json()
    lr = body["linkage_run"]
    assert lr is not None
    assert lr["status"] == "success"
    assert lr["trigger_type"] == "auto"

    detail = client.get(f"/api/linkage/runs/{lr['id']}", headers=headers["duty"])
    assert detail.status_code == 200
    det = detail.json()
    assert det["plan_name"] is not None
    assert det["alarm_id"] == body["alarm"]["id"]
    assert len(det["results"]) == 4
    assert all(x["status"] == "success" for x in det["results"])


def test_no_plan_means_no_auto_linkage(client, headers):
    """区域内无启用预案 -> 不自动联动。"""
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]  # B区一层无预案
    dev = client.get("/api/devices", params={"area_id": area["id"], "page_size": 1}, headers=headers["duty"]).json()["items"][0]
    body = client.post(
        "/api/alarms/simulate",
        json={"device_id": dev["id"], "fire_type": "ordinary"},
        headers=headers["duty"],
    ).json()
    assert body["linkage_run"] is None


def test_disabled_plan_not_auto_executed(client, headers):
    """停用预案不参与自动联动。"""
    # 选无种子预案的区域（A区二层 = area 索引1）
    areas = client.get("/api/areas", headers=headers["duty"]).json()
    area = areas[1]
    client.post(
        "/api/plans",
        json={"name": "停用预案", "area_id": area["id"], "fire_type": "electrical", "actions": [{"action_type": "fire_door", "action_name": "关闭防火门"}], "enabled": False},
        headers=headers["supervisor"],
    )
    dev = client.get("/api/devices", params={"area_id": area["id"], "page_size": 1}, headers=headers["duty"]).json()["items"][0]
    body = client.post(
        "/api/alarms/simulate",
        json={"device_id": dev["id"], "fire_type": "electrical"},
        headers=headers["duty"],
    ).json()
    assert body["linkage_run"] is None


def test_manual_execute_plan(client, headers):
    plan = client.get("/api/plans", headers=headers["duty"]).json()[0]
    r = client.post(f"/api/plans/{plan['id']}/execute", headers=headers["duty"])
    assert r.status_code == 200
    run = r.json()["run"]
    assert run["status"] == "success"
    assert run["trigger_type"] == "manual"

    detail = client.get(f"/api/linkage/runs/{run['id']}", headers=headers["duty"])
    assert detail.status_code == 200
    assert len(detail.json()["results"]) == len(plan["actions"]) > 0


def test_manual_execute_nonexistent_404(client, headers):
    assert client.post("/api/plans/999999/execute", headers=headers["duty"]).status_code == 404


def test_manual_execute_maintenance_403(client, headers):
    plan = client.get("/api/plans", headers=headers["duty"]).json()[0]
    assert client.post(f"/api/plans/{plan['id']}/execute", headers=headers["maintenance"]).status_code == 403


def test_run_detail_nonexistent_404(client, headers):
    assert client.get("/api/linkage/runs/999999", headers=headers["duty"]).status_code == 404


def test_runs_list(client, headers):
    plan = client.get("/api/plans", headers=headers["duty"]).json()[0]
    client.post(f"/api/plans/{plan['id']}/execute", headers=headers["duty"])
    r = client.get("/api/linkage/runs", headers=headers["duty"])
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    item = body["items"][0]
    assert "plan_id" in item and "alarm_id" in item and "trigger_type" in item