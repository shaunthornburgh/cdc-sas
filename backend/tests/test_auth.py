from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo
from tests.conftest import TEST_PASSWORD, auth_header, login

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"


def test_login_returns_tokens_and_user(client, make_user):
    make_user(Cargo.ASESOR, email="asesor@example.com", actividades=[A.VENTAS, A.CAPTACION])

    body = login(client, "asesor@example.com")

    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["expires_in"] == 15 * 60
    assert body["user"]["email"] == "asesor@example.com"
    assert body["user"]["cargo"] == "asesor"
    assert body["user"]["actividades"] == ["captacion", "ventas"]
    assert body["user"]["gps_checkin_enabled"] is True
    assert "hashed_password" not in body["user"]


def test_login_is_case_insensitive_on_email(client, make_user):
    make_user(email="Mixed.Case@Example.com")
    assert login(client, "  MIXED.case@example.COM ")["user"]["email"] == "mixed.case@example.com"


def test_login_wrong_password(client, make_user):
    make_user(email="a@example.com")
    res = client.post(LOGIN, json={"email": "a@example.com", "password": "nope"})
    assert res.status_code == 401


def test_login_unknown_email(client):
    res = client.post(LOGIN, json={"email": "ghost@example.com", "password": TEST_PASSWORD})
    assert res.status_code == 401


def test_login_inactive_user(client, make_user):
    make_user(email="off@example.com", is_active=False)
    res = client.post(LOGIN, json={"email": "off@example.com", "password": TEST_PASSWORD})
    assert res.status_code == 403


def test_me(client, make_user):
    make_user(Cargo.GERENCIA, email="boss@example.com", full_name="La Jefa")
    token = login(client, "boss@example.com")["access_token"]

    res = client.get(ME, headers=auth_header(token))

    assert res.status_code == 200
    me = res.json()
    assert me["full_name"] == "La Jefa"
    assert me["cargo"] == "gerencia"
    assert me["actividades"] == []
    assert me["funcion"] is None
    assert me["gps_checkin_enabled"] is False


def test_me_requires_token(client):
    res = client.get(ME)
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


def test_me_rejects_garbage_and_refresh_tokens(client, make_user):
    make_user(email="a@example.com")
    tokens = login(client, "a@example.com")
    assert client.get(ME, headers=auth_header("not-a-jwt")).status_code == 401
    assert client.get(ME, headers=auth_header(tokens["refresh_token"])).status_code == 401


def test_me_rejects_user_deactivated_after_login(client, make_user, db):
    user = make_user(email="a@example.com")
    token = login(client, "a@example.com")["access_token"]
    user.is_active = False
    db.flush()
    assert client.get(ME, headers=auth_header(token)).status_code == 401


def test_refresh_rotates_tokens(client, make_user):
    make_user(email="a@example.com")
    old = login(client, "a@example.com")

    res = client.post(REFRESH, json={"refresh_token": old["refresh_token"]})
    assert res.status_code == 200
    new = res.json()
    assert new["refresh_token"] != old["refresh_token"]
    assert client.get(ME, headers=auth_header(new["access_token"])).status_code == 200

    # The old refresh token can't be used twice.
    again = client.post(REFRESH, json={"refresh_token": old["refresh_token"]})
    assert again.status_code == 401


def test_refresh_rejects_access_token(client, make_user):
    make_user(email="a@example.com")
    access = login(client, "a@example.com")["access_token"]
    assert client.post(REFRESH, json={"refresh_token": access}).status_code == 401


def test_logout_revokes_both_tokens(client, make_user):
    make_user(email="a@example.com")
    tokens = login(client, "a@example.com")

    res = client.post(
        LOGOUT,
        json={"refresh_token": tokens["refresh_token"]},
        headers=auth_header(tokens["access_token"]),
    )
    assert res.status_code == 204
    assert client.get(ME, headers=auth_header(tokens["access_token"])).status_code == 401
    assert client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_logout_with_nothing_is_harmless(client):
    assert client.post(LOGOUT, json={}).status_code == 204
