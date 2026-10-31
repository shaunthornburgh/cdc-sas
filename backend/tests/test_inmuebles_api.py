import pytest

from app.models import Lead
from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, FuenteLead, FuncionIndependiente, TipoNegocio
from tests.conftest import auth_header, login
from tests.test_captaciones_api import COMPLETA, rapida

INM = "/api/v1/inmuebles"
CAPS = "/api/v1/captaciones"


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Vale Aux"
        ),
        "bruno": make_user(
            email="bruno@example.com", full_name="Bruno Capta", actividades=[A.CAPTACION]
        ),
        "diego": make_user(
            email="diego@example.com", full_name="Diego Ventas", actividades=[A.VENTAS]
        ),
        "laura": make_user(
            Cargo.ATENCION_CLIENTE,
            email="laura@example.com",
            full_name="Laura Atención",
            funcion=FuncionIndependiente.ATENCION_CLIENTE,
        ),
        "gente": make_user(email="otro@example.com", full_name="Sin Actividades"),
    }


@pytest.fixture
def H(client):
    cache: dict = {}

    def _h(user):
        if user.email not in cache:
            cache[user.email] = auth_header(login(client, user.email)["access_token"])
        return cache[user.email]

    return _h


def body(**kw):
    return {
        "codigo": "inm-0500",
        "negocio": "arriendo",
        "tipo_inmueble": "apartamento",
        "direccion": "Cl 33 # 80-20, Belén",
        "zona": "Belén",
        "precio": 2_200_000,
        "area_m2": "68",
        "habitaciones": 3,
        "banos": 2,
        "propietario_nombre": "Marta Ruiz",
        "propietario_telefono": "300 555 1234",
    } | kw


def crear(client, H, who, **kw):
    res = client.post(INM, json=body(**kw), headers=H(who))
    assert res.status_code == 201, res.text
    return res.json()


def aprobar(client, H, p, data):
    cap = client.post(CAPS, json=data, headers=H(p["bruno"])).json()
    res = client.post(
        f"{CAPS}/{cap['id']}/status", json={"estado": "aprobada"}, headers=H(p["coord"])
    )
    assert res.status_code == 200, res.text
    return cap


# ---------------------------------------------------------------- access


def test_access(client, p, H):
    for k in ("ger", "coord", "aux", "bruno", "diego", "laura"):
        assert client.get(INM, headers=H(p[k])).status_code == 200, k
    assert client.get(INM, headers=H(p["gente"])).status_code == 403  # no function, no activity
    assert client.post(INM, json=body(), headers=H(p["bruno"])).status_code == 403  # via captación
    assert client.post(INM, json=body(), headers=H(p["aux"])).status_code == 403
    assert client.get(f"{INM}/opciones", headers=H(p["coord"])).json()["puede_crear"] is True


# ---------------------------------------------------------------- CRUD


def test_create_validate_update_delete(client, p, H):
    inm = crear(client, H, p["coord"])
    assert (inm["codigo"], inm["titulo"], inm["estado"], inm["faltantes"]) == (
        "INM-0500",
        "Apto Belén",
        "disponible",
        [],
    )
    assert client.post(INM, json=body(codigo="INM-0500 "), headers=H(p["ger"])).status_code == 409
    assert (
        client.post(
            INM, json=body(codigo="INM-0501", zona="Marte"), headers=H(p["ger"])
        ).status_code
        == 422
    )
    assert (
        client.post(INM, json=body(codigo="INM-0502", precio=0), headers=H(p["ger"])).status_code
        == 422
    )

    url = f"{INM}/{inm['id']}"
    upd = client.patch(
        url, json={"precio": 2_400_000, "descripcion": "Con balcón"}, headers=H(p["coord"])
    ).json()
    ev = upd["eventos"][-1]
    assert (
        ev["titulo"] == "Datos actualizados" and "precio: $2.200.000 → $2.400.000" in ev["detalle"]
    )
    assert (
        client.patch(url, json={"precio": 1}, headers=H(p["diego"])).status_code == 403
    )  # not the captador
    # Owner data is hidden from people who don't need it.
    seen = client.get(url, headers=H(p["laura"])).json()
    assert (seen["propietario_nombre"], seen["ve_propietario"]) == (None, False)
    assert client.get(url, headers=H(p["aux"])).json()["propietario_nombre"] == "Marta Ruiz"

    assert client.delete(url, headers=H(p["diego"])).status_code == 403
    assert client.delete(url, headers=H(p["coord"])).status_code == 204
    assert client.get(url, headers=H(p["coord"])).status_code == 404


