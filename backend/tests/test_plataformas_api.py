"""Plataformas tradicionales (K15 / K15-ger): updates, plans, responsable, results, history."""

from datetime import date, datetime, timedelta

import pytest

from app.models import Cita, Lead, Plataforma
from app.models.enums import ActividadComercial as A
from app.models.enums import (
    Cargo,
    EstadoCita,
    EtapaLead,
    FuenteLead,
    FuncionIndependiente,
    TipoCita,
)
from app.services import fechas
from app.services import plataformas as svc
from app.services import rendimiento as rend
from tests.conftest import auth_header, login

PL = "/api/v1/plataformas"
NOW = datetime(2026, 10, 3, 11, 0, tzinfo=fechas.BOGOTA)


@pytest.fixture(autouse=True)
def reloj(monkeypatch):
    state = {"now": NOW}
    monkeypatch.setattr(fechas, "now", lambda: state["now"])
    return state


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Vale Aux"
        ),
        "juan": make_user(email="juan@example.com", full_name="Juan", actividades=[A.CAPTACION]),
        "laura": make_user(
            Cargo.ATENCION_CLIENTE,
            email="laura@example.com",
            full_name="Laura",
            funcion=FuncionIndependiente.ATENCION_CLIENTE,
        ),
    }


@pytest.fixture
def plats(db):
    out = {}
    for i, (f, n) in enumerate(
        [(FuenteLead.CIENCUADRAS, "Ciencuadras"), (FuenteLead.PROPPI, "Proppi")]
    ):
        x = Plataforma(fuente=f, nombre=n, orden=i, color="#00843D")
        db.add(x)
        out[f.value] = x
    db.flush()
    return out


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


PLAN = {
    "precio": 920_000,
    "activacion": "2026-07-15",
    "vencimiento": "2026-10-14",  # 92 days → $10.000 a day
    "cupo_total": 40,
    "destacados_total": 5,
    "alarma_dias": 10,
}


def actualizar(client, H, who, pl, usado=32, total=40, dest=3, **kw):
    body = {"cupo_usado": usado, "cupo_total": total, "destacados_usados": dest} | kw
    return client.post(f"{PL}/{pl.id}/actualizaciones", json=body, headers=H(who))


def fila(t, nombre):
    return next(x for x in t["plataformas"] if x["nombre"] == nombre)


# ---------------------------------------------------------------- access


def test_access(client, p, plats, H):
    for k in ("ger", "coord", "aux"):
        assert client.get(PL, headers=H(p[k])).status_code == 200, k
    for k in ("juan", "laura"):
        assert client.get(PL, headers=H(p[k])).status_code == 403, k
    o = ok(client.get(f"{PL}/opciones", headers=H(p["ger"])))
    assert o["gerencia"] is True
    assert {r["full_name"] for r in o["responsables"]} == {"Mateo Coord", "Vale Aux"}
    oc = ok(client.get(f"{PL}/opciones", headers=H(p["coord"])))
    assert (oc["gerencia"], oc["puede_descargar"]) == (False, True)
    oa = ok(client.get(f"{PL}/opciones", headers=H(p["aux"])))
    assert oa["puede_descargar"] is False
    assert client.get(f"{PL}/historico.csv", headers=H(p["aux"])).status_code == 403


# ---------------------------------------------------------------- plans and responsable


def test_plans_and_responsable(client, p, plats, H, db):
    cien = plats["ciencuadras"]
    assert (
        client.post(f"{PL}/{cien.id}/planes", json=PLAN, headers=H(p["coord"])).status_code == 403
    )
    bad = PLAN | {"vencimiento": "2026-07-01"}
    assert client.post(f"{PL}/{cien.id}/planes", json=bad, headers=H(p["ger"])).status_code == 422
    r = ok(client.post(f"{PL}/{cien.id}/planes", json=PLAN, headers=H(p["ger"])), 201)
    # 11 days to expiry, alarm 10 days before → still «Activo»
    assert (r["plan_estado"], r["plan_txt"]) == ("activo", "Activo · vence 14 oct")
    # Correcting the plan with the same activation date doesn't add another
    r = ok(
        client.post(f"{PL}/{cien.id}/planes", json=PLAN | {"alarma_dias": 15}, headers=H(p["ger"])),
        201,
    )
    assert (r["plan_estado"], r["plan_txt"]) == ("por_vencer", "⚠ Vence en 11 días")
    db.refresh(cien)
    assert len(cien.planes) == 1
    # Renewal registered before expiry: no more alarm
    ren = PLAN | {"activacion": "2026-10-15", "vencimiento": "2027-01-14"}
    r = ok(client.post(f"{PL}/{cien.id}/planes", json=ren, headers=H(p["ger"])), 201)
    assert (r["plan_estado"], r["plan_txt"]) == ("renovado", "Renovado · sigue desde 15 oct")
    assert r["plan"]["activacion"] == "2026-07-15"  # the one in force today

    # Responsable: Coordinación or the Auxiliar, chosen by Gerencia
    url = f"{PL}/{cien.id}/responsable"
    body = {"responsable_id": str(p["aux"].id)}
    assert client.put(url, json=body, headers=H(p["coord"])).status_code == 403
    bad = {"responsable_id": str(p["juan"].id)}
    assert client.put(url, json=bad, headers=H(p["ger"])).status_code == 422
    r = ok(client.put(url, json=body, headers=H(p["ger"])))
    assert r["responsable"]["full_name"] == "Vale Aux"
    ch = ok(client.get(f"{PL}/cambios", headers=H(p["coord"])))
    assert (ch[0]["tipo"], ch[0]["antes"], ch[0]["despues"]) == (
        "responsable",
        "Sin asignar",
        "Vale Aux",
    )
    assert ch[1]["tipo"] == "plan"


