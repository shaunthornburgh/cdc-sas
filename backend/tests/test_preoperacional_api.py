from datetime import UTC, datetime, timedelta

import pytest

from app.models import Preoperacional
from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, MedioTransporte
from app.services import fechas
from app.services import preoperacional as svc
from tests.conftest import auth_header, login

PRE = "/api/v1/preoperacional"
SI8 = [True] * 8


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gerente"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Valeria Aux"
        ),
        "laura": make_user(
            Cargo.ATENCION_CLIENTE, email="laura@example.com", full_name="Laura Atención"
        ),
        "juan": make_user(
            email="juan@example.com", full_name="Juan Asesor", actividades=[A.CAPTACION, A.VENTAS]
        ),
        "bruno": make_user(
            email="bruno@example.com", full_name="Bruno Moto", actividades=[A.CAPTACION]
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


# ---------------------------------------------------------------- submit


def test_form_definition(client, p, H):
    f = client.get(f"{PRE}/formulario", headers=H(p["juan"])).json()
    assert f["activo"] is True
    assert list(f["medios"]) == [
        "carro",
        "moto",
        "bicicleta",
        "transporte_publico",
        "a_pie",
        "otro",
    ]
    assert len(f["preguntas"]["carro"]) == 8 and len(f["preguntas"]["moto"]) == 8
    assert f["registro_de_hoy"] is None
    assert f["destinatario"].startswith("Le llegó a Coordinación")
    assert (
        client.get(f"{PRE}/formulario", headers=H(p["coord"])).json()["destinatario"]
        == "Le llegó a Gerencia."
    )


def test_vehicle_needs_plate_and_8_answers(client, p, H):
    h = H(p["juan"])
    assert (
        client.post(PRE, json={"medio": "carro", "respuestas": SI8}, headers=h).status_code == 422
    )
    assert (
        client.post(
            PRE, json={"medio": "carro", "placa": "ABC123", "respuestas": [True] * 7}, headers=h
        ).status_code
        == 422
    )
    res = client.post(
        PRE, json={"medio": "carro", "placa": " abc 123 ", "respuestas": SI8}, headers=h
    )
    assert res.status_code == 201
    body = res.json()
    assert body["placa"] == "ABC123" and body["tiene_novedad"] is False
    assert body["respuestas"][0]["pregunta"].startswith("¿La documentación")
    # Only one per day.
    assert client.post(PRE, json={"medio": "a_pie"}, headers=h).status_code == 409


def test_no_answer_is_a_novedad(client, p, H):
    answers = [True, True, False, True, True, True, True, True]  # frenos
    body = client.post(
        PRE,
        json={
            "medio": "moto",
            "placa": "KLM78F",
            "respuestas": answers,
            "observaciones": "Frenos con ruido",
        },
        headers=H(p["bruno"]),
    ).json()
    assert body["tiene_novedad"] is True and body["respuestas_no"] == [3]


def test_travel_report_without_questions(client, p, H):
    body = client.post(
        PRE,
        json={"medio": "transporte_publico", "placa": "IGNORED", "respuestas": SI8},
        headers=H(p["laura"]),
    ).json()
    assert (body["placa"], body["respuestas"], body["tiene_novedad"]) == (None, [], False)
    obs = client.post(
        PRE, json={"medio": "a_pie", "observaciones": "Me torcí el tobillo"}, headers=H(p["aux"])
    ).json()
    assert obs["tiene_novedad"] is True  # an observation is reviewed too


def test_everyone_can_submit_including_gerencia(client, p, H):
    for key in ("ger", "coord", "aux", "laura", "juan"):
        assert client.post(PRE, json={"medio": "otro"}, headers=H(p[key])).status_code == 201


def test_deactivated_cargo_cannot_submit(client, db, p, H):
    svc.set_config(db, Cargo.ASESOR, False, actor=p["ger"])
    res = client.post(PRE, json={"medio": "a_pie"}, headers=H(p["juan"]))
    assert res.status_code == 403
    assert client.get(f"{PRE}/formulario", headers=H(p["juan"])).json()["activo"] is False


def test_only_gerencia_changes_config(client, p, H):
    assert (
        client.put(
            f"{PRE}/config/asesor", json={"activo": False}, headers=H(p["coord"])
        ).status_code
        == 403
    )
    cfg = client.put(f"{PRE}/config/asesor", json={"activo": False}, headers=H(p["ger"])).json()
    assert cfg["asesor"] is False and cfg["gerencia"] is True
    assert client.get(f"{PRE}/config", headers=H(p["coord"])).json()["asesor"] is False


# ---------------------------------------------------------------- history & score


@pytest.fixture
def miercoles(monkeypatch):
    """A fixed Wednesday, so the tests that depend on «today» being a business day always run
    (on a weekend «today» would be «fin_de_semana» and nobody «sin realizar»)."""
    monkeypatch.setattr(fechas, "now", lambda: datetime(2026, 10, 14, 10, 0, tzinfo=fechas.BOGOTA))


def test_score_rule():
    assert [svc.puntaje(x) for x in (100, 95, 90, 85, 75, 69)] == [5, 4, 4, 3, 2, 1]


def test_my_history_counts_business_days(client, db, p, H, miercoles):
    juan = p["juan"]
    today = svc.hoy()
    first = today.replace(day=1)
    # Make Juan's account older than the month so every business day counts.
    juan.created_at = datetime(first.year, first.month, 1, tzinfo=UTC) - timedelta(days=40)
    business = [
        first + timedelta(days=i)
        for i in range((today - first).days)
        if (first + timedelta(days=i)).weekday() < 5
    ]
    if not business:
        pytest.skip("No business days before today in this month")
    done = business[:-1]  # miss the last business day before today
    for d in done:
        db.add(
            Preoperacional(
                user_id=juan.id,
                fecha=d,
                realizado_at=datetime.now(UTC),
                medio=MedioTransporte.A_PIE,
                respuestas=[],
            )
        )
    db.flush()

    h = client.get(f"{PRE}/mios", headers=H(juan)).json()
    r = h["resumen"]
    assert (r["dias_habiles"], r["cumplidos"]) == (len(business), len(done))
    assert r["pct"] == round(100 * len(done) / len(business))
    assert r["puntaje"] == svc.puntaje(r["pct"])
    missed = [e for e in h["eventos"] if e["tipo"] == "no_realizado"]
    assert [e["fecha"] for e in missed] == [business[-1].isoformat()]
    estados = {d["fecha"]: d["estado"] for d in h["dias"]}
    assert estados[business[-1].isoformat()] == "no_realizado"
    assert estados[today.isoformat()] == "pendiente"


def test_gerencia_is_record_only(client, p, H):
    client.post(
        PRE, json={"medio": "carro", "placa": "GHI789", "respuestas": SI8}, headers=H(p["ger"])
    )
    assert client.get(f"{PRE}/mios", headers=H(p["ger"])).json()["resumen"]["puntaje"] is None


# ---------------------------------------------------------------- team review (K09)


def test_team_visibility(client, p, H):
    for key, medio in (("juan", "a_pie"), ("coord", "otro")):
        client.post(PRE, json={"medio": medio}, headers=H(p[key]))
    coord_view = client.get(f"{PRE}/equipo", headers=H(p["coord"])).json()
    names = {f["user"]["full_name"] for f in coord_view["filas"]}
    assert {"Juan Asesor", "Bruno Moto", "Laura Atención", "Valeria Aux"} <= names
    assert "Mateo Coord" not in names and "Gerente" not in names  # Coordinación's goes to Gerencia

    ger_names = {
        f["user"]["full_name"]
        for f in client.get(f"{PRE}/equipo", headers=H(p["ger"])).json()["filas"]
    }
    assert {"Mateo Coord", "Gerente"} <= ger_names

    for key in ("juan", "aux", "laura"):
        assert client.get(f"{PRE}/equipo", headers=H(p[key])).status_code == 403


def test_team_kpis_and_review(client, p, H, miercoles):
    client.post(
        PRE, json={"medio": "carro", "placa": "ABC123", "respuestas": SI8}, headers=H(p["juan"])
    )
    nov = client.post(
        PRE,
        json={"medio": "moto", "placa": "KLM78F", "respuestas": [True, True, False] + [True] * 5},
        headers=H(p["bruno"]),
    ).json()
    data = client.get(f"{PRE}/equipo", headers=H(p["coord"])).json()
    estados = {f["user"]["full_name"]: f["estado"] for f in data["filas"]}
    assert (estados["Juan Asesor"], estados["Bruno Moto"], estados["Laura Atención"]) == (
        "realizado",
        "novedad",
        "sin_realizar",
    )
    k = data["kpis"]
    assert (k["realizados"], k["con_novedad"], k["novedades_sin_revisar"]) == (2, 1, 1)
    assert k["sin_realizar"] == k["total"] - 2

    url = f"{PRE}/{nov['id']}/revisar"
    assert client.post(url, json={}, headers=H(p["juan"])).status_code == 403
    rev = client.post(
        url, json={"nota": "Que lleve la moto al taller"}, headers=H(p["coord"])
    ).json()
    assert rev["revisado_por_name"] == "Mateo Coord"
    assert client.post(url, json={}, headers=H(p["coord"])).status_code == 422  # already reviewed


def test_export_csv(client, p, H):
    client.post(
        PRE,
        json={
            "medio": "moto",
            "placa": "KLM78F",
            "respuestas": [True, True, False] + [True] * 5,
            "observaciones": "frenos",
        },
        headers=H(p["bruno"]),
    )
    res = client.get(f"{PRE}/export.csv", headers=H(p["coord"]))
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    text = res.text
    assert "Bruno Moto" in text and "KLM78F" in text and "frenos están" in text
    assert client.get(f"{PRE}/export.csv", headers=H(p["juan"])).status_code == 403


def test_dashboard_and_asesor_home_show_it(client, p, H, miercoles):
    d = client.get("/api/v1/dashboard/coordinacion", headers=H(p["coord"])).json()
    assert d["preoperacional"]["sin_realizar"] == d["preoperacional"]["total"]
    assert any("realizado el preoperacional" in a["titulo"] for a in d["alertas"])

    home = client.get("/api/v1/asesor/inicio", headers=H(p["juan"])).json()
    assert home["preoperacional"] == {"activo": True, "realizado_at": None, "tiene_novedad": False}
    client.post(PRE, json={"medio": "a_pie"}, headers=H(p["juan"]))
    assert client.get("/api/v1/asesor/inicio", headers=H(p["juan"])).json()["preoperacional"][
        "realizado_at"
    ]
