"""Capacitaciones (prototypes X07 «Capacitaciones del equipo» and Z03 «Mis capacitaciones»;
decisions G-046, G-047 and G-086).

* **Programar** (X07): the Auxiliar administrativa, Coordinación and Gerencia program a training
  (date, time, área, tema, who presents, place or link) for the whole team, a group (Comercial,
  Atención y Preventa, Administrativa) or specific people. Everyone active except Gerencia can take
  part. Each participant gets an aviso and the training shows in their agenda.
* **Responder** (Z03): each participant accepts, or says they can't with a reason (cita con
  cliente, incapacidad o permiso, vacaciones, otro). The answer can change until it's completed.
* **Completar**: once the start time has passed, an organizer marks who attended (those who
  accepted are preselected) and the training is «realizada». It can also be cancelled with a
  reason while still programmed.
* **Registrar participación** (Z03): anyone records a training they took on their own (date, time,
  tema, área, who presented, what they learned, observations). It goes to the Auxiliar and Gerencia
  (aviso) and to the person's history.
* **Qué aprendí**: after attending a programmed one, the person can add what they learned.
* **Who sees what**: everyone sees their own («Mis capacitaciones»); the Auxiliar, Coordinación and
  Gerencia see the team's. The Excel (CSV) is for the Auxiliar and Gerencia only (G-047), from
  «Capacitaciones del equipo» or «Descargas del personal».
* Every change is a `CapacitacionEvento`, shown in «Registro de cambios» (module «Capacitaciones»).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Capacitacion, CapacitacionEvento, CapacitacionParticipante, User
from app.models.enums import Cargo
from app.services import fechas
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError

AREAS = [
    "Todas las áreas",
    "Comercial",
    "Atención y Preventa",
    "Administrativa",
    "Seguridad y salud en el trabajo",
    "Otra",
]
PARTICIPANTES = {
    "todo": "Todo el equipo",
    "com": "Comercial",
    "ate": "Atención y Preventa",
    "adm": "Administrativa",
    "per": "Personas específicas",
}
MOTIVOS = ["Cita con cliente a esa hora", "Incapacidad o permiso", "Vacaciones", "Otro motivo"]
# Z03 speaks to the person: «✓ Aceptaste participar», «✓ Participé»…
PRIMERA_PERSONA = {
    "✓ Aceptó": "✓ Aceptaste participar",
    "✕ No participa": "✕ No participarás",
    "✓ Participó": "✓ Participé",
    "✕ No participó": "✕ No participé",
}
ORGANIZAN = (Cargo.AUXILIAR_ADMINISTRATIVA, Cargo.COORDINACION, Cargo.GERENCIA)
DESCARGAN = (Cargo.AUXILIAR_ADMINISTRATIVA, Cargo.GERENCIA)
ORIGEN_POR = {
    Cargo.GERENCIA: "Programada por Gerencia",
    Cargo.COORDINACION: "Programada por Coordinación",
    Cargo.AUXILIAR_ADMINISTRATIVA: "Programada por la Auxiliar administrativa",
}


# ---------------------------------------------------------------- access


def organiza(u: User) -> bool:
    return u.is_active and u.cargo in ORGANIZAN


def descarga(u: User) -> bool:
    return u.is_active and u.cargo in DESCARGAN


def ensure_organiza(u: User) -> None:
    if not organiza(u):
        raise PermissionDeniedError(
            "Las capacitaciones del equipo las manejan la Auxiliar administrativa, Coordinación y "
            "Gerencia."
        )


def get(db: Session, user: User, id_: uuid.UUID) -> Capacitacion:
    c = db.get(Capacitacion, id_)
    if c is None or not (organiza(user) or _part(c, user) is not None):
        raise NotFoundError("Esa capacitación no existe.")
    return c


# ---------------------------------------------------------------- helpers


def grupo(u: User) -> str:
    from app.services.descargas import grupo as g

    return g(u)


def elegibles(db: Session) -> list[User]:
    """Who can take part: everyone active except Gerencia (X07's team)."""
    return list(
        db.scalars(
            select(User)
            .where(User.is_active.is_(True), User.cargo != Cargo.GERENCIA)
            .order_by(User.full_name)
        ).unique()
    )


def _part(c: Capacitacion, u: User) -> CapacitacionParticipante | None:
    return next((p for p in c.participantes if p.user_id == u.id), None)


def _ev(db: Session, c: Capacitacion, accion: str, actor: User | None, detalle: str | None = None):
    db.add(
        CapacitacionEvento(
            capacitacion_id=c.id,
            accion=accion,
            detalle=detalle,
            actor_id=actor.id if actor else None,
        )
    )


def _txt(v: Any, campo: str, n: int, *, req: bool = False) -> str | None:
    s = (str(v).strip() if v is not None else "") or None
    if req and not s:
        raise DomainError(f"Escribe {campo}.")
    if s and len(s) > n:
        raise DomainError(f"{campo.capitalize()} puede tener hasta {n} caracteres.")
    return s


def _inicio(data: dict[str, Any]) -> datetime:
    f, h = data.get("fecha"), data.get("hora")
    if not f or not h:
        raise DomainError("Elige la fecha y la hora.")
    if isinstance(f, str):
        f = date.fromisoformat(f)
    if isinstance(h, str):
        h = time.fromisoformat(h)
    return datetime.combine(f, h, tzinfo=fechas.BOGOTA)


def _area(v: Any) -> str:
    if v not in AREAS:
        raise DomainError("Elige el área.")
    return v


def hora_txt(dt: datetime) -> str:
    d = dt.astimezone(fechas.BOGOTA)
    h12 = d.hour % 12 or 12
    m = f":{d.minute:02d}"
    return f"{h12}{m} {'a. m.' if d.hour < 12 else 'p. m.'}"


def cuando(dt: datetime) -> str:
    """«jue 9 oct · 8:00 a. m.» (X07)."""
    d = dt.astimezone(fechas.BOGOTA)
    return f"{fechas._DIAS[d.weekday()]} {d.day} {fechas._MESES[d.month - 1]} · {hora_txt(dt)}"


def origen_txt(c: Capacitacion, para: User | None = None) -> str:
    if c.origen == "registrada":
        if para is not None and c.created_by_id == para.id:
            return "La registré yo"
        return f"Registrada por {c.created_by.full_name if c.created_by else '—'}"
    cargo = c.created_by.cargo if c.created_by else None
    return ORIGEN_POR.get(cargo, "Programada")


def estado_part(c: Capacitacion, p: CapacitacionParticipante) -> tuple[str, str, str]:
    """(state text, chip class, reason text) of one person in one training."""
    motivo = ""
    if p.motivo:
        motivo = (
            "Motivo: " + p.motivo.lower() + (f" · {p.motivo_detalle}" if p.motivo_detalle else "")
        )
    if c.estado == "cancelada":
        return "Cancelada", "gray", c.cancelada_motivo or ""
    if c.estado == "realizada":
        if p.asistio:
            return "✓ Participó", "ok", ""
        return "✕ No participó", "bad", motivo or "Sin respuesta"
    if p.respuesta == "acepta":
        return "✓ Aceptó", "ok", ""
    if p.respuesta == "no":
        return "✕ No participa", "bad", motivo
    return "Por responder", "warn", ""


# ---------------------------------------------------------------- actions


def _gente(db: Session, actor: User, data: dict[str, Any]) -> tuple[list[User], str]:
    k = data.get("participantes") or "todo"
    if k not in PARTICIPANTES:
        raise DomainError("Elige quiénes deben participar.")
    pool = elegibles(db)
    if k == "per":
        ids = {uuid.UUID(str(i)) for i in data.get("personas") or []}
        gente = [u for u in pool if u.id in ids]
        if len(gente) != len(ids):
            raise DomainError("Alguna de las personas elegidas no puede participar.")
    else:
        g = {"com": "ase", "ate": "ate", "adm": "aux"}.get(k)
        gente = [u for u in pool if g is None or grupo(u) == g]
    if not gente:
        raise DomainError("Elige al menos una persona que deba participar.")
    return gente, PARTICIPANTES[k]


def programar(db: Session, data: dict[str, Any], *, actor: User) -> Capacitacion:
    ensure_organiza(actor)
    inicio = _inicio(data)
    if inicio < fechas.now() - timedelta(minutes=5):
        raise DomainError("La fecha y la hora ya pasaron: elige una futura.")
    gente, txt = _gente(db, actor, data)
    c = Capacitacion(
        origen="programada",
        tema=_txt(data.get("tema"), "el tema", 200, req=True),
        area=_area(data.get("area")),
        presenta=_txt(data.get("presenta"), "quién la presenta", 200, req=True),
        lugar=_txt(data.get("lugar"), "el lugar o enlace", 300),
        inicio_at=inicio,
        estado="programada",
        participantes_txt=txt,
        created_by_id=actor.id,
    )
    c.created_by = actor
    c.participantes = [CapacitacionParticipante(user_id=u.id, user=u) for u in gente]
    db.add(c)
    db.flush()
    _ev(
        db,
        c,
        "Programó la capacitación",
        actor,
        f"{c.tema} · {cuando(inicio)} · {txt} ({len(gente)})",
    )
    db.flush()
    return c


def responder(
    db: Session,
    c: Capacitacion,
    *,
    acepta: bool,
    motivo: str | None,
    detalle: str | None,
    actor: User,
) -> CapacitacionParticipante:
    p = _part(c, actor)
    if p is None:
        raise PermissionDeniedError("No estás entre los participantes de esta capacitación.")
    if c.estado != "programada":
        raise ConflictError("Esta capacitación ya no recibe respuestas.")
    if acepta:
        p.respuesta, p.motivo, p.motivo_detalle = "acepta", None, None
    else:
        if motivo not in MOTIVOS:
            raise DomainError("Elige el motivo por el que no participarás.")
        det = _txt(detalle, "el detalle", 300)
        if motivo == "Otro motivo" and not det:
            raise DomainError("Cuenta cuál es el motivo.")
        p.respuesta, p.motivo, p.motivo_detalle = "no", motivo, det
    p.respondida_at = fechas.now()
    _ev(
        db,
        c,
        "Aceptó participar" if acepta else "No participará",
        actor,
        None if acepta else (motivo + (f" · {p.motivo_detalle}" if p.motivo_detalle else "")),
    )
    db.flush()
    return p


def completar(db: Session, c: Capacitacion, asistentes: list[uuid.UUID], *, actor: User):
    """Mark who attended → «realizada»."""
    ensure_organiza(actor)
    if c.estado != "programada":
        raise ConflictError("Esta capacitación ya está cerrada.")
    if c.inicio_at > fechas.now():
        raise DomainError("La asistencia se marca cuando ya empezó la capacitación.")
    ids = set(asistentes)
    otros = ids - {p.user_id for p in c.participantes}
    if otros:
        raise DomainError("Solo se marcan las personas que estaban invitadas.")
    for p in c.participantes:
        p.asistio = p.user_id in ids
    c.estado = "realizada"
    c.completada_at = fechas.now()
    c.completada_por_id = actor.id
    _ev(
        db,
        c,
        "Marcó la asistencia · realizada",
        actor,
        f"{len(ids)} de {len(c.participantes)} participaron",
    )
    db.flush()
    return c


def cancelar(db: Session, c: Capacitacion, motivo: str, *, actor: User) -> Capacitacion:
    ensure_organiza(actor)
    if c.estado != "programada":
        raise ConflictError("Solo se cancela una capacitación programada.")
    c.cancelada_motivo = _txt(motivo, "el motivo", 300, req=True)
    c.estado = "cancelada"
    _ev(db, c, "Canceló la capacitación", actor, c.cancelada_motivo)
    db.flush()
    return c


def registrar(db: Session, data: dict[str, Any], *, actor: User) -> Capacitacion:
    """Z03 «Registrar participación»: a training the person took (sent to Auxiliar y Gerencia)."""
    if not actor.is_active:
        raise PermissionDeniedError("Tu usuario no está activo.")
    inicio = _inicio(data)
    if inicio > fechas.now():
        raise DomainError("Registra capacitaciones que ya hiciste: la fecha no puede ser futura.")
    c = Capacitacion(
        origen="registrada",
        tema=_txt(data.get("tema"), "el tema", 200, req=True),
        area=_area(data.get("area")),
        presenta=_txt(data.get("presenta"), "quién la presentó", 200, req=True),
        inicio_at=inicio,
        estado="realizada",
        completada_at=fechas.now(),
        created_by_id=actor.id,
    )
    c.created_by = actor
    c.participantes = [
        CapacitacionParticipante(
            user_id=actor.id,
            user=actor,
            respuesta="acepta",
            respondida_at=fechas.now(),
            asistio=True,
            aprendio=_txt(data.get("aprendio"), "qué aprendiste", 2000, req=True),
            observaciones=_txt(data.get("observaciones"), "las observaciones", 2000),
        )
    ]
    db.add(c)
    db.flush()
    _ev(db, c, "Registró su participación", actor, f"{c.tema} · {cuando(inicio)}")
    db.flush()
    return c


def aprendizaje(
    db: Session, c: Capacitacion, aprendio: str, observaciones: str | None, *, actor: User
) -> CapacitacionParticipante:
    """After attending a programmed one: «¿Qué aprendiste?»."""
    p = _part(c, actor)
    if p is None or c.estado != "realizada" or not p.asistio:
        raise ConflictError("Escribe lo que aprendiste en una capacitación en la que participaste.")
    p.aprendio = _txt(aprendio, "qué aprendiste", 2000, req=True)
    p.observaciones = _txt(observaciones, "las observaciones", 2000)
    _ev(db, c, "Registró qué aprendió", actor)
    db.flush()
    return p


# ---------------------------------------------------------------- views


def _p(u: User | None) -> dict[str, Any] | None:
    return {"id": u.id, "full_name": u.full_name} if u else None


def _cap(c: Capacitacion, viewer: User) -> dict[str, Any]:
    return {
        "id": c.id,
        "code": c.code,
        "origen": c.origen,
        "origen_txt": origen_txt(c, viewer),
        "tema": c.tema,
        "area": c.area,
        "presenta": c.presenta,
        "lugar": c.lugar,
        "inicio_at": c.inicio_at,
        "cuando": cuando(c.inicio_at),
        "estado": c.estado,
        "cancelada_motivo": c.cancelada_motivo,
        "participantes_txt": c.participantes_txt,
        "creada_por": _p(c.created_by),
    }


def mis(db: Session, user: User) -> dict[str, Any]:
    """Z03: programmed ones to answer, and the person's history."""
    now = fechas.now()
    rows = db.scalars(
        select(CapacitacionParticipante)
        .join(Capacitacion, Capacitacion.id == CapacitacionParticipante.capacitacion_id)
        .where(CapacitacionParticipante.user_id == user.id)
        .order_by(Capacitacion.inicio_at.desc())
    ).unique()
    prog, his = [], []
    for p in rows:
        c = p.capacitacion
        e, cls, m = estado_part(c, p)
        e = PRIMERA_PERSONA.get(e, e)
        item = _cap(c, user) | {
            "respuesta": p.respuesta,
            "motivo": p.motivo,
            "motivo_detalle": p.motivo_detalle,
            "estado_txt": e,
            "estado_cls": cls,
            "motivo_txt": m,
            "asistio": p.asistio,
            "aprendio": p.aprendio,
            "observaciones": p.observaciones,
            "empezo": c.inicio_at <= now,
        }
        (prog if c.estado == "programada" else his).append(item)
    prog.sort(key=lambda x: x["inicio_at"])
    return {
        "persona": {"full_name": user.full_name, "cargo": user.cargo.value},
        "programadas": prog,
        "por_responder": sum(1 for x in prog if x["respuesta"] == "pendiente"),
        "historico": his,
        "areas": AREAS,
        "motivos": MOTIVOS,
        "organiza": organiza(user),
    }


@dataclass
class Rango:
    desde: date
    hasta: date

    @property
    def t1(self) -> datetime:
        return fechas.start_of_day(self.desde)

    @property
    def t2(self) -> datetime:
        return fechas.start_of_day(self.hasta + timedelta(days=1))


def equipo(db: Session, user: User, r: Rango) -> dict[str, Any]:
    """X07: KPIs, programmed trainings with each person's answer, and those the team registered."""
    ensure_organiza(user)
    if r.desde > r.hasta:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    now = fechas.now()
    caps = list(
        db.scalars(
            select(Capacitacion)
            .where(Capacitacion.inicio_at >= r.t1, Capacitacion.inicio_at < r.t2)
            .order_by(Capacitacion.inicio_at.desc())
        ).unique()
    )
    prog = [c for c in caps if c.origen == "programada"]
    reg = [c for c in caps if c.origen == "registrada"]
    lista = []
    no_part = con_motivo = pend = 0
    for c in prog:
        gente = []
        si = pe = no = 0
        for p in sorted(c.participantes, key=lambda x: x.user.full_name):
            e, cls, m = estado_part(c, p)
            if c.estado == "realizada":
                si += 1 if p.asistio else 0
                no += 0 if p.asistio else 1
            elif c.estado == "programada":
                si += p.respuesta == "acepta"
                pe += p.respuesta == "pendiente"
                no += p.respuesta == "no"
            if c.estado != "cancelada" and (
                (c.estado == "realizada" and not p.asistio)
                or (c.estado == "programada" and p.respuesta == "no")
            ):
                no_part += 1
                con_motivo += bool(p.motivo)
            gente.append(
                {
                    "user_id": p.user_id,
                    "full_name": p.user.full_name,
                    "grupo": grupo(p.user),
                    "respuesta": p.respuesta,
                    "estado_txt": e,
                    "estado_cls": cls,
                    "motivo_txt": m,
                    "asistio": p.asistio,
                    "aprendio": p.aprendio,
                }
            )
        pend += pe
        lista.append(
            _cap(c, user)
            | {
                "si": si,
                "pe": pe,
                "no": no,
                "gente": gente,
                "puede_completar": c.estado == "programada" and c.inicio_at <= now,
            }
        )
    registradas = [
        _cap(c, user)
        | {
            "persona": _p(c.created_by),
            "aprendio": c.participantes[0].aprendio if c.participantes else None,
            "observaciones": c.participantes[0].observaciones if c.participantes else None,
        }
        for c in reg
    ]
    return {
        "desde": r.desde,
        "hasta": r.hasta,
        "kpis": {
            "programadas": sum(1 for c in prog if c.estado != "cancelada"),
            "por_responder": pend,
            "registradas": len(reg),
            "no_participaron": no_part,
            "con_motivo": con_motivo,
        },
        "programadas": lista,
        "registradas": registradas,
        "puede_descargar": descarga(user),
        "areas": AREAS,
        "participantes": PARTICIPANTES,
        "personas": [
            {"id": u.id, "full_name": u.full_name, "grupo": grupo(u)} for u in elegibles(db)
        ],
    }


# ---------------------------------------------------------------- other modules


def por_responder(db: Session, user: User, now: datetime) -> list[Capacitacion]:
    """Avisos: programmed trainings this person hasn't answered (still ahead)."""
    return list(
        db.scalars(
            select(Capacitacion)
            .join(CapacitacionParticipante)
            .where(
                CapacitacionParticipante.user_id == user.id,
                CapacitacionParticipante.respuesta == "pendiente",
                Capacitacion.estado == "programada",
                Capacitacion.inicio_at > now,
            )
            .order_by(Capacitacion.inicio_at)
        ).unique()
    )


def por_completar(db: Session, user: User, now: datetime) -> list[Capacitacion]:
    """Avisos: trainings this organizer programmed that already happened, attendance unmarked."""
    return list(
        db.scalars(
            select(Capacitacion).where(
                Capacitacion.created_by_id == user.id,
                Capacitacion.origen == "programada",
                Capacitacion.estado == "programada",
                Capacitacion.inicio_at <= now,
            )
        ).unique()
    )


def registradas_desde(db: Session, desde: datetime, excepto: uuid.UUID) -> list[Capacitacion]:
    return list(
        db.scalars(
            select(Capacitacion)
            .where(
                Capacitacion.origen == "registrada",
                Capacitacion.created_at >= desde,
                Capacitacion.created_by_id != excepto,
            )
            .order_by(Capacitacion.created_at.desc())
        ).unique()
    )


def agenda_items(
    db: Session, target: User, d1: date, d2: date, *, propia: bool
) -> list[dict[str, Any]]:
    """Programmed trainings in the person's agenda (not the ones they declined)."""
    rows = db.scalars(
        select(CapacitacionParticipante)
        .join(Capacitacion, Capacitacion.id == CapacitacionParticipante.capacitacion_id)
        .where(
            CapacitacionParticipante.user_id == target.id,
            CapacitacionParticipante.respuesta != "no",
            Capacitacion.origen == "programada",
            Capacitacion.estado != "cancelada",
            Capacitacion.inicio_at >= fechas.start_of_day(d1),
            Capacitacion.inicio_at < fechas.start_of_day(d2 + timedelta(days=1)),
        )
    ).unique()
    out = []
    for p in rows:
        c = p.capacitacion
        local = c.inicio_at.astimezone(fechas.BOGOTA)
        e, cls, _m = estado_part(c, p)
        out.append(
            {
                "id": f"cap:{c.id}",
                "k": "sys",
                "tipo": "cap",
                "fecha": local.date(),
                "hora": local.time().replace(second=0, microsecond=0),
                "titulo": f"Capacitación · {c.tema}",
                "sub": " · ".join(x for x in (c.area, f"presenta {c.presenta}", c.lugar) if x),
                "estado_txt": e,
                "estado_cls": cls,
                "link": "/capacitaciones" if propia else None,
            }
        )
    return out