# ---------------------------------------------------------------- updates


def test_register_update(client, p, plats, H):
    cien, proppi = plats["ciencuadras"], plats["proppi"]
    ok(client.post(f"{PL}/{cien.id}/planes", json=PLAN, headers=H(p["ger"])), 201)
    # Gerencia doesn't register (K15-ger); the Auxiliar only her own portals
    assert actualizar(client, H, p["ger"], cien).status_code == 403
    assert actualizar(client, H, p["aux"], cien).status_code == 403
    assert actualizar(client, H, p["coord"], cien, usado=41).status_code == 422
    assert actualizar(client, H, p["coord"], cien, dest=6).status_code == 422  # plan has 5
    # No plan: the featured total is needed
    assert actualizar(client, H, p["coord"], proppi, usado=6, total=10, dest=1).status_code == 422
    ok(
        actualizar(client, H, p["coord"], proppi, usado=6, total=10, dest=1, destacados_total=2),
        201,
    )

    a = ok(actualizar(client, H, p["coord"], cien, observacion=" Revisado "), 201)
    assert (a["a_tiempo"], a["dias_desde_anterior"], a["observacion"]) == (True, None, "Revisado")
    t = ok(client.get(PL, headers=H(p["coord"])))
    c = fila(t, "Ciencuadras")
    assert (c["cupo_total"] - c["cupo_usado"], c["estado"], c["ultima_txt"]) == (
        8,
        "al_dia",
        "Hoy · 3 oct",
    )
    assert (t["cupo_disponible"], t["destacados_disponibles"]) == (8 + 4, 2 + 1)

    # The cupo total of the form keeps the plan in step
    ok(actualizar(client, H, p["coord"], cien, total=45), 201)
    t = ok(client.get(PL, headers=H(p["ger"])))
    assert fila(t, "Ciencuadras")["plan"]["cupo_total"] == 45

    ok(
        client.put(
            f"{PL}/{cien.id}/responsable",
            json={"responsable_id": str(p["aux"].id)},
            headers=H(p["ger"]),
        )
    )
    ok(actualizar(client, H, p["aux"], cien), 201)


def test_late_and_kpis(client, p, plats, H, reloj):
    cien = plats["ciencuadras"]
    ok(client.post(f"{PL}/{cien.id}/planes", json=PLAN, headers=H(p["ger"])), 201)
    ok(
        client.put(
            f"{PL}/{cien.id}/responsable",
            json={"responsable_id": str(p["coord"].id)},
            headers=H(p["ger"]),
        )
    )
    reloj["now"] = NOW - timedelta(days=12)
    ok(actualizar(client, H, p["coord"], cien), 201)
    reloj["now"] = NOW - timedelta(days=3)  # 9 days later: rule is 7
    tarde = ok(actualizar(client, H, p["coord"], cien), 201)
    assert (tarde["a_tiempo"], tarde["dias_desde_anterior"], tarde["regla_dias"]) == (False, 9, 7)
    reloj["now"] = NOW
    t = ok(
        client.get(PL, params={"desde": "2026-09-01", "hasta": "2026-10-03"}, headers=H(p["ger"]))
    )
    assert fila(t, "Ciencuadras")["estado"] == "al_dia"  # 3 days ago
    k = t["kpis"]
    assert (k["actualizaciones"], k["a_tiempo_pct"], k["del_responsable_pct"]) == (2, 50, 100)
    assert k["atrasadas"] == ["Proppi"]  # never updated
    reloj["now"] = NOW + timedelta(days=5)
    t = ok(client.get(PL, headers=H(p["coord"])))
    assert fila(t, "Ciencuadras")["estado_txt"] == "Atrasada"
    # Filters
    t = ok(
        client.get(
            PL,
            params={"desde": "2026-09-01", "hasta": "2026-09-25", "quien_id": str(p["coord"].id)},
            headers=H(p["ger"]),
        )
    )
    assert len(t["actualizaciones"]) == 1
    bad = {"desde": "2026-10-05", "hasta": "2026-10-01"}
    assert client.get(PL, params=bad, headers=H(p["ger"])).status_code == 422

    # Gerencia changes the rule
    assert (
        client.put(f"{PL}/regla", json={"dias_regla": 10}, headers=H(p["coord"])).status_code == 403
    )
    r = ok(client.put(f"{PL}/regla", json={"dias_regla": 10}, headers=H(p["ger"])))
    assert r == {"dias_regla": 10, "regla_confirmada": True}
    t = ok(client.get(PL, headers=H(p["coord"])))
    assert fila(t, "Ciencuadras")["estado"] == "al_dia"  # 8 days ≤ 10


