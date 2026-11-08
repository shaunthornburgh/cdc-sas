"""Registro de cambios (prototypes G06 «Registro de cambios» and G06-coord; decisions G-0xx).

Quién hizo qué, cuándo, y cómo estaba antes y después. It **doesn't store anything new**: it reads
the histories each module already keeps (lead_eventos, captacion_eventos, pedido_eventos,
movimiento_eventos, compensacion_eventos, configuracion_eventos, user_cambios…) and the records
that already say who did something and when (novedades, preoperacional reviews, platform updates,
agenda, comunicados), and shows them as one list. Nothing here can be edited or deleted.

* **Gerencia** sees everything.
* **Coordinación** sees the operation of its team: not comisiones, bonos, pagos, salarios, negocios
  (money) nor the configuración (G06-coord: «Comisiones, bonos, pagos y permisos solo los ve
  Gerencia»).
* Every download is logged too (in configuracion_eventos, section «registro_cambios»).
"""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ActividadEvento,
    AdminEvento,
    AgendaItem,
    Bono,
    Captacion,
    CaptacionEvento,
    Cierre,
    Cita,
    Comision,
    Comunicado,
    ConfigEvento,
    Inmueble,
    InmuebleEvento,
    Inventario,
    Lead,
    LeadEvento,
    LiquidacionSalario,
    Movimiento,
    MovimientoEvento,
    Novedad,
    Pedido,
    PedidoEvento,
    Plataforma,
    PlataformaActualizacion,
    PlataformaEvento,
    Preoperacional,
    RendimientoCambio,
    Reparacion,
    Solicitud,
    User,
    UserCambio,
)
from app.models.enums import Cargo, TipoEventoLead
from app.services import fechas
from app.services.errors import DomainError, PermissionDeniedError

MODULOS = [
    "Leads",
    "Citas",
    "Seguimientos",
    "Captaciones",
    "Pedidos",
    "Inmuebles",
    "Administración",
    "Indicadores",
    "Usuarios",
    "Ausencias",
    "Preoperacional",
    "GPS",
    "Plataformas",
    "Agenda",
    "Avisos",
    "Comisiones",
    "Bonos",
    "Pagos",
    "Salarios",
    "Negocios",
    "Integraciones",
    "Pólizas",
    "Rutas",
    "Asistencia",
    "Capacitaciones",
    "Pausas activas",
    "Descargas",
    "Configuración",
]
SOLO_GERENCIA = frozenset(
    {
        "Comisiones",
        "Bonos",
        "Pagos",
        "Salarios",
        "Negocios",
        "Integraciones",
        "Pólizas",
        "Configuración",
    }
)
MAX_POR_FUENTE = 3000
MAX_DIAS = 366
MAX_DESCARGA = 10_000


# ---------------------------------------------------------------- access


def can_view(user: User) -> bool:
    return user.is_active and user.cargo in (Cargo.GERENCIA, Cargo.COORDINACION)


def ensure_view(user: User) -> None:
    if not can_view(user):
        raise PermissionDeniedError("El registro de cambios lo ven Gerencia y Coordinación.")


def modulos_de(user: User) -> list[str]:
    if user.cargo == Cargo.GERENCIA:
        return MODULOS
    return [m for m in MODULOS if m not in SOLO_GERENCIA]


# ---------------------------------------------------------------- rows


@dataclass
class Fila:
    id: str
    at: datetime
    actor_id: uuid.UUID | None
    actor: str | None
    modulo: str
    accion: str
    registro: str | None = None
    antes: str | None = None
    despues: str | None = None
    link: str | None = None


def _txt(v: Any, limite: int = 220) -> str | None:
    """Dicts and lists as «clave: valor · clave: valor»; empty as None."""
    if v is None or v == "" or v == {} or v == []:
        return None
    if isinstance(v, dict):
        partes = [
            f"{str(k).replace('_', ' ')}: {_txt(x, 80)}"
            for k, x in v.items()
            if x not in (None, "", {}, [])
        ]
        s = " · ".join(partes)
    elif isinstance(v, (list, tuple)):
        s = ", ".join(str(x) for x in v)
    elif isinstance(v, bool):
        s = "sí" if v else "no"
    else:
        s = str(v)
    return (s[: limite - 1] + "…") if len(s) > limite else (s or None)


