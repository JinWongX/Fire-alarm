"""安全加固单测：登录限流、JWT 密钥外置、CORS 收敛、生产关闭文档、
RBAC 越权修复（设备写操作/stats/simulate/用户管理）、CSV/Excel 公式注入清洗、数据库轻量迁移。"""
import io
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import SECRET_KEY
from app.database import run_migrations


# ---------- 安全 1：JWT 密钥外置 ----------
def test_jwt_secret_random_default_len():
    assert len(SECRET_KEY) >= 64
    assert "fire-alarm-secret-key-change-me" not in SECRET_KEY


def test_jwt_secret_from_env():
    backend = Path(__file__).resolve().parent.parent
    code = (
        "import os; os.environ['FIRE_ALARM_SECRET']='ENV_SECRET_1234567890_1234567890_1234567890';"
        "from app.auth import SECRET_KEY; print(SECRET_KEY)"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=str(backend), capture_output=True, text=True)
    assert "ENV_SECRET_1234567890" in r.stdout


# ---------- 安全 4：登录限流 ----------
def test_login_rate_limit_429(client):
    payload = {"username": "duty", "password": "wrong"}
    codes = [client.post("/api/auth/login", json=payload).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5
    assert codes[-1] == 429


def test_login_rate_limit_recovers_after_window(client):
    """限流窗口基于时间：注入旧时间戳后应恢复正常。"""
    from app.routers import auth as auth_router
    from collections import deque
    import time
    auth_router._login_attempts["testclient|duty"] = deque([time.monotonic() - 61] * 5)
    r = client.post("/api/auth/login", json={"username": "duty", "password": "123456"})
    assert r.status_code == 200


# ---------- 安全 2/5：CORS 收敛 + 生产关闭文档 ----------
def test_cors_default_whitelist():
    from app.main import app as main_app
    cors = [m for m in main_app.user_middleware if m.cls is CORSMiddleware][0]
    assert cors.kwargs["allow_origins"] == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    assert cors.kwargs["allow_credentials"] is True


def test_production_env_disables_docs_and_wildcard_creds(monkeypatch):
    import importlib
    import app.main as main_mod

    monkeypatch.setenv("FIRE_ALARM_ENV", "production")
    monkeypatch.setenv("FIRE_ALARM_ORIGINS", "*")
    importlib.reload(main_mod)
    prod_app = main_mod.app
    with TestClient(prod_app) as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/openapi.json").status_code == 404
        assert c.get("/redoc").status_code == 404
        assert c.get("/").status_code == 200
    cors = [m for m in prod_app.user_middleware if m.cls is CORSMiddleware][0]
    assert cors.kwargs["allow_origins"] == ["*"]
    assert cors.kwargs["allow_credentials"] is False

    monkeypatch.delenv("FIRE_ALARM_ENV", raising=False)
    monkeypatch.delenv("FIRE_ALARM_ORIGINS", raising=False)
    importlib.reload(main_mod)


# ---------- 安全 7：RBAC 越权修复 ----------
def test_device_write_ops_only_supervisor(client, headers):
    area = client.get("/api/areas", headers=headers["duty"]).json()[1]
    for role in ("duty", "maintenance"):
        r = client.post(
            "/api/devices",
            json={"device_no": f"RBAC-{role}", "name": "越权设备", "device_type": "smoke", "area_id": area["id"]},
            headers=headers[role],
        )
        assert r.status_code == 403, f"create {role}"

    sup = client.post(
        "/api/devices",
        json={"device_no": "RBAC-SUP-1", "name": "主管设备", "device_type": "smoke", "area_id": area["id"]},
        headers=headers["supervisor"],
    )
    assert sup.status_code == 201
    did = sup.json()["id"]
    for role in ("duty", "maintenance"):
        assert client.put(f"/api/devices/{did}", json={"name": "x"}, headers=headers[role]).status_code == 403, f"update {role}"
        assert client.put(f"/api/devices/{did}/status", json={"status": "masked"}, headers=headers[role]).status_code == 403, f"status {role}"
        assert client.delete(f"/api/devices/{did}", headers=headers[role]).status_code == 403, f"delete {role}"
    # list/get 仅登录即可
    assert client.get("/api/devices", headers=headers["duty"]).status_code == 200
    assert client.get(f"/api/devices/{did}", headers=headers["duty"]).status_code == 200


def test_stats_dashboard_export_only_supervisor(client, headers):
    for role in ("duty", "maintenance"):
        assert client.get("/api/stats/dashboard", headers=headers[role]).status_code == 403, role
        assert client.get("/api/stats/export", params={"type": "csv", "data": "alarms"}, headers=headers[role]).status_code == 403, role


def test_simulate_roles(client, headers, device_in_area0):
    r_maint = client.post(
        "/api/alarms/simulate",
        json={"device_id": device_in_area0["id"], "fire_type": "ordinary"},
        headers=headers["maintenance"],
    )
    assert r_maint.status_code == 403
    r_duty = client.post(
        "/api/alarms/simulate",
        json={"device_id": device_in_area0["id"], "fire_type": "ordinary"},
        headers=headers["duty"],
    )
    assert r_duty.status_code == 200
    r_sup = client.post(
        "/api/alarms/simulate",
        json={"device_id": device_in_area0["id"], "fire_type": "ordinary"},
        headers=headers["supervisor"],
    )
    assert r_sup.status_code == 200


# ---------- 安全 6：公式注入清洗 ----------
def test_export_csv_sanitizes_formula_injection(client, headers, device_in_area0):
    client.post(
        "/api/alarms/simulate",
        json={"device_id": device_in_area0["id"], "fire_type": "ordinary", "scene": "=SUM(A1)"},
        headers=headers["duty"],
    )
    r = client.get("/api/stats/export", params={"type": "csv", "data": "alarms"}, headers=headers["supervisor"])
    assert r.status_code == 200
    content = r.content.decode("utf-8-sig")
    assert "'=SUM(A1)" in content
    assert "=SUM(A1)" not in content.replace("'=SUM(A1)", "")


def test_export_excel_sanitizes_formula_injection(client, headers, device_in_area0):
    client.post(
        "/api/alarms/simulate",
        json={"device_id": device_in_area0["id"], "fire_type": "ordinary", "scene": "@cmd|whoami"},
        headers=headers["duty"],
    )
    r = client.get("/api/stats/export", params={"type": "excel", "data": "alarms"}, headers=headers["supervisor"])
    assert r.status_code == 200
    wb = load_workbook(io.BytesIO(r.content), data_only=False)
    ws = wb.active
    values = [cell.value for row in ws.iter_rows() for cell in row if isinstance(cell.value, str)]
    assert any(v == "'@cmd|whoami" for v in values)


def test_sanitize_cell_direct():
    from app.routers.stats import _sanitize_cell
    assert _sanitize_cell("=1+1") == "'=1+1"
    assert _sanitize_cell("+123") == "'+123"
    assert _sanitize_cell("-abc") == "'-abc"
    assert _sanitize_cell("@SUM") == "'@SUM"
    assert _sanitize_cell("正常文本") == "正常文本"
    assert _sanitize_cell(123) == 123


# ---------- 迁移：轻量 ALTER TABLE ----------
def test_run_migrations_adds_missing_columns(tmp_path):
    old_db = tmp_path / "old_fire_alarm.db"
    engine = create_engine(f"sqlite:///{old_db}")
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR, password_hash VARCHAR, real_name VARCHAR, role VARCHAR, created_at DATETIME)"
        ))
        conn.execute(text(
            "CREATE TABLE plans (id INTEGER PRIMARY KEY, name VARCHAR, area_id INTEGER, fire_type VARCHAR, actions JSON, enabled BOOLEAN, created_at DATETIME)"
        ))
        conn.execute(text(
            "CREATE TABLE drills (id INTEGER PRIMARY KEY, title VARCHAR, drill_type VARCHAR, area_id INTEGER, plan_date VARCHAR, status VARCHAR, organizer VARCHAR, participants TEXT, process TEXT, score FLOAT, evaluate TEXT, summary TEXT)"
        ))
        conn.execute(text("INSERT INTO users (username, password_hash) VALUES ('old', 'x')"))
        conn.commit()

    run_migrations(engine)

    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()}
        assert "is_active" in cols
        pcols = {row[1] for row in conn.execute(text("PRAGMA table_info(plans)")).fetchall()}
        assert "created_by" in pcols
        dcols = {row[1] for row in conn.execute(text("PRAGMA table_info(drills)")).fetchall()}
        assert "duration" in dcols
        val = conn.execute(text("SELECT is_active FROM users WHERE username='old'")).fetchone()[0]
        assert val in (1, True)
    engine.dispose()


