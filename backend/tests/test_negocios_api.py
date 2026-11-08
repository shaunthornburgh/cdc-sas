"""Negocios (X02 · M16; G-029, G-031, G-033, G-055, G-060, G-087, G-091): access, the signature
flow for rentals and sales, caídas, ganancia and the link with Compensación and Pólizas."""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Cierre, Comision, Lead
from app.models.enums import (
    ActividadComercial,
    Cargo,
    EstadoCompensacion,
    EtapaLead,
    FuenteLead,
    FuncionIndependiente,
    TipoNegocio,
)
from app.services import fechas
from tests.conftest import auth_header, login

NG = "/api/v1/negocios"
AV = "/api/v1/avisos"
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
        "juan": make_user(
            Cargo.ASESOR,
            email="juan@example.com",
            full_name="Juan Asesor",
            actividades=[ActividadComercial.VENTAS, ActividadComercial.ARRIENDOS],
        ),
        "ana": make_user(
            Cargo.ASESOR,
            email="ana@example.com",
            full_name="Ana Asesora",
            actividades=[ActividadComercial.VENTAS],
        ),
        "aten": make_user(
            Cargo.ATENCION_CLIENTE,
            email="aten@example.com",
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
    return res.json() if res.content else None


def err(res, code, texto=""):
    assert res.status_code == code, res.text
    assert texto in res.json()["detail"], res.json()["detail"]


def _cierre(db, asesor, negocio=TipoNegocio.ARRIENDO, dias=5, nombre="Cliente Uno"):
    when = NOW - timedelta(days=dias)
    ld = Lead(
        full_name=nombre,
        phone="3000000000",
        fuente=FuenteLead.OTRO,
        etapa=EtapaLead.GANADO,
        negocio=negocio,
        busca="Apartamento en Belén",
        cerrado_at=when,
    )
    db.add(ld)
    db.flush()
    c = Cierre(lead_id=ld.id, negocio=negocio, cerrado_at=when, cerrador_id=asesor.id)
    db.add(c)
    db.flush()
    return c


def _item(client, h, c, **q):
    data = ok(client.get(NG, params={"desde": "2026-01-01", **q}, headers=h))
    return next(i for i in data["items"] if i["id"] == str(c.id))


def _tipos_aviso(client, h, vista="por_atender"):
    return [a["tipo"] for a in ok(client.get(AV, params={"vista": vista}, headers=h))["items"]]


def test_access_and_money_visibility(client, p, H, reloj, db):
    mio = _cierre(db, p["juan"])
    otro = _cierre(db, p["ana"], TipoNegocio.VENTA, nombre="Cliente Dos")
    assert client.get(NG, headers=H(p["aten"])).status_code == 403
    # The asesor sees only the deals they close, and no money
    a = ok(client.get(NG, headers=H(p["juan"])))
    assert a["modo"] == "asesor" and [i["id"] for i in a["items"]] == [str(mio.id)]
    assert "ganancia" not in a["items"][0]
    assert client.get(f"{NG}/{otro.id}", headers=H(p["juan"])).status_code == 404
    # Coordinación: everything, read-only, without money
    co = ok(client.get(NG, headers=H(p["coord"])))
    assert co["modo"] == "coordinacion" and len(co["items"]) == 2
    assert (
        "ganancia" not in co["kpis"] and "ganancias" not in co and "ganancia" not in co["items"][0]
    )
    assert co["puede"] == {"gestionar": False, "datos": False}
    err(client.patch(f"{NG}/{mio.id}", json={"valor": 1}, headers=H(p["coord"])), 403)
    # Gerencia edits data but doesn't confirm signatures; the Auxiliar does everything
    g = ok(client.get(NG, headers=H(p["ger"])))
    assert g["puede"] == {"gestionar": False, "datos": True} and "ganancia" in g["kpis"]
    ok(client.patch(f"{NG}/{mio.id}", json={"valor": 1_600_000}, headers=H(p["ger"])))
    err(
        client.post(f"{NG}/{mio.id}/confirmar", json={"fecha": str(HOY)}, headers=H(p["ger"])),
        403,
        "Auxiliar",
    )
    assert ok(client.get(NG, headers=H(p["aux"])))["puede"]["gestionar"] is True
    # Only the asesor of the deal asks to close it
    err(client.post(f"{NG}/{mio.id}/solicitar", json={}, headers=H(p["aux"])), 403)


def test_rental_flow_ganancia_commissions_and_policy(client, p, H, reloj, db):
    c = _cierre(db, p["juan"])
    ha, hj = H(p["aux"]), H(p["juan"])
    i = _item(client, ha, c)
    assert (i["situacion"], i["categoria"], i["etapa"]) == ("en_proceso", "neg", i["etapas"][0])
    # Data: value, documents and referral → ganancia (G-087)
    d = ok(
        client.patch(
            f"{NG}/{c.id}",
            json={"valor": 1_600_000, "docs_ubicacion": "Carpeta A-12"},
            headers=ha,
        )
    )
    g = d["ganancia"]
    # 20 % + IVA of the canon + papelería $75.000 with IVA; base without IVA = 320.000 + 63.025
    assert g["lineas"][0]["v"] == 455_800 and g["efectiva"] == 383_025 and g["estimadas"]
    assert d["historial"][0]["accion"] == f"Datos de {c.code} actualizados"
    err(client.patch(f"{NG}/{c.id}", json={"pct_venta": 2}, headers=ha), 422, "solo para ventas")
    err(client.patch(f"{NG}/{c.id}", json={"docs_ubicacion": " "}, headers=ha), 422)
    # Stages: observation required, no jumping to the last one
    err(
        client.post(
            f"{NG}/{c.id}/etapa", json={"etapa": "Contrato en firma", "observacion": ""}, headers=hj
        ),
        422,
    )
    err(
        client.post(
            f"{NG}/{c.id}/etapa",
            json={"etapa": "Contrato firmado", "observacion": "firmó"},
            headers=hj,
        ),
        422,
        "Solicitar cierre",
    )
    d = ok(
        client.post(
            f"{NG}/{c.id}/etapa",
            json={
                "etapa": "Contrato en firma",
                "observacion": "Póliza aprobada",
                "oferta": "Canon",
            },
            headers=hj,
        )
    )
    assert d["etapa"] == "Contrato en firma" and d["oferta"].startswith("Canon")
    # Policy approved in «Pólizas», still without the contract signature
    a = ok(
        client.post(
            "/api/v1/polizas/aseguradoras",
            json={
                "nombre": "Seguros Uno",
                "dias_max": 45,
                "poliza": {"nombre": "Básica", "precio_pct": 2},
            },
            headers=ha,
        ),
        201,
    )
    tipo = ok(client.get("/api/v1/polizas/aseguradoras", headers=ha))["items"]
    tipo_id = next(x for x in tipo if x["id"] == str(a["id"]))["tipos"][0]["id"]
    pol = ok(
        client.post(
            "/api/v1/polizas",
            json={
                "cierre_id": str(c.id),
                "tipo_id": tipo_id,
                "canon": 1_600_000,
                "estudio_fecha": "2026-09-30",
            },
            headers=ha,
        ),
        201,
    )
    ok(client.post(f"/api/v1/polizas/{pol['id']}/decidir", json={"aprobada": True}, headers=ha))
    i = _item(client, ha, c)
    assert i["poliza"]["estado"] == "aprobada"
    assert i["ganancia"]["lineas"][3]["v"] == -32_000  # 2 % of the canon, one month
    # Ask → return with reason → ask again
    d = ok(client.post(f"{NG}/{c.id}/solicitar", json={"nota": "Firmó hoy"}, headers=hj))
    assert d["situacion"] == "por_confirmar" and d["categoria"] == "pc"
    err(client.post(f"{NG}/{c.id}/solicitar", json={}, headers=hj), 409)
    assert "negocio_por_confirmar" in _tipos_aviso(client, ha)
    d = ok(client.post(f"{NG}/{c.id}/devolver", json={"motivo": "Falta un documento"}, headers=ha))
    assert d["situacion"] == "en_proceso" and d["devuelto_motivo"] == "Falta un documento"
    assert "negocio_devuelto" in _tipos_aviso(client, hj)
    assert "negocio_por_confirmar" not in _tipos_aviso(client, ha)
    ok(client.post(f"{NG}/{c.id}/solicitar", json={}, headers=hj))
    # Confirm: no future dates; then closed → ganancia to Compensación, commissions, policy
    err(
        client.post(f"{NG}/{c.id}/confirmar", json={"fecha": "2026-10-04"}, headers=ha),
        422,
        "futura",
    )
    d = ok(
        client.post(
            f"{NG}/{c.id}/confirmar",
            json={"fecha": "2026-10-02", "contrato_adjunto": True},
            headers=ha,
        )
    )
    assert d["resultado"] == {"cerrado": True, "comisiones": True, "poliza": True}
    assert (d["situacion"], d["etapa"], d["contrato_adjunto"]) == (
        "cerrado",
        "Contrato firmado",
        True,
    )
    assert d["ganancia_efectiva"] == 383_025 and not d["ganancia"]["estimadas"]
    coms = list(db.scalars(select(Comision).where(Comision.cierre_id == c.id)))
    assert [x.beneficiario_id for x in coms] == [p["juan"].id] and coms[0].valor == 89_283
    assert d["poliza"]["firma_fecha"] == "2026-10-02"
    assert "negocio_cerrado" in _tipos_aviso(client, hj, "resumen")
    # A closed deal doesn't move any more; a referral recalculates the commissions
    err(
        client.post(f"{NG}/{c.id}/caida", json={"motivo": "Otro", "observacion": "x"}, headers=hj),
        409,
    )
    d = ok(client.patch(f"{NG}/{c.id}", json={"referido": "Cliente Ejemplo 30"}, headers=ha))
    assert d["ganancia_efectiva"] == 223_025
    db.refresh(coms[0])
    assert coms[0].valor == round(223_025 * 23.31 / 100)


def test_sale_two_signatures_notary_and_money_received(client, p, H, reloj, db):
    c = _cierre(db, p["ana"], TipoNegocio.VENTA)
    ha, hn = H(p["aux"]), H(p["ana"])
    ok(client.patch(f"{NG}/{c.id}", json={"valor": 400_000_000, "pct_venta": 2.5}, headers=ha))
    err(client.patch(f"{NG}/{c.id}", json={"uso_comercial": True}, headers=ha), 422, "arriendos")
    err(client.patch(f"{NG}/{c.id}", json={"pct_venta": 30}, headers=ha), 422)
    ok(
        client.post(
            f"{NG}/{c.id}/etapa",
            json={"etapa": "Promesa firmada", "observacion": "Firmaron la promesa"},
            headers=hn,
        )
    )
    d = ok(client.post(f"{NG}/{c.id}/solicitar", json={}, headers=hn))
    assert d["solicitud"] == "promesa" and d["estado_txt"] == "Firma de promesa por confirmar"
    d = ok(client.post(f"{NG}/{c.id}/confirmar", json={"fecha": "2026-10-01"}, headers=ha))
    assert d["resultado"]["cerrado"] is False
    assert (d["situacion"], d["categoria"], d["promesa_fecha"]) == (
        "en_proceso",
        "pc",
        "2026-10-01",
    )
    assert d["paso_promesa"] is False
    # Escrituración needs the notary appointment (G-031)
    body = {"etapa": "Escrituración", "observacion": "Documentos listos"}
    err(client.post(f"{NG}/{c.id}/etapa", json=body, headers=hn), 422, "notaría")
    d = ok(
        client.post(
            f"{NG}/{c.id}/etapa",
            json=body | {"notaria": "Notaría 2", "notaria_at": "2026-10-04T10:00:00"},
            headers=hn,
        )
    )
    assert d["notaria"] == "Notaría 2" and "negocio_notaria" in _tipos_aviso(client, hn)
    # Money received (G-033)
    err(
        client.post(
            f"{NG}/{c.id}/abonos",
            json={"valor": 1, "fecha": "2026-10-01", "momento": "luna"},
            headers=ha,
        ),
        422,
    )
    d = ok(
        client.post(
            f"{NG}/{c.id}/abonos",
            json={"valor": 40_000_000, "fecha": "2026-10-01", "momento": "promesa"},
            headers=ha,
        ),
        201,
    )
    assert d["recibido"] == 40_000_000 and d["abonos"][0]["momento_txt"] == "En la promesa"
    # Escritura before the promesa → 422; then closed with 2,5 % of the price
    ok(client.post(f"{NG}/{c.id}/solicitar", json={}, headers=hn))
    err(client.post(f"{NG}/{c.id}/confirmar", json={"fecha": "2026-09-01"}, headers=ha), 422)
    d = ok(client.post(f"{NG}/{c.id}/confirmar", json={"fecha": "2026-10-03"}, headers=ha))
    assert (d["situacion"], d["etapa"]) == ("cerrado", "Escriturada")
    assert d["ganancia_efectiva"] == 10_000_000 and d["ganancia"]["lineas"][0]["v"] == 11_900_000


def test_caida_reported_dismissed_and_confirmed(client, p, H, reloj, db):
    c = _cierre(db, p["juan"])
    venta = _cierre(db, p["juan"], TipoNegocio.VENTA, nombre="Cliente Dos")
    ha, hj = H(p["aux"]), H(p["juan"])
    body = {"motivo": "Póliza negada", "observacion": "La aseguradora la negó"}
    err(client.post(f"{NG}/{venta.id}/caida", json=body, headers=hj), 422, "solo a arriendos")
    err(
        client.post(f"{NG}/{c.id}/caida", json={"motivo": "x", "observacion": "y"}, headers=hj), 422
    )
    d = ok(client.post(f"{NG}/{c.id}/caida", json=body, headers=hj))
    assert d["resultado"] == "reportada" and d["situacion"] == "en_proceso"
    assert d["estado_txt"] == "Caída reportada por el asesor"
    k = ok(client.get(NG, headers=ha))["kpis"]
    assert k["cai_reportadas"] == 1 and k["cai"] == 0
    err(client.post(f"{NG}/{c.id}/confirmar", json={"fecha": str(HOY)}, headers=ha), 409)
    ok(client.post(f"{NG}/{c.id}/caida/descartar", headers=ha))
    # A commission registered by hand in Compensación is cancelled when the caída is confirmed
    ok(
        client.put(
            f"/api/v1/compensacion/cierres/{c.id}",
            json={"ganancia": 1_000_000, "captador_id": None},
            headers=ha,
        )
    )
    ok(client.post(f"{NG}/{c.id}/caida", json=body, headers=hj))
    d = ok(client.post(f"{NG}/{c.id}/caida", json=body, headers=ha))
    assert d["resultado"] == "confirmada" and d["situacion"] == "caido"
    assert d["ganancia"]["neta"] == 0
    com = db.scalar(select(Comision).where(Comision.cierre_id == c.id))
    db.refresh(com)
    assert com.estado == EstadoCompensacion.ANULADA
    # The lead is still «Ganado», but the sync doesn't reopen it
    i = _item(client, ha, c)
    assert i["situacion"] == "caido" and i["categoria"] == "cai"
    assert "negocio_caido" in _tipos_aviso(client, hj, "resumen")
    assert "negocio_caido" in _tipos_aviso(client, H(p["ger"]), "resumen")
    err(client.patch(f"{NG}/{c.id}", json={"valor": 1_000_000}, headers=ha), 409)


def test_indicators_range_and_type(client, p, H, reloj, db):
    a = _cierre(db, p["juan"], dias=3)
    b = _cierre(db, p["ana"], TipoNegocio.VENTA, dias=40, nombre="Cliente Dos")
    ha = H(p["aux"])
    ok(client.patch(f"{NG}/{a.id}", json={"valor": 2_000_000}, headers=ha))
    ok(client.patch(f"{NG}/{b.id}", json={"valor": 300_000_000}, headers=ha))
    d = ok(client.get(NG, params={"desde": "2026-08-01", "hasta": "2026-10-03"}, headers=ha))
    assert d["kpis"]["total"] == 2 and d["kpis"]["neg"] == 2 and d["counts"]["proc"] == 2
    assert [g["code"] for g in d["ganancias"]][0] == b.code  # sorted by ganancia
    assert {t["tipo"]: t["n"] for t in d["por_tipo"]} == {"arriendo": 1, "venta": 1}
    d = ok(client.get(NG, params={"desde": "2026-08-01", "tipo": "venta"}, headers=ha))
    assert [i["id"] for i in d["items"]] == [str(b.id)]
    d = ok(client.get(NG, params={"desde": "2026-09-30", "hasta": "2026-10-03"}, headers=ha))
    assert [i["id"] for i in d["items"]] == [str(a.id)]
    err(client.get(NG, params={"desde": "2026-10-05", "hasta": "2026-10-01"}, headers=ha), 422)
    # Detail with its history (who changed what)
    h = ok(client.get(f"{NG}/{a.id}", headers=ha))["historial"]
    assert h[0]["por"] == "Valeria" and "$2.000.000" in h[0]["detalle"]
