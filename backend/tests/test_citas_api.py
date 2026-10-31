from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, FuenteLead
from app.services import leads as lead_service
from tests.conftest import auth_header, login

CITAS = "/api/v1/citas"
LEADS = "/api/v1/leads"


@pytest.fixture
def atencion(make_user):
    return make_user(Cargo.ATENCION_CLIENTE, email="laura@example.com", full_name="Laura Atención")


@pytest.fixture
def juan(make_user):
    return make_user(
        email="juan@example.com",
        full_name="Juan Asesor",
        actividades=[A.CAPTACION, A.VENTAS, A.ARRIENDOS],
    )


@pytest.fixture
def bruno(make_user):
    return make_user(
        email="bruno@example.com", full_name="Bruno Captador", actividades=[A.CAPTACION]
    )


@pytest.fixture
def h(client, atencion):
    return auth_header(login(client, atencion.email)["access_token"])


@pytest.fixture
def lead(db, atencion):
    lead = lead_service.create_lead(
        db,
        {"full_name": "Cliente Cita", "phone": "3005550199", "fuente": FuenteLead.FACEBOOK},
        actor=None,
    )
    lead_service.follow_lead(db, lead, atencion)
    return lead


def at(hours: float) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def new_cita(client, h, lead, asesor, hours=24, tipo="visita_arriendo"):
    body = {
        "lead_id": str(lead.id),
        "tipo": tipo,
        "scheduled_at": at(hours),
        "asesor_id": str(asesor.id),
        "inmueble": "INM-0333 Apto Laureles",
    }
    return client.post(CITAS, json=body, headers=h)


def test_create_cita_sets_lead_stage(client, h, lead, juan):
    res = new_cita(client, h, lead, juan)
    assert res.status_code == 201, res.text
    cita = res.json()
    assert cita["code"].startswith("CIT-")
    assert cita["estado"] == "pendiente"
    assert cita["asesor"]["full_name"] == "Juan Asesor"
    assert cita["lead"]["code"] == lead.code

    detail = client.get(f"{LEADS}/{lead.id}", headers=h).json()
    assert detail["etapa"] == "cita_programada"
    assert detail["cita_activa"]["code"] == cita["code"]
    assert detail["eventos"][-1]["tipo"] == "cita"


def test_asesor_needs_the_activity(client, h, lead, bruno):
    res = new_cita(client, h, lead, bruno, tipo="visita_venta")
    assert res.status_code == 422
    assert "Ventas" in res.json()["detail"]
    assert new_cita(client, h, lead, bruno, tipo="captacion").status_code == 201


def test_asesor_options_show_eligibility_and_busy(client, h, lead, juan, bruno, db):
    new_cita(client, h, lead, juan, hours=24)
    res = client.get(
        f"{CITAS}/asesores", params={"tipo": "visita_arriendo", "scheduled_at": at(24.5)}, headers=h
    )
    opts = {o["full_name"]: o for o in res.json()}
    assert opts["Juan Asesor"]["elegible"] is True
    assert opts["Juan Asesor"]["ocupado_con"] is not None
    assert opts["Bruno Captador"]["elegible"] is False


def test_overlapping_cita_conflicts(client, db, h, atencion, lead, juan):
    new_cita(client, h, lead, juan, hours=24)
    other = lead_service.create_lead(
        db, {"full_name": "Otro", "phone": "3005550111", "fuente": FuenteLead.PROPPI}, actor=None
    )
    lead_service.follow_lead(db, other, atencion)
    assert new_cita(client, h, other, juan, hours=24.5).status_code == 409
    assert new_cita(client, h, other, juan, hours=26).status_code == 201


def test_one_active_cita_per_lead(client, h, lead, juan, bruno):
    new_cita(client, h, lead, juan)
    assert new_cita(client, h, lead, bruno, tipo="captacion", hours=48).status_code == 409


def test_cita_in_the_past_rejected(client, h, lead, juan):
    assert new_cita(client, h, lead, juan, hours=-1).status_code == 422


