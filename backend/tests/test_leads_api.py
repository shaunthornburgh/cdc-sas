from datetime import UTC, datetime, timedelta

import pytest

from app.models import LeadEvento
from app.models.enums import ActividadComercial as A
from app.models.enums import (
    Cargo,
    EtapaLead,
    FuenteLead,
    FuncionIndependiente,
    MotivoPerdida,
    TipoEventoLead,
)
from app.services import leads as lead_service
from tests.conftest import auth_header, login

LEADS = "/api/v1/leads"


# ---------------------------------------------------------------- fixtures


@pytest.fixture
def atencion(make_user):
    return make_user(Cargo.ATENCION_CLIENTE, email="laura@example.com", full_name="Laura Atención")


@pytest.fixture
def preventas(make_user):
    return make_user(
        Cargo.ASESOR,
        email="pablo@example.com",
        full_name="Pablo Preventa",
        funcion=FuncionIndependiente.PRE_VENTAS,
    )


@pytest.fixture
def coord(make_user):
    return make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Coordinadora")


@pytest.fixture
def as_user(client):
    cache: dict[str, dict] = {}

    def _headers(user) -> dict:
        if user.email not in cache:
            cache[user.email] = auth_header(login(client, user.email)["access_token"])
        return cache[user.email]

    return _headers


@pytest.fixture
def make_lead(db):
    counter = 0

    def _make(**kw):
        nonlocal counter
        counter += 1
        data = {
            "full_name": f"Cliente {counter}",
            "phone": f"300 555 01{counter:02d}",
            "fuente": FuenteLead.FACEBOOK,
            "negocio": "arriendo",
            "busca": "Apartamento en Laureles",
        } | kw
        return lead_service.create_lead(db, data, actor=None)

    return _make


def future(hours: int = 24) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


# ---------------------------------------------------------------- access


@pytest.mark.parametrize(
    ("cargo", "kwargs"),
    [
        (Cargo.ASESOR, {"actividades": [A.CAPTACION, A.VENTAS]}),
        (Cargo.ASESOR, {}),
        (Cargo.AUXILIAR_ADMINISTRATIVA, {}),
    ],
)
def test_module_closed_to_asesores_and_auxiliar(client, make_user, as_user, cargo, kwargs):
    user = make_user(cargo, email="x@example.com", **kwargs)
    h = as_user(user)
    assert client.get(LEADS, headers=h).status_code == 403
    assert client.get("/api/v1/citas", headers=h).status_code == 403
    body = {"full_name": "X", "phone": "3005550000", "fuente": "facebook"}
    assert client.post(LEADS, json=body, headers=h).status_code == 403


def test_module_open_to_atencion_preventas_and_managers(
    client, atencion, preventas, coord, make_user, as_user
):
    gerente = make_user(Cargo.GERENCIA, email="g@example.com")
    for user in (atencion, preventas, coord, gerente):
        assert client.get(LEADS, headers=as_user(user)).status_code == 200


def test_requires_login(client):
    assert client.get(LEADS).status_code == 401


def test_handlers_see_unassigned_and_own_managers_see_all(
    client, db, atencion, preventas, coord, make_lead, as_user
):
    libre = make_lead(full_name="Libre")
    mio = make_lead(full_name="Mío")
    ajeno = make_lead(full_name="Ajeno")
    lead_service.follow_lead(db, mio, atencion)
    lead_service.follow_lead(db, ajeno, preventas)

    names = {lead["full_name"] for lead in client.get(LEADS, headers=as_user(atencion)).json()}
    assert names == {"Libre", "Mío"}
    assert client.get(f"{LEADS}/{ajeno.id}", headers=as_user(atencion)).status_code == 404

    all_names = {lead["full_name"] for lead in client.get(LEADS, headers=as_user(coord)).json()}
    assert {"Libre", "Mío", "Ajeno"} <= all_names
    assert libre.code.startswith("LD-")


# ---------------------------------------------------------------- CRUD


