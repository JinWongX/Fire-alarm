#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
功能可用性审计 —— 端到端全流程测试
===================================
串接核心业务完整流程（独立端口 8003 + 临时 sqlite 库，跑完关闭，不影响生产 8000）：

  登录主管 -> 新增设备 -> 模拟报警 -> 验证自动联动4动作 -> 确认真实火警
  -> 创建处置单自动生成 -> 追加处置记录 -> 处置闭环
  -> 创建异常巡检 -> 验证自动维修单+设备fault -> 维修完成设备normal
  -> 创建演练 -> 完成(评分) -> 统计dashboard 数据一致性 -> 导出 excel/csv

每一步断言跨模块数据一致性（报警/设备/联动/处置/巡检/维修/演练/统计）。

调用方式：在 backend 目录执行  python scripts/e2e_test.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

import httpx

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "127.0.0.1"
PORT = 8003
BASE = f"http://{HOST}:{PORT}"

PROC = None
_TMPDIR = None

steps: list[dict] = []


def step(title, expect, actual, ok):
    steps.append({"step": title, "expected": expect, "actual": str(actual)[:120], "ok": bool(ok)})
    print(f"{'PASS' if ok else 'FAIL'} | {title} | exp={expect} | act={str(actual)[:120]}")


def start_server():
    global PROC, _TMPDIR
    _TMPDIR = tempfile.mkdtemp(prefix="fire_alarm_e2e_")
    db_path = os.path.join(_TMPDIR, "fire_alarm_e2e.db")
    env = dict(os.environ)
    env["FIRE_ALARM_DB"] = db_path
    print(f"[setup] 临时数据库: {db_path}  端口 {PORT}")
    PROC = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", HOST, "--port", str(PORT), "--log-level", "warning"],
        cwd=BACKEND_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    c = httpx.Client(base_url=BASE, timeout=5)
    try:
        dl = time.time() + 60
        while time.time() < dl:
            try:
                if c.get("/").status_code == 200:
                    print("[setup] 服务就绪")
                    return
            except Exception:
                time.sleep(0.4)
        raise RuntimeError("e2e 服务启动超时")
    finally:
        c.close()


def stop_server():
    global PROC, _TMPDIR
    if PROC and PROC.poll() is None:
        PROC.terminate()
        try:
            PROC.wait(timeout=10)
        except subprocess.TimeoutExpired:
            PROC.kill()
        print("[teardown] e2e 服务已关闭")
    if _TMPDIR and os.path.isdir(_TMPDIR):
        shutil.rmtree(_TMPDIR, ignore_errors=True)
        print("[teardown] 临时目录已清理")