def _mes(d: date) -> str:
    return f"{fechas._MESES[d.month - 1]} {d.year}"


def _name(u: User | None) -> str | None:
    return u.full_name if u else None


@dataclass
class Rango:
    t1: datetime
    t2: datetime
    actor_id: uuid.UUID | None


Fuente = Callable[[Session, Rango], list[Fila]]
FUENTES: list[tuple[frozenset[str], Fuente]] = []


def fuente(*modulos: str):
    def deco(fn: Fuente) -> Fuente:
        FUENTES.append((frozenset(modulos), fn))
        return fn

    return deco


def _rango(q, col, r: Rango, actor_col):
    q = q.where(col >= r.t1, col < r.t2)
    if r.actor_id is not None:
        q = q.where(actor_col == r.actor_id)
    return q.order_by(col.desc()).limit(MAX_POR_FUENTE)


# ---------------------------------------------------------------- sources: comercial


@fuente("Leads", "Citas", "Seguimientos")
def _leads(db: Session, r: Rango) -> list[Fila]:
    q = (
        select(LeadEvento, Lead, Cita)
        .join(Lead, Lead.id == LeadEvento.lead_id)
        .outerjoin(Cita, Cita.id == LeadEvento.cita_id)
    )
    out = []
    for ev, lead, cita in db.execute(
        _rango(q, LeadEvento.created_at, r, LeadEvento.created_by_id)
    ).unique():
        modulo = (
            "Citas"
            if ev.tipo == TipoEventoLead.CITA
            else "Seguimientos"
            if ev.tipo == TipoEventoLead.SEGUIMIENTO
            else "Leads"
        )
        datos = ev.datos or {}
        antes = datos.get("antes")
        despues = datos.get("despues")
        if antes is None and despues is None and "campos" in datos:
            campos = datos["campos"]
            if isinstance(campos, dict):
                antes = {
                    k: v[0]
                    for k, v in campos.items()
                    if isinstance(v, (list, tuple)) and len(v) == 2
                }
                despues = {
                    k: v[1]
                    for k, v in campos.items()
                    if isinstance(v, (list, tuple)) and len(v) == 2
                }
        out.append(
            Fila(
                id=f"lead:{ev.id}",
                at=ev.created_at,
                actor_id=ev.created_by_id,
                actor=_name(ev.created_by),
                modulo=modulo,
                accion=ev.titulo,
                registro=cita.code if cita else lead.code,
                antes=_txt(antes),
                despues=_txt(despues) or _txt(ev.detalle),
                link=f"/leads/{lead.id}",
            )
        )
    return out


@fuente("Captaciones")
def _captaciones(db: Session, r: Rango) -> list[Fila]:
    q = select(CaptacionEvento, Captacion).join(
        Captacion, Captacion.id == CaptacionEvento.captacion_id
    )
    return [
        Fila(
            id=f"cap:{ev.id}",
            at=ev.created_at,
            actor_id=ev.created_by_id,
            actor=_name(ev.created_by),
            modulo="Captaciones",
            accion=ev.titulo,
            registro=f"{c.code} · {c.codigo_inmueble}",
            despues=_txt(ev.detalle),
            link=f"/captaciones/{c.id}",
        )
        for ev, c in db.execute(
            _rango(q, CaptacionEvento.created_at, r, CaptacionEvento.created_by_id)
        ).unique()
    ]


@fuente("Pedidos")
def _pedidos(db: Session, r: Rango) -> list[Fila]:
    q = select(PedidoEvento, Pedido).join(Pedido, Pedido.id == PedidoEvento.pedido_id)
    return [
        Fila(
            id=f"ped:{ev.id}",
            at=ev.created_at,
            actor_id=ev.created_by_id,
            actor=_name(ev.created_by),
            modulo="Pedidos",
            accion=ev.titulo,
            registro=p.code,
            antes=_txt((ev.datos or {}).get("antes")),
            despues=_txt((ev.datos or {}).get("despues")) or _txt(ev.detalle),
            link="/pedidos",
        )
        for ev, p in db.execute(
            _rango(q, PedidoEvento.created_at, r, PedidoEvento.created_by_id)
        ).unique()
    ]


