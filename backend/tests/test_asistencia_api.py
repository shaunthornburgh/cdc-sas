"""Asistencia (G-048 … G-051, Z04, K17, X08): marking, location, reviews, settings and wiring."""

from datetime import date, datetime, timedelta

import pytest

from app.models import Marcacion
from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, MedioTransporte
from app.services import asistencia, fechas, preoperacional
from tests.conftest import auth_header, login

AS = "/api/v1/asistencia"
SEDE = (6.2117, -75.5850)
LEJOS = (6.2300, -75.5850)  # ~2 km north
LUNES = date(2026, 10, 5)


def at(h: int, m: int, d: date = LUNES) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, tzinfo=fechas.BOGOTA)


@pytest.fixture
def reloj(monkeypatch):
    state = {"now": at(7, 58)}
    monkeypatch.setattr(fechas, "now", lambda: state["now"])
    return state


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo"),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Valeria"
        ),
        "juan": make_user(
            Cargo.ASESOR, email="juan@example.com", full_name="Juan", actividades=[A.VENTAS]
        ),
        "ana": make_user(
            Cargo.ASESOR, email="ana@example.com", full_name="Ana", actividades=[A.CAPTACION]
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
def sede(client, p, H, reloj):
    ok(
        client.put(
            f"{AS}/config", json={"valores": {"exigir_preoperacional": False}}, headers=H(p["aux"])
        )
    )
    return ok(
        client.post(
            f"{AS}/sedes",
            json={
                "nombre": "Sede principal",
                "direccion": "Cl 10 Sur # 50-28",
                "lat": SEDE[0],
                "lng": SEDE[1],
                "radio_m": 100,
            },
            headers=H(p["aux"]),
        ),
        201,
    )


def entrada(client, h, pos=SEDE, **kw):
    loc = {"lat": pos[0], "lng": pos[1]} if pos else {}
    return ok(client.post(f"{AS}/entrada", json=loc | kw, headers=h))


def salida(client, h, pos=SEDE, **kw):
    return ok(client.post(f"{AS}/salida", json={"lat": pos[0], "lng": pos[1]} | kw, headers=h))


def test_access_and_settings(client, p, H, reloj, sede):
    assert (
        client.post(f"{AS}/entrada", json={}, headers=H(p["ger"])).status_code == 403
    )  # Gerencia doesn't mark
    assert client.get(f"{AS}/equipo", headers=H(p["juan"])).status_code == 403
    assert (
        client.put(
            f"{AS}/config", json={"valores": {"limite_min": 45}}, headers=H(p["coord"])
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"{AS}/config", json={"valores": {"limite_min": 20}}, headers=H(p["aux"])
        ).status_code
        == 422
    )
    assert (
        client.put(
            f"{AS}/config", json={"valores": {"salida_lv": "07:00"}}, headers=H(p["ger"])
        ).status_code
        == 422
    )
    ok(
        client.put(
            f"{AS}/config",
            json={"valores": {"marcan": {c.value: True for c in Cargo}}},
            headers=H(p["ger"]),
        )
    )
    assert ok(client.get(f"{AS}/mia", headers=H(p["ger"])))["marca"] is True
    # Coordinación assigns asesores, not the Auxiliar; the Auxiliar assigns anyone
    otra = ok(
        client.post(
            f"{AS}/sedes",
            json={
                "nombre": "Envigado",
                "direccion": "Cra 43A # 38 Sur",
                "lat": 6.1719,
                "lng": -75.5868,
            },
            headers=H(p["ger"]),
        ),
        201,
    )
    assert (
        client.put(
            f"{AS}/ubicacion/{p['aux'].id}", json={"sede_id": otra["id"]}, headers=H(p["coord"])
        ).status_code
        == 403
    )
    ok(
        client.put(
            f"{AS}/ubicacion/{p['juan'].id}", json={"sede_id": otra["id"]}, headers=H(p["coord"])
        )
    )
    m = ok(client.get(f"{AS}/mia", headers=H(p["juan"])))
    assert m["ubicacion"] == "Oficina · Envigado" and "asignada por Mateo" in m["ubicacion_det"]
    assert (
        client.post(
            f"{AS}/sedes",
            json={"nombre": "X", "direccion": "Cra 1", "lat": 40, "lng": -3},
            headers=H(p["aux"]),
        ).status_code
        == 422
    )


def test_entrada_on_time_late_and_limit(client, p, H, reloj, sede):
    r = entrada(client, H(p["juan"]))
    assert (r["ok"], r["marcacion"]["entrada_txt"]) == (True, "A tiempo")
    assert (
        client.post(
            f"{AS}/entrada", json={"lat": SEDE[0], "lng": SEDE[1]}, headers=H(p["juan"])
        ).status_code
        == 409
    )
    reloj["now"] = at(8, 7)
    r = entrada(client, H(p["ana"]))["marcacion"]
    assert (r["entrada_txt"], r["tipo_tarde"], r["minutos_descuento"]) == (
        "Impuntual · leve · 7 min",
        "leve",
        7,
    )
    reloj["now"] = at(8, 25)
    r = entrada(client, H(p["coord"]))["marcacion"]
    assert r["tipo_tarde"] == "grave"
    reloj["now"] = at(8, 31)
    res = client.post(f"{AS}/entrada", json={"lat": SEDE[0], "lng": SEDE[1]}, headers=H(p["aux"]))
    assert res.status_code == 422 and "límite" in res.json()["detail"]
    t = ok(client.get(f"{AS}/equipo", headers=H(p["ger"])))
    assert (
        t["kpis"]["marcaron"],
        t["kpis"]["leves"],
        t["kpis"]["graves"],
        t["kpis"]["faltan"],
    ) == (3, 1, 1, ["Valeria"])
    assert (
        next(f for f in t["filas_hoy"] if f["nombre"] == "Valeria")["estado"]
        == "Sin marcar · impuntualidad"
    )


def test_preoperacional_first(client, p, H, reloj, sede, db):
    ok(
        client.put(
            f"{AS}/config", json={"valores": {"exigir_preoperacional": True}}, headers=H(p["aux"])
        )
    )
    res = client.post(f"{AS}/entrada", json={"lat": SEDE[0], "lng": SEDE[1]}, headers=H(p["juan"]))
    assert res.status_code == 422 and "preoperacional" in res.json()["detail"]
    preoperacional.registrar(
        db, p["juan"], medio=MedioTransporte.A_PIE, placa=None, respuestas=None, observaciones=None
    )
    db.flush()
    assert entrada(client, H(p["juan"]))["ok"]


def test_outside_accept_reject_and_remark(client, p, H, reloj, sede):
    r = entrada(client, H(p["juan"]), LEJOS)
    assert r["ok"] is False and r["requiere_justificacion"] and "Coordinación" in r["detalle"]
    r = entrada(
        client, H(p["juan"]), LEJOS, motivo="cambio_solicitado", texto="El cliente movió la visita"
    )
    assert r["marcacion"]["entrada_txt"] == "Por aprobar" and r["marcacion"][
        "entrada_lugar"
    ].startswith("A 2")
    mid = r["marcacion"]["id"]
    assert (
        client.post(
            f"{AS}/{mid}/revisar", json={"que": "entrada", "acepta": True}, headers=H(p["aux"])
        ).status_code
        == 403
    )
    assert (
        ok(
            client.post(
                f"{AS}/{mid}/revisar",
                json={"que": "entrada", "acepta": True},
                headers=H(p["coord"]),
            )
        )["entrada_txt"]
        == "Fuera de ubicación · aceptada"
    )
    # Ana: rejected → aviso → marks again inside at 9:00 → 60 min of impuntualidad
    r = entrada(client, H(p["ana"]), None, motivo="imprevisto", texto="No me carga el GPS")
    assert r["marcacion"]["entrada_lugar"] == "Sin ubicación ✕"
    x = ok(
        client.post(
            f"{AS}/{r['marcacion']['id']}/revisar",
            json={"que": "entrada", "acepta": False},
            headers=H(p["coord"]),
        )
    )
    assert x["entrada_estado"] == "rechazada"
    av = ok(client.get("/api/v1/avisos", headers=H(p["ana"])))["items"]
    assert any(
        a["titulo"] == "Marca entrada cuando estés en la sede o ubicación asignada" for a in av
    )
    reloj["now"] = at(9, 0)
    r = entrada(client, H(p["ana"]))["marcacion"]
    assert (r["entrada_estado"], r["minutos_tarde"], r["minutos_descuento"]) == (
        "impuntual",
        60,
        60,
    )
    # The Coordinador's own justification goes to Gerencia
    reloj["now"] = at(8, 10, LUNES + timedelta(days=1))
    r = entrada(
        client, H(p["coord"]), LEJOS, motivo="imprevisto", texto="Reunión con un propietario"
    )
    cid = r["marcacion"]["id"]
    assert (
        client.post(
            f"{AS}/{cid}/revisar", json={"que": "entrada", "acepta": True}, headers=H(p["coord"])
        ).status_code
        == 403
    )
    ok(
        client.post(
            f"{AS}/{cid}/revisar", json={"que": "entrada", "acepta": True}, headers=H(p["ger"])
        )
    )


def test_salida_early_and_extra(client, p, H, reloj, sede):
    entrada(client, H(p["juan"]))
    entrada(client, H(p["ana"]))
    reloj["now"] = at(16, 30)
    r = salida(client, H(p["juan"]))
    assert r["requiere_justificacion"] and "6:00 p. m." in r["titulo"]
    r = salida(client, H(p["juan"]), motivo="permiso", texto="Cita médica autorizada")["marcacion"]
    assert r["salida_txt"] == "En revisión · 1 h 30 min antes"
    x = ok(
        client.post(
            f"{AS}/{r['id']}/revisar", json={"que": "salida", "acepta": False}, headers=H(p["aux"])
        )
    )
    assert x["minutos_descuento"] == 90
    # Horas extra: Coordinación AND the Auxiliar
    reloj["now"] = at(19, 10)
    r = salida(client, H(p["ana"]), texto="Cierre con el cliente")["marcacion"]
    assert r["salida_txt"] == "Horas extra en revisión · 1 h 10 min"
    ok(
        client.post(
            f"{AS}/{r['id']}/revisar", json={"que": "extra", "acepta": True}, headers=H(p["coord"])
        )
    )
    assert (
        client.post(
            f"{AS}/{r['id']}/revisar", json={"que": "extra", "acepta": True}, headers=H(p["coord"])
        ).status_code
        == 409
    )
    t = ok(client.get(f"{AS}/equipo", headers=H(p["aux"])))
    pend = next(x for x in t["por_aprobar"] if x["que"] == "extra")
    assert pend["puede"] and pend["estado"] == "Coordinación: aceptó · Auxiliar: pendiente"
    x = ok(
        client.post(
            f"{AS}/{r['id']}/revisar", json={"que": "extra", "acepta": True}, headers=H(p["aux"])
        )
    )
    assert (x["salida_txt"], x["minutos_extra"]) == ("Horas extra aceptadas · 1 h 10 min", 70)
    t = ok(
        client.get(
            f"{AS}/equipo",
            params={"desde": "2026-10-01", "hasta": "2026-10-31"},
            headers=H(p["ger"]),
        )
    )
    assert (t["kpis"]["extra"], t["kpis"]["minutos"]) == (70, 90)
    csv_ = client.get(
        f"{AS}/export.csv",
        params={"desde": "2026-10-01", "hasta": "2026-10-31"},
        headers=H(p["aux"]),
    )
    assert csv_.status_code == 200 and "Horas extra aceptadas (min)" in csv_.text
    assert client.get(f"{AS}/export.csv", headers=H(p["coord"])).status_code == 403


def test_route_zone_salary_and_puntualidad(client, p, H, reloj, sede, db):
    # Ana has an accepted route in Laureles today: she marks there, not at the sede
    r = ok(
        client.post(
            "/api/v1/rutas",
            json={
                "asesor_id": str(p["ana"].id),
                "desde": "2026-10-05",
                "hasta": "2026-10-09",
                "dias": [1, 2, 3, 4, 5],
                "zonas": [
                    {
                        "zona": "Laureles",
                        "hora_inicio": "08:00",
                        "hora_fin": "12:00",
                        "dias": [1, 2, 3, 4, 5],
                    }
                ],
            },
            headers=H(p["coord"]),
        ),
        201,
    )
    ok(
        client.post(
            f"/api/v1/rutas/{r['id']}/responder", json={"acepta": True}, headers=H(p["ana"])
        )
    )
    assert ok(client.get(f"{AS}/mia", headers=H(p["ana"])))["ubicacion"] == "En ruta · Laureles"
    assert entrada(client, H(p["ana"]))["ok"] is False  # at the sede, ~4 km from Laureles
    m = entrada(client, H(p["ana"]), asistencia.ZONA_CENTROS["Laureles"])["marcacion"]
    assert (m["entrada_lugar"], m["asignada"]) == ("Laureles ✓", "En ruta · Laureles")
    # Juan: late two days → salary minutes and the automatic Puntualidad rating
    reloj["now"] = at(8, 12)
    entrada(client, H(p["juan"]))
    reloj["now"] = at(7, 55, LUNES + timedelta(days=1))
    entrada(client, H(p["juan"]))
    assert asistencia.para_salario(db, p["juan"].id, date(2026, 10, 1), date(2026, 10, 15)) == (
        12,
        0,
    )
    pu = asistencia.puntualidad(db, p["juan"], date(2026, 10, 1), date(2026, 10, 31))
    assert (pu["dias"], pu["a_tiempo"], pu["pct"], pu["txt"]) == (2, 1, 50, "1 grave")
    res = ok(client.get("/api/v1/rendimiento/mio", headers=H(p["juan"])))
    cal = next(c for c in res["calificaciones"] if c["key"] == "puntualidad")
    assert cal["automatico"] and cal["valor"] == preoperacional.puntaje(50)
    rc = ok(
        client.get(
            "/api/v1/registro-cambios",
            params={"modulo": "Asistencia", "desde": "2026-09-01", "hasta": "2026-12-31"},
            headers=H(p["ger"]),
        )
    )
    assert {"Agregó la sede", "Marcó entrada"} <= {x["accion"] for x in rc["items"]}
    assert db.query(Marcacion).count() == 3