def test_create_lead_manually_and_follow(client, atencion, as_user):
    body = {
        "full_name": "Mariana Restrepo",
        "phone": "300 555 0101",
        "email": "mariana@example.com",
        "fuente": "ciencuadras",
        "negocio": "venta",
        "busca": "Casa en Envigado",
        "presupuesto": "Hasta $650.000.000",
        "seguir": True,
    }
    res = client.post(LEADS, json=body, headers=as_user(atencion))
    assert res.status_code == 201, res.text
    lead = res.json()
    assert lead["code"].startswith("LD-")
    assert lead["etapa"] == "nuevo"
    assert lead["assigned_to"]["full_name"] == "Laura Atención"
    assert [e["tipo"] for e in lead["eventos"]] == ["recibido", "seguir"]


@pytest.mark.parametrize(
    "override", [{"phone": "12"}, {"fuente": "whatsapp"}, {"full_name": " "}, {"email": "nope"}]
)
def test_create_validation(client, atencion, as_user, override):
    body = {"full_name": "A", "phone": "3005550000", "fuente": "facebook"} | override
    assert client.post(LEADS, json=body, headers=as_user(atencion)).status_code == 422


def test_update_requires_ownership(client, db, atencion, preventas, make_lead, as_user):
    lead = make_lead()
    url = f"{LEADS}/{lead.id}"
    # Unassigned: has to follow first.
    res = client.patch(url, json={"zona": "Belén"}, headers=as_user(atencion))
    assert res.status_code == 403
    assert "Seguir lead" in res.json()["detail"]

    lead_service.follow_lead(db, lead, atencion)
    res = client.patch(url, json={"zona": "Belén"}, headers=as_user(atencion))
    assert res.status_code == 200
    assert res.json()["zona"] == "Belén"
    assert res.json()["eventos"][-1]["tipo"] == "datos"


def test_delete_only_managers(client, db, atencion, coord, make_lead, as_user):
    lead = make_lead()
    lead_service.follow_lead(db, lead, atencion)
    assert client.delete(f"{LEADS}/{lead.id}", headers=as_user(atencion)).status_code == 403
    assert client.delete(f"{LEADS}/{lead.id}", headers=as_user(coord)).status_code == 204
    assert client.get(f"{LEADS}/{lead.id}", headers=as_user(coord)).status_code == 404


# ---------------------------------------------------------------- seguir / reasignar


def test_follow_is_exclusive(client, atencion, preventas, make_lead, as_user):
    lead = make_lead()
    res = client.post(f"{LEADS}/{lead.id}/follow", headers=as_user(atencion))
    assert res.status_code == 200
    assert res.json()["can_edit"] is True

    # Pre-ventas can no longer see it (it isn't unassigned anymore).
    assert client.post(f"{LEADS}/{lead.id}/follow", headers=as_user(preventas)).status_code == 404


def test_follow_conflict_message_for_managers_view(client, db, atencion, preventas, make_lead):
    lead = make_lead()
    lead_service.follow_lead(db, lead, atencion)
    with pytest.raises(lead_service.ConflictError, match="Lo sigue Laura Atención"):
        lead_service.follow_lead(db, lead, preventas)


def test_only_managers_reassign(client, db, atencion, preventas, coord, make_lead, as_user):
    lead = make_lead()
    lead_service.follow_lead(db, lead, atencion)
    body = {"assigned_to_id": str(preventas.id)}
    assert (
        client.patch(f"{LEADS}/{lead.id}", json=body, headers=as_user(atencion)).status_code == 403
    )

    res = client.patch(f"{LEADS}/{lead.id}", json=body, headers=as_user(coord))
    assert res.status_code == 200
    assert res.json()["assigned_to"]["full_name"] == "Pablo Preventa"
    assert res.json()["eventos"][-1]["titulo"] == "Reasignado a Pablo Preventa"


def test_cannot_reassign_to_asesor(client, coord, make_user, make_lead, as_user):
    asesor = make_user(email="a@example.com", actividades=[A.VENTAS])
    lead = make_lead()
    res = client.patch(
        f"{LEADS}/{lead.id}", json={"assigned_to_id": str(asesor.id)}, headers=as_user(coord)
    )
    assert res.status_code == 422


# ---------------------------------------------------------------- actions & follow-ups


@pytest.fixture
def my_lead(db, atencion, make_lead):
    lead = make_lead()
    lead_service.follow_lead(db, lead, atencion)
    return lead


