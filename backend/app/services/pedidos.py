"""Pedidos (prototypes K06 / M06 / C10; decisions G-006 and the later «Pedidos» corrections).

- One form: cliente, negocio, tipo de inmueble, zona, presupuesto, fecha límite, urgencia,
  responsable, observaciones. Before creating, warn if the client already has an open pedido
  (the caller can still create it: «Es otra necesidad»).
- Only the responsable or Coordinación / Gerencia «Actualizar» (keeps before and after),
  mark «Atendido» or «Perdido» (with a reason), extend the deadline or reassign.
- Anyone in the module can «Proponer un inmueble» or «Comentar al responsable» on others'.
- A pedido past its deadline is never lost by itself: someone chooses «Extender fecha»
  (with a reason) or «Marcar perdido». Attended after expiring = «Recuperado».
- Asesores and Atención see their own and their team's; Coordinación and Gerencia see all.
"""

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Lead, Pedido, PedidoEvento, User
from app.models.enums import (
    EstadoPedido,
    MotivoPerdidaPedido,
    TipoEventoPedido,
    TipoNegocio,
    UrgenciaPedido,
)
from app.services import fechas
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError
from app.services.policies import can_own_pedidos, is_manager

E = EstadoPedido
# Single list for the whole tool (decision: «listas únicas en toda la herramienta»).
ZONAS = ("Belén", "El Poblado", "Envigado", "Guayabal", "Laureles", "Sabaneta", "Otra zona")
# Budget filter ranges of the prototype.
RANGOS = {
    "arr_2m": (TipoNegocio.ARRIENDO, 0, 2_000_000),
    "arr_2_5m": (TipoNegocio.ARRIENDO, 2_000_001, 5_000_000),
    "ven_500m": (TipoNegocio.VENTA, 0, 500_000_000),
    "ven_mas_500m": (TipoNegocio.VENTA, 500_000_001, None),
}
MOTIVO_LABELS = {
    MotivoPerdidaPedido.NO_INTERESARON: "No le interesaron las opciones",
    MotivoPerdidaPedido.COMPRO_CON_OTRO: "Compró o arrendó con otro",
    MotivoPerdidaPedido.PRESUPUESTO: "El presupuesto no alcanza",
    MotivoPerdidaPedido.NO_RESPONDE: "No responde",
    MotivoPerdidaPedido.OTRO: "Otro",
}
PROXIMO_A_VENCER = timedelta(days=3)
EDITABLE = (
    "negocio",
    "tipo_inmueble",
    "zona",
    "presupuesto",
    "fecha_limite",
    "urgencia",
    "observaciones",
    "cliente_nombre",
    "cliente_telefono",
)
_LABELS = {
    "negocio": "Negocio",
    "tipo_inmueble": "Tipo de inmueble",
    "zona": "Zona",
    "presupuesto": "Presupuesto",
    "fecha_limite": "Fecha límite",
    "urgencia": "Urgencia",
    "observaciones": "Observaciones",
    "cliente_nombre": "Cliente",
    "cliente_telefono": "Teléfono",
}


# ---------------------------------------------------------------- derived status


def vencido(p: Pedido, now: datetime | None = None) -> bool:
    return p.estado == E.ABIERTO and p.fecha_limite < (now or fechas.now())


def estado_visible(p: Pedido, now: datetime | None = None) -> str:
    """Chip of K06 / M06.

    urgente · vence_hoy · nuevo · abierto · vencido · atendido · recuperado · perdido
    """
    now = now or fechas.now()
    if p.estado == E.PERDIDO:
        return "perdido"
    if p.estado == E.ATENDIDO:
        return "recuperado" if p.vencio else "atendido"
    if vencido(p, now):
        return "vencido"
    if p.urgencia == UrgenciaPedido.URGENTE:
        return "urgente"
    if fechas.local_date(p.fecha_limite) == fechas.local_date(now):
        return "vence_hoy"
    if fechas.local_date(p.created_at or now) == fechas.local_date(now):
        return "nuevo"
    return "abierto"


def proximo_a_vencer(p: Pedido, now: datetime | None = None) -> bool:
    now = now or fechas.now()
    return p.estado == E.ABIERTO and now <= p.fecha_limite <= now + PROXIMO_A_VENCER


# ---------------------------------------------------------------- access


def can_edit(user: User, p: Pedido) -> bool:
    return is_manager(user) or p.responsable_id == user.id


def _ensure_edit(user: User, p: Pedido) -> None:
    if not can_edit(user, p):
        raise PermissionDeniedError(
            f"Solo {p.responsable.full_name} (responsable) o Coordinación pueden cambiarlo."
        )


