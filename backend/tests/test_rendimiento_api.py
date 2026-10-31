from datetime import timedelta

import pytest

from app.models import Calificacion, Captacion, Cita, Lead, LeadEvento, Seguimiento
from app.models.enums import ActividadComercial as A
from app.models.enums import (
    Cargo,
    EstadoCaptacion,
    EstadoCita,
    EtapaLead,
    FuenteLead,
    FuncionIndependiente,
    ModoCaptacion,
    MotivoPerdida,
    TipoCita,
    TipoEventoLead,
    TipoNegocio,
)
from app.services import rendimiento as svc
from tests.conftest import auth_header, login

R = "/api/v1/rendimiento"


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Vale Aux"
        ),
        "juan": make_user(
            email="juan@example.com",
            full_name="Juan Asesor",
            actividades=[A.CAPTACION, A.VENTAS, A.ARRIENDOS],
        ),
        "ana": make_user(email="ana@example.com", full_name="Ana Ventas", actividades=[A.VENTAS]),
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


@pytest.fixture
def T():
    """A moment inside the current month, before now."""
    return svc.periodo().start + timedelta(minutes=5)


def ganado(db, T, *, asesor, negocio, assigned=None, n=1):
    for _ in range(n):
        lead = Lead(
            full_name="Cliente Ganado",
            phone="3000000000",
            fuente=FuenteLead.OTRO,
            negocio=negocio,
            etapa=EtapaLead.GANADO,
            cerrado_at=T,
            assigned_to_id=assigned.id if assigned else None,
        )
        db.add(lead)
        db.flush()
        tipo = TipoCita.VISITA_VENTA if negocio == TipoNegocio.VENTA else TipoCita.VISITA_ARRIENDO
        db.add(
            Cita(
                lead_id=lead.id,
                tipo=tipo,
                scheduled_at=T,
                asesor_id=asesor.id,
                estado=EstadoCita.REALIZADA,
            )
        )
    db.flush()


def captacion(db, T, asesor, n=1, estado=EstadoCaptacion.APROBADA, verificado=True):
    for i in range(n):
        db.add(
            Captacion(
                negocio=TipoNegocio.VENTA if i % 2 else TipoNegocio.ARRIENDO,
                codigo_inmueble=f"INM-{asesor.full_name[:3]}-{estado.value[:3]}-{i}",
                direccion="Cl 1 # 2-3",
                modo=ModoCaptacion.RAPIDO,
                estado=estado,
                enviada_at=T,
                verificado_at=T + timedelta(hours=2) if verificado else None,
                asesor_id=asesor.id,
            )
        )
    db.flush()


def area(res, key):
    return next(a for a in res["areas"] if a["key"] == key)


# ---------------------------------------------------------------- permissions


def test_who_sees_what(client, p, H):
    assert client.get(f"{R}/mio", headers=H(p["juan"])).status_code == 200
    assert client.get(f"{R}/mio", headers=H(p["laura"])).status_code == 200
    assert client.get(f"{R}/mio", headers=H(p["coord"])).status_code == 200
    # Gerencia and the Auxiliar have no result of their own yet.
    assert client.get(f"{R}/mio", headers=H(p["ger"])).status_code == 403
    assert client.get(f"{R}/mio", headers=H(p["aux"])).status_code == 403

    juan, coord = str(p["juan"].id), str(p["coord"].id)
    assert client.get(f"{R}/personas/{coord}", headers=H(p["juan"])).status_code == 403
    assert client.get(f"{R}/personas/{juan}", headers=H(p["ana"])).status_code == 403
    assert client.get(f"{R}/equipo", headers=H(p["juan"])).status_code == 403
    assert client.get(f"{R}/empresa", headers=H(p["coord"])).status_code == 403

    def names(u):
        return {x["full_name"] for x in client.get(f"{R}/equipo", headers=H(u)).json()["personas"]}

    assert names(p["coord"]) == {"Juan Asesor", "Ana Ventas", "Laura Atención"}
    assert names(p["ger"]) == {"Juan Asesor", "Ana Ventas", "Laura Atención", "Mateo Coord"}
    assert names(p["aux"]) == names(p["ger"])
    # Coordinación sees its team, not other coordinators; Gerencia sees the Coordinador.
    assert client.get(f"{R}/personas/{juan}", headers=H(p["coord"])).status_code == 200
    assert client.get(f"{R}/personas/{coord}", headers=H(p["ger"])).status_code == 200


