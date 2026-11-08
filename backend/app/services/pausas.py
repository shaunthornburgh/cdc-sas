"""Pausas activas (prototype G11 and the Inicio banner; decisions G-041, G-045, G-060, G-065).

* **Who**: everyone active, every cargo including Gerencia, has two pauses a day (mañana and
  tarde), on working days (Monday to Friday) from the day they started.
* **The reminder**: at the scheduled time each person's Inicio shows «Es hora de tu pausa activa»
  with the message and «Realizada». It stays for the configured minutes (G-060) or until they tap
  it. Tapping it records the person, date, pause and time. Outside that window there is nothing to
  mark, and once the window has passed without it, that pause is «No realizada».
* **Absences**: a day with a registered absence («Ausencias y permisos») doesn't count.
* **Schedule** (G-045): the Auxiliar administrativa sets both times and the minutes on screen.
  **Message** (G-065): the Auxiliar and Gerencia; it can't be empty. Each change goes to «Registro
  de cambios» (module «Pausas activas»). Gerencia consults and downloads; it doesn't change the
  schedule.
* **Team view**: the Auxiliar and Gerencia see everyone; Coordinación sees its team (asesores and
  Atención y Preventa), read-only. It doesn't count in the indicators (G-045): it's a compliance
  record.
* **Download**: «Descargas del personal» › Pausas activas (and the «Descargar Excel» button here).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConfigEvento, Novedad, PausaActiva, PausaConfig, User
from app.models.enums import Cargo, EstadoNovedad
from app.services import fechas
from app.services.errors import ConflictError, DomainError, PermissionDeniedError

SECCION = "pausas_activas"  # in configuracion_eventos
DEFAULT = {
    "hora_manana": time(10, 0),
    "hora_tarde": time(15, 0),
    "minutos": 15,
    "mensaje": "Haz tu pausa activa: estira cuello, hombros y espalda (mensaje de ejemplo).",
}
TURNOS = {"manana": "mañana", "tarde": "tarde"}
MAX_DIAS = 366


# ---------------------------------------------------------------- config & access


@dataclass(frozen=True)
class Cfg:
    hora_manana: time
    hora_tarde: time
    minutos: int
    mensaje: str

    def hora(self, turno: str) -> time:
        return self.hora_manana if turno == "manana" else self.hora_tarde


def cfg(db: Session) -> Cfg:
    row = db.get(PausaConfig, 1)
    if row is None:
        return Cfg(**DEFAULT)
    return Cfg(row.hora_manana, row.hora_tarde, row.minutos, row.mensaje)


def ve_equipo(u: User) -> bool:
    return u.is_active and u.cargo in (
        Cargo.AUXILIAR_ADMINISTRATIVA,
        Cargo.GERENCIA,
        Cargo.COORDINACION,
    )


def cambia_horario(u: User) -> bool:
    return u.is_active and u.cargo == Cargo.AUXILIAR_ADMINISTRATIVA


def cambia_mensaje(u: User) -> bool:
    return u.is_active and u.cargo in (Cargo.AUXILIAR_ADMINISTRATIVA, Cargo.GERENCIA)


def _row(db: Session) -> PausaConfig:
    row = db.get(PausaConfig, 1)
    if row is None:
        row = PausaConfig(id=1, **DEFAULT)
        db.add(row)
        db.flush()
    return row


def _log(db: Session, actor: User, antes: dict, despues: dict, detalle: str) -> None:
    db.add(
        ConfigEvento(
            seccion=SECCION, actor_id=actor.id, antes=antes, despues=despues, detalle=detalle
        )
    )


def h12(t: time) -> str:
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d} {'a. m.' if t.hour < 12 else 'p. m.'}"


def set_horario(db: Session, manana: time, tarde: time, minutos: int, *, actor: User) -> Cfg:
    """G-045: the Auxiliar sets the schedule (times on the 15-minute clock)."""
    if not cambia_horario(actor):
        raise PermissionDeniedError(
            "El horario de las pausas lo configura la Auxiliar administrativa."
        )
    for t in (manana, tarde):
        if t.minute % 15 or t.second:
            raise DomainError("Las horas van en intervalos de 15 minutos.")
    if not manana < time(12, 0) <= tarde:
        raise DomainError("La pausa de la mañana va antes de las 12:00 y la de la tarde después.")
    if not 5 <= minutos <= 60:
        raise DomainError("El aviso queda en pantalla entre 5 y 60 minutos.")
    row = _row(db)
    antes = {"mañana": h12(row.hora_manana), "tarde": h12(row.hora_tarde), "minutos": row.minutos}
    row.hora_manana, row.hora_tarde, row.minutos = manana, tarde, minutos
    row.updated_by_id, row.updated_at = actor.id, fechas.now()
    despues = {"mañana": h12(manana), "tarde": h12(tarde), "minutos": minutos}
    if antes != despues:
        _log(db, actor, antes, despues, "Horario de las pausas")
    db.flush()
    return cfg(db)


def set_mensaje(db: Session, mensaje: str, *, actor: User) -> Cfg:
    """G-065: the message on everyone's Inicio (Auxiliar and Gerencia)."""
    if not cambia_mensaje(actor):
        raise PermissionDeniedError(
            "El mensaje lo pueden cambiar la Auxiliar administrativa y Gerencia."
        )
    m = (mensaje or "").strip()
    if not m:
        raise DomainError("Escribe el mensaje.")
    if len(m) > 300:
        raise DomainError("El mensaje puede tener hasta 300 caracteres.")
    row = _row(db)
    if row.mensaje != m:
        _log(db, actor, {"mensaje": row.mensaje}, {"mensaje": m}, "Mensaje de la pausa activa")
        row.mensaje = m
        row.updated_by_id, row.updated_at = actor.id, fechas.now()
    db.flush()
    return cfg(db)