def _ensure_open(p: Pedido) -> None:
    if p.estado != E.ABIERTO:
        raise DomainError(
            f"{p.code} ya está {'atendido' if p.estado == E.ATENDIDO else 'perdido'}."
        )


def get_pedido(db: Session, pedido_id: uuid.UUID) -> Pedido:
    p = db.get(Pedido, pedido_id)
    if p is None:
        raise NotFoundError("Pedido no encontrado.")
    return p


# ---------------------------------------------------------------- queries


@dataclass(frozen=True)
class PedidoFilters:
    vista: str = "mis"  # mis | equipo | todos | vencidos
    negocio: TipoNegocio | None = None
    zona: str | None = None
    rango: str | None = None
    proximos: bool = False
    responsable_id: uuid.UUID | None = None
    cerrados: bool = False  # include atendidos / perdidos
    q: str | None = None


def list_pedidos(db: Session, user: User, f: PedidoFilters) -> list[Pedido]:
    now = fechas.now()
    stmt = select(Pedido)
    if f.vista == "mis":
        stmt = stmt.where(Pedido.responsable_id == user.id)
    elif f.vista == "equipo":
        stmt = stmt.where(Pedido.responsable_id != user.id)
    elif f.vista == "vencidos":
        # Undecided expired ones + those that expired at some point (kept for Gerencia).
        stmt = stmt.where(
            or_((Pedido.estado == E.ABIERTO) & (Pedido.fecha_limite < now), Pedido.vencio)
        )
    elif f.vista == "todos":
        if not is_manager(user):
            raise PermissionDeniedError("Solo Coordinación y Gerencia ven todos los pedidos.")
    else:
        raise DomainError("Vista no válida.")
    if f.vista != "vencidos" and not f.cerrados:
        stmt = stmt.where(Pedido.estado == E.ABIERTO)
    if f.negocio:
        stmt = stmt.where(Pedido.negocio == f.negocio)
    if f.zona:
        stmt = stmt.where(Pedido.zona == f.zona)
    if f.rango:
        if f.rango not in RANGOS:
            raise DomainError("Rango de presupuesto no válido.")
        neg, lo, hi = RANGOS[f.rango]
        stmt = stmt.where(Pedido.negocio == neg, Pedido.presupuesto >= lo)
        if hi is not None:
            stmt = stmt.where(Pedido.presupuesto <= hi)
    if f.proximos:
        stmt = stmt.where(
            Pedido.estado == E.ABIERTO,
            Pedido.fecha_limite >= now,
            Pedido.fecha_limite <= now + PROXIMO_A_VENCER,
        )
    if f.responsable_id:
        stmt = stmt.where(Pedido.responsable_id == f.responsable_id)
    if f.q and (term := f.q.strip()):
        like = f"%{term}%"
        cond = Pedido.cliente_nombre.ilike(like) | Pedido.cliente_telefono.ilike(like)
        digits = term.upper().removeprefix("PED-").lstrip("0")
        if digits.isdigit():
            cond = cond | (Pedido.numero == int(digits))
        stmt = stmt.where(cond)
    rows = list(db.scalars(stmt.order_by(Pedido.fecha_limite)).unique())
    if f.vista == "vencidos":
        # Undecided first, then by deadline (most recent first).
        rows.sort(key=lambda p: (not vencido(p, now), -p.fecha_limite.timestamp()))
    return rows


def kpis(db: Session, user: User) -> dict[str, int]:
    """K06 cards. Managers: everyone; others: their own pedidos."""
    return kpis_globales(db, responsable_id=None if is_manager(user) else user.id)


def kpis_globales(db: Session, responsable_id: uuid.UUID | None = None) -> dict[str, int]:
    """Open, due within 3 days, expired this month, expired and still undecided."""
    now = fechas.now()
    month_start = fechas.start_of_day(fechas.local_date(now).replace(day=1))

    def n(stmt) -> int:
        return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    base = select(Pedido)
    if responsable_id:
        base = base.where(Pedido.responsable_id == responsable_id)
    abiertos = base.where(Pedido.estado == E.ABIERTO)
    return {
        "abiertos": n(abiertos),
        "proximos_a_vencer": n(
            abiertos.where(
                Pedido.fecha_limite >= now, Pedido.fecha_limite <= now + PROXIMO_A_VENCER
            )
        ),
        "vencidos_mes": n(
            base.where(
                Pedido.fecha_limite >= month_start,
                Pedido.fecha_limite < now,
                (Pedido.estado == E.ABIERTO) | Pedido.vencio,
            )
        ),
        "vencidos_sin_decidir": n(abiertos.where(Pedido.fecha_limite < now)),
    }


