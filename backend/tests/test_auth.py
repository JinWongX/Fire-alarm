"""认证模块单测：登录/登出校验、/me、token 校验、三角色 RBAC、密码哈希。"""
import os

import pytest
from jose import jwt as jose_jwt

from app.auth import create_access_token, hash_password, verify_password, SECRET_KEY


def test_login_success_duty(client):
    r = client.post("/api/auth/login", json={"username": "duty", "password": "123456"})
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["user"]["username"] == "duty"
    assert body["user"]["role"] == "duty"


def test_login_all_three_roles(client):
    for username, role in (("admin", "supervisor"), ("duty", "duty"), ("maintain", "maintenance")):
        r = client.post("/api/auth/login", json={"username": username, "password": "123456"})
        assert r.status_code == 200
        assert r.json()["user"]["role"] == role


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "duty", "password": "bad"})
    assert r.status_code == 401
    assert "token" not in r.json()


def test_login_user_not_found(client):
    r = client.post("/api/auth/login", json={"username": "ghost", "password": "123456"})
    assert r.status_code == 401


def test_login_missing_field_rejected(client):
    r = client.post("/api/auth/login", json={"username": "duty"})
    assert r.status_code == 422


def test_me_with_token(client, auth):
    r = client.get("/api/auth/me", headers=auth("duty"))
    assert r.status_code == 200
    assert r.json()["username"] == "duty"


def test_me_without_token_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_fake_token_401(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage.token.value"})
    assert r.status_code == 401


def test_me_expired_token_401(client):
    import calendar
    from datetime import datetime, timedelta
    exp = calendar.timegm((datetime.utcnow() - timedelta(hours=1)).timetuple())
    token = jose_jwt.encode({"sub": "duty", "role": "duty", "exp": exp}, SECRET_KEY, algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_role_dependency_allow_supervisor_and_duty(client, headers):
    # 建预案（仅 supervisor 放行）；值班员被拒
    areas = client.get("/api/areas", headers=headers["duty"]).json()
    area = areas[1]  # 该区域无普通火灾种子预案，避免唯一性 409
    actions = [{"action_type": "fire_door", "action_name": "关闭防火门"}]
    r_sup = client.post("/api/plans", json={"name": "P", "area_id": area["id"], "actions": actions}, headers=headers["supervisor"])
    assert r_sup.status_code == 201
    r_duty = client.post("/api/plans", json={"name": "P2", "area_id": area["id"], "actions": actions}, headers=headers["duty"])
    assert r_duty.status_code == 403
    # maintenance 越权建预案 403
    r_maint = client.post("/api/plans", json={"name": "P3", "area_id": area["id"], "actions": actions}, headers=headers["maintenance"])
    assert r_maint.status_code == 403


def test_role_dependency_permission_denied_403(client, headers):
    # 值班员/主管可确认；维保越权确认 403
    dev = client.get("/api/devices", params={"page_size": 1}, headers=headers["duty"]).json()["items"][0]
    sim = client.post(
        "/api/alarms/simulate",
        json={"device_id": dev["id"], "fire_type": "ordinary"},
        headers=headers["duty"],
    ).json()["alarm"]
    r = client.post(f"/api/alarms/{sim['id']}/confirm", json={"result": "true"}, headers=headers["maintenance"])
    assert r.status_code == 403
    # duty 放行
    r2 = client.post(f"/api/alarms/{sim['id']}/confirm", json={"result": "true"}, headers=headers["duty"])
    assert r2.status_code == 200


def test_hash_and_verify_password():
    hashed = hash_password("s3cret")
    assert hashed != "s3cret"
    assert verify_password("s3cret", hashed)
    assert not verify_password("wrong", hashed)


def test_create_access_token_roundtrip():
    token = create_access_token({"sub": "duty", "role": "duty"})
    payload = jose_jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    assert payload["sub"] == "duty"
    assert "exp" in payload


def test_token_without_sub_401(client):
    """签名有效但缺少 sub 声明的 token 应被拒绝。"""
    token = jose_jwt.encode({"role": "duty"}, SECRET_KEY, algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_for_unknown_user_401(client):
    """签名有效但用户名不存在的 token 应被拒绝。"""
    token = create_access_token({"sub": "ghost_user", "role": "duty"})
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_require_roles_direct():
    """require_roles 装饰器：未登录 401 / 角色不符 403 / 放行。"""
    from app.auth import require_roles
    from types import SimpleNamespace
    from fastapi import HTTPException

    calls = []

    @require_roles("supervisor")
    def fake(**kwargs):
        calls.append(1)
        return "ok"

    user_duty = SimpleNamespace(role="duty")
    user_sup = SimpleNamespace(role="supervisor")

    try:
        fake(current_user=None)
    except HTTPException as e:
        assert e.status_code == 401
    try:
        fake(current_user=user_duty)
    except HTTPException as e:
        assert e.status_code == 403
    assert fake(current_user=user_sup) == "ok"
    assert len(calls) == 1