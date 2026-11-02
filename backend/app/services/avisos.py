"""Avisos (prototypes G09 «Avisos y agenda», M10 / C05 «Notificaciones», decisions G-0xx).

* **What an aviso is** (C05): what happened, what to do, until when, and a button to do it.
* **The bell only gets what asks for an action with a deadline** («Por atender»). Informative
  notices go to «Resumen del día» and don't count in the bell (decision on notifications).
* **No aviso repeats**: each system aviso has a `clave` (the event) unique per person.
* **Generated from the other modules** when the person opens the page or the bell polls
  (`sincronizar`). Each generator returns what is pending *now*; a system aviso whose event is
  gone (the lead got a responsable, the cita was accepted…) is closed on its own as «Resuelto»,
  except the weekly area check, which Gerencia closes.
* **Gerencia** (G09): the weekly check of each area of the company, which warns only when one is
  below 60 %, plus what waits for Gerencia (salaries, commissions, Coordinador's GPS).
* **Comunicados** (not in the prototypes, requested): Gerencia sends to any cargo, Coordinación to
  asesores and Atención y Preventa. «Alta» goes to «Por atender»; «normal» to «Resumen del día».
  Opening it marks it read: the sender sees who read it.
* **Agenda** lives in app.services.agenda; «Actividad asignada» avisos come from it.
"""

from __future__ import annotations

import calendar
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AgendaItem,
    Aviso,
    AvisoNota,
    Bono,
    Captacion,
    Cita,
    Comision,
    Comunicado,
    ConfigSeccion,
    Lead,
    LiquidacionSalario,
    Movimiento,
    Novedad,
    Preoperacional,
    User,
)
from app.models.enums import (
    ETAPAS_CERRADAS,
    Cargo,
    EstadoCaptacion,
    EstadoCita,
    EstadoCompensacion,
    EstadoMovimiento,
    EstadoNovedad,
    EstadoSalario,
    TipoNovedad,
)
from app.services import configuracion, fechas
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError
from app.services.policies import LEAD_FUNCIONES, has_commercial_activity

AUDIENCIAS = {
    "gerencia": "Gerencia",
    "coordinacion": "Coordinación",
    "asesores": "Asesores",
    "atencion": "Atención y Preventa",
    "auxiliar": "Auxiliar administrativa",
}
AUDIENCIA_COORDINACION = ("asesores", "atencion")
MAX_POR_TIPO = 15  # a generator never floods the bell
MESES = fechas._MESES


# ---------------------------------------------------------------- who


def roles(u: User) -> set[str]:
    out = set()
    if u.cargo == Cargo.GERENCIA:
        out.add("gerencia")
    if u.cargo == Cargo.COORDINACION:
        out.add("coordinacion")
    if u.cargo == Cargo.AUXILIAR_ADMINISTRATIVA:
        out.add("auxiliar")
    if u.funcion in LEAD_FUNCIONES:
        out.add("atencion")
    if has_commercial_activity(u):
        out.add("asesores")
    return out


def puede_comunicar(u: User) -> bool:
    return u.is_active and u.cargo in (Cargo.GERENCIA, Cargo.COORDINACION)


def audiencias_de(u: User) -> dict[str, str]:
    if u.cargo == Cargo.GERENCIA:
        return AUDIENCIAS
    if u.cargo == Cargo.COORDINACION:
        return {k: AUDIENCIAS[k] for k in AUDIENCIA_COORDINACION}
    return {}


# ---------------------------------------------------------------- generators


@dataclass
class Spec:
    """A system aviso as a generator sees it now."""

    clave: str
    tipo: str
    tipo_txt: str
    nivel: str
    titulo: str
    detalle: str | None = None
    que_hacer: str | None = None
    limite_at: datetime | None = None
    link: str | None = None
    accion_txt: str | None = None
    datos: list[dict[str, Any]] = field(default_factory=list)
    requiere_accion: bool = True


Gen = Callable[[Session, User, datetime], list[Spec]]
# tipo → whether its avisos close on their own when the event is gone
AUTO_RESUELVE: dict[str, bool] = {}
GENERADORES: list[tuple[set[str], str, Gen]] = []


def generador(roles_: set[str], tipo: str, auto: bool = True):
    def deco(fn: Gen) -> Gen:
        GENERADORES.append((roles_, tipo, fn))
        AUTO_RESUELVE[tipo] = auto
        return fn

    return deco


def _cuando(dt: datetime) -> str:
    return fechas.fmt(dt)


