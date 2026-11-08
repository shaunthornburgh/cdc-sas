"""Pausas activas (G11; G-041, G-045, G-060, G-065): the reminder window, «Realizada», missed
pauses, absences, the schedule and message, the team view and the Descargas file."""

import csv
import io
from datetime import UTC, date, datetime

import pytest

from app.models import Novedad
from app.models.enums import ActividadComercial, Cargo, EstadoNovedad, TipoNovedad
from app.services import fechas
from tests.conftest import auth_header, login

PA = "/api/v1/pausas-activas"
# Wednesday 7 Oct 2026, 10:05: the morning pause (10:00, 15 minutes) is on screen
NOW = datetime(2026, 10, 7, 10, 5, tzinfo=fechas.BOGOTA)
INICIO = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def reloj(monkeypatch):
    state = {"now": NOW}
    monkeypatch.setattr(fechas, "now", lambda: state["now"])
    return state


@pytest.fixture
def p(make_user, db):
    out = {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Valeria Aux"
        ),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "juan": make_user(
            Cargo.ASESOR,
            email="juan@example.com",
            full_name="Juan Asesor",
            actividades=[ActividadComercial.VENTAS],
        ),
        "ana": make_user(
            Cargo.ASESOR,
            email="ana@example.com",
            full_name="Ana Asesora",
            actividades=[ActividadComercial.ARRIENDOS],
        ),
    }
    for u in out.values():  # they started on 1 Oct
        u.created_at = INICIO
    db.flush()
    return out


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
    return res.json() if res.content else None


def err(res, code, texto=""):
    assert res.status_code == code, res.text
    assert texto in res.json()["detail"], res.json()["detail"]


def test_reminder_window_and_mark(client, p, H, reloj):
    hj = H(p["juan"])
    a = ok(client.get(f"{PA}/ahora", headers=hj))
    assert a["activa"]["turno"] == "manana" and a["mensaje"].startswith("Haz tu pausa activa")
    assert [s["estado"] for s in a["hoy"]] == ["en_curso", "programada"]
    r = ok(client.post(f"{PA}/realizada", headers=hj))
    assert r["turno"] == "manana"
    err(client.post(f"{PA}/realizada", headers=hj), 409, "Ya marcaste")
    a = ok(client.get(f"{PA}/ahora", headers=hj))
    assert a["activa"] is None and a["hoy"][0]["estado_txt"] == "✓ Realizada · 10:05"
    # After the window: nothing to mark, and it's «No realizada» for whoever didn't
    reloj["now"] = datetime(2026, 10, 7, 10, 20, tzinfo=fechas.BOGOTA)
    err(client.post(f"{PA}/realizada", headers=H(p["ana"])), 409, "no hay una pausa")
    a = ok(client.get(f"{PA}/ahora", headers=H(p["ana"])))
    assert a["hoy"][0]["estado"] == "no_realizada"
    # Weekends have no pauses
    reloj["now"] = datetime(2026, 10, 10, 10, 5, tzinfo=fechas.BOGOTA)
    assert ok(client.get(f"{PA}/ahora", headers=hj))["activa"] is None
    # Gerencia has them too (G-041)
    reloj["now"] = datetime(2026, 10, 7, 15, 3, tzinfo=fechas.BOGOTA)
    assert ok(client.post(f"{PA}/realizada", headers=H(p["ger"])))["turno"] == "tarde"


def test_history_absences_and_compliance(client, p, H, reloj, db):
    db.add(
        Novedad(
            empleado_id=p["ana"].id,
            tipo=TipoNovedad.INCAPACIDAD,
            desde=date(2026, 10, 5),
            hasta=date(2026, 10, 5),
            estado=EstadoNovedad.REGISTRADA,
        )
    )
    db.flush()
    ok(client.post(f"{PA}/realizada", headers=H(p["ana"])))
    m = ok(
        client.get(
            f"{PA}/mias", params={"desde": "2026-10-01", "hasta": "2026-10-31"}, headers=H(p["ana"])
        )
    )
    # Oct 1, 2, 6: 6 missed; Oct 5: absence; Oct 7: morning done, afternoon still ahead
    assert m["resumen"] == {"pct": 14, "realizadas": 1, "no_realizadas": 6}
    hoy = m["dias"][0]
    assert hoy["fecha"] == "2026-10-07" and hoy["tarde"]["estado"] == "programada"
    lunes = next(d for d in m["dias"] if d["fecha"] == "2026-10-05")
    assert lunes["manana"]["estado_txt"] == "Ausencia"
    err(
        client.get(
            f"{PA}/mias", params={"desde": "2026-10-09", "hasta": "2026-10-01"}, headers=H(p["ana"])
        ),
        422,
    )