def pedido_abierto_del_cliente(
    db: Session, *, lead_id: uuid.UUID | None, telefono: str | None, nombre: str
) -> Pedido | None:
    conds = [func.lower(Pedido.cliente_nombre) == nombre.strip().lower()]
    if lead_id:
        conds.append(Pedido.lead_id == lead_id)
    if telefono and (digits := re.sub(r"\D", "", telefono)):
        conds.append(func.regexp_replace(Pedido.cliente_telefono, r"\D", "", "g") == digits)
    return (
        db.scalars(
            select(Pedido)
            .where(Pedido.estado == E.ABIERTO, or_(*conds))
            .order_by(Pedido.created_at)
        )
        .unique()
        .first()
    )


# ---------------------------------------------------------------- commands


def _event(
    db: Session,
    p: Pedido,
    tipo: TipoEventoPedido,
    titulo: str,
    actor: User | None,
    detalle: str | None = None,
    datos: dict[str, Any] | None = None,
) -> None:
    db.add(
        PedidoEvento(
            pedido_id=p.id,
            tipo=tipo,
            titulo=titulo,
            detalle=detalle,
            datos=datos or {},
            created_by_id=actor.id if actor else None,
        )
    )


def _validate(data: Mapping[str, Any]) -> None:
    if "zona" in data and data["zona"] not in ZONAS:
        raise DomainError("Elige una zona de la lista.")
    if "presupuesto" in data and (data["presupuesto"] is None or data["presupuesto"] <= 0):
        raise DomainError("Escribe el presupuesto del cliente.")


def _check_responsable(db: Session, responsable_id: uuid.UUID) -> User:
    u = db.get(User, responsable_id)
    if u is None or not can_own_pedidos(u):
        raise DomainError(
            "El responsable debe ser un asesor o una persona de Atención y Preventa activa."
        )
    return u


def create_pedido(
    db: Session,
    data: Mapping[str, Any],
    *,
    actor: User | None,
    responsable_id: uuid.UUID | None = None,
    otra_necesidad: bool = False,
) -> Pedido:
    _validate(data)
    if data["fecha_limite"] < fechas.now():
        raise DomainError("La fecha límite ya pasó.")
    resp = _check_responsable(db, responsable_id or (actor.id if actor else None))
    if not otra_necesidad and (
        dup := pedido_abierto_del_cliente(
            db,
            lead_id=data.get("lead_id"),
            telefono=data.get("cliente_telefono"),
            nombre=data["cliente_nombre"],
        )
    ):
        raise ConflictError(
            f"{dup.cliente_nombre} ya tiene el pedido {dup.code} abierto: "
            f"{dup.negocio.value} · {dup.tipo_inmueble.value} · {dup.zona} · responsable "
            f"{dup.responsable.full_name}. Si el cliente cambió lo que busca, actualiza ese pedido."
        )
    if data.get("lead_id") and db.get(Lead, data["lead_id"]) is None:
        raise DomainError("El lead no existe.")
    p = Pedido(
        **{k: data.get(k) for k in EDITABLE if k in data},
        lead_id=data.get("lead_id"),
        responsable_id=resp.id,
        responsable=resp,
        created_by_id=actor.id if actor else None,
    )
    db.add(p)
    db.flush()
    por = "" if actor is None or actor.id == resp.id else f" Lo creó {actor.full_name}."
    _event(
        db,
        p,
        TipoEventoPedido.CREADO,
        f"Pedido {p.code} creado",
        actor,
        f"Responsable: {resp.full_name}. Fecha límite: {fechas.fmt(p.fecha_limite)}.{por}",
    )
    db.flush()
    return p


def _fmt(k: str, v: Any) -> str:
    if v is None:
        return "—"
    if k == "presupuesto":
        return f"${v:,.0f}".replace(",", ".")
    if k == "fecha_limite":
        return fechas.fmt(v)
    return getattr(v, "value", str(v))


