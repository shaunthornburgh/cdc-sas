"""Configuración (Z02 / Z02-ger): brand, pay dates, rates, alerts, lead rules, pendientes."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models import LeadEvento, MovimientosConfig
from app.models.enums import Cargo, FuenteLead, FuncionIndependiente, TipoEventoLead
from app.services import compensacion as comp
from app.services import dashboard
from app.services import leads as lead_service
from tests.conftest import auth_header, login

CF = "/api/v1/configuracion"
PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo"),
        "aux": make_user(Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com"),
        "laura": make_user(
            Cargo.ATENCION_CLIENTE,
            email="laura@example.com",
            full_name="Laura",
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


# ---------------------------------------------------------------- access


def test_access(client, p, H):
    # The brand is public: the login page shows it
    m = ok(client.get(f"{CF}/marca"))
    assert (m["nombre"], m["color_principal"], m["logo"]) == ("CASA DOLCE CASA", "#00843D", None)
    g = ok(client.get(CF, headers=H(p["ger"])))
    assert g["gerencia"] is True and g["tarifas"]["arriendo_pct"] == 20.0
    assert g["pagos"] == {"dia_corte_1": 15, "dia_corte_2": 30, "dia_pago": 5}
    # Coordinación reads the pay dates only (Z02: «solo lectura»)
    c = ok(client.get(CF, headers=H(p["coord"])))
    assert (c["gerencia"], c["tarifas"], c["leads"], c["pendientes"]) == (False, None, None, [])
    assert c["pagos"]["dia_pago"] == 5
    for k in ("aux", "laura"):
        assert client.get(CF, headers=H(p[k])).status_code == 403
    assert client.put(f"{CF}/pagos", json=c["pagos"], headers=H(p["coord"])).status_code == 403
    assert (
        client.put(f"{CF}/tarifas", json={"iva_pct": 5}, headers=H(p["coord"])).status_code == 403
    )


# ---------------------------------------------------------------- brand


def test_brand(client, p, H):
    h = H(p["ger"])
    assert client.put(f"{CF}/marca", json={"nombre": "  "}, headers=h).status_code == 422
    assert client.put(f"{CF}/marca", json={"color_oscuro": "verde"}, headers=h).status_code == 422
    assert (
        client.put(
            f"{CF}/marca", json={"logo": "data:text/html;base64,PGI+"}, headers=h
        ).status_code
        == 422
    )
    big = "data:image/png;base64," + "A" * 210_000
    assert client.put(f"{CF}/marca", json={"logo": big}, headers=h).status_code == 422
    m = ok(
        client.put(
            f"{CF}/marca",
            json={"nombre": " Casa Nueva ", "color_principal": "#1a7f4b", "logo": PNG},
            headers=h,
        )
    )
    assert (m["nombre"], m["color_principal"], m["logo"][:15]) == (
        "Casa Nueva",
        "#1A7F4B",
        "data:image/png;",
    )
    assert ok(client.get(f"{CF}/marca"))["nombre"] == "Casa Nueva"
    ev = ok(client.get(CF, headers=h))["cambios"][0]
    assert ev["seccion"] == "marca" and ev["actor_name"] == "Gina Gerencia"
    assert ev["despues"]["logo"] == "logo propio"  # the history doesn't store the image
    m = ok(client.post(f"{CF}/marca/restaurar", headers=h))
    assert (m["nombre"], m["logo"]) == ("CASA DOLCE CASA", None)


# ---------------------------------------------------------------- pay dates → Compensación


def test_pay_dates_are_compensacion_config(client, p, H, db):
    h = H(p["ger"])
    bad = {"dia_corte_1": 20, "dia_corte_2": 15, "dia_pago": 5}
    assert client.put(f"{CF}/pagos", json=bad, headers=h).status_code == 422
    assert (
        client.put(
            f"{CF}/pagos", json={"dia_corte_1": 29, "dia_corte_2": 30, "dia_pago": 5}, headers=h
        ).status_code
        == 422
    )
    r = ok(
        client.put(
            f"{CF}/pagos", json={"dia_corte_1": 14, "dia_corte_2": 28, "dia_pago": 6}, headers=h
        )
    )
    assert r == {"dia_corte_1": 14, "dia_corte_2": 28, "dia_pago": 6}
    cfg = comp.get_config(db)
    assert (cfg["dia_corte_1"], cfg["dia_pago"]) == (14, 6)
    ev = ok(client.get(CF, headers=h))["cambios"][0]
    assert (ev["seccion"], ev["antes"], ev["despues"]) == (
        "pagos",
        {"dia_corte_1": 15, "dia_corte_2": 30, "dia_pago": 5},
        {"dia_corte_1": 14, "dia_corte_2": 28, "dia_pago": 6},
    )


# ---------------------------------------------------------------- rates, alerts, language


def test_rates_alerts_language(client, p, H, db):
    h = H(p["ger"])
    assert client.put(f"{CF}/tarifas", json={"iva_pct": -1}, headers=h).status_code == 422
    assert client.put(f"{CF}/tarifas", json={"nuevo": 1}, headers=h).status_code == 422
    t = ok(
        client.put(f"{CF}/tarifas", json={"arriendo_pct": "8.5", "retencion_pct": ""}, headers=h)
    )
    assert (t["arriendo_pct"], t["retencion_pct"]) == (8.5, None)
    pend = {x["clave"]: x for x in ok(client.get(CF, headers=h))["pendientes"]}
    assert pend["retencion"]["resuelto"] is False
    ok(client.put(f"{CF}/tarifas", json={"retencion_pct": 2.5}, headers=h))
    pend = {x["clave"]: x for x in ok(client.get(CF, headers=h))["pendientes"]}
    assert pend["retencion"]["resuelto"] is True

    assert (
        client.put(
            f"{CF}/automatizaciones", json={"lead_sin_responsable_min": 7}, headers=h
        ).status_code
        == 422
    )
    ok(client.put(f"{CF}/automatizaciones", json={"lead_sin_responsable_min": 30}, headers=h))
    # The Coordinación dashboard uses it
    s = dashboard.leads_summary(db)
    assert s["sin_responsable_min"] == 30
    assert dashboard.alerta_sin_responsable(db) == timedelta(minutes=30)

    assert client.put(f"{CF}/idioma", json={"idioma": "en"}, headers=h).status_code == 422
    assert client.put(f"{CF}/idioma", json={"idioma": "fr"}, headers=h).status_code == 422
    ok(client.put(f"{CF}/idioma", json={"idioma": "es"}, headers=h))
    assert client.put(f"{CF}/produccion", json={"uso_real": True}, headers=h).status_code == 422


# ---------------------------------------------------------------- lead rules → leads & rendimiento


def test_lead_rules_are_used(client, p, H, db):
    h = H(p["ger"])
    assert client.put(f"{CF}/leads", json={"puntos_perdido": 1.5}, headers=h).status_code == 422
    bad = {"puntos_ganado": 0.5, "puntos_perdido": 0.5}
    r = client.put(f"{CF}/leads", json=bad, headers=h)
    assert r.status_code == 422 and "menos" in r.json()["detail"]

    lead = lead_service.create_lead(
        db,
        {
            "full_name": "Cliente",
            "phone": "3005550101",
            "fuente": FuenteLead.FACEBOOK,
            "negocio": "arriendo",
        },
        actor=p["laura"],
    )
    lead.assigned_to_id = p["laura"].id  # she took it («Seguir lead»)
    for dias in (1, 0):  # 2 calls on 2 consecutive days
        db.add(
            LeadEvento(
                lead_id=lead.id,
                tipo=TipoEventoLead.LLAMADA,
                titulo="Llamada · no contestó",
                datos={"resultado": "no_contesto"},
                created_by_id=p["laura"].id,
                created_at=datetime.now(UTC) - timedelta(days=dias),
            )
        )
    db.flush()
    # Defaults (3 calls in 3 days) would make it cost points; Gerencia lowers them to 2 and 2
    ok(client.put(f"{CF}/leads", json={"llamadas_minimas": 2, "dias_seguidos": 2}, headers=h))
    res = ok(
        client.post(
            f"/api/v1/leads/{lead.id}/stage",
            json={"etapa": "perdido", "motivo": "no_contesta"},
            headers=H(p["laura"]),
        )
    )
    assert res["perdida_descuenta"] is False


# ---------------------------------------------------------------- pendientes and «uso real»


def test_pendientes_and_go_live(client, p, H, db):
    h = H(p["ger"])
    pend = ok(client.get(CF, headers=h))["pendientes"]
    assert len(pend) == 10 and not any(x["resuelto"] for x in pend)
    assert client.post(f"{CF}/uso-real", headers=h).status_code == 409
    # Automatic ones can't be ticked by hand
    assert (
        client.put(f"{CF}/pendientes/gps_plazo", json={"resuelto": True}, headers=h).status_code
        == 422
    )
    assert (
        client.put(
            f"{CF}/pendientes/metas", json={"resuelto": True}, headers=H(p["coord"])
        ).status_code
        == 403
    )
    for x in pend:
        if x["manual"]:
            ok(client.put(f"{CF}/pendientes/{x['clave']}", json={"resuelto": True}, headers=h))
    # Resolve the automatic ones where they live
    db.add(MovimientosConfig(id=1, minutos_alerta=20, plazo_horas=24))
    db.flush()
    ok(client.put("/api/v1/plataformas/regla", json={"dias_regla": 7}, headers=h))
    ok(client.put(f"{CF}/tarifas", json={"retencion_pct": 3.5}, headers=h))
    assert all(x["resuelto"] for x in ok(client.get(CF, headers=h))["pendientes"])
    r = ok(client.post(f"{CF}/uso-real", headers=h))
    assert (r["uso_real"], r["uso_real_por"]) == (True, "Gina Gerencia")
    assert client.post(f"{CF}/uso-real", headers=h).status_code == 409