# ---------------------------------------------------------------- results, history, rendimiento


def _lead(db, fuente, when, *, etapa=EtapaLead.PERDIDO, cita=False):
    ld = Lead(full_name="Cliente", phone="3000000000", fuente=fuente, etapa=etapa)
    if etapa == EtapaLead.GANADO:
        ld.cerrado_at = when
    db.add(ld)
    db.flush()
    ld.created_at = when
    if cita:
        db.add(
            Cita(
                lead_id=ld.id,
                tipo=TipoCita.VISITA_VENTA,
                scheduled_at=when,
                estado=EstadoCita.REALIZADA,
            )
        )
    db.flush()
    return ld


def test_results_and_history(client, p, plats, H, db):
    cien = plats["ciencuadras"]
    ok(client.post(f"{PL}/{cien.id}/planes", json=PLAN, headers=H(p["ger"])), 201)
    sep = datetime(2026, 9, 10, 10, 0, tzinfo=fechas.BOGOTA)
    for i in range(4):
        _lead(db, FuenteLead.CIENCUADRAS, sep + timedelta(days=i), cita=i < 2)
    _lead(db, FuenteLead.CIENCUADRAS, sep, etapa=EtapaLead.GANADO)
    _lead(db, FuenteLead.FACEBOOK, sep)  # not a traditional portal
    _lead(db, FuenteLead.CIENCUADRAS, datetime(2026, 8, 1, 10, 0, tzinfo=fechas.BOGOTA))  # out

    q = {"desde": "2026-09-01", "hasta": "2026-09-10"}
    r = ok(client.get(f"{PL}/resultados", params=q, headers=H(p["ger"])))
    c = next(x for x in r["filas"] if x["nombre"] == "Ciencuadras")
    assert (c["leads"], c["citas"], c["cierres"]) == (2, 1, 1)  # only 10 sep is in the range
    assert (c["costo"], c["costo_lead"], c["costo_cierre"], c["conversion"]) == (
        100_000,
        50_000,
        100_000,
        50.0,
    )
    assert r["kpis"]["leads"] == 2
    assert [b["label"] for b in r["barras"]] == ["sep"]
    pr = next(x for x in r["filas"] if x["nombre"] == "Proppi")
    assert (pr["costo"], pr["plan_estado"]) == (0, "sin_plan")

    ok(actualizar(client, H, p["coord"], cien, observacion="Ok"), 201)
    h = ok(client.get(f"{PL}/historico", headers=H(p["ger"])))
    assert h["total"] == 1 and len(h["columnas"]) == 22
    row = dict(zip(h["columnas"], h["filas"][0], strict=True))
    assert (row["Cupo disponible"], row["Precio del plan"], row["Activa"], row["A tiempo"]) == (
        "8",
        "$920.000",
        "Sí",
        "Sí",
    )
    res = client.get(f"{PL}/historico.csv", headers=H(p["coord"]))
    assert res.status_code == 200 and "attachment" in res.headers["content-disposition"]
    assert len(res.text.strip().splitlines()) == 2
    ch = ok(client.get(f"{PL}/cambios", headers=H(p["ger"])))
    assert ch[0]["tipo"] == "descarga"


def test_rendimiento_area(client, p, plats, H, db, reloj):
    cien = plats["ciencuadras"]
    ok(
        client.put(
            f"{PL}/{cien.id}/responsable",
            json={"responsable_id": str(p["coord"].id)},
            headers=H(p["ger"]),
        )
    )
    reloj["now"] = datetime(2026, 9, 28, 9, 0, tzinfo=fechas.BOGOTA)
    ok(actualizar(client, H, p["coord"], cien, destacados_total=5), 201)
    # Oct 1–3: last update 28 sep, within 7 days → every day «al día»
    reloj["now"] = NOW
    assert svc.cumplimiento(db, p["coord"], date(2026, 10, 1), date(2026, 10, 31)) == (3, 3, 1)
    reloj["now"] = NOW + timedelta(days=4)  # 7 oct: 6 and 7 oct are late (more than 7 days)
    assert svc.cumplimiento(db, p["coord"], date(2026, 10, 1), date(2026, 10, 31)) == (5, 7, 1)
    r = rend.Calculo(db, rend.periodo()).resultado(p["coord"])
    a = r.area("plataformas")
    assert (a.cumplimiento, a.logrado_txt) == (71, "Al día el 71 % de los días")
    # Nobody assigned → no data
    assert svc.cumplimiento(db, p["aux"], date(2026, 10, 1), date(2026, 10, 31)) is None