# ---------------------------------------------------------------- slots


def _dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=fechas.BOGOTA)


def ventana(c: Cfg, d: date, turno: str) -> tuple[datetime, datetime]:
    a = _dt(d, c.hora(turno))
    return a, a + timedelta(minutes=c.minutos)


def activa(c: Cfg, now: datetime) -> str | None:
    """The pause whose reminder is on screen now (working days only)."""
    d = fechas.local_date(now)
    if d.weekday() >= 5:
        return None
    for t in TURNOS:
        a, b = ventana(c, d, t)
        if a <= now < b:
            return t
    return None


def _inicio(u: User) -> date:
    return fechas.local_date(u.created_at)


def _ausencias(db: Session, ids: list[uuid.UUID], d1: date, d2: date) -> set[tuple]:
    out: set[tuple] = set()
    if not ids:
        return out
    for n in db.scalars(
        select(Novedad).where(
            Novedad.empleado_id.in_(ids),
            Novedad.estado == EstadoNovedad.REGISTRADA,
            Novedad.desde <= d2,
            Novedad.hasta >= d1,
        )
    ).unique():
        d = max(n.desde, d1)
        while d <= min(n.hasta, d2):
            out.add((n.empleado_id, d))
            d += timedelta(days=1)
    return out


def _registros(db: Session, ids: list[uuid.UUID], d1: date, d2: date) -> dict[tuple, PausaActiva]:
    if not ids:
        return {}
    return {
        (p.user_id, p.fecha, p.turno): p
        for p in db.scalars(
            select(PausaActiva).where(
                PausaActiva.user_id.in_(ids), PausaActiva.fecha >= d1, PausaActiva.fecha <= d2
            )
        ).unique()
    }


@dataclass
class Slot:
    user: User
    fecha: date
    turno: str
    programada: time
    estado: str  # realizada · no_realizada · en_curso · programada · ausencia
    realizada_at: datetime | None = None

    @property
    def txt(self) -> tuple[str, str]:
        if self.estado == "realizada":
            t = self.realizada_at.astimezone(fechas.BOGOTA).strftime("%H:%M")
            return f"✓ Realizada · {t}", "ok"
        return {
            "no_realizada": ("No realizada", "bad"),
            "en_curso": ("Ahora · por marcar", "warn"),
            "programada": ("Programada", "gray"),
            "ausencia": ("Ausencia", "info"),
        }[self.estado]