@generador({"coordinacion"}, "lead_sin_responsable")
def _lead_sin_responsable(db: Session, u: User, now: datetime) -> list[Spec]:
    """G-0xx: past the minutes Gerencia sets, Coordinación gets one aviso per lead."""
    mins = configuracion.get(db, "automatizaciones")["lead_sin_responsable_min"]
    leads = db.scalars(
        select(Lead)
        .where(
            Lead.assigned_to_id.is_(None),
            Lead.etapa.not_in(tuple(ETAPAS_CERRADAS)),
            Lead.created_at < now - timedelta(minutes=mins),
        )
        .order_by(Lead.created_at.desc())
        .limit(MAX_POR_TIPO)
    ).unique()
    return [
        Spec(
            clave=f"lead_sin_responsable:{ld.id}",
            tipo="lead_sin_responsable",
            tipo_txt="Lead sin responsable",
            nivel="warn",
            titulo=f"El lead {ld.code} lleva más de {mins} min sin responsable",
            detalle=f"{ld.full_name}"
            + (f" · {ld.busca}" if ld.busca else "")
            + f" · llegó {_cuando(ld.created_at)}.",
            que_hacer="Asígnalo o pide a Atención y Preventa que lo tome.",
            link=f"/leads/{ld.id}",
            accion_txt="Asignar el lead",
        )
        for ld in leads
    ]


@generador({"atencion"}, "lead_nuevo")
def _lead_nuevo(db: Session, u: User, now: datetime) -> list[Spec]:
    """C05 «Nuevo lead»: llegó y no tiene responsable."""
    leads = db.scalars(
        select(Lead)
        .where(
            Lead.assigned_to_id.is_(None),
            Lead.etapa.not_in(tuple(ETAPAS_CERRADAS)),
            Lead.created_at >= now - timedelta(days=3),
        )
        .order_by(Lead.created_at.desc())
        .limit(MAX_POR_TIPO)
    ).unique()
    return [
        Spec(
            clave=f"lead_nuevo:{ld.id}",
            tipo="lead_nuevo",
            tipo_txt="Nuevo lead",
            nivel="info",
            titulo=f"Llegó el lead {ld.code} y no tiene responsable",
            detalle=f"{ld.full_name}" + (f" · {ld.busca}" if ld.busca else ""),
            que_hacer="Tómalo con «Seguir lead» y registra cómo lo atendiste.",
            link=f"/leads/{ld.id}",
            accion_txt="Ver el lead",
        )
        for ld in leads
    ]


@generador({"asesores"}, "cita_por_aceptar")
def _cita_por_aceptar(db: Session, u: User, now: datetime) -> list[Spec]:
    citas = db.scalars(
        select(Cita)
        .where(Cita.asesor_id == u.id, Cita.estado == EstadoCita.PENDIENTE, Cita.scheduled_at > now)
        .order_by(Cita.scheduled_at)
        .limit(MAX_POR_TIPO)
    ).unique()
    return [
        Spec(
            clave=f"cita_por_aceptar:{c.id}",
            tipo="cita_por_aceptar",
            tipo_txt="Cita por aceptar",
            nivel="warn",
            titulo=f"Te asignaron la cita {c.code} · {_cuando(c.scheduled_at)}",
            detalle=f"{c.lead.full_name}" + (f" · {c.inmueble}" if c.inmueble else ""),
            que_hacer="Acéptala o recházala con el motivo.",
            limite_at=c.scheduled_at - timedelta(hours=1),
            link="/mis-citas",
            accion_txt="Ver la cita",
        )
        for c in citas
    ]


@generador({"coordinacion", "atencion"}, "cita_rechazada")
def _cita_rechazada(db: Session, u: User, now: datetime) -> list[Spec]:
    """C05 «Cita rechazada»: Coordinación sees all of them, Atención those of its leads."""
    q = select(Cita).where(Cita.estado == EstadoCita.RECHAZADA, Cita.scheduled_at > now)
    if u.cargo != Cargo.COORDINACION:
        q = q.join(Lead, Lead.id == Cita.lead_id).where(Lead.assigned_to_id == u.id)
    citas = db.scalars(q.order_by(Cita.scheduled_at).limit(MAX_POR_TIPO)).unique()
    return [
        Spec(
            clave=f"cita_rechazada:{c.id}",
            tipo="cita_rechazada",
            tipo_txt="Cita rechazada",
            nivel="bad" if c.scheduled_at - now <= timedelta(hours=1) else "warn",
            titulo=f"El asesor rechazó la cita {c.code}. ¿Deseas tomar acción?",
            detalle=f"{c.lead.full_name} · {_cuando(c.scheduled_at)}"
            + (f" · motivo: {c.motivo}" if c.motivo else ""),
            que_hacer="Asígnala a otro asesor, reprográmala o cancélala.",
            limite_at=c.scheduled_at,
            link="/citas",
            accion_txt="Asignar otro asesor",
        )
        for c in citas
    ]


@generador({"asesores", "coordinacion", "atencion"}, "gps_justificar")
def _gps_justificar(db: Session, u: User, now: datetime) -> list[Spec]:
    from app.services import movimientos as mov

    cfg = mov.get_config(db)
    rows = mov.pendientes_de(db, u)
    return [
        Spec(
            clave=f"gps_justificar:{m.id}",
            tipo="gps_justificar",
            tipo_txt="Justificar",
            nivel="warn",
            titulo=f"{mov.TIPO_LABELS[m.tipo]} · {_cuando(m.ocurrido_at)}",
            detalle=mov.detalle_txt(db, m, now),
            que_hacer="Justifícala: si no lo haces a tiempo o la rechazan, se descuenta 1 punto.",
            limite_at=mov.plazo_at(m, cfg),
            link="/movimientos",
            accion_txt="Justificar",
        )
        for m in rows
        if not mov.vencida(m, cfg, now)
    ][:MAX_POR_TIPO]


