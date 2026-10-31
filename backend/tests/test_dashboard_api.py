from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import (
    AccionSeguimiento,
    Cargo,
    EstadoCaptacion,
    EstadoCita,
    EtapaLead,
    FuenteLead,
    FuncionIndependiente,
    MotivoPerdida,
    MotivoRechazoCaptacion,
    ResultadoLlamada,
    TipoCita,
)
from app.models.enums import ActividadComercial as A
from app.services import captaciones as caps
from app.services import citas, leads
from tests.conftest import auth_header, login

DASH = "/api/v1/dashboard"


def now():
    return datetime.now(UTC)


@pytest.fixture
def people(make_user):
    return {
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "laura": make_user(
            Cargo.ATENCION_CLIENTE, email="laura@example.com", full_name="Laura Atención"
        ),
        "pablo": make_user(
            Cargo.ASESOR,
            email="pablo@example.com",
            full_name="Pablo Preventa",
            funcion=FuncionIndependiente.PRE_VENTAS,
        ),
        "juan": make_user(
            email="juan@example.com",
            full_name="Juan Asesor",
            actividades=[A.CAPTACION, A.VENTAS, A.ARRIENDOS],
        ),
        "carla": make_user(
            email="carla@example.com", full_name="Carla Arriendos", actividades=[A.ARRIENDOS]
        ),
    }


@pytest.fixture
def data(db, people):
    p = people
    mk = lambda name, **kw: leads.create_lead(  # noqa: E731
        db,
        {
            "full_name": name,
            "phone": "3005550100",
            "fuente": FuenteLead.FACEBOOK,
            "negocio": "arriendo",
        }
        | kw,
        actor=None,
    )
    # Two unassigned leads, one waiting > 15 min.
    old = mk("Viejo sin responsable")
    old.created_at = now() - timedelta(minutes=40)
    mk("Recién llegado", negocio="venta")

    # Laura's leads: one with an overdue follow-up, one with a call answered.
    a = mk("Con seguimiento")
    leads.follow_lead(db, a, p["laura"])
    seg = leads.programar_seguimiento(
        db,
        a,
        accion=AccionSeguimiento.LLAMAR,
        due_at=now() + timedelta(minutes=1),
        nota=None,
        actor=p["laura"],
    )
    seg.due_at = now() - timedelta(hours=2)  # overdue
    b = mk("Con llamada")
    leads.follow_lead(db, b, p["laura"])
    leads.registrar_llamada(
        db, b, resultado=ResultadoLlamada.CONTESTO, resumen="ok", duracion_min=3, actor=p["laura"]
    )

    # Pablo: a cita pending within the hour (needs action) + a lost lead this month.
    c = mk("Cita urgente")
    leads.follow_lead(db, c, p["pablo"])
    urgent = citas.create_cita(
        db,
        c,
        tipo=TipoCita.VISITA_ARRIENDO,
        scheduled_at=now() + timedelta(minutes=30),
        asesor_id=p["carla"].id,
        inmueble=None,
        notas=None,
        actor=p["pablo"],
    )
    d = mk("Perdido")
    leads.follow_lead(db, d, p["pablo"])
    leads.change_stage(db, d, EtapaLead.PERDIDO, motivo=MotivoPerdida.PRESUPUESTO, actor=p["pablo"])

    # Laura: a cita rejected by Juan, and one accepted later today... tomorrow to be safe.
    e = mk("Cita rechazada")
    leads.follow_lead(db, e, p["laura"])
    rej = citas.create_cita(
        db,
        e,
        tipo=TipoCita.VISITA_VENTA,
        scheduled_at=now() + timedelta(days=1),
        asesor_id=p["juan"].id,
        inmueble=None,
        notas=None,
        actor=p["laura"],
    )
    citas.set_estado(db, rej, EstadoCita.RECHAZADA, motivo="Choque", actor=p["coord"])

    # Captaciones (Juan): 2 por verificar, 1 aprobada (venta), 1 rechazada.
    def cap(code, negocio="venta"):
        return caps.create_captacion(
            db,
            {
                "modo": "rapido",
                "negocio": negocio,
                "codigo_inmueble": code,
                "direccion": f"Calle {code} 10",
            },
            actor=p["juan"],
        )

    cap("INM-1")
    cap("INM-2")
    caps.verificar(
        db, cap("INM-3"), EstadoCaptacion.APROBADA, motivo=None, observacion=None, actor=p["coord"]
    )
    caps.verificar(
        db,
        cap("INM-4", "arriendo"),
        EstadoCaptacion.RECHAZADA,
        motivo=MotivoRechazoCaptacion.CODIGO_INEXISTENTE,
        observacion=None,
        actor=p["coord"],
    )
    db.flush()
    return {"urgent": urgent, "rejected": rej}


@pytest.fixture
def h(client, people):
    return auth_header(login(client, "coord@example.com")["access_token"])


# ---------------------------------------------------------------- access


