"""Integraciones (G07): catalog, real results, honest connection states, secrets never stored."""

from datetime import date, datetime, timedelta

import pytest

from app.models import Lead, LeadEvento, Plataforma, PlataformaPlan
from app.models.enums import Cargo, EtapaLead, FuenteLead, TipoEventoLead, TipoNegocio
from app.services import fechas
from tests.conftest import auth_header, login

IN = "/api/v1/integraciones"
NOW = datetime(2026, 10, 3, 11, 0, tzinfo=fechas.BOGOTA)
Q = {"desde": "2026-09-04", "hasta": "2026-10-03"}  # 30 days, up to «today»


@pytest.fixture(autouse=True)
def reloj(monkeypatch):
    monkeypatch.setattr(fechas, "now", lambda: NOW)


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo"),
        "aux": make_user(Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com"),
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


def items(t):
    return {x["clave"]: x for g in t["grupos"] for x in g["items"]}


def _lead(db, fuente, when, etapa=EtapaLead.NUEVO, negocio=TipoNegocio.ARRIENDO):
    ld = Lead(full_name="Cliente", phone="3000000000", fuente=fuente, etapa=etapa, negocio=negocio)
    if etapa == EtapaLead.GANADO:
        ld.cerrado_at = when
    db.add(ld)
    db.flush()
    ld.created_at = when
    db.flush()
    return ld


def test_access_and_catalog(client, p, H):
    for k in ("coord", "aux"):
        assert client.get(IN, headers=H(p[k])).status_code == 403
    t = ok(client.get(IN, params=Q, headers=H(p["ger"])))
    assert [g["titulo"] for g in t["grupos"]] == [
        "Plataformas tradicionales",
        "Redes sociales",
        "Canales y servicios",
    ]
    assert len(items(t)) == 13
    assert {x["estado_txt"] for x in items(t).values()} == {
        "Sin conectar"
    }  # nothing is connected for real


def test_results_are_real(client, p, H, db):
    sep = datetime(2026, 9, 20, 10, 0, tzinfo=fechas.BOGOTA)
    _lead(db, FuenteLead.FACEBOOK, sep)
    _lead(db, FuenteLead.FACEBOOK, sep, EtapaLead.GANADO, TipoNegocio.ARRIENDO)
    _lead(db, FuenteLead.FACEBOOK, sep, EtapaLead.GANADO, TipoNegocio.VENTA)
    _lead(db, FuenteLead.FACEBOOK, datetime(2026, 8, 1, tzinfo=fechas.BOGOTA))  # out of range
    # Proppi's cost comes from its plan in «Plataformas tradicionales»
    pl = Plataforma(fuente=FuenteLead.PROPPI, nombre="Proppi")
    db.add(pl)
    db.flush()
    db.add(
        PlataformaPlan(
            plataforma_id=pl.id,
            precio=920_000,
            activacion=date(2026, 7, 15),
            vencimiento=date(2026, 10, 14),
            cupo_total=10,
            destacados_total=2,
        )
    )
    _lead(db, FuenteLead.PROPPI, sep)
    db.flush()
    g = H(p["ger"])
    fb = items(ok(client.get(IN, params=Q, headers=g)))["facebook"]
    ok(client.patch(f"{IN}/{fb['id']}", json={"costo_mensual": 300_000}, headers=g))
    d = ok(client.get(f"{IN}/{fb['id']}", params=Q, headers=g))
    r = d["resultados"]
    assert (r["leads"], r["cerrados"], r["arriendos"], r["ventas"], r["en_proceso"]) == (
        3,
        2,
        1,
        1,
        1,
    )
    assert (r["costo"], r["costo_lead"], r["costo_cierre"], r["conversion"]) == (
        300_000,
        100_000,
        150_000,
        66.7,
    )
    assert d["origen_costo"] == "Costo mensual registrado aquí"
    pr = ok(
        client.get(
            f"{IN}/{items(ok(client.get(IN, params=Q, headers=g)))['proppi']['id']}",
            params=Q,
            headers=g,
        )
    )
    assert (pr["resultados"]["costo"], pr["origen_costo"]) == (
        300_000,
        "Planes de «Plataformas tradicionales»",
    )
    t = ok(client.get(IN, params=Q, headers=g))
    assert (t["kpis"]["leads"], t["kpis"]["cerrados"], t["kpis"]["costos"]) == (4, 2, 600_000)


def test_connection_states_and_secrets(client, p, H):
    g = H(p["ger"])
    fb = items(ok(client.get(IN, headers=g)))["facebook"]
    url = f"{IN}/{fb['id']}"
    assert client.post(f"{url}/probar", headers=g).status_code == 422  # nothing saved yet
    assert client.put(f"{url}/datos", json={"valores": {"nada": "x"}}, headers=g).status_code == 422
    assert (
        client.put(f"{url}/datos", json={"valores": {"cuenta": ""}}, headers=g).status_code == 422
    )
    secreto = "EAAG-super-secreto-9876"
    r = ok(
        client.put(
            f"{url}/datos", json={"valores": {"cuenta": "act_123", "api": secreto}}, headers=g
        )
    )
    assert r["estado_txt"] == "Por confirmar conexión"
    res = client.get(url, headers=g)
    assert secreto not in res.text  # the secret is never stored nor returned
    campos = {c["key"]: c for c in res.json()["conexion"]["campos"]}
    assert (campos["cuenta"]["valor"], campos["api"]["valor"], campos["api"]["guardado"]) == (
        "act_123",
        None,
        "••••9876",
    )
    # Saving again with the secret empty keeps the hint
    ok(client.put(f"{url}/datos", json={"valores": {"formularios": "Todos", "api": ""}}, headers=g))
    assert {c["key"]: c for c in ok(client.get(url, headers=g))["conexion"]["campos"]}["api"][
        "guardado"
    ] == "••••9876"
    pr = ok(client.post(f"{url}/probar", headers=g))
    assert pr["ok"] is False and "Todavía no hay conector para Facebook" in pr["txt"]
    ok(client.post(f"{url}/desconectar", headers=g))
    d = ok(client.get(url, headers=g))
    assert d["estado"] == "sin_conectar" and all(
        c["guardado"] is None and c["valor"] is None for c in d["conexion"]["campos"]
    )
    assert client.post(f"{url}/desconectar", headers=g).status_code == 409
    acciones = [h["accion"] for h in d["historial"]]
    assert acciones[:3] == [
        "Desconectó la integración",
        "Probó la conexión",
        "Guardó los datos de conexión",
    ]
    # Calendar asks for nothing here
    cal = items(ok(client.get(IN, headers=g)))["calendario"]
    r = client.put(f"{IN}/{cal['id']}/datos", json={"valores": {}}, headers=g)
    assert r.status_code == 422 and "Mi agenda" in r.json()["detail"]


def test_settings_and_add(client, p, H):
    g = H(p["ger"])
    wa = items(ok(client.get(IN, headers=g)))["whatsapp"]
    url = f"{IN}/{wa['id']}"
    assert client.patch(url, json={"como": "fax"}, headers=g).status_code == 422
    assert client.patch(url, json={"costo_mensual": -1}, headers=g).status_code == 422
    r = ok(client.patch(url, json={"avisar_falla": False, "como": "directa"}, headers=g))
    assert (r["avisar_falla"], r["como"]) == (False, "directa")
    assert (
        client.post(IN, json={"nombre": "facebook", "grupo": "red"}, headers=g).status_code == 409
    )
    assert (
        client.post(IN, json={"nombre": "YouTube", "grupo": "video"}, headers=g).status_code == 422
    )
    assert (
        client.post(
            IN, json={"nombre": "YouTube", "grupo": "red"}, headers=H(p["coord"])
        ).status_code
        == 403
    )
    n = ok(
        client.post(
            IN,
            json={"nombre": "YouTube", "grupo": "red", "costo_mensual": 90_000, "usuario": "cdc"},
            headers=g,
        ),
        201,
    )
    assert (n["estado_txt"], n["es_lead"], n["resultados"]) == (
        "Por confirmar conexión",
        False,
        None,
    )
    assert "YouTube" in [x["nombre"] for x in ok(client.get(IN, headers=g))["grupos"][1]["items"]]
    # Registro de cambios: Gerencia sees it; Coordinación doesn't
    rc = ok(
        client.get(
            "/api/v1/registro-cambios",
            params={"modulo": "Integraciones", "desde": "2026-09-01", "hasta": "2026-12-31"},
            headers=g,
        )
    )
    assert {"Agregó la integración", "Avisar a Gerencia si la conexión falla"} <= {
        x["accion"] for x in rc["items"]
    }
    assert (
        client.get(
            "/api/v1/registro-cambios", params={"modulo": "Integraciones"}, headers=H(p["coord"])
        ).status_code
        == 403
    )


def test_whatsapp_usage(client, p, H, db):
    ld = _lead(db, FuenteLead.OTRO, NOW - timedelta(days=1))
    for medio in ("whatsapp", "whatsapp", "correo"):
        db.add(
            LeadEvento(
                lead_id=ld.id,
                tipo=TipoEventoLead.MENSAJE,
                titulo="Mensaje",
                datos={"medio": medio},
                created_at=NOW - timedelta(days=1),
            )
        )
    db.flush()
    g = H(p["ger"])
    wa = items(ok(client.get(IN, headers=g)))["whatsapp"]
    d = ok(client.get(f"{IN}/{wa['id']}", params=Q, headers=g))
    assert (d["uso_t"], d["uso"]) == ("Mensajes por WhatsApp registrados en los leads", "2")
