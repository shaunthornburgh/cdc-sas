from datetime import timedelta

import pytest

from app.models import Cita, Lead
from app.models.enums import ActividadComercial as A
from app.models.enums import (
    Cargo,
    EstadoCita,
    EtapaLead,
    FuenteLead,
    FuncionIndependiente,
    TipoCita,
    TipoNegocio,
)
from app.services import compensacion as svc
from app.services import rendimiento as rend
from tests.conftest import auth_header, login

C = "/api/v1/compensacion"


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Vale Aux"
        ),
        "juan": make_user(
            email="juan@example.com", full_name="Juan Asesor", actividades=[A.VENTAS, A.ARRIENDOS]
        ),
        "bruno": make_user(
            email="bruno@example.com", full_name="Bruno Capta", actividades=[A.CAPTACION]
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


def ganado(db, when, *, asesor, filtro=None, negocio=TipoNegocio.VENTA):
    lead = Lead(
        full_name="Cliente Ganado",
        phone="3000000000",
        fuente=FuenteLead.OTRO,
        negocio=negocio,
        etapa=EtapaLead.GANADO,
        cerrado_at=when,
        assigned_to_id=filtro.id if filtro else None,
    )
    db.add(lead)
    db.flush()
    db.add(
        Cita(
            lead_id=lead.id,
            tipo=TipoCita.VISITA_VENTA,
            scheduled_at=when,
            asesor_id=asesor.id,
            estado=EstadoCita.REALIZADA,
        )
    )
    db.flush()
    return lead


@pytest.fixture
def T():
    return rend.periodo().start + timedelta(minutes=5)


def tablero(client, H, who):
    res = client.get(C, headers=H(who))
    assert res.status_code == 200, res.text
    return res.json()


def coms(data, quien=None):
    return [
        c for c in data["comisiones"] if quien is None or c["beneficiario"]["full_name"] == quien
    ]


# ---------------------------------------------------------------- access


def test_access(client, p, H):
    for k in ("juan", "laura", "coord", "aux"):
        assert client.get(f"{C}/mio", headers=H(p[k])).status_code == 200
    for k in ("juan", "laura", "coord"):  # Coordinación sees only its own (DECISIONS)
        assert client.get(C, headers=H(p[k])).status_code == 403
        assert client.get(f"{C}/salarios", headers=H(p[k])).status_code == 403
    assert client.get(C, headers=H(p["aux"])).status_code == 200
    assert client.get(C, headers=H(p["ger"])).status_code == 200


# ---------------------------------------------------------------- deals → commissions


def test_deal_generates_commissions(client, db, p, H, T):
    ganado(db, T, asesor=p["juan"], filtro=p["laura"])
    neg = tablero(client, H, p["aux"])["cierres"][0]
    assert neg["code"].startswith("NEG-")
    assert (neg["cerrador"]["full_name"], neg["filtro"]["full_name"], neg["ganancia"]) == (
        "Juan Asesor",
        "Laura Atención",
        None,
    )
    assert coms(tablero(client, H, p["aux"])) == []  # no ganancia yet → nothing to pay

    url = f"{C}/cierres/{neg['id']}"
    assert client.put(url, json={"ganancia": 0}, headers=H(p["aux"])).status_code == 422
    assert client.put(url, json={"ganancia": 10_000_000}, headers=H(p["juan"])).status_code == 403
    assert (
        client.put(
            url,
            json={"ganancia": 10_000_000, "captador_id": str(p["laura"].id)},
            headers=H(p["aux"]),
        ).status_code
        == 422
    )
    assert client.put(url, json={"ganancia": 10_000_000}, headers=H(p["aux"])).status_code == 200
    data = tablero(client, H, p["ger"])
    # 10.000.000 × 33,3 % × 70 % = 2.331.000 · filtro 5 % = 500.000 · no captador yet.
    assert {(c["beneficiario"]["full_name"], c["tipo"], c["valor"]) for c in coms(data)} == {
        ("Juan Asesor", "cerrador", 2_331_000),
        ("Laura Atención", "filtro", 500_000),
    }
    # Adding the captador generates its share (30 % of the staff's 33,3 %).
    client.put(
        url, json={"ganancia": 10_000_000, "captador_id": str(p["bruno"].id)}, headers=H(p["ger"])
    )
    bruno = coms(tablero(client, H, p["ger"]), "Bruno Capta")[0]
    assert (bruno["tipo"], bruno["valor"], bruno["estado"]) == ("captador", 999_000, "generada")
    assert "ganancia $10.000.000 × 9,99 %" in bruno["detalle"]


def test_approval_flow_and_my_view(client, db, p, H, T):
    ganado(db, T, asesor=p["juan"])
    neg = tablero(client, H, p["aux"])["cierres"][0]
    client.put(f"{C}/cierres/{neg['id']}", json={"ganancia": 6_000_000}, headers=H(p["aux"]))
    com = coms(tablero(client, H, p["aux"]), "Juan Asesor")[0]
    url = f"{C}/comisiones/{com['id']}/accion"

    assert (
        client.post(url, json={"accion": "aprobar"}, headers=H(p["ger"])).status_code == 422
    )  # needs visto bueno
    assert (
        client.post(url, json={"accion": "visto_bueno"}, headers=H(p["ger"])).status_code == 403
    )  # Auxiliar's
    assert (
        client.post(url, json={"accion": "visto_bueno"}, headers=H(p["aux"])).json()["estado"]
        == "visto_bueno"
    )
    assert client.post(url, json={"accion": "aprobar"}, headers=H(p["aux"])).status_code == 403
    ap = client.post(url, json={"accion": "aprobar"}, headers=H(p["ger"])).json()
    assert ap["estado"] == "pendiente_pago"
    nxt = rend.periodo().siguiente_first()
    assert ap["se_paga"] == f"5 {svc.MES_CORTO[nxt.month - 1]}"
    pago = tablero(client, H, p["ger"])["pagos"][0]
    assert (pago["estado"], pago["valor"], pago["fecha_programada"]) == (
        "en_proceso",
        com["valor"],
        nxt.replace(day=5).isoformat(),
    )
    # Can't adjust after Gerencia approved.
    assert (
        client.post(
            url, json={"accion": "ajustar", "valor": 1, "motivo": "x x x"}, headers=H(p["ger"])
        ).status_code
        == 422
    )
    assert client.post(f"{C}/pagos/{pago['id']}/pagar", headers=H(p["aux"])).status_code == 403
    assert (
        client.post(f"{C}/pagos/{pago['id']}/pagar", headers=H(p["ger"])).json()["estado"]
        == "pagado"
    )
    assert coms(tablero(client, H, p["ger"]), "Juan Asesor")[0]["estado"] == "pagada"

    mine = client.get(f"{C}/mio", headers=H(p["juan"])).json()
    item = next(i for i in mine["items"] if i["clase"] == "comision")
    assert (item["estado_txt"], item["valor"]) == ("Pagada", 6_000_000 * 333 * 70 // 100_000)
    assert mine["pagos"][0]["estado_txt"] == "Pagado"
    assert mine["kpis"]["pagado"] == item["valor"]
    hist = client.get(f"{C}/historial/comision/{com['id']}", headers=H(p["ger"])).json()
    assert [h["accion"].split(" ·")[0] for h in hist] == [
        "Comisión generada",
        "Visto bueno de la Auxiliar",
        "Aprobada por Gerencia",
        "Pago registrado por Gerencia",
    ]


def test_adjust_and_cancel(client, db, p, H, T):
    ganado(db, T, asesor=p["juan"])
    neg = tablero(client, H, p["aux"])["cierres"][0]
    client.put(f"{C}/cierres/{neg['id']}", json={"ganancia": 3_000_000}, headers=H(p["aux"]))
    com = coms(tablero(client, H, p["aux"]))[0]
    url = f"{C}/comisiones/{com['id']}/accion"
    client.post(url, json={"accion": "visto_bueno"}, headers=H(p["aux"]))
    # With a visto bueno, changing the deal's profit is refused: adjust each commission instead.
    assert (
        client.put(
            f"{C}/cierres/{neg['id']}", json={"ganancia": 4_000_000}, headers=H(p["aux"])
        ).status_code
        == 422
    )
    assert (
        client.post(
            url, json={"accion": "ajustar", "valor": 700_000}, headers=H(p["ger"])
        ).status_code
        == 422
    )
    adj = client.post(
        url,
        json={"accion": "ajustar", "valor": 700_000, "motivo": "Se pactó otro valor"},
        headers=H(p["ger"]),
    ).json()
    assert (adj["valor"], adj["estado"]) == (700_000, "generada")  # needs a new visto bueno
    assert client.post(url, json={"accion": "anular"}, headers=H(p["aux"])).status_code == 422
    assert (
        client.post(url, json={"accion": "anular", "motivo": "Error"}, headers=H(p["aux"])).json()[
            "estado"
        ]
        == "anulada"
    )


def test_lost_deal_cancels_unpaid_commissions(client, db, p, H, T):
    lead = ganado(db, T, asesor=p["juan"])
    neg = tablero(client, H, p["aux"])["cierres"][0]
    client.put(f"{C}/cierres/{neg['id']}", json={"ganancia": 3_000_000}, headers=H(p["aux"]))
    lead.etapa = EtapaLead.PERDIDO
    db.flush()
    data = tablero(client, H, p["aux"])
    assert data["cierres"][0]["estado"] == "caido"
    assert coms(data)[0]["estado"] == "anulada"
    assert (
        client.put(
            f"{C}/cierres/{neg['id']}", json={"ganancia": 1}, headers=H(p["aux"])
        ).status_code
        == 422
    )


def test_manual_records(client, p, H):
    body = {"beneficiario_id": str(p["juan"].id), "concepto": "Bono por referido", "valor": 150_000}
    assert client.post(f"{C}/bonos", json=body, headers=H(p["coord"])).status_code == 403
    assert (
        client.post(f"{C}/bonos", json=body | {"valor": 0}, headers=H(p["aux"])).status_code == 422
    )
    b = client.post(f"{C}/bonos", json=body, headers=H(p["aux"])).json()
    assert (b["tipo"], b["estado_txt"]) == ("manual", "Generado")
    assert (
        client.post(
            f"{C}/comisiones", json=body | {"concepto": "Comisión acordada"}, headers=H(p["ger"])
        ).status_code
        == 201
    )
    assert client.post(f"{C}/inventado", json=body, headers=H(p["ger"])).status_code == 404


# ---------------------------------------------------------------- month-end


def test_month_end_bonuses_and_group_commission(client, db, p, H):
    prev = rend.periodo().anterior()
    when = prev.start + timedelta(days=3)
    lead = ganado(db, when, asesor=p["juan"], filtro=p["laura"])
    assert (
        client.post(
            f"{C}/calcular", params={"periodo": rend.periodo().key}, headers=H(p["ger"])
        ).status_code
        == 422
    )
    neg = tablero(client, H, p["ger"])["cierres"][0]
    client.put(f"{C}/cierres/{neg['id']}", json={"ganancia": 25_000_000}, headers=H(p["ger"]))
    assert lead.id  # deal counted in last month
    cfg = {"bono_umbral": 0, "bono_monto": 100_000, "meta_grupal": 20_000_000}
    assert client.put(f"{C}/config", json={"valores": cfg}, headers=H(p["aux"])).status_code == 403
    assert (
        client.put(
            f"{C}/config", json={"valores": {"reparto_cerrador": 80}}, headers=H(p["ger"])
        ).status_code
        == 422
    )
    assert client.put(f"{C}/config", json={"valores": cfg}, headers=H(p["ger"])).status_code == 200

    out = client.post(f"{C}/calcular", params={"periodo": prev.key}, headers=H(p["aux"])).json()
    assert out["grupal"] == 1 and out["bonos"] >= 3
    data = tablero(client, H, p["ger"])
    grupal = next(c for c in data["comisiones"] if c["tipo"] == "grupal")
    assert (grupal["beneficiario"]["full_name"], grupal["valor"]) == (
        "Mateo Coord",
        625_000,
    )  # 2,5 % × 25 M
    assert {b["beneficiario"]["full_name"] for b in data["bonos"]} >= {
        "Juan Asesor",
        "Laura Atención",
        "Mateo Coord",
    }
    # Running it again doesn't duplicate.
    assert client.post(
        f"{C}/calcular", params={"periodo": prev.key}, headers=H(p["ger"])
    ).json() == {"bonos": 0, "grupal": 0}


# ---------------------------------------------------------------- salaries


def test_salary_flow(client, p, H):
    url = f"{C}/salarios/config/{p['juan'].id}"
    assert (
        client.put(url, json={"salario_mensual": 1_800_000}, headers=H(p["aux"])).status_code == 403
    )
    assert (
        client.put(url, json={"salario_mensual": 1_800_000}, headers=H(p["ger"])).status_code == 200
    )
    s = client.get(f"{C}/salarios", params={"corte": 1}, headers=H(p["aux"])).json()
    fila = s["filas"][0]
    assert (fila["user"]["full_name"], fila["salario_corte"], fila["a_pagar"], fila["estado"]) == (
        "Juan Asesor",
        900_000,
        900_000,
        "por_confirmar",
    )
    assert "Laura Atención" in {x["full_name"] for x in s["sin_salario"]}
    acc = f"{C}/salarios/accion"
    assert (
        client.post(
            acc, json={"accion": "pagar", "ids": [fila["id"]]}, headers=H(p["ger"])
        ).status_code
        == 422
    )  # not confirmed
    assert (
        client.post(
            acc, json={"accion": "confirmar", "ids": [fila["id"]]}, headers=H(p["ger"])
        ).status_code
        == 403
    )
    assert (
        client.post(
            acc, json={"accion": "confirmar", "ids": [fila["id"]]}, headers=H(p["aux"])
        ).status_code
        == 200
    )
    assert (
        client.post(
            acc, json={"accion": "pagar", "ids": [fila["id"]]}, headers=H(p["ger"])
        ).status_code
        == 200
    )
    mine = client.get(f"{C}/mio", headers=H(p["juan"])).json()
    sal = next(
        i
        for i in mine["items"]
        if i["clase"] == "salario" and i["concepto"].startswith("Salario · 1.er")
    )
    assert sal["estado_txt"] == "Pagado"
    assert any(x["tipo"] == "salario" and x["valor"] == 900_000 for x in mine["pagos"])
    assert mine["como_ganas"][0]["detalle"].startswith("$1.800.000 al mes")
