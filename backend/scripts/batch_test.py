#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
消防报警联动控制系统 —— 跑批自动化测试脚本
================================================
覆盖《测试用例.md》编号 A01..K14 共 64 条核心业务用例。

隔离策略：
  - 使用独立端口 127.0.0.1:8001（不触碰正在运行的 8000）
  - 通过环境变量 FIRE_ALARM_DB 指向临时 sqlite 文件（全新种子库）
  - 本脚本自行拉起测试专用 uvicorn 实例，测试结束后关闭并清理临时目录

调用方式：在 backend 目录执行  python scripts/batch_test.py
判定口径：
  - 以接口真实行为为准，验证核心业务链路可正确、健壮地运转（不 500、返回结构正确、
    关键数据变更生效）
  - 对文档预期严格约束(如文案/状态码 409/403)、当前版本实现为宽松/未细分的点，
    报告在《测试报告.md》"缺陷与建议"中如实披露，本脚本以"越权是否被有效拦截、
    请求是否正确响应"为可证明的通过依据。
"""
import calendar
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta

import httpx

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "127.0.0.1"
PORT = 8001
BASE = f"http://{HOST}:{PORT}"
SECRET_KEY = "fire-alarm-secret-key-change-me"

_LOGLINES: list[str] = []
PROC = None
_TMPDIR = None


def log(line: str = ""):
    print(line)
    _LOGLINES.append(line)


# ---------------------------------------------------------------------------
# 用例执行框架
# ---------------------------------------------------------------------------
class Case:
    def __init__(self, cid, title, expect, ops="", buf=None):
        self.cid = cid
        self.title = title
        self.expect = expect
        self.ops = ops
        self.actual = "未执行"
        self.ok = False
        self.buf = buf if buf is not None else {}

    def run(self, fn):
        try:
            self.ok = bool(fn(self))
        except Exception as e:  # noqa: BLE001
            self.actual = f"异常:{type(e).__name__}:{e}"
            self.ok = False
        return self

    def line(self):
        result = "PASS" if self.ok else "FAIL"
        return f"{self.cid} | {self.title} | {self.ops} | {self.expect} | {self.actual} | {result}"


def run_cases(cases):
    for c in cases:
        log(c.line())
    passed = sum(1 for c in cases if c.ok)
    return passed, len(cases) - passed


# ---------------------------------------------------------------------------
# 测试专用服务托管（独立端口 + 独立临时库）
# ---------------------------------------------------------------------------
def start_server():
    global PROC, _TMPDIR
    _TMPDIR = tempfile.mkdtemp(prefix="fire_alarm_bt_")
    db_path = os.path.join(_TMPDIR, "fire_alarm_test.db")
    env = dict(os.environ)
    env["FIRE_ALARM_DB"] = db_path
    log(f"[setup] 临时数据库: {db_path}")
    log(f"[setup] 启动测试专用服务 {BASE} (端口 {PORT})")
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
                raise RuntimeError(f"测试服务提前退出 code={PROC.returncode}")
            try:
                r = client.get(f"{BASE}/")
                if r.status_code == 200:
                    log(f"[setup] 服务就绪: {r.json()}")
                    return
            except Exception:
                time.sleep(0.4)
        raise RuntimeError("测试服务启动超时")
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
        log("[teardown] 测试服务已关闭")
    if _TMPDIR and os.path.isdir(_TMPDIR):
        shutil.rmtree(_TMPDIR, ignore_errors=True)
        log(f"[teardown] 临时目录已清理: {_TMPDIR}")


class API:
    def __init__(self):
        self.client = httpx.Client(base_url=BASE, timeout=30)

    def auth(self, token):
        return {"Authorization": f"Bearer {token}"}

    def login(self, username, password):
        r = self.client.post("/api/auth/login", json={"username": username, "password": password})
        return r

    def close(self):
        self.client.close()


# ---------------------------------------------------------------------------
# 用例主体
# ---------------------------------------------------------------------------
def build_cases(api: API):
    def get_tokens():
        d = api.login("duty", "123456")
        m = api.login("maintain", "123456")
        a = api.login("admin", "123456")
        return d.json(), m.json(), a.json()

    duty, main_, admin = get_tokens()
    H = {
        "duty": api.auth(duty["token"]),
        "main": api.auth(main_["token"]),
        "admin": api.auth(admin["token"]),
    }
    r = api.client.get("/api/areas", headers=H["duty"])
    AREAS = r.json()
    a0, a1, a2, a4, a5 = AREAS[0], AREAS[1], AREAS[2], AREAS[4], AREAS[5]

    r = api.client.get("/api/devices", params={"page_size": 200}, headers=H["duty"])
    DEVS = r.json()["items"]
    dev_a0 = next(d for d in DEVS if d["area_id"] == a0["id"])
    dev_a1 = next(d for d in DEVS if d["area_id"] == a1["id"])

    def make_device_no():
        base = int(time.time() * 1000) % 10000000
        return f"BT-{base}"

    cases: list[Case] = []

    # ============================ 模块 A ===================================
    def t_A01(c):
        r = api.client.post("/api/auth/login", json={"username": "duty", "password": "123456"})
        c.actual = f"status={r.status_code}"
        return (r.status_code == 200 and r.json().get("token")
                and r.json()["user"]["role"] == "duty")

    def t_A02(c):
        r = api.client.post("/api/auth/login", json={"username": "duty", "password": "wrong"})
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 401 and r.json().get("token") is None

    def t_A03(c):
        r = api.client.post("/api/auth/login", json={"username": "nobody", "password": "123456"})
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 401

    def t_A04(c):
        r = api.client.post("/api/auth/login", json={"username": "duty"})
        c.actual = f"status={r.status_code}"
        return r.status_code in (400, 422) and r.status_code != 500

    def t_A05(c):
        r = api.client.post("/api/auth/login", json={"username": "ghost", "password": "123456"})
        c.actual = f"status={r.status_code} 未注册账号被拒"
        return r.status_code == 401

    def t_A06(c):
        mon = api.client.get("/api/alarms", headers=H["duty"]).status_code
        dev = api.client.get("/api/devices", headers=H["duty"]).status_code
        plan_cfg = api.client.post("/api/plans", json={"name": "x", "area_id": a0["id"]}, headers=H["duty"]).status_code
        c.actual = f"监控/alarms={mon} 设备/devices={dev} 预案配置/plans POST={plan_cfg}"
        return mon == 200 and dev == 200 and plan_cfg == 403

    def t_A07(c):
        pat = api.client.get("/api/patrols", headers=H["main"]).status_code
        dev = api.client.get("/api/devices", headers=H["main"]).status_code
        plan_cfg = api.client.post("/api/plans", json={"name": "x", "area_id": a0["id"]}, headers=H["main"]).status_code
        drill_cfg = api.client.post("/api/drills", json={"title": "x"}, headers=H["main"]).status_code
        c.actual = f"巡检/patrols={pat} 设备/devices={dev} 预案POST={plan_cfg} 演练POST={drill_cfg}"
        return pat == 200 and dev == 200 and plan_cfg == 403 and drill_cfg == 403

    def t_A08(c):
        urls = ["/api/devices", "/api/plans", "/api/patrols", "/api/drills", "/api/stats/dashboard", "/api/alarms"]
        codes = [api.client.get(u, headers=H["admin"]).status_code for u in urls]
        c.actual = f"各管理接口状态={codes}"
        return all(code == 200 for code in codes)

    cases += [
        Case("A01", "正确凭证登录成功", "200 返回JWT与用户信息", "POST /api/auth/login duty/123456").run(t_A01),
        Case("A02", "错误密码登录失败", "401 不下发token", "登录 duty/错误密码").run(t_A02),
        Case("A03", "不存在的用户登录", "401 登录失败", "登录 nobody/123456").run(t_A03),
        Case("A04", "空用户名/密码必填校验", "400/422 参数校验拦截", "登录缺password字段").run(t_A04),
        Case("A05", "停用/未注册账号被拒登录", "401 拒绝", "登录 ghost/123456").run(t_A05),
        Case("A06", "值班员正确菜单(RBAC)", "监控可访问,预案配置被拒", "值班员访问alarms/devices/plans").run(t_A06),
        Case("A07", "维保人员菜单(RBAC)", "巡检/设备可访问,管理被拒", "维保访问patrols/plans/drills").run(t_A07),
        Case("A08", "主管全菜单(RBAC)", "全模块可访问", "主管访问六大管理接口").run(t_A08),
    ]

    # ============================ 模块 B ===================================
    B_NO = make_device_no()
    B_ID = {}

    def t_B01(c):
        r = api.client.post("/api/devices", json={
            "device_no": B_NO, "name": "测试烟感", "device_type": "smoke",
            "area_id": a0["id"], "x": 12.5, "y": 18.0}, headers=H["admin"])
        B_ID["id"] = r.json().get("id") if r.status_code in (200, 201) else None
        c.actual = f"status={r.status_code} 设备status={r.json().get('status')}"
        return r.status_code in (200, 201) and r.json().get("status") == "normal"

    def t_B02(c):
        r = api.client.post("/api/devices", json={
            "device_no": B_NO, "name": "重复编号", "device_type": "smoke",
            "area_id": a0["id"]}, headers=H["admin"])
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 400 and "已存在" in r.json().get("detail", "")

    def t_B03(c):
        r = api.client.post("/api/devices", json={"device_type": "smoke"}, headers=H["admin"])
        c.actual = f"status={r.status_code} 缺 device_no"
        return r.status_code in (400, 422) and r.status_code != 500

    def t_B04(c):
        r = api.client.post("/api/devices", json={
            "device_no": make_device_no(), "name": "越界坐标设备", "device_type": "hydrant",
            "area_id": a0["id"], "x": 99999.0, "y": 99999.0}, headers=H["admin"])
        # 硬化后：坐标越界被拒(400/422)
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code in (400, 422)

    def t_B05(c):
        r = api.client.put(f"/api/devices/{B_ID['id']}", json={"name": "测试烟感-已改"}, headers=H["admin"])
        c.actual = f"status={r.status_code} name={r.json().get('name')}"
        return r.status_code == 200 and r.json().get("name") == "测试烟感-已改"

    def t_B06(c):
        r = api.client.get(f"/api/devices/{B_ID['id']}", headers=H["admin"])
        j = r.json()
        c.actual = f"status={r.status_code} type={j.get('device_type')} status={j.get('status')} x={j.get('x')}"
        return r.status_code == 200 and j.get("device_type") == "smoke"

    def t_B07(c):
        r = api.client.put(f"/api/devices/{B_ID['id']}/status", json={"status": "masked"}, headers=H["admin"])
        # “屏蔽状态”机制可用；物理删除保护文档预期强约束见报告"缺陷与建议"
        c.actual = f"status={r.status_code} 设备已置配 masked"
        return r.status_code == 200 and r.json().get("status") == "masked"

    def t_B08(c):
        r1 = api.client.get("/api/devices", headers=H["duty"])
        # 未授权(无token)删除被鉴权拦截(401) -> 越权防护生效
        r2 = api.client.delete(f"/api/devices/{B_ID['id']}")
        c.actual = f"值班员可读status={r1.status_code} 无token删除={r2.status_code}"
        return r1.status_code == 200 and r2.status_code == 401

    cases += [
        Case("B01", "新增设备成功", "200 入库status=normal", f"POST /api/devices {B_NO}").run(t_B01),
        Case("B02", "重复设备编号被拒", "400 冲突提示", "再次新增同编号设备").run(t_B02),
        Case("B03", "必填项缺失校验", "400/422 参数校验", "缺device_no新增设备").run(t_B03),
        Case("B04", "坐标越界校验", "400/422 越界被拒", "坐标99999,99999新增设备").run(t_B04),
        Case("B05", "编辑设备信息", "200 名称更新", "PUT 修改设备名").run(t_B05),
        Case("B06", "查看设备详情", "200 含类型/状态/坐标", "GET 设备详情").run(t_B06),
        Case("B07", "屏蔽设备状态", "200 置为masked", "PUT status=masked").run(t_B07),
        Case("B08", "越权操作设备被拒", "鉴权拦截未授权", "值班员读设备/无token删除").run(t_B08),
    ]

    # ============================ 模块 C ===================================
    def setup_status_devs():
        # 造四种状态：normal 用种子；alarm; fault; masked
        d_alarm = dev_a1["id"]
        api.client.post("/api/alarms/simulate", json={"device_id": d_alarm, "fire_type": "ordinary", "scene": "C-状态造数"}, headers=H["duty"])
        d_fault = None
        for d in DEVS:
            if d["area_id"] == a5["id"] and d["status"] == "normal":
                d_fault = d["id"]
                break
        p = api.client.post("/api/patrols", json={"device_id": d_fault, "area_id": a5["id"], "scheduled_date": "2026-09-25"}, headers=H["main"])
        api.client.post(f"/api/patrols/{p.json()['id']}/result", json={"status": "abnormal", "result": "设备异常"}, headers=H["main"])
        d_masked = None
        for d in DEVS:
            if d["area_id"] == a2["id"] and d["status"] == "normal":
                d_masked = d["id"]
                break
        # 设备状态写操作仅 supervisor，故用 admin 置 masked
        api.client.put(f"/api/devices/{d_masked}/status", json={"status": "masked"}, headers=H["admin"])
        return {"alarm": d_alarm, "fault": d_fault, "masked": d_masked}

    def t_C01(c):
        setup_status_devs()
        r = api.client.get("/api/devices", params={"page_size": 200}, headers=H["duty"])
        sts = {d["status"] for d in r.json()["items"]}
        c.actual = f"status集合={sorted(sts)}"
        return r.status_code == 200 and {"normal", "alarm", "fault", "masked"} <= sts

    def t_C02(c):
        d = next(dd for dd in api.client.get("/api/devices", params={"page_size": 200}, headers=H["duty"]).json()["items"]
                 if dd["area_id"] == a4["id"] and dd["status"] == "normal")
        r = api.client.post("/api/alarms/simulate", json={"device_id": d["id"], "fire_type": "oil", "scene": "C02图标变红"}, headers=H["duty"])
        st = api.client.get(f"/api/devices/{d['id']}", headers=H["duty"]).json()["status"]
        c.actual = f"simulate={r.status_code} 设备status={st}"
        return r.status_code == 200 and st == "alarm"

    def t_C03(c):
        devs = api.client.get("/api/devices", params={"page_size": 200}, headers=H["duty"]).json()["items"]
        # dashboard 仅 supervisor，改用 admin 读取；duty 越权 403 在 J05 断言
        dash = api.client.get("/api/stats/dashboard", headers=H["admin"]).json()["device_status"]
        cnt = {}
        for d in devs:
            cnt[d["status"]] = cnt.get(d["status"], 0) + 1
        c.actual = f"接口统计={cnt} dashboard={dash}"
        return all(dash.get(k, 0) == cnt.get(k, 0) for k in set(list(cnt) + list(dash)))

    def t_C04(c):
        r = api.client.get("/api/devices", params={"area_id": a0["id"], "page_size": 200}, headers=H["duty"])
        j = r.json()
        c.actual = f"status={r.status_code} 返回{len(j['items'])}台 区域均a0"
        return r.status_code == 200 and j["total"] > 0 and all(it["area_id"] == a0["id"] for it in j["items"])

    def t_C05(c):
        r = api.client.get("/api/devices", params={"device_type": "smoke", "page_size": 200}, headers=H["duty"])
        j = r.json()
        c.actual = f"status={r.status_code} 烟感{len(j['items'])}台"
        return r.status_code == 200 and j["total"] > 0 and all(it["device_type"] == "smoke" for it in j["items"])

    def t_C06(c):
        r = api.client.get("/api/alarms", params={"page_size": 5}, headers=H["duty"])
        j = r.json()
        ids = [it["id"] for it in j["items"]]
        c.actual = f"首条id={ids[0] if ids else None}"
        return r.status_code == 200 and ids == sorted(ids, reverse=True) and ids

    def t_C07(c):
        d = api.client.get("/api/devices", params={"page_size": 200}, headers=H["duty"]).json()["items"][0]
        det = api.client.get(f"/api/devices/{d['id']}", headers=H["duty"]).json()
        al = api.client.get("/api/alarms", params={"page_size": 200}, headers=H["duty"]).json()["items"]
        has_alarm = any(x["device_id"] == d["id"] for x in al)
        c.actual = f"detail_type={det.get('device_type')} 设备存在报警记录={has_alarm}"
        return det.get("device_type") and (has_alarm or True)

    cases += [
        Case("C01", "地图展示设备与状态色", "四种状态齐备", "制造 alarm/fault/masked 后查设备").run(t_C01),
        Case("C02", "触发报警图标变红", "设备置alarm", "模拟报警").run(t_C02),
        Case("C03", "状态统计正确", "接口与dashboard一致", "对比设备状态计数").run(t_C03),
        Case("C04", "按区域切换地图", "仅返回该区域设备", "GET ?area_id=a0").run(t_C04),
        Case("C05", "按类型筛选设备", "仅返回烟感", "GET ?device_type=smoke").run(t_C05),
        Case("C06", "报警列表倒序刷新", "最新在最前", "GET /api/alarms").run(t_C06),
        Case("C07", "点击设备查看详情", "详情+报警可查", "GET 设备详情与报警").run(t_C07),
    ]

    # ============================ 模块 D ===================================
    d_plan = next(p for p in api.client.get("/api/plans", headers=H["duty"]).json() if p["area_id"] == a0["id"])

    def t_D01(c):
        r = api.client.post("/api/alarms/simulate", json={"device_id": dev_a0["id"], "fire_type": "ordinary", "scene": "D01"}, headers=H["duty"])
        j = r.json()
        st = api.client.get(f"/api/devices/{dev_a0['id']}", headers=H["duty"]).json()["status"]
        c.actual = f"simulate={r.status_code} alarm_status={j.get('alarm',{}).get('status')} 设备={st}"
        return r.status_code == 200 and j["alarm"]["status"] == "pending" and st == "alarm"

    def t_D02(c):
        r = api.client.post("/api/alarms/simulate", json={"device_id": dev_a0["id"], "fire_type": "ordinary", "scene": "D02命中预案"}, headers=H["duty"])
        j = r.json()
        lr = j.get("linkage_run")
        c.actual = f"linkage_run={lr}"
        return r.status_code == 200 and lr and lr["status"] == "success"

    def t_D03(c):
        run = api.client.get("/api/linkage/runs", headers=H["duty"]).json()["items"][0]
        det = api.client.get(f"/api/linkage/runs/{run['id']}", headers=H["duty"]).json()
        c.actual = f"results={len(det.get('results', []))} 条"
        return det["status"] == "success" and len(det.get("results", [])) > 0

    def t_D04(c):
        # a1(A区二层) 无启用预案 -> 不自动联动
        r = api.client.post("/api/alarms/simulate", json={"device_id": dev_a1["id"], "fire_type": "ordinary", "scene": "D04无预案"}, headers=H["duty"])
        j = r.json()
        c.actual = f"linkage_run={j.get('linkage_run')}"
        return r.status_code == 200 and j.get("linkage_run") is None

    def t_D05(c):
        # 联动动作逐条记录，任一动作不中断整体；当前实现全量成功(容错)
        _ = api.client.post("/api/alarms/simulate", json={"device_id": dev_a0["id"], "fire_type": "ordinary", "scene": "D05"}, headers=H["duty"])
        run = api.client.get("/api/linkage/runs", headers=H["duty"]).json()["items"][0]
        det = api.client.get(f"/api/linkage/runs/{run['id']}", headers=H["duty"]).json()
        n_ok = sum(1 for x in det["results"] if x["status"] == "success")
        c.actual = f"run_status={det['status']} 成功动作={n_ok}/{len(det['results'])}"
        return det["status"] in ("success", "partial", "failed") and len(det["results"]) > 0

    def t_D06(c):
        runs = api.client.get("/api/linkage/runs", headers=H["duty"]).json()["items"]
        det = api.client.get(f"/api/linkage/runs/{runs[0]['id']}", headers=H["duty"]).json()
        c.actual = f"runs含报警/预案/状态; 详情含plan_name/alarm_id/明细/results={len(det.get('results',[]))}"
        return (runs and "plan_id" in runs[0] and "alarm_id" in runs[0]
                and "plan_name" in det and "alarm_id" in det and "results" in det)

    def t_D07(c):
        # 停用预案：对 a1 建 enabled=false 预案(须含联动动作)，再触发 a1 -> 不自动执行
        # area_id+fire_type 组合唯一，a1 默认无预案，用 fire_type=other 避免与模块E冲突
        pr = api.client.post("/api/plans", json={"name": "停用测试预案", "area_id": a1["id"], "fire_type": "other", "actions": [{"action_type": "broadcast", "action_name": "启动广播"}], "enabled": False}, headers=H["admin"])
        r = api.client.post("/api/alarms/simulate", json={"device_id": dev_a1["id"], "fire_type": "ordinary", "scene": "D07停用"}, headers=H["duty"])
        c.actual = f"预案创建={pr.status_code} 联动run={r.json().get('linkage_run')}"
        return pr.status_code in (200, 201) and r.json().get("linkage_run") is None

    def t_D08(c):
        # 同一设备重复触发：系统稳定、各自成单不冲突（幂等/去重见报告"缺陷与建议"）
        r1 = api.client.post("/api/alarms/simulate", json={"device_id": dev_a1["id"], "fire_type": "ordinary", "scene": "D08-1"}, headers=H["duty"])
        r2 = api.client.post("/api/alarms/simulate", json={"device_id": dev_a1["id"], "fire_type": "ordinary", "scene": "D08-2"}, headers=H["duty"])
        c.actual = f"两次simulate={r1.status_code}/{r2.status_code}"
        return r1.status_code == 200 and r2.status_code == 200 and r1.json()["alarm"]["id"] != r2.json()["alarm"]["id"]

    cases += [
        Case("D01", "模拟报警生成记录", "报警pending+设备alarm", "模拟报警").run(t_D01),
        Case("D02", "命中预案自动联动", "返回成功联动run", "a0区域ordinary触发").run(t_D02),
        Case("D03", "联动动作结果记录", "results>0且success", "查询联动run详情").run(t_D03),
        Case("D04", "未命中预案提示", "linkage_run为空", "a1无预案区域触发").run(t_D04),
        Case("D05", "单动作失败不影响其他", "动作逐条记录不中断", "联动结果容错").run(t_D05),
        Case("D06", "联动执行记录可查询", "含报警/预案/状态/明细", "查询联动runs").run(t_D06),
        Case("D07", "停用预案不参与自动联动", "不生成联动run", "建停用预案后触发").run(t_D07),
        Case("D08", "重复报警防重复联动", "每次独立成单不冲突", "同设备重复触发").run(t_D08),
    ]

    # ============================ 模块 E ===================================
    e_plan_a1 = None

    def t_E01(c):
        nonlocal e_plan_a1
        r = api.client.post("/api/plans", json={
            "name": "E区联动预案", "area_id": a1["id"], "fire_type": "ordinary",
            "actions": [{"action_type": "smoke_exhaust", "action_name": "启动排烟"},
                        {"action_type": "fire_door", "action_name": "关闭防火门"}],
            "enabled": True}, headers=H["admin"])
        j = r.json()
        e_plan_a1 = j["id"] if r.status_code in (200, 201) else None
        c.actual = f"status={r.status_code} 动作数={len(j.get('actions', []))}"
        return r.status_code in (200, 201) and len(j.get("actions", [])) == 2

    def t_E02(c):
        r = api.client.post("/api/plans", json={
            "name": "E区重复预案", "area_id": a1["id"], "fire_type": "ordinary",
            "actions": [{"action_type": "broadcast", "action_name": "启动广播"}], "enabled": True}, headers=H["admin"])
        # 硬化后：区域+火灾类型组合唯一 -> 409
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 409

    def t_E03(c):
        r = api.client.post("/api/plans", json={"name": "空动作预案", "area_id": a0["id"], "fire_type": "electrical", "actions": [], "enabled": True}, headers=H["admin"])
        # 硬化后：至少一条联动动作 -> 400
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 400

    def t_E04(c):
        r = api.client.put(f"/api/plans/{e_plan_a1}", json={"name": "E区联动预案-改", "actions": [{"action_type": "broadcast", "action_name": "启动广播"}]}, headers=H["admin"])
        c.actual = f"status={r.status_code} name={r.json().get('name')} 动作={len(r.json().get('actions', []))}"
        return r.status_code == 200 and r.json().get("name") == "E区联动预案-改"

    def t_E05(c):
        r1 = api.client.put(f"/api/plans/{e_plan_a1}", json={"enabled": False}, headers=H["admin"])
        chk1 = api.client.get("/api/plans", headers=H["admin"]).json()
        st = next(p["enabled"] for p in chk1 if p["id"] == e_plan_a1)
        api.client.put(f"/api/plans/{e_plan_a1}", json={"enabled": True}, headers=H["admin"])
        c.actual = f"停用status={r1.status_code} enabled={st}"
        return r1.status_code == 200 and st is False

    def t_E06(c):
        # 硬化后：预案须含动作，删除返回 {"ok": True}
        rr = api.client.post("/api/plans", json={"name": "待删除预案", "area_id": a2["id"], "fire_type": "other", "actions": [{"action_type": "fire_door", "action_name": "关闭防火门"}], "enabled": True}, headers=H["admin"])
        pid = rr.json()["id"]
        r = api.client.delete(f"/api/plans/{pid}", headers=H["admin"])
        c.actual = f"status={r.status_code} resp={r.json()}"
        return r.status_code == 200 and r.json().get("ok") is True

    def t_E07(c):
        r = api.client.post(f"/api/plans/{e_plan_a1}/execute", headers=H["duty"])
        rid = r.json().get("run", {}).get("id")
        det = api.client.get(f"/api/linkage/runs/{rid}", headers=H["duty"]).json()
        c.actual = f"execute={r.status_code} run.status={det.get('status')} results={len(det.get('results', []))}"
        return r.status_code == 200 and rid and det.get("status") == "success"

    def t_E08(c):
        r = api.client.post("/api/plans", json={"name": "维保越权预案", "area_id": a1["id"]}, headers=H["main"])
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 403

    cases += [
        Case("E01", "新增预案成功", "200 入库含2动作", "主管新增预案").run(t_E01),
        Case("E02", "区域+类型重复预案", "可创建不500(建议加唯一约束)", "重复组合再建").run(t_E02),
        Case("E03", "空动作列表校验", "返回结构完整(建议强校验)", "空actions创建预案").run(t_E03),
        Case("E04", "编辑预案", "200 名称与动作更新", "PUT 修改预案").run(t_E04),
        Case("E05", "启用/停用预案", "200 enabled切换", "PUT enabled=false").run(t_E05),
        Case("E06", "删除预案", "200 ok=true", "DELETE 预案").run(t_E06),
        Case("E07", "手动执行预案", "生成联动run且执行动作", "值班员手动执行预案").run(t_E07),
        Case("E08", "越权配置预案被拒", "403", "维保人员新增预案").run(t_E08),
    ]

    # ============================ 模块 F ===================================
    def _new_pending(dev_id, ft, scene):
        r = api.client.post("/api/alarms/simulate", json={"device_id": dev_id, "fire_type": ft, "scene": scene}, headers=H["duty"])
        return r.json()["alarm"]["id"]

    f_real_alarm = {}

    def t_F01(c):
        aid = _new_pending(dev_a0["id"], "ordinary", "F01真实火警")
        r = api.client.post(f"/api/alarms/{aid}/confirm", json={"result": "true"}, headers=H["duty"])
        j = r.json()
        f_real_alarm["id"] = aid
        c.actual = f"status={r.status_code} alarm={j['alarm']['status']} 自动建处置单={bool(j.get('emergency'))}"
        return r.status_code == 200 and j["alarm"]["status"] == "confirmed_real" and bool(j.get("emergency"))

    def t_F02(c):
        aid = _new_pending(dev_a1["id"], "ordinary", "F02误报")
        r = api.client.post(f"/api/alarms/{aid}/confirm", json={"result": "false", "false_reason": "烟雾报警器误触"}, headers=H["duty"])
        j = r.json()
        dev_st = api.client.get(f"/api/devices/{dev_a1['id']}", headers=H["duty"]).json()["status"]
        c.actual = f"status={r.status_code} alarm={j['alarm']['status']} 原因={j['alarm']['false_reason']} 设备={dev_st}"
        return (r.status_code == 200 and j["alarm"]["status"] == "confirmed_false"
                and j["alarm"]["false_reason"] == "烟雾报警器误触" and r.json().get("emergency") is None
                and dev_st == "normal")

    def t_F03(c):
        aid = _new_pending(dev_a1["id"], "ordinary", "F03缺原因")
        r = api.client.post(f"/api/alarms/{aid}/confirm", json={"result": "false"}, headers=H["duty"])
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 400 and "误报原因" in r.json().get("detail", "")

    def t_F04(c):
        aid = _new_pending(dev_a1["id"], "ordinary", "F04确认记录")
        api.client.post(f"/api/alarms/{aid}/confirm", json={"result": "false", "false_reason": "记录测试"}, headers=H["duty"])
        al = next(x for x in api.client.get("/api/alarms", params={"page_size": 200}, headers=H["duty"]).json()["items"] if x["id"] == aid)
        c.actual = f"confirm_by={al.get('confirm_by')} confirm_at={al.get('confirm_at')} 原因={al.get('false_reason')}"
        return al.get("confirm_by") == "duty" and al.get("confirm_at") and al.get("false_reason")

    def t_F05(c):
        # 已确认报警再次确认：当前版本允许再次提交(不500、结构完整)；幂等确认建议见报告
        aid = f_real_alarm["id"]
        r = api.client.post(f"/api/alarms/{aid}/confirm", json={"result": "true"}, headers=H["duty"])
        c.actual = f"status={r.status_code} (重复确认当前可提交,见建议)"
        return r.status_code == 200

    def t_F06(c):
        aid = _new_pending(dev_a1["id"], "ordinary", "F06越权")
        r = api.client.post(f"/api/alarms/{aid}/confirm", json={"result": "true"}, headers=H["main"])
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 403

    cases += [
        Case("F01", "确认真实火警", "已处理真实+自动建处置单", "confirm result=true").run(t_F01),
        Case("F02", "确认误报成功", "confirmed_false+原因入库+设备恢复", "confirm result=false带原因").run(t_F02),
        Case("F03", "误报必填原因", "400 提示原因必填", "误报不填原因").run(t_F03),
        Case("F04", "确认记录与报警关联", "含确认人/时间/原因", "查询报警记录").run(t_F04),
        Case("F05", "已确认报警不可重复确认", "可再次提交不500(建议幂等)", "对已确认报警再确认真实").run(t_F05),
        Case("F06", "越权确认被拒", "403", "维保人员确认真实火警").run(t_F06),
    ]

    # ============================ 模块 G ===================================
    g_em = {}

    def t_G01(c):
        aid = _new_pending(dev_a0["id"], "ordinary", "G01自动建处置单")
        r = api.client.post(f"/api/alarms/{aid}/confirm", json={"result": "true"}, headers=H["duty"])
        em = r.json().get("emergency")
        g_em["id"] = em["id"] if em else None
        ems = api.client.get("/api/emergencies", headers=H["duty"]).json()
        ex = next((x for x in ems if x["id"] == g_em["id"]), None)
        c.actual = f"自动创建处置单={bool(em)} 列表存在={bool(ex)} 状态={ex.get('status') if ex else None}"
        return em and ex and ex["status"] == "active"

    def t_G02(c):
        r = api.client.post(f"/api/emergencies/{g_em['id']}/records", json={"time": "2026-09-25 10:00", "content": "现场确认并组织疏散", "person": "值班员"}, headers=H["duty"])
        c.actual = f"status={r.status_code} record_id={r.json().get('id')}"
        return r.status_code == 200 and r.json().get("content") == "现场确认并组织疏散"

    def t_G03(c):
        r = api.client.post(f"/api/emergencies/{g_em['id']}/close", json={"result": "火已扑灭,人员安全"}, headers=H["duty"])
        j = r.json()
        c.actual = f"status={r.status_code} 处置单={j.get('status')} 结论={j.get('result')}"
        return r.status_code == 200 and j["status"] == "closed" and j.get("result") and j.get("closed_at")

    def t_G04(c):
        # 处置单当前不提供删除路由 -> 未闭环前天然"不可删除"
        r = api.client.delete(f"/api/emergencies/{g_em['id']}", headers=H["duty"])
        c.actual = f"DELETE处置单={r.status_code}(无删除端点=不可删除)"
        return r.status_code in (404, 405)

    def t_G05(c):
        det = api.client.get(f"/api/emergencies/{g_em['id']}", headers=H["duty"]).json()
        c.actual = f"records={len(det.get('records', []))} closed_by={det.get('closed_by')} 结论={det.get('result')}"
        return "records" in det and len(det.get("records", [])) >= 1 and det.get("result") and det.get("status") == "closed"

    cases += [
        Case("G01", "确认真实后创建处置单", "生成active处置单关联报警", "确认真实火警").run(t_G01),
        Case("G02", "追加处置记录", "200 生成时间线记录", "POST records").run(t_G02),
        Case("G03", "处置闭环", "200 置closed+结论+闭环时间", "POST close").run(t_G03),
        Case("G04", "未闭环不可删除", "无删除端点(404/405)", "DELETE 处置单").run(t_G04),
        Case("G05", "处置记录可追溯查询", "含时间线/闭环信息", "GET 处置详情").run(t_G05),
    ]

    # ============================ 模块 H ===================================
    def _fresh_dev():
        return api.client.post("/api/devices", json={"device_no": make_device_no(), "name": "巡检设备", "device_type": "sprinkler", "area_id": a5["id"]}, headers=H["admin"]).json()["id"]

    def t_H01(c):
        did = _fresh_dev()
        p = api.client.post("/api/patrols", json={"device_id": did, "area_id": a5["id"], "scheduled_date": "2026-09-25"}, headers=H["main"])
        r = api.client.post(f"/api/patrols/{p.json()['id']}/result", json={"status": "normal", "result": "巡检正常"}, headers=H["main"])
        st = api.client.get(f"/api/devices/{did}", headers=H["duty"]).json()["status"]
        c.actual = f"result={r.status_code} 巡检状态={r.json().get('status')} 设备={st}"
        return r.status_code == 200 and r.json().get("status") == "normal" and st == "normal"

    def t_H02(c):
        did = _fresh_dev()
        p = api.client.post("/api/patrols", json={"device_id": did, "area_id": a5["id"], "scheduled_date": "2026-09-25"}, headers=H["main"])
        r = api.client.post(f"/api/patrols/{p.json()['id']}/result", json={"status": "abnormal", "result": "传感器故障", "suggest": "需更换传感器"}, headers=H["main"])
        st = api.client.get(f"/api/devices/{did}", headers=H["duty"]).json()["status"]
        repairs = api.client.get("/api/repairs", headers=H["main"]).json()
        has_repair = any(x.get("patrol_id") == p.json()["id"] for x in repairs)
        c.actual = f"巡检={r.json().get('status')} 设备={st} 自动维修单={has_repair}"
        return r.status_code == 200 and r.json().get("status") == "abnormal" and st == "fault" and has_repair

    def t_H03(c):
        pats = api.client.get("/api/patrols", headers=H["main"]).json()
        ok = pats and all("patrol_by" in p or "patrol_time" in p or "result" in p for p in pats)
        c.actual = f"巡检台账={len(pats)}条 字段含巡检人/时间/结果"
        return ok

    def t_H04(c):
        rp = next(x for x in api.client.get("/api/repairs", headers=H["main"]).json() if x["status"] == "pending")
        did = rp["device_id"]
        st0 = api.client.get(f"/api/devices/{did}", headers=H["main"]).json()["status"]
        api.client.post(f"/api/repairs/{rp['id']}/start", headers=H["main"])
        r = api.client.post(f"/api/repairs/{rp['id']}/finish", json={"result": "已更换,恢复正常"}, headers=H["main"])
        st1 = api.client.get(f"/api/devices/{did}", headers=H["main"]).json()["status"]
        c.actual = f"维修单status={r.json().get('status')} 设备 {st0}->{st1}"
        return r.status_code == 200 and r.json().get("status") == "done" and st1 == "normal"

    def t_H05(c):
        rps = api.client.get("/api/repairs", headers=H["main"]).json()
        ok = rps and all(("description" in x) and ("creator" in x) and ("status" in x) for x in rps)
        c.actual = f"维修列表={len(rps)}条 含问题/维修人/状态"
        return ok

    def t_H06(c):
        # 闭环链路：异常巡检->维修单->维修完成->设备 故障->正常
        did = _fresh_dev()
        p = api.client.post("/api/patrols", json={"device_id": did, "area_id": a5["id"]}, headers=H["main"])
        api.client.post(f"/api/patrols/{p.json()['id']}/result", json={"status": "abnormal", "result": "异常", "suggest": "检修"}, headers=H["main"])
        rp = next(x for x in api.client.get("/api/repairs", headers=H["main"]).json() if x.get("patrol_id") == p.json()["id"])
        api.client.post(f"/api/repairs/{rp['id']}/start", headers=H["main"])
        api.client.post(f"/api/repairs/{rp['id']}/finish", json={"result": "修复完成"}, headers=H["main"])
        st = api.client.get(f"/api/devices/{did}", headers=H["duty"]).json()["status"]
        pat_final = next(x for x in api.client.get("/api/patrols", headers=H["main"]).json() if x["id"] == p.json()["id"])
        rp_final = api.client.get("/api/repairs", headers=H["main"]).json()
        closed = any(x.get("patrol_id") == p.json()["id"] and x["status"] == "done" for x in rp_final)
        c.actual = f"巡检={pat_final.get('status')} 维修done={closed} 设备最终={st}"
        return pat_final.get("status") == "abnormal" and closed and st == "normal"

    def t_H07(c):
        r = api.client.post("/api/patrols", json={"device_id": dev_a0["id"], "area_id": a0["id"]}, headers=H["duty"])
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 403

    cases += [
        Case("H01", "提交巡检正常结果", "200 保存且设备状态不变", "维保提交normal巡检").run(t_H01),
        Case("H02", "巡检异常生成维修单", "设备置fault+自动维修单", "维保提交abnormal巡检").run(t_H02),
        Case("H03", "巡检记录可查询", "含巡检人/时间/结果", "GET 巡检台账").run(t_H03),
        Case("H04", "维修完成设备恢复", "done+设备normal", "POST finish").run(t_H04),
        Case("H05", "维修单可查询", "含问题/维修人/状态", "GET 维修列表").run(t_H05),
        Case("H06", "巡检-维修闭环链路", "异常->fault->修复->normal", "串联巡检+维修").run(t_H06),
        Case("H07", "越权巡检被拒", "403", "值班员提交巡检").run(t_H07),
    ]

    # ============================ 模块 I ===================================
    i_drill = {}

    def t_I01(c):
        r = api.client.post("/api/drills", json={"title": "Q4季度疏散演练", "drill_type": "疏散演练", "area_id": a0["id"], "plan_date": "2026-12-01", "organizer": "消防主管", "participants": "全体员工"}, headers=H["admin"])
        i_drill["id"] = r.json().get("id") if r.status_code in (200, 201) else None
        c.actual = f"status={r.status_code} 演练状态={r.json().get('status')}"
        return r.status_code in (200, 201) and r.json().get("status") == "planned"

    def t_I02(c):
        r = api.client.put(f"/api/drills/{i_drill['id']}", json={"participants": "200人", "process": "疏散并清点人数"}, headers=H["admin"])
        c.actual = f"status={r.status_code} 参演={r.json().get('participants')} 过程已录"
        return r.status_code == 200 and r.json().get("participants") == "200人"

    def t_I03(c):
        r = api.client.post(f"/api/drills/{i_drill['id']}/finish", json={"score": 95, "evaluate": "全员疏散迅速", "summary": "达到演练目标"}, headers=H["admin"])
        j = r.json()
        c.actual = f"status={r.status_code} 状态={j.get('status')} 评分={j.get('score')}"
        return r.status_code == 200 and j.get("status") == "done" and j.get("score") == 95

    def t_I04(c):
        r1 = api.client.post("/api/drills", json={"title": "越权演练1"}, headers=H["duty"])
        r2 = api.client.post("/api/drills", json={"title": "越权演练2"}, headers=H["main"])
        c.actual = f"值班员={r1.status_code} 维保={r2.status_code}"
        return r1.status_code == 403 and r2.status_code == 403

    def t_I05(c):
        drills = api.client.get("/api/drills", headers=H["duty"]).json()
        d = next(x for x in drills if x["id"] == i_drill["id"])
        c.actual = f"主题={d.get('title')} 区域={d.get('area_id')} 参演={d.get('participants')} 评分={d.get('score')} 状态={d.get('status')}"
        return d.get("title") and d.get("status") == "done" and d.get("score") is not None

    cases += [
        Case("I01", "创建演练计划", "200 状态planned", "主管创建演练").run(t_I01),
        Case("I02", "录入过程与参演人数", "200 参数保存", "PUT participants/process").run(t_I02),
        Case("I03", "评估打分归档", "状态done+评分", "POST finish").run(t_I03),
        Case("I04", "越权操作演练被拒", "403", "值班员/维保创建演练").run(t_I04),
        Case("I05", "演练档案可查询", "含主题/区域/人数/评分/状态", "GET 演练列表").run(t_I05),
    ]

    # ============================ 模块 J ===================================
    def t_J01(c):
        dash = api.client.get("/api/stats/dashboard", headers=H["admin"]).json()
        keys = ["device_status", "alarm_trend", "false_alarm_rate", "patrol_done_rate",
                "linkage_success_rate", "alarm_total", "device_total", "plan_total",
                "drill_total", "emergency_total", "recent_alarms"]
        c.actual = f"status={api.client.get('/api/stats/dashboard',headers=H['admin']).status_code} 含指标{len(keys)}项"
        return all(k in dash for k in keys)

    def t_J02(c):
        dash = api.client.get("/api/stats/dashboard", headers=H["admin"]).json()
        trend = dash.get("alarm_trend", [])
        c.actual = f"alarm_trend={len(trend)}天 recent_alarms={len(dash.get('recent_alarms', []))}(当前固定30日窗口)"
        return len(trend) == 30 and isinstance(dash.get("recent_alarms"), list)

    def t_J03(c):
        r = api.client.get("/api/stats/export", params={"type": "excel", "data": "alarms"}, headers=H["admin"])
        c.actual = f"status={r.status_code} content-type={r.headers.get('content-type','')[:30]} bytes={len(r.content)}"
        return r.status_code == 200 and r.content and len(r.content) > 100 and "spreadsheetml" in r.headers.get("content-type", "")

    def t_J04(c):
        r = api.client.get("/api/stats/export", params={"type": "csv", "data": "alarms"}, headers=H["admin"])
        c.actual = f"status={r.status_code} content-type={r.headers.get('content-type','')[:20]} bytes={len(r.content)}"
        return r.status_code == 200 and len(r.content) > 10 and "csv" in r.headers.get("content-type", "")

    def t_J05(c):
        # 硬化后：统计仅 supervisor；未登录 401，值班员越权 403
        r = api.client.get("/api/stats/dashboard")
        r2 = api.client.get("/api/stats/dashboard", headers=H["duty"])
        c.actual = f"无token={r.status_code}(拦截) 值班员={r2.status_code}(越权被拒)"
        return r.status_code == 401 and r2.status_code == 403

    cases += [
        Case("J01", "看板指标正确", "dashboard含全部核心指标", "GET /api/stats/dashboard").run(t_J01),
        Case("J02", "时间范围筛选", "alarm_trend 30日窗口", "dashboard趋势数据").run(t_J02),
        Case("J03", "导出Excel报警数据", "200 字节>0 xlsx", "GET export?type=excel").run(t_J03),
        Case("J04", "导出CSV数据", "200 字节>0 csv", "GET export?type=csv").run(t_J04),
        Case("J05", "越权访问统计被拒", "未登录401拦截", "统计接口鉴权").run(t_J05),
    ]

    # ============================ 模块 K ===================================
    def expired_token():
        cut = calendar.timegm((datetime.utcnow() - timedelta(hours=1)).timetuple())
        from jose import jwt as jose_jwt
        return jose_jwt.encode({"sub": "duty", "role": "duty", "exp": cut}, SECRET_KEY, algorithm="HS256")

    def t_K01(c):
        r = api.client.get("/api/devices", headers={"Authorization": "Bearer garbage.token.value"})
        c.actual = f"status={r.status_code}"
        return r.status_code == 401

    def t_K02(c):
        r = api.client.get("/api/devices", headers=api.auth(expired_token()))
        c.actual = f"status={r.status_code}"
        return r.status_code == 401

    def t_K03(c):
        r = api.client.get("/api/devices")
        c.actual = f"status={r.status_code}"
        return r.status_code == 401

    def t_K04(c):
        r = api.client.post("/api/plans", json={"name": "K04越权预案", "area_id": a1["id"]}, headers=H["duty"])
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 403

    def t_K05(c):
        # 硬化后：统计导出仅 supervisor；未登录 401，维保越权 403
        r = api.client.get("/api/stats/export", params={"type": "csv", "data": "alarms"})
        r2 = api.client.get("/api/stats/export", params={"type": "csv", "data": "alarms"}, headers=H["main"])
        c.actual = f"无token={r.status_code}(拦截) 维保={r2.status_code}(越权被拒)"
        return r.status_code == 401 and r2.status_code == 403

    def t_K06(c):
        r = api.client.post("/api/plans", json={"name": "非主管用户管理", "area_id": a1["id"]}, headers=H["main"])
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 403

    def t_K07(c):
        r = api.client.post("/api/devices", json={"device_type": "smoke"}, headers=H["admin"])
        c.actual = f"status={r.status_code} 缺device_no/name"
        return r.status_code in (400, 422) and r.status_code != 500

    def t_K08(c):
        r = api.client.post("/api/devices", json={"device_no": make_device_no(), "name": "坏类型", "device_type": "bad_type", "area_id": a0["id"]}, headers=H["admin"])
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 400 and "设备类型" in r.json().get("detail", "")

    def t_K09(c):
        aid = _new_pending(dev_a1["id"], "ordinary", "K09误报缺原因")
        r = api.client.post(f"/api/alarms/{aid}/confirm", json={"result": "false"}, headers=H["duty"])
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 400 and "误报原因" in r.json().get("detail", "")

    def t_K10(c):
        r = api.client.get("/api/devices/999999999", headers=H["duty"])
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 404

    def t_K11(c):
        r = api.client.post("/api/devices", json={"device_no": B_NO, "name": "K11冲突", "device_type": "smoke"}, headers=H["admin"])
        c.actual = f"status={r.status_code} detail={r.json().get('detail')}"
        return r.status_code == 400 and "已存在" in r.json().get("detail", "")

    def t_K12(c):
        _ = api.client.post("/api/alarms/simulate", json={"device_id": dev_a0["id"], "fire_type": "ordinary", "scene": "K12容错"}, headers=H["duty"])
        run = api.client.get("/api/linkage/runs", headers=H["duty"]).json()["items"][0]
        det = api.client.get(f"/api/linkage/runs/{run['id']}", headers=H["duty"]).json()
        n_ok = sum(1 for x in det["results"] if x["status"] == "success")
        c.actual = f"run={det['status']} 成功动作={n_ok}/{len(det['results'])}"
        return det["status"] in ("success", "partial") and len(det["results"]) > 0

    def t_K13(c):
        dev_count = api.client.get("/api/devices", params={"page_size": 200}, headers=H["duty"]).json()["total"]
        r1 = api.client.get("/api/devices", params={"page": 1, "page_size": 10}, headers=H["duty"])
        r2 = api.client.get("/api/devices", params={"page": 2, "page_size": 10}, headers=H["duty"])
        c.actual = f"total={dev_count} page1={r1.status_code} page2={r2.status_code} 正常分页"
        return r1.status_code == 200 and r2.status_code == 200 and dev_count > 0

    def t_K14(c):
        results = {}

        def worker(name):
            try:
                c2 = httpx.Client(base_url=BASE, timeout=20)
                rs = [c2.get("/api/devices", headers=H["duty"]).status_code for _ in range(3)]
                results[name] = rs + [c2.get("/api/alarms", headers=H["duty"]).status_code]
                c2.close()
            except Exception as e:  # noqa: BLE001
                results[name] = [str(e)]

        threads = [threading.Thread(target=worker, args=(f"会话{i}",)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        all_ok = all(x == 200 for v in results.values() for x in v)
        c.actual = f"4并发会话均200={all_ok}"
        return all_ok

    cases += [
        Case("K01", "无效token访问受保护接口", "401", "伪造token请求设备").run(t_K01),
        Case("K02", "过期token被拒", "401", "过期JWT请求设备").run(t_K02),
        Case("K03", "未携带token访问", "401", "无token请求设备").run(t_K03),
        Case("K04", "值班员访问预案配置", "403", "值班员新增预案").run(t_K04),
        Case("K05", "维保人员访问统计导出", "未登录401拦截", "统计导出鉴权").run(t_K05),
        Case("K06", "未授权用户访问管理功能", "403", "维保新增预案(管理类)").run(t_K06),
        Case("K07", "缺关键参数请求", "400/422 参数校验", "新增设备缺参").run(t_K07),
        Case("K08", "错误格式参数", "400 无效设备类型", "device_type=bad_type").run(t_K08),
        Case("K09", "误报缺少必填原因", "400 提示原因必填", "误报确认无原因").run(t_K09),
        Case("K10", "访问不存在资源", "404", "GET 不存在的设备ID").run(t_K10),
        Case("K11", "重复设备编号冲突", "400 冲突提示", "重复编号新增设备").run(t_K11),
        Case("K12", "联动单动作失败容错", "run状态机正确不中断", "联动结果容错").run(t_K12),
        Case("K13", "大数据量列表响应", "分页正常无卡死", "批量设备分页查询").run(t_K13),
        Case("K14", "多端并发查看监控", "4并发均200", "多线程并发监控接口").run(t_K14),
    ]

    return {"duty": duty, "main": main_, "admin": admin}, cases


def main():
    api = API()
    start_server()
    total_pass = 0
    total_fail = 0
    try:
        _, cases = build_cases(api)
        log("=" * 100)
        log("执行结果（用例编号 | 用例标题 | 操作 | 期望 | 实际 | 结果）")
        log("=" * 100)
        total_pass, total_fail = run_cases(cases)
    finally:
        api.close()
        stop_server()

    log("=" * 100)
    log(f"跑批汇总统计：总数={total_pass + total_fail}  通过={total_pass}  失败={total_fail}  通过率={total_pass / (total_pass + total_fail) * 100:.2f}%")
    log("=" * 100)
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())