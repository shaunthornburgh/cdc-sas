import pytest

from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, FuncionIndependiente
from tests.conftest import auth_header, login

CAPS = "/api/v1/captaciones"


@pytest.fixture
def juan(make_user):
    return make_user(
        email="juan@example.com", full_name="Juan Captador", actividades=[A.CAPTACION, A.VENTAS]
    )


@pytest.fixture
def ana(make_user):
    return make_user(email="ana@example.com", full_name="Ana Captadora", actividades=[A.CAPTACION])


@pytest.fixture
def coord(make_user):
    return make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coordinador")


@pytest.fixture
def as_user(client):
    cache: dict[str, dict] = {}

    def _h(user):
        if user.email not in cache:
            cache[user.email] = auth_header(login(client, user.email)["access_token"])
        return cache[user.email]

    return _h


def rapida(**kw):
    return {
        "negocio": "venta",
        "codigo_inmueble": "inm-0360",
        "direccion": "Cl 10 Sur # 43-80, Poblado",
    } | kw


COMPLETA = {
    "modo": "completo",
    "negocio": "arriendo",
    "codigo_inmueble": "INM-0370",
    "direccion": "Cra 70 # 45-12 apto 301",
    "tipo_inmueble": "apartamento",
    "barrio": "Laureles",
    "municipio": "Medellín",
    "precio": 2_400_000,
    "area_m2": "72.5",
    "habitaciones": 3,
    "banos": 2,
    "parqueadero": True,
    "propietario_nombre": "Rosa Elena Múnera",
    "propietario_telefono": "300 555 0177",
}


def create(client, h, **kw):
    res = client.post(CAPS, json=rapida(**kw), headers=h)
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------- access


@pytest.mark.parametrize(
    ("cargo", "kwargs"),
    [
        (Cargo.ASESOR, {"actividades": [A.VENTAS, A.ARRIENDOS]}),
        (Cargo.AUXILIAR_ADMINISTRATIVA, {}),
        (Cargo.ATENCION_CLIENTE, {}),
        (Cargo.ASESOR, {"funcion": FuncionIndependiente.PRE_VENTAS}),
    ],
)
def test_module_needs_captacion_activity(client, make_user, as_user, cargo, kwargs):
    user = make_user(cargo, email="x@example.com", **kwargs)
    h = as_user(user)
    assert client.get(CAPS, headers=h).status_code == 403
    assert client.post(CAPS, json=rapida(), headers=h).status_code == 403


def test_requires_login(client):
    assert client.get(CAPS).status_code == 401


def test_captador_sees_only_own_managers_see_all(client, juan, ana, coord, as_user):
    mine = create(client, as_user(juan))
    other = create(client, as_user(ana), codigo_inmueble="INM-0361")

    juan_codes = [c["code"] for c in client.get(CAPS, headers=as_user(juan)).json()["items"]]
    assert juan_codes == [mine["code"]]
    assert client.get(f"{CAPS}/{other['id']}", headers=as_user(juan)).status_code == 404

    all_codes = {c["code"] for c in client.get(CAPS, headers=as_user(coord)).json()["items"]}
    assert {mine["code"], other["code"]} <= all_codes


def test_losing_captacion_activity_closes_the_module(client, db, juan, as_user):
    from app.services.users import set_actividades

    h = as_user(juan)
    create(client, h)
    set_actividades(db, juan, [A.VENTAS])
    db.flush()
    assert client.get(CAPS, headers=h).status_code == 403


# ---------------------------------------------------------------- create


def test_quick_registration(client, juan, as_user):
    body = rapida(gps={"lat": 6.2086, "lng": -75.5671, "precision_m": 25})
    cap = client.post(CAPS, json=body, headers=as_user(juan)).json()
    assert cap["code"].startswith("CAP-")
    assert cap["codigo_inmueble"] == "INM-0360"  # normalised
    assert cap["estado"] == "por_verificar"
    assert cap["modo"] == "rapido"
    assert cap["asesor"]["full_name"] == "Juan Captador"
    assert cap["gps_precision_m"] == 25 and cap["gps_at"] is not None
    assert cap["eventos"][0]["titulo"] == "Enviada a verificación · Registro rápido"


def test_full_form_requires_its_fields(client, juan, as_user):
    h = as_user(juan)
    missing = {k: v for k, v in COMPLETA.items() if k not in ("barrio", "propietario_telefono")}
    res = client.post(CAPS, json=missing, headers=h)
    assert res.status_code == 422
    assert "barrio" in res.json()["detail"] and "teléfono del propietario" in res.json()["detail"]

    cap = client.post(CAPS, json=COMPLETA, headers=h).json()
    assert (cap["tipo_inmueble"], cap["habitaciones"], cap["precio"]) == (
        "apartamento",
        3,
        2_400_000,
    )


def test_duplicate_code_is_blocked(client, juan, ana, as_user):
    create(client, as_user(juan))
    res = client.post(CAPS, json=rapida(codigo_inmueble=" INM-0360 "), headers=as_user(ana))
    assert res.status_code == 409
    assert res.json()["detail"].startswith("Inmueble ya registrado")
    assert "Juan Captador" in res.json()["detail"]


