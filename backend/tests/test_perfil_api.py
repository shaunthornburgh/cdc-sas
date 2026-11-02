"""Mi perfil (Z01 / M11) and the personal data Coordinación / Gerencia keep in «Usuarios»."""

import pytest

from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, FuncionIndependiente
from tests.conftest import TEST_PASSWORD, auth_header, login

PF = "/api/v1/perfil"
US = "/api/v1/users"
PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Vale Aux"
        ),
        "juan": make_user(
            email="juan@example.com", full_name="Juan Asesor", actividades=[A.CAPTACION, A.VENTAS]
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


def ok(res, code=200):
    assert res.status_code == code, res.text
    return res.json()


def datos(res):
    return {d["k"]: d["v"] for d in res["datos"]}


def test_profile_per_cargo(client, p, H):
    j = ok(client.get(PF, headers=H(p["juan"])))
    assert (j["cargo_txt"], j["area"], j["actividades"]) == (
        "Asesor comercial",
        "Comercial",
        ["Captación", "Ventas"],
    )
    d = datos(j)
    assert d["Correo (usuario)"] == "juan@example.com" and d["Coordinador"] == "Mateo Coord"
    assert (d["Teléfono"], d["Cédula"]) == ("Sin registrar", "Sin registrar")
    assert j["regla_nombre"].startswith("Tu nombre y tus demás datos los cambian")
    assert j["resultados"]["href"] == "/resultados"
    assert [a["t"] for a in j["accesos"]] == [
        "Mis resultados",
        "Mis pagos y bonos",
        "Mi preoperacional",
        "Mi agenda",
    ]
    c = ok(client.get(PF, headers=H(p["coord"])))
    assert (
        datos(c)["Equipo a cargo"] == "2 personas"
        and c["regla_nombre"] == "Tu nombre lo cambia Gerencia."
    )
    a = ok(client.get(PF, headers=H(p["aux"])))
    assert (datos(a)["Reporta a"], a["resultados"]) == ("Gerencia", None)
    g = ok(client.get(PF, headers=H(p["ger"])))
    assert datos(g)["Acceso"] == "Completo" and "Mis pagos y bonos" not in [
        x["t"] for x in g["accesos"]
    ]
    assert ok(client.get(PF, headers=H(p["laura"])))["area"] == "Atención y Preventa"


def test_managers_keep_personal_data_with_history(client, p, H):
    url = f"{US}/{p['juan'].id}"
    body = {"telefono": "300 000 0021", "documento": "1.020.454.521", "fecha_ingreso": "2026-02-02"}
    # The person can't change their own data
    assert client.patch(url, json=body, headers=H(p["juan"])).status_code == 403
    assert client.patch(url, json={"telefono": "abc"}, headers=H(p["coord"])).status_code == 422
    assert (
        client.patch(url, json={"fecha_ingreso": "2099-01-01"}, headers=H(p["coord"])).status_code
        == 422
    )
    u = ok(client.patch(url, json=body, headers=H(p["coord"])))
    assert (u["telefono"], u["documento"], u["fecha_ingreso"]) == (
        "300 000 0021",
        "1.020.454.521",
        "2026-02-02",
    )
    d = datos(ok(client.get(PF, headers=H(p["juan"]))))
    assert (d["Teléfono"], d["Cédula"], d["Fecha de ingreso"]) == (
        "300 000 0021",
        "••••••4521",
        "2 feb 2026",
    )
    ok(client.patch(url, json={"full_name": "Juan Pérez", "telefono": ""}, headers=H(p["coord"])))
    h = ok(client.get(f"{url}/cambios", headers=H(p["ger"])))
    porcampo = {x["campo"]: x for x in reversed(h)}  # newest wins
    assert (porcampo["full_name"]["antes"], porcampo["full_name"]["despues"]) == (
        "Juan Asesor",
        "Juan Pérez",
    )
    assert porcampo["documento"]["despues"] == "••••••4521"  # never stored in clear in the history
    assert (
        porcampo["telefono"]["despues"] is None
        and porcampo["telefono"]["actor_name"] == "Mateo Coord"
    )
    assert client.get(f"{url}/cambios", headers=H(p["juan"])).status_code == 403
    # Coordinación still can't touch Gerencia
    assert (
        client.patch(
            f"{US}/{p['ger'].id}", json={"telefono": "3001112222"}, headers=H(p["coord"])
        ).status_code
        == 403
    )


def test_photo(client, p, H):
    h = H(p["laura"])
    assert (
        client.put(f"{PF}/foto", json={"foto": "data:text/html;base64,PGI+"}, headers=h).status_code
        == 422
    )
    big = "data:image/png;base64," + "A" * 401_000
    assert client.put(f"{PF}/foto", json={"foto": big}, headers=h).status_code == 422
    assert ok(client.put(f"{PF}/foto", json={"foto": PNG}, headers=h))["foto"] == PNG
    assert ok(client.get(f"{PF}/foto", headers=h))["foto"] == PNG
    assert ok(client.get(PF, headers=h))["tiene_foto"] is True
    ok(client.put(f"{PF}/foto", json={"foto": None}, headers=h))
    hist = ok(client.get(f"{US}/{p['laura'].id}/cambios", headers=H(p["coord"])))
    assert [(x["campo"], x["antes"], x["despues"]) for x in hist] == [
        ("foto", "con foto", "sin foto"),
        ("foto", "sin foto", "con foto"),
    ]


def test_password(client, p, H):
    h = H(p["aux"])
    url = f"{PF}/password"
    assert (
        client.post(url, json={"actual": "mala", "nueva": "OtraClave2026"}, headers=h).status_code
        == 422
    )
    assert (
        client.post(url, json={"actual": TEST_PASSWORD, "nueva": "corta"}, headers=h).status_code
        == 422
    )
    assert (
        client.post(
            url, json={"actual": TEST_PASSWORD, "nueva": TEST_PASSWORD}, headers=h
        ).status_code
        == 422
    )
    assert (
        client.post(
            url, json={"actual": TEST_PASSWORD, "nueva": "aux@example.com"}, headers=h
        ).status_code
        == 422
    )
    assert (
        client.post(
            url, json={"actual": TEST_PASSWORD, "nueva": "OtraClave2026"}, headers=h
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "aux@example.com", "password": TEST_PASSWORD}
        ).status_code
        == 401
    )
    assert login(client, "aux@example.com", "OtraClave2026")["access_token"]


def test_data_policy(client, p, H):
    h = H(p["juan"])
    assert ok(client.get(PF, headers=h))["politica_aceptada_at"] is None
    assert ok(client.post(f"{PF}/politica", headers=h))["politica_aceptada_at"]
    assert client.post(f"{PF}/politica", headers=h).status_code == 409