@fuente("Inmuebles")
def _inmuebles(db: Session, r: Rango) -> list[Fila]:
    q = select(InmuebleEvento, Inmueble).join(Inmueble, Inmueble.id == InmuebleEvento.inmueble_id)
    return [
        Fila(
            id=f"inm:{ev.id}",
            at=ev.created_at,
            actor_id=ev.created_by_id,
            actor=_name(ev.created_by),
            modulo="Inmuebles",
            accion=ev.titulo,
            registro=i.codigo,
            antes=_txt((ev.datos or {}).get("antes")),
            despues=_txt((ev.datos or {}).get("despues")) or _txt(ev.detalle),
            link="/inmuebles",
        )
        for ev, i in db.execute(
            _rango(q, InmuebleEvento.created_at, r, InmuebleEvento.created_by_id)
        ).unique()
    ]


@fuente("Administración")
def _admin(db: Session, r: Rango) -> list[Fila]:
    evs = list(
        db.scalars(
            _rango(select(AdminEvento), AdminEvento.created_at, r, AdminEvento.created_by_id)
        ).unique()
    )
    codes: dict[uuid.UUID, str] = {}
    for model, col in (
        (Inventario, "inventario_id"),
        (Reparacion, "reparacion_id"),
        (Solicitud, "solicitud_id"),
    ):
        ids = {getattr(e, col) for e in evs if getattr(e, col)}
        if ids:
            for x in db.scalars(select(model).where(model.id.in_(ids))).unique():
                codes[x.id] = x.code
    return [
        Fila(
            id=f"adm:{e.id}",
            at=e.created_at,
            actor_id=e.created_by_id,
            actor=_name(e.created_by),
            modulo="Administración",
            accion=e.titulo,
            registro=codes.get(e.inventario_id or e.reparacion_id or e.solicitud_id),  # type: ignore[arg-type]
            despues=_txt(e.detalle),
            link="/inmuebles/administracion",
        )
        for e in evs
    ]


# ---------------------------------------------------------------- sources: people


@fuente("Usuarios")
def _usuarios(db: Session, r: Rango) -> list[Fila]:
    from app.services.users import CAMPO_LABELS

    out = []
    q = select(ActividadEvento, User).join(User, User.id == ActividadEvento.user_id)
    for ev, u in db.execute(
        _rango(q, ActividadEvento.created_at, r, ActividadEvento.changed_by_id)
    ).unique():
        act = ev.actividad.value.capitalize().replace("Captacion", "Captación")
        out.append(
            Fila(
                id=f"act:{ev.id}",
                at=ev.created_at,
                actor_id=ev.changed_by_id,
                actor=ev.changed_by_name,
                modulo="Usuarios",
                accion=f"{'Activó' if ev.activada else 'Quitó'} la actividad {act}",
                registro=u.full_name,
                antes="Inactiva" if ev.activada else "Activa",
                despues="Activa" if ev.activada else "Inactiva",
                link="/usuarios",
            )
        )
    q2 = select(UserCambio, User).join(User, User.id == UserCambio.user_id)
    for c, u in db.execute(_rango(q2, UserCambio.created_at, r, UserCambio.actor_id)).unique():
        propio = c.actor_id == c.user_id
        campo = CAMPO_LABELS.get(c.campo, c.campo).lower()
        out.append(
            Fila(
                id=f"uc:{c.id}",
                at=c.created_at,
                actor_id=c.actor_id,
                actor=_name(c.actor),
                modulo="Usuarios",
                accion=f"{'Cambió su' if propio else 'Cambió'} {campo}",
                registro=u.full_name,
                antes=c.antes,
                despues=c.despues,
                link=None if propio else "/usuarios",
            )
        )
    return out


@fuente("Indicadores")
def _indicadores(db: Session, r: Rango) -> list[Fila]:
    q = select(RendimientoCambio, User).join(User, User.id == RendimientoCambio.user_id)
    acc = {"pesos": "Cambió los pesos", "metas": "Cambió las metas", "calificaciones": "Calificó"}
    return [
        Fila(
            id=f"ren:{c.id}",
            at=c.created_at,
            actor_id=c.created_by_id,
            actor=_name(c.created_by),
            modulo="Indicadores",
            accion=f"{acc.get(c.tipo, c.tipo)} · {_mes(c.periodo)}",
            registro=u.full_name,
            antes=_txt(c.antes),
            despues=_txt(c.despues),
            link=f"/resultados/{u.id}",
        )
        for c, u in db.execute(
            _rango(q, RendimientoCambio.created_at, r, RendimientoCambio.created_by_id)
        ).unique()
    ]