# ---------------------------------------------------------------- calculations


def test_asesor_result(client, db, p, H, T):
    juan = p["juan"]
    # Weights 50 / 30 / 20 (default for 3 activities) · goals 1 venta, 3 arriendos, 10 captaciones.
    ganado(db, T, asesor=juan, negocio=TipoNegocio.VENTA, n=2)  # 2 of 1 → capped at 100
    ganado(db, T, asesor=juan, negocio=TipoNegocio.ARRIENDO)  # 1 of 3 → 33
    ganado(db, T, asesor=p["ana"], negocio=TipoNegocio.ARRIENDO)  # Ana's: not Juan's
    captacion(db, T, juan, n=5)  # 5 of 10 → 50
    captacion(db, T, juan, n=3, estado=EstadoCaptacion.RECHAZADA)  # don't count
    captacion(db, T, juan, n=2, estado=EstadoCaptacion.POR_VERIFICAR, verificado=False)

    r = client.get(f"{R}/mio", headers=H(juan)).json()
    v, ar, cap = area(r, "ventas"), area(r, "arriendos"), area(r, "captacion")
    assert (v["logrado"], v["cumplimiento"], v["cumple"]) == (2, 100, True)
    assert (ar["logrado"], ar["cumplimiento"]) == (1, 33)
    assert ar["falta"] == "Llevas 1 de 3 arriendos: te faltan 2"
    assert (cap["logrado"], cap["cumplimiento"]) == (5, 50)
    # 100×0.5 + 33×0.3 + 50×0.2 = 69.9
    assert r["por_areas"] == pytest.approx(69.9)
    assert (r["total"], r["semaforo"]) == (70, "amarillo")
    assert r["mejoras"]["items"][0]["key"] == "arriendos"  # lowest first


def test_low_rating_takes_5_points_and_only_coordinacion_rates(client, db, p, H, T):
    ana = p["ana"]
    ganado(db, T, asesor=ana, negocio=TipoNegocio.VENTA)
    url = f"{R}/calificaciones/{ana.id}"
    body = {"valores": {"uniforme": 2, "actitud": 5}}
    assert client.put(url, json=body, headers=H(p["ger"])).status_code == 403  # Gerencia consults
    assert client.put(url, json=body, headers=H(p["aux"])).status_code == 403
    assert (
        client.put(url, json={"valores": {"uniforme": 6}}, headers=H(p["coord"])).status_code == 422
    )
    assert (
        client.put(url, json={"valores": {"inventado": 3}}, headers=H(p["coord"])).status_code
        == 422
    )
    r = client.put(url, json=body, headers=H(p["coord"])).json()
    assert (r["por_areas"], r["puntos_descuento"], r["total"]) == (100, 5, 95)
    assert r["descuentos"][0]["titulo"] == "Correcto uso del uniforme: 2 de 5"
    cal = {c["key"]: c for c in r["calificaciones"]}
    assert cal["uniforme"]["quien"] == "Asignado por Mateo Coord"
    assert cal["puntualidad"]["valor"] is None  # needs «Marcar entrada»
    # «Material de trabajo» is only for asesores.
    lau = client.get(f"{R}/personas/{p['laura'].id}", headers=H(p["coord"])).json()
    assert "material" not in {c["key"] for c in lau["calificaciones"]}
    # The person sees them, can't change them.
    mine = client.get(f"{R}/mio", headers=H(ana)).json()
    assert mine["total"] == 95 and mine["puede"]["calificar"] is False
    assert client.put(url, json=body, headers=H(ana)).status_code == 403


def test_coordinador_rated_by_auxiliar_or_gerencia(client, p, H):
    url = f"{R}/calificaciones/{p['coord'].id}"
    assert client.put(url, json={"valores": {"carne": 1}}, headers=H(p["coord"])).status_code == 403
    assert (
        client.put(url, json={"valores": {"material": 4}}, headers=H(p["aux"])).status_code == 422
    )
    assert client.put(url, json={"valores": {"carne": 1}}, headers=H(p["aux"])).status_code == 200
    assert client.put(url, json={"valores": {"bateria": 4}}, headers=H(p["ger"])).status_code == 200