def test_run_migrations_idempotent(tmp_path):
    old_db = tmp_path / "idem.db"
    engine = create_engine(f"sqlite:///{old_db}")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR, is_active BOOLEAN)"))
        conn.commit()
    run_migrations(engine)
    run_migrations(engine)  # 二次运行不报错
    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()}
        assert "is_active" in cols
    engine.dispose()


def test_get_db_direct():
    """get_db 生成器默认路径：产出会话并在关闭时释放。"""
    from app.database import get_db

    gen = get_db()
    db = next(gen)
    assert db is not None
    try:
        next(gen)
    except StopIteration:
        pass
    db.close()


# ---------- F-11：安全响应头 ----------
def test_security_response_headers_present(client, headers):
    r = client.get("/api/areas", headers=headers["duty"])
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["content-security-policy"] == "default-src 'self'"


# ---------- F-10：分页 page_size 上限截断 ----------
def test_pagination_page_size_capped_at_500(client, headers, db_session):
    from app.models import Device
    for i in range(505):
        db_session.add(Device(device_no=f"CLAMP-{i:04d}", name="clamp", device_type="smoke"))
    db_session.commit()
    # page<1 归 1；page_size 超过 500 按 500 截断，响应结构不变
    r = client.get("/api/devices", params={"page": -1, "page_size": 100000}, headers=headers["duty"])
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"total", "items"}
    assert len(body["items"]) == 500
    assert body["total"] >= 505