@fuente("Ausencias")
def _novedades(db: Session, r: Rango) -> list[Fila]:
    from app.services.novedades import TIPO_LABELS

    out = []
    for n in db.scalars(
        _rango(select(Novedad), Novedad.created_at, r, Novedad.registrada_por_id)
    ).unique():
        out.append(
            Fila(
                id=f"nov:{n.id}",
                at=n.created_at,
                actor_id=n.registrada_por_id,
                actor=_name(n.registrada_por),
                modulo="Ausencias",
                accion=f"Registró {TIPO_LABELS[n.tipo].lower()}",
                registro=f"{n.code} · {n.empleado.full_name}",
                despues=f"{n.dias} día{'s' if n.dias != 1 else ''} · "
                f"{n.desde.isoformat()} a {n.hasta.isoformat()}",
                link="/novedades",
            )
        )
    q = select(Novedad).where(Novedad.anulada_at.is_not(None))
    for n in db.scalars(_rango(q, Novedad.anulada_at, r, Novedad.anulada_por_id)).unique():
        out.append(
            Fila(
                id=f"nova:{n.id}",
                at=n.anulada_at,  # type: ignore[arg-type]
                actor_id=n.anulada_por_id,
                actor=_name(n.anulada_por),
                modulo="Ausencias",
                accion="Anuló la novedad",
                registro=f"{n.code} · {n.empleado.full_name}",
                antes="Registrada",
                despues=f"Anulada · {n.motivo_anulacion}",
                link="/novedades",
            )
        )
    return out


@fuente("Preoperacional")
def _preop(db: Session, r: Rango) -> list[Fila]:
    q = select(Preoperacional).where(Preoperacional.revisado_at.is_not(None))
    return [
        Fila(
            id=f"pre:{p.id}",
            at=p.revisado_at,  # type: ignore[arg-type]
            actor_id=p.revisado_por_id,
            actor=_name(p.revisado_por),
            modulo="Preoperacional",
            accion="Revisó la novedad del preoperacional",
            registro=f"{p.user.full_name} · {p.fecha.isoformat()}",
            antes="Por revisar",
            despues="Revisada" + (f" · {p.revision_nota}" if p.revision_nota else ""),
            link="/preoperacionales",
        )
        for p in db.scalars(
            _rango(q, Preoperacional.revisado_at, r, Preoperacional.revisado_por_id)
        ).unique()
    ]


# ---------------------------------------------------------------- sources: field, platforms, agenda


@fuente("GPS")
def _gps(db: Session, r: Rango) -> list[Fila]:
    from app.models.enums import EstadoMovimiento
    from app.services.movimientos import ESTADO_LABELS, EVENTO_LABELS

    def est(v: str | None) -> str | None:
        try:
            return ESTADO_LABELS[EstadoMovimiento(v)] if v else None
        except ValueError:
            return v

    q = select(MovimientoEvento, Movimiento).outerjoin(
        Movimiento, Movimiento.id == MovimientoEvento.movimiento_id
    )
    out = []
    for ev, m in db.execute(
        _rango(q, MovimientoEvento.created_at, r, MovimientoEvento.actor_id)
    ).unique():
        out.append(
            Fila(
                id=f"mov:{ev.id}",
                at=ev.created_at,
                actor_id=ev.actor_id,
                actor=_name(ev.actor),
                modulo="GPS",
                accion=EVENTO_LABELS[ev.tipo]
                + (f" · {ev.detalle}" if m is None and ev.detalle else ""),
                registro=f"{m.code} · {m.empleado.full_name}" if m else "Movimientos y GPS",
                antes=est(ev.estado_antes) if m else None,
                despues=(est(ev.estado_despues) if ev.estado_despues != ev.estado_antes else None)
                or (_txt(ev.detalle) if m else None),
                link="/movimientos",
            )
        )
    return out


