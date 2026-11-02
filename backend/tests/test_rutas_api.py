"""Rutas (G-083, M04, X08, G-051): validation, accept/reject, Mi ruta, import, access, rating."""

from datetime import datetime, timedelta

import pytest

from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo
from app.services import fechas
from tests.conftest import auth_header, login

RT = "/api/v1/rutas"
NOW = datetime(2026, 10, 5, 9, 0, tzinfo=fechas.BOGOTA)  # Monday


@pytest.fixture
def reloj(monkeypatch):
    state = {"now": NOW}
    monkeypatch.setattr(fechas, "now", lambda: state["now"])
    return state


@pytest.fixture
def p(make_user):
    return {
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com"),
        "aux": make_user(Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com"),
        "juan": make_user(
            Cargo.ASESOR,
            email="juan@example.com",
            full_name="Juan Captador",
            actividades=[A.CAPTACION],
        ),
        "carla": make_user(
            Cargo.ASESOR, email="carla@example.com", full_name="Carla", actividades=[A.ARRIENDOS]
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


def ruta(asesor, **kw):
    base = {
        "asesor_id": str(asesor.id),
        "desde": "2026-10-05",
        "hasta": "2026-10-09",
        "dias": [1, 2, 3, 4, 5],
        "zonas": [
            {
                "zona": "Laureles",
                "hora_inicio": "08:30",
                "hora_fin": "12:00",
                "dias": [1, 2, 3, 4, 5],
            },
            {"zona": "Belén", "hora_inicio": "14:00", "hora_fin": "17:00", "dias": [1, 3, 5]},
        ],
        "observacion": "Captación de apartamentos en oferta",
    }
    return base | kw


def err(res, code=422):
    assert res.status_code == code, res.text
    return res.json()["detail"]


def test_access(client, p, H, reloj):
    assert client.get(RT, headers=H(p["juan"])).status_code == 403
    assert client.get(f"{RT}/mi-ruta", headers=H(p["carla"])).status_code == 403
    assert client.get(f"{RT}/opciones", headers=H(p["carla"])).status_code == 403
    for k in ("coord", "ger", "aux"):
        ok(client.get(RT, headers=H(p[k])))
    for k in ("ger", "aux", "juan"):
        assert client.post(RT, json=ruta(p["juan"]), headers=H(p[k])).status_code == 403
    o = ok(client.get(f"{RT}/opciones", headers=H(p["coord"])))
    assert [a["nombre"] for a in o["asesores"]] == ["Juan Captador"] and o["puede_programar"]


def test_validation(client, p, H, reloj):
    h = H(p["coord"])
    assert "no tiene Captación activa" in err(client.post(RT, json=ruta(p["carla"]), headers=h))
    assert "Revisa las fechas" in err(
        client.post(RT, json=ruta(p["juan"], hasta="2026-10-01"), headers=h)
    )
    assert "al menos un día" in err(client.post(RT, json=ruta(p["juan"], dias=[]), headers=h))
    z = ruta(p["juan"])["zonas"]
    assert "hora final" in err(
        client.post(RT, json=ruta(p["juan"], zonas=[z[0] | {"hora_fin": "08:00"}]), headers=h)
    )
    assert "no están en los días" in err(
        client.post(RT, json=ruta(p["juan"], dias=[1, 2], zonas=[z[0]]), headers=h)
    )
    assert "Repetiste la zona" in err(
        client.post(
            RT,
            json=ruta(
                p["juan"], zonas=[z[0], z[0] | {"hora_inicio": "13:00", "hora_fin": "15:00"}]
            ),
            headers=h,
        )
    )
    cruce = [z[0], z[1] | {"zona": "Envigado", "hora_inicio": "11:00", "dias": [1]}]
    assert "se cruzan en horario" in err(
        client.post(RT, json=ruta(p["juan"], zonas=cruce), headers=h)
    )
    assert "lista de zonas" in err(
        client.post(RT, json=ruta(p["juan"], zonas=[z[0] | {"zona": "Marte"}]), headers=h)
    )
    ok(client.post(RT, json=ruta(p["juan"]), headers=h), 201)
    assert "ya tiene una ruta por aceptar" in err(
        client.post(RT, json=ruta(p["juan"], desde="2026-10-08", hasta="2026-10-20"), headers=h),
        409,
    )


def test_reject_resend_accept_and_mi_ruta(client, p, H, reloj):
    h, hj = H(p["coord"]), H(p["juan"])
    r = ok(client.post(RT, json=ruta(p["juan"]), headers=h), 201)
    assert r["estado_txt"] == "Por aceptar"
    av = ok(client.get("/api/v1/avisos", headers=hj))["items"]
    assert any(a["tipo"] == "ruta_por_aceptar" for a in av)
    # Reject: reason and explanation required
    assert (
        client.post(
            f"{RT}/{r['id']}/responder", json={"acepta": False, "motivo": "permiso"}, headers=hj
        ).status_code
        == 422
    )
    assert (
        client.post(f"{RT}/{r['id']}/responder", json={"acepta": True}, headers=h).status_code
        == 403
    )
    x = ok(
        client.post(
            f"{RT}/{r['id']}/responder",
            json={"acepta": False, "motivo": "permiso", "texto": "Tengo permiso el martes"},
            headers=hj,
        )
    )
    assert x["estado"] == "rechazada" and "Tengo permiso o incapacidad" in x["motivo_txt"]
    assert any(
        a["tipo"] == "ruta_rechazada" for a in ok(client.get("/api/v1/avisos", headers=h))["items"]
    )
    # Adjust and send again: the old one is cancelled
    r2 = ok(
        client.post(
            RT,
            json=ruta(
                p["juan"],
                dias=[1, 3, 4, 5],
                zonas=[ruta(p["juan"])["zonas"][0] | {"dias": [1, 3, 4, 5]}],
                reemplaza_id=r["id"],
            ),
            headers=h,
        ),
        201,
    )
    assert ok(client.get(f"{RT}/{r['id']}", headers=h))["estado"] == "cancelada"
    assert not any(
        a["tipo"] == "ruta_rechazada" for a in ok(client.get("/api/v1/avisos", headers=h))["items"]
    )
    ok(client.post(f"{RT}/{r2['id']}/responder", json={"acepta": True}, headers=hj))
    assert (
        client.post(f"{RT}/{r2['id']}/responder", json={"acepta": True}, headers=hj).status_code
        == 409
    )
    # Mi ruta: Monday has Laureles; mark arrival
    m = ok(client.get(f"{RT}/mi-ruta", headers=hj))
    assert [t["titulo"] for t in m["timeline"]] == ["Captación · Laureles"] and m["siguiente"][
        "zona"
    ] == "Laureles"
    ok(client.post(f"{RT}/llegada", json={"zona_id": m["siguiente"]["id"]}, headers=hj), 201)
    assert (
        client.post(f"{RT}/llegada", json={"zona_id": m["siguiente"]["id"]}, headers=hj).status_code
        == 409
    )
    m = ok(client.get(f"{RT}/mi-ruta", headers=hj))
    assert (m["hechos"], m["siguiente"], m["timeline"][0]["estado_txt"]) == (1, None, "✓ Hecho")
    # Tuesday has no zone in the new version
    reloj["now"] = NOW + timedelta(days=1)
    assert ok(client.get(f"{RT}/mi-ruta", headers=hj))["timeline"] == []
    # Agenda shows the route zones; locations too
    ag = ok(
        client.get(
            "/api/v1/agenda", params={"desde": "2026-10-05", "hasta": "2026-10-09"}, headers=hj
        )
    )
    assert sum(1 for i in ag["items"] if i["tipo"] == "ruta") == 4
    reloj["now"] = NOW
    ub = {u["nombre"]: u for u in ok(client.get(f"{RT}/ubicaciones", headers=H(p["aux"])))}
    assert ub["Juan Captador"]["donde"] == "En ruta · Laureles" and ub["Carla"]["nota"].startswith(
        "Sin Captación"
    )


def test_cancel_rate_and_registro(client, p, H, reloj):
    h = H(p["coord"])
    r = ok(client.post(RT, json=ruta(p["juan"]), headers=h), 201)
    assert (
        client.post(
            f"{RT}/{r['id']}/calificar", json={"puntos": 4}, headers=H(p["ger"])
        ).status_code
        == 409
    )
    ok(client.post(f"{RT}/{r['id']}/responder", json={"acepta": True}, headers=H(p["juan"])))
    assert (
        client.post(f"{RT}/{r['id']}/calificar", json={"puntos": 4}, headers=h).status_code == 403
    )
    x = ok(client.post(f"{RT}/{r['id']}/calificar", json={"puntos": 4}, headers=H(p["ger"])))
    assert x["calificacion"] == 4
    res = ok(client.get("/api/v1/rendimiento/mio", headers=h))
    rutas = next(a for a in res["areas"] if a["key"] == "rutas")
    assert (rutas["cumplimiento"], rutas["logrado_txt"]) == (80, "4 de 5 en promedio")
    ok(client.post(f"{RT}/{r['id']}/cancelar", headers=h))
    assert client.post(f"{RT}/{r['id']}/cancelar", headers=h).status_code == 409
    av = ok(client.get("/api/v1/avisos", params={"vista": "resumen"}, headers=H(p["juan"])))[
        "items"
    ]
    assert any(a["tipo"] == "ruta_cancelada" for a in av)
    lst = ok(client.get(RT, params={"estado": "cancelada"}, headers=H(p["ger"])))
    assert lst["total"] == 1
    rc = ok(
        client.get(
            "/api/v1/registro-cambios",
            params={"modulo": "Rutas", "desde": "2026-09-01", "hasta": "2026-12-31"},
            headers=h,
        )
    )
    assert {"Asignó la ruta", "Aceptó la ruta", "Calificó la ruta", "Canceló la ruta"} <= {
        i["accion"] for i in rc["items"]
    }


def test_import(client, p, H, reloj):
    h = H(p["coord"])
    plantilla = client.get(f"{RT}/plantilla.csv", headers=h)
    assert plantilla.status_code == 200 and "asesor_correo;desde" in plantilla.text
    from app.services.rutas import PLANTILLA_COLS

    cab = ";".join(PLANTILLA_COLS)
    filas = [
        "juan@example.com;2026-10-12;2026-10-16;L a V;Laureles;08:00-11:00;L a V;"
        "Belén;11:30-14:00;L a V;;;;Ruta",
        "carla@example.com;2026-10-12;2026-10-16;L a V;Belén;08:00-12:00;L a V;;;;;;;",
        "juan@example.com;2026-10-14;2026-10-20;L a V;Belén;08:00-12:00;L a V;;;;;;;",
        "nadie@example.com;2026-10-12;2026-10-16;L a V;Belén;08:00-12:00;L a V;;;;;;;",
        "juan@example.com;12/10/2026;16/10/2026;L-Q;Belén;08:00-12:00;L;;;;;;;",
    ]
    texto = "\n".join([cab, *filas])
    rev = ok(client.post(f"{RT}/importar", json={"texto": texto}, headers=h))
    assert (rev["correctas"], rev["total"], rev["asignadas"]) == (1, 5, 0)
    errores = [f["error"] for f in rev["filas"]]
    assert errores[0] is None and "Captación" in errores[1] and "Otra fila" in errores[2]
    assert "nadie@example.com" in errores[3] and "no válidos" in errores[4]
    assert ok(client.get(RT, headers=h))["total"] == 0  # review only
    rev = ok(client.post(f"{RT}/importar", json={"texto": texto, "confirmar": True}, headers=h))
    assert rev["asignadas"] == 1
    item = ok(client.get(RT, headers=h))["items"][0]
    assert (item["origen"], item["estado"], item["zonas_txt"]) == (
        "excel",
        "por_aceptar",
        "Laureles (L a V 08:00–11:00) · Belén (L a V 11:30–14:00)",
    )
    assert client.post(f"{RT}/importar", json={"texto": "a;b\n1;2"}, headers=h).status_code == 422
