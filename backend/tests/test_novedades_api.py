from datetime import UTC, date, datetime

import pytest

from app.models import Preoperacional
from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, MedioTransporte
from app.services import compensacion as comp
from tests.conftest import auth_header, login

NOV = "/api/v1/novedades"
SEP = "desde=2026-09-01&hasta=2026-09-30"


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Vale Aux"
        ),
        "ana": make_user(email="ana@example.com", full_name="Ana Ventas", actividades=[A.VENTAS]),
        "bruno": make_user(
            email="bruno@example.com", full_name="Bruno Capta", actividades=[A.CAPTACION]
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


def registrar(
    client, H, who, emp, tipo="incapacidad", desde="2026-09-14", hasta="2026-09-17", **kw
):
    data = {"empleado_id": str(emp.id), "tipo": tipo, "desde": desde, "hasta": hasta} | kw
    return client.post(NOV, json=data, headers=H(who))


# ---------------------------------------------------------------- access


def test_access(client, p, H):
    for k in ("ger", "coord", "aux"):
        assert client.get(NOV, headers=H(p[k])).status_code == 200, k
    assert client.get(NOV, headers=H(p["ana"])).status_code == 403
    assert client.get(f"{NOV}/opciones", headers=H(p["ana"])).status_code == 403
    o = ok(client.get(f"{NOV}/opciones", headers=H(p["aux"])))
    assert o["puede_registrar"] is True
    assert "Gina Gerencia" not in [e["full_name"] for e in o["empleados"]]
    assert "Ana Ventas" in [e["full_name"] for e in o["empleados"]]
    assert set(o["descontables"]) == {"incapacidad", "permiso_no_remunerado"}
    # Gerencia sees but doesn't register (K13)
    og = ok(client.get(f"{NOV}/opciones", headers=H(p["ger"])))
    assert (og["puede_registrar"], og["empleados"]) == (False, [])
    assert registrar(client, H, p["ger"], p["ana"]).status_code == 403
    assert registrar(client, H, p["ana"], p["bruno"]).status_code == 403
    assert ok(registrar(client, H, p["coord"], p["ana"]), 201)


# ---------------------------------------------------------------- register, list, annul


def test_register_list_and_annul(client, p, H):
    assert registrar(client, H, p["aux"], p["ger"]).status_code == 422  # Gerencia isn't listed
    assert (
        registrar(client, H, p["aux"], p["ana"], desde="2026-09-10", hasta="2026-09-09").status_code
        == 422
    )  # noqa: E501
    assert registrar(client, H, p["aux"], p["ana"], hasta="2027-06-01").status_code == 422  # > 180

    r = ok(
        registrar(client, H, p["aux"], p["ana"], observacion=" Certificado EPS ", soportes=1), 201
    )
    n = r["novedad"]
    assert (n["code"][:4], n["dias"], n["fechas_txt"], n["descuenta"], n["observacion"]) == (
        "NOV-",
        4,
        "14 al 17 sep",
        True,
        "Certificado EPS",
    )
    assert (n["registrada_por_name"], r["avisos"]) == ("Vale Aux", [])

    # Overlapping the same person is refused; another person is fine
    res = registrar(
        client,
        H,
        p["coord"],
        p["ana"],
        tipo="permiso_remunerado",
        desde="2026-09-17",
        hasta="2026-09-17",
    )  # noqa: E501
    assert res.status_code == 409 and "NOV-" in res.json()["detail"]
    ok(
        registrar(
            client,
            H,
            p["coord"],
            p["bruno"],
            tipo="permiso_remunerado",
            desde="2026-09-30",
            hasta="2026-10-01",
        ),
        201,
    )  # noqa: E501
    ok(
        registrar(
            client,
            H,
            p["coord"],
            p["bruno"],
            tipo="permiso_no_remunerado",
            desde="2026-09-01",
            hasta="2026-09-01",
        ),
        201,
    )  # noqa: E501

    lst = ok(client.get(f"{NOV}?{SEP}", headers=H(p["ger"])))
    assert len(lst["items"]) == 3
    # Days inside the range only: Bruno's permit has 1 of its 2 days in September
    assert lst["dias"] == {"incapacidad": 4, "permiso_no_remunerado": 1, "permiso_remunerado": 1}
    assert lst["items"][0]["puede_editar"] is False  # Gerencia only reads
    only = ok(
        client.get(f"{NOV}?{SEP}&tipo=incapacidad&empleado_id={p['ana'].id}", headers=H(p["aux"]))
    )  # noqa: E501
    assert [x["id"] for x in only["items"]] == [n["id"]]
    assert (
        client.get(f"{NOV}?desde=2026-09-30&hasta=2026-09-01", headers=H(p["aux"])).status_code
        == 422
    )  # noqa: E501

    # Edit only the note and attachments
    url = f"{NOV}/{n['id']}"
    assert client.patch(url, json={"desde": "2026-09-01"}, headers=H(p["aux"])).status_code == 422
    assert ok(client.patch(url, json={"soportes": 2}, headers=H(p["coord"])))["soportes"] == 2
    assert client.patch(url, json={"soportes": 3}, headers=H(p["ger"])).status_code == 403

    # Annul (with a reason); it stops counting but stays visible on request
    assert client.post(f"{url}/anular", json={"motivo": ""}, headers=H(p["aux"])).status_code == 422
    a = ok(client.post(f"{url}/anular", json={"motivo": "Fechas equivocadas"}, headers=H(p["aux"])))
    assert (a["novedad"]["estado"], a["novedad"]["anulada_por_name"]) == ("anulada", "Vale Aux")
    assert (
        client.post(f"{url}/anular", json={"motivo": "otra"}, headers=H(p["aux"])).status_code
        == 409
    )
    assert client.patch(url, json={"soportes": 1}, headers=H(p["aux"])).status_code == 409
    lst = ok(client.get(f"{NOV}?{SEP}", headers=H(p["aux"])))
    assert (len(lst["items"]), lst["dias"]["incapacidad"]) == (2, 0)
    lst = ok(client.get(f"{NOV}?{SEP}&anuladas=true", headers=H(p["aux"])))
    assert len(lst["items"]) == 3
    # Once annulled, the same dates can be registered again
    ok(registrar(client, H, p["aux"], p["ana"]), 201)


# ---------------------------------------------------------------- salary


def test_salary_discount(client, db, p, H):
    comp.set_salario(db, p["ana"], 3_000_000, actor=p["ger"])  # $100.000 a day
    sep = date(2026, 9, 1)
    liq1 = next(x for x in comp.liquidaciones(db, p["aux"], sep, 1) if x.user_id == p["ana"].id)
    liq2 = next(x for x in comp.liquidaciones(db, p["aux"], sep, 2) if x.user_id == p["ana"].id)
    assert (liq1.descuento, liq1.novedades) == (0, None)

    # 14–17 sep: 2 days in each cut
    n = ok(registrar(client, H, p["aux"], p["ana"]), 201)["novedad"]
    db.refresh(liq1)
    db.refresh(liq2)
    assert (liq1.descuento, liq1.novedades) == (200_000, "Incapacidad 2 días")
    assert liq2.descuento == 200_000
    # A paid permit is counted but not discounted
    ok(
        registrar(
            client,
            H,
            p["aux"],
            p["ana"],
            tipo="permiso_remunerado",
            desde="2026-09-01",
            hasta="2026-09-01",
        ),
        201,
    )  # noqa: E501
    db.refresh(liq1)
    assert (liq1.descuento, liq1.novedades) == (
        200_000,
        "Incapacidad 2 días · Permiso remunerado 1 día",
    )

    # The Auxiliar confirms the 1st cut: later novedades don't touch it and warn
    comp.accion_salario(db, liq1, "confirmar", actor=p["aux"])
    r = ok(
        registrar(
            client,
            H,
            p["aux"],
            p["ana"],
            tipo="permiso_no_remunerado",
            desde="2026-09-08",
            hasta="2026-09-08",
        ),
        201,
    )  # noqa: E501
    assert r["avisos"] == ["El salario del 1.er corte de sep ya está confirmado: ajústalo a mano."]
    db.refresh(liq1)
    assert liq1.descuento == 200_000

    # Annulling gives the unconfirmed cut its money back
    ok(client.post(f"{NOV}/{n['id']}/anular", json={"motivo": "Error"}, headers=H(p["aux"])))
    db.refresh(liq2)
    assert (liq2.descuento, liq2.novedades) == (0, None)

    # A new salary recalculates the discount; it never goes past the cut's salary
    ok(registrar(client, H, p["aux"], p["ana"], desde="2026-09-16", hasta="2026-09-30"), 201)
    comp.set_salario(db, p["ana"], 1_500_000, actor=p["ger"])
    db.refresh(liq2)
    assert (liq2.salario_corte, liq2.descuento) == (750_000, 750_000)


# ---------------------------------------------------------------- «Del preoperacional»


def test_preoperacional_tab(client, db, p, H):
    def pre(u, d, obs=None, no=False):
        x = Preoperacional(
            user_id=u.id,
            fecha=d,
            realizado_at=datetime.now(UTC),
            medio=MedioTransporte.MOTO,
            placa="KLM78F",
            respuestas=[{"pregunta": "¿Frenos en buen estado?", "si": not no}],
            observaciones=obs,
            tiene_novedad=bool(obs) or no,
        )
        db.add(x)
        return x

    a = pre(p["bruno"], date(2026, 9, 3), "frenos con ruido", no=True)
    pre(p["ana"], date(2026, 9, 4))  # no novedad: not listed
    pre(p["coord"], date(2026, 9, 4), "llanta baja")  # Coordinación's own: only Gerencia reviews
    db.flush()

    rows = ok(client.get(f"{NOV}/preoperacional?{SEP}", headers=H(p["coord"])))
    assert [r["empleado"]["full_name"] for r in rows] == ["Bruno Capta"]
    r = rows[0]
    assert r["medio"] == "Moto · KLM78F"
    assert r["texto"] == "NO en: ¿Frenos en buen estado? · Observación: «frenos con ruido»"
    assert (r["revisado"], r["puede_revisar"]) == (False, True)
    assert ok(client.get(f"{NOV}?{SEP}", headers=H(p["coord"])))["preop_sin_revisar"] == 1

    ger = ok(client.get(f"{NOV}/preoperacional?{SEP}", headers=H(p["ger"])))
    assert len(ger) == 2
    aux = ok(client.get(f"{NOV}/preoperacional?{SEP}", headers=H(p["aux"])))
    assert len(aux) == 2 and not any(x["puede_revisar"] for x in aux)  # sees, doesn't review

    # Reviewed through the preoperacional module
    ok(
        client.post(
            f"/api/v1/preoperacional/{a.id}/revisar",
            json={"nota": "Ya cambió"},
            headers=H(p["coord"]),
        )
    )  # noqa: E501
    r = ok(client.get(f"{NOV}/preoperacional?{SEP}", headers=H(p["coord"])))[0]
    assert (r["revisado"], r["revisado_por_name"], r["puede_revisar"]) == (
        True,
        "Mateo Coord",
        False,
    )