@generador({"coordinacion", "gerencia"}, "gps_revisar")
def _gps_revisar(db: Session, u: User, now: datetime) -> list[Spec]:
    from app.services import movimientos as mov

    rows = db.scalars(
        select(Movimiento)
        .where(Movimiento.estado == EstadoMovimiento.POR_REVISAR)
        .order_by(Movimiento.ocurrido_at)
    ).unique()
    return [
        Spec(
            clave=f"gps_revisar:{m.id}",
            tipo="gps_revisar",
            tipo_txt="Justificación por revisar",
            nivel="info",
            titulo=f"{m.empleado.full_name} justificó: {mov.TIPO_LABELS[m.tipo].lower()}",
            detalle=mov.detalle_txt(db, m, now),
            que_hacer="Apruébala o recházala (rechazada descuenta 1 punto).",
            link="/movimientos",
            accion_txt="Revisar",
        )
        for m in rows
        if mov.can_review(u, m)
    ][:MAX_POR_TIPO]


@generador({"coordinacion"}, "captacion_verificar")
def _captacion_verificar(db: Session, u: User, now: datetime) -> list[Spec]:
    caps = db.scalars(
        select(Captacion)
        .where(Captacion.estado == EstadoCaptacion.POR_VERIFICAR)
        .order_by(Captacion.enviada_at)
        .limit(MAX_POR_TIPO)
    ).unique()
    return [
        Spec(
            clave=f"captacion_verificar:{c.id}:{c.reenvios}",
            tipo="captacion_verificar",
            tipo_txt="Captación por verificar",
            nivel="warn" if now - c.enviada_at > timedelta(hours=24) else "info",
            titulo=f"Verificar la captación {c.codigo_inmueble} · {c.asesor.full_name}",
            detalle=c.direccion,
            que_hacer="Verifica el código y la dirección: solo las aprobadas suman al asesor.",
            limite_at=c.enviada_at + timedelta(hours=24),
            link=f"/captaciones/{c.id}",
            accion_txt="Verificar",
        )
        for c in caps
    ]


@generador({"coordinacion", "auxiliar"}, "plataforma_atrasada")
def _plataforma_atrasada(db: Session, u: User, now: datetime) -> list[Spec]:
    """The responsable of each late portal; Coordinación for those without one."""
    from app.services import plataformas as plat

    cfg = plat.get_config(db)
    ps = [
        p
        for p in plat.plataformas(db)
        if p.responsable_id == u.id or (p.responsable_id is None and u.cargo == Cargo.COORDINACION)
    ]
    last = plat.ultimas(db, [p.id for p in ps])
    out = []
    d = fechas.local_date(now)
    for p in ps:
        code, _, _ = plat.estado(last.get(p.id), cfg.dias_regla, d)
        if code == "al_dia":
            continue
        a = last.get(p.id)
        out.append(
            Spec(
                clave=f"plataforma_atrasada:{p.id}:{a.id if a else 'nunca'}",
                tipo="plataforma_atrasada",
                tipo_txt="Plataforma atrasada",
                nivel="warn",
                titulo=f"{p.nombre} está atrasada: última {plat.hace_txt(a, d).lower()}",
                detalle=f"Se debe actualizar al menos cada {cfg.dias_regla} días.",
                que_hacer="Registra la actualización: cupo, destacados y publicaciones activas.",
                link="/plataformas",
                accion_txt="Registrar actualización",
            )
        )
    return out


def _corte_txt(liq: LiquidacionSalario) -> str:
    return f"{'1.er' if liq.corte == 1 else '2.º'} corte de {MESES[liq.periodo.month - 1]}"


@generador({"gerencia", "auxiliar"}, "salarios")
def _salarios(db: Session, u: User, now: datetime) -> list[Spec]:
    """Auxiliar: salaries to confirm once the cut day passed. Gerencia: confirmed, to approve."""
    estado = EstadoSalario.CONFIRMADO if u.cargo == Cargo.GERENCIA else EstadoSalario.POR_CONFIRMAR
    hoy = fechas.local_date(now)
    grupos: dict[tuple[date, int], list[LiquidacionSalario]] = {}
    dias_pago = configuracion.pagos(db)
    for liq in db.scalars(
        select(LiquidacionSalario).where(LiquidacionSalario.estado == estado)
    ).unique():
        dia = dias_pago["dia_corte_1" if liq.corte == 1 else "dia_corte_2"]
        ultimo = calendar.monthrange(liq.periodo.year, liq.periodo.month)[1]
        corte_dia = liq.periodo.replace(day=min(dia, ultimo))
        if estado == EstadoSalario.POR_CONFIRMAR and hoy < corte_dia - timedelta(days=3):
            continue
        grupos.setdefault((liq.periodo, liq.corte), []).append(liq)
    out = []
    for (periodo, corte), ls in sorted(grupos.items()):
        txt = _corte_txt(ls[0])
        nombres = ", ".join(sorted(x.user.full_name.split()[0] for x in ls)[:4]) + (
            "…" if len(ls) > 4 else ""
        )
        if u.cargo == Cargo.GERENCIA:
            titulo = (
                f"La Auxiliar confirmó {len(ls)} salario{'s' if len(ls) != 1 else ''} del {txt}"
            )
            que, acc, tt = (
                "Apruébalos y regístralos como pagados.",
                "Ver salarios",
                "Salarios por aprobar",
            )
        else:
            titulo = f"{len(ls)} salario{'s' if len(ls) != 1 else ''} del {txt} por confirmar"
            que, acc, tt = (
                "Revisa las novedades y confírmalos para que Gerencia los apruebe.",
                "Confirmar salarios",
                "Salarios por confirmar",
            )
        out.append(
            Spec(
                clave=f"salarios:{estado.value}:{periodo.isoformat()}:{corte}",
                tipo="salarios",
                tipo_txt=tt,
                nivel="info",
                titulo=titulo,
                detalle=nombres,
                que_hacer=que,
                link="/salarios",
                accion_txt=acc,
            )
        )
    return out


