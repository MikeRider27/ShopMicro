def register(client, email="user@example.com", password="secret123", name="Test User"):
    return client.post(
        "/register",
        json={"email": email, "password": password, "name": name},
    )


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_register_success(client):
    resp = register(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["user"]["email"] == "user@example.com"
    assert "access_token" in data


def test_register_missing_fields(client):
    resp = client.post("/register", json={"email": "user@example.com"})
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = register(client, password="123")
    assert resp.status_code == 400


def test_register_duplicate_email(client):
    register(client)
    resp = register(client)
    assert resp.status_code == 409


def test_register_invalid_email_format(client):
    resp = register(client, email="no-es-un-email")
    assert resp.status_code == 400


def test_register_whitespace_only_name(client):
    resp = register(client, name="   ")
    assert resp.status_code == 400


def test_register_rejects_unknown_fields(client):
    resp = client.post(
        "/register",
        json={
            "email": "user@example.com",
            "password": "secret123",
            "name": "Test User",
            "is_admin": True,
        },
    )
    assert resp.status_code == 400
    assert "is_admin" in resp.get_json()["details"]


def test_login_success(client):
    register(client)
    resp = client.post(
        "/login", json={"email": "user@example.com", "password": "secret123"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.get_json()


def test_login_invalid_password(client):
    register(client)
    resp = client.post(
        "/login", json={"email": "user@example.com", "password": "wrong-password"}
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/login", json={"email": "nobody@example.com", "password": "secret123"}
    )
    assert resp.status_code == 401


def test_me_with_valid_token(client):
    token = register(client).get_json()["access_token"]
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["user"]["email"] == "user@example.com"


def test_me_without_token(client):
    resp = client.get("/me")
    assert resp.status_code == 401


def test_me_with_invalid_token(client):
    resp = client.get("/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 422 or resp.status_code == 401