@fuente("Plataformas")
def _plataformas(db: Session, r: Rango) -> list[Fila]:
    nombres = {p.id: p.nombre for p in db.scalars(select(Plataforma)).unique()}
    acc = {
        "responsable": "Asignó el responsable",
        "plan": "Registró o corrigió el plan",
        "activa": "Activó o desactivó la plataforma",
        "regla": "Cambió cada cuántos días se actualiza",
        "descarga": "Descargó el histórico",
    }
    out = [
        Fila(
            id=f"pla:{ev.id}",
            at=ev.created_at,
            actor_id=ev.actor_id,
            actor=_name(ev.actor),
            modulo="Plataformas",
            accion=acc.get(ev.tipo.value, ev.tipo.value),
            registro=nombres.get(ev.plataforma_id) if ev.plataforma_id else "Todas",
            antes=ev.antes,
            despues=ev.despues or _txt(ev.detalle),
            link="/plataformas",
        )
        for ev in db.scalars(
            _rango(
                select(PlataformaEvento), PlataformaEvento.created_at, r, PlataformaEvento.actor_id
            )
        ).unique()
    ]
    q = select(PlataformaActualizacion)
    for a in db.scalars(
        _rango(
            q, PlataformaActualizacion.realizada_at, r, PlataformaActualizacion.actualizado_por_id
        )
    ).unique():
        out.append(
            Fila(
                id=f"plu:{a.id}",
                at=a.realizada_at,
                actor_id=a.actualizado_por_id,
                actor=_name(a.actualizado_por),
                modulo="Plataformas",
                accion="Registró la actualización"
                + ("" if a.a_tiempo else f" (tarde, {a.dias_desde_anterior} días)"),
                registro=a.plataforma.nombre,
                despues=f"Cupo {a.cupo_usado} de {a.cupo_total} · "
                f"destacados {a.destacados_usados} de {a.destacados_total}",
                link="/plataformas",
            )
        )
    return out


@fuente("Agenda")
def _agenda(db: Session, r: Rango) -> list[Fila]:
    out = []
    for it in db.scalars(
        _rango(select(AgendaItem), AgendaItem.created_at, r, AgendaItem.creado_por_id)
    ).unique():
        propia = it.creado_por_id == it.user_id
        out.append(
            Fila(
                id=f"agc:{it.id}",
                at=it.created_at,
                actor_id=it.creado_por_id,
                actor=_name(it.creado_por),
                modulo="Agenda",
                accion="Agregó una actividad a su agenda" if propia else "Asignó una actividad",
                registro=it.user.full_name,
                despues=f"«{it.titulo}» · {it.fecha.isoformat()}",
            )
        )
    q = select(AgendaItem).where(
        AgendaItem.respondida_at.is_not(None), AgendaItem.creado_por_id != AgendaItem.user_id
    )
    for it in db.scalars(_rango(q, AgendaItem.respondida_at, r, AgendaItem.user_id)).unique():
        verbo = {"hecha": "Marcó hecha", "rechazada": "Rechazó", "justificada": "Justificó"}.get(
            it.estado, "Respondió"
        )
        out.append(
            Fila(
                id=f"agr:{it.id}",
                at=it.respondida_at,  # type: ignore[arg-type]
                actor_id=it.user_id,
                actor=it.user.full_name,
                modulo="Agenda",
                accion=f"{verbo} una actividad asignada",
                registro=f"«{it.titulo}»",
                antes="Pendiente",
                despues=it.estado.capitalize() + (f" · {it.motivo}" if it.motivo else ""),
            )
        )
    q = select(AgendaItem).where(AgendaItem.eliminado_at.is_not(None))
    for it in db.scalars(
        _rango(q, AgendaItem.eliminado_at, r, AgendaItem.eliminado_por_id)
    ).unique():
        out.append(
            Fila(
                id=f"age:{it.id}",
                at=it.eliminado_at,  # type: ignore[arg-type]
                actor_id=it.eliminado_por_id,
                actor=_name(it.eliminado_por),
                modulo="Agenda",
                accion="Eliminó una actividad",
                registro=it.user.full_name,
                antes=f"«{it.titulo}» · {it.fecha.isoformat()}",
                despues="Eliminada",
            )
        )
    return out


