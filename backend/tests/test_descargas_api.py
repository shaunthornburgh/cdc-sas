"""Descargas del personal (X10): access, filters, the three files and the download log."""

import csv
import io
from datetime import date, datetime

import pytest

from app.models import Marcacion, Novedad, Preoperacional
from app.models.enums import (
    ActividadComercial,
    Cargo,
    EstadoNovedad,
    FuncionIndependiente,
    MedioTransporte,
    TipoNovedad,
)
from app.services import fechas
from tests.conftest import auth_header, login

DS = "/api/v1/descargas"
NOW = datetime(2026, 10, 7, 15, 0, tzinfo=fechas.BOGOTA)  # a Wednesday


@pytest.fixture
def reloj(monkeypatch):
    monkeypatch.setattr(fechas, "now", lambda: NOW)


@pytest.fixture
def p(make_user):
    return {
        "ger": make_user(Cargo.GERENCIA, email="ger@example.com", full_name="Gina Gerencia"),
        "aux": make_user(
            Cargo.AUXILIAR_ADMINISTRATIVA, email="aux@example.com", full_name="Valeria Aux"
        ),
        "coord": make_user(Cargo.COORDINACION, email="coord@example.com", full_name="Mateo Coord"),
        "juan": make_user(
            Cargo.ASESOR,
            email="juan@example.com",
            full_name="Juan Asesor",
            actividades=[ActividadComercial.VENTAS],
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
    return res


def rows(res) -> list[list[str]]:
    text = res.content.decode("utf-8")
    assert text.startswith("﻿")  # Excel reads the accents
    return list(csv.reader(io.StringIO(text[1:]), delimiter=";"))


Q = {"desde": "2026-10-01", "hasta": "2026-10-07"}


def test_access_and_options(client, p, H, reloj):
    for k in ("juan", "laura"):
        assert client.get(DS, headers=H(p[k])).status_code == 403
        assert client.get(f"{DS}/pre.csv", params=Q, headers=H(p[k])).status_code == 403
    o = ok(client.get(DS, headers=H(p["aux"]))).json()
    assert [t["key"] for t in o["tipos"]] == ["pre", "asi", "aus", "pau", "cap"]
    assert all(t["disponible"] for t in o["tipos"])
    c = {t["key"]: t["grupos"] for t in ok(client.get(DS, headers=H(p["coord"]))).json()["tipos"]}
    assert c["pre"] == ["ase", "ate", "aux"] and c["asi"] == ["ase", "ate"]
    # Coordinación can't download Gerencia, a group outside its team, or itself
    r = client.get(
        f"{DS}/pre.csv",
        params=Q | {"alcance": "emp", "user_id": str(p["ger"].id)},
        headers=H(p["coord"]),
    )
    assert r.status_code == 403
    r = client.get(
        f"{DS}/asi.csv", params=Q | {"alcance": "car", "grupo": "aux"}, headers=H(p["coord"])
    )
    assert r.status_code == 403
    # Validation
    assert client.get(f"{DS}/pau.csv", params=Q, headers=H(p["aux"])).status_code == 200
    assert client.get(f"{DS}/xyz.csv", params=Q, headers=H(p["aux"])).status_code == 404
    bad = {"desde": "2026-10-08", "hasta": "2026-10-01"}
    assert client.get(f"{DS}/pre.csv", params=bad, headers=H(p["aux"])).status_code == 422
    largo = {"desde": "2025-01-01", "hasta": "2026-10-01"}
    assert client.get(f"{DS}/pre.csv", params=largo, headers=H(p["aux"])).status_code == 422
    sin = Q | {"alcance": "emp"}
    assert client.get(f"{DS}/pre.csv", params=sin, headers=H(p["aux"])).status_code == 422


def test_preoperacional_file_with_missed_days_and_score(client, p, H, reloj, db):
    juan = p["juan"]
    db.add(
        Preoperacional(
            user_id=juan.id,
            fecha=date(2026, 10, 1),
            realizado_at=datetime(2026, 10, 1, 7, 40, tzinfo=fechas.BOGOTA),
            medio=MedioTransporte.CARRO,
            placa="ABC123",
            respuestas=[{"pregunta": f"Pregunta {i}", "si": i != 2} for i in range(1, 9)],
            tiene_novedad=True,
            observaciones="Una direccional no prende",
        )
    )
    db.add(
        Preoperacional(
            user_id=juan.id,
            fecha=date(2026, 10, 2),
            realizado_at=datetime(2026, 10, 2, 7, 50, tzinfo=fechas.BOGOTA),
            medio=MedioTransporte.A_PIE,
            respuestas=[],
        )
    )
    db.flush()
    params = Q | {"alcance": "emp", "user_id": str(juan.id)}
    prev = ok(client.get(f"{DS}/pre/vista-previa", params=params, headers=H(p["aux"]))).json()
    assert prev["filas"] == 4
    assert prev["archivo"] == "CDC_Preoperacional_JuanAsesor_2026-10-01_a_2026-10-07.csv"
    res = ok(client.get(f"{DS}/pre.csv", params=params, headers=H(p["aux"])))
    assert prev["archivo"] in res.headers["content-disposition"]
    head, *data = rows(res)
    assert head[:4] == ["Persona", "Cargo", "Fecha", "Estado"]
    # Oct 1 and 2 done, Oct 5 and 6 missed (today, Oct 7, counts only once done): 50 % → score 1
    assert [(r[2], r[3]) for r in data] == [
        ("2026-10-01", "Realizado"),
        ("2026-10-02", "Realizado"),
        ("2026-10-05", "No realizado"),
        ("2026-10-06", "No realizado"),
    ]
    assert data[0][6] == "ABC123" and data[0][7].startswith("1 SÍ · 2 NO")
    assert data[0][9] == "Sí" and data[1][7] == "Solo reporte del trayecto"
    assert {r[13] for r in data} == {"1"} and {r[14] for r in data} == {"50"}
    # Logged: «Descargas recientes» and «Registro de cambios» (module Descargas)
    rec = ok(client.get(DS, headers=H(p["aux"]))).json()["recientes"]
    assert rec[0]["archivo"] == prev["archivo"] and rec[0]["filas"] == "4 filas"
    t = ok(
        client.get(
            "/api/v1/registro-cambios",
            params={"modulo": "Descargas", "desde": "2026-10-01", "hasta": "2026-12-31"},
            headers=H(p["ger"]),
        )
    ).json()
    assert any(i["accion"] == "Descargó preoperacionales" for i in t["items"]), t


def test_attendance_and_absences_by_group(client, p, H, reloj, db):
    db.add(
        Marcacion(
            user_id=p["laura"].id,
            fecha=date(2026, 10, 6),
            asignada="Oficina · Sede principal",
            entrada_at=datetime(2026, 10, 6, 8, 0, tzinfo=fechas.BOGOTA),
            entrada_estado="a_tiempo",
            entrada_lugar="Sede principal",
        )
    )
    db.add(
        Marcacion(
            user_id=p["aux"].id,
            fecha=date(2026, 10, 6),
            asignada="Oficina · Sede principal",
            entrada_at=datetime(2026, 10, 6, 8, 0, tzinfo=fechas.BOGOTA),
            entrada_estado="a_tiempo",
        )
    )
    for desde, hasta, estado in (
        (date(2026, 9, 29), date(2026, 10, 2), EstadoNovedad.REGISTRADA),
        (date(2026, 10, 5), date(2026, 10, 5), EstadoNovedad.ANULADA),
        (date(2026, 8, 1), date(2026, 8, 2), EstadoNovedad.REGISTRADA),  # outside the range
    ):
        db.add(
            Novedad(
                empleado_id=p["juan"].id,
                tipo=TipoNovedad.INCAPACIDAD,
                desde=desde,
                hasta=hasta,
                estado=estado,
                registrada_por_id=p["aux"].id,
                motivo_anulacion="Fechas equivocadas" if estado == EstadoNovedad.ANULADA else None,
            )
        )
    db.flush()
    # Asistencia of «Atención y Preventa» only
    res = ok(
        client.get(
            f"{DS}/asi.csv", params=Q | {"alcance": "car", "grupo": "ate"}, headers=H(p["coord"])
        )
    )
    _head, *data = rows(res)
    assert [(r[0], r[1], r[6]) for r in data] == [
        ("Laura Atención", "Atención y Preventa", "A tiempo")
    ]
    assert "CDC_Asistencia_AtencionYPreventa_" in res.headers["content-disposition"]
    # Everyone (Gerencia): the Auxiliar's marcación too
    _h, *todos = rows(ok(client.get(f"{DS}/asi.csv", params=Q, headers=H(p["ger"]))))
    assert {r[0] for r in todos} == {"Laura Atención", "Valeria Aux"}
    # Ausencias: the two that touch the range, the cancelled one with its reason
    head, *aus = rows(ok(client.get(f"{DS}/aus.csv", params=Q, headers=H(p["aux"]))))
    assert head[3] == "Tipo"
    assert [(r[1], r[6], r[11]) for r in aus] == [
        ("Juan Asesor", "2", "Registrada"),
        ("Juan Asesor", "1", "Anulada"),
    ]
    assert aus[1][13] == "Fechas equivocadas"
    # Gerencia has no absences in K13, so it isn't a group here
    r = client.get(
        f"{DS}/aus.csv", params=Q | {"alcance": "car", "grupo": "ger"}, headers=H(p["aux"])
    )
    assert r.status_code == 403
