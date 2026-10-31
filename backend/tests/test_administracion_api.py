from datetime import timedelta

import pytest

from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo
from app.services import administracion as svc
from tests.conftest import auth_header, login
from tests.test_inmuebles_api import body as inm_body

ADM = "/api/v1/administracion-inmuebles"
INM = "/api/v1/inmuebles"


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


@pytest.fixture
def inm(client, p, H):
    res = client.post(INM, json=inm_body(), headers=H(p["coord"]))
    assert res.status_code == 201, res.text
    return res.json()


def hoy():
    return svc.hoy()


def ok(res, code=200):
    assert res.status_code == code, res.text
    return res.json()


def programar(client, H, who, inm, resp, **kw):
    data = {
        "inmueble_id": inm["id"],
        "tipo": "recepcion",
        "fecha": str(hoy() + timedelta(days=2)),
        "referencia": "CTO-0102 · Cliente Ejemplo 42",
        "responsable_id": str(resp.id),
    } | kw
    return client.post(f"{ADM}/inventarios", json=data, headers=H(who))


# ---------------------------------------------------------------- access


def test_access(client, p, H, inm):
    for k in ("ger", "coord", "aux"):
        r = ok(client.get(f"{ADM}/resumen", headers=H(p[k])))
        assert r["puede_gestionar"] is True, k
        assert r["plazo"] == 15
        assert any(i["codigo"] == "INM-0500" for i in r["inmuebles"])
        assert "Bruno Capta" in [u["full_name"] for u in r["responsables"]]
        assert "Sin Actividades" not in [u["full_name"] for u in r["responsables"]]
    r = ok(client.get(f"{ADM}/resumen", headers=H(p["bruno"])))
    assert (r["puede_gestionar"], r["inmuebles"], r["responsables"]) == (False, [], [])
    assert client.get(f"{ADM}/resumen", headers=H(p["gente"])).status_code == 403
    assert client.get(f"{ADM}/inventarios", headers=H(p["gente"])).status_code == 403
    # Only managers create
    assert programar(client, H, p["bruno"], inm, p["bruno"]).status_code == 403
    rep = {"inmueble_id": inm["id"], "titulo": "Fuga", "categoria": "plomeria", "fecha": str(hoy())}
    assert client.post(f"{ADM}/reparaciones", json=rep, headers=H(p["diego"])).status_code == 403
    assert ok(client.post(f"{ADM}/reparaciones", json=rep, headers=H(p["aux"])), 201)


def test_others_only_see_what_is_assigned_to_them(client, p, H, inm):
    a = ok(programar(client, H, p["aux"], inm, p["bruno"]), 201)
    b = ok(programar(client, H, p["aux"], inm, p["diego"]), 201)
    ids = lambda who: [i["id"] for i in ok(client.get(f"{ADM}/inventarios", headers=H(who)))]  # noqa: E731
    assert ids(p["bruno"]) == [a["id"]]
    assert set(ids(p["coord"])) == {a["id"], b["id"]}
    assert client.get(f"{ADM}/inventarios/{b['id']}", headers=H(p["bruno"])).status_code == 404
    assert ok(client.get(f"{ADM}/resumen", headers=H(p["bruno"])))["kpis"]["inventarios"] == 1


# ---------------------------------------------------------------- inventarios