def actualizar(
    db: Session, p: Pedido, changes: Mapping[str, Any], *, que_cambio: str, actor: User
) -> Pedido:
    """«Actualizar»: same pedido, the history keeps what it was and what it is now."""
    _ensure_edit(actor, p)
    _ensure_open(p)
    if not (que_cambio or "").strip():
        raise DomainError("Escribe qué cambió.")
    data = {k: v for k, v in changes.items() if k in EDITABLE}
    _validate(data)
    if "fecha_limite" in data and data["fecha_limite"] < fechas.now():
        raise DomainError("La nueva fecha límite ya pasó.")
    changed = {k: v for k, v in data.items() if getattr(p, k) != v}
    antes = {k: _fmt(k, getattr(p, k)) for k in changed}
    for k, v in changed.items():
        setattr(p, k, v)
    despues = {k: _fmt(k, getattr(p, k)) for k in changed}
    detalle = " · ".join(f"{_LABELS[k]}: {antes[k]} → {despues[k]}" for k in changed)
    _event(
        db,
        p,
        TipoEventoPedido.ACTUALIZADO,
        f"Actualizado · {que_cambio.strip()}",
        actor,
        detalle or None,
        {"antes": antes, "despues": despues},
    )
    db.flush()
    return p


def extender(db: Session, p: Pedido, nueva_fecha: datetime, *, motivo: str, actor: User) -> Pedido:
    _ensure_edit(actor, p)
    _ensure_open(p)
    if not vencido(p):
        raise DomainError(
            "Solo se extiende la fecha de un pedido vencido; para cambiarla antes, actualízalo."
        )
    if nueva_fecha < fechas.now():
        raise DomainError("La nueva fecha límite ya pasó.")
    if not (motivo or "").strip():
        raise DomainError("Escribe el motivo.")
    antes = p.fecha_limite
    p.fecha_limite = nueva_fecha
    p.vencio = True
    _event(
        db,
        p,
        TipoEventoPedido.EXTENDIDO,
        f"Fecha extendida · {fechas.fmt(antes)} → {fechas.fmt(nueva_fecha)}",
        actor,
        motivo.strip(),
    )
    db.flush()
    return p


def atender(db: Session, p: Pedido, *, nota: str | None, actor: User) -> Pedido:
    _ensure_edit(actor, p)
    _ensure_open(p)
    if vencido(p):
        p.vencio = True
    p.estado = E.ATENDIDO
    p.cerrado_at = fechas.now()
    _event(
        db,
        p,
        TipoEventoPedido.ATENDIDO,
        "Recuperado y atendido" if p.vencio else "Atendido",
        actor,
        (nota or "").strip() or None,
    )
    db.flush()
    return p


def marcar_perdido(
    db: Session, p: Pedido, *, motivo: MotivoPerdidaPedido, nota: str | None, actor: User
) -> Pedido:
    _ensure_edit(actor, p)
    _ensure_open(p)
    if vencido(p):
        p.vencio = True
    p.estado = E.PERDIDO
    p.motivo_perdida = motivo
    p.cerrado_at = fechas.now()
    detalle = MOTIVO_LABELS[motivo] + (f" · {nota.strip()}" if (nota or "").strip() else "")
    _event(db, p, TipoEventoPedido.PERDIDO, "Cliente perdido", actor, detalle)
    db.flush()
    return p


def proponer(db: Session, p: Pedido, *, inmueble: str, nota: str | None, actor: User) -> Pedido:
    """«Proponer un inmueble» to the responsable (anyone in the module)."""
    _ensure_open(p)
    if not (inmueble or "").strip():
        raise DomainError("Escribe el inmueble que propones.")
    _event(
        db,
        p,
        TipoEventoPedido.PROPUESTA,
        f"{actor.full_name} propone {inmueble.strip()}",
        actor,
        (nota or "").strip() or None,
        {"inmueble": inmueble.strip()},
    )
    db.flush()
    return p


def comentar(db: Session, p: Pedido, *, texto: str, actor: User) -> Pedido:
    if not (texto or "").strip():
        raise DomainError("Escribe el comentario.")
    _event(
        db, p, TipoEventoPedido.COMENTARIO, f"Comentario de {actor.full_name}", actor, texto.strip()
    )
    db.flush()
    return p


def reasignar(db: Session, p: Pedido, responsable_id: uuid.UUID, *, actor: User) -> Pedido:
    if not is_manager(actor):
        raise PermissionDeniedError("Solo Coordinación o Gerencia reasignan pedidos.")
    _ensure_open(p)
    if responsable_id == p.responsable_id:
        return p
    nuevo = _check_responsable(db, responsable_id)
    antes = p.responsable.full_name
    p.responsable_id = nuevo.id
    p.responsable = nuevo
    _event(
        db,
        p,
        TipoEventoPedido.REASIGNADO,
        f"Reasignado a {nuevo.full_name}",
        actor,
        f"Antes: {antes}.",
    )
    db.flush()
    return p


def responsables(db: Session) -> list[User]:
    users = db.scalars(select(User).where(User.is_active).order_by(User.full_name)).unique()
    return [u for u in users if can_own_pedidos(u)]
