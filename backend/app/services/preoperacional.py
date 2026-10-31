"""Preoperacional (prototypes M07 / C08 / K09; decisions G-007, G-008, G-012 and «según medio»).

- Everyone does it (all cargos, same form). Gerencia turns it on or off per cargo; when off
  there is no daily reminder, it doesn't count and doesn't lower the score.
- Carro / Moto: plate + 8 SÍ/NO questions. Other means: only a travel report.
- Every NO (or an observation) is a «novedad»; Coordinación marks it as reviewed.
- Who sees whose: Coordinación's goes to Gerencia; Asesores', Atención / Pre-ventas' and the
  Auxiliar's go to Coordinación; Gerencia sees all of them.
- Monthly score from business days (Mon–Fri) done: 100 % = 5 · 90–99 % = 4 · 80–89 % = 3 ·
  70–79 % = 2 · < 70 % = 1. Gerencia's is a record only (no score). A score of 2 or 1
  costs 5 points in the month's result.
"""

import csv
import io
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Preoperacional, PreoperacionalConfig, User
from app.models.enums import MEDIOS_CON_VEHICULO, Cargo, MedioTransporte
from app.services import fechas
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError

M = MedioTransporte
MEDIO_LABELS = {
    M.CARRO: "Carro",
    M.MOTO: "Moto",
    M.BICICLETA: "Bicicleta",
    M.TRANSPORTE_PUBLICO: "Transporte público",
    M.A_PIE: "A pie",
    M.OTRO: "Otro",
}
# Official lists defined by Gerencia (prototype M07).
PREGUNTAS: dict[MedioTransporte, tuple[str, ...]] = {
    M.CARRO: (
        "¿La documentación del conductor y del vehículo está vigente y disponible?",
        "¿Las luces y direccionales funcionan correctamente?",
        "¿Las llantas, incluida la de repuesto, están en buen estado?",
        "¿Los niveles de fluidos son adecuados y no se observan fugas?",
        "¿Los cinturones de seguridad funcionan correctamente y están en buen estado?",
        "¿Los limpiabrisas funcionan correctamente y permiten una buena visibilidad?",
        "¿Los espejos están completos, en buen estado y permiten una adecuada visibilidad?",
        "¿Cuenta con el equipo de prevención y seguridad requerido y está en buen estado?",
    ),
    M.MOTO: (
        "¿La documentación del conductor y de la motocicleta está vigente y disponible?",
        "¿Las luces y direccionales funcionan correctamente?",
        "¿Los frenos están en buen estado y funcionan correctamente?",
        "¿Las llantas están en buen estado?",
        "¿Los espejos están completos y permiten una adecuada visibilidad?",
        "¿Los niveles de fluidos son adecuados y no se observan fugas?",
        "¿Cuenta con casco y elementos de protección en buen estado?",
        "¿Cuenta con el equipo de prevención y seguridad requerido y está en buen estado?",
    ),
}
DESCUENTO_NOTA_BAJA = 5  # points off the month's result when the score is 2 or 1


# ---------------------------------------------------------------- config & access


def config(db: Session) -> dict[Cargo, bool]:
    rows = dict(db.execute(select(PreoperacionalConfig.cargo, PreoperacionalConfig.activo)).all())
    return {c: rows.get(c, True) for c in Cargo}


def set_config(db: Session, cargo: Cargo, activo: bool, *, actor: User) -> dict[Cargo, bool]:
    if actor.cargo != Cargo.GERENCIA:
        raise PermissionDeniedError("Solo Gerencia activa o desactiva el preoperacional por cargo.")
    row = db.get(PreoperacionalConfig, cargo)
    if row is None:
        row = PreoperacionalConfig(cargo=cargo)
        db.add(row)
    row.activo = activo
    row.updated_by_id = actor.id
    db.flush()
    return config(db)


def activo_para(db: Session, user: User) -> bool:
    return config(db)[user.cargo]


def reviewer_cargos(actor: User) -> frozenset[Cargo] | None:
    """Cargos whose preoperacional this person reviews. None = not a reviewer."""
    if actor.cargo == Cargo.GERENCIA:
        return frozenset(Cargo)
    if actor.cargo == Cargo.COORDINACION:
        return frozenset({Cargo.ASESOR, Cargo.ATENCION_CLIENTE, Cargo.AUXILIAR_ADMINISTRATIVA})
    return None