@generador({"gerencia", "auxiliar"}, "compensacion")
def _compensacion(db: Session, u: User, now: datetime) -> list[Spec]:
    """Comisiones y bonos: visto bueno (Auxiliar) → aprobación y pago (Gerencia)."""
    E = EstadoCompensacion
    estados = (E.VISTO_BUENO, E.PENDIENTE_PAGO) if u.cargo == Cargo.GERENCIA else (E.GENERADA,)
    out = []
    for est in estados:
        items = [
            *db.scalars(select(Comision).where(Comision.estado == est)).unique(),
            *db.scalars(select(Bono).where(Bono.estado == est)).unique(),
        ]
        if not items:
            continue
        total = sum(x.valor for x in items)
        valor = "$" + f"{total:,}".replace(",", ".")
        titulo, que, tt = {
            E.GENERADA: (
                "comisiones y bonos para dar visto bueno",
                "Revísalos y dales visto bueno.",
                "Visto bueno pendiente",
            ),
            E.VISTO_BUENO: (
                "comisiones y bonos por aprobar",
                "Apruébalos para programar el pago.",
                "Comisiones por aprobar",
            ),
            E.PENDIENTE_PAGO: (
                "comisiones y bonos pendientes de pago",
                "Regístralos como pagados cuando hagas la transferencia.",
                "Comisiones por pagar",
            ),
        }[est]
        out.append(
            Spec(
                clave=f"compensacion:{est.value}:{len(items)}:{total}",
                tipo="compensacion",
                tipo_txt=tt,
                nivel="info",
                titulo=f"{len(items)} {titulo}",
                detalle=f"Total {valor}.",
                que_hacer=que,
                link="/compensacion",
                accion_txt="Ver comisiones",
            )
        )
    return out


@generador({"coordinacion"}, "preop_novedad")
def _preop_novedad(db: Session, u: User, now: datetime) -> list[Spec]:
    from app.services import preoperacional as preop

    allowed = preop.reviewer_cargos(u) or frozenset()
    rows = db.scalars(
        select(Preoperacional)
        .where(
            Preoperacional.tiene_novedad.is_(True),
            Preoperacional.revisado_at.is_(None),
            Preoperacional.fecha >= fechas.local_date(now) - timedelta(days=7),
        )
        .order_by(Preoperacional.realizado_at.desc())
    ).unique()
    return [
        Spec(
            clave=f"preop_novedad:{p.id}",
            tipo="preop_novedad",
            tipo_txt="Novedad del preoperacional",
            nivel="warn",
            titulo=f"{p.user.full_name} reportó una novedad en el preoperacional",
            detalle=(p.observaciones or "Respondió «NO» en alguna pregunta")[:200],
            que_hacer="Revísala y márcala como revisada.",
            link="/preoperacionales",
            accion_txt="Revisar",
        )
        for p in rows
        if p.user.cargo in allowed
    ][:MAX_POR_TIPO]


@generador({"gerencia"}, "novedades_mes", auto=False)
def _novedades_mes(db: Session, u: User, now: datetime) -> list[Spec]:
    """Informative (G09 «Ausencias y permisos»): goes to «Resumen del día»."""
    d = fechas.local_date(now)
    m1 = d.replace(day=1)
    rows = list(
        db.scalars(
            select(Novedad).where(
                Novedad.estado == EstadoNovedad.REGISTRADA, Novedad.desde <= d, Novedad.hasta >= m1
            )
        ).unique()
    )
    if not rows:
        return []
    from app.services import novedades as nov

    dias = nov.resumen(rows, m1, d)
    partes = [
        f"{dias[t.value]} día{'s' if dias[t.value] != 1 else ''} de {nov.TIPO_LABELS[t].lower()}"
        for t in TipoNovedad
        if dias[t.value]
    ]
    return [
        Spec(
            clave=f"novedades_mes:{m1.isoformat()}",
            tipo="novedades_mes",
            tipo_txt="Ausencias y permisos",
            nivel="warn",
            titulo=f"Se registraron {len(rows)} {'novedades' if len(rows) != 1 else 'novedad'} "
            f"en {MESES[d.month - 1]}",
            detalle=", ".join(partes) + ".",
            link="/novedades",
            accion_txt="Ver novedades",
            requiere_accion=False,
        )
    ]