@fuente("Avisos")
def _comunicados(db: Session, r: Rango) -> list[Fila]:
    from app.services.avisos import AUDIENCIAS

    return [
        Fila(
            id=f"com:{c.id}",
            at=c.created_at,
            actor_id=c.creado_por_id,
            actor=_name(c.creado_por),
            modulo="Avisos",
            accion="Envió un aviso" + (" de prioridad alta" if c.prioridad == "alta" else ""),
            registro=", ".join(AUDIENCIAS.get(a, a) for a in c.audiencia),
            despues=f"«{c.titulo}»",
            link="/avisos?tab=enviados",
        )
        for c in db.scalars(
            _rango(select(Comunicado), Comunicado.created_at, r, Comunicado.creado_por_id)
        ).unique()
    ]


# ---------------------------------------------------------------- sources: Gerencia only


@fuente("Comisiones", "Bonos", "Pagos", "Salarios", "Negocios")
def _compensacion(db: Session, r: Rango) -> list[Fila]:
    from app.models import CompensacionEvento

    evs = list(
        db.scalars(
            _rango(
                select(CompensacionEvento),
                CompensacionEvento.created_at,
                r,
                CompensacionEvento.created_by_id,
            )
        ).unique()
    )
    ids: dict[str, set[uuid.UUID]] = {}
    for e in evs:
        try:
            ids.setdefault(e.entidad, set()).add(uuid.UUID(e.entidad_id))
        except ValueError:
            continue
    nombre: dict[uuid.UUID, str] = {}
    if ids.get("comision"):
        for c in db.scalars(select(Comision).where(Comision.id.in_(ids["comision"]))).unique():
            nombre[c.id] = (f"{c.cierre.code} · " if c.cierre else "") + c.beneficiario.full_name
    if ids.get("bono"):
        for b in db.scalars(select(Bono).where(Bono.id.in_(ids["bono"]))).unique():
            nombre[b.id] = b.beneficiario.full_name
    if ids.get("cierre"):
        for c in db.scalars(select(Cierre).where(Cierre.id.in_(ids["cierre"]))).unique():
            nombre[c.id] = c.code
    if ids.get("liquidacion"):
        for x in db.scalars(
            select(LiquidacionSalario).where(LiquidacionSalario.id.in_(ids["liquidacion"]))
        ).unique():
            nombre[x.id] = (
                f"{x.user.full_name} · {'1.er' if x.corte == 1 else '2.º'} corte "
                f"{fechas._MESES[x.periodo.month - 1]}"
            )
    if ids.get("salario"):
        for u in db.scalars(select(User).where(User.id.in_(ids["salario"]))).unique():
            nombre[u.id] = u.full_name
    modulo = {
        "comision": "Comisiones",
        "bono": "Bonos",
        "pago": "Pagos",
        "liquidacion": "Salarios",
        "salario": "Salarios",
        "cierre": "Negocios",
    }
    out = []
    for e in evs:
        try:
            reg = nombre.get(uuid.UUID(e.entidad_id))
        except ValueError:
            reg = None
        out.append(
            Fila(
                id=f"cmp:{e.id}",
                at=e.created_at,
                actor_id=e.created_by_id,
                actor=_name(e.created_by),
                modulo=modulo.get(e.entidad, "Comisiones"),
                accion=e.accion,
                registro=reg or ("Configuración de pagos" if e.entidad == "config" else None),
                antes=_txt(e.antes),
                despues=_txt(e.despues),
                link=(
                    "/salarios"
                    if e.entidad in ("liquidacion", "salario")
                    else "/negocios"
                    if e.entidad == "cierre"
                    else "/compensacion"
                ),
            )
        )
    return out


@fuente("Integraciones")
def _integraciones(db: Session, r: Rango) -> list[Fila]:
    from app.models import IntegracionEvento

    q = select(IntegracionEvento)
    return [
        Fila(
            id=f"int:{e.id}",
            at=e.created_at,
            actor_id=e.actor_id,
            actor=_name(e.actor),
            modulo="Integraciones",
            accion=e.accion,
            registro=e.integracion.nombre,
            antes=e.antes,
            despues=e.despues,
            link="/integraciones",
        )
        for e in db.scalars(
            _rango(q, IntegracionEvento.created_at, r, IntegracionEvento.actor_id)
        ).unique()
    ]