def destinatario(user: User) -> str:
    """Who receives this person's report (shown after sending)."""
    if user.cargo == Cargo.GERENCIA:
        return "Queda como registro."
    if user.cargo == Cargo.COORDINACION:
        return "Le llegó a Gerencia."
    return "Le llegó a Coordinación. Gerencia también puede verlo."


def _ensure_can_review(actor: User, target: User) -> None:
    allowed = reviewer_cargos(actor)
    if allowed is None or target.cargo not in allowed:
        raise PermissionDeniedError("No revisas el preoperacional de esta persona.")


# ---------------------------------------------------------------- submit


def hoy() -> date:
    return fechas.local_date(fechas.now())


def get_de_hoy(db: Session, user: User) -> Preoperacional | None:
    return db.scalar(
        select(Preoperacional).where(
            Preoperacional.user_id == user.id, Preoperacional.fecha == hoy()
        )
    )


def registrar(
    db: Session,
    user: User,
    *,
    medio: MedioTransporte,
    placa: str | None,
    respuestas: list[bool] | None,
    observaciones: str | None,
) -> Preoperacional:
    if not user.is_active:
        raise PermissionDeniedError("Usuario inactivo.")
    if not activo_para(db, user):
        raise PermissionDeniedError("El preoperacional está desactivado para tu cargo.")
    if get_de_hoy(db, user) is not None:
        raise ConflictError("Ya realizaste el preoperacional de hoy.")

    observaciones = (observaciones or "").strip() or None
    guardadas: list[dict[str, Any]] = []
    placa_norm = None
    if medio in MEDIOS_CON_VEHICULO:
        placa_norm = "".join((placa or "").split()).upper()
        if not (5 <= len(placa_norm) <= 7 and placa_norm.isalnum()):
            raise DomainError("Escribe la placa del vehículo (5 a 7 letras y números).")
        preguntas = PREGUNTAS[medio]
        if respuestas is None or len(respuestas) != len(preguntas):
            raise DomainError(f"Responde las {len(preguntas)} preguntas.")
        guardadas = [
            {"pregunta": p, "si": bool(r)} for p, r in zip(preguntas, respuestas, strict=True)
        ]
    # Bicicleta, transporte público, a pie u otro: only the travel report (no plate, no questions).

    pre = Preoperacional(
        user_id=user.id,
        user=user,
        fecha=hoy(),
        realizado_at=fechas.now(),
        medio=medio,
        placa=placa_norm,
        respuestas=guardadas,
        observaciones=observaciones,
        tiene_novedad=any(not r["si"] for r in guardadas) or observaciones is not None,
    )
    db.add(pre)
    try:
        db.flush()
    except IntegrityError:
        raise ConflictError("Ya realizaste el preoperacional de hoy.") from None
    return pre


def revisar(db: Session, pre: Preoperacional, *, nota: str | None, actor: User) -> Preoperacional:
    _ensure_can_review(actor, pre.user)
    if not pre.tiene_novedad:
        raise DomainError("Este preoperacional no tiene novedades para revisar.")
    if pre.revisado_at is not None:
        raise DomainError("La novedad ya fue revisada.")
    pre.revisado_por_id = actor.id
    pre.revisado_por = actor
    pre.revisado_at = fechas.now()
    pre.revision_nota = (nota or "").strip() or None
    db.flush()
    return pre


def get_para_revisar(db: Session, actor: User, pre_id: uuid.UUID) -> Preoperacional:
    pre = db.get(Preoperacional, pre_id)
    if pre is None:
        raise NotFoundError("Preoperacional no encontrado.")
    if pre.user_id != actor.id:
        _ensure_can_review(actor, pre.user)
    return pre


# ---------------------------------------------------------------- scoring


def puntaje(pct: int) -> int:
    if pct >= 100:
        return 5
    if pct >= 90:
        return 4
    if pct >= 80:
        return 3
    if pct >= 70:
        return 2
    return 1


def mes_bounds(mes: str | None) -> tuple[date, date]:
    """'YYYY-MM' (default: current month) → first and last day."""
    today = hoy()
    if mes:
        try:
            y, m = (int(x) for x in mes.split("-"))
            first = date(y, m, 1)
        except ValueError:
            raise DomainError("Mes no válido (usa AAAA-MM).") from None
    else:
        first = today.replace(day=1)
    nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return first, nxt - timedelta(days=1)


def _dias_habiles(desde: date, hasta: date) -> list[date]:
    out, d = [], desde
    while d <= hasta:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


