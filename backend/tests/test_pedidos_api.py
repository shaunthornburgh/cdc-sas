from datetime import UTC, datetime, timedelta

import pytest

from app.models import Pedido
from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo
from tests.conftest import auth_header, login

PED = "/api/v1/pedidos"


def future(days: float = 5) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


@pytest.fixture
def p(make_user):
    return {
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "juan": make_user(
            email="juan@example.com", full_name="Juan Asesor", actividades=[A.VENTAS, A.ARRIENDOS]
        ),
        "ana": make_user(email="ana@example.com", full_name="Ana Ventas", actividades=[A.VENTAS]),
        "laura": make_user(
            Cargo.ATENCION_CLIENTE, email="laura@example.com", full_name="Laura Atención"
        ),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Valeria Aux"
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


def body(**kw):
    return {
        "cliente_nombre": "Cliente Cinco",
        "cliente_telefono": "300 555 0105",
        "negocio": "arriendo",
        "tipo_inmueble": "apartamento",
        "zona": "Laureles",
        "presupuesto": 2_000_000,
        "fecha_limite": future(),
        "observaciones": "2 habitaciones, con parqueadero",
    } | kw


def create(client, h, **kw):
    res = client.post(PED, json=body(**kw), headers=h)
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------- access


def test_access(client, p, H):
    assert client.get(PED, headers=H(p["aux"])).status_code == 403
    for k in ("juan", "laura", "coord"):
        assert client.get(PED, headers=H(p[k])).status_code == 200
    assert client.get(PED, params={"vista": "todos"}, headers=H(p["juan"])).status_code == 403
    assert client.get(PED, params={"vista": "todos"}, headers=H(p["coord"])).status_code == 200


# ---------------------------------------------------------------- create


def test_create_defaults_to_me(client, p, H):
    ped = create(client, H(p["juan"]))
    assert ped["code"].startswith("PED-")
    assert ped["responsable"]["full_name"] == "Juan Asesor"
    assert (ped["estado"], ped["estado_visible"], ped["can_edit"]) == ("abierto", "nuevo", True)
    assert ped["eventos"][0]["tipo"] == "creado"


def test_create_for_someone_else(client, p, H):
    ped = create(client, H(p["laura"]), responsable_id=str(p["juan"].id))
    assert ped["responsable"]["full_name"] == "Juan Asesor"
    assert ped["can_edit"] is False  # Laura created it but Juan is responsable
    assert "Lo creó Laura Atención" in ped["eventos"][0]["detalle"]


@pytest.mark.parametrize(
    "override",
    [{"zona": "Marte"}, {"presupuesto": 0}, {"fecha_limite": future(-1)}, {"negocio": "permuta"}],
)
def test_create_validation(client, p, H, override):
    assert client.post(PED, json=body(**override), headers=H(p["juan"])).status_code == 422


def test_cannot_assign_to_auxiliar(client, p, H):
    assert (
        client.post(
            PED, json=body(responsable_id=str(p["aux"].id)), headers=H(p["coord"])
        ).status_code
        == 422
    )


def test_duplicate_client_warns_then_allows(client, p, H):
    first = create(client, H(p["juan"]))
    res = client.post(
        PED,
        json=body(cliente_nombre="Otra Persona", cliente_telefono="(300) 555-0105"),
        headers=H(p["ana"]),
    )
    assert res.status_code == 409
    assert first["code"] in res.json()["detail"]
    again = client.post(
        PED, json=body(cliente_telefono="(300) 555-0105", otra_necesidad=True), headers=H(p["ana"])
    )
    assert again.status_code == 201


# ---------------------------------------------------------------- lists


def test_mis_and_equipo(client, p, H):
    mine = create(client, H(p["juan"]))
    other = create(
        client,
        H(p["ana"]),
        cliente_nombre="Cliente Once",
        cliente_telefono="3005550111",
        negocio="venta",
        presupuesto=500_000_000,
    )
    mis = client.get(PED, headers=H(p["juan"])).json()
    assert [x["code"] for x in mis["items"]] == [mine["code"]]
    assert mis["kpis"]["abiertos"] == 1  # own numbers for an asesor
    eq = client.get(PED, params={"vista": "equipo"}, headers=H(p["juan"])).json()
    assert [x["code"] for x in eq["items"]] == [other["code"]]
    assert eq["items"][0]["can_edit"] is False


def test_filters(client, p, H):
    h = H(p["juan"])
    a = create(client, h)  # arriendo 2M Laureles
    b = create(
        client,
        h,
        cliente_nombre="Beatriz Bravo",
        cliente_telefono="3005550002",
        negocio="venta",
        presupuesto=700_000_000,
        zona="El Poblado",
        fecha_limite=future(1),
    )
    c = create(
        client,
        h,
        cliente_nombre="Carlos Cano",
        cliente_telefono="3005550003",
        negocio="venta",
        presupuesto=450_000_000,
        zona="Envigado",
        fecha_limite=future(10),
    )

    def codes(**params):
        return {x["code"] for x in client.get(PED, params=params, headers=h).json()["items"]}

    assert codes(negocio="venta") == {b["code"], c["code"]}
    assert codes(zona="Envigado") == {c["code"]}
    assert codes(rango="arr_2m") == {a["code"]}
    assert codes(rango="ven_mas_500m") == {b["code"]}
    assert codes(rango="ven_500m") == {c["code"]}
    assert codes(proximos=True) == {b["code"]}
    assert codes(q="beatriz") == {b["code"]}
    assert codes(q=a["code"]) == {a["code"]}


# ---------------------------------------------------------------- actions


def test_update_keeps_before_and_after(client, p, H):
    ped = create(client, H(p["juan"]))
    url = f"{PED}/{ped['id']}"
    assert (
        client.patch(url, json={"presupuesto": 2_500_000}, headers=H(p["juan"])).status_code == 422
    )  # que_cambio
    res = client.patch(
        url,
        json={
            "presupuesto": 2_500_000,
            "zona": "Belén",
            "que_cambio": "Ahora busca 3 habitaciones",
        },
        headers=H(p["juan"]),
    ).json()
    ev = res["eventos"][-1]
    assert ev["titulo"] == "Actualizado · Ahora busca 3 habitaciones"
    assert ev["datos"]["antes"]["zona"] == "Laureles" and ev["datos"]["despues"]["zona"] == "Belén"
    assert "$2.000.000 → $2.500.000" in ev["detalle"]
    # Not the responsable: forbidden. Coordinación: allowed.
    assert (
        client.patch(
            url, json={"zona": "Sabaneta", "que_cambio": "x"}, headers=H(p["ana"])
        ).status_code
        == 403
    )
    assert (
        client.patch(
            url, json={"zona": "Sabaneta", "que_cambio": "x"}, headers=H(p["coord"])
        ).status_code
        == 200
    )


def test_attend_and_lose(client, p, H):
    a = create(client, H(p["juan"]))
    b = create(client, H(p["juan"]), cliente_nombre="Otro", cliente_telefono="3005550199")
    res = client.post(
        f"{PED}/{a['id']}/atendido", json={"nota": "Se enviaron 4 opciones"}, headers=H(p["juan"])
    ).json()
    assert (res["estado"], res["estado_visible"]) == ("atendido", "atendido")
    assert client.post(f"{PED}/{b['id']}/perdido", json={}, headers=H(p["juan"])).status_code == 422
    lost = client.post(
        f"{PED}/{b['id']}/perdido", json={"motivo": "compro_con_otro"}, headers=H(p["juan"])
    ).json()
    assert (lost["estado_visible"], lost["motivo_perdida"]) == ("perdido", "compro_con_otro")
    # Closed: leaves «Mis pedidos», no more changes.
    assert client.get(PED, headers=H(p["juan"])).json()["items"] == []
    assert (
        client.post(f"{PED}/{a['id']}/atendido", json={}, headers=H(p["juan"])).status_code == 422
    )


def test_expired_never_lost_by_itself_extend_or_lose(client, db, p, H):
    ped = create(client, H(p["juan"]))
    url = f"{PED}/{ped['id']}"
    # Extending a not-yet-expired pedido is refused.
    assert (
        client.post(
            f"{url}/extender", json={"fecha_limite": future(9), "motivo": "x"}, headers=H(p["juan"])
        ).status_code
        == 422
    )
    db.get(Pedido, ped["id"]).fecha_limite = datetime.now(UTC) - timedelta(hours=2)
    db.flush()
    cur = client.get(url, headers=H(p["juan"])).json()
    assert (cur["estado"], cur["estado_visible"], cur["vencido"]) == ("abierto", "vencido", True)
    assert (
        client.get(PED, params={"vista": "vencidos"}, headers=H(p["coord"])).json()["kpis"][
            "vencidos_sin_decidir"
        ]
        == 1
    )

    assert (
        client.post(
            f"{url}/extender", json={"fecha_limite": future(3), "motivo": " "}, headers=H(p["juan"])
        ).status_code
        == 422
    )
    ext = client.post(
        f"{url}/extender",
        json={"fecha_limite": future(3), "motivo": "El cliente pidió más tiempo"},
        headers=H(p["juan"]),
    ).json()
    assert (ext["vencido"], ext["vencio"]) == (False, True)
    done = client.post(f"{url}/atendido", json={}, headers=H(p["juan"])).json()
    assert done["estado_visible"] == "recuperado"
    # Kept in «Vencidos» for Gerencia.
    assert ped["code"] in [
        x["code"]
        for x in client.get(PED, params={"vista": "vencidos"}, headers=H(p["coord"])).json()[
            "items"
        ]
    ]


def test_propose_and_comment_on_others(client, p, H):
    ped = create(client, H(p["juan"]))
    url = f"{PED}/{ped['id']}"
    res = client.post(
        f"{url}/proponer",
        json={"inmueble": "INM-0351 · Cl 33 # 80-20, Belén", "nota": "Acepta mascotas"},
        headers=H(p["ana"]),
    ).json()
    assert res["eventos"][-1]["titulo"] == "Ana Ventas propone INM-0351 · Cl 33 # 80-20, Belén"
    assert (
        client.post(f"{url}/comentar", json={"texto": " "}, headers=H(p["laura"])).status_code
        == 422
    )
    res = client.post(
        f"{url}/comentar", json={"texto": "Prefiere visitas en la tarde"}, headers=H(p["laura"])
    ).json()
    assert res["eventos"][-1]["tipo"] == "comentario"
    # Proposing doesn't let her change it.
    assert client.post(f"{url}/atendido", json={}, headers=H(p["ana"])).status_code == 403


def test_reassign_only_managers(client, p, H):
    ped = create(client, H(p["juan"]))
    url = f"{PED}/{ped['id']}/reasignar"
    assert (
        client.post(
            url, json={"responsable_id": str(p["ana"].id)}, headers=H(p["juan"])
        ).status_code
        == 403
    )
    res = client.post(url, json={"responsable_id": str(p["ana"].id)}, headers=H(p["coord"])).json()
    assert res["responsable"]["full_name"] == "Ana Ventas"


def test_options(client, p, H):
    o = client.get(f"{PED}/opciones", headers=H(p["juan"])).json()
    assert "Laureles" in o["zonas"] and "arr_2m" in o["rangos"]
    names = {r["full_name"] for r in o["responsables"]}
    assert {"Juan Asesor", "Ana Ventas", "Laura Atención"} <= names and "Valeria Aux" not in names


def test_dashboard_and_asesor_home(client, db, p, H):
    hoy = create(
        client, H(p["juan"]), fecha_limite=(datetime.now(UTC) + timedelta(minutes=30)).isoformat()
    )
    venc = create(
        client, H(p["juan"]), cliente_nombre="Vencido Pérez", cliente_telefono="3005550777"
    )
    db.get(Pedido, venc["id"]).fecha_limite = datetime.now(UTC) - timedelta(hours=3)
    db.flush()

    d = client.get("/api/v1/dashboard/coordinacion", headers=H(p["coord"])).json()["pedidos"]
    assert d["vencidos_sin_decidir"] == 1
    assert [x["code"] for x in d["lista_sin_decidir"]] == [venc["code"]]
    mine = d["por_persona"][str(p["juan"].id)]
    assert (mine["vencidos"], mine["por_vencer"]) == (1, 1)
    alerts = client.get("/api/v1/dashboard/coordinacion", headers=H(p["coord"])).json()["alertas"]
    assert any(a["titulo"] == f"Pedido {venc['code']} vencido · Juan Asesor" for a in alerts)

    pend = client.get("/api/v1/asesor/inicio", headers=H(p["juan"])).json()["pendientes"]
    chips = {(x["titulo"].split(" vence")[0].split(" vencido")[0], x["chip"]) for x in pend}
    assert (f"Pedido {venc['code']}", "Decidir") in chips
    assert (f"Pedido {hoy['code']}", "Urgente") in chips