def test_status_flow_reject_reassign_accept_cancel(client, h, lead, juan, make_user):
    ana = make_user(email="ana@example.com", full_name="Ana Asesora", actividades=[A.ARRIENDOS])
    cita = new_cita(client, h, lead, juan).json()
    url = f"{CITAS}/{cita['id']}"

    assert client.post(f"{url}/status", json={"estado": "rechazada"}, headers=h).status_code == 422
    rej = client.post(
        f"{url}/status", json={"estado": "rechazada", "motivo": "Choque con otra cita"}, headers=h
    ).json()
    assert rej["estado"] == "rechazada"
    assert rej["requiere_accion"] is True and rej["bucket"] == "accion"

    # A rejected cita can't be accepted directly: it has to go to another asesor first.
    assert client.post(f"{url}/status", json={"estado": "aceptada"}, headers=h).status_code == 422
    sent = client.post(f"{url}/reassign", json={"asesor_id": str(ana.id)}, headers=h).json()
    assert (sent["estado"], sent["asesor"]["full_name"]) == ("pendiente", "Ana Asesora")

    ok = client.post(f"{url}/status", json={"estado": "aceptada"}, headers=h).json()
    assert ok["estado"] == "aceptada" and ok["bucket"] == "aceptadas"

    cancel = client.post(
        f"{url}/status", json={"estado": "cancelada", "motivo": "El cliente canceló"}, headers=h
    ).json()
    assert cancel["estado"] == "cancelada"
    assert [e["titulo"].split(" ", 2)[-1] for e in cancel["historial"]][-1].endswith("cancelada")

    # Lead goes back to En gestión and can get a new cita.
    assert client.get(f"{LEADS}/{lead.id}", headers=h).json()["etapa"] == "en_gestion"


def test_reschedule_needs_reason_and_reaccept(client, h, lead, juan):
    cita = new_cita(client, h, lead, juan).json()
    url = f"{CITAS}/{cita['id']}"
    client.post(f"{url}/status", json={"estado": "aceptada"}, headers=h)

    res = client.post(
        f"{url}/reschedule",
        json={"scheduled_at": at(48), "motivo": "El cliente pidió cambiar el día"},
        headers=h,
    ).json()
    assert res["estado"] == "pendiente"
    assert "reprogramada" in res["historial"][-1]["titulo"]
    empty = client.post(
        f"{url}/reschedule", json={"scheduled_at": at(50), "motivo": " "}, headers=h
    )
    assert empty.status_code == 422


def test_realizada_only_after_it_happened(client, db, h, lead, juan):
    cita_json = new_cita(client, h, lead, juan).json()
    url = f"{CITAS}/{cita_json['id']}"
    client.post(f"{url}/status", json={"estado": "aceptada"}, headers=h)
    assert client.post(f"{url}/status", json={"estado": "realizada"}, headers=h).status_code == 422

    from app.models import Cita

    cita = db.get(Cita, cita_json["id"])
    cita.scheduled_at = datetime.now(UTC) - timedelta(hours=2)
    db.flush()
    res = client.post(
        f"{url}/status", json={"estado": "realizada", "motivo": "Le gustó"}, headers=h
    )
    assert res.json()["estado"] == "realizada"


def test_pending_within_one_hour_requires_action(client, h, lead, juan):
    cita = new_cita(client, h, lead, juan, hours=0.5).json()
    assert cita["requiere_accion"] is True
    listing = client.get(CITAS, params={"bucket": "accion"}, headers=h).json()
    assert [c["code"] for c in listing["items"]] == [cita["code"]]
    assert listing["counts"]["accion"] == 1


def test_lead_with_active_cita_cannot_be_closed(client, h, lead, juan):
    new_cita(client, h, lead, juan)
    res = client.post(
        f"{LEADS}/{lead.id}/stage", json={"etapa": "perdido", "motivo": "no_interesado"}, headers=h
    )
    assert res.status_code == 422
    assert "cita" in res.json()["detail"]


def test_only_owner_programs_citas(client, db, lead, juan, make_user):
    other = make_user(Cargo.ATENCION_CLIENTE, email="otra@example.com")
    h2 = auth_header(login(client, other.email)["access_token"])
    # The lead belongs to Laura: invisible to the other Atención user.
    assert new_cita(client, h2, lead, juan).status_code == 404