@dataclass(frozen=True)
class Resumen:
    dias_habiles: int
    cumplidos: int
    novedades: int
    pct: int | None
    puntaje: int | None  # None = Gerencia (record only) or no business days yet
    descuento: int


def resumen_mes(
    user: User,
    registros: dict[date, Preoperacional],
    first: date,
    last: date,
    activo: bool,
) -> tuple[Resumen, list[date]]:
    """Business days that count (from the person's start, up to today; today only once done)."""
    today = hoy()
    starts = [fechas.local_date(user.created_at)] + list(registros)
    start = max(first, min(starts)) if starts else first
    end = min(last, today)
    dias = [d for d in _dias_habiles(start, end) if d < today or d in registros]
    cumplidos = sum(1 for d in dias if d in registros)
    if not activo or not dias:
        return Resumen(len(dias), cumplidos, 0, None, None, 0), []
    pct = round(100 * cumplidos / len(dias))
    pts = None if user.cargo == Cargo.GERENCIA else puntaje(pct)
    novedades = sum(1 for d in dias if d in registros and registros[d].tiene_novedad)
    faltantes = [d for d in dias if d not in registros]
    return Resumen(
        len(dias), cumplidos, novedades, pct, pts, DESCUENTO_NOTA_BAJA if pts and pts <= 2 else 0
    ), faltantes


def _registros(db: Session, user_ids: Iterable[uuid.UUID], first: date, last: date) -> dict:
    out: dict[uuid.UUID, dict[date, Preoperacional]] = {}
    ids = list(user_ids)
    if not ids:
        return out
    for p in db.scalars(
        select(Preoperacional).where(
            Preoperacional.user_id.in_(ids),
            Preoperacional.fecha >= first,
            Preoperacional.fecha <= last,
        )
    ).unique():
        out.setdefault(p.user_id, {})[p.fecha] = p
    return out


# ---------------------------------------------------------------- own history (M07 «Mi historial»)


def mi_historial(db: Session, user: User, mes: str | None) -> dict[str, Any]:
    first, last = mes_bounds(mes)
    activo = activo_para(db, user)
    regs = _registros(db, [user.id], first, last).get(user.id, {})
    res, faltantes = resumen_mes(user, regs, first, last, activo)
    today = hoy()
    dias = []
    d = first
    while d <= last:
        if d in regs:
            estado = "novedad" if regs[d].tiene_novedad else "realizado"
        elif d.weekday() >= 5:
            estado = "fin_de_semana"
        elif d >= today:
            estado = "pendiente" if d == today else "futuro"
        elif d in faltantes:
            estado = "no_realizado"
        else:
            estado = "sin_contar"  # before the person started
        dias.append({"fecha": d, "estado": estado})
        d += timedelta(days=1)
    eventos = sorted(
        [
            {"fecha": p.fecha, "tipo": "novedad", "registro": p}
            for p in regs.values()
            if p.tiene_novedad
        ]
        + [{"fecha": f, "tipo": "no_realizado", "registro": None} for f in faltantes],
        key=lambda e: e["fecha"],
    )
    return {
        "mes": f"{first:%Y-%m}",
        "activo": activo,
        "resumen": res,
        "dias": dias,
        "eventos": eventos,
        "registros": sorted(regs.values(), key=lambda p: p.fecha, reverse=True),
    }


# ---------------------------------------------------------------- team (K09)


