"""Leads: visibility, «Seguir lead», actions, follow-ups and stage rules.

Prototypes C01 / C02 and decisions G-013, G-044 and G-045:
- Leads arrive on their own; nobody is assigned until someone presses «Seguir lead».
- After that only the owner works the lead, unless Coordinación or Gerencia reassign it.
- Atención / Pre-ventas see unassigned leads and their own. Managers see everything.
- Ganado / Perdido close the lead (archived). Perdido always has a reason, and whether it
  costs performance points follows the call rule below.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.models import Cita, Lead, LeadEvento, Seguimiento, User
from app.models.enums import (
    ETAPAS_CERRADAS,
    AccionSeguimiento,
    EstadoCita,
    EtapaLead,
    FuenteLead,
    MedioContacto,
    MotivoPerdida,
    ResultadoLlamada,
    TipoEventoLead,
)
from app.services import configuracion, fechas
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError
from app.services.policies import can_use_leads, is_manager

# «No contesta» doesn't cost points after N calls on N consecutive days (G-045). Gerencia sets both
# in Configuración («Leads ganados y perdidos»); these are the defaults.
MIN_LLAMADAS_SIN_DESCUENTO = 3
MIN_DIAS_SEGUIDOS_SIN_DESCUENTO = 3

FUENTE_LABELS = {
    FuenteLead.CIENCUADRAS: "Ciencuadras",
    FuenteLead.ESPACIO_URBANO: "Espacio Urbano",
    FuenteLead.PROPPI: "Proppi",
    FuenteLead.FINCA_RAIZ: "Finca Raíz",
    FuenteLead.METROCUADRADO: "Metrocuadrado",
    FuenteLead.FACEBOOK: "Facebook",
    FuenteLead.INSTAGRAM: "Instagram",
    FuenteLead.TIKTOK: "TikTok",
    FuenteLead.OTRO: "Otra fuente",
}
ETAPA_LABELS = {
    EtapaLead.NUEVO: "Nuevo",
    EtapaLead.EN_GESTION: "En gestión",
    EtapaLead.SEGUIMIENTO: "Seguimiento",
    EtapaLead.CITA_PROGRAMADA: "Cita programada",
    EtapaLead.GANADO: "Ganado",
    EtapaLead.PERDIDO: "Perdido",
}
MOTIVO_LABELS = {
    MotivoPerdida.NO_CONTESTA: "No contesta",
    MotivoPerdida.NUMERO_EQUIVOCADO: "Número equivocado",
    MotivoPerdida.NO_INTERESADO: "No interesado",
    MotivoPerdida.COMPRO_CON_OTRO: "Compró o arrendó con otro",
    MotivoPerdida.PRESUPUESTO: "Presupuesto no alcanza",
}
ACCION_LABELS = {
    AccionSeguimiento.LLAMAR: "Llamar",
    AccionSeguimiento.ENVIAR_OPCIONES: "Enviar opciones",
    AccionSeguimiento.ENVIAR_INFORMACION: "Enviar información",
    AccionSeguimiento.CONFIRMAR_CITA: "Confirmar cita",
    AccionSeguimiento.SEGUIMIENTO_PROPUESTA: "Hacer seguimiento a una propuesta",
    AccionSeguimiento.VOLVER_A_CONTACTAR: "Volver a contactar",
}
MEDIO_LABELS = {
    MedioContacto.WHATSAPP: "WhatsApp",
    MedioContacto.CORREO: "Correo",
    MedioContacto.SMS: "Mensaje de texto",
}
_LLAMADA_TITULOS = {
    ResultadoLlamada.CONTESTO: "Llamada · contestó",
    ResultadoLlamada.NO_CONTESTO: "Llamada · no contestó",
    ResultadoLlamada.NUMERO_EQUIVOCADO: "Llamada · número equivocado",
}
EDITABLE_FIELDS = (
    "full_name",
    "phone",
    "email",
    "fuente",
    "fuente_detalle",
    "negocio",
    "busca",
    "presupuesto",
    "zona",
    "para_cuando",
    "notas",
)


# ---------------------------------------------------------------- access


def _visible(stmt: Select, user: User) -> Select:
    if is_manager(user):
        return stmt
    return stmt.where(or_(Lead.assigned_to_id == user.id, Lead.assigned_to_id.is_(None)))


def get_lead(db: Session, user: User, lead_id: uuid.UUID) -> Lead:
    lead = db.scalar(_visible(select(Lead).where(Lead.id == lead_id), user))
    if lead is None:
        raise NotFoundError("Lead no encontrado.")
    return lead


def can_edit(user: User, lead: Lead) -> bool:
    return is_manager(user) or lead.assigned_to_id == user.id


def ensure_can_edit(user: User, lead: Lead) -> None:
    if can_edit(user, lead):
        return
    if lead.assigned_to_id is None:
        raise PermissionDeniedError("Primero toma el lead con «Seguir lead».")
    raise PermissionDeniedError(
        f"Este lead lo sigue {lead.assigned_to.full_name if lead.assigned_to else 'otra persona'}."
    )


def ensure_open(lead: Lead) -> None:
    if lead.is_closed:
        raise DomainError(
            f"El lead está cerrado ({ETAPA_LABELS[lead.etapa]}). "
            "Solo Coordinación o Gerencia pueden reabrirlo."
        )


# ---------------------------------------------------------------- queries


@dataclass(frozen=True)
class LeadFilters:
    etapas: tuple[EtapaLead, ...] = ()
    abiertos: bool | None = None  # True: not Ganado/Perdido · False: only archived
    assigned: str | None = None  # "me" | "none" | user uuid
    fuente: FuenteLead | None = None
    desde: date | None = None  # created_at, Bogotá days, inclusive
    hasta: date | None = None
    q: str | None = None
    limit: int = 200


def list_leads(db: Session, user: User, f: LeadFilters) -> list[Lead]:
    stmt = _visible(select(Lead), user)
    if f.etapas:
        stmt = stmt.where(Lead.etapa.in_(f.etapas))
    if f.abiertos is True:
        stmt = stmt.where(Lead.etapa.not_in(ETAPAS_CERRADAS))
    elif f.abiertos is False:
        stmt = stmt.where(Lead.etapa.in_(ETAPAS_CERRADAS))
    if f.assigned == "me":
        stmt = stmt.where(Lead.assigned_to_id == user.id)
    elif f.assigned == "none":
        stmt = stmt.where(Lead.assigned_to_id.is_(None))
    elif f.assigned:
        try:
            stmt = stmt.where(Lead.assigned_to_id == uuid.UUID(f.assigned))
        except ValueError:
            raise DomainError("Responsable no válido.") from None
    if f.fuente:
        stmt = stmt.where(Lead.fuente == f.fuente)
    if f.desde:
        stmt = stmt.where(Lead.created_at >= fechas.start_of_day(f.desde))
    if f.hasta:
        stmt = stmt.where(Lead.created_at < fechas.start_of_day(f.hasta + timedelta(days=1)))
    if f.q and (term := f.q.strip()):
        like = f"%{term}%"
        cond = Lead.full_name.ilike(like) | Lead.phone.ilike(like) | Lead.email.ilike(like)
        digits = term.upper().removeprefix("LD-").lstrip("0")
        if digits.isdigit():
            cond = cond | (Lead.numero == int(digits))
        stmt = stmt.where(cond)
    stmt = stmt.order_by(Lead.created_at.desc()).limit(f.limit)
    return list(db.scalars(stmt).unique())


@dataclass(frozen=True)
class LeadExtras:
    llamadas: int = 0
    ultimo_evento: LeadEvento | None = None


def extras_for(db: Session, leads: list[Lead]) -> dict[uuid.UUID, LeadExtras]:
    """Call counts and last history line for a page of leads (two queries)."""
    ids = [lead.id for lead in leads]
    if not ids:
        return {}
    calls = dict(
        db.execute(
            select(LeadEvento.lead_id, func.count())
            .where(LeadEvento.lead_id.in_(ids), LeadEvento.tipo == TipoEventoLead.LLAMADA)
            .group_by(LeadEvento.lead_id)
        ).all()
    )
    last = {
        ev.lead_id: ev
        for ev in db.scalars(
            select(LeadEvento)
            .where(LeadEvento.lead_id.in_(ids))
            .ext(distinct_on(LeadEvento.lead_id))
            .order_by(LeadEvento.lead_id, LeadEvento.created_at.desc())
        ).unique()
    }
    return {i: LeadExtras(llamadas=calls.get(i, 0), ultimo_evento=last.get(i)) for i in ids}


def eventos(db: Session, lead: Lead) -> list[LeadEvento]:
    stmt = select(LeadEvento).where(LeadEvento.lead_id == lead.id).order_by(LeadEvento.created_at)
    return list(db.scalars(stmt).unique())


@dataclass(frozen=True)
class CallStats:
    llamadas: int
    dias_seguidos: int  # longest run of consecutive (Bogotá) days with at least one call


def call_stats(db: Session, lead: Lead) -> CallStats:
    times = db.scalars(
        select(LeadEvento.created_at).where(
            LeadEvento.lead_id == lead.id, LeadEvento.tipo == TipoEventoLead.LLAMADA
        )
    ).all()
    days = sorted({fechas.local_date(t) for t in times})
    best = run = 0
    for i, d in enumerate(days):
        run = run + 1 if i and (d - days[i - 1]).days == 1 else 1
        best = max(best, run)
    return CallStats(llamadas=len(times), dias_seguidos=best)


def perdida_descuenta(
    motivo: MotivoPerdida,
    stats: CallStats,
    llamadas: int = MIN_LLAMADAS_SIN_DESCUENTO,
    dias: int = MIN_DIAS_SEGUIDOS_SIN_DESCUENTO,
) -> bool:
    """G-045: «Número equivocado» never costs points.

    «No contesta» doesn't either after `llamadas` calls on `dias` consecutive days.
    """
    if motivo == MotivoPerdida.NUMERO_EQUIVOCADO:
        return False
    if motivo == MotivoPerdida.NO_CONTESTA:
        return not (stats.llamadas >= llamadas and stats.dias_seguidos >= dias)
    return True


# ---------------------------------------------------------------- commands


def _event(
    db: Session,
    lead: Lead,
    tipo: TipoEventoLead,
    titulo: str,
    actor: User | None,
    detalle: str | None = None,
    datos: dict[str, Any] | None = None,
    cita: Cita | None = None,
) -> LeadEvento:
    ev = LeadEvento(
        lead_id=lead.id,
        tipo=tipo,
        titulo=titulo,
        detalle=detalle,
        datos=datos or {},
        cita_id=cita.id if cita else None,
        created_by_id=actor.id if actor else None,
    )
    db.add(ev)
    return ev


def _after_action(lead: Lead) -> None:
    """Automatic stage moves after work is logged on the lead."""
    if lead.etapa == EtapaLead.NUEVO:
        lead.etapa = EtapaLead.EN_GESTION
    elif lead.etapa == EtapaLead.SEGUIMIENTO and lead.proximo_seguimiento is None:
        lead.etapa = EtapaLead.EN_GESTION


def create_lead(
    db: Session, data: Mapping[str, Any], *, actor: User | None, seguir: bool = False
) -> Lead:
    lead = Lead(**{k: data[k] for k in EDITABLE_FIELDS if k in data})
    lead.created_by_id = actor.id if actor else None
    db.add(lead)
    db.flush()
    fuente = FUENTE_LABELS[lead.fuente]
    if actor is None:
        _event(
            db, lead, TipoEventoLead.RECIBIDO, "Lead recibido", None, f"Llegó solo desde {fuente}."
        )
    else:
        _event(
            db,
            lead,
            TipoEventoLead.RECIBIDO,
            "Lead registrado",
            actor,
            f"Registrado por {actor.full_name} · llegó desde {fuente}.",
        )
    if seguir and actor is not None:
        follow_lead(db, lead, actor)
    db.flush()
    return lead


def update_lead(db: Session, lead: Lead, changes: Mapping[str, Any], *, actor: User) -> Lead:
    data = {k: v for k, v in changes.items() if k in EDITABLE_FIELDS}
    if "assigned_to_id" in changes:
        _reassign(db, lead, changes["assigned_to_id"], actor)
    if not data:
        db.flush()
        return lead

    ensure_can_edit(actor, lead)
    changed = [k for k, v in data.items() if getattr(lead, k) != v]
    for k in changed:
        setattr(lead, k, data[k])
    if changed:
        _event(
            db,
            lead,
            TipoEventoLead.DATOS,
            "Datos del cliente actualizados",
            actor,
            datos={"campos": changed},
        )
    db.flush()
    return lead


def _reassign(db: Session, lead: Lead, user_id: uuid.UUID | None, actor: User) -> None:
    if not is_manager(actor):
        raise PermissionDeniedError("Solo Coordinación o Gerencia pueden reasignar un lead.")
    if user_id == lead.assigned_to_id:
        return
    if user_id is None:
        lead.assigned_to_id = None
        lead.assigned_at = None
        _event(
            db,
            lead,
            TipoEventoLead.ASIGNACION,
            "Responsable quitado",
            actor,
            f"{actor.full_name} dejó el lead sin responsable.",
        )
        return
    new = db.get(User, user_id)
    if new is None or not new.is_active or not can_use_leads(new):
        raise DomainError(
            "El responsable debe ser una persona activa de Atención al Cliente, "
            "Pre-ventas, Coordinación o Gerencia."
        )
    before = lead.assigned_to.full_name if lead.assigned_to else "sin responsable"
    lead.assigned_to_id = new.id
    lead.assigned_to = new
    lead.assigned_at = fechas.now()
    _event(
        db,
        lead,
        TipoEventoLead.ASIGNACION,
        f"Reasignado a {new.full_name}",
        actor,
        f"Antes: {before}. Reasignado por {actor.full_name}.",
    )


def delete_lead(db: Session, lead: Lead, *, actor: User) -> None:
    if not is_manager(actor):
        raise PermissionDeniedError("Solo Coordinación o Gerencia pueden eliminar un lead.")
    db.delete(lead)
    db.flush()


def follow_lead(db: Session, lead: Lead, actor: User) -> Lead:
    """«Seguir lead»: the first person to press it becomes the only owner."""
    # Two people clicking at once: lock the row so only one of them wins.
    db.execute(select(Lead.id).where(Lead.id == lead.id).with_for_update())
    db.refresh(lead)
    ensure_open(lead)
    if lead.assigned_to_id == actor.id:
        return lead
    if lead.assigned_to_id is not None:
        owner = lead.assigned_to.full_name if lead.assigned_to else "otra persona"
        desde = f" desde {fechas.fmt(lead.assigned_at)}" if lead.assigned_at else ""
        raise ConflictError(
            f"Lo sigue {owner}{desde}. Solo Coordinación o Gerencia pueden reasignarlo."
        )
    lead.assigned_to_id = actor.id
    lead.assigned_to = actor
    lead.assigned_at = fechas.now()
    _event(
        db,
        lead,
        TipoEventoLead.SEGUIR,
        "Seguir lead",
        actor,
        f"{actor.full_name} tomó el lead y quedó como responsable.",
    )
    db.flush()
    return lead


def registrar_llamada(
    db: Session,
    lead: Lead,
    *,
    resultado: ResultadoLlamada,
    resumen: str | None,
    duracion_min: int | None,
    actor: User,
) -> LeadEvento:
    ensure_can_edit(actor, lead)
    ensure_open(lead)
    if resultado == ResultadoLlamada.CONTESTO and not (resumen or "").strip():
        raise DomainError("Escribe el resumen de la llamada: qué se habló.")
    intento = call_stats(db, lead).llamadas + 1
    titulo = _LLAMADA_TITULOS[resultado]
    if resultado == ResultadoLlamada.CONTESTO and duracion_min:
        titulo += f" · {duracion_min} min"
    ev = _event(
        db,
        lead,
        TipoEventoLead.LLAMADA,
        titulo,
        actor,
        (resumen or "").strip() or f"Intento {intento}.",
        {"resultado": resultado.value, "duracion_min": duracion_min, "intento": intento},
    )
    _after_action(lead)
    db.flush()
    return ev


def registrar_mensaje(
    db: Session,
    lead: Lead,
    *,
    tipo: TipoEventoLead,
    medio: MedioContacto,
    texto: str,
    actor: User,
    inmueble_ids: list[uuid.UUID] | None = None,
) -> LeadEvento:
    """A message sent to the client (MENSAJE) or options/information sent (OPCIONES).

    Options can be properties picked from the catalog: they're listed in the lead's history and
    each property records that it was sent to this client.
    """
    from app.services import inmuebles as inm_service  # noqa: PLC0415 (avoids an import cycle)

    ensure_can_edit(actor, lead)
    ensure_open(lead)
    inms = inm_service.para_enviar(db, inmueble_ids) if inmueble_ids else []
    texto = texto.strip()
    if not texto and not inms:
        raise DomainError(
            "Escribe el mensaje que enviaste."
            if tipo == TipoEventoLead.MENSAJE
            else "Elige los inmuebles o escribe qué información enviaste."
        )
    base = "Mensaje enviado" if tipo == TipoEventoLead.MENSAJE else "Opciones enviadas"
    if inms:
        lista = " · ".join(f"{i.codigo} {inm_service.titulo(i)}" for i in inms)
        texto = f"{lista}." + (f" «{texto}»" if texto else "")
    datos: dict[str, Any] = {"medio": medio.value}
    if inms:
        datos["inmuebles"] = [i.codigo for i in inms]
    ev = _event(
        db,
        lead,
        tipo,
        f"{base} · {MEDIO_LABELS[medio]}" + (f" · {len(inms)} inmuebles" if len(inms) > 1 else ""),
        actor,
        texto,
        datos,
    )
    if inms:
        inm_service.registrar_envio(db, inms, lead, MEDIO_LABELS[medio], actor)
    _after_action(lead)
    db.flush()
    return ev


def registrar_observacion(db: Session, lead: Lead, *, texto: str, actor: User) -> LeadEvento:
    ensure_can_edit(actor, lead)
    ensure_open(lead)
    if not texto.strip():
        raise DomainError("Escribe la observación.")
    ev = _event(db, lead, TipoEventoLead.OBSERVACION, "Observación", actor, texto.strip())
    _after_action(lead)
    db.flush()
    return ev


def programar_seguimiento(
    db: Session,
    lead: Lead,
    *,
    accion: AccionSeguimiento,
    due_at,
    nota: str | None,
    actor: User,
) -> Seguimiento:
    ensure_can_edit(actor, lead)
    ensure_open(lead)
    if due_at < fechas.now() - timedelta(minutes=5):
        raise DomainError("La fecha y hora del seguimiento ya pasaron.")
    seg = Seguimiento(
        lead_id=lead.id,
        accion=accion,
        due_at=due_at,
        nota=(nota or "").strip() or None,
        created_by_id=actor.id,
    )
    lead.seguimientos.append(seg)
    _event(
        db,
        lead,
        TipoEventoLead.SEGUIMIENTO,
        f"Seguimiento programado · {fechas.fmt(due_at)} · {ACCION_LABELS[accion]}",
        actor,
        seg.nota,
        {"accion": accion.value, "due_at": due_at.isoformat()},
    )
    if lead.etapa != EtapaLead.CITA_PROGRAMADA:
        lead.etapa = EtapaLead.SEGUIMIENTO
    db.flush()
    return seg


def completar_seguimiento(
    db: Session, lead: Lead, seguimiento_id: uuid.UUID, *, resultado: str, actor: User
) -> Seguimiento:
    ensure_can_edit(actor, lead)
    ensure_open(lead)
    seg = next((s for s in lead.seguimientos if s.id == seguimiento_id), None)
    if seg is None:
        raise NotFoundError("Seguimiento no encontrado.")
    if seg.done_at is not None:
        raise DomainError("Este seguimiento ya está marcado como realizado.")
    if not resultado.strip():
        raise DomainError("Escribe qué pasó o qué se habló.")
    seg.done_at = fechas.now()
    seg.done_by_id = actor.id
    seg.resultado = resultado.strip()
    _event(
        db,
        lead,
        TipoEventoLead.SEGUIMIENTO,
        f"Seguimiento realizado · {ACCION_LABELS[seg.accion]}",
        actor,
        seg.resultado,
        {"seguimiento_id": str(seg.id)},
    )
    _after_action(lead)
    db.flush()
    return seg


def change_stage(
    db: Session,
    lead: Lead,
    etapa: EtapaLead,
    *,
    motivo: MotivoPerdida | None,
    actor: User,
) -> Lead:
    manager = is_manager(actor)
    if etapa == lead.etapa:
        return lead
    if etapa == EtapaLead.CITA_PROGRAMADA:
        raise DomainError("«Cita programada» se asigna sola al programar una cita.")
    if lead.is_closed and not manager:
        raise PermissionDeniedError("Solo Coordinación o Gerencia pueden reabrir un lead cerrado.")
    ensure_can_edit(actor, lead)
    if etapa == EtapaLead.GANADO and not manager:
        raise PermissionDeniedError(
            "«Ganado» lo marca Coordinación o Gerencia cuando se confirma el cierre del negocio."
        )

    closing = etapa in ETAPAS_CERRADAS
    if closing and (activa := lead.cita_activa):
        raise DomainError(f"Primero cancela o cierra la cita {activa.code}.")

    detalle = None
    if etapa == EtapaLead.PERDIDO:
        if motivo is None:
            raise DomainError("Elige el motivo por el que se perdió el lead.")
        stats = call_stats(db, lead)
        lead.motivo_perdida = motivo
        reglas = configuracion.get(db, "leads")
        lead.perdida_descuenta = perdida_descuenta(
            motivo, stats, reglas["llamadas_minimas"], reglas["dias_seguidos"]
        )
        titulo = f"Lead marcado como perdido · {MOTIVO_LABELS[motivo]}"
        detalle = (
            "Descuenta en el rendimiento."
            if lead.perdida_descuenta
            else "No descuenta en el rendimiento."
        ) + f" Llamadas registradas: {stats.llamadas}."
    elif etapa == EtapaLead.GANADO:
        lead.motivo_perdida = None
        lead.perdida_descuenta = None
        titulo = "Lead ganado"
    else:
        if lead.is_closed:
            lead.motivo_perdida = None
            lead.perdida_descuenta = None
            lead.cerrado_at = None
            titulo = f"Lead reabierto · {ETAPA_LABELS[etapa]}"
        else:
            titulo = f"Etapa: {ETAPA_LABELS[etapa]}"

    if closing:
        lead.cerrado_at = fechas.now()
        for seg in lead.seguimientos:  # no reminders for archived leads
            if seg.done_at is None:
                seg.done_at = lead.cerrado_at
                seg.done_by_id = actor.id
                seg.resultado = "Cancelado: el lead se cerró."

    lead.etapa = etapa
    _event(
        db,
        lead,
        TipoEventoLead.ETAPA,
        titulo,
        actor,
        detalle,
        {"etapa": etapa.value, "motivo": motivo.value if motivo else None},
    )
    db.flush()
    return lead


# ---------------------------------------------------------------- dashboard numbers


def stats(db: Session, user: User, periodo: str) -> dict[str, int]:
    """KPI row of C01. Team totals for managers; own work for Atención / Pre-ventas."""
    today = fechas.local_date(fechas.now())
    start_day = {
        "hoy": today,
        "semana": today - timedelta(days=today.weekday()),
        "mes": today.replace(day=1),
    }.get(periodo)
    if start_day is None:
        raise DomainError("Período no válido.")
    start = fechas.start_of_day(start_day)
    mine = not is_manager(user)

    def count(stmt) -> int:
        return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    def ev(tipo: TipoEventoLead):
        stmt = select(LeadEvento.id).where(LeadEvento.tipo == tipo, LeadEvento.created_at >= start)
        return stmt.where(LeadEvento.created_by_id == user.id) if mine else stmt

    llamadas = ev(TipoEventoLead.LLAMADA)
    end = fechas.start_of_day(today + timedelta(days=1))
    segs = select(Seguimiento.id).where(Seguimiento.due_at >= start, Seguimiento.due_at < end)
    citas = select(Cita.id).where(Cita.created_at >= start)
    realizadas = select(Cita.id).where(
        Cita.estado == EstadoCita.REALIZADA, Cita.scheduled_at >= start
    )
    if mine:
        segs = segs.where(Seguimiento.created_by_id == user.id)
        citas = citas.where(Cita.created_by_id == user.id)
        realizadas = realizadas.where(Cita.created_by_id == user.id)

    return {
        "recibidos": count(select(Lead.id).where(Lead.created_at >= start)),
        "sin_responsable": count(
            select(Lead.id).where(Lead.assigned_to_id.is_(None), Lead.etapa.not_in(ETAPAS_CERRADAS))
        ),
        "seguidos": count(ev(TipoEventoLead.SEGUIR)),
        "llamadas": count(llamadas),
        "llamadas_contestadas": count(
            llamadas.where(LeadEvento.datos["resultado"].astext == ResultadoLlamada.CONTESTO.value)
        ),
        "seguimientos": count(segs),
        "seguimientos_realizados": count(segs.where(Seguimiento.done_at.is_not(None))),
        "citas_programadas": count(citas),
        "citas_realizadas": count(realizadas),
    }
