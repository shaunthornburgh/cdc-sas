"""Avisos (G09 / M10 / C05): system avisos, sync and auto-resolve, comunicados, Mi agenda."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.models import Aviso, Cita, Comunicado, Lead
from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, EstadoCita, FuenteLead, FuncionIndependiente, TipoCita
from app.services import avisos as svc
from app.services import fechas
from app.services import rendimiento as rend
from tests.conftest import auth_header, login

AV = "/api/v1/avisos"


def _hoy() -> date:
    """Today in Bogotá, as the app counts it (the container's date is UTC: after 7 p. m. in
    Bogotá it's already tomorrow)."""
    return fechas.local_date(fechas.now())


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "aux": make_user(Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Vale"),
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


def lista(client, H, who, vista="por_atender"):
    return ok(client.get(AV, params={"vista": vista}, headers=H(who)))["items"]


def _lead(db, minutos_atras: int, **kw) -> Lead:
    ld = Lead(full_name="Cliente Nuevo", phone="3001234567", fuente=FuenteLead.PROPPI, **kw)
    db.add(ld)
    db.flush()
    ld.created_at = datetime.now(UTC) - timedelta(minutes=minutos_atras)
    db.flush()
    return ld


# ---------------------------------------------------------------- system avisos


def test_lead_without_responsable_syncs_and_resolves(client, p, H, db):
    viejo = _lead(db, 40)
    _lead(db, 5)  # not yet: under the 15 minutes
    c = ok(client.get(f"{AV}/conteo", headers=H(p["coord"])))
    assert c["por_atender"] == 1
    items = lista(client, H, p["coord"])
    a = items[0]
    assert (a["tipo"], a["nivel"], a["link"], a["accion_txt"]) == (
        "lead_sin_responsable",
        "warn",
        f"/leads/{viejo.id}",
        "Asignar el lead",
    )
    assert "más de 15 min" in a["titulo"] and a["que_hacer"]
    # Atención sees new leads (both), as «Nuevo lead»
    assert {x["tipo"] for x in lista(client, H, p["laura"])} == {"lead_nuevo"}
    # Syncing again never repeats it
    lista(client, H, p["coord"])
    assert db.query(Aviso).filter(Aviso.destinatario_id == p["coord"].id).count() == 1
    # Gerencia moved the threshold to 30 minutes: the text follows
    ok(
        client.put(
            "/api/v1/configuracion/automatizaciones",
            json={"lead_sin_responsable_min": 30},
            headers=H(p["ger"]),
        )
    )
    assert "más de 30 min" in lista(client, H, p["coord"])[0]["titulo"]
    # Someone takes it: closes on its own
    viejo.assigned_to_id = p["laura"].id
    db.flush()
    assert lista(client, H, p["coord"]) == []
    at = lista(client, H, p["coord"], "atendidos")[0]
    assert (at["estado"], at["resuelto_auto"]) == ("atendido", True)
    # Other roles don't get it
    assert lista(client, H, p["juan"]) == []


def test_citas(client, p, H, db):
    ld = _lead(db, 60, assigned_to_id=p["laura"].id)
    cuando = datetime.now(UTC) + timedelta(days=1)
    pend = Cita(
        lead_id=ld.id, tipo=TipoCita.VISITA_VENTA, scheduled_at=cuando, asesor_id=p["juan"].id
    )
    rech = Cita(
        lead_id=ld.id,
        tipo=TipoCita.VISITA_VENTA,
        scheduled_at=cuando,
        estado=EstadoCita.RECHAZADA,
        motivo="Choque con otra cita",
    )
    db.add_all([pend, rech])
    db.flush()
    j = lista(client, H, p["juan"])
    assert [x["tipo"] for x in j] == ["cita_por_aceptar"] and j[0]["limite_at"]
    assert "cita_rechazada" in {x["tipo"] for x in lista(client, H, p["coord"])}
    lau = [x for x in lista(client, H, p["laura"]) if x["tipo"] == "cita_rechazada"]
    assert len(lau) == 1 and "Choque" in lau[0]["detalle"]
    pend.estado = EstadoCita.ACEPTADA
    db.flush()
    assert lista(client, H, p["juan"]) == []


def test_area_below_60_weekly(client, p, H, monkeypatch):
    calls = []

    def fake(db, viewer, periodo):
        calls.append(periodo)
        return {
            "areas": [
                {
                    "key": "comercial",
                    "titulo": "Comercial",
                    "total": 57,
                    "anterior": 68,
                    "personas": "Juan 48 · Ana 66",
                    "metas": [
                        {"titulo": "Captaciones aprobadas", "pct": 41, "logrado": 7, "meta": 17}
                    ],
                },
                {
                    "key": "atencion",
                    "titulo": "Atención",
                    "total": 82,
                    "anterior": 80,
                    "personas": "",
                    "metas": [],
                },
            ]
        }

    monkeypatch.setattr(rend, "empresa", fake)
    items = lista(client, H, p["ger"])
    area = [x for x in items if x["tipo"] == "area_bajo"]
    assert len(area) == 1 and area[0]["nivel"] == "bad"
    assert [d["lbl"] for d in area[0]["datos"]] == [
        "Resultado del área",
        "Lo que más la bajó",
        "Mes anterior",
    ]
    assert (
        area[0]["datos"][0]["val"] == "57%"
        and "Captaciones aprobadas 41%" in area[0]["datos"][1]["sub"]
    )
    # Once a week: the next sync doesn't recalculate, and the aviso stays until Gerencia closes it
    lista(client, H, p["ger"])
    assert len(calls) == 1
    assert [x for x in lista(client, H, p["ger"]) if x["tipo"] == "area_bajo"]
    # Coordinación never gets it
    assert not [x for x in lista(client, H, p["coord"]) if x["tipo"] == "area_bajo"]


# ---------------------------------------------------------------- actions on an aviso


def test_note_schedule_attend_reopen(client, p, H, db):
    _lead(db, 40)
    a = lista(client, H, p["coord"])[0]
    url = f"{AV}/{a['id']}"
    assert (
        client.post(f"{url}/notas", json={"texto": "x"}, headers=H(p["coord"])).status_code == 422
    )
    ok(client.post(f"{url}/notas", json={"texto": "Hablé con Laura"}, headers=H(p["coord"])), 201)
    manana = (fechas.local_date(fechas.now()) + timedelta(days=1)).isoformat()
    it = ok(
        client.post(
            f"{url}/agendar",
            json={"titulo": "Reunión con Atención", "fecha": manana, "hora": "09:00"},
            headers=H(p["coord"]),
        ),
        201,
    )
    assert (it["aviso_id"], it["hora_txt"]) == (a["id"], "9:00 a. m.")
    # Someone else's aviso doesn't exist for them
    assert client.post(f"{url}/atender", json={}, headers=H(p["ger"])).status_code == 404
    r = ok(client.post(f"{url}/atender", json={"nota": "Asignado a Laura"}, headers=H(p["coord"])))
    assert (r["estado"], r["atendido_por_name"], r["resuelto_auto"]) == (
        "atendido",
        "Mateo Coord",
        False,
    )
    assert [n["texto"][:12] for n in r["notas"]] == ["Hablé con La", "Agendado en ", "Asignado a L"]
    assert client.post(f"{url}/atender", json={}, headers=H(p["coord"])).status_code == 409
    # Attended by hand: the next sync doesn't reopen or touch it
    assert lista(client, H, p["coord"]) == []
    r = ok(client.post(f"{url}/reabrir", headers=H(p["coord"])))
    assert r["estado"] == "por_atender"


# ---------------------------------------------------------------- comunicados


def test_comunicados_and_read_receipts(client, p, H, db):
    body = {
        "titulo": "Reunión general",
        "cuerpo": "El viernes a las 8:00 a. m.",
        "audiencia": ["gerencia"],
    }
    assert client.post(f"{AV}/comunicados", json=body, headers=H(p["coord"])).status_code == 403
    assert client.post(f"{AV}/comunicados", json=body, headers=H(p["juan"])).status_code == 403
    o = ok(client.get(f"{AV}/opciones", headers=H(p["coord"])))
    assert set(o["audiencias"]) == {"asesores", "atencion"}
    pasado = (_hoy() - timedelta(days=2)).isoformat()
    bad = body | {"audiencia": ["asesores"], "expira_el": pasado}
    assert client.post(f"{AV}/comunicados", json=bad, headers=H(p["coord"])).status_code == 422

    c = ok(
        client.post(
            f"{AV}/comunicados",
            json=body | {"audiencia": ["asesores", "atencion"]},
            headers=H(p["coord"]),
        ),
        201,
    )
    assert (c["total"], c["leidos"], c["audiencia_txt"]) == (2, 0, "Asesores, Atención y Preventa")
    # «normal»: «Resumen del día», not the bell
    assert lista(client, H, p["juan"]) == []
    res = lista(client, H, p["juan"], "resumen")
    assert res[0]["titulo"] == "Reunión general" and res[0]["enviado_por"] == "Mateo Coord"
    assert ok(client.get(f"{AV}/conteo", headers=H(p["juan"])))["resumen_sin_leer"] == 1
    cnt = ok(client.post(f"{AV}/leidos", json={"ids": [res[0]["id"]]}, headers=H(p["juan"])))
    assert cnt["resumen_sin_leer"] == 0
    enviados = ok(client.get(f"{AV}/comunicados", headers=H(p["coord"])))
    assert enviados[0]["leidos"] == 1
    assert {x["nombre"]: bool(x["leido_at"]) for x in enviados[0]["lecturas"]} == {
        "Juan Asesor": True,
        "Laura Atención": False,
    }
    # «alta» from Gerencia to everyone: in the bell, with what to do
    alta = body | {"audiencia": list(svc.AUDIENCIAS), "prioridad": "alta"}
    c2 = ok(client.post(f"{AV}/comunicados", json=alta, headers=H(p["ger"])), 201)
    assert c2["total"] == 4  # everyone but the sender
    a = lista(client, H, p["aux"])[0]
    assert (a["tipo"], a["nivel"], a["que_hacer"]) == (
        "comunicado",
        "warn",
        "Léelo y márcalo como atendido.",
    )
    # Gerencia sees every comunicado; Coordinación only its own
    assert len(ok(client.get(f"{AV}/comunicados", headers=H(p["ger"])))) == 2
    assert len(ok(client.get(f"{AV}/comunicados", headers=H(p["coord"])))) == 1
    # Expired: hidden
    db.query(Comunicado).update({"expira_el": _hoy() - timedelta(days=1)})
    db.flush()
    assert lista(client, H, p["aux"]) == [] and lista(client, H, p["juan"], "resumen") == []