@generador({"gerencia"}, "area_bajo", auto=False)
def _area_bajo(db: Session, u: User, now: datetime) -> list[Spec]:
    """G09: once a week the system checks each area of the company and warns Gerencia only when
    one is below 60 % (rojo). Uses the month so far, or the previous month during the first week
    (rendimiento has no weekly cut)."""
    year, week, _ = fechas.local_date(now).isocalendar()
    semana = f"{year}-W{week:02d}"
    if configuracion.get(db, "avisos")["semana_areas"] == semana:
        return []
    from app.services import rendimiento as rend

    row = db.get(ConfigSeccion, "avisos") or ConfigSeccion(seccion="avisos", valores={})
    row.valores = {"semana_areas": semana}
    db.add(row)
    # Early in the month there is almost nothing to measure: check the month that just ended.
    p = rend.periodo()
    if fechas.local_date(now).day <= 7:
        p = p.anterior()
    data = rend.empresa(db, u, p)
    out = []
    for a in data["areas"]:
        if a["total"] is None or a["total"] >= 60:
            continue
        peor = min(a["metas"], key=lambda m: m["pct"], default=None)
        out.append(
            Spec(
                clave=f"area_bajo:{a['key']}:{semana}",
                tipo="area_bajo",
                tipo_txt="■ Área por debajo del 60%",
                nivel="bad",
                titulo=f"El área {a['titulo']} va en {a['total']}% en {p.label}. "
                "Toma acciones o aplica estrategias.",
                detalle=f"Revisión semanal · {a['personas']}",
                que_hacer="Agrega una nota con la estrategia o agenda una acción.",
                link="/rendimiento-empresa",
                accion_txt="Ver rendimiento del área",
                datos=[
                    {
                        "lbl": "Resultado del área",
                        "val": f"{a['total']}%",
                        "sub": "Rojo · menos de 60%",
                        "rojo": True,
                    },
                    {
                        "lbl": "Lo que más la bajó",
                        "sub": f"{peor['titulo']} {peor['pct']}% "
                        f"({peor['logrado']} de {peor['meta']})"
                        if peor
                        else "Sin metas medibles",
                    },
                    {
                        "lbl": "Mes anterior",
                        "sub": f"{a['anterior']}%" if a["anterior"] is not None else "Sin datos",
                    },
                ],
            )
        )
    return out


@generador({"gerencia", "coordinacion", "auxiliar", "atencion", "asesores"}, "agenda_asignada")
def _agenda_asignada(db: Session, u: User, now: datetime) -> list[Spec]:
    """G-088: someone put an activity in your agenda. Closes once you mark it done, reject it or
    justify it (or they delete it)."""
    hoy = fechas.local_date(now)
    rows = db.scalars(
        select(AgendaItem)
        .where(
            AgendaItem.user_id == u.id,
            AgendaItem.creado_por_id != u.id,
            AgendaItem.estado == "pendiente",
            AgendaItem.eliminado_at.is_(None),
            AgendaItem.fecha >= hoy - timedelta(days=30),
        )
        .order_by(AgendaItem.fecha, AgendaItem.hora)
        .limit(MAX_POR_TIPO)
    ).unique()
    out = []
    for it in rows:
        por = it.creado_por.full_name if it.creado_por else "Alguien"
        cuando = datetime.combine(it.fecha, it.hora or time(23, 59), tzinfo=fechas.BOGOTA)
        out.append(
            Spec(
                clave=f"agenda_asignada:{it.id}",
                tipo="agenda_asignada",
                tipo_txt="Actividad asignada",
                nivel="warn" if it.prioridad == "alta" or cuando < now else "info",
                titulo=f"{por} te asignó: «{it.titulo}»",
                detalle=it.nota,
                que_hacer="Hazla y márcala hecha, o recházala o justifícala con el motivo.",
                limite_at=cuando,
                link="/avisos?tab=agenda" if u.cargo == Cargo.GERENCIA else "/agenda",
                accion_txt="Ver en mi agenda",
            )
        )
    return out


@generador({"gerencia", "auxiliar"}, "poliza_por_activar")
def _poliza_por_activar(db: Session, u: User, now: datetime) -> list[Spec]:
    """G-087: policies to activate within the insurer's deadline. The Auxiliar gets «por vencer»
    and «vencida»; Gerencia only the expired ones."""
    from app.services import polizas

    out = []
    for p, a in polizas.por_activar(db):
        if a["st"] == "o" or (u.cargo == Cargo.GERENCIA and a["st"] != "v"):
            continue
        reg = polizas.registro(p)
        vencida = a["st"] == "v"
        out.append(
            Spec(
                clave=f"poliza_por_activar:{p.id}:{a['st']}",
                tipo="poliza_por_activar",
                tipo_txt="Póliza por activar",
                nivel="bad" if vencida else "warn",
                titulo=(
                    f"Póliza vencida sin activar: {reg}"
                    if vencida
                    else f"Póliza por activar: {reg} · faltan {a['falta']} días"
                ),
                detalle=f"{p.aseguradora.nombre} · contrato firmado hace {a['dias']} días · "
                f"plazo {p.aseguradora.dias_max} días",
                que_hacer="Activa la póliza con la fecha y el número de póliza.",
                limite_at=datetime.combine(a["max"], time(23, 59), tzinfo=fechas.BOGOTA),
                link="/polizas?tab=ale",
                accion_txt="Activar póliza",
            )
        )
    return out[:MAX_POR_TIPO]