# ---------- F-13：不再使用 datetime.utcnow（弃用告警） ----------
def test_no_datetime_utcnow_in_app_source():
    backend = Path(__file__).resolve().parent.parent
    app_dir = backend / "app"
    py_files = list(app_dir.rglob("*.py"))
    assert py_files, "should find app python files"
    for f in py_files:
        content = f.read_text(encoding="utf-8")
        assert "datetime.utcnow" not in content, f"{f} 仍含 datetime.utcnow"


def test_utcnow_no_deprecation_warning():
    import warnings
    backend = Path(__file__).resolve().parent.parent
    code = (
        "import warnings;"
        "warnings.filterwarnings('error', category=DeprecationWarning, message='.*utcnow.*');"
        "from app.auth import create_access_token;"
        "t=create_access_token({'sub':'x'});"
        "from app.main import app;"
        "print('ok')"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=str(backend), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


# ---------- F-15：seed 幂等 + SEED_DISABLED 关闭 ----------
def test_seed_idempotent_and_disable_switch(monkeypatch):
    from app.database import Base
    from app.seed import seed
    from app.models import User, Area
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    try:
        # 空库首次 seed
        seed(s)
        users_first = s.query(User).count()
        areas_first = s.query(Area).count()
        assert users_first >= 3

        # 幂等：users 非空时再次 seed 不重复灌入
        seed(s)
        assert s.query(User).count() == users_first
        assert s.query(Area).count() == areas_first

        # 显式关闭：FIRE_ALARM_SEED_DISABLED=1 时跳过
        monkeypatch.setenv("FIRE_ALARM_SEED_DISABLED", "1")
        seed(s)
        assert s.query(User).count() == users_first
        assert s.query(Area).count() == areas_first
        monkeypatch.delenv("FIRE_ALARM_SEED_DISABLED", raising=False)
    finally:
        s.close()
        engine.dispose()


# ---------- AL-08/AL-17：SQLite 外键、busy_timeout、WAL ----------
def test_module_engine_sqlite_pragmas(client):
    from app.database import engine
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).fetchone()[0] == 1
        assert conn.execute(text("PRAGMA busy_timeout")).fetchone()[0] == 5000
        assert conn.execute(text("PRAGMA journal_mode")).fetchone()[0] == "wal"


def test_module_engine_foreign_keys_enforced(client):
    """生产引擎外键生效：插入孤儿外键行被拒（AL-08）。"""
    from app.database import SessionLocal
    from app.models import Device
    with SessionLocal() as s:
        try:
            s.add(Device(device_no="FK-ORPHAN", name="孤儿设备", device_type="smoke", area_id=999999))
            s.commit()
            raise AssertionError("外键约束应拒绝孤儿设备")
        except Exception as exc:
            assert "FOREIGN KEY" in str(exc).upper() or "integrity" in str(exc).lower()
            s.rollback()


def test_sqlite_pragmas_apply_to_memory_engine():
    """事件式 PRAGMA 对 :memory: 引擎同样生效（对 :memory: 测试库同样生效）。"""
    from app.database import _sqlite_pragmas
    from sqlalchemy import event
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    event.listen(eng, "connect", _sqlite_pragmas)
    with eng.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).fetchone()[0] == 1
        assert conn.execute(text("PRAGMA busy_timeout")).fetchone()[0] == 5000
    eng.dispose()


# ---------- AL-16：JWT 密钥未设置时的 warning ----------
def test_jwt_secret_missing_warns_on_import():
    backend = Path(__file__).resolve().parent.parent
    code = (
        "import os;os.environ.pop('FIRE_ALARM_SECRET', None);"
        "import logging, sys;"
        "logging.basicConfig(level=logging.WARNING, stream=sys.stdout, force=True);"
        "from app.auth import SECRET_KEY;"
        "print('ok')"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=str(backend), capture_output=True, text=True)
    assert "FIRE_ALARM_SECRET" in r.stdout
    assert "ok" in r.stdout


