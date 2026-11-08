"""Coordinación / Gerencia dashboard (prototype K01-DashCoord, phone K11-CoordCel).

Everything is aggregated from existing data (users, leads, citas, captaciones, pedidos,
preoperacional) with grouped queries, so the cost doesn't grow with the number of people. The
prototype's tareas, GPS alerts, attendance and rendimiento tiles aren't here: they live on their
own pages (Agenda, Movimientos y GPS, Asistencia, Mi equipo).
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from app.models import Captacion, Cita, Lead, LeadEvento, Pedido, Seguimiento, User
from app.models.enums import (
    CITA_ACTIVA,
    ETAPAS_CERRADAS,
    EstadoCaptacion,
    EstadoCita,
    EstadoPedido,
    EtapaLead,
    ResultadoLlamada,
    TipoEventoLead,
    TipoNegocio,
)
from app.services import captaciones as cap_service
from app.services import citas as cita_service
from app.services import configuracion, fechas
from app.services import pedidos as pedido_service
from app.services import preoperacional as preop_service
from app.services.policies import LEAD_FUNCIONES, can_capture

# A lead waiting this long without an owner is flagged (the «aviso» of the prototype).
LEAD_SIN_RESPONSABLE_ALERTA = timedelta(minutes=15)  # default; Gerencia sets it in Configuración


def alerta_sin_responsable(db: Session) -> timedelta:
    return timedelta(minutes=configuracion.get(db, "automatizaciones")["lead_sin_responsable_min"])


# A follow-up counts as «a tiempo» if marked done within this margin after its time.
SEGUIMIENTO_TOLERANCIA = timedelta(minutes=30)
LIST_LIMIT = 6


@dataclass(frozen=True)
class Ventana:
    now: datetime
    hoy: datetime
    manana: datetime
    semana: datetime
    mes: datetime


def ventana() -> Ventana:
    now = fechas.now()
    today = fechas.local_date(now)
    return Ventana(
        now=now,
        hoy=fechas.start_of_day(today),
        manana=fechas.start_of_day(today + timedelta(days=1)),
        semana=fechas.start_of_day(today - timedelta(days=today.weekday())),
        mes=fechas.start_of_day(today.replace(day=1)),
    )


def _count(db: Session, stmt: Select) -> int:
    return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0


def _by(db: Session, stmt) -> dict:
    return {k: v for k, v in db.execute(stmt).all()}


# ---------------------------------------------------------------- leads


def leads_summary(db: Session, v: Ventana | None = None) -> dict[str, Any]:
    v = v or ventana()
    abiertos = Lead.etapa.not_in(ETAPAS_CERRADAS)
    por_etapa = dict.fromkeys([e.value for e in EtapaLead], 0)
    for etapa, n in db.execute(
        select(Lead.etapa, func.count()).where(abiertos).group_by(Lead.etapa)
    ):
        por_etapa[EtapaLead(etapa).value] = n
    # Closed ones only for this month (they're archived).
    for etapa, n in db.execute(
        select(Lead.etapa, func.count())
        .where(Lead.etapa.in_(ETAPAS_CERRADAS), Lead.cerrado_at >= v.mes)
        .group_by(Lead.etapa)
    ):
        por_etapa[EtapaLead(etapa).value] = n

    por_negocio = {
        (k.value if k else "sin_tipo"): n
        for k, n in db.execute(
            select(Lead.negocio, func.count()).where(abiertos).group_by(Lead.negocio)
        )
    }
    sin_resp = select(Lead.id).where(abiertos, Lead.assigned_to_id.is_(None))
    vencidos = (
        select(Seguimiento.id)
        .join(Lead, Lead.id == Seguimiento.lead_id)
        .where(Seguimiento.done_at.is_(None), Seguimiento.due_at < v.now, abiertos)
    )
    return {
        "por_etapa": por_etapa,
        "abiertos": sum(n for k, n in por_etapa.items() if k not in ("ganado", "perdido")),
        "abiertos_por_negocio": por_negocio,
        "sin_responsable": _count(db, sin_resp),
        "sin_responsable_min": int(alerta_sin_responsable(db).total_seconds() // 60),
        "sin_responsable_alerta": _count(
            db, sin_resp.where(Lead.created_at < v.now - alerta_sin_responsable(db))
        ),
        "nuevos_hoy": _count(db, select(Lead.id).where(Lead.created_at >= v.hoy)),
        "nuevos_semana": _count(db, select(Lead.id).where(Lead.created_at >= v.semana)),
        "seguimientos_vencidos": _count(db, vencidos),
        "ganados_mes": por_etapa["ganado"],
        "perdidos_mes": por_etapa["perdido"],
        "perdidos_con_descuento_mes": _count(
            db,
            select(Lead.id).where(
                Lead.etapa == EtapaLead.PERDIDO, Lead.cerrado_at >= v.mes, Lead.perdida_descuenta
            ),
        ),
    }


# ---------------------------------------------------------------- citas


def _cita_item(c: Cita, now: datetime) -> dict[str, Any]:
    return {
        "id": c.id,
        "code": c.code,
        "tipo": c.tipo,
        "estado": c.estado,
        "scheduled_at": c.scheduled_at,
        "asesor_name": c.asesor_name,
        "lead_id": c.lead_id,
        "lead_code": c.lead.code,
        "lead_name": c.lead.full_name,
        "motivo": c.motivo,
        "requiere_accion": cita_service.requiere_accion(c, now),
    }


def citas_summary(db: Session, v: Ventana | None = None) -> dict[str, Any]:
    v = v or ventana()
    activas = list(
        db.scalars(
            select(Cita).where(Cita.estado.in_(CITA_ACTIVA)).order_by(Cita.scheduled_at)
        ).unique()
    )
    accion = [c for c in activas if cita_service.requiere_accion(c, v.now)]
    hoy = list(
        db.scalars(
            select(Cita)
            .where(
                Cita.scheduled_at >= v.hoy,
                Cita.scheduled_at < v.manana,
                Cita.estado != EstadoCita.CANCELADA,
            )
            .order_by(Cita.scheduled_at)
        ).unique()
    )
    proximas = [c for c in activas if c.scheduled_at >= v.now and c not in accion]
    pendientes = [c for c in activas if c.estado == EstadoCita.PENDIENTE]
    return {
        "pendientes": len(pendientes),
        "pendientes_menos_1h": sum(1 for c in pendientes if c in accion),
        "rechazadas": sum(1 for c in activas if c.estado == EstadoCita.RECHAZADA),
        "requieren_accion": len(accion),
        "hoy_total": len(hoy),
        "hoy_aceptadas": sum(1 for c in hoy if c.estado == EstadoCita.ACEPTADA),
        "hoy_realizadas": sum(1 for c in hoy if c.estado == EstadoCita.REALIZADA),
        "realizadas_mes": _count(
            db,
            select(Cita.id).where(Cita.estado == EstadoCita.REALIZADA, Cita.scheduled_at >= v.mes),
        ),
        "lista_accion": [_cita_item(c, v.now) for c in accion[:LIST_LIMIT]],
        "lista_hoy": [_cita_item(c, v.now) for c in hoy[: LIST_LIMIT * 2]],
        "lista_proximas": [_cita_item(c, v.now) for c in proximas[:LIST_LIMIT]],
    }


# ---------------------------------------------------------------- captaciones


def captaciones_summary(db: Session, v: Ventana | None = None) -> dict[str, Any]:
    v = v or ventana()
    counts = dict.fromkeys([e.value for e in EstadoCaptacion], 0)
    for estado, n in db.execute(select(Captacion.estado, func.count()).group_by(Captacion.estado)):
        counts[EstadoCaptacion(estado).value] = n
    pend = list(
        db.scalars(
            select(Captacion)
            .where(Captacion.estado == EstadoCaptacion.POR_VERIFICAR)
            .order_by(Captacion.enviada_at)
            .limit(LIST_LIMIT)
        ).unique()
    )
    verificadas_mes = select(Captacion).where(Captacion.verificado_at >= v.mes)
    return {
        "counts": counts,
        "aprobacion_pct": cap_service.aprobacion_pct(counts),
        "registradas_mes": _count(db, select(Captacion.id).where(Captacion.created_at >= v.mes)),
        "aprobadas_mes": _count(
            db, verificadas_mes.where(Captacion.estado == EstadoCaptacion.APROBADA)
        ),
        "rechazadas_mes": _count(
            db, verificadas_mes.where(Captacion.estado == EstadoCaptacion.RECHAZADA)
        ),
        "sin_publicar": _count(
            db,
            select(Captacion.id).where(
                Captacion.estado == EstadoCaptacion.APROBADA, Captacion.publicada_at.is_(None)
            ),
        ),
        "lista_por_verificar": [
            {
                "id": c.id,
                "code": c.code,
                "codigo_inmueble": c.codigo_inmueble,
                "negocio": c.negocio,
                "asesor_name": c.asesor.full_name,
                "enviada_at": c.enviada_at,
                "reenvios": c.reenvios,
            }
            for c in pend
        ],
    }


# ---------------------------------------------------------------- team


def _people(db: Session) -> tuple[list[User], list[User]]:
    """(asesores with commercial activities, Atención / Pre-ventas), active only."""
    users = list(db.scalars(select(User).where(User.is_active).order_by(User.full_name)).unique())
    asesores = [u for u in users if cita_service.es_asesor(u)]
    atencion = [u for u in users if u.funcion in LEAD_FUNCIONES]
    return asesores, atencion


def equipo(db: Session, v: Ventana | None = None) -> dict[str, Any]:
    v = v or ventana()
    asesores, atencion = _people(db)
    a_ids = [u.id for u in asesores]
    t_ids = [u.id for u in atencion]

    # --- asesores: citas and captaciones
    citas_rows = (
        list(
            db.scalars(
                select(Cita).where(
                    Cita.asesor_id.in_(a_ids),
                    (Cita.estado.in_(CITA_ACTIVA)) | (Cita.scheduled_at >= v.mes),
                )
            ).unique()
        )
        if a_ids
        else []
    )
    citas_by = defaultdict(list)
    for c in citas_rows:
        citas_by[c.asesor_id].append(c)

    capt = defaultdict(lambda: defaultdict(int))
    if a_ids:
        for asesor_id, negocio, estado, n, n_mes in db.execute(
            select(
                Captacion.asesor_id,
                Captacion.negocio,
                Captacion.estado,
                func.count(),
                func.count().filter(Captacion.verificado_at >= v.mes),
            )
            .where(Captacion.asesor_id.in_(a_ids))
            .group_by(Captacion.asesor_id, Captacion.negocio, Captacion.estado)
        ):
            estado = EstadoCaptacion(estado)
            if estado == EstadoCaptacion.APROBADA:
                capt[asesor_id][f"aprobadas_{TipoNegocio(negocio).value}_mes"] += n_mes
            elif estado == EstadoCaptacion.POR_VERIFICAR:
                capt[asesor_id]["por_verificar"] += n
            else:
                capt[asesor_id]["rechazadas"] += n

    asesores_out = []
    for u in asesores:
        mine = citas_by[u.id]
        pend = sorted(
            (c for c in mine if c.estado == EstadoCita.PENDIENTE), key=lambda c: c.scheduled_at
        )
        hoy = [
            c
            for c in mine
            if v.hoy <= c.scheduled_at < v.manana and c.estado != EstadoCita.CANCELADA
        ]
        cp = capt[u.id]
        capta = can_capture(u)
        asesores_out.append(
            {
                "id": u.id,
                "full_name": u.full_name,
                "actividades": u.actividades,
                "gps_checkin_enabled": u.gps_checkin_enabled,
                "citas_sin_aceptar": len(pend),
                "cita_sin_aceptar_code": pend[0].code if pend else None,
                "cita_sin_aceptar_urgente": any(
                    cita_service.requiere_accion(c, v.now) for c in pend
                ),
                "citas_hoy": len(hoy),
                "citas_aceptadas_activas": sum(
                    1 for c in mine if c.estado == EstadoCita.ACEPTADA and c.scheduled_at >= v.now
                ),
                "citas_realizadas_mes": sum(
                    1 for c in mine if c.estado == EstadoCita.REALIZADA and c.scheduled_at >= v.mes
                ),
                "captaciones_venta_mes": cp["aprobadas_venta_mes"] if capta else None,
                "captaciones_arriendo_mes": cp["aprobadas_arriendo_mes"] if capta else None,
                "captaciones_por_verificar": cp["por_verificar"] if capta else None,
                "captaciones_rechazadas": cp["rechazadas"] if capta else None,
            }
        )

    # --- Atención / Pre-ventas: their leads work this month
    ev = _by_user_events(db, t_ids, v)
    seg = defaultdict(lambda: {"total": 0, "a_tiempo": 0, "vencidos": 0})
    if t_ids:
        due_in_month = and_(Seguimiento.due_at >= v.mes, Seguimiento.due_at <= v.now)
        a_tiempo = and_(
            Seguimiento.done_at.is_not(None),
            Seguimiento.done_at <= Seguimiento.due_at + SEGUIMIENTO_TOLERANCIA,
        )
        for uid, total, ok, venc in db.execute(
            select(
                Seguimiento.created_by_id,
                func.count().filter(due_in_month),
                func.count().filter(due_in_month, a_tiempo),
                func.count().filter(Seguimiento.done_at.is_(None), Seguimiento.due_at < v.now),
            )
            .where(Seguimiento.created_by_id.in_(t_ids))
            .group_by(Seguimiento.created_by_id)
        ):
            seg[uid] = {"total": total, "a_tiempo": ok, "vencidos": venc}

    leads_by = defaultdict(lambda: defaultdict(int))
    primera = {}
    if t_ids:
        for uid, etapa, n in db.execute(
            select(Lead.assigned_to_id, Lead.etapa, func.count())
            .where(Lead.assigned_to_id.in_(t_ids))
            .where((Lead.etapa.not_in(ETAPAS_CERRADAS)) | (Lead.cerrado_at >= v.mes))
            .group_by(Lead.assigned_to_id, Lead.etapa)
        ):
            leads_by[uid][EtapaLead(etapa).value] += n
        primera = _by(
            db,
            select(
                Lead.assigned_to_id,
                func.avg(func.extract("epoch", Lead.assigned_at - Lead.created_at) / 60),
            )
            .where(Lead.assigned_to_id.in_(t_ids), Lead.assigned_at >= v.mes)
            .group_by(Lead.assigned_to_id),
        )
    citas_t = defaultdict(lambda: {"programadas": 0, "realizadas": 0, "accion": 0})
    if t_ids:
        for c in db.scalars(
            select(Cita).where(
                Cita.created_by_id.in_(t_ids),
                (Cita.created_at >= v.mes) | Cita.estado.in_(CITA_ACTIVA),
            )
        ).unique():
            row = citas_t[c.created_by_id]
            if c.created_at >= v.mes:
                row["programadas"] += 1
            if c.estado == EstadoCita.REALIZADA and c.scheduled_at >= v.mes:
                row["realizadas"] += 1
            if cita_service.requiere_accion(c, v.now):
                row["accion"] += 1

    atencion_out = []
    for u in atencion:
        lb = leads_by[u.id]
        e = ev[u.id]
        atencion_out.append(
            {
                "id": u.id,
                "full_name": u.full_name,
                "funcion": u.funcion,
                "leads_seguidos_mes": e["seguir"],
                "primera_respuesta_min": round(float(primera[u.id]))
                if primera.get(u.id) is not None
                else None,
                "llamadas_mes": e["llamadas"],
                "llamadas_contestadas_mes": e["contestadas"],
                "seguimientos_mes": seg[u.id]["total"],
                "seguimientos_a_tiempo_mes": seg[u.id]["a_tiempo"],
                "seguimientos_vencidos": seg[u.id]["vencidos"],
                "citas_programadas_mes": citas_t[u.id]["programadas"],
                "citas_realizadas_mes": citas_t[u.id]["realizadas"],
                "citas_requieren_accion": citas_t[u.id]["accion"],
                "leads_abiertos": sum(n for k, n in lb.items() if k not in ("ganado", "perdido")),
                "ganados_mes": lb["ganado"],
                "perdidos_mes": lb["perdido"],
            }
        )

    return {
        "usuarios_activos": _count(db, select(User.id).where(User.is_active)),
        "asesores_activos": len(asesores),
        "atencion_activos": len(atencion),
        "con_captacion": sum(1 for u in asesores if can_capture(u)),
        "asesores": asesores_out,
        "atencion": atencion_out,
    }


def _by_user_events(db: Session, ids: list[uuid.UUID], v: Ventana) -> dict:
    out = defaultdict(lambda: {"seguir": 0, "llamadas": 0, "contestadas": 0})
    if not ids:
        return out
    contesto = LeadEvento.datos["resultado"].astext == ResultadoLlamada.CONTESTO.value
    for uid, seguir, llamadas, contestadas in db.execute(
        select(
            LeadEvento.created_by_id,
            func.count().filter(LeadEvento.tipo == TipoEventoLead.SEGUIR),
            func.count().filter(LeadEvento.tipo == TipoEventoLead.LLAMADA),
            func.count().filter(LeadEvento.tipo == TipoEventoLead.LLAMADA, contesto),
        )
        .where(LeadEvento.created_by_id.in_(ids), LeadEvento.created_at >= v.mes)
        .group_by(LeadEvento.created_by_id)
    ):
        out[uid] = {"seguir": seguir, "llamadas": llamadas, "contestadas": contestadas}
    return out


# ---------------------------------------------------------------- alerts


def alertas(leads: dict, citas: dict, caps: dict, eq: dict) -> list[dict[str, Any]]:
    """«Alertas en tiempo real» (K01) with «Qué hacer» (K11). Most urgent first."""
    out: list[dict[str, Any]] = []
    now = fechas.now()
    for c in citas["lista_accion"]:
        if c["estado"] == EstadoCita.RECHAZADA:
            out.append(
                {
                    "nivel": "warn",
                    "titulo": f"{c['asesor_name'] or 'El asesor'} rechazó la cita {c['code']}",
                    "detalle": (f"Motivo: {c['motivo']} · " if c["motivo"] else "")
                    + f"{c['lead_name']} · {fechas.fmt(c['scheduled_at'])}",
                    "que_hacer": "Asignar otro asesor, reprogramarla o cancelarla.",
                    "link": "/citas",
                    "accion": "Ver la cita",
                }
            )
        else:
            mins = int((c["scheduled_at"] - now).total_seconds() // 60)
            cuando = "ya pasó la hora" if mins < 0 else f"faltan {mins} min"
            quien = c["asesor_name"] or "Sin asesor"
            out.append(
                {
                    "nivel": "bad",
                    "titulo": f"{c['code']} sin aceptar · {cuando}",
                    "detalle": f"{quien} · {c['lead_name']} · Atención y Preventa tiene el aviso",
                    "que_hacer": "Llamar al asesor o asignar la cita a otro.",
                    "link": "/citas",
                    "accion": "Ver la cita",
                }
            )
    if n := leads["sin_responsable_alerta"]:
        quien = "lead lleva" if n == 1 else "leads llevan"
        out.append(
            {
                "nivel": "warn",
                "titulo": f"{n} {quien} más de {leads['sin_responsable_min']} min sin responsable",
                "detalle": f"{leads['sin_responsable']} sin responsable en total",
                "que_hacer": "Pedir a Atención y Preventa que los tome, o asignarlos.",
                "link": "/leads",
                "accion": "Ver leads",
            }
        )
    if n := leads["seguimientos_vencidos"]:
        quienes = [p["full_name"] for p in eq["atencion"] if p["seguimientos_vencidos"]]
        out.append(
            {
                "nivel": "warn",
                "titulo": f"{n} {'seguimiento vencido' if n == 1 else 'seguimientos vencidos'}",
                "detalle": " · ".join(quienes) or "Sin responsable",
                "que_hacer": "Recordar a la persona que lo haga y lo marque como realizado.",
                "link": "/leads",
                "accion": "Ver leads",
            }
        )
    pend = caps["lista_por_verificar"]
    if n := caps["counts"]["por_verificar"]:
        que = "captación por verificar" if n == 1 else "captaciones por verificar"
        out.append(
            {
                "nivel": "warn",
                "titulo": f"{n} {que}",
                "detalle": " · ".join(
                    f"{firstname(p['asesor_name'])} {p['code']}" for p in pend[:4]
                ),
                "que_hacer": "Revisar el código en la otra plataforma y aprobar o rechazar.",
                "link": "/captaciones",
                "accion": "Verificar",
            }
        )
    rank = {"bad": 0, "warn": 1}
    return sorted(out, key=lambda a: rank[a["nivel"]])


def firstname(name: str) -> str:
    return name.split()[0] if name else ""


# ---------------------------------------------------------------- composite


def pedidos_summary(db: Session, v: Ventana | None = None) -> dict[str, Any]:
    v = v or ventana()
    abiertos = list(
        db.scalars(select(Pedido).where(Pedido.estado == EstadoPedido.ABIERTO)).unique()
    )
    sin_decidir = sorted(
        (p for p in abiertos if p.fecha_limite < v.now), key=lambda p: p.fecha_limite
    )
    por_persona: dict[str, dict[str, Any]] = {}
    for p in abiertos:
        row = por_persona.setdefault(
            str(p.responsable_id), {"por_vencer": 0, "hoy": 0, "vencidos": 0}
        )
        if p.fecha_limite < v.now:
            row["vencidos"] += 1
        elif pedido_service.proximo_a_vencer(p, v.now):
            row["por_vencer"] += 1
            if p.fecha_limite < v.manana:
                row["hoy"] += 1
    return {
        **pedido_service.kpis_globales(db),
        "por_persona": por_persona,
        "lista_sin_decidir": [
            {
                "id": p.id,
                "code": p.code,
                "cliente": p.cliente_nombre,
                "responsable": p.responsable.full_name,
                "fecha_limite": p.fecha_limite,
            }
            for p in sin_decidir[:LIST_LIMIT]
        ],
    }


def coordinacion(db: Session, actor: User | None = None) -> dict[str, Any]:
    v = ventana()
    leads = leads_summary(db, v)
    citas = citas_summary(db, v)
    caps = captaciones_summary(db, v)
    eq = equipo(db, v)
    preop = preop_service.hoy_resumen(db, actor) if actor is not None else None
    ped = pedidos_summary(db, v)
    out = alertas(leads, citas, caps, eq) + [
        {
            "nivel": "bad",
            "titulo": f"Pedido {x['code']} vencido · {x['responsable']}",
            "detalle": f"{x['cliente']} · venció {fechas.fmt(x['fecha_limite'])} · podría perderse",
            "que_hacer": "Hablar con el responsable: extender la fecha o marcarlo perdido.",
            "link": "/pedidos",
            "accion": "Ver pedidos",
        }
        for x in ped["lista_sin_decidir"]
    ]
    if preop:
        out = sorted(out + _alertas_preop(preop), key=lambda a: {"bad": 0, "warn": 1}[a["nivel"]])
    return {
        "generado_at": v.now,
        "leads": leads,
        "citas": citas,
        "captaciones": caps,
        "equipo": eq,
        "preoperacional": preop,
        "pedidos": ped,
        "alertas": out,
    }


def _alertas_preop(p: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    if p["sin_realizar"]:
        n = p["sin_realizar"]
        quien = "persona no ha" if n == 1 else "personas no han"
        out.append(
            {
                "nivel": "warn",
                "titulo": f"{n} {quien} realizado el preoperacional",
                "detalle": " · ".join(p["faltan"][:5]),
                "que_hacer": "Recordarles que lo hagan hoy: si no, baja su nota del mes.",
                "link": "/preoperacionales",
                "accion": "Ver preoperacionales",
            }
        )
    if n := p["novedades_sin_revisar"]:
        out.append(
            {
                "nivel": "warn",
                "titulo": f"{n} {'novedad' if n == 1 else 'novedades'} del preoperacional sin ver",
                "detalle": "Respuestas NO u observaciones de hoy",
                "que_hacer": "Leer la novedad, hablar con la persona y marcarla como revisada.",
                "link": "/preoperacionales",
                "accion": "Revisar",
            }
        )
    return out