def equipo(db: Session, actor: User, fecha: date | None = None) -> dict[str, Any]:
    allowed = reviewer_cargos(actor)
    if allowed is None:
        raise PermissionDeniedError(
            "Solo Coordinación y Gerencia ven los preoperacionales del equipo."
        )
    fecha = fecha or hoy()
    cfg = config(db)
    people = [
        u
        for u in db.scalars(select(User).where(User.is_active).order_by(User.full_name)).unique()
        # Coordinación doesn't review its own (it goes to Gerencia); Gerencia sees all, itself too.
        if u.cargo in allowed and (u.id != actor.id or actor.cargo == Cargo.GERENCIA)
    ]
    del_dia = (
        {
            p.user_id: p
            for p in db.scalars(
                select(Preoperacional).where(
                    Preoperacional.fecha == fecha,
                    Preoperacional.user_id.in_([u.id for u in people]),
                )
            ).unique()
        }
        if people
        else {}
    )
    filas = []
    for u in people:
        p = del_dia.get(u.id)
        if not cfg[u.cargo]:
            estado = "desactivado"
        elif p is None:
            estado = "fin_de_semana" if fecha.weekday() >= 5 else "sin_realizar"
        elif p.tiene_novedad:
            estado = "novedad"
        elif p.medio in MEDIOS_CON_VEHICULO:
            estado = "realizado"
        else:
            estado = "reporte"
        filas.append({"user": u, "estado": estado, "registro": p})

    contables = [f for f in filas if f["estado"] not in ("desactivado", "fin_de_semana")]
    first, last = mes_bounds(f"{fecha:%Y-%m}")
    prev_last = first - timedelta(days=1)
    prev_first = prev_last.replace(day=1)
    regs_mes = _registros(db, [u.id for u in people], first, last)
    regs_prev = _registros(db, [u.id for u in people], prev_first, prev_last)
    mes_rows, prev_done, prev_total = [], 0, 0
    for u in people:
        res, _ = resumen_mes(u, regs_mes.get(u.id, {}), first, last, cfg[u.cargo])
        mes_rows.append({"user": u, "resumen": res})
        rp, _ = resumen_mes(u, regs_prev.get(u.id, {}), prev_first, prev_last, cfg[u.cargo])
        if u.cargo != Cargo.GERENCIA and rp.pct is not None:
            prev_done += rp.cumplidos
            prev_total += rp.dias_habiles
    return {
        "fecha": fecha,
        "mes": f"{first:%Y-%m}",
        "config": cfg,
        "kpis": {
            "total": len(contables),
            "realizados": sum(1 for f in contables if f["estado"] != "sin_realizar"),
            "con_novedad": sum(1 for f in contables if f["estado"] == "novedad"),
            "novedades_sin_revisar": sum(
                1
                for f in contables
                if f["estado"] == "novedad" and f["registro"].revisado_at is None
            ),
            "sin_realizar": sum(1 for f in contables if f["estado"] == "sin_realizar"),
            "cumplimiento_mes_anterior": round(100 * prev_done / prev_total)
            if prev_total
            else None,
        },
        "filas": filas,
        "mes_rows": mes_rows,
    }


def hoy_resumen(db: Session, actor: User) -> dict[str, Any]:
    """Compact numbers for dashboards (K01 card, M01 banner)."""
    data = equipo(db, actor)
    faltan = [f["user"].full_name for f in data["filas"] if f["estado"] == "sin_realizar"]
    estados = {f["user"].id: f["estado"] for f in data["filas"]}
    return {**data["kpis"], "faltan": faltan, "por_persona": estados}


# ---------------------------------------------------------------- export (CSV opens in Excel)


def export_csv(db: Session, actor: User, mes: str | None, user_id: uuid.UUID | None) -> str:
    allowed = reviewer_cargos(actor)
    if allowed is None:
        raise PermissionDeniedError("Solo Coordinación y Gerencia descargan preoperacionales.")
    first, last = mes_bounds(mes)
    stmt = (
        select(Preoperacional)
        .join(User, User.id == Preoperacional.user_id)
        .where(Preoperacional.fecha >= first, Preoperacional.fecha <= last, User.cargo.in_(allowed))
        .order_by(User.full_name, Preoperacional.fecha)
    )
    if user_id:
        stmt = stmt.where(Preoperacional.user_id == user_id)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(
        [
            "Persona",
            "Cargo",
            "Fecha",
            "Hora",
            "Medio",
            "Placa",
            "Respuestas NO",
            "Novedad",
            "Observaciones",
            "Revisado por",
            "Revisado",
        ]
    )
    for p in db.scalars(stmt).unique():
        w.writerow(
            [
                p.user.full_name,
                p.user.cargo.value,
                p.fecha.isoformat(),
                p.realizado_at.astimezone(fechas.BOGOTA).strftime("%H:%M"),
                MEDIO_LABELS[p.medio],
                p.placa or "",
                " · ".join(PREGUNTAS[p.medio][n - 1] for n in p.respuestas_no)
                if p.respuestas_no
                else "",
                "Sí" if p.tiene_novedad else "No",
                p.observaciones or "",
                p.revisado_por_name or "",
                p.revisado_at.astimezone(fechas.BOGOTA).strftime("%Y-%m-%d %H:%M")
                if p.revisado_at
                else "",
            ]
        )
    return "﻿" + buf.getvalue()  # BOM so Excel opens accents correctly