def test_status_rules(client, p, H):
    inm = crear(client, H, p["coord"])
    url = f"{INM}/{inm['id']}/estado"
    assert (
        client.post(url, json={"estado": "vendido"}, headers=H(p["coord"])).status_code == 422
    )  # it's a rental
    assert (
        client.post(url, json={"estado": "separado"}, headers=H(p["coord"])).status_code == 422
    )  # needs a reason
    assert client.post(url, json={"estado": "arrendado"}, headers=H(p["laura"])).status_code == 403
    sep = client.post(
        url, json={"estado": "separado", "nota": "Separado por Cliente 5"}, headers=H(p["coord"])
    ).json()
    assert (sep["estado_txt"], sep["eventos"][-1]["titulo"]) == (
        "Separado",
        "Disponible → Separado",
    )
    arr = client.post(url, json={"estado": "arrendado"}, headers=H(p["ger"])).json()
    assert arr["estado"] == "arrendado"
    kpis = client.get(INM, headers=H(p["coord"])).json()["kpis"]
    assert (kpis["disponibles"], kpis["cerrados_mes"]) == (0, 1)


# ---------------------------------------------------------------- captaciones → catalog


def test_approved_captacion_creates_property(client, p, H):
    cap = aprobar(client, H, p, COMPLETA)
    items = client.get(INM, headers=H(p["bruno"])).json()["items"]
    inm = next(i for i in items if i["codigo"] == "INM-0370")
    assert (inm["captacion_code"], inm["captador_name"], inm["zona"], inm["precio"]) == (
        cap["code"],
        "Bruno Capta",
        "Laureles",
        2_400_000,
    )
    assert inm["eventos"][0]["titulo"].startswith(f"Registrado desde la captación {cap['code']}")
    # The captador can complete it but not change its status; nobody deletes it.
    url = f"{INM}/{inm['id']}"
    assert client.patch(url, json={"estrato": 4}, headers=H(p["bruno"])).status_code == 200
    assert client.patch(url, json={"negocio": "venta"}, headers=H(p["bruno"])).status_code == 403
    assert client.delete(url, headers=H(p["ger"])).status_code == 409
    mios = client.get(INM, params={"vista": "mios"}, headers=H(p["bruno"])).json()["items"]
    assert [i["codigo"] for i in mios] == ["INM-0370"]


def test_quick_captacion_is_incomplete_and_links_to_existing(client, p, H):
    aprobar(client, H, p, rapida())
    inm = client.get(INM, params={"incompletos": True}, headers=H(p["coord"])).json()["items"][0]
    assert inm["codigo"] == "INM-0360" and "precio" in inm["faltantes"]
    # A property registered by hand gets linked when its captación is approved later.
    manual = crear(client, H, p["coord"], codigo="INM-0380", negocio="venta", precio=450_000_000)
    aprobar(client, H, p, rapida(codigo_inmueble="INM-0380", direccion="Cra 43A # 1-50, Poblado"))
    got = client.get(f"{INM}/{manual['id']}", headers=H(p["coord"])).json()
    assert got["captador_name"] == "Bruno Capta" and got["eventos"][-1]["titulo"].startswith(
        "Vinculado a la captación"
    )
    # A pending captación blocks registering the same code by hand.
    client.post(CAPS, json=rapida(codigo_inmueble="INM-0390"), headers=H(p["bruno"]))
    assert client.post(INM, json=body(codigo="INM-0390"), headers=H(p["coord"])).status_code == 409


