"""统计模块单测：dashboard 关键字段、比值数学正确、export excel/csv。"""
def _simulate(client, headers, dev_id, scene):
    return client.post(
        "/api/alarms/simulate",
        json={"device_id": dev_id, "fire_type": "ordinary", "scene": scene},
        headers=headers["duty"],
    ).json()


def test_dashboard_key_fields(client, headers):
    r = client.get("/api/stats/dashboard", headers=headers["supervisor"])
    assert r.status_code == 200
    dash = r.json()
    for key in (
        "device_status", "alarm_trend", "false_alarm_rate", "patrol_done_rate",
        "linkage_success_rate", "alarm_total", "alarm_true", "alarm_false",
        "device_total", "plan_total", "drill_total", "emergency_total", "recent_alarms",
    ):
        assert key in dash, key


def test_dashboard_rates_math(client, headers, device_in_area0):
    """误报率/巡检完成率/联动成功率数学正确（无除零）。"""
    dev = device_in_area0

    # 1 条真实报警确认 -> confirmed_real；1 条误报确认 -> confirmed_false
    real = _simulate(client, headers, dev["id"], "真实")
    client.post(f"/api/alarms/{real['alarm']['id']}/confirm", json={"result": "true"}, headers=headers["duty"])
    false = _simulate(client, headers, dev["id"], "误报")
    client.post(f"/api/alarms/{false['alarm']['id']}/confirm", json={"result": "false", "false_reason": "误触"}, headers=headers["duty"])

    # 创建巡检并完成（normal）
    area = client.get("/api/areas", headers=headers["duty"]).json()[0]
    p = client.post("/api/patrols", json={"device_id": dev["id"], "area_id": area["id"]}, headers=headers["maintenance"]).json()
    client.post(f"/api/patrols/{p['id']}/result", json={"status": "normal"}, headers=headers["maintenance"])

    dash = client.get("/api/stats/dashboard", headers=headers["supervisor"]).json()
    alarm_total = dash["alarm_total"]
    assert alarm_total >= 2
    expected_false_rate = round(dash["alarm_false"] / alarm_total * 100, 1)
    expected_true = dash["alarm_total"] - dash["alarm_false"]
    assert dash["alarm_true"] == expected_true
    assert dash["false_alarm_rate"] == expected_false_rate
    assert dash["false_alarm_rate"] > 0

    patrol_total = dash["patrol_done_rate"]
    assert 0 <= patrol_total <= 100
    assert isinstance(dash["linkage_success_rate"], (int, float))
    assert dash["alarm_trend"][0]["count"] >= 0
    assert len(dash["alarm_trend"]) == 30


def test_dashboard_no_alarms_not_zero_division(client, db_session, headers):
    """清空报警/联动数据后比率字段为 0 而非抛除零错误。"""
    from app.models import Alarm, LinkageResult, LinkageRun
    db_session.query(LinkageResult).delete()
    db_session.query(LinkageRun).delete()
    db_session.query(Alarm).delete()
    db_session.commit()
    dash = client.get("/api/stats/dashboard", headers=headers["supervisor"]).json()
    assert dash["alarm_total"] == 0
    assert dash["false_alarm_rate"] == 0.0
    assert dash["linkage_success_rate"] == 0.0


def test_dashboard_device_status_counts(client, headers, device_in_area0):
    dev = device_in_area0
    _simulate(client, headers, dev["id"], "置alarm")
    dash = client.get("/api/stats/dashboard", headers=headers["supervisor"]).json()
    status = dash["device_status"]
    assert status["alarm"] >= 1
    assert sum(status.values()) == dash["device_total"]


def test_export_excel_content_type(client, headers):
    r = client.get("/api/stats/export", params={"type": "excel", "data": "alarms"}, headers=headers["supervisor"])
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers.get("content-type", "")
    assert len(r.content) > 100


def test_export_csv_content_type(client, headers):
    r = client.get("/api/stats/export", params={"type": "csv", "data": "patrols"}, headers=headers["supervisor"])
    assert r.status_code == 200
    assert "csv" in r.headers.get("content-type", "")
    assert len(r.content) > 10


def test_export_invalid_type_400(client, headers):
    r = client.get("/api/stats/export", params={"type": "pdf", "data": "alarms"}, headers=headers["supervisor"])
    assert r.status_code == 400


def test_export_invalid_data_400(client, headers):
    r = client.get("/api/stats/export", params={"type": "excel", "data": "users"}, headers=headers["supervisor"])
    assert r.status_code == 400