def slots(db: Session, gente: list[User], d1: date, d2: date, now: datetime) -> list[Slot]:
    """Every pause of these people in the range (working days, from their start)."""
    c = cfg(db)
    ids = [u.id for u in gente]
    regs = _registros(db, ids, d1, d2)
    aus = _ausencias(db, ids, d1, d2)
    con_registro = {k[:2] for k in regs}
    out = []
    d = d1
    while d <= d2:
        if d.weekday() < 5:
            for u in gente:
                if d < _inicio(u) and (u.id, d) not in con_registro:
                    continue
                for t in TURNOS:
                    r = regs.get((u.id, d, t))
                    a, b = ventana(c, d, t)
                    if r is not None:
                        out.append(Slot(u, d, t, r.programada, "realizada", r.realizada_at))
                    elif (u.id, d) in aus:
                        out.append(Slot(u, d, t, c.hora(t), "ausencia"))
                    elif now >= b:
                        out.append(Slot(u, d, t, c.hora(t), "no_realizada"))
                    elif now >= a:
                        out.append(Slot(u, d, t, c.hora(t), "en_curso"))
                    else:
                        out.append(Slot(u, d, t, c.hora(t), "programada"))
        d += timedelta(days=1)
    return out


def cumplimiento(ss: list[Slot]) -> tuple[int | None, int, int]:
    """(% done of the pauses that already closed, done, missed)."""
    hechas = sum(1 for s in ss if s.estado == "realizada")
    faltas = sum(1 for s in ss if s.estado == "no_realizada")
    total = hechas + faltas
    return (round(100 * hechas / total) if total else None), hechas, faltas


# ---------------------------------------------------------------- the person


def ahora(db: Session, user: User) -> dict[str, Any]:
    """The Inicio banner and today's two pauses."""
    c = cfg(db)
    now = fechas.now()
    hoy = fechas.local_date(now)
    hoy_slots = slots(db, [user], hoy, hoy, now) if user.is_active else []
    t = activa(c, now)
    pendiente = next((s for s in hoy_slots if s.turno == t and s.estado == "en_curso"), None)
    _a, fin = ventana(c, hoy, t) if t else (None, None)
    return {
        "mensaje": c.mensaje,
        "minutos": c.minutos,
        "activa": (
            {"turno": t, "titulo": f"pausa activa de la {TURNOS[t]}", "hasta": fin}
            if pendiente is not None
            else None
        ),
        "hoy": [_slot(s) for s in hoy_slots],
        "horario": {"manana": h12(c.hora_manana), "tarde": h12(c.hora_tarde)},
    }


def marcar(db: Session, user: User) -> PausaActiva:
    """«Realizada»: only while the reminder is on screen."""
    if not user.is_active:
        raise PermissionDeniedError("Tu usuario no está activo.")
    c = cfg(db)
    now = fechas.now()
    t = activa(c, now)
    if t is None:
        raise ConflictError("Ahora no hay una pausa activa por marcar.")
    hoy = fechas.local_date(now)
    existe = db.scalar(
        select(PausaActiva).where(
            PausaActiva.user_id == user.id, PausaActiva.fecha == hoy, PausaActiva.turno == t
        )
    )
    if existe is not None:
        raise ConflictError(f"Ya marcaste la pausa de la {TURNOS[t]}.")
    p = PausaActiva(user_id=user.id, fecha=hoy, turno=t, programada=c.hora(t), realizada_at=now)
    db.add(p)
    db.flush()
    return p


def _slot(s: Slot) -> dict[str, Any]:
    e, cls = s.txt
    return {
        "fecha": s.fecha,
        "turno": s.turno,
        "turno_txt": TURNOS[s.turno].capitalize(),
        "programada": h12(s.programada),
        "estado": s.estado,
        "estado_txt": e,
        "estado_cls": cls,
        "realizada_at": s.realizada_at,
    }


def _rango(d1: date, d2: date) -> None:
    if d1 > d2:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    if (d2 - d1).days + 1 > MAX_DIAS:
        raise DomainError("El periodo puede ser de hasta un año.")


def _por_dia(ss: list[Slot]) -> list[dict[str, Any]]:
    dias: dict[tuple, dict[str, Any]] = {}
    for s in ss:
        k = (s.user.id, s.fecha)
        r = dias.setdefault(
            k, {"fecha": s.fecha, "user_id": s.user.id, "full_name": s.user.full_name}
        )
        r[s.turno] = _slot(s)
    return sorted(dias.values(), key=lambda r: (r["fecha"], r["full_name"]), reverse=True)