def test_weights_sum_100_and_goals_apply_next_month(client, db, p, H, T):
    juan = p["juan"]
    captacion(db, T, juan, n=5)
    url = f"{R}/config/{juan.id}"
    bad = {"pesos": {"ventas": 50, "arriendos": 30, "captacion": 30}}
    res = client.put(f"{url}/pesos", json=bad, headers=H(p["coord"]))
    assert res.status_code == 422 and "110" in res.json()["detail"]
    assert (
        client.put(
            f"{url}/pesos", json={"pesos": {"ventas": 100}}, headers=H(p["coord"])
        ).status_code
        == 422
    )
    good = {"pesos": {"ventas": 0, "arriendos": 0, "captacion": 100}}
    assert client.put(f"{url}/pesos", json=good, headers=H(juan)).status_code == 403  # not own
    cfg = client.put(f"{url}/pesos", json=good, headers=H(p["coord"])).json()
    assert cfg["pesos"]["captacion"] == 100 and cfg["pesos_configurados"]
    assert client.get(f"{R}/mio", headers=H(juan)).json()["total"] == 50  # 5 of 10 × 100 %

    cfg = client.put(f"{url}/metas", json={"metas": {"captacion": 5}}, headers=H(p["coord"])).json()
    assert (cfg["metas"]["captacion"], cfg["metas_siguiente"]["captacion"]) == (10, 5)
    assert client.get(f"{R}/mio", headers=H(juan)).json()["total"] == 50  # this month unchanged
    assert (
        client.put(
            f"{url}/metas", json={"metas": {"captacion": 0}}, headers=H(p["coord"])
        ).status_code
        == 422
    )

    log = client.get(f"{R}/cambios/{juan.id}", headers=H(p["coord"])).json()
    assert [c["tipo"] for c in log] == ["metas", "pesos"]
    assert log[1]["antes"] == {"ventas": 50, "arriendos": 30, "captacion": 20}
    assert log[1]["created_by_name"] == "Mateo Coord"


def test_atencion_weights_only_gerencia(client, p, H):
    url = f"{R}/config/{p['laura'].id}/pesos"
    pesos = {"pesos": {k: v for k, v in svc.PESOS_ATENCION.items()}}
    assert client.put(url, json=pesos, headers=H(p["coord"])).status_code == 403
    assert client.put(url, json=pesos, headers=H(p["ger"])).status_code == 200
    assert (
        client.get(f"{R}/config/{p['laura'].id}", headers=H(p["coord"])).json()["puede_configurar"]
        is False
    )


def test_atencion_result_with_won_and_lost(client, db, p, H, T):
    laura, juan = p["laura"], p["juan"]
    leads = []
    for i in range(10):
        lead = Lead(
            full_name=f"Lead {i}",
            phone="3001112233",
            fuente=FuenteLead.OTRO,
            assigned_to_id=laura.id,
        )
        db.add(lead)
        leads.append(lead)
    db.flush()
    for lead in leads:
        db.add(
            LeadEvento(
                lead_id=lead.id,
                tipo=TipoEventoLead.LLAMADA,
                titulo="Llamada",
                datos={"resultado": "contesto"},
                created_by_id=laura.id,
                created_at=T,
            )
        )
    for lead in leads[:4]:  # 4 citas from 10 leads → 40 % conversion (goal 40 %)
        db.add(
            Cita(
                lead_id=lead.id,
                tipo=TipoCita.VISITA_ARRIENDO,
                scheduled_at=T,
                asesor_id=juan.id,
                estado=EstadoCita.REALIZADA,
                created_by_id=laura.id,
            )
        )
    db.add(
        Cita(lead_id=leads[5].id, tipo=TipoCita.INVENTARIO, scheduled_at=T, created_by_id=laura.id)
    )  # doesn't count
    db.add(
        Seguimiento(
            lead_id=leads[0].id,
            accion="llamar",
            due_at=T,
            created_by_id=laura.id,
            done_at=T + timedelta(minutes=10),
        )
    )
    db.add(
        Seguimiento(
            lead_id=leads[1].id,
            accion="llamar",
            due_at=T,
            created_by_id=laura.id,
            done_at=T + timedelta(hours=3),
        )
    )
    db.flush()
    ganado(db, T, asesor=juan, negocio=TipoNegocio.ARRIENDO, assigned=laura, n=2)
    for desc in (True, False):
        db.add(
            Lead(
                full_name="Perdido",
                phone="3000",
                fuente=FuenteLead.OTRO,
                assigned_to_id=laura.id,
                etapa=EtapaLead.PERDIDO,
                motivo_perdida=MotivoPerdida.NO_INTERESADO
                if desc
                else MotivoPerdida.NUMERO_EQUIVOCADO,
                perdida_descuenta=desc,
                cerrado_at=T,
            )
        )
    db.flush()

    r = client.get(f"{R}/mio", headers=H(laura)).json()
    assert area(r, "leads_gestionados")["logrado"] == 10
    assert area(r, "llamadas")["logrado_txt"] == "10 · 10 contestadas"
    seg = area(r, "seguimientos")
    assert (seg["logrado_txt"], seg["cumplimiento"]) == ("1 de 2 a tiempo", 50)
    assert area(r, "citas_programadas")["logrado"] == 4
    assert area(r, "citas_realizadas")["logrado"] == 4
    assert area(r, "conversion")["cumplimiento"] == 100
    assert area(r, "cierres")["logrado"] == 2
    # Ganado +1 each, perdido that «descuenta» −0.5; number-equivocado doesn't.
    assert r["puntos_ajuste"] == pytest.approx(1.5)
    assert {a["titulo"] for a in r["ajustes"]} == {
        "Ganados: 2",
        "Perdidos sin descuento: 1",
        "Perdidos con descuento: 1",
    }
    # The 2 won arriendos count for Juan (his realized citas), not twice for Laura.
    assert area(client.get(f"{R}/mio", headers=H(juan)).json(), "arriendos")["logrado"] == 2


