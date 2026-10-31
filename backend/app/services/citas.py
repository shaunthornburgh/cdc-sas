"""Citas: who can receive them, status flow, reassignment and rescheduling.

Prototype C03 and decision G-014:
- A cita goes to an asesor «Pendiente de aceptación»; the asesor accepts or rejects it.
- It never stays without someone responsible: rejected citas, citas without an asesor and
  pending citas starting within 1 hour «require action» from Atención / Pre-ventas, who
  reassign, reschedule or cancel them. Only Atención / Pre-ventas (and managers) reschedule.
- Each cita type needs an asesor with the matching commercial activity.

The asesor-side screen (accept / reject from their own app) comes with the Asesor module;
until then Atención or Coordinación record the asesor's answer here.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cita, Lead, LeadEvento, User
from app.models.enums import (
    CITA_ACTIVA,
    ActividadComercial,
    EstadoCita,
    EtapaLead,
    TipoCita,
    TipoEventoLead,
)
from app.services import fechas
from app.services import leads as lead_service
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError

A = ActividadComercial
# Activities that let an asesor receive each type (any of them). Empty = any asesor.
REQUISITOS: dict[TipoCita, frozenset[ActividadComercial]] = {
    TipoCita.VISITA_ARRIENDO: frozenset({A.ARRIENDOS}),
    TipoCita.VISITA_VENTA: frozenset({A.VENTAS}),
    TipoCita.CAPTACION: frozenset({A.CAPTACION}),
    TipoCita.REUNION_ASESORIA: frozenset({A.VENTAS, A.ARRIENDOS}),
    TipoCita.VISITA_CONTROL: frozenset(),
    TipoCita.INVENTARIO: frozenset(),
}
TIPO_LABELS = {
    TipoCita.VISITA_ARRIENDO: "Visita a inmueble · arriendo",
    TipoCita.VISITA_VENTA: "Visita a inmueble · venta",
    TipoCita.CAPTACION: "Captación",
    TipoCita.VISITA_CONTROL: "Visita de control al inmueble",
    TipoCita.INVENTARIO: "Inventario",
    TipoCita.REUNION_ASESORIA: "Reunión de asesoría",
}
ESTADO_LABELS = {
    EstadoCita.PENDIENTE: "pendiente de aceptación",
    EstadoCita.ACEPTADA: "aceptada",
    EstadoCita.RECHAZADA: "rechazada",
    EstadoCita.REALIZADA: "realizada",
    EstadoCita.CANCELADA: "cancelada",
}
TRANSICIONES: dict[EstadoCita, frozenset[EstadoCita]] = {
    EstadoCita.PENDIENTE: frozenset(
        {EstadoCita.ACEPTADA, EstadoCita.RECHAZADA, EstadoCita.CANCELADA}
    ),
    EstadoCita.ACEPTADA: frozenset({EstadoCita.REALIZADA, EstadoCita.CANCELADA}),
    EstadoCita.RECHAZADA: frozenset({EstadoCita.CANCELADA}),  # or reassign / reschedule
    EstadoCita.REALIZADA: frozenset(),
    EstadoCita.CANCELADA: frozenset(),
}
DURACION = timedelta(hours=1)  # a slot; two citas of one asesor can't overlap
ALERTA_ANTES = timedelta(hours=1)
_ACT_LABELS = {A.CAPTACION: "Captación", A.VENTAS: "Ventas", A.ARRIENDOS: "Arriendos"}


# ---------------------------------------------------------------- asesores


def es_asesor(user: User) -> bool:
    """People who go to citas: active, with commercial activities, no independent function."""
    return user.is_active and user.funcion is None and bool(user.actividades)


def cumple_requisito(user: User, tipo: TipoCita) -> bool:
    req = REQUISITOS[tipo]
    return es_asesor(user) and (not req or bool(req & set(user.actividades)))


def requisito_texto(tipo: TipoCita) -> str | None:
    req = REQUISITOS[tipo]
    return " o ".join(_ACT_LABELS[a] for a in A if a in req) or None


def cita_en_horario(
    db: Session, asesor_id: uuid.UUID, at: datetime, exclude_id: uuid.UUID | None = None
) -> Cita | None:
    stmt = select(Cita).where(
        Cita.asesor_id == asesor_id,
        Cita.estado.in_((EstadoCita.PENDIENTE, EstadoCita.ACEPTADA)),
        Cita.scheduled_at > at - DURACION,
        Cita.scheduled_at < at + DURACION,
    )
    if exclude_id:
        stmt = stmt.where(Cita.id != exclude_id)
    return db.scalars(stmt).unique().first()


@dataclass(frozen=True)
class AsesorDisponible:
    user: User
    elegible: bool
    ocupado_con: Cita | None


def asesores(
    db: Session, tipo: TipoCita, at: datetime | None, exclude_id: uuid.UUID | None = None
) -> list[AsesorDisponible]:
    people = [u for u in db.scalars(select(User).order_by(User.full_name)).unique() if es_asesor(u)]
    out = [
        AsesorDisponible(
            user=u,
            elegible=cumple_requisito(u, tipo),
            ocupado_con=cita_en_horario(db, u.id, at, exclude_id) if at else None,
        )
        for u in people
    ]
    # Eligible and free first, as in the prototype's picker.
    return sorted(out, key=lambda a: (not a.elegible, a.ocupado_con is not None, a.user.full_name))


def _check_asesor(
    db: Session, asesor_id: uuid.UUID, tipo: TipoCita, at: datetime, exclude_id=None
) -> User:
    asesor = db.get(User, asesor_id)
    if asesor is None or not es_asesor(asesor):
        raise DomainError("Elige un asesor activo con actividades comerciales.")
    if not cumple_requisito(asesor, tipo):
        raise DomainError(
            f"{asesor.full_name} no puede recibir «{TIPO_LABELS[tipo]}»: "
            f"necesita {requisito_texto(tipo)} activo."
        )
    if other := cita_en_horario(db, asesor.id, at, exclude_id):
        raise ConflictError(
            f"{asesor.full_name} ya tiene la cita {other.code} "
            f"a las {fechas.fmt(other.scheduled_at)}."
        )
    return asesor


def _future(at: datetime) -> None:
    if at < fechas.now():
        raise DomainError("La fecha y hora de la cita ya pasaron.")


# ---------------------------------------------------------------- queries


def requiere_accion(cita: Cita, now: datetime | None = None) -> bool:
    now = now or fechas.now()
    if cita.estado not in CITA_ACTIVA:
        return False
    return (
        cita.estado == EstadoCita.RECHAZADA
        or cita.asesor_id is None
        or (cita.estado == EstadoCita.PENDIENTE and cita.scheduled_at - now <= ALERTA_ANTES)
    )


def bucket(cita: Cita, now: datetime | None = None) -> str:
    """Tabs of C03."""
    if requiere_accion(cita, now):
        return "accion"
    return {
        EstadoCita.PENDIENTE: "pendientes",
        EstadoCita.ACEPTADA: "aceptadas",
        EstadoCita.REALIZADA: "realizadas",
        EstadoCita.CANCELADA: "canceladas",
    }[cita.estado]


BUCKETS = ("accion", "pendientes", "aceptadas", "realizadas", "canceladas")


@dataclass(frozen=True)
class CitaFilters:
    bucket: str | None = None
    lead_id: uuid.UUID | None = None
    asesor_id: uuid.UUID | None = None
    desde: date | None = None  # scheduled_at, Bogotá days, inclusive
    hasta: date | None = None


def list_citas(db: Session, f: CitaFilters) -> tuple[list[Cita], dict[str, int]]:
    """All citas matching the filters (except bucket), plus per-bucket counts."""
    stmt = select(Cita).order_by(Cita.scheduled_at)
    if f.lead_id:
        stmt = stmt.where(Cita.lead_id == f.lead_id)
    if f.asesor_id:
        stmt = stmt.where(Cita.asesor_id == f.asesor_id)
    if f.desde:
        stmt = stmt.where(Cita.scheduled_at >= fechas.start_of_day(f.desde))
    if f.hasta:
        stmt = stmt.where(Cita.scheduled_at < fechas.start_of_day(f.hasta + timedelta(days=1)))
    rows = list(db.scalars(stmt).unique())
    now = fechas.now()
    counts = dict.fromkeys(BUCKETS, 0)
    for c in rows:
        counts[bucket(c, now)] += 1
    if f.bucket:
        if f.bucket not in BUCKETS:
            raise DomainError("Pestaña no válida.")
        rows = [c for c in rows if bucket(c, now) == f.bucket]
        if f.bucket in ("realizadas", "canceladas"):
            rows.reverse()  # most recent first
    return rows, counts


def historial(db: Session, citas: list[Cita]) -> dict[uuid.UUID, list[LeadEvento]]:
    ids = [c.id for c in citas]
    out: dict[uuid.UUID, list[LeadEvento]] = {i: [] for i in ids}
    if ids:
        stmt = select(LeadEvento).where(LeadEvento.cita_id.in_(ids)).order_by(LeadEvento.created_at)
        for ev in db.scalars(stmt).unique():
            out[ev.cita_id].append(ev)
    return out


def get_cita(db: Session, cita_id: uuid.UUID) -> Cita:
    cita = db.get(Cita, cita_id)
    if cita is None:
        raise NotFoundError("Cita no encontrada.")
    return cita


# ---------------------------------------------------------------- commands


def _event(db: Session, cita: Cita, titulo: str, actor: User, detalle: str | None = None):
    return lead_service._event(
        db, cita.lead, TipoEventoLead.CITA, titulo, actor, detalle, cita=cita
    )


def _lead_after_cita_closed(lead: Lead) -> None:
    if lead.etapa == EtapaLead.CITA_PROGRAMADA and lead.cita_activa is None:
        lead.etapa = EtapaLead.EN_GESTION


def create_cita(
    db: Session,
    lead: Lead,
    *,
    tipo: TipoCita,
    scheduled_at: datetime,
    asesor_id: uuid.UUID,
    inmueble: str | None,
    notas: str | None,
    actor: User,
) -> Cita:
    lead_service.ensure_can_edit(actor, lead)
    lead_service.ensure_open(lead)
    _future(scheduled_at)
    if activa := lead.cita_activa:
        raise ConflictError(
            f"El lead ya tiene la cita {activa.code} activa. Reprográmala o cancélala primero."
        )
    asesor = _check_asesor(db, asesor_id, tipo, scheduled_at)
    cita = Cita(
        lead=lead,
        tipo=tipo,
        scheduled_at=scheduled_at,
        asesor_id=asesor.id,
        asesor=asesor,
        inmueble=(inmueble or "").strip() or None,
        notas=(notas or "").strip() or None,
        created_by_id=actor.id,
    )
    db.add(cita)
    db.flush()
    lead.etapa = EtapaLead.CITA_PROGRAMADA
    _event(
        db,
        cita,
        f"Cita {cita.code} programada · {fechas.fmt(scheduled_at)}",
        actor,
        f"{TIPO_LABELS[tipo]} con {asesor.full_name}. Pendiente de aceptación."
        + (f" Inmueble: {cita.inmueble}." if cita.inmueble else ""),
    )
    db.flush()
    return cita


def set_estado(
    db: Session, cita: Cita, estado: EstadoCita, *, motivo: str | None, actor: User
) -> Cita:
    if estado not in TRANSICIONES[cita.estado]:
        raise DomainError(
            f"Una cita {ESTADO_LABELS[cita.estado]} no puede pasar a {ESTADO_LABELS[estado]}."
        )
    motivo = (motivo or "").strip() or None
    if estado in (EstadoCita.RECHAZADA, EstadoCita.CANCELADA) and not motivo:
        raise DomainError("Escribe el motivo.")
    if estado == EstadoCita.REALIZADA and cita.scheduled_at > fechas.now():
        raise DomainError("La cita aún no ha ocurrido.")

    quien = cita.asesor_name or "el asesor"
    titulos = {
        EstadoCita.ACEPTADA: f"Cita {cita.code} aceptada por {quien}",
        EstadoCita.RECHAZADA: f"Cita {cita.code} rechazada por {quien}",
        EstadoCita.REALIZADA: f"Cita {cita.code} realizada",
        EstadoCita.CANCELADA: f"Cita {cita.code} cancelada",
    }
    cita.estado = estado
    if motivo:
        cita.motivo = motivo
    detalle = motivo
    if estado == EstadoCita.RECHAZADA:
        detalle = f"{motivo} Asigna otro asesor, reprográmala o cancélala."
    _event(db, cita, titulos[estado], actor, detalle)
    if estado == EstadoCita.CANCELADA:
        _lead_after_cita_closed(cita.lead)
    db.flush()
    return cita


def reasignar(db: Session, cita: Cita, asesor_id: uuid.UUID, *, actor: User) -> Cita:
    if cita.estado not in CITA_ACTIVA:
        raise DomainError(f"La cita está {ESTADO_LABELS[cita.estado]}; no se puede reasignar.")
    if asesor_id == cita.asesor_id and cita.estado != EstadoCita.RECHAZADA:
        return cita
    asesor = _check_asesor(db, asesor_id, cita.tipo, cita.scheduled_at, exclude_id=cita.id)
    cita.asesor_id = asesor.id
    cita.asesor = asesor
    cita.estado = EstadoCita.PENDIENTE
    _event(
        db,
        cita,
        f"Cita {cita.code} enviada a {asesor.full_name}",
        actor,
        "Pendiente de aceptación.",
    )
    db.flush()
    return cita


def reprogramar(
    db: Session, cita: Cita, scheduled_at: datetime, *, motivo: str, actor: User
) -> Cita:
    if cita.estado not in CITA_ACTIVA:
        raise DomainError(f"La cita está {ESTADO_LABELS[cita.estado]}; no se puede reprogramar.")
    if not (motivo or "").strip():
        raise DomainError("Escribe el motivo de la reprogramación.")
    _future(scheduled_at)
    if cita.asesor_id and (
        other := cita_en_horario(db, cita.asesor_id, scheduled_at, exclude_id=cita.id)
    ):
        raise ConflictError(
            f"{cita.asesor_name} ya tiene la cita {other.code} "
            f"a las {fechas.fmt(other.scheduled_at)}."
        )
    antes = cita.scheduled_at
    cita.scheduled_at = scheduled_at
    # The asesor has to accept the new time again (a rejected cita stays rejected).
    if cita.estado == EstadoCita.ACEPTADA:
        cita.estado = EstadoCita.PENDIENTE
    _event(
        db,
        cita,
        f"Cita {cita.code} reprogramada · {fechas.fmt(antes)} → {fechas.fmt(scheduled_at)}",
        actor,
        motivo.strip(),
    )
    db.flush()
    return cita


def update_detalles(
    db: Session, cita: Cita, *, inmueble: str | None, notas: str | None, actor: User
) -> Cita:
    cita.inmueble = (inmueble or "").strip() or None
    cita.notas = (notas or "").strip() or None
    db.flush()
    return cita


# ---------------------------------------------------------------- asesor side (M03)
# The asesor answers their own citas: accept, reject (reason + note), take a cita another
# asesor rejected (first one wins), and close it after the visit with the result.

MOTIVOS_RECHAZO_ASESOR = (
    "Choque con otra cita",
    "La zona no me corresponde",
    "Sin disponibilidad en ese horario",
    "Otro",
)


def _ensure_mine(cita: Cita, asesor: User) -> None:
    if cita.asesor_id != asesor.id:
        raise PermissionDeniedError("Esta cita no está asignada a ti.")


def aceptar_por_asesor(db: Session, cita: Cita, *, asesor: User) -> Cita:
    _ensure_mine(cita, asesor)
    if cita.estado != EstadoCita.PENDIENTE:
        raise DomainError(f"La cita está {ESTADO_LABELS[cita.estado]}; no hay nada que aceptar.")
    _future(cita.scheduled_at)
    return set_estado(db, cita, EstadoCita.ACEPTADA, motivo=None, actor=asesor)


def rechazar_por_asesor(
    db: Session, cita: Cita, *, motivo: str, observacion: str, asesor: User
) -> Cita:
    _ensure_mine(cita, asesor)
    if cita.estado != EstadoCita.PENDIENTE:
        raise DomainError(f"La cita está {ESTADO_LABELS[cita.estado]}; ya no se puede rechazar.")
    if motivo not in MOTIVOS_RECHAZO_ASESOR:
        raise DomainError("Elige un motivo de la lista.")
    if not (observacion or "").strip():
        raise DomainError("Escribe la observación para rechazar.")
    return set_estado(
        db, cita, EstadoCita.RECHAZADA, motivo=f"{motivo} · {observacion.strip()}", actor=asesor
    )


def disponible_para(cita: Cita, asesor: User, db: Session, now: datetime | None = None) -> bool:
    """A rejected (or unassigned) future cita this asesor could take right now."""
    now = now or fechas.now()
    return (
        cita.estado in (EstadoCita.RECHAZADA, EstadoCita.PENDIENTE)
        and (cita.estado == EstadoCita.RECHAZADA or cita.asesor_id is None)
        and cita.asesor_id != asesor.id
        and cita.scheduled_at > now
        and cumple_requisito(asesor, cita.tipo)
        and cita_en_horario(db, asesor.id, cita.scheduled_at, exclude_id=cita.id) is None
    )


def tomar(db: Session, cita: Cita, *, asesor: User) -> Cita:
    """«Tomar cita»: the first asesor who takes a rejected cita becomes responsible."""
    db.execute(select(Cita.id).where(Cita.id == cita.id).with_for_update())
    db.refresh(cita)
    if cita.estado not in (EstadoCita.RECHAZADA, EstadoCita.PENDIENTE) or (
        cita.estado == EstadoCita.PENDIENTE and cita.asesor_id is not None
    ):
        raise ConflictError("Otro asesor ya tomó esta cita.")
    if cita.asesor_id == asesor.id:
        raise DomainError("Tú rechazaste esta cita; la toma otro asesor.")
    _future(cita.scheduled_at)
    _check_asesor(db, asesor.id, cita.tipo, cita.scheduled_at, exclude_id=cita.id)
    antes = cita.asesor_name
    cita.asesor_id = asesor.id
    cita.asesor = asesor
    cita.estado = EstadoCita.ACEPTADA
    _event(
        db,
        cita,
        f"Cita {cita.code} tomada por {asesor.full_name}",
        asesor,
        f"La había rechazado {antes}. Queda aceptada." if antes else "Queda aceptada.",
    )
    db.flush()
    return cita


def cerrar_por_asesor(db: Session, cita: Cita, *, resultado: str, asesor: User) -> Cita:
    _ensure_mine(cita, asesor)
    if cita.estado != EstadoCita.ACEPTADA:
        raise DomainError("Solo se cierra una cita aceptada.")
    if not (resultado or "").strip():
        raise DomainError("Escribe qué pasó en la visita.")
    return set_estado(db, cita, EstadoCita.REALIZADA, motivo=resultado, actor=asesor)