def test_filters(client, p, H):
    crear(client, H, p["coord"])  # arriendo 2,2 M Belén 3 hab
    crear(
        client,
        H,
        p["coord"],
        codigo="INM-0600",
        negocio="venta",
        habitaciones=2,
        zona="El Poblado",
        precio=700_000_000,
        direccion="Cl 10 # 40-10",
    )
    crear(
        client,
        H,
        p["coord"],
        codigo="INM-0601",
        tipo_inmueble="local",
        zona="Guayabal",
        precio=4_000_000,
        habitaciones=None,
        direccion="Cra 52 # 10-10",
    )

    def codes(**params):
        return {
            i["codigo"]
            for i in client.get(INM, params=params, headers=H(p["laura"])).json()["items"]
        }

    assert codes(negocio="venta") == {"INM-0600"}
    assert codes(tipo="local") == {"INM-0601"}
    assert codes(zona="Belén") == {"INM-0500"}
    assert codes(rango="arr_2m") == set()
    assert codes(rango="arr_2_5m") == {"INM-0500", "INM-0601"}
    assert codes(habitaciones=3) == {"INM-0500"}
    assert codes(precio_min=3_000_000, precio_max=5_000_000) == {"INM-0601"}
    assert codes(q="poblado") == {"INM-0600"}
    assert codes(estado="disponible") == {"INM-0500", "INM-0600", "INM-0601"}


# ---------------------------------------------------------------- «Enviar opciones»


def test_send_options_to_a_lead(client, db, p, H):
    a = crear(client, H, p["coord"])
    b = crear(client, H, p["coord"], codigo="INM-0501", zona="Laureles", direccion="Cra 70 # 1-1")
    v = crear(client, H, p["coord"], codigo="INM-0600", negocio="venta", direccion="Cl 10 # 40-10")
    lead = Lead(
        full_name="Cliente Opciones",
        phone="3001234567",
        fuente=FuenteLead.OTRO,
        negocio=TipoNegocio.ARRIENDO,
        zona="Laureles",
        assigned_to_id=p["laura"].id,
    )
    db.add(lead)
    db.flush()
    url = f"{INM}/para-lead/{lead.id}"
    ops = client.get(url, headers=H(p["laura"])).json()
    assert [o["codigo"] for o in ops] == ["INM-0501", "INM-0500"]  # rentals only, lead's zone first
    send = {
        "tipo": "opciones",
        "medio": "whatsapp",
        "texto": "",
        "inmueble_ids": [a["id"], b["id"]],
    }
    res = client.post(f"/api/v1/leads/{lead.id}/actions", json=send, headers=H(p["laura"]))
    assert res.status_code == 200, res.text
    assert {
        o["codigo"]: o["ya_enviado"] for o in client.get(url, headers=H(p["laura"])).json()
    } == {"INM-0501": True, "INM-0500": True}
    hist = client.get(f"{INM}/{a['id']}", headers=H(p["coord"])).json()["eventos"]
    assert hist[-1]["titulo"] == f"Enviado como opción a {lead.code} · Cliente Opciones"
    # Not-available properties can't be offered; and once sent, it isn't deleted.
    client.post(
        f"{INM}/{v['id']}/estado",
        json={"estado": "retirado", "nota": "El propietario lo retiró"},
        headers=H(p["coord"]),
    )
    bad = send | {"inmueble_ids": [v["id"]]}
    assert (
        client.post(f"/api/v1/leads/{lead.id}/actions", json=bad, headers=H(p["laura"])).status_code
        == 422
    )
    assert client.delete(f"{INM}/{a['id']}", headers=H(p["coord"])).status_code == 409
    assert (
        client.post(
            f"/api/v1/leads/{lead.id}/actions",
            json=send | {"inmueble_ids": []},
            headers=H(p["laura"]),
        ).status_code
        == 422
    )