@generador({"asesores"}, "poliza_aprobada", auto=False)
def _poliza_aprobada(db: Session, u: User, now: datetime) -> list[Spec]:
    """G-034: the policy of your rental was approved; the deal goes on."""
    from app.services import polizas

    out = []
    for p in polizas.aprobadas_de(db, u, fechas.local_date(now) - timedelta(days=15)):
        out.append(
            Spec(
                clave=f"poliza_aprobada:{p.id}:{p.estudios}",
                tipo="poliza_aprobada",
                tipo_txt="Póliza aprobada",
                nivel="info",
                titulo=f"Se aprobó la póliza del arriendo {p.cierre.code}",
                detalle="El negocio sigue en proceso.",
                que_hacer="Sigue con el cliente y coordina la firma del contrato.",
                requiere_accion=False,
            )
        )
    return out[:MAX_POR_TIPO]


@generador({"asesores"}, "ruta_por_aceptar")
def _ruta_por_aceptar(db: Session, u: User, now: datetime) -> list[Spec]:
    """G-083 «Nueva ruta asignada»: accept it or reject it with a reason."""
    from app.models import Ruta
    from app.services import rutas

    rs = db.scalars(
        select(Ruta)
        .where(Ruta.asesor_id == u.id, Ruta.estado == "por_aceptar")
        .order_by(Ruta.desde)
        .limit(MAX_POR_TIPO)
    ).unique()
    return [
        Spec(
            clave=f"ruta_por_aceptar:{r.id}",
            tipo="ruta_por_aceptar",
            tipo_txt="Nueva ruta asignada",
            nivel="warn",
            titulo=f"Nueva ruta asignada: {rutas.periodo_txt(r)}",
            detalle=f"{rutas.dias_txt(r.dias)} · {rutas.zonas_txt(r.zonas)}"
            + (f" · «{r.observacion}»" if r.observacion else ""),
            que_hacer="Acéptala o recházala eligiendo el motivo y explicándolo.",
            limite_at=datetime.combine(r.desde, time(8, 0), tzinfo=fechas.BOGOTA),
            link="/rutas",
            accion_txt="Responder",
        )
        for r in rs
    ]


@generador({"coordinacion"}, "ruta_rechazada")
def _ruta_rechazada(db: Session, u: User, now: datetime) -> list[Spec]:
    """A rejected route waits to be adjusted and sent again (or left as is)."""
    from app.models import Ruta
    from app.services import rutas

    rs = db.scalars(
        select(Ruta)
        .where(Ruta.estado == "rechazada", Ruta.hasta >= fechas.local_date(now))
        .order_by(Ruta.respondida_at.desc())
        .limit(MAX_POR_TIPO)
    ).unique()
    return [
        Spec(
            clave=f"ruta_rechazada:{r.id}",
            tipo="ruta_rechazada",
            tipo_txt="Ruta rechazada",
            nivel="warn",
            titulo=f"{r.asesor.full_name} rechazó la ruta del {rutas.periodo_txt(r)}",
            detalle=f"{rutas.MOTIVOS.get(r.motivo or '', r.motivo)} · «{r.motivo_texto}»",
            que_hacer="Ajústala según el motivo y vuelve a enviarla, o cancélala.",
            link="/rutas?tab=list",
            accion_txt="Ajustar y volver a enviar",
        )
        for r in rs
    ]


@generador({"coordinacion"}, "ruta_aceptada", auto=False)
def _ruta_aceptada(db: Session, u: User, now: datetime) -> list[Spec]:
    from app.models import Ruta
    from app.services import rutas

    rs = db.scalars(
        select(Ruta).where(
            Ruta.estado == "aceptada",
            Ruta.creado_por_id == u.id,
            Ruta.respondida_at >= now - timedelta(days=7),
        )
    ).unique()
    return [
        Spec(
            clave=f"ruta_aceptada:{r.id}",
            tipo="ruta_aceptada",
            tipo_txt="Ruta aceptada",
            nivel="info",
            titulo=f"{r.asesor.full_name} aceptó la ruta del {rutas.periodo_txt(r)}",
            detalle=rutas.zonas_txt(r.zonas),
            requiere_accion=False,
        )
        for r in rs
    ][:MAX_POR_TIPO]