@fuente("Pólizas")
def _polizas(db: Session, r: Rango) -> list[Fila]:
    from app.models import PolizaEvento

    q = select(PolizaEvento)
    return [
        Fila(
            id=f"pol:{e.id}",
            at=e.created_at,
            actor_id=e.actor_id,
            actor=_name(e.actor),
            modulo="Pólizas",
            accion=e.accion,
            registro=e.registro,
            antes=e.antes,
            despues=e.despues,
            link="/polizas",
        )
        for e in db.scalars(_rango(q, PolizaEvento.created_at, r, PolizaEvento.actor_id)).unique()
    ]


@fuente("Rutas")
def _rutas(db: Session, r: Rango) -> list[Fila]:
    from app.models import RutaEvento

    q = select(RutaEvento)
    return [
        Fila(
            id=f"rut:{e.id}",
            at=e.created_at,
            actor_id=e.actor_id,
            actor=_name(e.actor),
            modulo="Rutas",
            accion=e.accion,
            registro=f"{e.ruta.asesor.full_name} · {e.ruta.desde:%d/%m}–{e.ruta.hasta:%d/%m}",
            antes=e.antes,
            despues=e.despues,
            link="/rutas?tab=list",
        )
        for e in db.scalars(_rango(q, RutaEvento.created_at, r, RutaEvento.actor_id)).unique()
    ]


@fuente("Asistencia")
def _asistencia(db: Session, r: Rango) -> list[Fila]:
    from app.models import AsistenciaEvento

    q = select(AsistenciaEvento)
    return [
        Fila(
            id=f"asi:{e.id}",
            at=e.created_at,
            actor_id=e.actor_id,
            actor=_name(e.actor),
            modulo="Asistencia",
            accion=e.accion,
            registro=e.registro,
            antes=e.antes,
            despues=e.despues,
            link="/asistencia",
        )
        for e in db.scalars(
            _rango(q, AsistenciaEvento.created_at, r, AsistenciaEvento.actor_id)
        ).unique()
    ]


@fuente("Configuración")
def _configuracion(db: Session, r: Rango) -> list[Fila]:
    from app.services.configuracion import SECCION_LABELS

    return [
        Fila(
            id=f"cfg:{e.id}",
            at=e.created_at,
            actor_id=e.actor_id,
            actor=_name(e.actor),
            modulo="Configuración",
            accion="Descargó el registro de cambios"
            if e.seccion == "registro_cambios"
            else f"Cambió {SECCION_LABELS.get(e.seccion, e.seccion).lower()}",
            registro="Registro de cambios"
            if e.seccion == "registro_cambios"
            else SECCION_LABELS.get(e.seccion, e.seccion),
            antes=_txt(e.antes),
            despues=_txt(e.despues) or e.detalle,
            link=None if e.seccion == "registro_cambios" else "/configuracion",
        )
        for e in db.scalars(
            _rango(
                select(ConfigEvento).where(
                    ConfigEvento.seccion.not_in(("descargas", "pausas_activas"))
                ),
                ConfigEvento.created_at,
                r,
                ConfigEvento.actor_id,
            )
        ).unique()
    ]


@fuente("Capacitaciones")
def _capacitaciones(db: Session, r: Rango) -> list[Fila]:
    from app.models import CapacitacionEvento

    q = select(CapacitacionEvento)
    return [
        Fila(
            id=f"cap:{e.id}",
            at=e.created_at,
            actor_id=e.actor_id,
            actor=_name(e.actor),
            modulo="Capacitaciones",
            accion=e.accion,
            registro=f"{e.capacitacion.code} · {e.capacitacion.tema}",
            despues=e.detalle,
            link="/capacitaciones?tab=equipo",
        )
        for e in db.scalars(
            _rango(q, CapacitacionEvento.created_at, r, CapacitacionEvento.actor_id)
        ).unique()
    ]