def test_rejected_code_can_be_used_again(client, juan, ana, coord, as_user):
    cap = create(client, as_user(juan))
    client.post(
        f"{CAPS}/{cap['id']}/status",
        json={"estado": "rechazada", "motivo": "codigo_no_corresponde"},
        headers=as_user(coord),
    )
    assert client.post(CAPS, json=rapida(), headers=as_user(ana)).status_code == 201


@pytest.mark.parametrize(
    "override", [{"negocio": "permuta"}, {"direccion": "x"}, {"codigo_inmueble": ""}]
)
def test_create_validation(client, juan, as_user, override):
    assert client.post(CAPS, json=rapida(**override), headers=as_user(juan)).status_code == 422


def test_manager_registers_for_a_captador_without_gps(client, juan, coord, as_user):
    body = rapida(asesor_id=str(juan.id), gps={"lat": 6.2, "lng": -75.5})
    cap = client.post(CAPS, json=body, headers=as_user(coord)).json()
    assert cap["asesor"]["full_name"] == "Juan Captador"
    assert cap["gps_at"] is None
    assert "Registrada por Mateo Coordinador" in cap["eventos"][0]["detalle"]


def test_captador_cannot_register_for_someone_else(client, juan, ana, as_user):
    res = client.post(CAPS, json=rapida(asesor_id=str(ana.id)), headers=as_user(juan))
    assert res.status_code == 403


def test_cannot_assign_to_person_without_captacion(client, coord, make_user, as_user):
    vendedor = make_user(email="v@example.com", actividades=[A.VENTAS])
    res = client.post(CAPS, json=rapida(asesor_id=str(vendedor.id)), headers=as_user(coord))
    assert res.status_code == 422


# ---------------------------------------------------------------- verification


def test_only_managers_verify(client, juan, as_user):
    cap = create(client, as_user(juan))
    res = client.post(
        f"{CAPS}/{cap['id']}/status", json={"estado": "aprobada"}, headers=as_user(juan)
    )
    assert res.status_code == 403


def test_approve(client, juan, coord, as_user):
    cap = create(client, as_user(juan))
    res = client.post(
        f"{CAPS}/{cap['id']}/status", json={"estado": "aprobada"}, headers=as_user(coord)
    ).json()
    assert res["estado"] == "aprobada"
    assert res["verificado_por_name"] == "Mateo Coordinador"
    assert res["eventos"][-1]["titulo"] == "Aprobada por Mateo Coordinador"
    # Already verified: can't be verified again.
    again = client.post(
        f"{CAPS}/{cap['id']}/status",
        json={"estado": "rechazada", "motivo": "codigo_inexistente"},
        headers=as_user(coord),
    )
    assert again.status_code == 422


def test_reject_requires_reason(client, juan, coord, as_user):
    cap = create(client, as_user(juan))
    url = f"{CAPS}/{cap['id']}/status"
    assert client.post(url, json={"estado": "rechazada"}, headers=as_user(coord)).status_code == 422
    res = client.post(
        url,
        json={
            "estado": "rechazada",
            "motivo": "codigo_inexistente",
            "observacion": "No aparece en Ciencuadras",
        },
        headers=as_user(coord),
    ).json()
    assert (res["estado"], res["motivo_rechazo"]) == ("rechazada", "codigo_inexistente")
    assert "No aparece en Ciencuadras" in res["eventos"][-1]["detalle"]


def test_correct_and_resubmit(client, juan, coord, as_user):
    h = as_user(juan)
    cap = create(client, h)
    client.post(
        f"{CAPS}/{cap['id']}/status",
        json={"estado": "rechazada", "motivo": "codigo_no_corresponde"},
        headers=as_user(coord),
    )
    url = f"{CAPS}/{cap['id']}/resubmit"

    same = {"codigo_inmueble": "INM-0360", "direccion": "Cl 10 Sur # 43-80, Poblado"}
    assert client.post(url, json=same, headers=h).status_code == 422

    res = client.post(url, json={**same, "codigo_inmueble": "INM-0365"}, headers=h).json()
    assert (res["estado"], res["codigo_inmueble"], res["reenvios"]) == (
        "por_verificar",
        "INM-0365",
        1,
    )
    assert res["verificado_por_name"] is None
    assert "Antes: INM-0360" in res["eventos"][-1]["detalle"]
    # Not rejected anymore: can't resubmit again.
    assert (
        client.post(url, json={**same, "codigo_inmueble": "INM-0366"}, headers=h).status_code == 422
    )


def test_resubmit_checks_duplicates(client, juan, ana, coord, as_user):
    cap = create(client, as_user(juan))
    create(client, as_user(ana), codigo_inmueble="INM-0399")
    client.post(
        f"{CAPS}/{cap['id']}/status",
        json={"estado": "rechazada", "motivo": "codigo_inexistente"},
        headers=as_user(coord),
    )
    res = client.post(
        f"{CAPS}/{cap['id']}/resubmit",
        json={"codigo_inmueble": "INM-0399", "direccion": "Otra dirección 123"},
        headers=as_user(juan),
    )
    assert res.status_code == 409