@pytest.mark.parametrize(
    ("cargo", "kwargs"),
    [
        (Cargo.ASESOR, {"actividades": [A.CAPTACION]}),
        (Cargo.ATENCION_CLIENTE, {}),
        (Cargo.AUXILIAR_ADMINISTRATIVA, {}),
    ],
)
def test_only_managers(client, make_user, cargo, kwargs):
    make_user(cargo, email="x@example.com", **kwargs)
    hx = auth_header(login(client, "x@example.com")["access_token"])
    for path in ("/coordinacion", "/leads", "/citas", "/captaciones", "/equipo"):
        assert client.get(DASH + path, headers=hx).status_code == 403


def test_gerencia_has_access(client, make_user):
    make_user(Cargo.GERENCIA, email="g@example.com")
    hg = auth_header(login(client, "g@example.com")["access_token"])
    assert client.get(f"{DASH}/coordinacion", headers=hg).status_code == 200


def test_empty_database(client, h):
    d = client.get(f"{DASH}/coordinacion", headers=h).json()
    assert d["leads"]["abiertos"] == 0
    assert d["citas"]["requieren_accion"] == 0
    assert d["captaciones"]["aprobacion_pct"] is None
    # No lead / cita / captación alerts (people haven't done today's preoperacional yet).
    assert [a for a in d["alertas"] if "preoperacional" not in a["titulo"]] == []


# ---------------------------------------------------------------- sections


def test_leads_summary(client, h, data):
    s = client.get(f"{DASH}/leads", headers=h).json()
    assert s["sin_responsable"] == 2
    assert s["sin_responsable_alerta"] == 1
    assert s["nuevos_hoy"] == 7
    assert s["seguimientos_vencidos"] == 1
    assert s["por_etapa"]["perdido"] == 1 and s["perdidos_mes"] == 1
    assert s["perdidos_con_descuento_mes"] == 1
    assert s["por_etapa"]["cita_programada"] == 2
    assert s["abiertos"] == 6
    assert s["abiertos_por_negocio"] == {"arriendo": 5, "venta": 1}


def test_citas_summary(client, h, data):
    s = client.get(f"{DASH}/citas", headers=h).json()
    assert (s["pendientes"], s["pendientes_menos_1h"], s["rechazadas"]) == (1, 1, 1)
    assert s["requieren_accion"] == 2
    assert [c["code"] for c in s["lista_accion"]] == [data["urgent"].code, data["rejected"].code]
    assert s["lista_accion"][0]["lead_name"] == "Cita urgente"


def test_captaciones_summary(client, h, data):
    s = client.get(f"{DASH}/captaciones", headers=h).json()
    assert s["counts"] == {"por_verificar": 2, "aprobada": 1, "rechazada": 1}
    assert s["aprobacion_pct"] == 50
    assert (s["registradas_mes"], s["aprobadas_mes"], s["rechazadas_mes"]) == (4, 1, 1)
    assert s["sin_publicar"] == 1
    assert [c["codigo_inmueble"] for c in s["lista_por_verificar"]] == ["INM-1", "INM-2"]


def test_equipo(client, h, data):
    s = client.get(f"{DASH}/equipo", headers=h).json()
    assert (s["asesores_activos"], s["atencion_activos"], s["con_captacion"]) == (2, 2, 1)

    asesores = {a["full_name"]: a for a in s["asesores"]}
    carla, juan = asesores["Carla Arriendos"], asesores["Juan Asesor"]
    assert (
        carla["citas_sin_aceptar"],
        carla["cita_sin_aceptar_code"],
        carla["cita_sin_aceptar_urgente"],
    ) == (1, data["urgent"].code, True)
    assert carla["captaciones_venta_mes"] is None  # no Captación → «no aplica»
    assert (juan["captaciones_venta_mes"], juan["captaciones_arriendo_mes"]) == (1, 0)
    assert (juan["captaciones_por_verificar"], juan["captaciones_rechazadas"]) == (2, 1)

    atencion = {a["full_name"]: a for a in s["atencion"]}
    laura, pablo = atencion["Laura Atención"], atencion["Pablo Preventa"]
    assert laura["leads_seguidos_mes"] == 3
    assert (laura["llamadas_mes"], laura["llamadas_contestadas_mes"]) == (1, 1)
    assert laura["seguimientos_vencidos"] == 1
    assert (laura["seguimientos_mes"], laura["seguimientos_a_tiempo_mes"]) == (1, 0)
    assert laura["citas_programadas_mes"] == 1 and laura["citas_requieren_accion"] == 1
    assert (pablo["perdidos_mes"], pablo["citas_requieren_accion"]) == (1, 1)
    assert laura["primera_respuesta_min"] is not None


def test_alerts_most_urgent_first(client, h, data):
    alerts = client.get(f"{DASH}/coordinacion", headers=h).json()["alertas"]
    assert alerts[0]["nivel"] == "bad" and "sin aceptar" in alerts[0]["titulo"]
    titles = " | ".join(a["titulo"] for a in alerts)
    assert "rechazó la cita" in titles
    assert "1 lead lleva más de 15 min sin responsable" in titles
    assert "1 seguimiento vencido" in titles
    assert "2 captaciones por verificar" in titles
    assert all(a["link"].startswith("/") and a["que_hacer"] for a in alerts)