def test_inventario_flow(client, p, H, inm):
    assert (
        programar(client, H, p["aux"], inm, p["bruno"], referencia=" ").status_code == 422
    )  # needs a reference
    assert programar(client, H, p["aux"], inm, p["gente"]).status_code == 422  # can't be in charge
    inv = ok(programar(client, H, p["aux"], inm, p["bruno"]), 201)
    assert (inv["code"][:4], inv["estado"], len(inv["ambientes"])) == ("INV-", "programado", 8)
    assert inv["ambientes"][0]["estado"] is None
    assert inv["inmueble"]["titulo"] == "Apto Belén"
    url = f"{ADM}/inventarios/{inv['id']}"
    k = ok(client.get(f"{ADM}/resumen", headers=H(p["aux"])))["kpis"]
    assert k["inventarios_semana"] == 1

    # Reschedule while programado (managers only)
    assert client.patch(url, json={"referencia": "x"}, headers=H(p["bruno"])).status_code == 403
    upd = ok(client.patch(url, json={"fecha": str(hoy())}, headers=H(p["coord"])))
    assert upd["eventos"][-1]["titulo"] == "Reprogramado"

    # The asesor fills it in on site
    amb = inv["ambientes"]
    path = lambda i: f"{url}/ambientes/{amb[i]['id']}"  # noqa: E731
    assert client.patch(path(0), json={"estado": "malo"}, headers=H(p["bruno"])).status_code == 422
    r = ok(
        client.patch(
            path(2),
            json={"estado": "malo", "observacion": "Grifo dañado", "fotos": 2},
            headers=H(p["bruno"]),
        )
    )
    assert (r["estado"], r["novedades"], r["fotos"]) == ("realizado", 1, 2)
    assert client.patch(path(0), json={"estado": "bueno"}, headers=H(p["diego"])).status_code == 404

    # Signatures: managers only, and every room checked
    assert client.post(f"{url}/firmar", headers=H(p["bruno"])).status_code == 403
    res = client.post(f"{url}/firmar", headers=H(p["aux"]))
    assert res.status_code == 422 and "Falta revisar" in res.json()["detail"]
    for i in range(8):
        if i != 2:
            ok(client.patch(path(i), json={"estado": "bueno"}, headers=H(p["bruno"])))
    r = ok(client.post(f"{url}/firmar", headers=H(p["aux"])))
    assert (r["estado"], r["puede_llenar"]) == ("con_novedades", False)
    assert client.post(f"{url}/firmar", headers=H(p["aux"])).status_code == 409
    assert client.patch(path(0), json={"estado": "malo"}, headers=H(p["aux"])).status_code == 409
    assert client.delete(url, headers=H(p["aux"])).status_code == 409

    # Repair from the findings, only once
    rep = ok(client.post(f"{url}/reparacion", headers=H(p["aux"])), 201)
    assert (rep["estado"], rep["inventario_code"], rep["titulo"]) == (
        "recibida",
        inv["code"],
        "Baños: Grifo dañado",
    )
    assert rep["solicitante"] == f"Inventario de recepción {inv['code']}"
    assert client.post(f"{url}/reparacion", headers=H(p["aux"])).status_code == 409
    assert ok(client.get(url, headers=H(p["aux"])))["reparacion_code"] == rep["code"]
    k = ok(client.get(f"{ADM}/resumen", headers=H(p["aux"])))["kpis"]
    assert (k["inventarios_novedades"], k["reparaciones_abiertas"]) == (1, 1)

    # The catalog's history shows it, and the property can't be deleted any more
    hist = [
        e["titulo"] for e in ok(client.get(f"{INM}/{inm['id']}", headers=H(p["coord"])))["eventos"]
    ]
    assert f"Inventario {inv['code']} firmado con novedades" in hist
    assert client.delete(f"{INM}/{inm['id']}", headers=H(p["coord"])).status_code == 409


def test_inventario_all_good_is_signed(client, p, H, inm):
    inv = ok(programar(client, H, p["coord"], inm, p["bruno"]), 201)
    url = f"{ADM}/inventarios/{inv['id']}"
    assert client.post(f"{url}/firmar", headers=H(p["coord"])).status_code == 409  # not done yet
    for a in inv["ambientes"]:
        ok(
            client.patch(
                f"{url}/ambientes/{a['id']}", json={"estado": "bueno"}, headers=H(p["aux"])
            )
        )
    r = ok(client.post(f"{url}/firmar", headers=H(p["coord"])))
    assert (r["estado"], r["estado_txt"]) == ("firmado", "Firmado")
    assert client.post(f"{url}/reparacion", headers=H(p["coord"])).status_code == 422