@fuente("Pausas activas")
def _pausas(db: Session, r: Rango) -> list[Fila]:
    """G11: schedule and message changes (the pauses themselves are a daily record, not changes)."""
    return [
        Fila(
            id=f"pau:{e.id}",
            at=e.created_at,
            actor_id=e.actor_id,
            actor=_name(e.actor),
            modulo="Pausas activas",
            accion=f"Cambió {(e.detalle or 'la configuración').lower()}",
            registro="Pausas activas",
            antes=_txt(e.antes),
            despues=_txt(e.despues),
            link="/pausas-activas?tab=equipo",
        )
        for e in db.scalars(
            _rango(
                select(ConfigEvento).where(ConfigEvento.seccion == "pausas_activas"),
                ConfigEvento.created_at,
                r,
                ConfigEvento.actor_id,
            )
        ).unique()
    ]


@fuente("Descargas")
def _descargas(db: Session, r: Rango) -> list[Fila]:
    """X10: who downloaded which file of the staff's data (logged by services.descargas)."""
    return [
        Fila(
            id=f"dsc:{e.id}",
            at=e.created_at,
            actor_id=e.actor_id,
            actor=_name(e.actor),
            modulo="Descargas",
            accion=f"Descargó {str(e.despues.get('descarga', 'un archivo')).lower()}",
            registro=e.despues.get("archivo"),
            antes=None,
            despues=" · ".join(
                str(x) for x in (e.despues.get("quien"), e.despues.get("periodo"), e.detalle) if x
            ),
            link="/descargas",
        )
        for e in db.scalars(
            _rango(
                select(ConfigEvento).where(ConfigEvento.seccion == "descargas"),
                ConfigEvento.created_at,
                r,
                ConfigEvento.actor_id,
            )
        ).unique()
    ]


# ---------------------------------------------------------------- query


@dataclass
class Filtros:
    desde: date
    hasta: date
    modulo: str | None = None
    actor_id: uuid.UUID | None = None
    q: str | None = None


def rango_defecto() -> tuple[date, date]:
    hoy = fechas.local_date(fechas.now())
    return hoy - timedelta(days=6), hoy


def consultar(db: Session, user: User, f: Filtros) -> list[Fila]:
    """Every visible row of the range, newest first (no pagination)."""
    ensure_view(user)
    if f.desde > f.hasta:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    if (f.hasta - f.desde).days > MAX_DIAS:
        raise DomainError("Consulta como máximo un año a la vez.")
    visibles = set(modulos_de(user))
    if f.modulo:
        if f.modulo not in MODULOS:
            raise DomainError("Ese módulo no existe.")
        if f.modulo not in visibles:
            raise PermissionDeniedError("Ese módulo solo lo ve Gerencia.")
        visibles = {f.modulo}
    r = Rango(
        fechas.start_of_day(f.desde), fechas.start_of_day(f.hasta + timedelta(days=1)), f.actor_id
    )
    filas: list[Fila] = []
    for mods, fn in FUENTES:
        if mods & visibles:
            filas += [x for x in fn(db, r) if x.modulo in visibles]
    if f.q and f.q.strip():
        needle = f.q.strip().lower()
        filas = [
            x
            for x in filas
            if any(
                needle in (v or "").lower()
                for v in (x.registro, x.accion, x.antes, x.despues, x.actor)
            )
        ]
    filas.sort(key=lambda x: x.at, reverse=True)
    return filas


def actores(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.full_name)).unique())


def export_csv(db: Session, user: User, f: Filtros) -> tuple[str, int]:
    from app.models import ConfigEvento as CE

    filas = consultar(db, user, f)[:MAX_DESCARGA]
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf)
    w.writerow(["Fecha", "Hora", "Usuario", "Módulo", "Acción", "Registro", "Antes", "Después"])
    for x in filas:
        local = x.at.astimezone(fechas.BOGOTA)
        w.writerow(
            [
                local.date().isoformat(),
                f"{local:%H:%M}",
                x.actor or "Sistema",
                x.modulo,
                x.accion,
                x.registro or "",
                x.antes or "",
                x.despues or "",
            ]
        )
    filtros = {
        "desde": f.desde.isoformat(),
        "hasta": f.hasta.isoformat(),
        "modulo": f.modulo,
        "q": f.q,
    }
    ev = CE(
        seccion="registro_cambios",
        actor_id=user.id,
        antes={},
        despues={k: v for k, v in filtros.items() if v},
        detalle=f"{len(filas)} filas",
    )
    ev.actor = user
    db.add(ev)
    db.flush()
    return buf.getvalue(), len(filas)
