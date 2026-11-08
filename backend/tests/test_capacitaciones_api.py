"""Capacitaciones (X07, Z03; G-046, G-047): programar, responder, completar, registrar, the team
view, avisos, agenda and the Descargas file."""

import csv
import io
from datetime import datetime, timedelta

import pytest

from app.models.enums import ActividadComercial, Cargo, FuncionIndependiente
from app.services import fechas
from tests.conftest import auth_header, login

CP = "/api/v1/capacitaciones"
AV = "/api/v1/avisos"
NOW = datetime(2026, 10, 7, 10, 0, tzinfo=fechas.BOGOTA)


@pytest.fixture
def reloj(monkeypatch):
    state = {"now": NOW}
    monkeypatch.setattr(fechas, "now", lambda: state["now"])
    return state


@pytest.fixture
def p(make_user):
    return {
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
    return res.json() if res.content else None


def err(res, code, texto=""):
    assert res.status_code == code, res.text
    assert texto in res.json()["detail"], res.json()["detail"]


CAP = {
    "fecha": "2026-10-09",
    "hora": "08:00",
    "area": "Todas las áreas",
    "tema": "Uso del software: seguimientos y agenda",
    "presenta": "Gina Gerencia",
    "lugar": "Sala de reuniones",
}


def _tipos(client, h, vista="por_atender"):
    return [a["tipo"] for a in ok(client.get(AV, params={"vista": vista}, headers=h))["items"]]


def test_program_by_group_and_access(client, p, H, reloj):
    # Asesores and Atención don't see the team view or program
    for k in ("juan", "laura"):
        assert client.get(f"{CP}/equipo", headers=H(p[k])).status_code == 403
        assert client.post(CP, json=CAP, headers=H(p[k])).status_code == 403
    # Validation
    err(
        client.post(CP, json=CAP | {"fecha": "2026-10-01"}, headers=H(p["coord"])),
        422,
        "ya pasaron",
    )
    err(client.post(CP, json=CAP | {"area": "Marte"}, headers=H(p["coord"])), 422, "área")
    err(client.post(CP, json=CAP | {"tema": " "}, headers=H(p["coord"])), 422, "tema")
    err(client.post(CP, json=CAP | {"participantes": "per"}, headers=H(p["coord"])), 422)
    # Comercial = the asesores; everyone = all but Gerencia; specific people
    c = ok(client.post(CP, json=CAP | {"participantes": "com"}, headers=H(p["coord"])), 201)
    assert c["participantes"] == 2 and c["code"].startswith("CAP-")
    todo = ok(client.post(CP, json=CAP, headers=H(p["ger"])), 201)
    assert todo["participantes"] == 5  # aux, coord, juan, ana, laura
    per = ok(
        client.post(
            CP,
            json=CAP | {"participantes": "per", "personas": [str(p["laura"].id)]},
            headers=H(p["aux"]),
        ),
        201,
    )
    assert per["participantes"] == 1
    eq = ok(client.get(f"{CP}/equipo", headers=H(p["aux"])))
    assert eq["kpis"]["programadas"] == 3 and eq["kpis"]["por_responder"] == 8
    origen = {x["code"]: x["origen_txt"] for x in eq["programadas"]}
    assert origen[c["code"]] == "Programada por Coordinación"
    assert eq["puede_descargar"] is True
    assert ok(client.get(f"{CP}/equipo", headers=H(p["coord"])))["puede_descargar"] is False


def test_answer_complete_and_learned(client, p, H, reloj):
    c = ok(client.post(CP, json=CAP | {"participantes": "com"}, headers=H(p["coord"])), 201)
    cid = c["id"]
    hj, ha = H(p["juan"]), H(p["ana"])
    # The participant sees it, has an aviso and an agenda item
    m = ok(client.get(f"{CP}/mias", headers=hj))
    assert (
        m["por_responder"] == 1
        and m["programadas"][0]["origen_txt"] == "Programada por Coordinación"
    )
    assert "capacitacion_responder" in _tipos(client, hj)
    ag = ok(
        client.get(
            "/api/v1/agenda", params={"desde": "2026-10-09", "hasta": "2026-10-09"}, headers=hj
        )
    )
    assert any(i["id"] == f"cap:{cid}" for i in ag["items"]), ag
    # Not invited → 404; bad reason → 422
    assert (
        client.post(
            f"{CP}/{cid}/responder", json={"acepta": True}, headers=H(p["laura"])
        ).status_code
        == 404
    )
    err(
        client.post(f"{CP}/{cid}/responder", json={"acepta": False, "motivo": "x"}, headers=ha), 422
    )
    err(
        client.post(
            f"{CP}/{cid}/responder", json={"acepta": False, "motivo": "Otro motivo"}, headers=ha
        ),
        422,
        "motivo",
    )
    ok(client.post(f"{CP}/{cid}/responder", json={"acepta": True}, headers=hj))
    r = ok(
        client.post(
            f"{CP}/{cid}/responder",
            json={"acepta": False, "motivo": "Cita con cliente a esa hora"},
            headers=ha,
        )
    )
    assert r["estado_txt"] == "✕ No participa" and "cita con cliente" in r["motivo_txt"]
    assert "capacitacion_responder" not in _tipos(client, hj)
    # Declined ones leave the agenda
    ag = ok(
        client.get(
            "/api/v1/agenda", params={"desde": "2026-10-09", "hasta": "2026-10-09"}, headers=ha
        )
    )
    assert not any(i["id"] == f"cap:{cid}" for i in ag["items"])
    # Completing before it starts → 422; organizers only
    err(
        client.post(f"{CP}/{cid}/completar", json={"asistentes": []}, headers=H(p["coord"])),
        422,
        "empezó",
    )
    reloj["now"] = NOW + timedelta(days=2, hours=1)
    assert "capacitacion_completar" in _tipos(client, H(p["coord"]))
    assert (
        client.post(f"{CP}/{cid}/completar", json={"asistentes": []}, headers=hj).status_code == 403
    )
    err(
        client.post(
            f"{CP}/{cid}/completar", json={"asistentes": [str(p["laura"].id)]}, headers=H(p["aux"])
        ),
        422,
        "invitadas",
    )
    d = ok(
        client.post(
            f"{CP}/{cid}/completar", json={"asistentes": [str(p["juan"].id)]}, headers=H(p["aux"])
        )
    )
    assert (d["estado"], d["participaron"]) == ("realizada", 1)
    err(client.post(f"{CP}/{cid}/responder", json={"acepta": True}, headers=hj), 409)
    err(client.post(f"{CP}/{cid}/cancelar", json={"motivo": "x"}, headers=H(p["aux"])), 409)
    # History and «qué aprendí»
    his = ok(client.get(f"{CP}/mias", headers=hj))["historico"]
    assert his[0]["estado_txt"] == "✓ Participé"
    ok(
        client.post(
            f"{CP}/{cid}/aprendizaje", json={"aprendio": "Agendar seguimientos"}, headers=hj
        )
    )
    err(client.post(f"{CP}/{cid}/aprendizaje", json={"aprendio": "x"}, headers=ha), 409)
    eq = ok(client.get(f"{CP}/equipo", headers=H(p["ger"])))
    x = eq["programadas"][0]
    assert (x["si"], x["no"], x["pe"]) == (1, 1, 0) and eq["kpis"]["no_participaron"] == 1
    assert eq["kpis"]["con_motivo"] == 1


def test_register_cancel_and_download(client, p, H, reloj):
    hl = H(p["laura"])
    reg = {
        "fecha": "2026-10-02",
        "hora": "16:00",
        "area": "Comercial",
        "tema": "Fotos que venden en portales",
        "presenta": "Proveedor externo",
        "aprendio": "Luz natural y foto de fachada primero",
    }
    err(
        client.post(f"{CP}/registrar", json=reg | {"fecha": "2026-10-20"}, headers=hl),
        422,
        "futura",
    )
    err(client.post(f"{CP}/registrar", json=reg | {"aprendio": ""}, headers=hl), 422)
    ok(client.post(f"{CP}/registrar", json=reg, headers=hl), 201)
    his = ok(client.get(f"{CP}/mias", headers=hl))["historico"]
    assert his[0]["origen_txt"] == "La registré yo" and his[0]["estado_txt"] == "✓ Participé"
    eq = ok(client.get(f"{CP}/equipo", headers=H(p["aux"])))
    assert (
        eq["kpis"]["registradas"] == 1
        and eq["registradas"][0]["persona"]["full_name"] == "Laura Atención"
    )
    assert "capacitacion_registrada" in _tipos(client, H(p["ger"]), "resumen")
    # Cancel a programmed one
    c = ok(client.post(CP, json=CAP, headers=H(p["aux"])), 201)
    err(client.post(f"{CP}/{c['id']}/cancelar", json={"motivo": " "}, headers=H(p["aux"])), 422)
    ok(
        client.post(
            f"{CP}/{c['id']}/cancelar",
            json={"motivo": "Se cruza con el cierre de mes"},
            headers=H(p["aux"]),
        )
    )
    assert ok(client.get(f"{CP}/equipo", headers=H(p["aux"])))["kpis"]["programadas"] == 0
    # Descargas: one row per person and training; Coordinación can't download it (G-047)
    q = {"desde": "2026-10-01", "hasta": "2026-10-31"}
    res = client.get("/api/v1/descargas/cap.csv", params=q, headers=H(p["aux"]))
    assert res.status_code == 200, res.text
    head, *rows = list(csv.reader(io.StringIO(res.content.decode()[1:]), delimiter=";"))
    assert head[:4] == ["Código", "Fecha", "Hora", "Tema"]
    temas = [(r[3], r[9], r[8]) for r in rows]
    assert ("Fotos que venden en portales", "Laura Atención", "Realizada") in temas
    assert sum(1 for t in temas if t[2] == "Cancelada") == 5
    err(client.get("/api/v1/descargas/cap.csv", params=q, headers=H(p["coord"])), 403, "Auxiliar")