def test_coordinador_areas_without_data_dont_count(client, db, p, H, T):
    ganado(db, T, asesor=p["ana"], negocio=TipoNegocio.VENTA)  # Ana 100
    captacion(db, T, p["juan"], n=2)  # verified in 2 h → monitoreo 100 %
    r = client.get(f"{R}/mio", headers=H(p["coord"])).json()
    assert area(r, "plataformas")["cumplimiento"] is None
    assert area(r, "plataformas")["sin_datos"].startswith("Sin datos")
    assert r["peso_con_datos"] == 65  # equipo 50 + monitoreo 15
    eq = area(r, "equipo")
    assert eq["logrado_txt"].endswith("3 personas")


def test_company_view(client, db, p, H, T):
    ganado(db, T, asesor=p["ana"], negocio=TipoNegocio.VENTA)
    e = client.get(f"{R}/empresa", headers=H(p["ger"])).json()
    com = next(a for a in e["areas"] if a["key"] == "comercial")
    assert com["n"] == 2
    ventas = next(m for m in com["metas"] if m["titulo"] == "Ventas cerradas")
    assert (ventas["logrado"], ventas["meta"]) == (1, 2)  # Ana 1 of 1 + Juan 0 of 1
    assert any(a["nivel"] == "bad" for a in e["avisos"])  # some area under 60 %
    adm = next(a for a in e["areas"] if a["key"] == "administrativa")
    assert adm["total"] is None


def test_previous_month_and_future_month(client, p, H):
    prev = svc.periodo().anterior().key
    r = client.get(f"{R}/mio", params={"periodo": prev}, headers=H(p["juan"])).json()
    assert r["periodo"]["en_curso"] is False and r["puede"]["calificar"] is False
    nxt = svc.periodo().siguiente_first().strftime("%Y-%m")
    assert client.get(f"{R}/mio", params={"periodo": nxt}, headers=H(p["juan"])).status_code == 422


def test_team_csv(client, p, H):
    res = client.get(f"{R}/equipo.csv", headers=H(p["coord"]))
    assert res.status_code == 200 and "Juan Asesor" in res.text


def test_rating_unit_rules(db, p):
    assert svc.semaforo(80) == "verde" and svc.semaforo(79.6) == "amarillo"
    assert svc.semaforo(65) == "naranja" and svc.semaforo(59) == "rojo"
    assert svc.cargo_txt(p["juan"]) == "Asesor · Ventas + Arriendos + Captación"
    # A saved rating row is unique per person, month and indicator.
    db.add(
        Calificacion(user_id=p["ana"].id, periodo=svc.periodo().first, indicador="carne", valor=3)
    )
    db.flush()