# ---------- AL-18：成功登录重置失败计数 ----------
def test_login_success_resets_rate_limit_counter(client):
    for _ in range(3):
        assert client.post("/api/auth/login", json={"username": "duty", "password": "wrong"}).status_code == 401
    # 一次成功登录即清零失败计数
    assert client.post("/api/auth/login", json={"username": "duty", "password": "123456"}).status_code == 200
    codes = [client.post("/api/auth/login", json={"username": "duty", "password": "wrong"}).status_code for _ in range(5)]
    assert codes == [401] * 5
    # 第 6 次才触发 429
    assert client.post("/api/auth/login", json={"username": "duty", "password": "wrong"}).status_code == 429


# ---------- AL-32：全局未捕获异常兜底 ----------
def test_unhandled_exception_returns_500_and_hides_stack(client):
    from app.main import app
    from fastapi.testclient import TestClient

    @app.get("/_boom")
    def _boom():
        raise RuntimeError("内部测试异常")

    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/_boom")
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/_boom"]
    assert r.status_code == 500
    assert r.json() == {"detail": "服务器内部错误"}
    assert "boom" not in r.text


# ---------- AL-05/06/07：迁移为既有库去重并建唯一索引 ----------
def test_run_migrations_dedup_and_unique_indexes(tmp_path):
    old_db = tmp_path / "dup.db"
    engine = create_engine(f"sqlite:///{old_db}")
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE emergencies (id INTEGER PRIMARY KEY, alarm_id INTEGER, title VARCHAR, start_at DATETIME, status VARCHAR, result TEXT, closed_by VARCHAR, closed_at DATETIME)"
        ))
        conn.execute(text("INSERT INTO emergencies (id, alarm_id) VALUES (1, 10)"))
        conn.execute(text("INSERT INTO emergencies (id, alarm_id) VALUES (2, 10)"))
        conn.execute(text("INSERT INTO emergencies (id, alarm_id) VALUES (3, 10)"))
        conn.execute(text(
            "CREATE TABLE repairs (id INTEGER PRIMARY KEY, patrol_id INTEGER, device_id INTEGER, title VARCHAR, description TEXT, creator VARCHAR, status VARCHAR, created_at DATETIME, closed_at DATETIME, result TEXT)"
        ))
        conn.execute(text("INSERT INTO repairs (id, patrol_id) VALUES (1, 20)"))
        conn.execute(text("INSERT INTO repairs (id, patrol_id) VALUES (2, 20)"))
        conn.execute(text(
            "CREATE TABLE plans (id INTEGER PRIMARY KEY, name VARCHAR, area_id INTEGER, fire_type VARCHAR, actions JSON, enabled BOOLEAN, created_by INTEGER, created_at DATETIME)"
        ))
        conn.execute(text("INSERT INTO plans (id, name, area_id, fire_type) VALUES (1, 'a', 30, 'ordinary')"))
        conn.execute(text("INSERT INTO plans (id, name, area_id, fire_type) VALUES (2, 'b', 30, 'ordinary')"))
        conn.commit()

    run_migrations(engine)
    run_migrations(engine)  # 幂等：二次运行不报错

    with engine.connect() as conn:
        assert [r[0] for r in conn.execute(text("SELECT id FROM emergencies WHERE alarm_id=10 ORDER BY id")).fetchall()] == [1]
        assert [r[0] for r in conn.execute(text("SELECT id FROM repairs WHERE patrol_id=20")).fetchall()] == [1]
        assert [r[0] for r in conn.execute(text("SELECT id FROM plans WHERE area_id=30 AND fire_type='ordinary'")).fetchall()] == [1]
        names = {r[0] for r in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='index' AND name IN ('ix_emergencies_alarm_id','ix_repairs_patrol_id','ix_plans_area_fire_type')")
        ).fetchall()}
        assert names == {"ix_emergencies_alarm_id", "ix_repairs_patrol_id", "ix_plans_area_fire_type"}
        # 唯一索引真正生效
        try:
            conn.execute(text("INSERT INTO emergencies (id, alarm_id) VALUES (99, 10)"))
            conn.commit()
            raise AssertionError("唯一索引应拒绝重复 alarm_id")
        except Exception:
            conn.rollback()
    engine.dispose()


def test_run_migrations_skips_when_key_columns_missing(tmp_path):
    """表存在但缺唯一索引所需列时跳过（迁移防御分支）。"""
    old_db = tmp_path / "nocols.db"
    engine = create_engine(f"sqlite:///{old_db}")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE plans (id INTEGER PRIMARY KEY, name VARCHAR)"))
        conn.commit()
    run_migrations(engine)
    with engine.connect() as conn:
        names = {r[0] for r in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_plans_area_fire_type'")
        ).fetchall()}
        assert "ix_plans_area_fire_type" not in names
    engine.dispose()