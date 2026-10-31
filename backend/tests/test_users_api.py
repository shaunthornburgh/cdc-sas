import uuid

import pytest
from sqlalchemy import select

from app.models import ActividadEvento
from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, FuncionIndependiente
from tests.conftest import TEST_PASSWORD, auth_header, login

USERS = "/api/v1/users"


@pytest.fixture
def coord(make_user):
    return make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Coordinadora")


@pytest.fixture
def gerente(make_user):
    return make_user(Cargo.GERENCIA, email="gerente@example.com")


@pytest.fixture
def as_coord(client, coord):
    return auth_header(login(client, coord.email)["access_token"])


@pytest.fixture
def as_gerente(client, gerente):
    return auth_header(login(client, gerente.email)["access_token"])


def new_user_body(**overrides):
    body = {
        "email": "nuevo@example.com",
        "password": "una-clave-segura",
        "full_name": "Nuevo Usuario",
        "cargo": "asesor",
    }
    return body | overrides


# ---------------------------------------------------------------- access


@pytest.mark.parametrize(
    "cargo", [Cargo.ASESOR, Cargo.AUXILIAR_ADMINISTRATIVA, Cargo.ATENCION_CLIENTE]
)
def test_other_cargos_are_forbidden(client, make_user, cargo):
    make_user(cargo, email="x@example.com")
    headers = auth_header(login(client, "x@example.com")["access_token"])
    assert client.get(USERS, headers=headers).status_code == 403
    assert client.post(USERS, json=new_user_body(), headers=headers).status_code == 403


def test_requires_login(client):
    assert client.get(USERS).status_code == 401


def test_coordinacion_and_gerencia_can_list(client, as_coord, as_gerente, make_user):
    make_user(email="asesor@example.com", actividades=[A.CAPTACION])
    for headers in (as_coord, as_gerente):
        res = client.get(USERS, headers=headers)
        assert res.status_code == 200
        emails = {u["email"] for u in res.json()}
        assert {"asesor@example.com", "coord@example.com", "gerente@example.com"} <= emails


def test_list_filters(client, as_coord, make_user):
    make_user(email="ana@example.com", full_name="Ana Pérez")
    make_user(Cargo.AUXILIAR_ADMINISTRATIVA, email="luis@example.com", is_active=False)

    by_q = client.get(USERS, params={"q": "pérez"}, headers=as_coord).json()
    assert [u["email"] for u in by_q] == ["ana@example.com"]
    by_cargo = client.get(USERS, params={"cargo": "auxiliar_administrativa"}, headers=as_coord)
    assert [u["email"] for u in by_cargo.json()] == ["luis@example.com"]
    inactive = client.get(USERS, params={"is_active": False}, headers=as_coord).json()
    assert [u["email"] for u in inactive] == ["luis@example.com"]


def test_get_user_and_404(client, as_coord, coord):
    assert client.get(f"{USERS}/{coord.id}", headers=as_coord).json()["email"] == coord.email
    assert client.get(f"{USERS}/{uuid.uuid4()}", headers=as_coord).status_code == 404


# ---------------------------------------------------------------- create


def test_create_user(client, as_coord, coord, db):
    body = new_user_body(email="Nuevo@Example.com", actividades=["captacion", "ventas"])
    res = client.post(USERS, json=body, headers=as_coord)

    assert res.status_code == 201, res.text
    user = res.json()
    assert user["email"] == "nuevo@example.com"
    assert user["actividades"] == ["captacion", "ventas"]
    assert user["gps_checkin_enabled"] is True
    assert "password" not in user and "hashed_password" not in user

    # The new user can log in, and the initial activities are logged against the creator.
    assert login(client, "nuevo@example.com", "una-clave-segura")["user"]["id"] == user["id"]
    events = db.scalars(select(ActividadEvento).where(ActividadEvento.user_id == user["id"]))
    assert {(e.actividad, e.activada, e.changed_by_id) for e in events} == {
        (A.CAPTACION, True, coord.id),
        (A.VENTAS, True, coord.id),
    }


