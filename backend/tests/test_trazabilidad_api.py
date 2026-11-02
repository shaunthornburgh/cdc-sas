"""Registro de cambios (G06 / G06-coord): one list over the histories the modules already keep."""

from datetime import timedelta

import pytest

from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, FuenteLead, FuncionIndependiente
from app.services import fechas
from app.services import leads as lead_service
from tests.conftest import auth_header, login

RC = "/api/v1/registro-cambios"


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Vale Aux"
        ),
        "juan": make_user(
            email="juan@example.com", full_name="Juan Asesor", actividades=[A.VENTAS]
        ),
        "laura": make_user(
            Cargo.ATENCION_CLIENTE,
            email="laura@example.com",
            full_name="Laura Atención",
            funcion=FuncionIndependiente.ATENCION_CLIENTE,
        ),
    }


@pytest.fixture
def H(client):
    cache: dict = {}

    def _h(user):
        if user.email not in cache:
            cache[user.email] = auth_header(login(client, user.email)["access_token"])
        return cache[user.email]

    return _h


def ok(res, code=200):
    assert res.status_code == code, res.text
    return res.json()


@pytest.fixture
def cambios(client, p, H, db):
    """A few real actions in different modules, done through the API / services."""
    ok(
        client.patch(
            f"/api/v1/users/{p['juan'].id}",
            json={"telefono": "300 000 0021"},
            headers=H(p["coord"]),
        )
    )
    ok(
        client.post(
            f"/api/v1/users/{p['juan'].id}/activities",
            json={"actividades": ["ventas", "captacion"]},
            headers=H(p["coord"]),
        )
    )
    ok(client.put("/api/v1/configuracion/tarifas", json={"iva_pct": 18}, headers=H(p["ger"])))
    lead = lead_service.create_lead(
        db,
        {
            "full_name": "Cliente Ejemplo 24",
            "phone": "3005550124",
            "fuente": FuenteLead.PROPPI,
            "negocio": "arriendo",
        },
        actor=p["laura"],
    )
    db.flush()
    return lead


def test_access(client, p, H):
    for k in ("ger", "coord"):
        assert client.get(RC, headers=H(p[k])).status_code == 200
    for k in ("aux", "juan", "laura"):
        assert client.get(RC, headers=H(p[k])).status_code == 403
    o = ok(client.get(f"{RC}/opciones", headers=H(p["ger"])))
    assert "Comisiones" in o["modulos"] and o["alcance"] is None
    oc = ok(client.get(f"{RC}/opciones", headers=H(p["coord"])))
    assert "Comisiones" not in oc["modulos"] and "Configuración" not in oc["modulos"]
    assert "solo los ve Gerencia" in oc["alcance"]


def test_unified_list(client, p, H, cambios):
    d = ok(client.get(RC, headers=H(p["ger"])))
    por_modulo = {}
    for x in d["items"]:
        por_modulo.setdefault(x["modulo"], []).append(x)
    tel = [x for x in por_modulo["Usuarios"] if x["accion"] == "Cambió teléfono"][0]
    assert (tel["actor"], tel["registro"], tel["antes"], tel["despues"]) == (
        "Mateo Coord",
        "Juan Asesor",
        None,
        "300 000 0021",
    )
    act = [x for x in por_modulo["Usuarios"] if "Captación" in x["accion"]][0]
    assert (act["accion"], act["antes"], act["despues"]) == (
        "Activó la actividad Captación",
        "Inactiva",
        "Activa",
    )
    cfg = por_modulo["Configuración"][0]
    assert (cfg["accion"], cfg["antes"], cfg["despues"]) == (
        "Cambió tarifas de intermediación",
        "iva pct: 19.0",
        "iva pct: 18.0",
    )
    lead = por_modulo["Leads"][0]
    assert (lead["actor"], lead["registro"], lead["link"]) == (
        "Laura Atención",
        cambios.code,
        f"/leads/{cambios.id}",
    )
    # Newest first
    ats = [x["at"] for x in d["items"]]
    assert ats == sorted(ats, reverse=True)


def test_coordinacion_scope(client, p, H, cambios):
    d = ok(client.get(RC, headers=H(p["coord"])))
    assert "Configuración" not in {x["modulo"] for x in d["items"]}
    assert {"Usuarios", "Leads"} <= {x["modulo"] for x in d["items"]}
    assert (
        client.get(RC, params={"modulo": "Configuración"}, headers=H(p["coord"])).status_code == 403
    )


def test_filters_and_pages(client, p, H, cambios):
    g = H(p["ger"])
    assert {
        x["modulo"] for x in ok(client.get(RC, params={"modulo": "Usuarios"}, headers=g))["items"]
    } == {"Usuarios"}
    por_mateo = ok(client.get(RC, params={"usuario_id": str(p["coord"].id)}, headers=g))["items"]
    assert por_mateo and {x["actor"] for x in por_mateo} == {"Mateo Coord"}
    busca = ok(client.get(RC, params={"q": cambios.code.lower()}, headers=g))["items"]
    assert busca and all(x["registro"] == cambios.code for x in busca)
    manana = fechas.local_date(fechas.now()) + timedelta(days=1)
    vacio = ok(
        client.get(RC, params={"desde": manana.isoformat(), "hasta": manana.isoformat()}, headers=g)
    )
    assert (vacio["total"], vacio["items"]) == (0, [])
    bad = {"desde": manana.isoformat(), "hasta": (manana - timedelta(days=3)).isoformat()}
    assert client.get(RC, params=bad, headers=g).status_code == 422
    assert client.get(RC, params={"modulo": "Nada"}, headers=g).status_code == 422
    todo = ok(client.get(RC, headers=g))
    p1 = ok(client.get(RC, params={"limit": 2}, headers=g))
    p2 = ok(client.get(RC, params={"limit": 2, "offset": 2}, headers=g))
    assert p1["total"] == todo["total"] >= 4
    assert [x["id"] for x in p1["items"] + p2["items"]] == [x["id"] for x in todo["items"][:4]]


def test_download_is_logged(client, p, H, cambios):
    g = H(p["ger"])
    res = client.get(f"{RC}/export.csv", params={"modulo": "Usuarios"}, headers=g)
    assert res.status_code == 200 and "attachment" in res.headers["content-disposition"]
    lines = res.text.lstrip("﻿").strip().splitlines()
    assert lines[0] == "Fecha,Hora,Usuario,Módulo,Acción,Registro,Antes,Después" and len(lines) >= 3
    desc = ok(client.get(RC, params={"modulo": "Configuración"}, headers=g))["items"][0]
    assert (desc["accion"], desc["actor"]) == ("Descargó el registro de cambios", "Gina Gerencia")
    assert "modulo: Usuarios" in desc["despues"]
    assert client.get(f"{RC}/export.csv", headers=H(p["aux"])).status_code == 403