def test_delete_programado(client, p, H, inm):
    inv = ok(programar(client, H, p["aux"], inm, p["bruno"]), 201)
    url = f"{ADM}/inventarios/{inv['id']}"
    assert client.delete(url, headers=H(p["bruno"])).status_code == 403
    assert client.delete(url, headers=H(p["aux"])).status_code == 204
    assert client.get(url, headers=H(p["aux"])).status_code == 404


# ---------------------------------------------------------------- reparaciones


def test_reparacion_flow(client, p, H, inm):
    data = {
        "inmueble_id": inm["id"],
        "titulo": "Humedad en la habitación principal",
        "categoria": "humedad",
        "prioridad": "urgente",
        "solicitante": "Inquilino · Cliente Ejemplo 12",
        "fecha": str(hoy() - timedelta(days=4)),
        "responsable_id": str(p["diego"].id),
    }
    rep = ok(client.post(f"{ADM}/reparaciones", json=data, headers=H(p["aux"])), 201)
    assert (rep["estado"], rep["paga"], rep["dias"], rep["responsable"]["full_name"]) == (
        "recibida",
        "por_definir",
        4,
        "Diego Ventas",
    )
    url = f"{ADM}/reparaciones/{rep['id']}"
    k = ok(client.get(f"{ADM}/resumen", headers=H(p["aux"])))["kpis"]
    assert (k["reparaciones_abiertas"], k["reparaciones_urgentes"]) == (1, 1)

    # A quote is needed before moving on
    st = lambda e, who="aux": client.post(f"{url}/estado", json={"estado": e}, headers=H(p[who]))  # noqa: E731
    assert st("cotizada").status_code == 422
    assert client.post(f"{url}/avance", json={}, headers=H(p["diego"])).status_code == 422
    assert client.post(f"{url}/avance", json={"valor": 0}, headers=H(p["diego"])).status_code == 422
    assert (
        client.post(f"{url}/avance", json={"comentario": "x"}, headers=H(p["bruno"])).status_code
        == 404
    )  # not his
    r = ok(
        client.post(
            f"{url}/avance",
            json={"proveedor": "Proveedor Ejemplo 3", "valor": 250_000},
            headers=H(p["diego"]),
        )
    )
    assert r["eventos"][-1]["detalle"] == "Proveedor Ejemplo 3 · $250.000"
    assert st("cotizada", "diego").status_code == 403  # status is for managers
    assert ok(st("cotizada"))["estado_txt"] == "Cotizada"
    assert ok(st("en_ejecucion"))["estado"] == "en_ejecucion"
    assert st("terminada").status_code == 422  # who pays?
    ok(client.post(f"{url}/avance", json={"paga": "propietario"}, headers=H(p["aux"])))
    r = ok(st("terminada"))
    assert (r["fecha_fin"], r["dias"], r["puede_avance"], r["puede_gestionar"]) == (
        str(hoy()),
        4,
        False,
        False,
    )
    assert st("aprobada").status_code == 409
    assert client.patch(url, json={"titulo": "Otra"}, headers=H(p["aux"])).status_code == 409
    assert client.delete(url, headers=H(p["aux"])).status_code == 409
    k = ok(client.get(f"{ADM}/resumen", headers=H(p["aux"])))["kpis"]
    assert (k["reparaciones_abiertas"], k["reparacion_dias_promedio"]) == (0, 4)


# ---------------------------------------------------------------- solicitudes