@generador({"asesores"}, "ruta_cancelada", auto=False)
def _ruta_cancelada(db: Session, u: User, now: datetime) -> list[Spec]:
    from app.models import Ruta
    from app.services import rutas

    rs = db.scalars(
        select(Ruta).where(
            Ruta.asesor_id == u.id,
            Ruta.estado == "cancelada",
            Ruta.motivo.is_(None),  # not a rejected one replaced by a new version
            Ruta.cancelada_at >= now - timedelta(days=7),
        )
    ).unique()
    return [
        Spec(
            clave=f"ruta_cancelada:{r.id}",
            tipo="ruta_cancelada",
            tipo_txt="Ruta cancelada",
            nivel="info",
            titulo=f"Coordinación canceló tu ruta del {rutas.periodo_txt(r)}",
            detalle=rutas.zonas_txt(r.zonas),
            requiere_accion=False,
        )
        for r in rs
    ][:MAX_POR_TIPO]


# ---------------------------------------------------------------- sync


def sincronizar(db: Session, user: User, *, now: datetime | None = None) -> None:
    """Create, refresh or close this person's system avisos from what is pending now."""
    now = now or fechas.now()
    mis_roles = roles(user)
    specs: dict[str, Spec] = {}
    corridos: set[str] = set()
    for rs, tipo, gen in GENERADORES:
        if mis_roles & rs:
            corridos.add(tipo)
            for s in gen(db, user, now):
                specs[s.clave] = s
    existentes = {
        a.clave: a
        for a in db.scalars(
            select(Aviso).where(Aviso.destinatario_id == user.id, Aviso.origen == "sistema")
        ).unique()
    }
    for clave, s in specs.items():
        a = existentes.get(clave)
        if a is None:
            a = Aviso(destinatario_id=user.id, origen="sistema", clave=clave, estado="por_atender")
            a.destinatario = user
            db.add(a)
        elif a.estado != "por_atender":
            continue
        for k in (
            "tipo",
            "tipo_txt",
            "nivel",
            "titulo",
            "detalle",
            "que_hacer",
            "limite_at",
            "link",
            "accion_txt",
            "datos",
            "requiere_accion",
        ):
            setattr(a, k, getattr(s, k))
    for clave, a in existentes.items():
        if (
            clave not in specs
            and a.estado == "por_atender"
            and a.tipo in corridos
            and AUTO_RESUELVE.get(a.tipo, True)
        ):
            a.estado, a.atendido_at, a.resuelto_auto = "atendido", now, True
    db.flush()


# ---------------------------------------------------------------- list and actions


def _visibles(db: Session, user: User):
    hoy = fechas.local_date(fechas.now())
    return (
        select(Aviso)
        .outerjoin(Comunicado, Comunicado.id == Aviso.comunicado_id)
        .where(
            Aviso.destinatario_id == user.id,
            (Comunicado.expira_el.is_(None)) | (Comunicado.expira_el >= hoy),
        )
    )


def listar(db: Session, user: User, vista: str) -> list[Aviso]:
    """vista: por_atender · atendidos · resumen (informative ones)."""
    q = _visibles(db, user)
    if vista == "por_atender":
        q = q.where(Aviso.requiere_accion.is_(True), Aviso.estado == "por_atender")
        orden = {"bad": 0, "warn": 1, "info": 2, "gray": 3}
        rows = list(db.scalars(q.order_by(Aviso.created_at.desc())).unique())
        return sorted(
            rows,
            key=lambda a: (
                orden.get(a.nivel, 9),
                a.limite_at or datetime.max.replace(tzinfo=fechas.BOGOTA),
            ),
        )
    if vista == "atendidos":
        q = q.where(Aviso.requiere_accion.is_(True), Aviso.estado == "atendido")
        return list(db.scalars(q.order_by(Aviso.atendido_at.desc()).limit(50)).unique())
    if vista == "resumen":
        desde = fechas.now() - timedelta(days=7)
        q = q.where(Aviso.requiere_accion.is_(False), Aviso.updated_at >= desde)
        return list(db.scalars(q.order_by(Aviso.created_at.desc())).unique())
    raise DomainError("Esa vista no existe.")


def conteo(db: Session, user: User) -> dict[str, int]:
    q = _visibles(db, user)
    por_atender = db.scalar(
        select(func.count()).select_from(
            q.where(Aviso.requiere_accion.is_(True), Aviso.estado == "por_atender").subquery()
        )
    )
    sin_leer = db.scalar(
        select(func.count()).select_from(
            q.where(
                Aviso.requiere_accion.is_(False),
                Aviso.leido_at.is_(None),
                Aviso.updated_at >= fechas.now() - timedelta(days=7),
            ).subquery()
        )
    )
    hoy = fechas.local_date(fechas.now())
    agenda = db.scalar(
        select(func.count()).where(
            AgendaItem.user_id == user.id,
            AgendaItem.estado == "pendiente",
            AgendaItem.eliminado_at.is_(None),
            AgendaItem.fecha <= hoy,
        )
    )
    return {
        "por_atender": por_atender or 0,
        "resumen_sin_leer": sin_leer or 0,
        "agenda_hoy": agenda or 0,
    }


def get_aviso(db: Session, user: User, id_: uuid.UUID) -> Aviso:
    a = db.get(Aviso, id_)
    if a is None or a.destinatario_id != user.id:
        raise NotFoundError("Ese aviso no existe.")
    return a