def test_call_moves_lead_to_en_gestion(client, atencion, my_lead, as_user):
    url = f"{LEADS}/{my_lead.id}/actions"
    res = client.post(
        url, json={"tipo": "llamada", "resultado": "no_contesto"}, headers=as_user(atencion)
    )
    assert res.status_code == 200
    lead = res.json()
    assert lead["etapa"] == "en_gestion"
    assert lead["llamadas"] == 1
    assert lead["eventos"][-1]["titulo"] == "Llamada · no contestó"
    assert lead["eventos"][-1]["detalle"] == "Intento 1."


def test_answered_call_needs_summary(client, atencion, my_lead, as_user):
    url = f"{LEADS}/{my_lead.id}/actions"
    h = as_user(atencion)
    assert (
        client.post(url, json={"tipo": "llamada", "resultado": "contesto"}, headers=h).status_code
        == 422
    )
    body = {
        "tipo": "llamada",
        "resultado": "contesto",
        "resumen": "Busca 2 habitaciones",
        "duracion_min": 6,
    }
    res = client.post(url, json=body, headers=h)
    assert res.json()["eventos"][-1]["titulo"] == "Llamada · contestó · 6 min"


@pytest.mark.parametrize(
    ("body", "titulo"),
    [
        ({"tipo": "mensaje", "medio": "whatsapp", "texto": "Hola"}, "Mensaje enviado · WhatsApp"),
        ({"tipo": "opciones", "medio": "correo", "texto": "3 aptos"}, "Opciones enviadas · Correo"),
        ({"tipo": "observacion", "texto": "Prefiere tardes"}, "Observación"),
    ],
)
def test_other_actions(client, atencion, my_lead, as_user, body, titulo):
    res = client.post(f"{LEADS}/{my_lead.id}/actions", json=body, headers=as_user(atencion))
    assert res.status_code == 200
    assert res.json()["eventos"][-1]["titulo"] == titulo


def test_followup_flow(client, atencion, my_lead, as_user):
    h = as_user(atencion)
    body = {"accion": "llamar", "due_at": future(2), "nota": "Confirmar si le gustó alguna opción"}
    res = client.post(f"{LEADS}/{my_lead.id}/followups", json=body, headers=h)
    assert res.status_code == 201
    lead = res.json()
    assert lead["etapa"] == "seguimiento"
    seg = lead["proximo_seguimiento"]
    assert seg["accion"] == "llamar"

    done = client.post(
        f"{LEADS}/{my_lead.id}/followups/{seg['id']}/complete",
        json={"resultado": "Le gustó el de Laureles"},
        headers=h,
    ).json()
    assert done["proximo_seguimiento"] is None
    assert done["etapa"] == "en_gestion"
    assert done["eventos"][-1]["titulo"] == "Seguimiento realizado · Llamar"


def test_followup_in_the_past_rejected(client, atencion, my_lead, as_user):
    body = {"accion": "llamar", "due_at": future(-3)}
    res = client.post(f"{LEADS}/{my_lead.id}/followups", json=body, headers=as_user(atencion))
    assert res.status_code == 422


# ---------------------------------------------------------------- stage / perdido / ganado


def test_lost_requires_reason_and_closes(client, atencion, my_lead, as_user):
    url = f"{LEADS}/{my_lead.id}/stage"
    h = as_user(atencion)
    assert client.post(url, json={"etapa": "perdido"}, headers=h).status_code == 422

    res = client.post(url, json={"etapa": "perdido", "motivo": "presupuesto"}, headers=h)
    lead = res.json()
    assert lead["etapa"] == "perdido"
    assert lead["perdida_descuenta"] is True
    assert lead["cerrado_at"] is not None

    # Closed: no more actions, and the owner can't reopen it.
    act = client.post(
        f"{LEADS}/{my_lead.id}/actions", json={"tipo": "observacion", "texto": "x"}, headers=h
    )
    assert act.status_code == 422
    assert client.post(url, json={"etapa": "en_gestion"}, headers=h).status_code == 403


def test_wrong_number_never_costs_points(client, atencion, my_lead, as_user):
    res = client.post(
        f"{LEADS}/{my_lead.id}/stage",
        json={"etapa": "perdido", "motivo": "numero_equivocado"},
        headers=as_user(atencion),
    )
    assert res.json()["perdida_descuenta"] is False


