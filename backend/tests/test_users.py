"""用户管理单测：仅 supervisor CRUD、角色校验、is_active 停用后登录/访问被拒。"""
def test_list_users_only_supervisor(client, headers):
    for role in ("duty", "maintenance"):
        assert client.get("/api/users", headers=headers[role]).status_code == 403, role
    r = client.get("/api/users", headers=headers["supervisor"])
    assert r.status_code == 200
    assert len(r.json()) >= 3
    assert all({"id", "username", "role", "is_active"} <= set(u) for u in r.json())


def test_create_user_supervisor_only(client, headers):
    for role in ("duty", "maintenance"):
        assert client.post(
            "/api/users", json={"username": "x1", "password": "123456", "role": "duty"}, headers=headers[role]
        ).status_code == 403, role
    r = client.post(
        "/api/users",
        json={"username": "newbie", "password": "s3cret", "real_name": "新员工", "role": "duty"},
        headers=headers["supervisor"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "newbie"
    assert body["role"] == "duty"
    assert body["is_active"] is True


def test_create_user_duplicate_400(client, headers):
    r = client.post("/api/users", json={"username": "duty", "password": "x"}, headers=headers["supervisor"])
    assert r.status_code == 400
    assert "已存在" in r.json()["detail"]


def test_create_user_invalid_role_400(client, headers):
    r = client.post("/api/users", json={"username": "badrole", "password": "x", "role": "boss"}, headers=headers["supervisor"])
    assert r.status_code == 400


def test_update_user_profile_and_password(client, headers):
    created = client.post(
        "/api/users", json={"username": "upduser", "password": "oldpwd", "real_name": "旧名"}, headers=headers["supervisor"]
    ).json()
    uid = created["id"]
    r = client.put(
        f"/api/users/{uid}",
        json={"real_name": "新名", "role": "supervisor", "password": "newpwd"},
        headers=headers["supervisor"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["real_name"] == "新名"
    assert body["role"] == "supervisor"
    # 新密码可登录
    login = client.post("/api/auth/login", json={"username": "upduser", "password": "newpwd"})
    assert login.status_code == 200


def test_deactivate_user_blocks_login_and_access(client, headers):
    created = client.post(
        "/api/users", json={"username": "suspend", "password": "123456", "role": "duty"}, headers=headers["supervisor"]
    ).json()
    uid = created["id"]
    # 停用前可登录
    assert client.post("/api/auth/login", json={"username": "suspend", "password": "123456"}).status_code == 200

    r = client.put(f"/api/users/{uid}", json={"is_active": False}, headers=headers["supervisor"])
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    # 停用后登录 401
    assert client.post("/api/auth/login", json={"username": "suspend", "password": "123456"}).status_code == 401
    # 已签发 token 访问也 401
    from app.auth import create_access_token
    token = create_access_token({"sub": "suspend", "role": "duty"})
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.get("/api/areas", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_update_nonexistent_user_404(client, headers):
    assert client.put("/api/users/999999", json={"real_name": "x"}, headers=headers["supervisor"]).status_code == 404


def test_update_user_invalid_role_400(client, headers):
    created = client.post(
        "/api/users", json={"username": "rolefix", "password": "x", "role": "duty"}, headers=headers["supervisor"]
    ).json()
    r = client.put(f"/api/users/{created['id']}", json={"role": "boss"}, headers=headers["supervisor"])
    assert r.status_code == 400


def test_users_requires_auth(client):
    assert client.get("/api/users").status_code == 401


# ---------- reset_password：主管专属、密码 min6、返回 UserOut ----------
def test_reset_password_flow(client, headers):
    created = client.post(
        "/api/users", json={"username": "resetme", "password": "123456", "role": "duty"}, headers=headers["supervisor"]
    ).json()
    uid = created["id"]
    r = client.post(f"/api/users/{uid}/reset_password", json={"password": "newpass6"}, headers=headers["supervisor"])
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "resetme"
    assert body["role"] == "duty"
    # 新密码可登录，旧密码失效
    assert client.post("/api/auth/login", json={"username": "resetme", "password": "newpass6"}).status_code == 200
    assert client.post("/api/auth/login", json={"username": "resetme", "password": "123456"}).status_code == 401


def test_reset_password_only_supervisor(client, headers):
    uid = client.post(
        "/api/users", json={"username": "reset403", "password": "123456", "role": "duty"}, headers=headers["supervisor"]
    ).json()["id"]
    for role in ("duty", "maintenance"):
        r = client.post(f"/api/users/{uid}/reset_password", json={"password": "abcdef"}, headers=headers[role])
        assert r.status_code == 403, role


def test_reset_password_min_length_422(client, headers):
    uid = client.post(
        "/api/users", json={"username": "shortpwd", "password": "123456", "role": "duty"}, headers=headers["supervisor"]
    ).json()["id"]
    r = client.post(f"/api/users/{uid}/reset_password", json={"password": "12345"}, headers=headers["supervisor"])
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][-1] == "password"


def test_reset_password_nonexistent_404(client, headers):
    r = client.post("/api/users/999999/reset_password", json={"password": "abcdef"}, headers=headers["supervisor"])
    assert r.status_code == 404