def atender(db: Session, a: Aviso, *, actor: User, nota: str | None = None) -> Aviso:
    if a.estado == "atendido":
        raise ConflictError("Este aviso ya está atendido.")
    if nota and nota.strip():
        agregar_nota(db, a, nota, actor=actor)
    now = fechas.now()
    a.estado, a.atendido_at, a.atendido_por_id, a.atendido_por = "atendido", now, actor.id, actor
    a.leido_at = a.leido_at or now
    db.flush()
    return a


def reabrir(db: Session, a: Aviso, *, actor: User) -> Aviso:
    if a.estado != "atendido":
        raise ConflictError("Este aviso no está atendido.")
    a.estado, a.atendido_at, a.atendido_por_id, a.resuelto_auto = "por_atender", None, None, False
    db.flush()
    return a


def agregar_nota(db: Session, a: Aviso, texto: str, *, actor: User) -> AvisoNota:
    texto = (texto or "").strip()
    if len(texto) < 3:
        raise DomainError("Escribe la nota.")
    n = AvisoNota(aviso_id=a.id, autor_id=actor.id, texto=texto[:1000])
    n.autor = actor
    a.notas.append(n)
    db.flush()
    return n


def marcar_leidos(db: Session, user: User, ids: list[uuid.UUID]) -> int:
    now = fechas.now()
    n = 0
    for a in db.scalars(
        select(Aviso).where(Aviso.id.in_(ids), Aviso.destinatario_id == user.id)
    ).unique():
        if a.leido_at is None:
            a.leido_at = now
            n += 1
    db.flush()
    return n


# ---------------------------------------------------------------- comunicados


def destinatarios(db: Session, audiencia: list[str], *, excepto: uuid.UUID) -> list[User]:
    us = db.scalars(select(User).where(User.is_active.is_(True))).unique()
    want = set(audiencia)
    return [u for u in us if u.id != excepto and roles(u) & want]


def enviar_comunicado(db: Session, data: dict[str, Any], *, actor: User) -> tuple[Comunicado, int]:
    if not puede_comunicar(actor):
        raise PermissionDeniedError("Los avisos generales los envían Gerencia y Coordinación.")
    titulo = (data.get("titulo") or "").strip()
    cuerpo = (data.get("cuerpo") or "").strip()
    if len(titulo) < 3 or len(cuerpo) < 3:
        raise DomainError("Escribe el título y el mensaje.")
    aud = list(dict.fromkeys(data.get("audiencia") or []))
    permitidas = audiencias_de(actor)
    if not aud:
        raise DomainError("Elige a quién va dirigido.")
    if extra := [x for x in aud if x not in permitidas]:
        raise PermissionDeniedError(
            f"No puedes enviar avisos a {AUDIENCIAS.get(extra[0], extra[0])}."
            if extra[0] in AUDIENCIAS
            else "Esa audiencia no existe."
        )
    prioridad = data.get("prioridad") or "normal"
    if prioridad not in ("normal", "alta"):
        raise DomainError("La prioridad es normal o alta.")
    expira = data.get("expira_el")
    if expira is not None and expira < fechas.local_date(fechas.now()):
        raise DomainError("La fecha de vencimiento ya pasó.")
    para = destinatarios(db, aud, excepto=actor.id)
    if not para:
        raise DomainError("No hay personas activas en esa audiencia.")
    c = Comunicado(
        titulo=titulo[:160],
        cuerpo=cuerpo[:4000],
        prioridad=prioridad,
        audiencia=aud,
        expira_el=expira,
        creado_por_id=actor.id,
    )
    c.creado_por = actor
    db.add(c)
    db.flush()
    alta = prioridad == "alta"
    for u in para:
        db.add(
            Aviso(
                destinatario_id=u.id,
                origen="comunicado",
                comunicado_id=c.id,
                tipo="comunicado",
                tipo_txt="Aviso de "
                + ("Gerencia" if actor.cargo == Cargo.GERENCIA else "Coordinación"),
                nivel="warn" if alta else "info",
                titulo=c.titulo,
                detalle=c.cuerpo,
                que_hacer="Léelo y márcalo como atendido." if alta else None,
                requiere_accion=alta,
                estado="por_atender",
            )
        )
    db.flush()
    return c, len(para)


def comunicados(db: Session, user: User) -> list[tuple[Comunicado, list[Aviso]]]:
    """Sent ones with their read receipts: Gerencia sees all, Coordinación its own."""
    if not puede_comunicar(user):
        raise PermissionDeniedError("Los avisos generales los ven Gerencia y Coordinación.")
    q = select(Comunicado).order_by(Comunicado.created_at.desc()).limit(30)
    if user.cargo != Cargo.GERENCIA:
        q = q.where(Comunicado.creado_por_id == user.id)
    out = []
    for c in db.scalars(q).unique():
        copias = list(db.scalars(select(Aviso).where(Aviso.comunicado_id == c.id)).unique())
        out.append((c, sorted(copias, key=lambda a: a.destinatario.full_name)))
    return out
