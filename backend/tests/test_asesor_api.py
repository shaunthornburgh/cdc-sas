from datetime import UTC, datetime, timedelta

import pytest

from app.models import Cita
from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, EstadoCaptacion, FuenteLead, MotivoRechazoCaptacion, TipoCita
from app.services import captaciones as caps
from app.services import citas, leads
from tests.conftest import auth_header, login

BASE = "/api/v1/asesor"


@pytest.fixture
def p(make_user):
    return {
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "laura": make_user(
            Cargo.ATENCION_CLIENTE, email="laura@example.com", full_name="Laura Atención"
        ),
        "juan": make_user(
            email="juan@example.com", full_name="Juan Asesor", actividades=[A.CAPTACION, A.VENTAS]
        ),
        "ana": make_user(email="ana@example.com", full_name="Ana Ventas", actividades=[A.VENTAS]),
        "carla": make_user(
            email="carla@example.com", full_name="Carla Arriendos", actividades=[A.ARRIENDOS]
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


@pytest.fixture
def cita_juan(db, p):
    lead = leads.create_lead(
        db,
        {"full_name": "Cliente Venta", "phone": "3005550100", "fuente": FuenteLead.PROPPI},
        actor=None,
    )
    leads.follow_lead(db, lead, p["laura"])
    return citas.create_cita(
        db,
        lead,
        tipo=TipoCita.VISITA_VENTA,
        scheduled_at=datetime.now(UTC) + timedelta(days=1),
        asesor_id=p["juan"].id,
        inmueble="INM-0290",
        notas="Llega en carro",
        actor=p["laura"],
    )


# ---------------------------------------------------------------- access


def test_access(client, p, H):
    assert client.get(f"{BASE}/inicio", headers=H(p["laura"])).status_code == 403
    assert client.get(f"{BASE}/inicio", headers=H(p["juan"])).status_code == 200
    # Managers: must pick an asesor; can view one; asesores can't view others.
    assert client.get(f"{BASE}/inicio", headers=H(p["coord"])).status_code == 422
    assert (
        client.get(
            f"{BASE}/inicio", params={"asesor_id": str(p["juan"].id)}, headers=H(p["coord"])
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"{BASE}/inicio", params={"asesor_id": str(p["laura"].id)}, headers=H(p["coord"])
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"{BASE}/inicio", params={"asesor_id": str(p["ana"].id)}, headers=H(p["juan"])
        ).status_code
        == 403
    )


def test_auxiliar_forbidden(client, make_user):
    make_user(Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com")
    h = auth_header(login(client, "aux@example.com")["access_token"])
    assert client.get(f"{BASE}/inicio", headers=h).status_code == 403
    assert client.get(f"{BASE}/citas", headers=h).status_code == 403


# ---------------------------------------------------------------- inicio


def test_inicio_content(client, db, p, H, cita_juan):
    def cap(code):
        return caps.create_captacion(
            db,
            {
                "modo": "rapido",
                "negocio": "venta",
                "codigo_inmueble": code,
                "direccion": f"Calle {code} 1",
            },
            actor=p["juan"],
        )

    caps.verificar(
        db,
        cap("INM-1"),
        EstadoCaptacion.RECHAZADA,
        motivo=MotivoRechazoCaptacion.CODIGO_INEXISTENTE,
        observacion=None,
        actor=p["coord"],
    )
    caps.verificar(
        db, cap("INM-2"), EstadoCaptacion.APROBADA, motivo=None, observacion=None, actor=p["coord"]
    )
    cap("INM-3")
    db.flush()

    d = client.get(f"{BASE}/inicio", headers=H(p["juan"])).json()
    assert d["asesor"]["actividades"] == ["captacion", "ventas"]
    chips = [(x["chip"], x["titulo"]) for x in d["pendientes"]]
    assert chips[0] == ("Aceptar", "Cita pendiente de aceptación")
    assert any(c == "Corregir" and t.endswith("rechazada") for c, t in chips)
    assert any(c == "Publicar" for c, _ in chips)
    assert "te la asignó Laura Atención" in d["pendientes"][0]["detalle"]
    assert d["captaciones"]["counts"] == {"por_verificar": 1, "aprobada": 1, "rechazada": 1}
    assert set(d["resultados"]) == {"captacion", "ventas"}  # only active activities
    assert d["resultados"]["ventas"]["por_responder"] == 1
    assert d["citas_counts"]["responder"] == 1


def test_no_captacion_means_no_captaciones_block(client, p, H):
    d = client.get(f"{BASE}/inicio", headers=H(p["carla"])).json()
    assert d["captaciones"] is None
    assert set(d["resultados"]) == {"arriendos"}


# ---------------------------------------------------------------- answering citas


def test_accept(client, p, H, cita_juan):
    url = f"{BASE}/citas/{cita_juan.id}/aceptar"
    assert client.post(url, headers=H(p["ana"])).status_code == 403  # not hers
    assert client.post(url, headers=H(p["laura"])).status_code == 403  # not an asesor
    res = client.post(url, headers=H(p["juan"])).json()
    assert res["estado"] == "aceptada" and res["mia"]
    assert client.post(url, headers=H(p["juan"])).status_code == 422
    lists = client.get(f"{BASE}/citas", headers=H(p["juan"])).json()
    assert [c["code"] for c in lists["proximas"]] == [cita_juan.code]


def test_reject_then_another_asesor_takes_it(client, p, H, cita_juan):
    url = f"{BASE}/citas/{cita_juan.id}"
    assert (
        client.post(
            f"{url}/rechazar",
            json={"motivo": "Porque sí", "observacion": "x"},
            headers=H(p["juan"]),
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{url}/rechazar",
            json={"motivo": "Choque con otra cita", "observacion": " "},
            headers=H(p["juan"]),
        ).status_code
        == 422
    )
    rej = client.post(
        f"{url}/rechazar",
        json={"motivo": "Choque con otra cita", "observacion": "Tengo otra visita"},
        headers=H(p["juan"]),
    ).json()
    assert rej["estado"] == "rechazada"

    # Ana has Ventas and is free: she is offered it. Carla (Arriendos) is not.
    ana_home = client.get(f"{BASE}/inicio", headers=H(p["ana"])).json()
    assert any(
        x["chip"] == "Tomar" and x["cita_id"] == str(cita_juan.id) for x in ana_home["pendientes"]
    )
    assert not any(
        x["chip"] == "Tomar"
        for x in client.get(f"{BASE}/inicio", headers=H(p["carla"])).json()["pendientes"]
    )

    assert client.post(f"{url}/tomar", headers=H(p["juan"])).status_code == 422  # he rejected it
    assert client.post(f"{url}/tomar", headers=H(p["carla"])).status_code == 422  # no Ventas
    took = client.post(f"{url}/tomar", headers=H(p["ana"])).json()
    assert (took["estado"], took["asesor_name"], took["mia"]) == ("aceptada", "Ana Ventas", True)
    # Nobody else can take it now.
    other = p["juan"]
    assert client.post(f"{url}/tomar", headers=H(other)).status_code in (409, 422)


def test_close_after_the_visit(client, db, p, H, cita_juan):
    url = f"{BASE}/citas/{cita_juan.id}"
    client.post(f"{url}/aceptar", headers=H(p["juan"]))
    assert (
        client.post(
            f"{url}/cerrar", json={"resultado": "Le gustó"}, headers=H(p["juan"])
        ).status_code
        == 422
    )  # not yet
    db.get(Cita, cita_juan.id).scheduled_at = datetime.now(UTC) - timedelta(hours=1)
    db.flush()
    assert client.get(f"{BASE}/citas", headers=H(p["juan"])).json()["counts"]["por_cerrar"] == 1
    res = client.post(
        f"{url}/cerrar", json={"resultado": "Le gustó, quiere oferta"}, headers=H(p["juan"])
    ).json()
    assert res["estado"] == "realizada"
    assert client.get(f"{BASE}/citas", headers=H(p["juan"])).json()["counts"]["cerradas"] == 1


def test_manager_view_is_read_only(client, p, H, cita_juan):
    d = client.get(
        f"{BASE}/citas", params={"asesor_id": str(p["juan"].id)}, headers=H(p["coord"])
    ).json()
    assert d["responder"][0]["code"] == cita_juan.code
    assert (
        client.post(f"{BASE}/citas/{cita_juan.id}/aceptar", headers=H(p["coord"])).status_code
        == 403
    )
