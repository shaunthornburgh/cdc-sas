"""Pólizas (X11, G-087, G-075, G-072, G-084, G-034): insurers, flow, alerts, access."""

from datetime import date, datetime, timedelta

import pytest

from app.models import Cierre, Lead
from app.models.enums import ActividadComercial, Cargo, EtapaLead, FuenteLead, TipoNegocio
from app.services import fechas
from tests.conftest import auth_header, login

PZ = "/api/v1/polizas"
NOW = datetime(2026, 10, 3, 11, 0, tzinfo=fechas.BOGOTA)
HOY = date(2026, 10, 3)


@pytest.fixture
def reloj(monkeypatch):
    state = {"now": NOW}
    monkeypatch.setattr(fechas, "now", lambda: state["now"])
    return state


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Valeria"
        ),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com"),
        "ase": make_user(
            Cargo.ASESOR,
            email="ase@example.com",
            full_name="Bruno Asesor",
            actividades=[ActividadComercial.ARRIENDOS],
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
    return res.json() if res.content else None


def _cierre(db, asesor, negocio=TipoNegocio.ARRIENDO):
    ld = Lead(
        full_name="Cliente",
        phone="3000000000",
        fuente=FuenteLead.OTRO,
        etapa=EtapaLead.GANADO,
        negocio=negocio,
        busca="Apartamento en Belén",
        cerrado_at=NOW,
    )
    db.add(ld)
    db.flush()
    c = Cierre(lead_id=ld.id, negocio=negocio, cerrado_at=NOW, cerrador_id=asesor.id)
    db.add(c)
    db.flush()
    return c


def _aseguradora(client, h, nombre="Seguros Uno", dias=45, aviso=10, pct=2.5):
    a = ok(
        client.post(
            f"{PZ}/aseguradoras",
            json={
                "nombre": nombre,
                "nit": "900.000.000-1",
                "dias_max": dias,
                "aviso_dias": aviso,
                "poliza": {
                    "nombre": "Básica",
                    "precio_pct": pct,
                    "costo_estudio": 40000,
                    "dias_respuesta": 2,
                    "coberturas": ["can", "adm", "nada"],
                },
            },
            headers=h,
        ),
        201,
    )
    vista = ok(client.get(f"{PZ}/aseguradoras", headers=h))
    item = next(x for x in vista["items"] if x["id"] == a["id"])
    return item


def test_access(client, p, H, reloj):
    for k in ("coord", "ase"):
        assert client.get(PZ, headers=H(p[k])).status_code == 403
        assert client.get(f"{PZ}/aseguradoras", headers=H(p[k])).status_code == 403
    ok(client.get(PZ, headers=H(p["aux"])))
    assert client.get(f"{PZ}/comparar", headers=H(p["aux"])).status_code == 403
    ok(client.get(f"{PZ}/comparar", headers=H(p["ger"])))


def test_insurers(client, p, H, reloj, db):
    h = H(p["aux"])
    bad = {
        "nombre": "X",
        "dias_max": 10,
        "aviso_dias": 20,
        "poliza": {"nombre": "B", "precio_pct": 2},
    }
    assert (
        client.post(f"{PZ}/aseguradoras", json=bad | {"nombre": "Seguros"}, headers=h).status_code
        == 422
    )
    a = _aseguradora(client, h)
    assert a["tipos"][0]["coberturas"] == ["can", "adm"] and a["agregada"].startswith("Valeria")
    dup = {"nombre": "seguros uno", "dias_max": 30, "poliza": {"nombre": "B", "precio_pct": 2}}
    assert client.post(f"{PZ}/aseguradoras", json=dup, headers=h).status_code == 409
    ok(
        client.post(
            f"{PZ}/aseguradoras/{a['id']}/tipos",
            json={"nombre": "Completa", "precio_pct": 3.1},
            headers=h,
        ),
        201,
    )
    assert (
        client.post(
            f"{PZ}/aseguradoras/{a['id']}/tipos",
            json={"nombre": "básica", "precio_pct": 2},
            headers=h,
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"{PZ}/aseguradoras/{a['id']}", json={"dias_max": 30, "aviso_dias": 40}, headers=h
        ).status_code
        == 422
    )
    r = ok(
        client.patch(
            f"{PZ}/aseguradoras/{a['id']}", json={"dias_max": 60, "aviso_dias": 5}, headers=h
        )
    )
    assert (r["dias_max"], r["aviso_dias"]) == (60, 5)
    # Used by a policy → can't be deleted, only deactivated
    c = _cierre(db, p["ase"])
    ok(
        client.post(
            PZ,
            json={"cierre_id": str(c.id), "tipo_id": a["tipos"][0]["id"], "canon": 1_500_000},
            headers=h,
        ),
        201,
    )
    r = client.delete(f"{PZ}/aseguradoras/{a['id']}", headers=h)
    assert r.status_code == 409 and "desactivarla" in r.json()["detail"]
    ok(client.patch(f"{PZ}/aseguradoras/{a['id']}", json={"activa": False}, headers=h))
    assert a["id"] not in [
        x["id"] for x in ok(client.get(f"{PZ}/opciones", headers=h))["aseguradoras"]
    ]
    # An unused one is deleted, keeping who and when
    b = _aseguradora(client, h, "Seguros Dos")
    ok(client.delete(f"{PZ}/aseguradoras/{b['id']}", headers=h), 204)
    v = ok(client.get(f"{PZ}/aseguradoras", headers=h))
    assert "Seguros Dos" not in [x["nombre"] for x in v["items"]]
    assert (
        v["eliminadas"][0]["nombre"] == "Seguros Dos" and "por Valeria" in v["eliminadas"][0]["txt"]
    )


def test_flow_alerts_and_recovery(client, p, H, reloj, db):
    h = H(p["aux"])
    a = _aseguradora(client, h, dias=45, aviso=10)
    tipo = a["tipos"][0]["id"]
    venta = _cierre(db, p["ase"], TipoNegocio.VENTA)
    r = client.post(
        PZ, json={"cierre_id": str(venta.id), "tipo_id": tipo, "canon": 1_500_000}, headers=h
    )
    assert r.status_code == 422 and "ventas no llevan póliza" in r.json()["detail"]
    c = _cierre(db, p["ase"])
    negocios = ok(client.get(f"{PZ}/opciones", headers=h))["negocios"]
    assert str(c.id) in [n["id"] for n in negocios] and str(venta.id) not in [
        n["id"] for n in negocios
    ]
    pol = ok(
        client.post(
            PZ,
            json={
                "cierre_id": str(c.id),
                "tipo_id": tipo,
                "canon": 2_000_000,
                "radicado": "RAD-1",
                "estudio_fecha": str(HOY - timedelta(days=50)),
            },
            headers=h,
        ),
        201,
    )
    assert (pol["estado_txt"], pol["costo_mes"]) == ("En estudio", 50_000)
    assert (
        client.post(
            PZ, json={"cierre_id": str(c.id), "tipo_id": tipo, "canon": 2_000_000}, headers=h
        ).status_code
        == 409
    )
    u = f"{PZ}/{pol['id']}"
    assert client.post(f"{u}/retomar", json={"motivo": "x"}, headers=h).status_code == 409
    assert client.post(f"{u}/decidir", json={"aprobada": False}, headers=h).status_code == 422
    r = ok(
        client.post(
            f"{u}/decidir", json={"aprobada": False, "motivo": "Codeudor sin ingresos"}, headers=h
        )
    )
    assert r["estado"] == "negada" and r["puede_retomar"]
    r = ok(client.post(f"{u}/retomar", json={"motivo": "Cambió el codeudor"}, headers=h))
    assert (r["estado"], r["estudios"]) == ("en_estudio", 2)
    r = ok(client.post(f"{u}/decidir", json={"aprobada": True}, headers=h))
    assert r["recuperada"] is True and r["estado_txt"] == "Aprobada · falta la firma"
    # G-034: the asesor who closed it is told
    av = ok(client.get("/api/v1/avisos", params={"vista": "resumen"}, headers=H(p["ase"])))["items"]
    assert any(x["titulo"] == f"Se aprobó la póliza del arriendo {c.code}" for x in av)
    # Signed 40 days ago with a 45-day deadline and a 10-day warning → por vencer
    assert (
        client.post(
            f"{u}/activar", json={"fecha": "2026-10-03", "numero": "P-1"}, headers=h
        ).status_code
        == 409
    )
    assert client.post(f"{u}/firma", json={"fecha": "2026-10-10"}, headers=h).status_code == 422
    ok(client.post(f"{u}/firma", json={"fecha": str(HOY - timedelta(days=40))}, headers=h))
    t = ok(client.get(PZ, headers=h))
    assert [(x["negocio"], x["alerta"]["st"], x["alerta"]["falta"]) for x in t["alertas"]] == [
        (c.code, "p", 5)
    ]

    def titulos(u_):
        return [x["titulo"] for x in ok(client.get("/api/v1/avisos", headers=H(u_)))["items"]]

    assert any(x.startswith("Póliza por activar") for x in titulos(p["aux"]))
    assert not any("Póliza" in x for x in titulos(p["ger"]))  # Gerencia only gets the expired ones
    reloj["now"] = NOW + timedelta(days=7)
    t = ok(client.get(PZ, headers=h))
    assert (t["kpis"]["vencidas"], t["alertas"][0]["alerta"]["falta"]) == (1, -2)
    assert any(x.startswith("Póliza vencida sin activar") for x in titulos(p["ger"]))
    # Activate → «Contratos activos», alert off
    assert (
        client.post(
            f"{u}/activar", json={"fecha": "2026-10-09", "numero": " "}, headers=h
        ).status_code
        == 422
    )
    r = ok(
        client.post(
            f"{u}/activar",
            json={"fecha": "2026-10-09", "numero": "POL-77", "soporte": True},
            headers=h,
        )
    )
    assert r["estado"] == "activa" and r["historial"][0]["despues"].endswith("fuera del plazo")
    t = ok(client.get(PZ, params={"desde": "2026-10-01", "hasta": "2026-10-31"}, headers=h))
    assert (
        t["kpis"]["activas"],
        t["kpis"]["costo_mes"],
        t["kpis"]["canon_mes"],
        t["kpis"]["nuevas"],
    ) == (1, 50_000, 2_000_000, 1)
    assert (t["kpis"]["por_activar"], t["kpis"]["recuperadas"], len(t["contratos"])) == (0, 1, 1)
    assert t["por_aseguradora"][0]["activa_desde"] == "2026-10-09"
    # An active one isn't deleted: it's ended
    assert client.post(f"{u}/eliminar", json={"motivo": "error"}, headers=h).status_code == 409
    r = ok(client.post(f"{u}/terminar", json={"fecha": "2026-10-10"}, headers=h))
    assert r["estado_txt"] == "Terminada"
    ok(client.post(f"{u}/eliminar", json={"motivo": "Registro duplicado"}, headers=h), 204)
    assert client.get(u, headers=h).status_code == 404
    # Registro de cambios: Gerencia sees the Pólizas module
    rc = ok(
        client.get(
            "/api/v1/registro-cambios",
            params={"modulo": "Pólizas", "desde": "2026-09-01", "hasta": "2026-12-31"},
            headers=H(p["ger"]),
        )
    )
    acc = {x["accion"] for x in rc["items"]}
    assert {
        "Agregó la aseguradora",
        "Retomó el estudio",
        "Aprobó la póliza · póliza recuperada",
        "Activó la póliza",
        "Eliminó la póliza",
    } <= acc


def test_property_policy_and_comparator(client, p, H, reloj, db):
    from app.models import Inmueble

    h = H(p["ger"])
    a = _aseguradora(client, h, pct=2.0)
    tipo = a["tipos"][0]["id"]
    inm = Inmueble(
        codigo="INM-9001",
        negocio=TipoNegocio.ARRIENDO,
        direccion="Cl 1",
        barrio="Laureles",
        precio=1_600_000,
    )
    venta = Inmueble(
        codigo="INM-9002", negocio=TipoNegocio.VENTA, direccion="Cl 2", precio=500_000_000
    )
    db.add_all([inm, venta])
    db.flush()
    assert (
        client.post(PZ, json={"inmueble_id": str(venta.id), "tipo_id": tipo}, headers=h).status_code
        == 422
    )
    assert client.post(PZ, json={"tipo_id": tipo, "canon": 1_000_000}, headers=h).status_code == 422
    pol = ok(
        client.post(
            PZ,
            json={
                "inmueble_id": str(inm.id),
                "tipo_id": tipo,
                "seguro_inmueble": True,
                "estudio_fecha": "2026-09-20",
            },
            headers=h,
        ),
        201,
    )
    assert (pol["canon"], pol["inmueble"]) == (
        1_600_000,
        "INM-9001 Laureles",
    )  # canon from the property
    u = f"{PZ}/{pol['id']}"
    ok(client.post(f"{u}/decidir", json={"aprobada": True}, headers=h))
    ok(client.post(f"{u}/firma", json={"fecha": "2026-10-01"}, headers=h))
    ok(client.post(f"{u}/activar", json={"fecha": "2026-10-02", "numero": "POL-1"}, headers=h))
    cmp_ = ok(
        client.get(
            f"{PZ}/comparar", params={"desde": "2026-10-01", "hasta": "2026-10-31"}, headers=h
        )
    )
    card = next(x for x in cmp_["cards"] if x["aseguradora"] == "Seguros Uno")
    assert (
        card["activas"],
        card["con_seguro"],
        card["canon_mes"],
        card["aprobacion"],
        card["estudios"],
    ) == (1, 1, 1_600_000, 100, 1)
    assert card["inmuebles"][0]["d"] == "INM-9001 Laureles"