def test_schedule_message_and_team(client, p, H, reloj):
    # Schedule: only the Auxiliar (G-045); message: Auxiliar and Gerencia (G-065)
    body = {"hora_manana": "09:30", "hora_tarde": "15:30", "minutos": 45}
    err(client.put(f"{PA}/horario", json=body, headers=H(p["ger"])), 403, "Auxiliar")
    err(
        client.put(f"{PA}/horario", json=body | {"hora_manana": "09:40"}, headers=H(p["aux"])),
        422,
        "15 minutos",
    )
    err(client.put(f"{PA}/horario", json=body | {"hora_manana": "13:00"}, headers=H(p["aux"])), 422)
    err(client.put(f"{PA}/horario", json=body | {"minutos": 90}, headers=H(p["aux"])), 422)
    ok(client.put(f"{PA}/horario", json=body, headers=H(p["aux"])))
    err(client.put(f"{PA}/mensaje", json={"mensaje": " "}, headers=H(p["ger"])), 422)
    err(client.put(f"{PA}/mensaje", json={"mensaje": "Estira"}, headers=H(p["coord"])), 403)
    ok(client.put(f"{PA}/mensaje", json={"mensaje": "Estira la espalda"}, headers=H(p["ger"])))
    a = ok(client.get(f"{PA}/ahora", headers=H(p["juan"])))
    assert a["mensaje"] == "Estira la espalda" and a["horario"]["manana"] == "9:30 a. m."
    assert a["activa"]["turno"] == "manana"  # 9:30 + 45 min covers 10:05
    ok(client.post(f"{PA}/realizada", headers=H(p["juan"])))
    # Team view: access, KPIs, Coordinación only sees its team
    assert client.get(f"{PA}/equipo", headers=H(p["juan"])).status_code == 403
    e = ok(client.get(f"{PA}/equipo", headers=H(p["aux"])))
    assert e["config"]["minutos"] == 45 and e["puede"]["horario"] is True
    k = e["kpis"]["manana"]
    assert (k["hechas"], k["total"], k["estado"]) == (1, 5, "en_curso")
    c = ok(client.get(f"{PA}/equipo", headers=H(p["coord"])))
    assert {f["full_name"] for f in c["hoy_filas"]} == {"Juan Asesor", "Ana Asesora"}
    assert c["puede"]["horario"] is False and c["puede"]["mensaje"] is False
    one = ok(client.get(f"{PA}/equipo", params={"user_id": str(p["juan"].id)}, headers=H(p["ger"])))
    assert one["persona"]["full_name"] == "Juan Asesor" and one["persona"]["dias"]
    err(
        client.get(f"{PA}/equipo", params={"user_id": str(p["ger"].id)}, headers=H(p["coord"])), 403
    )
    # Registro de cambios: module «Pausas activas»
    t = ok(
        client.get(
            "/api/v1/registro-cambios",
            params={"modulo": "Pausas activas", "desde": "2026-10-01", "hasta": "2026-12-31"},
            headers=H(p["ger"]),
        )
    )
    assert {i["accion"] for i in t["items"]} == {
        "Cambió horario de las pausas",
        "Cambió mensaje de la pausa activa",
    }
    # Descargas: closed pauses only (today's afternoon isn't there yet)
    res = client.get(
        "/api/v1/descargas/pau.csv",
        params={
            "desde": "2026-10-01",
            "hasta": "2026-10-07",
            "alcance": "emp",
            "user_id": str(p["juan"].id),
        },
        headers=H(p["aux"]),
    )
    assert res.status_code == 200, res.text
    head, *rows = list(csv.reader(io.StringIO(res.content.decode()[1:]), delimiter=";"))
    assert head[3:6] == ["Pausa", "Hora programada", "Estado"]
    assert len(rows) == 9  # 4 days × 2 + this morning
    assert rows[-1][3:7] == ["Mañana", "09:30", "Realizada", "10:05"]
    assert {r[5] for r in rows[:-1]} == {"No realizada"}
