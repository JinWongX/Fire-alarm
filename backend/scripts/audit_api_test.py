#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
功能可用性审计 —— 补充接口测试（边界/参数校验/响应合规/权限拦截）
=================================================================
在 batch_test.py（8001 + 81 条核心用例全过）基础上，补充覆盖：
  1) 请求参数校验：缺参 / 类型错 / 超长 / 非法枚举 / 越界坐标 / 不存在的依赖外键
  2) 响应格式合规：状态码与结构是否与 PRD 一致
  3) 权限拦截：路由级 403/401，以及 method 级越权（如非主管增删改设备、非主管导出）
  4) 空数据 / 边界值 / 事务一致性前置探针

隔离策略：
  - 独立端口 127.0.0.1:8002（避开生产 8000、跑批 8001）
  - 通过环境变量 FIRE_ALARM_DB 指向全新临时 sqlite 种子库
  - 本脚本自行拉起测试专用 uvicorn，测试结束后关闭并清理临时目录

调用方式：在 backend 目录执行  python scripts/audit_api_test.py
期望口径以《系统PRD文档.md》为准；实际行为与期望不一致记 FAIL 并计入缺陷清单。
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
PORT = 8002
BASE = f"http://{HOST}:{PORT}"

PROC = None
_TMPDIR = None

results: list[dict] = []


def rec(cid, title, request, expected, actual, ok):
    results.append(
        {"id": cid, "title": title, "request": request, "expected": expected, "actual": actual, "ok": ok}
    )
    print(f"{'PASS' if ok else 'FAIL'} | {cid} | {title} | req={request} | exp={expected} | act={actual}")


# ---------------------------------------------------------------------------
# 测试专用服务托管
# ---------------------------------------------------------------------------
def start_server():
    global PROC, _TMPDIR
    _TMPDIR = tempfile.mkdtemp(prefix="fire_alarm_audit_")
    db_path = os.path.join(_TMPDIR, "fire_alarm_audit.db")
    env = dict(os.environ)
    env["FIRE_ALARM_DB"] = db_path
    print(f"[setup] 临时数据库: {db_path}")
    print(f"[setup] 启动审计测试服务 {BASE} (端口 {PORT})")
    PROC = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", HOST, "--port", str(PORT), "--log-level", "warning"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 60
    client = httpx.Client(timeout=5)
    try:
        while time.time() < deadline:
            if PROC.poll() is not None:
                raise RuntimeError(f"审计服务提前退出 code={PROC.returncode}")
            try:
                r = client.get(f"{BASE}/")
                if r.status_code == 200:
                    print(f"[setup] 服务就绪: {r.json()}")
                    return
            except Exception:
                time.sleep(0.4)
        raise RuntimeError("审计服务启动超时")
    finally:
        client.close()


def stop_server():
    global PROC, _TMPDIR
    if PROC is not None and PROC.poll() is None:
        PROC.terminate()
        try:
            PROC.wait(timeout=10)
        except subprocess.TimeoutExpired:
            PROC.kill()
        print("[teardown] 审计服务已关闭")
    if _TMPDIR and os.path.isdir(_TMPDIR):
        shutil.rmtree(_TMPDIR, ignore_errors=True)
        print(f"[teardown] 临时目录已清理: {_TMPDIR}")


class API:
    def __init__(self):
        self.c = httpx.Client(base_url=BASE, timeout=30)

    def h(self, token):
        return {"Authorization": f"Bearer {token}"}

    def login(self, u, p):
        return self.c.post("/api/auth/login", json={"username": u, "password": p})