def mias(db: Session, user: User, d1: date, d2: date) -> dict[str, Any]:
    _rango(d1, d2)
    now = fechas.now()
    ss = slots(db, [user], d1, min(d2, fechas.local_date(now)), now)
    pct, hechas, faltas = cumplimiento(ss)
    return {
        "desde": d1,
        "hasta": d2,
        "resumen": {"pct": pct, "realizadas": hechas, "no_realizadas": faltas},
        "dias": _por_dia(ss),
        "ve_equipo": ve_equipo(user),
    }


# ---------------------------------------------------------------- team (G11)


CARGO_TXT = {
    Cargo.ASESOR: "Asesor comercial",
    Cargo.ATENCION_CLIENTE: "Atención y Preventa",
    Cargo.COORDINACION: "Coordinación",
    Cargo.AUXILIAR_ADMINISTRATIVA: "Auxiliar administrativa",
    Cargo.GERENCIA: "Gerencia",
}


def cargo_txt(u: User) -> str:
    if u.cargo == Cargo.ASESOR and u.funcion is not None:
        return "Atención y Preventa"
    return CARGO_TXT.get(u.cargo, u.cargo.value)


def equipo_de(db: Session, viewer: User) -> list[User]:
    """Auxiliar and Gerencia: everyone. Coordinación: asesores and Atención y Preventa."""
    from app.services.descargas import grupo

    gente = list(db.scalars(select(User).where(User.is_active).order_by(User.full_name)).unique())
    if viewer.cargo == Cargo.COORDINACION:
        return [u for u in gente if grupo(u) in ("ase", "ate")]
    return gente


def equipo(
    db: Session, viewer: User, d1: date, d2: date, user_id: uuid.UUID | None = None
) -> dict[str, Any]:
    if not ve_equipo(viewer):
        raise PermissionDeniedError(
            "El registro de pausas activas lo ven la Auxiliar administrativa, Coordinación y "
            "Gerencia."
        )
    _rango(d1, d2)
    now = fechas.now()
    hoy = fechas.local_date(now)
    c = cfg(db)
    gente = equipo_de(db, viewer)
    if user_id is not None:
        gente_f = [u for u in gente if u.id == user_id]
        if not gente_f:
            raise PermissionDeniedError("No ves las pausas de esa persona.")
    else:
        gente_f = gente
    hoy_ss = slots(db, gente_f, hoy, hoy, now)
    rango_ss = slots(db, gente_f, d1, min(d2, hoy), now) if d1 <= hoy else []
    pct, _h, faltas = cumplimiento(rango_ss)

    def kpi(turno: str) -> dict[str, Any]:
        ss = [s for s in hoy_ss if s.turno == turno and s.estado != "ausencia"]
        hechas = [s for s in ss if s.estado == "realizada"]
        faltan = [s.user.full_name.split()[0] for s in ss if s.estado == "no_realizada"]
        a, b = ventana(c, hoy, turno)
        return {
            "hechas": len(hechas),
            "total": len(ss),
            "faltan": faltan,
            "estado": "cerrada" if now >= b else ("en_curso" if now >= a else "programada"),
            "hora": h12(c.hora(turno)),
        }

    filas_hoy = []
    for u in gente_f:
        mine = {s.turno: s for s in hoy_ss if s.user.id == u.id}
        if not mine:
            continue
        filas_hoy.append(
            {
                "user_id": u.id,
                "full_name": u.full_name,
                "cargo": cargo_txt(u),
                "manana": _slot(mine["manana"]),
                "tarde": _slot(mine["tarde"]),
            }
        )
    return {
        "desde": d1,
        "hasta": d2,
        "hoy": hoy,
        "habil": hoy.weekday() < 5,
        "config": {
            "hora_manana": c.hora_manana.strftime("%H:%M"),
            "hora_tarde": c.hora_tarde.strftime("%H:%M"),
            "manana_txt": h12(c.hora_manana),
            "tarde_txt": h12(c.hora_tarde),
            "minutos": c.minutos,
            "mensaje": c.mensaje,
        },
        "kpis": {"manana": kpi("manana"), "tarde": kpi("tarde"), "pct": pct, "faltas": faltas},
        "hoy_filas": filas_hoy,
        "persona": (
            {"full_name": gente_f[0].full_name, "dias": _por_dia(rango_ss)} if user_id else None
        ),
        "personas": [{"id": u.id, "full_name": u.full_name} for u in gente],
        "puede": {
            "horario": cambia_horario(viewer),
            "mensaje": cambia_mensaje(viewer),
            "descargar": True,
        },
        "rol": viewer.cargo.value,
    }