def test_create_atencion_cliente_gets_funcion(client, as_coord):
    res = client.post(USERS, json=new_user_body(cargo="atencion_cliente"), headers=as_coord)
    assert res.status_code == 201
    assert res.json()["funcion"] == "atencion_cliente"


def test_create_preventas_any_cargo(client, as_coord):
    body = new_user_body(cargo="auxiliar_administrativa", funcion="pre_ventas")
    assert client.post(USERS, json=body, headers=as_coord).json()["funcion"] == "pre_ventas"


def test_create_rejects_funcion_with_activities(client, as_coord):
    body = new_user_body(funcion="pre_ventas", actividades=["ventas"])
    res = client.post(USERS, json=body, headers=as_coord)
    assert res.status_code == 422
    assert "no se pueden combinar" in res.json()["detail"]


def test_create_duplicate_email(client, as_coord, coord):
    res = client.post(USERS, json=new_user_body(email="COORD@example.com"), headers=as_coord)
    assert res.status_code == 409


@pytest.mark.parametrize(
    "override",
    [{"email": "not-an-email"}, {"password": "short"}, {"full_name": "   "}, {"cargo": "jefe"}],
)
def test_create_validation(client, as_coord, override):
    assert client.post(USERS, json=new_user_body(**override), headers=as_coord).status_code == 422


def test_only_gerencia_creates_gerencia(client, as_coord, as_gerente):
    body = new_user_body(cargo="gerencia")
    assert client.post(USERS, json=body, headers=as_coord).status_code == 403
    assert client.post(USERS, json=body, headers=as_gerente).status_code == 201


# ---------------------------------------------------------------- update


def test_update_basic_fields(client, as_coord, make_user):
    user = make_user(email="a@example.com")
    res = client.patch(
        f"{USERS}/{user.id}",
        json={"full_name": "Nombre Nuevo", "cargo": "auxiliar_administrativa"},
        headers=as_coord,
    )
    assert res.status_code == 200
    assert res.json()["full_name"] == "Nombre Nuevo"
    assert res.json()["cargo"] == "auxiliar_administrativa"


def test_deactivate_user_blocks_their_session(client, as_coord, make_user):
    user = make_user(email="a@example.com")
    their_token = login(client, "a@example.com")["access_token"]

    res = client.patch(f"{USERS}/{user.id}", json={"is_active": False}, headers=as_coord)
    assert res.json()["is_active"] is False
    assert client.get("/api/v1/auth/me", headers=auth_header(their_token)).status_code == 401
    bad_login = {"email": "a@example.com", "password": TEST_PASSWORD}
    assert client.post("/api/v1/auth/login", json=bad_login).status_code == 403


def test_cannot_deactivate_or_demote_self(client, as_coord, coord):
    url = f"{USERS}/{coord.id}"
    assert client.patch(url, json={"is_active": False}, headers=as_coord).status_code == 403
    assert client.patch(url, json={"cargo": "asesor"}, headers=as_coord).status_code == 403
    assert client.patch(url, json={"full_name": "Yo"}, headers=as_coord).status_code == 200


def test_coordinacion_cannot_touch_or_promote_to_gerencia(
    client, as_coord, as_gerente, gerente, make_user
):
    asesor = make_user(email="a@example.com")
    gerente_url = f"{USERS}/{gerente.id}"
    promote = {"cargo": "gerencia"}
    assert client.patch(gerente_url, json={"full_name": "X"}, headers=as_coord).status_code == 403
    res = client.patch(f"{USERS}/{asesor.id}", json=promote, headers=as_coord)
    assert res.status_code == 403
    res = client.patch(f"{USERS}/{asesor.id}", json=promote, headers=as_gerente)
    assert res.status_code == 200


def test_update_rejects_null_for_required_fields(client, as_coord, make_user):
    user = make_user(email="a@example.com")
    res = client.patch(f"{USERS}/{user.id}", json={"cargo": None}, headers=as_coord)
    assert res.status_code == 422


