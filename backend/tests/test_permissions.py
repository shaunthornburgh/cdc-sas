from typing import Annotated

import pytest
from fastapi import Depends, FastAPI

from app.api.permissions import require_actividad, require_cargo, require_funcion
from app.api.router import api_router
from app.models import User
from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, FuncionIndependiente
from tests.conftest import auth_header, login

# A throwaway app with guarded routes, so the real API stays untouched.
guarded = FastAPI()
guarded.include_router(api_router, prefix="/api/v1")


@guarded.get(
    "/direccion", dependencies=[Depends(require_cargo(Cargo.GERENCIA, Cargo.COORDINACION))]
)
def direccion() -> dict:
    return {"ok": True}


@guarded.get("/checkin")
def checkin(user: Annotated[User, Depends(require_actividad(A.CAPTACION))]) -> dict:
    return {"email": user.email}


@guarded.get("/ventas-y-arriendos")
def ventas_y_arriendos(
    _: Annotated[User, Depends(require_actividad(A.VENTAS, A.ARRIENDOS, require_all=True))],
) -> dict:
    return {"ok": True}


@guarded.get("/preventas", dependencies=[Depends(require_funcion(FuncionIndependiente.PRE_VENTAS))])
def preventas() -> dict:
    return {"ok": True}


@pytest.fixture
def gclient(make_client):
    return make_client(guarded)


def _get(client, path, email):
    token = login(client, email)["access_token"]
    return client.get(path, headers=auth_header(token)).status_code


@pytest.mark.parametrize(
    ("cargo", "expected"),
    [
        (Cargo.GERENCIA, 200),
        (Cargo.COORDINACION, 200),
        (Cargo.ASESOR, 403),
        (Cargo.AUXILIAR_ADMINISTRATIVA, 403),
        (Cargo.ATENCION_CLIENTE, 403),
    ],
)
def test_require_cargo(gclient, make_user, cargo, expected):
    make_user(cargo, email="u@example.com")
    assert _get(gclient, "/direccion", "u@example.com") == expected


def test_require_cargo_needs_login(gclient):
    assert gclient.get("/direccion").status_code == 401


def test_require_actividad(gclient, make_user):
    make_user(email="capta@example.com", actividades=[A.CAPTACION])
    make_user(email="vende@example.com", actividades=[A.VENTAS])
    make_user(Cargo.GERENCIA, email="boss@example.com")

    assert _get(gclient, "/checkin", "capta@example.com") == 200
    assert _get(gclient, "/checkin", "vende@example.com") == 403
    # No implicit superuser: Gerencia without Captación can't check in.
    assert _get(gclient, "/checkin", "boss@example.com") == 403


def test_require_actividad_all(gclient, make_user):
    make_user(email="both@example.com", actividades=[A.VENTAS, A.ARRIENDOS])
    make_user(email="one@example.com", actividades=[A.VENTAS])
    assert _get(gclient, "/ventas-y-arriendos", "both@example.com") == 200
    assert _get(gclient, "/ventas-y-arriendos", "one@example.com") == 403


def test_require_funcion(gclient, make_user):
    make_user(email="pre@example.com", funcion=FuncionIndependiente.PRE_VENTAS)
    make_user(email="asesor@example.com", actividades=[A.VENTAS])
    assert _get(gclient, "/preventas", "pre@example.com") == 200
    assert _get(gclient, "/preventas", "asesor@example.com") == 403
