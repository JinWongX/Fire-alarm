"""pytest 基建：隔离数据库 + FastAPI TestClient + 三角色认证 helper。

隔离策略：
  - 每个测试使用独立的内存 SQLite（StaticPool），并 seed 一份全新数据；
  - 通过 app.dependency_overrides[get_db] 注入该测试会话，绝不触碰 backend/fire_alarm.db；
  - 在导入 app 前将 FIRE_ALARM_DB 指向临时文件，确保 lifespan 建表/seed 也不写真实库。
"""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_TMPDIR = tempfile.mkdtemp(prefix="pytest_fire_")
os.environ["FIRE_ALARM_DB"] = os.path.join(_TMPDIR, "fire_alarm_test.db")

from app.auth import create_access_token, hash_password, verify_password  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402
import app.models as models  # noqa: E402,F401  确保所有模型注册到 Base.metadata

# 角色名 -> 种子用户名（seed.py：admin=supervisor，duty=duty，maintain=maintenance）
ROLE_USERNAME = {
    "supervisor": "admin",
    "duty": "duty",
    "maintenance": "maintain",
}

# 种子用户（角色 -> 密码），供登录复用
SEED_LOGIN = {
    "admin": ("admin", "123456"),
    "duty": ("duty", "123456"),
    "maintain": ("maintain", "123456"),
}


def make_token(role: str) -> str:
    """按角色签发 JWT（sub 使用种子用户名）。"""
    username = ROLE_USERNAME[role]
    return create_access_token({"sub": username, "role": role})


@pytest.fixture()
def db_session():
    """为每个测试构造专属内存 SQLite：建表 + seed，并覆盖 get_db。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    seed(test_session)

    def _override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = _override_get_db
    yield test_session
    app.dependency_overrides.pop(get_db, None)
    test_session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def client(db_session):
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    """每个用例结束清空内存登录限流计数，避免跨用例累计导致误 429。"""
    from app.routers import auth as auth_router

    yield
    auth_router._login_attempts.clear()


@pytest.fixture()
def auth():
    """返回 角色名 -> 鉴权 header 的函数。角色: supervisor/duty/maintenance。"""
    def _auth(role: str):
        return {"Authorization": f"Bearer {make_token(role)}"}
    return _auth


@pytest.fixture()
def headers(auth):
    """返回 三角色 header 字典。"""
    return {role: auth(role) for role in ("supervisor", "duty", "maintenance")}


@pytest.fixture()
def area0(db_session):
    """第一个区域（A区一层，种子含 ordinary 联动预案），返回 dict。"""
    area = db_session.query(models.Area).order_by(models.Area.id).first()
    return {"id": area.id, "name": area.name}


@pytest.fixture()
def device_in_area0(db_session):
    """区域0内的第一台设备（命中种子联动预案），返回 dict。"""
    area = db_session.query(models.Area).order_by(models.Area.id).first()
    dev = (
        db_session.query(models.Device)
        .filter(models.Device.area_id == area.id)
        .order_by(models.Device.id)
        .first()
    )
    return {"id": dev.id, "area_id": dev.area_id}


@pytest.fixture()
def new_device(client, headers):
    """便捷夹具：创建一个无报警关联的新设备，返回其 dict。"""
    def _make(device_no="T-DEV-001"):
        area = client.get("/api/areas", headers=headers["duty"]).json()[0]
        r = client.post(
            "/api/devices",
            json={
                "device_no": device_no,
                "name": "测试设备",
                "device_type": "smoke",
                "area_id": area["id"],
            },
            headers=headers["supervisor"],
        )
        r.raise_for_status()
        return r.json()
    return _make