def main():
    c = httpx.Client(base_url=BASE, timeout=30)
    start_server()
    try:
        def login(u, p):
            r = c.post("/api/auth/login", json={"username": u, "password": p})
            return r.json()["token"]

        tk = {"sup": login("admin", "123456"), "duty": login("duty", "123456"), "maint": login("maintain", "123456")}
        H = {k: {"Authorization": f"Bearer {v}"} for k, v in tk.items()}

        # ---- 1. 主管新增设备 ----
        areas = c.get("/api/areas", headers=H["sup"]).json()
        a0 = areas[0]  # A区一层，含4动作普通火灾预案
        dev_no = "E2E-" + str(int(time.time() * 1000) % 100000 % 8999 + 1000)
        newdev = c.post("/api/devices", json={"device_no": dev_no, "name": "端到端烟感", "device_type": "smoke", "area_id": a0["id"], "x": 30, "y": 40}, headers=H["sup"])
        nd = newdev.json()
        step("主管新增设备", "201 且 status=normal", (newdev.status_code, nd.get("status")), newdev.status_code in (200, 201) and nd.get("status") == "normal")
        ndid = nd["id"]

        # ---- 2. 值班员模拟报警（A区一层 ordinary 命中4动作预案）----
        sim = c.post("/api/alarms/simulate", json={"device_id": ndid, "fire_type": "ordinary", "scene": "端到端走廊烟雾"}, headers=H["duty"])
        sj = sim.json()
        alarm_id = sj["alarm"]["id"]
        step("模拟报警生成待确认报警", "200 alarm.status=pending", (sim.status_code, sj.get("alarm", {}).get("status")), sim.status_code == 200 and sj.get("alarm", {}).get("status") == "pending")
        step("报警后设备状态置alarm", "device.status=alarm", c.get(f"/api/devices/{ndid}", headers=H["duty"]).json().get("status"), c.get(f"/api/devices/{ndid}", headers=H["duty"]).json().get("status") == "alarm")
        step("自动联动命中预案", "linkage_run 非空且success", sj.get("linkage_run"), bool(sj.get("linkage_run")) and sj["linkage_run"]["status"] == "success" and sj["linkage_run"]["trigger_type"] == "auto")
        lr_id = sj["linkage_run"]["id"]

        # ---- 3. 联动执行4动作逐条记录 ----
        det = c.get(f"/api/linkage/runs/{lr_id}", headers=H["duty"]).json()
        acts = {x["action_type"] for x in det.get("results", [])}
        step("联动run详情含4个动作", "smoke_exhaust/fire_door/emergency_light/broadcast 全部success",
             sorted(acts),
             det["status"] == "success" and len(det.get("results", [])) == 4 and len(acts) == 4 and all(x["status"] == "success" for x in det["results"]))
        step("联动run与报警/预案关联", "alarm_id/plan_id/plan_name 齐全", (det.get("alarm_id"), det.get("plan_id"), det.get("plan_name")),
             det.get("alarm_id") == alarm_id and det.get("plan_id") and det.get("plan_name"))

        # ---- 4. 确认真实火警 -> 自动建处置单 ----
        cf = c.post(f"/api/alarms/{alarm_id}/confirm", json={"result": "true", "scene": "现场确认" if False else "端到端真实火警"}, headers=H["duty"]).json()
        em = cf.get("emergency")
        emid = em["id"]
        step("确认真实火警", "alarm.status=confirmed_real", cf.get("alarm", {}).get("status"), cf.get("alarm", {}).get("status") == "confirmed_real")
        step("确认真实自动创建处置单", "emergency 非空且 active, 关联报警", (bool(em), em.get("status"), em.get("alarm_id") if isinstance(em, dict) else None),
             bool(em) and em["status"] == "active")
        em_detail = c.get(f"/api/emergencies/{emid}", headers=H["duty"]).json()
        step("处置单与报警/报警状态关联", "处置单 alarm 关联到该报警且报警confirmed_real",
             (em_detail.get("alarm_id"), em_detail.get("alarm", {}).get("status")),
             em_detail.get("alarm_id") == alarm_id and em_detail.get("alarm", {}).get("status") == "confirmed_real")

        # ---- 5. 追加处置记录 ----
        rec = c.post(f"/api/emergencies/{emid}/records", json={"time": "2026-09-26 10:00", "content": "现场确认火势并组织人员疏散", "person": "值班员"}, headers=H["duty"])
        step("追加处置记录", "200 content保存", (rec.status_code, rec.json().get("content") if rec.status_code == 200 else ""), rec.status_code == 200 and rec.json().get("content") == "现场确认火势并组织人员疏散")

        # ---- 6. 处置闭环 ----
        cl = c.post(f"/api/emergencies/{emid}/close", json={"result": "火已扑灭，人员安全"}, headers=H["duty"]).json()
        step("处置闭环", "status=closed 且 closed_at/result 记录", (cl.get("status"), bool(cl.get("closed_at")), cl.get("result")),
             cl.get("status") == "closed" and cl.get("closed_at") and cl.get("result"))

        # ---- 7. 异常巡检 -> 自动维修 + 设备fault ----
        patrol_dev = next(d for d in c.get("/api/devices", params={"page_size": 500}, headers=H["maint"]).json()["items"] if d["area_id"] == areas[2]["id"] and d["status"] == "normal")
        pj = c.post("/api/patrols", json={"device_id": patrol_dev["id"], "area_id": areas[2]["id"], "scheduled_date": "2026-09-26"}, headers=H["maint"]).json()
        pid = pj["id"]
        pr = c.post(f"/api/patrols/{pid}/result", json={"status": "abnormal", "result": "压力表指示异常", "suggest": "需更换压力表"}, headers=H["maint"]).json()
        step("提交异常巡检", "patrol.status=abnormal", pr.get("status"), pr.get("status") == "abnormal")
        step("异常后设备置fault", "device.status=fault", c.get(f"/api/devices/{patrol_dev['id']}", headers=H["maint"]).json().get("status"), c.get(f"/api/devices/{patrol_dev['id']}", headers=H["maint"]).json().get("status") == "fault")
        repairs = c.get("/api/repairs", headers=H["maint"]).json()
        rr = next((x for x in repairs if x.get("patrol_id") == pid), None)
        step("自动生成维修单", "存在 patrol_id 关联的维修单", bool(rr) and rr.get("status"), bool(rr) and rr.get("status") == "pending" and rr.get("device_id") == patrol_dev["id"])

        # ---- 8. 维修完成 -> 设备normal ----
        c.post(f"/api/repairs/{rr['id']}/start", headers=H["maint"])
        fr = c.post(f"/api/repairs/{rr['id']}/finish", json={"result": "已更换压力表并复位"}, headers=H["maint"]).json()
        step("维修完成", "repair.status=done", fr.get("status"), fr.get("status") == "done" and fr.get("closed_at"))
        step("维修后设备恢复normal", "device.status=normal", c.get(f"/api/devices/{patrol_dev['id']}", headers=H["maint"]).json().get("status"), c.get(f"/api/devices/{patrol_dev['id']}", headers=H["maint"]).json().get("status") == "normal")

        # ---- 9. 演练 ----
        dj = c.post("/api/drills", json={"title": "端到端季度演练", "drill_type": "疏散演练", "area_id": a0["id"], "plan_date": "2026-12-01", "organizer": "消防主管", "participants": "全体员工"}, headers=H["sup"]).json()
        did = dj["id"]
        step("创建演练", "status=planned", dj.get("status"), dj.get("status") == "planned")
        fj = c.post(f"/api/drills/{did}/finish", json={"score": 96, "evaluate": "疏散迅速有序", "summary": "达成目标"}, headers=H["sup"]).json()
        step("完成演练", "status=done score=96", (fj.get("status"), fj.get("score")), fj.get("status") == "done" and fj.get("score") == 96)

        # ---- 10. 统计 dashboard 数据一致性 ----
        dash = c.get("/api/stats/dashboard", headers=H["sup"]).json()
        step("dashboard含核心指标", "device_status/alarm_trend/误报率/巡检完成率/联动成功率存在",
             sorted(k for k in ["device_status", "alarm_trend", "false_alarm_rate", "patrol_done_rate", "linkage_success_rate"] if k in dash),
             all(k in dash for k in ["device_status", "alarm_trend", "false_alarm_rate", "patrol_done_rate", "linkage_success_rate"]))
        step("dashboard计数跨模块一致", "alarm_total>=1, emergency_total>=1, drill_total>=1, patrol已完成",
             (dash.get("alarm_total"), dash.get("emergency_total"), dash.get("drill_total"), dash.get("patrol_done_rate")),
             dash.get("alarm_total") >= 1 and dash.get("emergency_total") >= 1 and dash.get("drill_total") >= 1)
        # 设备状态分布交叉核对
        devs = c.get("/api/devices", params={"page_size": 500}, headers=H["sup"]).json()["items"]
        cnt = {}
        for d in devs:
            cnt[d["status"]] = cnt.get(d["status"], 0) + 1
        ds = dash["device_status"]
        step("dashboard设备状态分布与接口一致", "各状态计数一致", (cnt, ds), all(ds.get(k, 0) == cnt.get(k, 0) for k in set(list(cnt) + list(ds))))
        # 报警明细列表
        ad = c.get("/api/stats/alarms", headers=H["sup"])
        j = ad.json()
        step("报警明细列表", "200 {total,items} 且含新建报警", (ad.status_code, j.get("total") if isinstance(j, dict) else None),
             ad.status_code == 200 and isinstance(j, dict) and "total" in j and any(x["id"] == alarm_id for x in j.get("items", [])))

        # ---- 11. 导出 excel / csv ----
        ex = c.get("/api/stats/export", params={"type": "excel", "data": "alarms"}, headers=H["sup"])
        step("导出Excel(alarms)", "200 xlsx 字节>0", (ex.status_code, ex.headers.get("content-type", "")[:40], len(ex.content)),
             ex.status_code == 200 and len(ex.content) > 100 and "spreadsheetml" in ex.headers.get("content-type", ""))
        ct = c.get("/api/stats/export", params={"type": "csv", "data": "alarms"}, headers=H["sup"])
        step("导出CSV(alarms)", "200 csv 字节>0", (ct.status_code, ct.headers.get("content-type", "")[:20], len(ct.content)),
             ct.status_code == 200 and len(ct.content) > 10 and "csv" in ct.headers.get("content-type", ""))

    finally:
        c.close()
        stop_server()

    passed = sum(1 for s in steps if s["ok"])
    print("=" * 100)
    print(f"端到端全流程步骤汇总：总数={len(steps)}  通过={passed}  失败={len(steps) - passed}")
    print("=" * 100)
    return 0 if passed == len(steps) else 1


if __name__ == "__main__":
    sys.exit(main())