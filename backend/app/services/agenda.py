"""Agenda (G09 agenda, M17 / C07 / X06 «Mi agenda», K19 «Agenda»; decisions G-088, G-089, G-090).

* **One view per person** that joins what the system puts in the agenda (citas, seguimientos,
  vencimientos de pedidos) with the activities added by hand.
* **Who sees which agenda** (G-088): each person their own; Coordinación also its team (asesores
  and Atención y Preventa); Gerencia and the Auxiliar everyone's. Asesores never see another one.
* **Who adds in which agenda**: each person in their own; Coordinación in asesores' and Atención's;
  Gerencia in all; the Auxiliar in all but Gerencia's.
* **What can be done with an activity**: each person only deletes what they put (it goes to
  «Actividades eliminadas» with who and when). What someone else put is marked done, rejected or
  justified, rejecting and justifying with a mandatory reason; whoever put it gets an aviso.
* **Atrasada** (G-090): pending and its date (and time) already passed.
* System items are read-only; «Abrir» only shows in your own agenda.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import AgendaItem, Aviso, Cita, Lead, Pedido, Seguimiento, User
from app.models.enums import Cargo, EstadoCita, EstadoPedido, TipoCita
from app.services import fechas
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError
from app.services.policies import LEAD_FUNCIONES, has_commercial_activity

ROL_TXT = {
    "ger": "Gerencia",
    "coo": "Coordinación",
    "aux": "Auxiliar administrativa",
    "ase": "Asesor",
    "ate": "Atención y Preventa",
}
ESTADO = {
    "pendiente": ("Pendiente", "gray"),
    "atrasada": ("Atrasada", "bad"),
    "hecha": ("✓ Hecha", "ok"),
    "rechazada": ("Rechazada", "bad"),
    "justificada": ("Justificada", "info"),
}
# Legend (G09): colour per kind of item
TIPOS = {
    "cita": "Cita",
    "seg": "Seguimiento o pendiente",
    "ped": "Vencimiento",
    "ctl": "Control e inventario",
    "mia": "Agregada por la persona",
    "asg": "Asignada por otra persona",
}
MAX_DIAS = 42
CITAS_CONTROL = (TipoCita.VISITA_CONTROL, TipoCita.INVENTARIO)


# ---------------------------------------------------------------- who


def rol(u: User) -> str | None:
    if not u.is_active:
        return None
    if u.cargo == Cargo.GERENCIA:
        return "ger"
    if u.cargo == Cargo.COORDINACION:
        return "coo"
    if u.cargo == Cargo.AUXILIAR_ADMINISTRATIVA:
        return "aux"
    if u.funcion in LEAD_FUNCIONES:
        return "ate"
    if has_commercial_activity(u):
        return "ase"
    return None


def puede_ver(viewer: User, target: User) -> bool:
    rv, rt = rol(viewer), rol(target)
    if rv is None or rt is None:
        return False
    if viewer.id == target.id or rv in ("ger", "aux"):
        return True
    return rv == "coo" and rt in ("ase", "ate")


def puede_agregar(viewer: User, target: User) -> bool:
    rv, rt = rol(viewer), rol(target)
    if rv is None or rt is None:
        return False
    if viewer.id == target.id or rv == "ger":
        return True
    if rv == "aux":
        return rt != "ger"
    return rv == "coo" and rt in ("ase", "ate")


def ensure_use(user: User) -> None:
    if rol(user) is None:
        raise PermissionDeniedError("Tu cargo no tiene agenda.")


def personas(db: Session, viewer: User) -> list[User]:
    """«Agenda de [persona]»: you first, then the agendas you can see."""
    ensure_use(viewer)
    us = [
        u
        for u in db.scalars(select(User).where(User.is_active.is_(True))).unique()
        if u.id != viewer.id and puede_ver(viewer, u)
    ]
    return [viewer, *sorted(us, key=lambda u: u.full_name)]


def get_target(db: Session, viewer: User, user_id: uuid.UUID | None) -> User:
    ensure_use(viewer)
    if user_id is None or user_id == viewer.id:
        return viewer
    t = db.get(User, user_id)
    if t is None or not puede_ver(viewer, t):
        raise NotFoundError("No puedes ver esa agenda.")
    return t


# ---------------------------------------------------------------- items


def _cuando(it: AgendaItem) -> datetime:
    return datetime.combine(it.fecha, it.hora or time(23, 59), tzinfo=fechas.BOGOTA)


def estado_de(it: AgendaItem, now: datetime) -> str:
    if it.estado == "pendiente" and _cuando(it) < now:
        return "atrasada"
    return it.estado


def acciones(viewer: User, it: AgendaItem) -> dict[str, bool]:
    """G-088: owner marks done; rejects / justifies only what others put; delete only your own."""
    mio = it.creado_por_id == viewer.id
    dueno = it.user_id == viewer.id
    pend = it.estado == "pendiente" and it.eliminado_at is None
    return {
        "hecha": dueno and pend,
        "rechazar": dueno and not mio and pend,
        "justificar": dueno and not mio and pend,
        "eliminar": mio and it.eliminado_at is None,
    }


def manuales(db: Session, target: User, d1: date, d2: date) -> list[AgendaItem]:
    return list(
        db.scalars(
            select(AgendaItem).where(
                AgendaItem.user_id == target.id,
                AgendaItem.eliminado_at.is_(None),
                AgendaItem.fecha >= d1,
                AgendaItem.fecha <= d2,
            )
        ).unique()
    )


def eliminadas(db: Session, target: User, limit: int = 20) -> list[AgendaItem]:
    return list(
        db.scalars(
            select(AgendaItem)
            .where(AgendaItem.user_id == target.id, AgendaItem.eliminado_at.is_not(None))
            .order_by(AgendaItem.eliminado_at.desc())
            .limit(limit)
        ).unique()
    )


def sistema(db: Session, viewer: User, target: User, d1: date, d2: date) -> list[dict[str, Any]]:
    """What the system puts in the agenda: citas, seguimientos and pedido deadlines (read-only).

    «Abrir» only in your own agenda (G-089).
    """
    t1, t2 = fechas.start_of_day(d1), fechas.start_of_day(d2 + timedelta(days=1))
    now = fechas.now()
    yo = viewer.id == target.id
    rt = rol(target)
    out: list[dict[str, Any]] = []
    from app.services.citas import TIPO_LABELS as CITA_LABELS

    q = select(Cita).where(
        Cita.scheduled_at >= t1,
        Cita.scheduled_at < t2,
        Cita.estado.in_(
            (EstadoCita.PENDIENTE, EstadoCita.ACEPTADA, EstadoCita.REALIZADA, EstadoCita.RECHAZADA)
        ),
    )
    if rt == "ate":
        q = q.join(Lead, Lead.id == Cita.lead_id).where(
            or_(Cita.asesor_id == target.id, Lead.assigned_to_id == target.id)
        )
    else:
        q = q.where(Cita.asesor_id == target.id)
    est_cita = {
        EstadoCita.PENDIENTE: ("Por aceptar", "warn"),
        EstadoCita.ACEPTADA: ("Aceptada", "ok"),
        EstadoCita.REALIZADA: ("✓ Realizada", "ok"),
        EstadoCita.RECHAZADA: ("Rechazada", "bad"),
    }
    for c in db.scalars(q).unique():
        local = c.scheduled_at.astimezone(fechas.BOGOTA)
        e, cls = est_cita[c.estado]
        quien = c.asesor_name if rt == "ate" and c.asesor_id != target.id else None
        out.append(
            {
                "id": f"cita:{c.id}",
                "k": "sys",
                "tipo": "ctl" if c.tipo in CITAS_CONTROL else "cita",
                "fecha": local.date(),
                "hora": local.time().replace(second=0, microsecond=0),
                "titulo": f"{CITA_LABELS[c.tipo]} · {c.code}",
                "sub": " · ".join(x for x in (c.lead.full_name, c.inmueble, quien) if x),
                "estado_txt": e,
                "estado_cls": cls,
                "link": ("/mis-citas" if rt == "ase" else "/citas") if yo else None,
            }
        )

    if rt in ("ate", "coo", "ger"):
        from app.services.leads import ACCION_LABELS

        segs = db.scalars(
            select(Seguimiento)
            .join(Lead, Lead.id == Seguimiento.lead_id)
            .where(
                Lead.assigned_to_id == target.id,
                Seguimiento.due_at >= t1,
                Seguimiento.due_at < t2,
            )
        ).unique()
        for s in segs:
            local = s.due_at.astimezone(fechas.BOGOTA)
            if s.done_at:
                e, cls = "✓ Hecho", "ok"
            elif s.due_at < now:
                e, cls = "Vencido", "bad"
            else:
                e, cls = (
                    ("Hoy", "gray")
                    if local.date() == fechas.local_date(now)
                    else ("Programado", "gray")
                )
            out.append(
                {
                    "id": f"seg:{s.id}",
                    "k": "sys",
                    "tipo": "seg",
                    "fecha": local.date(),
                    "hora": local.time().replace(second=0, microsecond=0),
                    "titulo": f"Seguimiento · {ACCION_LABELS[s.accion]} · {s.lead.full_name}",
                    "sub": s.lead.code + (f" · {s.nota}" if s.nota else ""),
                    "estado_txt": e,
                    "estado_cls": cls,
                    "link": f"/leads/{s.lead_id}" if yo else None,
                }
            )

    if rt == "ase":
        from app.services import rutas

        out += rutas.agenda_items(db, target, d1, d2, propia=yo)

    peds = db.scalars(
        select(Pedido).where(
            Pedido.responsable_id == target.id,
            Pedido.estado == EstadoPedido.ABIERTO,
            Pedido.fecha_limite >= t1,
            Pedido.fecha_limite < t2,
        )
    ).unique()
    for p in peds:
        local = p.fecha_limite.astimezone(fechas.BOGOTA)
        vencido = p.fecha_limite < now
        out.append(
            {
                "id": f"ped:{p.id}",
                "k": "sys",
                "tipo": "ped",
                "fecha": local.date(),
                "hora": local.time().replace(second=0, microsecond=0),
                "titulo": f"Vence {p.code}",
                "sub": f"{p.negocio.value.capitalize()} · {p.cliente_nombre}",
                "estado_txt": "Vencido"
                if vencido
                else ("Vence hoy" if local.date() == fechas.local_date(now) else "Por vencer"),
                "estado_cls": "bad"
                if vencido or local.date() == fechas.local_date(now)
                else "warn",
                "link": "/pedidos" if yo else None,
            }
        )
    return out


def get_item(db: Session, viewer: User, id_: uuid.UUID) -> AgendaItem:
    it = db.get(AgendaItem, id_)
    if it is None or it.eliminado_at is not None or not puede_ver(viewer, it.user):
        raise NotFoundError("Esa actividad no existe.")
    return it


# ---------------------------------------------------------------- commands


def agregar(
    db: Session,
    actor: User,
    data: dict[str, Any],
    *,
    para: User | None = None,
    aviso: Aviso | None = None,
) -> AgendaItem:
    para = para or actor
    if not puede_agregar(actor, para):
        raise PermissionDeniedError("No puedes agregar actividades a esa agenda.")
    titulo = (data.get("titulo") or "").strip()
    if len(titulo) < 3:
        raise DomainError("Escribe la actividad y la fecha.")
    fecha = data.get("fecha")
    if fecha is None:
        raise DomainError("Escribe la actividad y la fecha.")
    if fecha < fechas.local_date(fechas.now()):
        raise DomainError("La fecha ya pasó.")
    prioridad = data.get("prioridad") or "normal"
    if prioridad not in ("normal", "alta"):
        raise DomainError("La prioridad es normal o alta.")
    it = AgendaItem(
        user_id=para.id,
        creado_por_id=actor.id,
        fecha=fecha,
        hora=data.get("hora"),
        titulo=titulo[:200],
        nota=(data.get("nota") or "").strip()[:500] or None,
        prioridad=prioridad,
        estado="pendiente",
        aviso_id=aviso.id if aviso else None,
    )
    it.user, it.creado_por, it.aviso = para, actor, aviso
    db.add(it)
    db.flush()
    if aviso is not None:
        from app.services import avisos

        cuando = f"{fecha.day} {fechas._MESES[fecha.month - 1]}" + (
            f" {data['hora']:%H:%M}" if data.get("hora") else ""
        )
        avisos.agregar_nota(
            db, aviso, f"Agendado en mi agenda: «{it.titulo}» · {cuando}", actor=actor
        )
    return it


def _avisar_respuesta(db: Session, it: AgendaItem, actor: User) -> None:
    """Whoever assigned the activity gets an aviso with the answer (G-088)."""
    if it.creado_por_id is None or it.creado_por_id == actor.id:
        return
    verbo = {"hecha": "marcó hecha", "rechazada": "rechazó", "justificada": "justificó"}[it.estado]
    db.add(
        Aviso(
            destinatario_id=it.creado_por_id,
            origen="sistema",
            clave=f"agenda_respuesta:{it.id}:{it.estado}",
            tipo="agenda_respuesta",
            tipo_txt="Agenda",
            nivel="ok" if it.estado == "hecha" else "warn",
            titulo=f"{actor.full_name} {verbo} «{it.titulo}»",
            detalle=f"Motivo: {it.motivo}" if it.motivo else None,
            link="/agenda",
            accion_txt="Ver su agenda",
            requiere_accion=False,
            estado="por_atender",
        )
    )


def marcar_hecha(db: Session, it: AgendaItem, *, actor: User) -> AgendaItem:
    if not acciones(actor, it)["hecha"]:
        raise PermissionDeniedError(
            "Solo la persona de la agenda la marca hecha, si está pendiente."
        )
    now = fechas.now()
    it.estado, it.hecha_at, it.respondida_at = "hecha", now, now
    _avisar_respuesta(db, it, actor)
    db.flush()
    return it


def responder(
    db: Session, it: AgendaItem, estado: str, motivo: str | None, *, actor: User
) -> AgendaItem:
    """Reject or justify what someone else assigned, always with a reason."""
    if estado not in ("rechazada", "justificada"):
        raise DomainError("La respuesta es rechazar o justificar.")
    if not acciones(actor, it)["rechazar"]:
        if it.creado_por_id == actor.id:
            raise ConflictError("Lo que pusiste tú no se rechaza: elimínalo.")
        raise PermissionDeniedError("Solo la persona de la agenda responde lo que le asignaron.")
    motivo = (motivo or "").strip()
    if len(motivo) < 3:
        raise DomainError("Escribe el motivo.")
    it.estado, it.motivo, it.respondida_at = estado, motivo[:500], fechas.now()
    _avisar_respuesta(db, it, actor)
    db.flush()
    return it


def eliminar(db: Session, it: AgendaItem, *, actor: User) -> AgendaItem:
    if not acciones(actor, it)["eliminar"]:
        raise PermissionDeniedError(
            "Solo se elimina lo que pusiste tú. "
            "Lo que te asignaron se hace, se rechaza o se justifica."
        )
    it.eliminado_at, it.eliminado_por_id, it.eliminado_por = fechas.now(), actor.id, actor
    db.flush()
    return it


def hora_txt(h: time | None) -> str:
    if h is None:
        return "Sin hora"
    return f"{(h.hour % 12) or 12}:{h.minute:02d} {'a. m.' if h.hour < 12 else 'p. m.'}"


def rango(desde: date | None, hasta: date | None) -> tuple[date, date]:
    """Default: 7 days from today (G09). At most six weeks at a time."""
    d1 = desde or fechas.local_date(fechas.now())
    d2 = hasta or d1 + timedelta(days=6)
    if d1 > d2:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    if (d2 - d1).days > MAX_DIAS:
        raise DomainError("Consulta como máximo seis semanas a la vez.")
    return d1, d2
