#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""冒烟自检脚本：对本地 FastAPI 服务连续调用关键接口，逐步骤打印 PASS/FAIL。"""
import sys

import httpx

BASE = "http://127.0.0.1:8000"
client = httpx.Client(base_url=BASE, timeout=20)
results = []
failed = False


def check(name, cond, detail=""):
    global failed
    results.append((name, bool(cond), detail))
    if not cond:
        failed = True
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")


def login(username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        return None
    return r.json()


def auth(user):
    return {"Authorization": f"Bearer {user['token']}"}


def main():
    # 1. 登录三种角色
    duty = login("duty", "123456")
    maint = login("maintain", "123456")
    admin = login("admin", "123456")
    check("登录 duty", duty is not None)
    check("登录 maintain", maint is not None)
    check("登录 admin", admin is not None)
    if not (duty and maint and admin):
        print("登录失败，中止")
        sys.exit(1)

    h_duty, h_maint, h_admin = auth(duty), auth(maint), auth(admin)

    # 每个角色访问 /me
    check("duty /me", client.get("/api/auth/me", headers=h_duty).status_code == 200)
    check("maintain /me", client.get("/api/auth/me", headers=h_maint).status_code == 200)
    check("admin /me", client.get("/api/auth/me", headers=h_admin).status_code == 200)

    # 无 token 访问 business 接口应 401
    r = client.get("/api/devices")
    check("无token访问被拒绝(401)", r.status_code == 401, f"status={r.status_code}")

    # 2. 设备列表 + 分页 + 过滤
    r = client.get("/api/devices", params={"page": 1, "page_size": 5}, headers=h_duty)
    check("设备列表分页", r.status_code == 200 and r.json()["total"] > 0, f"total={r.json().get('total')}")
    r = client.get("/api/devices", params={"device_type": "smoke"}, headers=h_duty)
    check("设备按类型过滤(smoke)", r.status_code == 200 and r.json()["total"] > 0, f"total={r.json().get('total')}")
    r = client.get("/api/areas", headers=h_duty)
    check("区域列表", r.status_code == 200 and len(r.json()) == 6, f"areas={len(r.json())}")

    devices = client.get("/api/devices", params={"page_size": 100}, headers=h_duty).json()["items"]
    if not devices:
        print("无设备数据，中止")
        sys.exit(1)
    target = devices[0]

    # 3. 模拟报警 -> 设备置alarm + 自动联动
    r = client.post(
        "/api/alarms/simulate",
        json={"device_id": target["id"], "fire_type": "ordinary", "scene": "冒烟自检模拟火警"},
        headers=h_duty,
    )
    sim_ok = r.status_code == 200
    sim = r.json() if sim_ok else {}
    check(
        "模拟报警+自动联动",
        sim_ok and sim.get("alarm") and sim.get("linkage_run"),
        f"status={r.status_code}",
    )
    alarm_id = sim.get("alarm", {}).get("id")

    # 设备状态已置 alarm
    r = client.get(f"/api/devices/{target['id']}", headers=h_duty)
    check("设备状态置alarm", r.status_code == 200 and r.json()["status"] == "alarm", r.json().get("status"))

    # 4. 确认报警(误报需reason 校验)
    r = client.post(f"/api/alarms/{alarm_id}/confirm", json={"result": "false"}, headers=h_duty)
    check("误报缺原因被拒(400)", r.status_code == 400, f"status={r.status_code}")

    # 确认真实火警 -> 创建处置单
    r = client.post(
        f"/api/alarms/{alarm_id}/confirm",
        json={"result": "true"},
        headers=h_duty,
    )
    confirm_ok = r.status_code == 200 and r.json().get("emergency")
    check("确认真实火警+创建处置单", confirm_ok, f"status={r.status_code}")
    emergency_id = r.json().get("emergency", {}).get("id")

    # 5. 处置单 records + close
    r = client.post(
        f"/api/emergencies/{emergency_id}/records",
        json={"time": "2025-09-25 10:00", "content": "现场确认并组织疏散", "person": "值班员"},
        headers=h_duty,
    )
    check("添加处置记录", r.status_code == 200, f"status={r.status_code}")
    r = client.post(f"/api/emergencies/{emergency_id}/close", json={"result": "火已扑灭，人群安全疏散"}, headers=h_duty)
    check("关闭处置单", r.status_code == 200 and r.json()["status"] == "closed", f"status={r.status_code}")

    # 6. 手动执行预案
    plans = client.get("/api/plans", headers=h_admin).json()
    check("预案列表", len(plans) > 0, f"plans={len(plans)}")
    plan_id = plans[0]["id"]
    r = client.post(f"/api/plans/{plan_id}/execute", headers=h_duty)
    check("手动执行预案联动", r.status_code == 200 and r.json().get("run"), f"status={r.status_code}")
    run_id = r.json().get("run", {}).get("id")
    r = client.get(f"/api/linkage/runs/{run_id}", headers=h_duty)
    check(
        "联动run详情含results",
        r.status_code == 200 and len(r.json().get("results", [])) > 0,
        f"results={len(r.json().get('results', []))}",
    )

    # 权限：maintain 不能执行联动(duty/supervisor)    实际上plans execute 需 duty/supervisor，maintain应403
    r = client.post(f"/api/plans/{plan_id}/execute", headers=h_maint)
    check("maintain执行联动被拒(403)", r.status_code == 403, f"status={r.status_code}")

    # 7. 巡检
    r = client.post(
        "/api/patrols",
        json={"device_id": target["id"], "area_id": target["area_id"], "scheduled_date": "2025-09-26"},
        headers=h_maint,
    )
    patrol_ok = r.status_code in (200, 201)
    patrol_id = r.json().get("id") if patrol_ok else None
    check("创建巡检任务", patrol_ok, f"status={r.status_code}")

    # abnormal 巡检 -> 建维修单 + 设备置fault
    r = client.post(
        f"/api/patrols/{patrol_id}/result",
        json={"status": "abnormal", "result": "探测器故障", "suggest": "需更换"},
        headers=h_maint,
    )
    check(
        "异常巡检创建维修单+设备置fault",
        r.status_code == 200 and target["id"] and client.get(f"/api/devices/{target['id']}", headers=h_maint).json()["status"] == "fault",
        f"patrol_status={r.json().get('status')}",
    )

    r = client.get("/api/patrols/summary", headers=h_maint)
    check("巡检summary", r.status_code == 200 and "done_rate" in r.json(), f"status={r.status_code}")

    # 8. 维修流程
    repairs = client.get("/api/repairs", headers=h_maint).json()
    repair_id = next((rp["id"] for rp in repairs if rp["status"] == "pending"), None)
    if repair_id is None:
        print("无 pending 维修单，中止")
        sys.exit(1)
    r = client.post(f"/api/repairs/{repair_id}/start", headers=h_maint)
    check("维修单 start", r.status_code == 200 and r.json()["status"] == "in_progress", f"status={r.json().get('status')}")
    r = client.post(f"/api/repairs/{repair_id}/finish", json={"result": "已修复完成"}, headers=h_maint)
    check(
        "维修完成+设备置normal",
        r.status_code == 200
        and r.json()["status"] == "done"
        and client.get(f"/api/devices/{target['id']}", headers=h_maint).json()["status"] == "normal",
        f"status={r.json().get('status')}",
    )

    # 9. 演练
    r = client.post(
        "/api/drills",
        json={"title": "Q4灭火演练", "drill_type": "灭火演练", "plan_date": "2025-12-01", "organizer": "消防主管", "participants": "全员"},
        headers=h_admin,
    )
    drill_ok = r.status_code in (200, 201)
    drill_id = r.json().get("id") if drill_ok else None
    check("创建演练", drill_ok, f"status={r.status_code}")
    r = client.post(f"/api/drills/{drill_id}/finish", json={"score": 95, "evaluate": "表现优秀", "summary": "应急响应迅速"}, headers=h_admin)
    check("演练完成", r.status_code == 200 and r.json()["status"] == "done", f"status={r.json().get('status')}")

    # 10. dashboard
    r = client.get("/api/stats/dashboard", headers=h_admin)
    dash = r.json()
    check(
        "统计dashboard",
        r.status_code == 200
        and "device_status" in dash
        and "alarm_trend" in dash
        and "false_alarm_rate" in dash
        and "linkage_success_rate" in dash,
        f"status={r.status_code}",
    )

    # 11. 导出 excel / csv
    r = client.get("/api/stats/export", params={"type": "excel", "data": "alarms"}, headers=h_admin)
    check("导出excel", r.status_code == 200 and r.headers.get("content-type", "").startswith("application/vnd") and len(r.content) > 100, f"bytes={len(r.content)}")
    r = client.get("/api/stats/export", params={"type": "csv", "data": "drills"}, headers=h_admin)
    check("导出csv", r.status_code == 200 and "csv" in r.headers.get("content-type", "") and len(r.content) > 10, f"bytes={len(r.content)}")
    r = client.get("/api/stats/alarms", headers=h_admin)
    j = r.json()
    check("报警明细列表", r.status_code == 200 and isinstance(j, dict) and "total" in j and "items" in j, f"status={r.status_code}")

    # 12. 误报流程(校验 false_reason 逻辑)
    r = client.post(
        "/api/alarms/simulate",
        json={"device_id": target["id"], "fire_type": "ordinary", "scene": "误报测试"},
        headers=h_duty,
    )
    fake_id = r.json()["alarm"]["id"] if r.status_code == 200 else None
    r = client.post(f"/api/alarms/{fake_id}/confirm", json={"result": "false", "false_reason": "误触报警按钮"}, headers=h_duty)
    check("误报确认(带原因)", r.status_code == 200 and r.json()["alarm"]["status"] == "confirmed_false", f"status={r.json().get('alarm', {}).get('status')}")

    dstats = client.get("/api/stats/dashboard", headers=h_admin).json()
    check(
        "误报率统计更新",
        dstats["alarm_false"] >= 1 and dstats["false_alarm_rate"] > 0,
        f"false_alarm_rate={dstats.get('false_alarm_rate')}",
    )

    print()
    print("========== 冒烟自检结果 ==========")
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  {detail}")
    print(f"  通过 {sum(1 for _, ok, _ in results if ok)} / {len(results)}")
    print("==================================")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()