def test_solicitud_flow(client, p, H, inm):
    data = {
        "inmueble_id": inm["id"],
        "tipo": "queja",
        "de": "inquilino",
        "nombre": "Cliente Ejemplo 44",
        "canal": "whatsapp",
        "descripcion": "Demora en la reparación del calentador",
        "fecha": str(hoy() - timedelta(days=30)),
        "responsable_id": str(p["bruno"].id),
    }
    fut = data | {"fecha": str(hoy() + timedelta(days=1))}
    assert client.post(f"{ADM}/solicitudes", json=fut, headers=H(p["aux"])).status_code == 422
    sol = ok(client.post(f"{ADM}/solicitudes", json=data, headers=H(p["aux"])), 201)
    assert (sol["estado"], sol["fuera_de_plazo"], sol["plazo"]) == ("abierta", True, 15)
    assert sol["dias_habiles"] > 15
    url = f"{ADM}/solicitudes/{sol['id']}"
    lst = ok(client.get(f"{ADM}/solicitudes?estado=fuera_de_plazo", headers=H(p["aux"])))
    assert [s["id"] for s in lst] == [sol["id"]]
    assert (
        ok(client.get(f"{ADM}/resumen", headers=H(p["aux"])))["kpis"]["solicitudes_fuera_plazo"]
        == 1
    )

    st = lambda e, nota=None, who="aux": client.post(  # noqa: E731
        f"{url}/estado", json={"estado": e, "nota": nota}, headers=H(p[who])
    )
    assert st("respondida").status_code == 422  # answer it instead
    assert st("en_tramite", who="bruno").status_code == 403
    assert ok(st("en_tramite"))["estado_txt"] == "En trámite"
    assert st("en_tramite").status_code == 409

    # The person in charge answers
    res = client.post(f"{url}/responder", json={"respuesta": "ok"}, headers=H(p["bruno"]))
    assert res.status_code == 422  # too short
    r = ok(
        client.post(
            f"{url}/responder",
            json={"respuesta": "Ya se aprobó el cambio del calentador."},
            headers=H(p["bruno"]),
        )
    )
    assert (r["estado"], r["fuera_de_plazo"], r["fecha_respuesta"]) == (
        "respondida",
        False,
        str(hoy()),
    )
    assert (
        client.post(
            f"{url}/responder", json={"respuesta": "Otra vez"}, headers=H(p["aux"])
        ).status_code
        == 409
    )  # noqa: E501
    assert ok(st("cerrada"))["estado"] == "cerrada"
    assert st("en_tramite").status_code == 409


def test_solicitud_close_without_answer_needs_reason(client, p, H, inm):
    data = {
        "inmueble_id": inm["id"],
        "tipo": "peticion",
        "de": "propietario",
        "canal": "correo",
        "descripcion": "Copia del estado de cuenta",
        "fecha": str(hoy()),
    }
    sol = ok(client.post(f"{ADM}/solicitudes", json=data, headers=H(p["coord"])), 201)
    assert sol["responsable"]["full_name"] == "Mateo Coord"  # defaults to whoever registers it
    url = f"{ADM}/solicitudes/{sol['id']}/estado"
    assert client.post(url, json={"estado": "cerrada"}, headers=H(p["coord"])).status_code == 422
    r = ok(
        client.post(
            url, json={"estado": "cerrada", "nota": "Se entregó en oficina"}, headers=H(p["coord"])
        )
    )
    assert (r["estado"], r["puede_gestionar"]) == ("cerrada", False)


# ---------------------------------------------------------------- filters


def test_date_filter(client, p, H, inm):
    ok(programar(client, H, p["aux"], inm, p["bruno"], fecha=str(hoy() - timedelta(days=40))), 201)
    ok(programar(client, H, p["aux"], inm, p["bruno"]), 201)
    q = f"desde={hoy() - timedelta(days=10)}&hasta={hoy() + timedelta(days=10)}"
    assert len(ok(client.get(f"{ADM}/inventarios?{q}", headers=H(p["aux"])))) == 1
    assert len(ok(client.get(f"{ADM}/inventarios?estado=firmado", headers=H(p["aux"])))) == 0
    assert (
        client.get(
            f"{ADM}/inventarios?desde={hoy()}&hasta={hoy() - timedelta(days=1)}",
            headers=H(p["aux"]),
        ).status_code  # noqa: E501
        == 422
    )
    assert client.get(f"{ADM}/inventarios?estado=nada", headers=H(p["aux"])).status_code == 422
    assert (
        len(ok(client.get(f"{ADM}/inventarios?inmueble_id={inm['id']}", headers=H(p["aux"])))) == 2
    )


def test_dias_habiles():
    from datetime import date

    assert svc.dias_habiles(date(2026, 10, 2), date(2026, 10, 9)) == 5  # fri → fri
    assert svc.dias_habiles(date(2026, 10, 3), date(2026, 10, 4)) == 0  # weekend