def test_update_to_atencion_cliente(client, as_coord, make_user):
    with_acts = make_user(email="a@example.com", actividades=[A.VENTAS])
    without = make_user(email="b@example.com")
    body = {"cargo": "atencion_cliente"}

    assert client.patch(f"{USERS}/{with_acts.id}", json=body, headers=as_coord).status_code == 422
    res = client.patch(f"{USERS}/{without.id}", json=body, headers=as_coord)
    assert res.status_code == 200
    assert res.json()["funcion"] == "atencion_cliente"


# ---------------------------------------------------------------- activities


def test_toggle_activities_updates_gps_and_history(client, as_coord, coord, make_user):
    user = make_user(email="a@example.com", actividades=[A.VENTAS])
    url = f"{USERS}/{user.id}/activities"

    res = client.post(url, json={"actividades": ["ventas", "captacion"]}, headers=as_coord)
    assert res.status_code == 200
    assert res.json()["actividades"] == ["captacion", "ventas"]
    assert res.json()["gps_checkin_enabled"] is True
    assert {
        link.granted_by_id for link in user.actividad_links if link.actividad == A.CAPTACION
    } == {coord.id}

    res = client.post(url, json={"actividades": ["ventas"]}, headers=as_coord)
    assert res.json()["actividades"] == ["ventas"]
    assert res.json()["gps_checkin_enabled"] is False

    history = client.get(f"{url}/history", headers=as_coord).json()
    assert [(h["actividad"], h["activada"]) for h in history] == [
        ("captacion", False),
        ("captacion", True),
        ("ventas", True),  # initial activity, created without an actor (fixture)
    ]
    assert [h["changed_by_name"] for h in history] == ["Coordinadora", "Coordinadora", None]


def test_setting_same_activities_logs_nothing(client, as_coord, make_user, db):
    user = make_user(email="a@example.com")
    url = f"{USERS}/{user.id}/activities"
    client.post(url, json={"actividades": ["ventas"]}, headers=as_coord)
    client.post(url, json={"actividades": ["ventas", "ventas"]}, headers=as_coord)
    assert len(client.get(f"{url}/history", headers=as_coord).json()) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"cargo": Cargo.ASESOR, "funcion": FuncionIndependiente.PRE_VENTAS},
        {"cargo": Cargo.ATENCION_CLIENTE},
    ],
)
def test_activities_rejected_for_independent_functions(client, as_coord, make_user, kwargs):
    user = make_user(email="a@example.com", **kwargs)
    res = client.post(
        f"{USERS}/{user.id}/activities", json={"actividades": ["ventas"]}, headers=as_coord
    )
    assert res.status_code == 422


def test_activities_rejects_unknown_activity(client, as_coord, make_user):
    user = make_user(email="a@example.com")
    res = client.post(
        f"{USERS}/{user.id}/activities", json={"actividades": ["pre_ventas"]}, headers=as_coord
    )
    assert res.status_code == 422


# ---------------------------------------------------------------- funcion


def test_set_and_clear_funcion(client, as_coord, make_user):
    user = make_user(email="a@example.com")
    url = f"{USERS}/{user.id}/funcion"

    assert client.post(url, json={"funcion": "pre_ventas"}, headers=as_coord).json()["funcion"] == (
        "pre_ventas"
    )
    assert client.post(url, json={"funcion": None}, headers=as_coord).json()["funcion"] is None


def test_funcion_rejected_when_user_has_activities(client, as_coord, make_user):
    user = make_user(email="a@example.com", actividades=[A.CAPTACION])
    res = client.post(
        f"{USERS}/{user.id}/funcion", json={"funcion": "pre_ventas"}, headers=as_coord
    )
    assert res.status_code == 422
    # Same rule via PATCH.
    res = client.patch(f"{USERS}/{user.id}", json={"funcion": "pre_ventas"}, headers=as_coord)
    assert res.status_code == 422


def test_cannot_clear_funcion_of_atencion_cliente(client, as_coord, make_user):
    user = make_user(Cargo.ATENCION_CLIENTE, email="a@example.com")
    res = client.post(f"{USERS}/{user.id}/funcion", json={"funcion": None}, headers=as_coord)
    assert res.status_code == 422