def main():
    api = API()
    start_server()
    try:
        duty = api.login("duty", "123456").json()["token"]
        maint = api.login("maintain", "123456").json()["token"]
        admin = api.login("admin", "123456").json()["token"]
        Hd, Hm, Ha = api.h(duty), api.h(maint), api.h(admin)

        areas = api.c.get("/api/areas", headers=Hd).json()
        a0 = areas[0]
        dev0 = api.c.get("/api/devices", params={"page": 1, "page_size": 1}, headers=Hd).json()["items"][0]
        dev0id = dev0["id"]

        def short(s, n=60):
            s = str(s)
            return s if len(s) <= n else s[:n] + "…"

        # ================= 认证 / 令牌 =================
        r = api.c.post("/api/auth/login", json={"username": "duty"})
        rec("AT-01", "登录缺password参数", "POST /api/auth/login 缺password",
            "422 参数校验拦截", short((r.status_code, r.json())), r.status_code == 422 and r.status_code != 500)

        r = api.c.post("/api/auth/login", json={"username": "duty", "password": 123456})
        rec("AT-02", "密码类型为数字非字符串", "POST /api/auth/login password=123456(int)",
            "422 类型校验拦截", short((r.status_code, r.json())), r.status_code == 422 and r.status_code != 500)

        r = api.c.get("/api/devices", headers={"Authorization": "Bearer"})
        rec("AT-03", "空token(Bearer无凭据)", "GET /api/devices Authorization 'Bearer'",
            "401 未授权", short(r.status_code), r.status_code == 401)

        r = api.c.get("/api/auth/me", headers=Ha)
        rec("AT-04", "有效token访问/me", "GET /api/auth/me supervisor",
            "200 返回用户信息", short((r.status_code, r.json().get("role"))), r.status_code == 200 and r.json().get("role") == "supervisor")

        # ================= 设备参数校验 / 边界 =================
        r = api.c.post("/api/devices", json={"name": "缺编号", "device_type": "smoke", "area_id": a0["id"]}, headers=Ha)
        rec("DV-01", "新增设备缺device_no", "POST /api/devices 缺编号",
            "422 必填校验", short((r.status_code, r.json())), r.status_code in (400, 422) and r.status_code != 500)

        long_no = "X" * 300
        r = api.c.post("/api/devices", json={"device_no": long_no, "name": "超长编号", "device_type": "smoke", "area_id": a0["id"]}, headers=Ha)
        rec("DV-02", "超长设备编号(300字符)", "POST /api/devices device_no=300字符",
            "400/422 长度校验拦截(上限64)", short((r.status_code, r.json())), r.status_code in (400, 422) and r.status_code != 500)

        r = api.c.post("/api/devices", json={"device_no": "X-BADT", "name": "坏类型", "device_type": "bogus", "area_id": a0["id"]}, headers=Ha)
        rec("DV-03", "非法设备类型", "POST /api/devices device_type=bogus",
            "400 无效设备类型", short((r.status_code, r.json())), r.status_code == 400)

        r = api.c.post("/api/devices", json={"device_no": "X-BAD", "name": "坏区域", "device_type": "smoke", "area_id": 999999}, headers=Ha)
        rec("DV-04", "外键area_id不存在", "POST /api/devices area_id=999999",
            "400/422 外键约束(引用不存在区域)", short((r.status_code, r.json())), r.status_code in (400, 422) and r.status_code != 200)

        r = api.c.post("/api/devices", json={"device_no": "X-FAR", "name": "越界坐标", "device_type": "hydrant", "area_id": a0["id"], "x": 99999.0, "y": 99999.0}, headers=Ha)
        rec("DV-05", "坐标越界(99999,99999)", "POST /api/devices 坐标越界",
            "400/422 坐标边界校验拦截(0<=x,y<=100)", short((r.status_code, r.json())), r.status_code in (400, 422) and r.status_code != 500)

        r = api.c.post("/api/devices", json={"device_no": "X-VOID", "name": "", "device_type": "smoke", "area_id": a0["id"]}, headers=Ha)
        rec("DV-06", "空字符串设备名", "POST /api/devices name=''",
            "400/422 空名/空白名校验拦截", short((r.status_code, r.json())), r.status_code in (400, 422) and r.status_code != 500)

        r = api.c.post("/api/devices", json={"device_no": "X-FLOAT", "name": "坐标非数字", "device_type": "smoke", "area_id": a0["id"], "x": "abc"}, headers=Ha)
        rec("DV-07", "坐标为字符串非数字", "POST /api/devices x='abc'",
            "422 类型校验拦截", short((r.status_code, r.json())), r.status_code == 422 and r.status_code != 500)

        r = api.c.put(f"/api/devices/{dev0id}/status", json={"status": "bogus"}, headers=Ha)
        rec("DV-08", "非法设备状态", "PUT /api/devices/{id}/status status=bogus",
            "400 无效状态", short((r.status_code, r.json())), r.status_code == 400)

        r = api.c.get("/api/devices", params={"page": -1, "page_size": -1}, headers=Hd)
        rec("DV-09", "负值分页边界", "GET /api/devices?page=-1&page_size=-1",
            "不 500，正常返回为空列表", short(r.status_code), r.status_code != 500)

        # ================= 设备写操作 RBAC(method 级) =================
        tmp_no = "AUD-DEV-" + str(int(time.time() * 1000) % 100000)
        r = api.c.post("/api/devices", json={"device_no": tmp_no, "name": "值班员增设备", "device_type": "smoke", "area_id": a0["id"]}, headers=Hd)
        rec("DV-10", "值班员新增设备", "POST /api/devices (duty)",
            "403 PRD 设备增删改仅主管", short((r.status_code, r.json())), r.status_code == 403)

        r = api.c.put("/api/devices/%d/status" % dev0id, json={"status": "masked"}, headers=Hm)
        rec("DV-11", "维保屏蔽设备", "PUT /api/devices/{id}/status masked (maintain)",
            "403 PRD 仅主管", short((r.status_code, r.json())), r.status_code == 403)

        dev_for_del = api.c.post("/api/devices", json={"device_no": "AUD-DEL", "name": "待删", "device_type": "smoke", "area_id": a0["id"]}, headers=Ha)
        del_id = dev_for_del.json()["id"] if dev_for_del.status_code in (200, 201) else dev0id
        r = api.c.delete(f"/api/devices/{del_id}", headers=Hm)
        rec("DV-12", "维保删除设备", "DELETE /api/devices/{id} (maintain)",
            "403 PRD 仅主管", short((r.status_code, r.json())), r.status_code == 403)

        r = api.c.delete(f"/api/devices/{dev0id}")
        rec("DV-13", "无token删除设备", "DELETE /api/devices/{id} 无token",
            "401 鉴权拦截", short(r.status_code), r.status_code == 401)

        # 关联业务数据后仍可物理删除（BR-F1-02）探针
        del_tmp = api.c.post("/api/devices", json={"device_no": "AUD-KEEP", "name": "删除探针设备", "device_type": "smoke", "area_id": a0["id"]}, headers=Ha).json()
        del_trg = del_tmp["id"]
        api.c.post("/api/alarms/simulate", json={"device_id": del_trg, "fire_type": "ordinary", "scene": "删除探针"}, headers=Ha)
        r = api.c.delete(f"/api/devices/{del_trg}", headers=Ha)
        alarms_after = api.c.get("/api/alarms", params={"page_size": 200}, headers=Ha)
        orphan = sum(1 for x in alarms_after.json().get("items", []) if x["device_id"] == del_trg)
        post = f"delete={r.status_code} alarms={orphan} list_status={alarms_after.status_code}"
        rec("DV-14", "有报警记录的设备不可物理删除", "DELETE 设备(该设备已有报警记录)",
            "409 设备存在关联报警,禁止物理删除,报警保留", short(post),
            r.status_code == 409 and orphan >= 1)

        # ================= 预案参数 / 唯一性 / RBAC =================
        r = api.c.post("/api/plans", json={"name": "非法火灾类型", "area_id": a0["id"], "fire_type": "bogus", "actions": [], "enabled": True}, headers=Ha)
        rec("PL-01", "非法火灾类型", "POST /api/plans fire_type=bogus",
            "400 枚举校验(PRD: electrical/ordinary/oil)", short((r.status_code, r.json())), r.status_code == 400)

        r = api.c.post("/api/plans", json={"name": "空动作预案", "area_id": a0["id"], "fire_type": "ordinary", "actions": [], "enabled": True}, headers=Ha)
        rec("PL-02", "空动作预案", "POST /api/plans actions=[]",
            "400 BR-F4-02 至少一个联动动作", short((r.status_code, r.json())), r.status_code == 400)

        api.c.post("/api/plans", json={"name": "P1", "area_id": a0["id"], "fire_type": "ordinary", "actions": [{"action_type": "broadcast", "action_name": "广播"}], "enabled": True}, headers=Ha)
        r = api.c.post("/api/plans", json={"name": "P2", "area_id": a0["id"], "fire_type": "ordinary", "actions": [{"action_type": "broadcast", "action_name": "广播"}], "enabled": True}, headers=Ha)
        rec("PL-03", "区域+火灾类型重复预案", "POST /api/plans 再次创建同区域同类型",
            "409 BR-F4-01 组合唯一", short((r.status_code, r.json())), r.status_code == 409)

        r = api.c.post("/api/plans", json={"name": "维保建预案", "area_id": a0["id"]}, headers=Hm)
        rec("PL-04", "维保新增预案", "POST /api/plans (maintain)",
            "403 PRD 仅主管", short((r.status_code, r.json())), r.status_code == 403)

        plan0 = api.c.get("/api/plans", headers=Ha).json()[0]
        r = api.c.post(f"/api/plans/{plan0['id']}/execute", headers=Hm)
        rec("PL-05", "维保手动执行预案", "POST /api/plans/{id}/execute (maintain)",
            "403 PRD 仅值班员/主管", short((r.status_code, r.json())), r.status_code == 403)

        # ================= 报警参数 / 确认 =================
        r = api.c.post("/api/alarms/simulate", json={"device_id": 999999, "fire_type": "ordinary"}, headers=Hd)
        rec("AL-01", "模拟报警设备不存在", "POST /api/alarms/simulate device_id=999999",
            "404 设备不存在", short((r.status_code, r.json())), r.status_code == 404)

        r = api.c.post("/api/alarms/simulate", json={"device_id": dev0id, "fire_type": "bogus"}, headers=Hd)
        rec("AL-02", "模拟报警非法火灾类型", "POST /api/alarms/simulate fire_type=bogus",
            "400 无效火灾类型", short((r.status_code, r.json())), r.status_code == 400)

        r = api.c.post("/api/alarms/simulate", json={"fire_type": "ordinary"}, headers=Hd)
        rec("AL-03", "模拟报警缺device_id", "POST /api/alarms/simulate 缺device_id",
            "422 必填校验拦截", short((r.status_code, r.json())), r.status_code == 422 and r.status_code != 500)

        r = api.c.post("/api/alarms/simulate", json={"device_id": dev0id, "fire_type": "ordinary", "scene": "维保触发"}, headers=Hm)
        rec("AL-04", "维保触发模拟报警", "POST /api/alarms/simulate (maintain)",
            "403 报警动作仅值班员/主管", short((r.status_code, r.json())), r.status_code == 403)

        aid = api.c.post("/api/alarms/simulate", json={"device_id": dev0id, "fire_type": "ordinary", "scene": "确认校验"}, headers=Hd).json()["alarm"]["id"]
        r = api.c.post(f"/api/alarms/{aid}/confirm", json={"result": "maybe"}, headers=Hd)
        rec("AL-05", "非true/false确认结果", "POST /api/alarms/{id}/confirm result=maybe",
            "400 result 必须 true/false", short((r.status_code, r.json())), r.status_code == 400)

        r = api.c.post("/api/alarms/999999/confirm", json={"result": "true"}, headers=Hd)
        rec("AL-06", "确认不存在的报警", "POST /api/alarms/999999/confirm",
            "404 报警不存在", short((r.status_code, r.json())), r.status_code == 404)

        aid2 = api.c.post("/api/alarms/simulate", json={"device_id": dev0id, "fire_type": "ordinary", "scene": "维保确认"}, headers=Hd).json()["alarm"]["id"]
        r = api.c.post(f"/api/alarms/{aid2}/confirm", json={"result": "true"}, headers=Hm)
        rec("AL-07", "维保确认火警", "POST /api/alarms/{id}/confirm (maintain)",
            "403 确认仅值班员/主管", short((r.status_code, r.json())), r.status_code == 403)

        aid3 = api.c.post("/api/alarms/simulate", json={"device_id": dev0id, "fire_type": "ordinary", "scene": "重复确认"}, headers=Hd).json()["alarm"]["id"]
        ec = api.c.post(f"/api/alarms/{aid3}/confirm", json={"result": "true"}, headers=Hd)
        em_ids = set()
        if ec.status_code == 200 and ec.json().get("emergency"):
            em_ids.add(ec.json()["emergency"]["id"])
        ec2 = api.c.post(f"/api/alarms/{aid3}/confirm", json={"result": "true"}, headers=Hd)
        if ec2.status_code == 200 and ec2.json().get("emergency"):
            em_ids.add(ec2.json()["emergency"]["id"])
        rec("AL-08", "同一报警重复确认真实", "POST confirm result=true 两次同一报警",
            "已确认报警不可重复确认(幂等), 处置单仅1张", short((ec2.status_code, "emergency_count=" + str(len(em_ids)))),
            ec2.status_code in (400, 409) or len(em_ids) <= 1)

        # ================= 联动 / 处置 / 巡检 / 维修 / 演练 =================
        r = api.c.get("/api/linkage/runs/999999", headers=Hd)
        rec("LK-01", "联动记录不存在", "GET /api/linkage/runs/999999",
            "404 联动记录不存在", short((r.status_code, r.json())), r.status_code == 404)

        aid4 = api.c.post("/api/alarms/simulate", json={"device_id": dev0id, "fire_type": "ordinary", "scene": "处置校验"}, headers=Hd).json()["alarm"]["id"]
        em = api.c.post(f"/api/alarms/{aid4}/confirm", json={"result": "true"}, headers=Hd).json()["emergency"]
        emid = em["id"]
        r = api.c.post(f"/api/emergencies/{emid}/close", json={}, headers=Hd)
        rec("EM-01", "闭环缺处置结论", "POST /api/emergencies/{id}/close 缺result",
            "422 result必填", short((r.status_code, r.json())), r.status_code == 422 and r.status_code != 500)

        api.c.post(f"/api/emergencies/{emid}/close", json={"result": "首次闭环"}, headers=Hd)
        r = api.c.post(f"/api/emergencies/{emid}/close", json={"result": "二次闭环"}, headers=Hd)
        rec("EM-02", "已闭环处置单重复闭环(幂等)", "POST close 对已closed处置单再次close",
            "200 幂等, 保持closed状态", short((r.status_code, r.json().get("status"))), r.status_code == 200 and r.json().get("status") == "closed")

        r = api.c.post("/api/emergencies", json={"title": "维保建处置"}, headers=Hm)
        rec("EM-03", "维保创建处置单", "POST /api/emergencies (maintain)",
            "403 处置仅值班员/主管", short((r.status_code, r.json())), r.status_code == 403)

        p1 = api.c.post("/api/patrols", json={"device_id": dev0id, "area_id": a0["id"]}, headers=Hm).json()
        pid1 = p1["id"]
        r = api.c.post(f"/api/patrols/{pid1}/result", json={"status": "abnormal"}, headers=Hm)
        rec("PT-01", "异常巡检缺结果说明", "POST result status=abnormal 缺result/描述",
            "400 BR-F7-04 异常须说明", short((r.status_code, r.json())), r.status_code == 400)

        r = api.c.post("/api/patrols/999999/result", json={"status": "normal"}, headers=Hm)
        rec("PT-02", "巡检任务不存在", "POST /api/patrols/999999/result",
            "404 巡检任务不存在", short((r.status_code, r.json())), r.status_code == 404)

        r = api.c.post("/api/patrols", json={"device_id": dev0id, "area_id": a0["id"]}, headers=Hd)
        rec("PT-03", "值班员创建巡检", "POST /api/patrols (duty)",
            "403 巡检仅维保/主管", short((r.status_code, r.json())), r.status_code == 403)

        # 硬化后：同一设备已有 pending/in_progress 维修单时再创建 -> 409（防重复工单）
        _pt_dev = api.c.post("/api/devices", json={"device_no": "AUD-PT4", "name": "防重工单设备", "device_type": "smoke", "area_id": a0["id"]}, headers=Ha).json()
        _pp = api.c.post("/api/patrols", json={"device_id": _pt_dev["id"], "area_id": a0["id"]}, headers=Hm).json()["id"]
        api.c.post(f"/api/patrols/{_pp}/result", json={"status": "abnormal", "result": "异常A", "suggest": "说明A"}, headers=Hm)
        dup = [x for x in api.c.get("/api/repairs", headers=Hm).json() if x.get("device_id") == _pt_dev["id"] and x["status"] in ("pending", "in_progress")]
        r2 = api.c.post("/api/repairs", json={"device_id": _pt_dev["id"], "title": "重复工单"}, headers=Hm)
        rec("PT-04", "同一设备已有active维修单再建", "POST /api/repairs 同设备再次创建维修单",
            "409 设备已有进行中的维修单(防重复工单)", short((r2.status_code, r2.json())),
            r2.status_code == 409 and len(dup) == 1)

        r = api.c.post("/api/repairs/999999/finish", json={"result": "x"}, headers=Hm)
        rec("RP-01", "维修单不存在finish", "POST /api/repairs/999999/finish",
            "404 维修单不存在", short((r.status_code, r.json())), r.status_code == 404)

        rp0 = next((x for x in api.c.get("/api/repairs", headers=Hm).json() if x["status"] == "pending"), None)
        rr = None
        if rp0:
            rr = api.c.post(f"/api/repairs/{rp0['id']}/start", headers=Hd)
        rec("RP-02", "值班员启动维修", "POST /api/repairs/{id}/start (duty)",
            "403 维修仅维保/主管", short((rr.status_code, rr.json()) if rr else "无pending工单"), rr is not None and rr.status_code == 403)

        # 用新设备产生一条 pending 维修单，再验证 finish 缺 result -> 422
        _rp_dev = api.c.post("/api/devices", json={"device_no": "AUD-RP3", "name": "维修缺结果设备", "device_type": "smoke", "area_id": a0["id"]}, headers=Ha).json()
        _rp_pat = api.c.post("/api/patrols", json={"device_id": _rp_dev["id"], "area_id": a0["id"]}, headers=Hm).json()["id"]
        api.c.post(f"/api/patrols/{_rp_pat}/result", json={"status": "abnormal", "result": "异常", "suggest": "说明"}, headers=Hm)
        rp_new = next(x for x in api.c.get("/api/repairs", headers=Hm).json() if x.get("patrol_id") == _rp_pat)
        rr2 = api.c.post(f"/api/repairs/{rp_new['id']}/finish", json={}, headers=Hm)
        rec("RP-03", "维修finish缺结果", "POST /api/repairs/{id}/finish 缺result",
            "422 result必填", short((rr2.status_code, rr2.json())), rr2.status_code == 422 and rr2.status_code != 500)

        r = api.c.post("/api/drills/999999/finish", json={"score": 90}, headers=Ha)
        rec("DR-01", "演练不存在finish", "POST /api/drills/999999/finish",
            "404 演练不存在", short((r.status_code, r.json())), r.status_code == 404)

        dr = api.c.post("/api/drills", json={"title": "审计演练", "drill_type": "疏散演练", "area_id": a0["id"]}, headers=Ha).json()
        r = api.c.post(f"/api/drills/{dr['id']}/finish", json={"score": 999, "evaluate": "x"}, headers=Ha)
        rec("DR-02", "演练评分越界(999)", "POST /api/drills/{id}/finish score=999",
            "400 BR 评分0-100边界校验", short((r.status_code, "score=" + str(r.json().get("score")))), r.status_code == 400)

        r = api.c.delete(f"/api/drills/{dr['id']}", headers=Hd)
        rec("DR-03", "值班员删除演练", "DELETE /api/drills/{id} (duty)",
            "403 演练仅主管", short((r.status_code, r.json())), r.status_code == 403)

        # ================= 统计 RBAC / 导出参数 =================
        r = api.c.get("/api/stats/dashboard", headers=Hd)
        rec("ST-01", "值班员访问统计看板", "GET /api/stats/dashboard (duty)",
            "403 PRD 统计仅主管", short((r.status_code, r.json())) if r.status_code != 200 else "200 有数据", r.status_code == 403)

        r = api.c.get("/api/stats/export", params={"type": "csv", "data": "alarms"}, headers=Hm)
        rec("ST-02", "维保导出CSV", "GET /api/stats/export (maintain)",
            "403 PRD 导出仅主管", short((r.status_code, r.headers.get('content-type', ''))), r.status_code == 403)

        r = api.c.get("/api/stats/export", params={"type": "pdf", "data": "alarms"}, headers=Ha)
        rec("ST-03", "非法导出格式pdf", "GET /api/stats/export type=pdf",
            "400 type必须excel/csv", short((r.status_code, r.json())), r.status_code == 400)

        r = api.c.get("/api/stats/export", params={"type": "excel", "data": "users"}, headers=Ha)
        rec("ST-04", "非法导出数据集users", "GET /api/stats/export data=users",
            "400 不支持的数据集", short((r.status_code, r.json())), r.status_code == 400)

        r = api.c.get("/api/stats/export", params={"type": "excel", "data": "alarms"}, headers=Ha)
        rec("ST-05", "主管导出Excel合规", "GET /api/stats/export excel/alarms 主管",
            "200 xlsx content-type 且字节>0",
            short((r.status_code, r.headers.get('content-type', '')[:40], len(r.content))),
            r.status_code == 200 and len(r.content) > 100 and "spreadsheetml" in r.headers.get("content-type", ""))

        r = api.c.get("/api/stats/alarms", headers=Hd)
        r2 = api.c.get("/api/stats/alarms", headers=Ha)
        rec("ST-06", "报警明细接口权限", "GET /api/stats/alarms 值班员/主管",
            "值班员403, 主管200且返回{total,items}", short((r.status_code, r2.status_code,
            {k: v for k, v in r2.json().items() if k in ('total', 'items')} if r2.status_code == 200 else None)),
            r.status_code == 403 and r2.status_code == 200 and isinstance(r2.json(), dict) and "total" in r2.json() and "items" in r2.json())

        # ================= 空数据 / 响应结构 =================
        r = api.c.get("/api/alarms", params={"page_size": 5}, headers=Ha)
        j = r.json() if hasattr(r, "json") else {}
        rec("EB-01", "报警列表结构", "GET /api/alarms 返回结构",
            "200 {total, items[]}", short((r.status_code, type(j).__name__, len(j.get('items', [])))), r.status_code == 200 and isinstance(j, dict) and "items" in j and "total" in j)

        r = api.c.get("/api/areas", headers=Ha)
        rec("EB-02", "区域列表非空", "GET /api/areas",
            "200 返回种子区域6个", short((r.status_code, len(r.json()))), r.status_code == 200 and len(r.json()) == 6)

    finally:
        api.c.close()
        stop_server()

    passed = sum(1 for x in results if x["ok"])
    print("=" * 100)
    print(f"审计接口用例汇总：总数={len(results)}  通过={passed}  失败={len(results) - passed}")
    print("=" * 100)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())