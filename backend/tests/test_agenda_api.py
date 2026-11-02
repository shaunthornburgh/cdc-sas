"""Agenda (G09, M17 / C07 / X06, K19; G-088, G-089, G-090)."""

from datetime import datetime, timedelta

import pytest

from app.models import Cita, Lead, Pedido, Seguimiento
from app.models.enums import (
    AccionSeguimiento,
    Cargo,
    EstadoCita,
    FuenteLead,
    FuncionIndependiente,
    TipoCita,
    TipoInmueble,
    TipoNegocio,
)
from app.models.enums import ActividadComercial as A
from app.services import fechas
from tests.conftest import auth_header, login

AG = "/api/v1/agenda"
AV = "/api/v1/avisos"
# Saturday 3 oct 2026, 11:00 a. m. in Bogotá
NOW = datetime(2026, 10, 3, 11, 0, tzinfo=fechas.BOGOTA)
HOY = "2026-10-03"
MANANA = "2026-10-04"


@pytest.fixture(autouse=True)
def reloj(monkeypatch):
    monkeypatch.setattr(fechas, "now", lambda: NOW)


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Vale Aux"
        ),
        "juan": make_user(
            email="juan@example.com", full_name="Juan Asesor", actividades=[A.VENTAS]
        ),
        "ana": make_user(
            email="ana@example.com", full_name="Ana Asesora", actividades=[A.CAPTACION]
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


def agregar(
    client, H, who, para=None, titulo="Llamar al propietario de INM-0350", fecha=MANANA, **kw
):
    body = {"titulo": titulo, "fecha": fecha} | kw
    if para is not None:
        body["para_id"] = str(para.id)
    return client.post(AG, json=body, headers=H(who))


def vista(client, H, who, target=None, **q):
    params = {"desde": HOY, "hasta": "2026-10-09"} | q
    if target is not None:
        params["user_id"] = str(target.id)
    return client.get(AG, params=params, headers=H(who))


# ---------------------------------------------------------------- who sees / adds (G-088)


def test_visibility(client, p, H):
    def nombres(who):
        return [x["full_name"] for x in ok(client.get(f"{AG}/personas", headers=H(who)))]

    # Coordinación: its own and its team (asesores, Atención)
    assert nombres(p["coord"]) == ["Mateo Coord", "Ana Asesora", "Juan Asesor", "Laura Atención"]
    # Gerencia and the Auxiliar: everyone
    assert len(nombres(p["ger"])) == 6 and len(nombres(p["aux"])) == 6
    # Asesores and Atención: only their own
    assert nombres(p["juan"]) == ["Juan Asesor"] and nombres(p["laura"]) == ["Laura Atención"]
    assert vista(client, H, p["juan"], p["ana"]).status_code == 404
    assert vista(client, H, p["coord"], p["aux"]).status_code == 404
    assert ok(vista(client, H, p["aux"], p["ger"]))["persona"]["puede_agregar"] is False
    assert ok(vista(client, H, p["ger"], p["aux"]))["persona"]["puede_agregar"] is True


def test_who_adds_where(client, p, H):
    assert agregar(client, H, p["coord"], p["juan"]).status_code == 201
    assert agregar(client, H, p["coord"], p["laura"]).status_code == 201
    assert agregar(client, H, p["coord"], p["aux"]).status_code == 403
    assert agregar(client, H, p["aux"], p["coord"]).status_code == 201
    assert agregar(client, H, p["aux"], p["ger"]).status_code == 403
    assert agregar(client, H, p["ger"], p["aux"]).status_code == 201
    assert agregar(client, H, p["juan"], p["ana"]).status_code == 403  # between asesores, nothing
    assert agregar(client, H, p["juan"], fecha="2026-10-02").status_code == 422
    assert agregar(client, H, p["juan"], titulo="").status_code == 422


# ---------------------------------------------------------------- assigned by someone else


def test_assigned_activity_flow(client, p, H):
    it = ok(agregar(client, H, p["coord"], p["juan"], prioridad="alta", nota="Llevar el acta"), 201)
    assert (it["tipo"], it["por_name"], it["por_yo"]) == ("asg", "Mateo Coord", True)
    # Juan's view: «Asignada por Mateo Coord (Coordinación) · prioridad alta»
    mine = [x for x in ok(vista(client, H, p["juan"]))["items"] if x["id"] == it["id"]][0]
    assert mine["sub"] == "Asignada por Mateo Coord (Coordinación) · prioridad alta"
    assert mine["acciones"] == {
        "hecha": True,
        "rechazar": True,
        "justificar": True,
        "eliminar": False,
    }
    # It reaches Juan's bell
    av = ok(client.get(AV, headers=H(p["juan"])))["items"]
    assert [a["tipo"] for a in av] == ["agenda_asignada"] and "Mateo Coord te asignó" in av[0][
        "titulo"
    ]
    # He can't delete it; he rejects it with a reason
    assert client.delete(f"{AG}/{it['id']}", headers=H(p["juan"])).status_code == 403
    url = f"{AG}/{it['id']}/rechazar"
    assert client.post(url, json={"motivo": ""}, headers=H(p["juan"])).status_code == 422
    r = ok(client.post(url, json={"motivo": "Tengo permiso ese día"}, headers=H(p["juan"])))
    assert (r["estado"], r["estado_txt"], r["motivo"]) == (
        "rechazada",
        "Rechazada",
        "Tengo permiso ese día",
    )
    assert client.post(f"{AG}/{it['id']}/hecha", headers=H(p["juan"])).status_code == 403
    # Juan's aviso closed on its own; Mateo got the answer in «Resumen del día»
    assert ok(client.get(AV, headers=H(p["juan"])))["items"] == []
    res = ok(client.get(AV, params={"vista": "resumen"}, headers=H(p["coord"])))["items"]
    assert res[0]["titulo"] == "Juan Asesor rechazó «Llamar al propietario de INM-0350»"
    assert res[0]["detalle"] == "Motivo: Tengo permiso ese día"
    # Mateo deletes what he put: it goes to «Actividades eliminadas»
    assert client.delete(f"{AG}/{it['id']}", headers=H(p["coord"])).status_code == 204
    v = ok(vista(client, H, p["juan"]))
    assert v["items"] == []
    assert (v["eliminadas"][0]["eliminada_por"], v["eliminadas"][0]["por_name"]) == (
        "Mateo Coord",
        "Mateo Coord",
    )


def test_justify_and_done(client, p, H):
    a = ok(agregar(client, H, p["aux"], p["laura"]), 201)
    j = ok(
        client.post(
            f"{AG}/{a['id']}/justificar", json={"motivo": "Lo hizo Pablo"}, headers=H(p["laura"])
        )
    )
    assert j["estado"] == "justificada"
    b = ok(agregar(client, H, p["aux"], p["laura"], titulo="Archivar respuestas"), 201)
    h = ok(client.post(f"{AG}/{b['id']}/hecha", headers=H(p["laura"])))
    assert (h["estado_txt"], h["acciones"]["hecha"]) == ("✓ Hecha", False)
    titulos = [
        x["titulo"]
        for x in ok(client.get(AV, params={"vista": "resumen"}, headers=H(p["aux"])))["items"]
    ]
    assert "Laura Atención marcó hecha «Archivar respuestas»" in titulos
    # Only the owner of the agenda answers: Coordinación (who can see it) can't
    c = ok(agregar(client, H, p["coord"], p["laura"], titulo="Otra cosa"), 201)
    assert client.post(f"{AG}/{c['id']}/hecha", headers=H(p["coord"])).status_code == 403


def test_own_activity_and_late(client, p, H):
    mia = ok(agregar(client, H, p["juan"], fecha=HOY, hora="08:00"), 201)
    # 8:00 already passed at 11:00: «Atrasada» (G-090)
    assert (mia["tipo"], mia["estado"], mia["estado_txt"]) == ("mia", "atrasada", "Atrasada")
    assert mia["acciones"] == {
        "hecha": True,
        "rechazar": False,
        "justificar": False,
        "eliminar": True,
    }
    assert (
        client.post(
            f"{AG}/{mia['id']}/rechazar", json={"motivo": "xxx"}, headers=H(p["juan"])
        ).status_code
        == 409
    )
    ok(client.post(f"{AG}/{mia['id']}/hecha", headers=H(p["juan"])))
    assert client.delete(f"{AG}/{mia['id']}", headers=H(p["juan"])).status_code == 204
    # Doesn't count in anyone's bell (nobody else put it)
    assert ok(client.get(AV, headers=H(p["juan"])))["items"] == []


# ---------------------------------------------------------------- system items


def test_system_items(client, p, H, db):
    lead = Lead(
        full_name="Cliente Ejemplo 4",
        phone="3001112233",
        fuente=FuenteLead.OTRO,
        assigned_to_id=p["laura"].id,
    )
    db.add(lead)
    db.flush()
    db.add_all(
        [
            Cita(
                lead_id=lead.id,
                tipo=TipoCita.VISITA_VENTA,
                scheduled_at=NOW + timedelta(hours=5),
                asesor_id=p["juan"].id,
                estado=EstadoCita.ACEPTADA,
                inmueble="INM-0290",
            ),
            Cita(
                lead_id=lead.id,
                tipo=TipoCita.INVENTARIO,
                scheduled_at=NOW + timedelta(days=2),
                asesor_id=p["juan"].id,
                estado=EstadoCita.PENDIENTE,
            ),
            Seguimiento(
                lead_id=lead.id, accion=AccionSeguimiento.LLAMAR, due_at=NOW + timedelta(hours=2)
            ),
            Pedido(
                cliente_nombre="Cliente Ejemplo 5",
                negocio=TipoNegocio.ARRIENDO,
                tipo_inmueble=TipoInmueble.APARTAMENTO,
                zona="Laureles",
                presupuesto=2_000_000,
                fecha_limite=NOW + timedelta(hours=6),
                responsable_id=p["juan"].id,
            ),
        ]
    )
    db.flush()
    juan = ok(vista(client, H, p["juan"]))["items"]
    assert [(x["tipo"], x["estado_txt"]) for x in juan] == [
        ("cita", "Aceptada"),
        ("ped", "Vence hoy"),
        ("ctl", "Por aceptar"),
    ]
    assert juan[0]["link"] == "/mis-citas" and juan[0]["hora_txt"] == "4:00 p. m."
    # Coordinación sees them read-only: no «Abrir»
    assert all(x["link"] is None for x in ok(vista(client, H, p["coord"], p["juan"]))["items"])
    # Atención: the citas of its leads and its seguimientos
    laura = ok(vista(client, H, p["laura"]))["items"]
    assert [x["tipo"] for x in laura] == ["seg", "cita", "ctl"]
    assert laura[0]["titulo"] == "Seguimiento · Llamar · Cliente Ejemplo 4"
    assert "Juan Asesor" in laura[1]["sub"]


def test_range_limits(client, p, H):
    assert vista(client, H, p["juan"], desde="2026-10-09", hasta="2026-10-03").status_code == 422
    assert vista(client, H, p["juan"], desde="2026-10-01", hasta="2026-12-31").status_code == 422
    v = ok(client.get(AG, headers=H(p["juan"])))
    assert (v["desde"], v["hasta"]) == (HOY, "2026-10-09")  # 7 days from today