def test_publish_only_when_approved(client, juan, coord, as_user):
    h = as_user(juan)
    cap = create(client, h)
    url = f"{CAPS}/{cap['id']}/publish"
    assert client.post(url, headers=h).status_code == 422
    client.post(f"{CAPS}/{cap['id']}/status", json={"estado": "aprobada"}, headers=as_user(coord))
    res = client.post(url, headers=h).json()
    assert res["publicada_at"] is not None


# ---------------------------------------------------------------- edit / delete / reassign


def test_edit_rules(client, juan, coord, as_user):
    h = as_user(juan)
    cap = create(client, h)
    url = f"{CAPS}/{cap['id']}"
    res = client.patch(
        url, json={"observaciones": "Propietario disponible en las tardes"}, headers=h
    )
    assert res.status_code == 200 and res.json()["can_edit"] is True

    client.post(f"{url}/status", json={"estado": "aprobada"}, headers=as_user(coord))
    assert client.patch(url, json={"barrio": "El Poblado"}, headers=h).status_code == 403
    assert (
        client.patch(url, json={"barrio": "El Poblado"}, headers=as_user(coord)).status_code == 200
    )


def test_rejected_code_change_goes_through_resubmit(client, juan, coord, as_user):
    h = as_user(juan)
    cap = create(client, h)
    client.post(
        f"{CAPS}/{cap['id']}/status",
        json={"estado": "rechazada", "motivo": "codigo_inexistente"},
        headers=as_user(coord),
    )
    res = client.patch(f"{CAPS}/{cap['id']}", json={"codigo_inmueble": "INM-0368"}, headers=h)
    assert res.status_code == 422


def test_delete_rules(client, juan, coord, as_user):
    h = as_user(juan)
    a = create(client, h)
    b = create(client, h, codigo_inmueble="INM-0362")
    assert client.delete(f"{CAPS}/{a['id']}", headers=h).status_code == 204  # withdraw
    client.post(f"{CAPS}/{b['id']}/status", json={"estado": "aprobada"}, headers=as_user(coord))
    assert client.delete(f"{CAPS}/{b['id']}", headers=h).status_code == 403
    assert client.delete(f"{CAPS}/{b['id']}", headers=as_user(coord)).status_code == 204


def test_reassign(client, juan, ana, coord, make_user, as_user):
    cap = create(client, as_user(juan))
    url = f"{CAPS}/{cap['id']}/reassign"
    assert (
        client.post(url, json={"asesor_id": str(ana.id)}, headers=as_user(juan)).status_code == 403
    )
    vendedor = make_user(email="v@example.com", actividades=[A.VENTAS])
    assert (
        client.post(url, json={"asesor_id": str(vendedor.id)}, headers=as_user(coord)).status_code
        == 422
    )
    res = client.post(url, json={"asesor_id": str(ana.id)}, headers=as_user(coord)).json()
    assert res["asesor"]["full_name"] == "Ana Captadora"
    assert client.get(f"{CAPS}/{cap['id']}", headers=as_user(juan)).status_code == 404


# ---------------------------------------------------------------- list & filters


def test_filters_and_counts(client, juan, ana, coord, as_user):
    a = create(client, as_user(juan), negocio="venta")
    b = create(
        client,
        as_user(ana),
        codigo_inmueble="INM-0362",
        negocio="arriendo",
        direccion="Cra 43A # 60 Sur-15, Sabaneta",
    )
    create(client, as_user(ana), codigo_inmueble="INM-0363")
    h = as_user(coord)
    client.post(f"{CAPS}/{a['id']}/status", json={"estado": "aprobada"}, headers=h)
    client.post(
        f"{CAPS}/{b['id']}/status",
        json={"estado": "rechazada", "motivo": "codigo_inexistente"},
        headers=h,
    )

    def codes(**params):
        return {
            c["codigo_inmueble"] for c in client.get(CAPS, params=params, headers=h).json()["items"]
        }

    assert codes(estado="por_verificar") == {"INM-0363"}
    assert codes(estado=["aprobada", "rechazada"]) == {"INM-0360", "INM-0362"}
    assert codes(asesor_id=str(ana.id)) == {"INM-0362", "INM-0363"}
    assert codes(negocio="arriendo") == {"INM-0362"}
    assert codes(q="sabaneta") == {"INM-0362"}
    assert codes(q=a["code"]) == {"INM-0360"}
    data = client.get(CAPS, params={"estado": "por_verificar"}, headers=h).json()
    assert data["counts"] == {"por_verificar": 1, "aprobada": 1, "rechazada": 1}
    assert data["aprobacion_pct"] == 50


def test_captadores_list_for_managers(client, juan, ana, coord, make_user, as_user):
    make_user(email="v@example.com", actividades=[A.VENTAS])
    names = [
        u["full_name"] for u in client.get(f"{CAPS}/captadores", headers=as_user(coord)).json()
    ]
    assert names == ["Ana Captadora", "Juan Captador"]
    assert client.get(f"{CAPS}/captadores", headers=as_user(juan)).status_code == 403