def test_no_contesta_penalty_depends_on_3_calls_in_3_days(db, atencion, my_lead):
    def add_call(days_ago: int):
        db.add(
            LeadEvento(
                lead_id=my_lead.id,
                tipo=TipoEventoLead.LLAMADA,
                titulo="Llamada · no contestó",
                datos={"resultado": "no_contesto"},
                created_by_id=atencion.id,
                created_at=datetime.now(UTC) - timedelta(days=days_ago),
            )
        )
        db.flush()

    add_call(2)
    add_call(1)
    stats = lead_service.call_stats(db, my_lead)
    assert (stats.llamadas, stats.dias_seguidos) == (2, 2)
    assert lead_service.perdida_descuenta(MotivoPerdida.NO_CONTESTA, stats) is True

    add_call(0)
    stats = lead_service.call_stats(db, my_lead)
    assert (stats.llamadas, stats.dias_seguidos) == (3, 3)
    assert lead_service.perdida_descuenta(MotivoPerdida.NO_CONTESTA, stats) is False
    assert lead_service.perdida_descuenta(MotivoPerdida.NO_INTERESADO, stats) is True


def test_ganado_and_reopen_only_managers(client, atencion, coord, my_lead, as_user):
    url = f"{LEADS}/{my_lead.id}/stage"
    assert client.post(url, json={"etapa": "ganado"}, headers=as_user(atencion)).status_code == 403
    assert (
        client.post(url, json={"etapa": "ganado"}, headers=as_user(coord)).json()["etapa"]
        == "ganado"
    )
    reopened = client.post(url, json={"etapa": "en_gestion"}, headers=as_user(coord)).json()
    assert reopened["etapa"] == "en_gestion"
    assert reopened["cerrado_at"] is None


def test_cita_programada_cannot_be_set_by_hand(client, atencion, my_lead, as_user):
    res = client.post(
        f"{LEADS}/{my_lead.id}/stage", json={"etapa": "cita_programada"}, headers=as_user(atencion)
    )
    assert res.status_code == 422


# ---------------------------------------------------------------- filters & stats


def test_filters(client, db, atencion, coord, make_lead, as_user):
    a = make_lead(full_name="Ana Gómez", fuente=FuenteLead.PROPPI)
    b = make_lead(full_name="Bruno Díaz")
    lead_service.follow_lead(db, b, atencion)
    lead_service.change_stage(
        db, b, EtapaLead.PERDIDO, motivo=MotivoPerdida.NO_INTERESADO, actor=atencion
    )
    h = as_user(coord)

    def names(**params):
        return {x["full_name"] for x in client.get(LEADS, params=params, headers=h).json()}

    assert names(etapa="perdido") == {"Bruno Díaz"}
    assert names(etapa=["nuevo", "perdido"]) == {"Ana Gómez", "Bruno Díaz"}
    assert names(abiertos=True) == {"Ana Gómez"}
    assert names(assigned="none") == {"Ana Gómez"}
    assert names(assigned=str(atencion.id)) == {"Bruno Díaz"}
    assert names(fuente="proppi") == {"Ana Gómez"}
    assert names(q="gómez") == {"Ana Gómez"}
    assert names(q=a.code) == {"Ana Gómez"}
    today = datetime.now(UTC).astimezone(lead_service.fechas.BOGOTA).date()
    assert names(desde=today.isoformat(), hasta=today.isoformat()) == {"Ana Gómez", "Bruno Díaz"}
    assert names(hasta=(today - timedelta(days=1)).isoformat()) == set()


def test_stats(client, atencion, my_lead, make_lead, as_user):
    make_lead()
    h = as_user(atencion)
    client.post(
        f"{LEADS}/{my_lead.id}/actions",
        json={"tipo": "llamada", "resultado": "contesto", "resumen": "ok"},
        headers=h,
    )
    s = client.get(f"{LEADS}/stats", params={"periodo": "hoy"}, headers=h).json()
    assert s["recibidos"] == 2
    assert s["sin_responsable"] == 1
    assert s["seguidos"] == 1
    assert (s["llamadas"], s["llamadas_contestadas"]) == (1, 1)
    assert client.get(f"{LEADS}/stats", params={"periodo": "año"}, headers=h).status_code == 422
