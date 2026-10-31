"""Asesor home (prototypes M01-Asesor1 / M02-Asesor2) and «Mis citas» (M03).

Only data that exists today: the asesor's citas, captaciones and activities. The cards of
the prototype that need modules not built yet (entrada/GPS, preoperacional, negocios,
pedidos, rendimiento, pagos) are left out.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Captacion, Cita, Pedido, User
from app.models.enums import (
    CITA_ACTIVA,
    ActividadComercial,
    EstadoCaptacion,
    EstadoCita,
    EstadoPedido,
    TipoCita,
    TipoNegocio,
)
from app.services import citas as cita_service
from app.services import fechas
from app.services import pedidos as pedido_service
from app.services import preoperacional as preop_service
from app.services.captaciones import MOTIVO_LABELS
from app.services.dashboard import ventana
from app.services.leads import FUENTE_LABELS

A = ActividadComercial
RECORDATORIO_ANTES = timedelta(hours=1)
TIPO_CORTO = {
    TipoCita.VISITA_ARRIENDO: "Arriendo",
    TipoCita.VISITA_VENTA: "Venta",
    TipoCita.CAPTACION: "Captación",
    TipoCita.VISITA_CONTROL: "Control",
    TipoCita.INVENTARIO: "Inventario",
    TipoCita.REUNION_ASESORIA: "Asesoría",
}
BUCKETS = ("responder", "proximas", "por_cerrar", "cerradas")


def _creator_names(db: Session, citas: list[Cita]) -> dict:
    ids = {c.created_by_id for c in citas if c.created_by_id}
    if not ids:
        return {}
    return dict(db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all())


def cita_item(c: Cita, asesor: User, db: Session, now: datetime, creators: dict) -> dict[str, Any]:
    mine = c.asesor_id == asesor.id
    return {
        "id": c.id,
        "code": c.code,
        "tipo": c.tipo,
        "estado": c.estado,
        "scheduled_at": c.scheduled_at,
        "inmueble": c.inmueble,
        "notas": c.notas,
        "motivo": c.motivo,
        "cliente": c.lead.full_name,
        "fuente": FUENTE_LABELS[c.lead.fuente],
        "programada_por": creators.get(c.created_by_id),
        "asesor_name": c.asesor_name,
        "mia": mine,
        "puede_aceptar": mine and c.estado == EstadoCita.PENDIENTE and c.scheduled_at > now,
        "puede_tomar": not mine and cita_service.disponible_para(c, asesor, db, now),
        "puede_cerrar": mine and c.estado == EstadoCita.ACEPTADA and c.scheduled_at <= now,
    }


def _bucket(c: Cita, asesor: User, now: datetime) -> str | None:
    if c.asesor_id != asesor.id:
        return "responder"  # available to take
    if c.estado == EstadoCita.PENDIENTE:
        return "responder"
    if c.estado == EstadoCita.ACEPTADA:
        return "proximas" if c.scheduled_at > now else "por_cerrar"
    if c.estado in (EstadoCita.REALIZADA, EstadoCita.CANCELADA):
        return "cerradas"
    return None  # rejected by me: no longer mine to handle


def mis_citas(db: Session, asesor: User) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """M03 lists: to answer (mine pending + rejected I can take), upcoming, to close, closed."""
    v = ventana()
    mine = list(
        db.scalars(
            select(Cita)
            .where(
                Cita.asesor_id == asesor.id,
                Cita.estado.in_(CITA_ACTIVA) | (Cita.scheduled_at >= v.mes),
            )
            .order_by(Cita.scheduled_at)
        ).unique()
    )
    others = [
        c
        for c in db.scalars(
            select(Cita)
            .where(
                Cita.estado == EstadoCita.RECHAZADA,
                Cita.scheduled_at > v.now,
                (Cita.asesor_id != asesor.id) | Cita.asesor_id.is_(None),
            )
            .order_by(Cita.scheduled_at)
        ).unique()
        if cita_service.disponible_para(c, asesor, db, v.now)
    ]
    creators = _creator_names(db, mine + others)
    out: dict[str, list[dict]] = {b: [] for b in BUCKETS}
    for c in mine + others:
        if (b := _bucket(c, asesor, v.now)) is not None:
            out[b].append(cita_item(c, asesor, db, v.now, creators))
    out["cerradas"].reverse()
    out["responder"].sort(key=lambda x: x["scheduled_at"])
    return out, {b: len(items) for b, items in out.items()}


def _cap_summary(db: Session, asesor: User, v) -> dict[str, Any]:
    counts = dict.fromkeys([e.value for e in EstadoCaptacion], 0)
    aprob_mes = {TipoNegocio.VENTA.value: 0, TipoNegocio.ARRIENDO.value: 0}
    publicadas_mes = 0
    for estado, negocio, n, n_mes, pub_mes in db.execute(
        select(
            Captacion.estado,
            Captacion.negocio,
            func.count(),
            func.count().filter(Captacion.verificado_at >= v.mes),
            func.count().filter(Captacion.publicada_at >= v.mes),
        )
        .where(Captacion.asesor_id == asesor.id)
        .group_by(Captacion.estado, Captacion.negocio)
    ):
        estado = EstadoCaptacion(estado)
        counts[estado.value] += n
        if estado == EstadoCaptacion.APROBADA:
            aprob_mes[TipoNegocio(negocio).value] += n_mes
            publicadas_mes += pub_mes
    sin_publicar = list(
        db.scalars(
            select(Captacion)
            .where(
                Captacion.asesor_id == asesor.id,
                Captacion.estado == EstadoCaptacion.APROBADA,
                Captacion.publicada_at.is_(None),
            )
            .order_by(Captacion.verificado_at)
        ).unique()
    )
    rechazadas = list(
        db.scalars(
            select(Captacion)
            .where(Captacion.asesor_id == asesor.id, Captacion.estado == EstadoCaptacion.RECHAZADA)
            .order_by(Captacion.verificado_at.desc())
        ).unique()
    )
    return {
        "counts": counts,
        "aprobadas_venta_mes": aprob_mes["venta"],
        "aprobadas_arriendo_mes": aprob_mes["arriendo"],
        "publicadas_mes": publicadas_mes,
        "sin_publicar": len(sin_publicar),
        "_sin_publicar": sin_publicar,
        "_rechazadas": rechazadas,
    }


def _citas_mes(citas_mes: list[Cita], tipos: set[TipoCita], now: datetime) -> dict[str, int]:
    rows = [c for c in citas_mes if c.tipo in tipos and c.estado != EstadoCita.CANCELADA]
    return {
        "citas": len(rows),
        "realizadas": sum(1 for c in rows if c.estado == EstadoCita.REALIZADA),
        "proximas": sum(
            1 for c in rows if c.estado == EstadoCita.ACEPTADA and c.scheduled_at > now
        ),
        "por_responder": sum(1 for c in rows if c.estado == EstadoCita.PENDIENTE),
    }


def inicio(db: Session, asesor: User) -> dict[str, Any]:
    v = ventana()
    citas_lists, citas_counts = mis_citas(db, asesor)
    acts = set(asesor.actividades)
    capta = A.CAPTACION in acts

    # ---- «Mis pendientes y recordatorios» (M01), most urgent first
    pend: list[dict[str, Any]] = []
    for c in citas_lists["responder"]:
        cuando = fechas.fmt(c["scheduled_at"])
        if c["mia"]:
            por = f" · te la asignó {c['programada_por']}" if c["programada_por"] else ""
            pend.append(
                {
                    "orden": 0,
                    "titulo": "Cita pendiente de aceptación",
                    "detalle": f"{c['code']} · {TIPO_CORTO[c['tipo']]} · {cuando}{por}",
                    "cls": "warn",
                    "chip": "Aceptar",
                    "link": "/mis-citas",
                    "cita_id": c["id"],
                }
            )
        else:
            quien = c["asesor_name"] or "Un asesor"
            pend.append(
                {
                    "orden": 1,
                    "titulo": "Cita disponible para tomar",
                    "detalle": f"{quien} rechazó {c['code']} · {TIPO_CORTO[c['tipo']]} · {cuando}. "
                    "¿Deseas tomarla?",
                    "cls": "warn",
                    "chip": "Tomar",
                    "link": "/mis-citas",
                    "cita_id": c["id"],
                }
            )
    for c in citas_lists["por_cerrar"]:
        pend.append(
            {
                "orden": 2,
                "titulo": f"Cita {c['code']} por cerrar",
                "detalle": f"{fechas.fmt(c['scheduled_at'])} · {c['cliente']} · "
                "cuenta qué pasó en la visita",
                "cls": "warn",
                "chip": "Cerrar",
                "link": "/mis-citas",
                "cita_id": c["id"],
            }
        )
    for c in citas_lists["proximas"]:
        pronto = c["scheduled_at"] - v.now <= RECORDATORIO_ANTES
        if pronto or c["scheduled_at"] < v.manana + timedelta(days=1):
            inm = f" · {c['inmueble']}" if c["inmueble"] else ""
            pend.append(
                {
                    "orden": 3 if pronto else 5,
                    "titulo": "Recordatorio: cita en 1 hora" if pronto else "Recordatorio de cita",
                    "detalle": f"{fechas.fmt(c['scheduled_at'])} · {TIPO_CORTO[c['tipo']]}{inm} "
                    f"· {c['cliente']}",
                    "cls": "info" if pronto else "ok",
                    "chip": "Ver" if pronto else "Aceptada",
                    "link": "/mis-citas",
                    "cita_id": c["id"],
                }
            )

    cap = _cap_summary(db, asesor, v) if capta else None
    if cap:
        for k in cap.pop("_rechazadas"):
            mot = MOTIVO_LABELS[k.motivo_rechazo].capitalize() if k.motivo_rechazo else "Rechazada"
            pend.append(
                {
                    "orden": 2,
                    "titulo": f"Captación {k.code} rechazada",
                    "detalle": f"{mot} · corrige y vuelve a enviar",
                    "cls": "bad",
                    "chip": "Corregir",
                    "link": f"/captaciones/{k.id}",
                    "captacion_id": k.id,
                }
            )
        for k in cap.pop("_sin_publicar"):
            pend.append(
                {
                    "orden": 4,
                    "titulo": f"Captación {k.code} aprobada",
                    "detalle": f"{k.codigo_inmueble} · márcala publicada cuando ya esté en línea",
                    "cls": "info",
                    "chip": "Publicar",
                    "link": f"/captaciones/{k.id}",
                    "captacion_id": k.id,
                }
            )
    for pe in db.scalars(
        select(Pedido)
        .where(Pedido.responsable_id == asesor.id, Pedido.estado == EstadoPedido.ABIERTO)
        .order_by(Pedido.fecha_limite)
    ).unique():
        neg = "Venta" if pe.negocio == TipoNegocio.VENTA else "Arriendo"
        if pedido_service.vencido(pe, v.now):
            pend.append(
                {
                    "orden": 1,
                    "titulo": f"Pedido {pe.code} vencido",
                    "detalle": f"{pe.cliente_nombre} · {neg} · {pe.zona} · extender o perdido",
                    "cls": "bad",
                    "chip": "Decidir",
                    "link": "/pedidos",
                }
            )
        elif pe.fecha_limite < v.manana:
            pend.append(
                {
                    "orden": 1,
                    "titulo": f"Pedido {pe.code} vence hoy {fechas.fmt(pe.fecha_limite)[-5:]}",
                    "detalle": f"{neg} · {pe.cliente_nombre}",
                    "cls": "bad",
                    "chip": "Urgente",
                    "link": "/pedidos",
                }
            )
        elif pedido_service.proximo_a_vencer(pe, v.now):
            pend.append(
                {
                    "orden": 4,
                    "titulo": f"Pedido {pe.code} vence {fechas.fmt(pe.fecha_limite)}",
                    "detalle": f"{neg} · {pe.cliente_nombre}",
                    "cls": "warn",
                    "chip": "Por vencer",
                    "link": "/pedidos",
                }
            )
    pend.sort(key=lambda p: p["orden"])
    for p in pend:
        p.pop("orden")

    # ---- «Mis resultados de <mes>» per active activity (M01 tabs)
    citas_mes = list(
        db.scalars(
            select(Cita).where(Cita.asesor_id == asesor.id, Cita.scheduled_at >= v.mes)
        ).unique()
    )
    resultados: dict[str, dict[str, int]] = {}
    if capta and cap:
        resultados["captacion"] = {
            "aprobadas_venta": cap["aprobadas_venta_mes"],
            "aprobadas_arriendo": cap["aprobadas_arriendo_mes"],
            "por_verificar": cap["counts"]["por_verificar"],
            "publicadas": cap["publicadas_mes"],
        }
    if A.VENTAS in acts:
        resultados["ventas"] = _citas_mes(
            citas_mes, {TipoCita.VISITA_VENTA, TipoCita.REUNION_ASESORIA}, v.now
        )
    if A.ARRIENDOS in acts:
        resultados["arriendos"] = _citas_mes(citas_mes, {TipoCita.VISITA_ARRIENDO}, v.now)

    hoy = [
        c
        for b in ("responder", "proximas", "por_cerrar", "cerradas")
        for c in citas_lists[b]
        if c["mia"] and v.hoy <= c["scheduled_at"] < v.manana
    ]
    hoy.sort(key=lambda c: c["scheduled_at"])
    pre_hoy = preop_service.get_de_hoy(db, asesor)
    return {
        "preoperacional": {
            "activo": preop_service.activo_para(db, asesor),
            "realizado_at": pre_hoy.realizado_at if pre_hoy else None,
            "tiene_novedad": bool(pre_hoy and pre_hoy.tiene_novedad),
        },
        "asesor": {
            "id": asesor.id,
            "full_name": asesor.full_name,
            "cargo": asesor.cargo,
            "actividades": asesor.actividades,
            "gps_checkin_enabled": asesor.gps_checkin_enabled,
        },
        "pendientes": pend,
        "citas_hoy": hoy,
        "citas_counts": citas_counts,
        "captaciones": cap,
        "resultados": resultados,
    }
