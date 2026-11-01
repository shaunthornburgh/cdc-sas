"""Movimientos y GPS (K05): alerts, justification, review, field work, config, history."""

from datetime import datetime, timedelta

import pytest

from app.models import Cita, Inmueble, Lead
from app.models.enums import ActividadComercial as A
from app.models.enums import (
    Cargo,
    EstadoCita,
    EtapaLead,
    FuenteLead,
    FuncionIndependiente,
    TipoCita,
    TipoNegocio,
)
from app.services import fechas
from app.services import movimientos as svc
from app.services import rendimiento as rend
from tests.conftest import auth_header, login

MOV = "/api/v1/movimientos"
# Saturday 3 oct 2026, 11:00 a. m. in Bogotá: inside the working day.
NOW = datetime(2026, 10, 3, 11, 0, tzinfo=fechas.BOGOTA)


@pytest.fixture(autouse=True)
def reloj(monkeypatch):
    state = {"now": NOW}
    monkeypatch.setattr(fechas, "now", lambda: state["now"])
    return state


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "aux": make_user(Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com"),
        "juan": make_user(
            email="juan@example.com", full_name="Juan Capta", actividades=[A.CAPTACION]
        ),
        "carla": make_user(
            email="carla@example.com", full_name="Carla Arriendos", actividades=[A.ARRIENDOS]
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


def alerta(client, H, who, tipo="salida_ruta", **kw):
    return client.post(f"{MOV}/alertas", json={"tipo": tipo} | kw, headers=H(who))


def campo(client, H, who, **kw):
    data = {"tipo_campo": "otra", "actividad_campo": "captacion"} | kw
    return client.post(f"{MOV}/campo", json=data, headers=H(who))


CITA_OK = {
    "motivo": "cita_fuera_ruta",
    "inmueble_codigo": "inm-0351",
    "cliente": "Cliente Ejemplo 17",
    "observacion": "El cliente pidió ver otro inmueble",
}


# ---------------------------------------------------------------- access


def test_access(client, p, H):
    for k in ("ger", "coord", "juan", "laura"):
        assert client.get(MOV, headers=H(p[k])).status_code == 200, k
    # No GPS: Auxiliar and an asesor without Captación
    for k in ("aux", "carla"):
        assert client.get(MOV, headers=H(p[k])).status_code == 403, k
    assert client.get(f"{MOV}/panel", headers=H(p["juan"])).status_code == 403
    assert client.get(f"{MOV}/export.csv", headers=H(p["juan"])).status_code == 403
    o = ok(client.get(f"{MOV}/opciones", headers=H(p["juan"])))
    assert (o["perfil"], o["panel"], o["gps_activo"]) == ("asesor", False, True)
    assert o["alertas_propias"] == ["salida_ruta", "tiempo_detenido"]
    assert o["tipos_campo"] == {}
    og = ok(client.get(f"{MOV}/opciones", headers=H(p["ger"])))
    assert (og["perfil"], og["panel"], og["gerencia"]) == (None, True, True)
    nombres = [e["full_name"] for e in og["empleados"]]
    assert {"Juan Capta", "Mateo Coord", "Laura Atención"} <= set(nombres)
    assert "Carla Arriendos" not in nombres
    ol = ok(client.get(f"{MOV}/opciones", headers=H(p["laura"])))
    assert set(ol["tipos_campo"]) == {"apoyo_cita", "otra"}  # no acompañamiento (G-040)
    assert ol["gps_activo"] is False  # only while in the field


# ---------------------------------------------------------------- GPS reports


def test_report_rules(client, p, H, reloj):
    m = ok(alerta(client, H, p["juan"], lugar="Laureles", lat=6.24, lng=-75.59), 201)
    assert (m["code"][:4], m["estado"], m["es_alerta"], m["puede_justificar"]) == (
        "MOV-",
        "sin_justificar",
        True,
        True,
    )
    assert m["tiene_ubicacion"] and "lat" not in m  # coordinates only via /ubicacion
    assert m["revisa"] == "Coordinación"
    d = ok(alerta(client, H, p["juan"], "tiempo_detenido"), 201)
    assert d["minutos_umbral"] == 20 and "Más de 20 min" in d["detalle_txt"]
    # Not for this cargo / no GPS
    assert alerta(client, H, p["juan"], "salida_zona").status_code == 422
    assert alerta(client, H, p["carla"]).status_code == 403
    # Coordinador and Atención: only while in the field
    assert alerta(client, H, p["coord"], "salida_zona").status_code == 422
    assert alerta(client, H, p["laura"], "tiempo_detenido").status_code == 422
    # Outside the working day
    reloj["now"] = NOW.replace(hour=19)
    assert alerta(client, H, p["juan"]).status_code == 422
    reloj["now"] = NOW
    old = (NOW - timedelta(days=2)).isoformat()
    assert alerta(client, H, p["juan"], ocurrido_at=old).status_code == 422


# ---------------------------------------------------------------- justify + review


def test_justify_and_review_by_coordinacion(client, p, H, db):
    db.add(Inmueble(codigo="INM-0351", negocio=TipoNegocio.ARRIENDO, direccion="Cra 1"))
    db.flush()
    m = ok(alerta(client, H, p["juan"]), 201)
    url = f"{MOV}/{m['id']}"
    # Wrong motive for a salida, missing fields, someone else
    bad = {"motivo": "inventario", "inmueble_codigo": "X", "cliente": "Y", "observacion": "Z"}
    assert client.post(f"{url}/justificar", json=bad, headers=H(p["juan"])).status_code == 422
    falta = CITA_OK | {"cliente": ""}
    assert client.post(f"{url}/justificar", json=falta, headers=H(p["juan"])).status_code == 422
    assert client.post(f"{url}/justificar", json=CITA_OK, headers=H(p["coord"])).status_code == 403
    # Can't review before it's justified
    assert client.post(f"{url}/aprobar", json={}, headers=H(p["coord"])).status_code == 409

    j = ok(client.post(f"{url}/justificar", json=CITA_OK, headers=H(p["juan"])))
    assert (j["estado"], j["inmueble_codigo"], j["inmueble_en_catalogo"]) == (
        "por_revisar",
        "INM-0351",
        True,
    )
    assert j["detalle_txt"] == "Cita fuera de ruta · INM-0351 · Cliente Ejemplo 17"
    assert client.post(f"{url}/justificar", json=CITA_OK, headers=H(p["juan"])).status_code == 409
    # Gerencia doesn't review asesores (K05-ger: only the Coordinador's)
    assert client.post(f"{url}/aprobar", json={}, headers=H(p["ger"])).status_code == 403
    lst = ok(client.get(MOV, headers=H(p["coord"])))
    assert lst["items"][0]["puede_revisar"] is True

    r = ok(client.post(f"{url}/aprobar", json={"nota": "ok"}, headers=H(p["coord"])))
    assert (r["estado"], r["revisado_por_name"], r["descuenta"]) == (
        "aprobada",
        "Mateo Coord",
        False,
    )
    assert client.post(f"{url}/rechazar", json={}, headers=H(p["coord"])).status_code == 409

    h = ok(client.get(f"{url}/historial", headers=H(p["ger"])))
    assert [e["tipo"] for e in h] == ["creado", "justificado", "aprobado"]
    assert (h[2]["actor_name"], h[2]["estado_antes"], h[2]["estado_despues"]) == (
        "Mateo Coord",
        "por_revisar",
        "aprobada",
    )
    # Someone else's alert isn't visible to another asesor
    otro = ok(alerta(client, H, p["juan"]), 201)
    assert client.get(f"{MOV}/{otro['id']}", headers=H(p["laura"])).status_code == 404


def test_personal_reasons(client, p, H):
    s = ok(alerta(client, H, p["juan"]), 201)
    body = {"motivo": "permiso_personal", "motivo_texto": "Trámite"}
    url = f"{MOV}/{s['id']}/justificar"
    assert client.post(url, json=body, headers=H(p["juan"])).status_code == 422  # who authorized
    j = ok(client.post(url, json=body | {"autorizo": "coordinacion"}, headers=H(p["juan"])))
    assert j["detalle_txt"] == "Permiso personal · Trámite · autorizó coordinación"
    d = ok(alerta(client, H, p["juan"], "tiempo_detenido"), 201)
    j = ok(
        client.post(
            f"{MOV}/{d['id']}/justificar",
            json={
                "motivo": "imprevisto_personal",
                "motivo_texto": "Llanta pinchada",
                "evidencias": 2,
            },
            headers=H(p["juan"]),
        )
    )
    assert (j["evidencias"], j["autorizo"]) == (2, None)


def test_rejection_takes_a_point(client, p, H, db):
    m = ok(alerta(client, H, p["juan"]), 201)
    ok(client.post(f"{MOV}/{m['id']}/justificar", json=CITA_OK, headers=H(p["juan"])))
    r = ok(client.post(f"{MOV}/{m['id']}/rechazar", json={}, headers=H(p["coord"])))
    assert (r["estado"], r["descuenta"]) == ("rechazada", True)
    res = rend.Calculo(db, rend.periodo()).resultado(p["juan"])
    gps = [d for d in res.descuentos if d["titulo"].startswith("GPS")]
    assert len(gps) == 1 and gps[0]["puntos"] == 1 and m["code"] in gps[0]["detalle"]


def test_deadline(client, p, H, db, reloj):
    m = ok(alerta(client, H, p["juan"]), 201)
    assert m["plazo_at"] is None  # PENDIENTE DE CONFIGURACIÓN: nothing expires
    reloj["now"] = NOW + timedelta(days=3)
    assert svc.descuentos(db, p["juan"], rend.periodo().start, rend.periodo().end) == []
    # Only Coordinación / Gerencia configure
    assert (
        client.put(f"{MOV}/config", json={"plazo_horas": 24}, headers=H(p["juan"])).status_code
        == 403
    )
    c = ok(client.put(f"{MOV}/config", json={"plazo_horas": 24}, headers=H(p["ger"])))
    assert (c["plazo_horas"], c["updated_by_name"]) == (24, "Gina Gerencia")
    lst = ok(client.get(MOV, headers=H(p["juan"])))
    it = lst["pendientes"][0]
    assert (it["vencida"], it["descuenta"], it["puede_justificar"]) == (True, True, False)
    res = client.post(f"{MOV}/{m['id']}/justificar", json=CITA_OK, headers=H(p["juan"]))
    assert res.status_code == 409
    assert len(svc.descuentos(db, p["juan"], rend.periodo().start, rend.periodo().end)) == 1
    # Clearing the deadline (null) sets it back to «pendiente»
    c = ok(client.put(f"{MOV}/config", json={"plazo_horas": None}, headers=H(p["coord"])))
    assert c["plazo_horas"] is None
    panel = ok(client.get(f"{MOV}/panel", headers=H(p["coord"])))
    assert "Plazo para justificar: 24 h → pendiente" in panel["cambios_config"][0]["detalle"]


# ---------------------------------------------------------------- field work


def _cita(db, asesor):
    lead = Lead(
        full_name="Cliente", phone="3001112233", fuente=FuenteLead.OTRO, etapa=EtapaLead.NUEVO
    )
    db.add(lead)
    db.flush()
    c = Cita(
        lead_id=lead.id,
        tipo=TipoCita.VISITA_VENTA,
        scheduled_at=NOW + timedelta(hours=5),
        asesor_id=asesor.id,
        estado=EstadoCita.ACEPTADA,
    )
    db.add(c)
    db.flush()
    return c


def test_coordinador_field_work_and_gerencia_review(client, p, H, db, reloj, make_user):
    ana = make_user(email="ana@example.com", full_name="Ana Capta", actividades=[A.CAPTACION])
    assert campo(client, H, p["juan"]).status_code == 403
    assert campo(client, H, p["coord"], tipo_campo="acompanamiento_ruta").status_code == 422
    grupal = {"tipo_campo": "salida_grupal", "acompanados_ids": [str(ana.id)]}
    assert campo(client, H, p["coord"], **grupal).status_code == 422  # needs 2+
    w = ok(
        campo(
            client,
            H,
            p["coord"],
            tipo_campo="acompanamiento_ruta",
            acompanados_ids=[str(p["juan"].id)],
            detalle="captación Laureles",
        ),
        201,
    )
    assert (w["estado"], w["en_curso"], w["acompanados"], w["puede_finalizar"]) == (
        "registro",
        True,
        ["Juan Capta"],
        True,
    )
    assert campo(client, H, p["coord"]).status_code == 409  # already in the field
    o = ok(client.get(f"{MOV}/opciones", headers=H(p["coord"])))
    assert o["gps_activo"] is True

    # While in the field the Coordinador gets alerts; Gerencia reviews them
    a = ok(alerta(client, H, p["coord"], "salida_zona", lugar="Itagüí"), 201)
    assert a["revisa"] == "Gerencia"
    ok(client.post(f"{MOV}/{a['id']}/justificar", json=CITA_OK, headers=H(p["coord"])))
    assert (
        client.post(f"{MOV}/{a['id']}/aprobar", json={}, headers=H(p["coord"])).status_code == 403
    )
    ok(client.post(f"{MOV}/{a['id']}/aprobar", json={}, headers=H(p["ger"])))

    reloj["now"] = NOW + timedelta(hours=2, minutes=10)
    assert client.post(f"{MOV}/{w['id']}/finalizar", headers=H(p["ger"])).status_code == 403
    f = ok(client.post(f"{MOV}/{w['id']}/finalizar", headers=H(p["coord"])))
    assert (f["en_curso"], f["duracion_txt"]) == (False, "2 h 10 min")
    assert client.post(f"{MOV}/{w['id']}/finalizar", headers=H(p["coord"])).status_code == 409
    # Records aren't justified or reviewed
    res = client.post(f"{MOV}/{w['id']}/justificar", json=CITA_OK, headers=H(p["coord"]))
    assert res.status_code == 422

    lst = ok(
        client.get(MOV, params={"desde": "2026-10-01", "hasta": "2026-10-03"}, headers=H(p["ger"]))
    )
    k = lst["kpis"]
    assert (k["alertas"], k["justificadas"], k["coord_campo_min"], k["coord_campo_salidas"]) == (
        1,
        1,
        130,
        1,
    )
    per = {r["empleado"]["full_name"]: r for r in lst["por_empleado"]}
    assert per["Mateo Coord"]["campo_min"] == 130


def test_atencion_apoyo_en_cita(client, p, H, db):
    c = _cita(db, p["juan"])
    assert campo(client, H, p["laura"], tipo_campo="salida_grupal").status_code == 422
    assert campo(client, H, p["laura"], tipo_campo="apoyo_cita").status_code == 422  # no cita
    o = ok(client.get(f"{MOV}/opciones", headers=H(p["laura"])))
    assert o["citas"][0]["txt"].startswith(c.code)
    w = ok(campo(client, H, p["laura"], tipo_campo="apoyo_cita", cita_id=str(c.id)), 201)
    assert (w["tipo"], w["cita_code"]) == ("atencion_campo", c.code)
    a = ok(alerta(client, H, p["laura"], "tiempo_detenido"), 201)
    assert a["revisa"] == "Coordinación"
    panel = ok(client.get(f"{MOV}/panel", headers=H(p["coord"])))
    assert [x["empleado"]["full_name"] for x in panel["atencion_campo"]["abiertos"]] == [
        "Laura Atención"
    ]


# ---------------------------------------------------------------- list, panel, export, privacy


def test_filters_panel_export_and_location_log(client, p, H):
    a = ok(alerta(client, H, p["juan"], lugar="Laureles", lat=6.24, lng=-75.59), 201)
    ok(alerta(client, H, p["juan"], "tiempo_detenido", lat=6.20, lng=-75.57), 201)
    g = H(p["ger"])
    assert len(ok(client.get(MOV, params={"tipo": "salida_ruta"}, headers=g))["items"]) == 1
    assert len(ok(client.get(MOV, params={"estado": "aprobada"}, headers=g))["items"]) == 0
    lst = ok(client.get(MOV, params={"empleado_id": str(p["coord"].id)}, headers=g))
    assert lst["items"] == [] and lst["por_empleado"][0]["alertas"] == 2  # per person ignores it
    assert (
        client.get(
            MOV, params={"desde": "2026-10-05", "hasta": "2026-10-01"}, headers=g
        ).status_code
        == 422
    )

    pn = ok(client.get(f"{MOV}/panel", headers=g))
    assert (pn["con_gps"], len(pn["hoy"]), len(pn["mapa"])) == (["Juan Capta"], 2, 2)
    assert {(m["x"], m["y"]) for m in pn["mapa"]} == {(0.0, 0.0), (1.0, 1.0)}  # NW → top-left
    assert pn["sin_gps"] == ["Carla Arriendos"]

    u = ok(client.post(f"{MOV}/{a['id']}/ubicacion", headers=g))
    assert (u["lat"], u["lugar"]) == (6.24, "Laureles")
    h = ok(client.get(f"{MOV}/{a['id']}/historial", headers=g))
    assert (h[-1]["tipo"], h[-1]["actor_name"]) == ("ubicacion", "Gina Gerencia")

    res = client.get(f"{MOV}/export.csv", headers=g)
    assert res.status_code == 200 and "attachment" in res.headers["content-disposition"]
    lines = res.text.lstrip("﻿").strip().splitlines()
    assert lines[0].startswith("Código,Fecha") and len(lines) == 3


def test_config_alert_time(client, p, H):
    assert (
        client.put(f"{MOV}/config", json={"minutos_alerta": 2}, headers=H(p["coord"])).status_code
        == 422
    )
    ok(client.put(f"{MOV}/config", json={"minutos_alerta": 30}, headers=H(p["coord"])))
    d = ok(alerta(client, H, p["juan"], "tiempo_detenido"), 201)
    assert d["minutos_umbral"] == 30