def test_stats_requires_auth(client):
    assert client.get("/api/stats/dashboard").status_code == 401
    assert client.get("/api/stats/export", params={"type": "csv", "data": "alarms"}).status_code == 401


def test_dashboard_time_range_filter(client, headers, device_in_area0):
    """dashboard 支持 from/to 时间筛选报警。"""
    _simulate(client, headers, device_in_area0["id"], "范围测试")
    total = client.get("/api/stats/dashboard", headers=headers["supervisor"]).json()["alarm_total"]
    assert total >= 1
    # 未来时间段应过滤掉全部报警，且 from==to 时为 1 天窗口
    future = client.get(
        "/api/stats/dashboard", params={"from": "3000-01-01", "to": "3000-01-01"}, headers=headers["supervisor"]
    )
    assert future.status_code == 200
    assert future.json()["alarm_total"] == 0
    assert len(future.json()["alarm_trend"]) == 1


def test_dashboard_trend_from_without_to(client, headers, device_in_area0):
    """仅给 from 时趋势天数 = (今天-from)+1，而非固定 30 天（AL-33）。"""
    from datetime import datetime, timedelta
    from app.models import utcnow
    _simulate(client, headers, device_in_area0["id"], "from-only")
    from_date = (utcnow().date() - timedelta(days=5)).strftime("%Y-%m-%d")
    dash = client.get("/api/stats/dashboard", params={"from": from_date}, headers=headers["supervisor"]).json()
    expected = (utcnow().date() - datetime.strptime(from_date, "%Y-%m-%d").date()).days + 1
    assert expected == 6
    assert len(dash["alarm_trend"]) == expected


def test_dashboard_invalid_date_400(client, headers):
    r = client.get("/api/stats/dashboard", params={"from": "2026/09/01"}, headers=headers["supervisor"])
    assert r.status_code == 400
    assert "YYYY-MM-DD" in r.json()["detail"]


def test_export_time_range_filter(client, headers, device_in_area0):
    """export 支持 from/to 时间筛选。"""
    _simulate(client, headers, device_in_area0["id"], "导出范围")
    r_future = client.get(
        "/api/stats/export",
        params={"type": "csv", "data": "alarms", "from": "3000-01-01", "to": "3000-12-31"},
        headers=headers["supervisor"],
    )
    assert r_future.status_code == 200
    # 只含表头（无数据行）
    assert len(r_future.content.decode("utf-8-sig").strip().splitlines()) == 1


def test_stats_alarms_list_supervisor_only(client, headers, device_in_area0):
    """/api/stats/alarms 报警明细仅主管可见，返回 {total, items} 结构。"""
    _simulate(client, headers, device_in_area0["id"], "明细权限")
    r = client.get("/api/stats/alarms", headers=headers["supervisor"])
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j, dict) and "total" in j and "items" in j
    assert j["total"] >= 1
    assert any(x["device_id"] if "device_id" in x else x["id"] for x in j["items"])
    assert client.get("/api/stats/alarms", headers=headers["duty"]).status_code == 403
    assert client.get("/api/stats/alarms", headers=headers["maintenance"]).status_code == 403


def test_export_drills_csv(client, headers):
    from urllib.parse import unquote
    r = client.get("/api/stats/export", params={"type": "csv", "data": "drills"}, headers=headers["supervisor"])
    assert r.status_code == 200
    lines = r.content.decode("utf-8-sig").strip().splitlines()
    assert len(lines) >= 2  # 表头 + 数据
    assert "演练记录" in unquote(r.headers.get("content-disposition", ""))


def test_export_patrols_with_date_range(client, headers):
    """巡检导出支持 from/to 日期筛选。"""
    r = client.get(
        "/api/stats/export",
        params={"type": "csv", "data": "patrols", "from": "2000-01-01", "to": "2000-12-31"},
        headers=headers["supervisor"],
    )
    assert r.status_code == 200
    # 未来段内无巡检 -> 仅表头
    assert len(r.content.decode("utf-8-sig").strip().splitlines()) == 1


def test_export_drills_with_date_range(client, headers):
    """演练导出支持 from/to 日期筛选。"""
    r = client.get(
        "/api/stats/export",
        params={"type": "csv", "data": "drills", "from": "3000-01-01", "to": "3000-12-31"},
        headers=headers["supervisor"],
    )
    assert r.status_code == 200
    assert len(r.content.decode("utf-8-sig").strip().splitlines()) == 1