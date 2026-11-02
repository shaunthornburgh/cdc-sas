"""Rendimiento: the month's result per person, team and company (K07, K14, K18, M08, C04, G12).

How the result is calculated (prototype v143 · DECISIONS G-0xx):

* **Result** = Σ (cumplimiento of each area × its weight) + ajustes − descuentos, shown between
  0 and 100. One point = 1 % of the month's result.
* **Cumplimiento** of an area = logrado ÷ meta, capped at 100 %. An area «cumple» at 100 %.
* **Areas without data** (their module doesn't exist yet, or there is nothing to measure this month)
  don't count: the result is calculated over the weight of the areas that do have data, and the
  screen says so.
* **Calificaciones (1 a 5)** have no weight: each 2 or 1 takes off 5 points. The preoperacional is
  a rating calculated by the system (preoperacional.puntaje). Puntualidad needs «Marcar entrada»,
  which doesn't exist yet, so it is shown without data.
* **Atención y Preventa**: each lead ganado adds 1 point; each lead perdido that «descuenta»
  (leads.perdida_descuenta) takes off 0.5. Gerencia changes both in Configuración.
* **Semáforo**: verde 80–100 · amarillo 70–79 · naranja 60–69 · rojo < 60.
* Nobody adds or removes points by hand: numbers come from what each person registers.

What counts in each area, and how it avoids counting twice, is in the ``AREAS`` descriptions.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Calificacion,
    Captacion,
    Cita,
    Lead,
    LeadEvento,
    Pedido,
    RendimientoCambio,
    RendimientoConfig,
    Seguimiento,
    User,
)
from app.models.enums import (
    ActividadComercial,
    Cargo,
    EstadoCaptacion,
    EstadoCita,
    EstadoPedido,
    EtapaLead,
    TipoCita,
    TipoEventoLead,
    TipoNegocio,
)
from app.services import configuracion, fechas, movimientos, plataformas
from app.services import preoperacional as preop
from app.services.errors import DomainError, NotFoundError, PermissionDeniedError
from app.services.leads import ETAPA_LABELS, MOTIVO_LABELS
from app.services.pedidos import MOTIVO_LABELS as MOTIVO_PEDIDO_LABELS
from app.services.policies import LEAD_FUNCIONES, has_commercial_activity

DESCUENTO_CALIFICACION = 5  # points off for each rating of 2 or 1
SEGUIMIENTO_MARGEN = timedelta(minutes=30)  # «a tiempo»: done up to 30 min after its time
VERIFICACION_PLAZO = timedelta(hours=24)  # Coordinación verifies a captación within 24 h
CITAS_DE_CLIENTE = (TipoCita.VISITA_ARRIENDO, TipoCita.VISITA_VENTA, TipoCita.REUNION_ASESORIA)
MESES = (
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre"
).split()


# ---------------------------------------------------------------- areas


@dataclass(frozen=True)
class AreaDef:
    key: str
    titulo: str
    descripcion: str  # what counts
    meta_default: int | None  # None: no configurable goal
    unidad: tuple[str, str] = ("", "")  # singular, plural (for «1 venta» / «13 arriendos»)
    que_hacer: str = ""
    link: str = ""


AREAS: dict[str, AreaDef] = {
    a.key: a
    for a in (
        # ---- Asesores
        AreaDef(
            "ventas",
            "Ventas",
            "Leads de venta marcados «Ganado» este mes cuya última cita realizada fue tuya. "
            "Cuenta una vez, cuando Coordinación o Gerencia confirma el cierre.",
            1,
            ("venta", "ventas"),
            "Revisa tus clientes de venta con cita realizada y los pedidos de venta abiertos.",
            "/pedidos",
        ),
        AreaDef(
            "arriendos",
            "Arriendos",
            "Leads de arriendo marcados «Ganado» este mes cuya última cita realizada fue tuya.",
            3,
            ("arriendo", "arriendos"),
            "Revisa los pedidos de arriendo abiertos y agenda visitas esta semana.",
            "/pedidos",
        ),
        AreaDef(
            "captacion",
            "Captación",
            "Captaciones aprobadas por Coordinación este mes. Las rechazadas no cuentan hasta que "
            "se corrigen y se aprueban; un código ya registrado no se puede volver a enviar.",
            10,
            ("captación", "captaciones"),
            "Completa las captaciones pendientes y corrige las que Coordinación devolvió.",
            "/captaciones",
        ),
        # ---- Atención y Preventa
        AreaDef(
            "leads_gestionados",
            "Leads gestionados",
            "Leads distintos en los que registraste al menos una acción este mes.",
            30,
            ("lead", "leads"),
            "Atiende primero los leads nuevos del día.",
            "/leads",
        ),
        AreaDef(
            "llamadas",
            "Llamadas",
            "Llamadas registradas en el historial de tus leads este mes.",
            45,
            ("llamada", "llamadas"),
            "Haz las llamadas de seguimiento en la mañana.",
            "/leads",
        ),
        AreaDef(
            "seguimientos",
            "Seguimientos a tiempo",
            "Seguimientos que programaste con hora en este mes y que marcaste como realizados a "
            "más tardar 30 minutos después. Los cancelados porque el lead se cerró no cuentan.",
            None,
            ("seguimiento", "seguimientos"),
            "Revisa tus seguimientos al empezar el día y márcalos al hacerlos.",
            "/leads",
        ),
        AreaDef(
            "citas_programadas",
            "Citas programadas",
            "Citas con cliente (visita de venta, de arriendo o reunión de asesoría) que "
            "programaste este mes. Visitas de control e inventarios no cuentan.",
            12,
            ("cita", "citas"),
            "Ofrece dos horarios al cliente en la misma llamada.",
            "/citas",
        ),
        AreaDef(
            "citas_realizadas",
            "Citas realizadas",
            "De las citas que programaste este mes, las que el asesor marcó como realizadas.",
            10,
            ("cita", "citas"),
            "Confirma cada cita el día anterior y avisa al asesor si el cliente cambia la hora.",
            "/citas",
        ),
        AreaDef(
            "conversion",
            "Conversión lead → cita",
            "Citas programadas ÷ leads gestionados del mes. La meta es un porcentaje.",
            40,
            ("%", "%"),
            "Sigue el guion de calificación y propone la cita en la primera llamada.",
            "/leads",
        ),
        AreaDef(
            "cierres",
            "Cierres",
            "Leads a tu cargo marcados «Ganado» este mes.",
            5,
            ("lead ganado", "leads ganados"),
            "Llama a los clientes con cita realizada que no han respondido.",
            "/leads",
        ),
        # ---- Coordinación
        AreaDef(
            "equipo",
            "Resultados del equipo",
            "Promedio del resultado de los asesores y de Atención y Preventa: si el equipo baja, "
            "tu resultado baja; si sube, sube.",
            None,
            que_hacer="Revisa con las personas en rojo o naranja sus áreas más bajas.",
            link="/equipo",
        ),
        AreaDef(
            "monitoreo",
            "Monitoreo y seguimiento",
            "Por ahora: captaciones enviadas este mes que Coordinación verificó en menos de 24 "
            "horas. Qué más cuenta aquí está PENDIENTE DE CONFIGURACIÓN.",
            None,
            ("captación", "captaciones"),
            "Verifica las captaciones el mismo día en que llegan.",
            "/captaciones",
        ),
        AreaDef(
            "plataformas",
            "Actualización de plataformas",
            "Días del mes en que las plataformas que tiene asignadas estuvieron al día "
            "(actualizadas dentro de la regla de días que define Gerencia).",
            None,
            link="/plataformas",
        ),
        AreaDef(
            "rutas",
            "Rutas del equipo",
            "Las crea el Coordinador y Gerencia las califica de 1 a 5 (4 de 5 = 80 %).",
            None,
        ),
    )
}
SIN_MODULO: dict[str, str] = {}
AREAS_ASESOR = (
    ("ventas", ActividadComercial.VENTAS),
    ("arriendos", ActividadComercial.ARRIENDOS),
    ("captacion", ActividadComercial.CAPTACION),
)
AREAS_ATENCION = (
    "leads_gestionados",
    "llamadas",
    "seguimientos",
    "citas_programadas",
    "citas_realizadas",
    "conversion",
    "cierres",
)
AREAS_COORDINACION = ("equipo", "monitoreo", "plataformas", "rutas")
PESOS_ATENCION = dict(zip(AREAS_ATENCION, (10, 10, 15, 15, 15, 20, 15), strict=True))
PESOS_COORDINACION = dict(zip(AREAS_COORDINACION, (50, 15, 20, 15), strict=True))
PESOS_ASESOR = {1: (100,), 2: (50, 50), 3: (50, 30, 20)}


# ---------------------------------------------------------------- calificaciones (1 a 5)


@dataclass(frozen=True)
class IndicadorDef:
    key: str
    titulo: str
    que_hacer: str
    solo_asesores: bool = False


INDICADORES = (
    IndicadorDef("actitud", "Actitud y compromiso", "Habla con tu coordinador sobre qué mejorar."),
    IndicadorDef(
        "puesto", "Puesto de trabajo ordenado", "Deja tu puesto ordenado al terminar el día."
    ),
    IndicadorDef(
        "uniforme",
        "Correcto uso del uniforme",
        "Usa el uniforme completo todos los días: con 2 o menos se descuentan 5 puntos.",
    ),
    IndicadorDef(
        "material",
        "Material de trabajo",
        "Sal con el material completo: carpeta, formatos, llaves y metro.",
        solo_asesores=True,
    ),
    IndicadorDef("carne", "Carné", "Lleva el carné visible durante la jornada."),
    IndicadorDef(
        "bateria",
        "Batería del teléfono",
        "Sal con el celular cargado y lleva cargador: lo necesitas para el GPS y las citas.",
    ),
)
INDICADOR_KEYS = {i.key: i for i in INDICADORES}


# ---------------------------------------------------------------- who is measured, and by whom


def perfil(user: User) -> str | None:
    """asesor · atencion · coordinacion, or None (Gerencia and Auxiliar have no result yet)."""
    if not user.is_active:
        return None
    if user.cargo == Cargo.COORDINACION:
        return "coordinacion"
    if user.funcion in LEAD_FUNCIONES:
        return "atencion"
    if has_commercial_activity(user):
        return "asesor"
    return None


def cargo_txt(user: User) -> str:
    p = perfil(user)
    if p == "coordinacion":
        return "Coordinador"
    if p == "atencion":
        return "Atención y Preventa"
    acts = [t for k, a in AREAS_ASESOR if user.has_actividad(a) for t in [AREAS[k].titulo]]
    return "Asesor · " + " + ".join(acts)


def area_keys(user: User) -> list[str]:
    p = perfil(user)
    if p == "asesor":
        return [k for k, act in AREAS_ASESOR if user.has_actividad(act)]
    if p == "atencion":
        return list(AREAS_ATENCION)
    if p == "coordinacion":
        return list(AREAS_COORDINACION)
    return []


def indicadores_de(user: User) -> list[IndicadorDef]:
    asesor = perfil(user) == "asesor"
    return [i for i in INDICADORES if asesor or not i.solo_asesores]


def can_view(viewer: User, target: User) -> bool:
    p = perfil(target)
    if p is None:
        return False
    if viewer.id == target.id or viewer.cargo in (Cargo.GERENCIA, Cargo.AUXILIAR_ADMINISTRATIVA):
        return True
    return viewer.cargo == Cargo.COORDINACION and p in ("asesor", "atencion")


def can_rate(viewer: User, target: User) -> bool:
    """Asesores and Atención: only Coordinación. The Coordinador: the Auxiliar or Gerencia."""
    if viewer.id == target.id:
        return False
    p = perfil(target)
    if p in ("asesor", "atencion"):
        return viewer.cargo == Cargo.COORDINACION
    if p == "coordinacion":
        return viewer.cargo in (Cargo.AUXILIAR_ADMINISTRATIVA, Cargo.GERENCIA)
    return False


def can_configure(viewer: User, target: User) -> bool:
    """Weights and goals: asesores → Coordinación or Gerencia; Atención, Coordinador → Gerencia."""
    if viewer.id == target.id:
        return False
    p = perfil(target)
    if p == "asesor":
        return viewer.cargo in (Cargo.COORDINACION, Cargo.GERENCIA)
    return p is not None and viewer.cargo == Cargo.GERENCIA


def can_see_team(viewer: User) -> bool:
    return viewer.cargo in (Cargo.COORDINACION, Cargo.GERENCIA, Cargo.AUXILIAR_ADMINISTRATIVA)


def team(db: Session, viewer: User) -> list[User]:
    """Coordinación: asesores and Atención · Gerencia and the Auxiliar: also the Coordinador."""
    if not can_see_team(viewer):
        raise PermissionDeniedError("No tienes acceso al rendimiento del equipo.")
    perfiles = ("asesor", "atencion") if viewer.cargo == Cargo.COORDINACION else None
    users = db.scalars(select(User).where(User.is_active).order_by(User.full_name)).unique()
    return [u for u in users if (p := perfil(u)) and (perfiles is None or p in perfiles)]


def get_target(db: Session, viewer: User, user_id: uuid.UUID) -> User:
    target = db.get(User, user_id)
    if target is None or perfil(target) is None:
        raise NotFoundError("Esa persona no tiene rendimiento.")
    if not can_view(viewer, target):
        raise PermissionDeniedError("No puedes ver el rendimiento de esta persona.")
    return target


# ---------------------------------------------------------------- periods


@dataclass(frozen=True)
class Periodo:
    first: date
    last: date

    @property
    def key(self) -> str:
        return self.first.strftime("%Y-%m")

    @property
    def label(self) -> str:
        return f"{MESES[self.first.month - 1]} {self.first.year}"

    @property
    def mes(self) -> str:
        return MESES[self.first.month - 1]

    @property
    def start(self) -> datetime:
        return fechas.start_of_day(self.first)

    @property
    def end(self) -> datetime:
        return fechas.start_of_day(self.last + timedelta(days=1))

    @property
    def en_curso(self) -> bool:
        return self.start <= fechas.now() < self.end

    @property
    def hasta(self) -> datetime:
        return min(self.end, fechas.now())

    def anterior(self) -> Periodo:
        return periodo((self.first - timedelta(days=1)).strftime("%Y-%m"))

    def siguiente_first(self) -> date:
        return self.last + timedelta(days=1)


def periodo(mes: str | None = None) -> Periodo:
    first, last = preop.mes_bounds(mes)
    if first > fechas.local_date(fechas.now()):
        raise DomainError("Ese mes todavía no empieza.")
    return Periodo(first, last)


def semaforo(r: float | None) -> str | None:
    if r is None:
        return None
    if r >= 80:
        return "verde"
    if r >= 70:
        return "amarillo"
    if r >= 60:
        return "naranja"
    return "rojo"


def _pct(logrado: float, meta: float) -> int:
    return min(100, round(100 * logrado / meta)) if meta else 0


def _n(x: float) -> str:
    """1 → «1» · 39.29 → «39,3»."""
    r = round(x, 1)
    return (str(int(r)) if r == int(r) else str(r)).replace(".", ",")


def _cant(n: int, unidad: tuple[str, str]) -> str:
    return f"{n} {unidad[0] if n == 1 else unidad[1]}".strip()


# ---------------------------------------------------------------- config (weights and goals)


def default_pesos(user: User) -> dict[str, int]:
    keys = area_keys(user)
    p = perfil(user)
    if p == "atencion":
        return dict(PESOS_ATENCION)
    if p == "coordinacion":
        return dict(PESOS_COORDINACION)
    return dict(zip(keys, PESOS_ASESOR.get(len(keys), ()), strict=False))


def _row(db: Session, user_id: uuid.UUID, first: date) -> RendimientoConfig | None:
    return db.scalar(
        select(RendimientoConfig)
        .where(RendimientoConfig.user_id == user_id, RendimientoConfig.periodo <= first)
        .order_by(RendimientoConfig.periodo.desc())
        .limit(1)
    )


@dataclass
class Config:
    pesos: dict[str, int]
    metas: dict[str, int]
    pesos_configurados: bool
    metas_configuradas: bool


def config_de(db: Session, user: User, first: date) -> Config:
    """The row in force for that month (the latest one from that month or before)."""
    keys = area_keys(user)
    row = _row(db, user.id, first)
    saved = (row.pesos if row else {}) or {}
    ok = set(saved) == set(keys) and sum(saved.values()) == 100
    pesos = {k: int(saved[k]) for k in keys} if ok else default_pesos(user)
    saved_m = (row.metas if row else {}) or {}
    metas = {
        k: int(saved_m.get(k, AREAS[k].meta_default))
        for k in keys
        if AREAS[k].meta_default is not None
    }
    return Config(pesos, metas, ok, bool(saved_m))


def _upsert(db: Session, user: User, first: date, actor: User) -> RendimientoConfig:
    row = db.scalar(
        select(RendimientoConfig).where(
            RendimientoConfig.user_id == user.id, RendimientoConfig.periodo == first
        )
    )
    if row is None:
        cur = config_de(db, user, first)
        row = RendimientoConfig(user_id=user.id, periodo=first, pesos=cur.pesos, metas=cur.metas)
        db.add(row)
    row.updated_by_id = actor.id
    row.updated_at = fechas.now()
    return row


def _log(db: Session, user: User, tipo: str, first: date, antes: dict, despues: dict, actor: User):
    db.add(
        RendimientoCambio(
            user_id=user.id,
            tipo=tipo,
            periodo=first,
            antes=antes,
            despues=despues,
            created_by_id=actor.id,
        )
    )


def guardar_pesos(db: Session, target: User, pesos: dict[str, int], *, actor: User) -> Config:
    """Weights apply from this month on (they're also copied into goals saved for later months)."""
    if not can_configure(actor, target):
        raise PermissionDeniedError(
            "Los pesos de los asesores los configura Coordinación; los de Atención y Preventa y "
            "del Coordinador, Gerencia."
        )
    keys = area_keys(target)
    if set(pesos) != set(keys):
        raise DomainError("Pon un peso a cada área de esta persona.")
    if any(not isinstance(v, int) or v < 0 or v > 100 for v in pesos.values()):
        raise DomainError("Cada peso va de 0 % a 100 %.")
    if (total := sum(pesos.values())) != 100:
        raise DomainError(f"La suma debe ser exactamente 100 %. Ahora suma {total} %.")
    p = periodo()
    antes = config_de(db, target, p.first).pesos
    if antes == pesos:
        return config_de(db, target, p.first)
    row = _upsert(db, target, p.first, actor)
    row.pesos = dict(pesos)
    for later in db.scalars(
        select(RendimientoConfig).where(
            RendimientoConfig.user_id == target.id, RendimientoConfig.periodo > p.first
        )
    ):
        later.pesos = dict(pesos)
    _log(db, target, "pesos", p.first, antes, pesos, actor)
    db.flush()
    return config_de(db, target, p.first)


def guardar_metas(db: Session, target: User, metas: dict[str, int], *, actor: User) -> Config:
    """Goals apply from next month: this month's result keeps the goals it started with."""
    if not can_configure(actor, target):
        raise PermissionDeniedError(
            "Las metas de los asesores las configura Coordinación; las de Atención y Preventa, "
            "Gerencia."
        )
    validas = {k for k in area_keys(target) if AREAS[k].meta_default is not None}
    if not metas or not set(metas) <= validas:
        raise DomainError("Esa persona no tiene meta en esa área.")
    if any(not isinstance(v, int) or v < 1 or v > 10_000 for v in metas.values()):
        raise DomainError("Cada meta debe ser un número mayor que 0.")
    if "conversion" in metas and metas["conversion"] > 100:
        raise DomainError("La meta de conversión es un porcentaje (de 1 a 100).")
    nxt = periodo().siguiente_first()
    antes = config_de(db, target, nxt).metas
    nuevas = antes | metas
    if nuevas == antes:
        return config_de(db, target, nxt)
    row = _upsert(db, target, nxt, actor)
    row.metas = nuevas
    _log(db, target, "metas", nxt, antes, nuevas, actor)
    db.flush()
    return config_de(db, target, nxt)


def guardar_calificaciones(
    db: Session, target: User, valores: dict[str, int], *, actor: User
) -> None:
    """Ratings of the current month. The person sees them but can't change them."""
    if not can_rate(actor, target):
        raise PermissionDeniedError(
            "Las calificaciones de asesores y Atención las asigna Coordinación; las del "
            "Coordinador, la Auxiliar administrativa o Gerencia."
        )
    validos = {i.key for i in indicadores_de(target)}
    if not valores or not set(valores) <= validos:
        raise DomainError("Ese indicador no se califica a esta persona.")
    if any(not isinstance(v, int) or not 1 <= v <= 5 for v in valores.values()):
        raise DomainError("Cada calificación va de 1 a 5.")
    p = periodo()
    rows = {
        c.indicador: c
        for c in db.scalars(
            select(Calificacion).where(
                Calificacion.user_id == target.id, Calificacion.periodo == p.first
            )
        ).unique()
    }
    antes = {k: c.valor for k, c in rows.items() if k in valores}
    cambios = {k: v for k, v in valores.items() if antes.get(k) != v}
    if not cambios:
        return
    for k, v in cambios.items():
        if (c := rows.get(k)) is None:
            db.add(
                Calificacion(
                    user_id=target.id,
                    periodo=p.first,
                    indicador=k,
                    valor=v,
                    calificado_por_id=actor.id,
                )
            )
        else:
            c.valor = v
            c.calificado_por_id = actor.id
            c.updated_at = fechas.now()
    _log(
        db,
        target,
        "calificaciones",
        p.first,
        {k: antes.get(k) for k in cambios},
        cambios,
        actor,
    )
    db.flush()


def cambios(db: Session, target: User, limit: int = 30) -> list[RendimientoCambio]:
    return list(
        db.scalars(
            select(RendimientoCambio)
            .where(RendimientoCambio.user_id == target.id)
            .order_by(RendimientoCambio.created_at.desc())
            .limit(limit)
        ).unique()
    )


# ---------------------------------------------------------------- the calculation


@dataclass
class Area:
    key: str
    titulo: str
    descripcion: str
    peso: int
    meta: int | None = None
    meta_txt: str = ""
    logrado: float = 0
    logrado_txt: str = ""
    cumplimiento: int | None = None  # None = no data, doesn't count
    sin_datos: str | None = None
    falta: str = ""
    aporte: float = 0
    peso_efectivo: float = 0

    @property
    def cumple(self) -> bool:
        return self.cumplimiento is not None and self.cumplimiento >= 100


@dataclass
class Resultado:
    user: User
    periodo: Periodo
    areas: list[Area]
    por_areas: float | None
    peso_con_datos: int
    calificaciones: list[dict[str, Any]]
    descuentos: list[dict[str, Any]]
    ajustes: list[dict[str, Any]]
    avisos: list[dict[str, Any]] = field(default_factory=list)

    @property
    def puntos_descuento(self) -> float:
        return sum(d["puntos"] for d in self.descuentos)

    @property
    def puntos_ajuste(self) -> float:
        return sum(a["puntos"] for a in self.ajustes)

    @property
    def total_exacto(self) -> float | None:
        if self.por_areas is None:
            return None
        return round(self.por_areas + self.puntos_ajuste - self.puntos_descuento, 2)

    @property
    def total(self) -> int | None:
        t = self.total_exacto
        return None if t is None else max(0, min(100, round(t)))

    @property
    def metas_cumplidas(self) -> tuple[int, int]:
        con = [a for a in self.areas if a.cumplimiento is not None]
        return sum(1 for a in con if a.cumple), len(con)

    def area(self, key: str) -> Area | None:
        return next((a for a in self.areas if a.key == key), None)


class Calculo:
    """Calculates results for one month, sharing what several people need (leads ganados…)."""

    def __init__(self, db: Session, p: Periodo):
        self.db = db
        self.p = p
        self._cache: dict[uuid.UUID, Resultado] = {}
        self._ganados: list[tuple[Lead, uuid.UUID | None, TipoNegocio | None]] | None = None

    # ---- shared data

    def ganados(self) -> list[tuple[Lead, uuid.UUID | None, TipoNegocio | None]]:
        """Leads ganados this month, with the asesor of their last cita realizada."""
        if self._ganados is None:
            leads = self.db.scalars(
                select(Lead)
                .options(selectinload(Lead.citas))
                .where(
                    Lead.etapa == EtapaLead.GANADO,
                    Lead.cerrado_at >= self.p.start,
                    Lead.cerrado_at < self.p.end,
                )
            ).unique()
            out = []
            for lead in leads:
                hechas = sorted(
                    (
                        c
                        for c in lead.citas
                        if c.estado == EstadoCita.REALIZADA and c.tipo in CITAS_DE_CLIENTE
                    ),
                    key=lambda c: c.scheduled_at,
                )
                ultima = hechas[-1] if hechas else None
                negocio = lead.negocio
                if (
                    negocio is None
                    and ultima is not None
                    and ultima.tipo != TipoCita.REUNION_ASESORIA
                ):
                    negocio = (
                        TipoNegocio.VENTA
                        if ultima.tipo == TipoCita.VISITA_VENTA
                        else TipoNegocio.ARRIENDO
                    )
                out.append((lead, ultima.asesor_id if ultima else None, negocio))
            self._ganados = out
        return self._ganados

    # ---- one person

    def resultado(self, user: User) -> Resultado:
        if user.id in self._cache:
            return self._cache[user.id]
        p = perfil(user)
        if p is None:
            raise NotFoundError("Esa persona no tiene rendimiento.")
        cfg = config_de(self.db, user, self.p.first)
        areas = [
            Area(key=k, titulo=AREAS[k].titulo, descripcion=AREAS[k].descripcion, peso=cfg.pesos[k])
            for k in area_keys(user)
        ]
        for a in areas:
            a.meta = cfg.metas.get(a.key)
        ajustes: list[dict[str, Any]] = []
        if p == "asesor":
            self._asesor(user, areas)
        elif p == "atencion":
            ajustes = self._atencion(user, areas)
        else:
            self._coordinacion(user, areas)

        con = [a for a in areas if a.cumplimiento is not None and a.peso > 0]
        peso = sum(a.peso for a in con)
        for a in con:
            a.peso_efectivo = round(100 * a.peso / peso, 2)
            a.aporte = round(a.cumplimiento * a.peso / peso, 2)
        por_areas = round(sum(a.aporte for a in con), 2) if peso else None

        cal, desc, avisos = self._calificaciones(user)
        r = Resultado(user, self.p, areas, por_areas, peso, cal, desc, ajustes, avisos)
        self._cache[user.id] = r
        return r

    def _asesor(self, user: User, areas: list[Area]) -> None:
        for a in areas:
            d = AREAS[a.key]
            if a.key in ("ventas", "arriendos"):
                neg = TipoNegocio.VENTA if a.key == "ventas" else TipoNegocio.ARRIENDO
                n = sum(1 for _, ase, ng in self.ganados() if ase == user.id and ng == neg)
                a.logrado, a.logrado_txt = n, _cant(n, d.unidad)
            else:
                caps = list(
                    self.db.scalars(
                        select(Captacion).where(
                            Captacion.asesor_id == user.id,
                            Captacion.estado == EstadoCaptacion.APROBADA,
                            Captacion.verificado_at >= self.p.start,
                            Captacion.verificado_at < self.p.end,
                        )
                    ).unique()
                )
                n = len(caps)
                ven = sum(1 for c in caps if c.negocio == TipoNegocio.VENTA)
                a.logrado = n
                a.logrado_txt = f"{n} aprobada{'s' if n != 1 else ''}" + (
                    f" ({ven} venta · {n - ven} arriendo)" if n else ""
                )
            self._cumplir(a, d)

    def _atencion(self, user: User, areas: list[Area]) -> list[dict[str, Any]]:
        p, db = self.p, self.db
        evs = db.execute(
            select(LeadEvento.lead_id, LeadEvento.tipo, LeadEvento.datos).where(
                LeadEvento.created_by_id == user.id,
                LeadEvento.created_at >= p.start,
                LeadEvento.created_at < p.end,
                LeadEvento.tipo != TipoEventoLead.RECIBIDO,
            )
        ).all()
        leads = len({e.lead_id for e in evs})
        llamadas = [e for e in evs if e.tipo == TipoEventoLead.LLAMADA]
        contestadas = sum(1 for e in llamadas if (e.datos or {}).get("resultado") == "contesto")
        segs = [
            s
            for s in db.scalars(
                select(Seguimiento).where(
                    Seguimiento.created_by_id == user.id,
                    Seguimiento.due_at >= p.start,
                    Seguimiento.due_at < p.hasta,
                )
            )
            if not (s.resultado or "").startswith("Cancelado")
        ]
        a_tiempo = sum(1 for s in segs if s.done_at and s.done_at <= s.due_at + SEGUIMIENTO_MARGEN)
        citas = list(
            db.scalars(
                select(Cita).where(
                    Cita.created_by_id == user.id,
                    Cita.created_at >= p.start,
                    Cita.created_at < p.end,
                    Cita.tipo.in_(CITAS_DE_CLIENTE),
                )
            ).unique()
        )
        realizadas = sum(1 for c in citas if c.estado == EstadoCita.REALIZADA)
        ganados = [lead for lead, _, _ in self.ganados() if lead.assigned_to_id == user.id]
        perdidos = list(
            db.scalars(
                select(Lead).where(
                    Lead.assigned_to_id == user.id,
                    Lead.etapa == EtapaLead.PERDIDO,
                    Lead.cerrado_at >= p.start,
                    Lead.cerrado_at < p.end,
                )
            ).unique()
        )

        for a in areas:
            d = AREAS[a.key]
            if a.key == "leads_gestionados":
                a.logrado, a.logrado_txt = leads, _cant(leads, d.unidad)
            elif a.key == "llamadas":
                a.logrado = len(llamadas)
                a.logrado_txt = f"{len(llamadas)} · {contestadas} contestadas"
            elif a.key == "seguimientos":
                if not segs:
                    a.sin_datos = "Sin seguimientos programados para este mes todavía."
                    continue
                a.meta_txt = f"{len(segs)} programados"
                a.logrado, a.logrado_txt = a_tiempo, f"{a_tiempo} de {len(segs)} a tiempo"
                a.cumplimiento = _pct(a_tiempo, len(segs))
                if late := len(segs) - a_tiempo:
                    a.falta = f"{a_tiempo} de {len(segs)} a tiempo: {late} se pasaron de la hora"
                continue
            elif a.key == "citas_programadas":
                a.logrado, a.logrado_txt = len(citas), _cant(len(citas), d.unidad)
            elif a.key == "citas_realizadas":
                a.logrado, a.logrado_txt = realizadas, _cant(realizadas, d.unidad)
            elif a.key == "conversion":
                meta = a.meta or 0
                a.meta_txt = f"{meta} %"
                if not leads:
                    a.sin_datos = "Sin leads gestionados este mes todavía."
                    continue
                conv = 100 * len(citas) / leads
                a.logrado, a.logrado_txt = round(conv, 1), f"{_n(conv)} %"
                a.cumplimiento = _pct(conv, meta)
                if conv < meta:
                    a.falta = f"{_n(conv)} % de {meta} % ({len(citas)} citas ÷ {leads} leads)"
                continue
            elif a.key == "cierres":
                a.logrado, a.logrado_txt = len(ganados), _cant(len(ganados), d.unidad)
            self._cumplir(a, d)

        ajustes: list[dict[str, Any]] = []
        puntos = configuracion.get(self.db, "leads")  # Gerencia sets them in Configuración
        if ganados:
            ajustes.append(
                {
                    "tipo": "ganados",
                    "titulo": f"Ganados: {len(ganados)}",
                    "detalle": "Negocios cerrados, confirmados por Coordinación o Gerencia.",
                    "puntos": puntos["puntos_ganado"] * len(ganados),
                }
            )
        con = [lead for lead in perdidos if lead.perdida_descuenta]
        sin = [lead for lead in perdidos if not lead.perdida_descuenta]
        if sin:
            ajustes.append(
                {
                    "tipo": "perdidos_sin_descuento",
                    "titulo": f"Perdidos sin descuento: {len(sin)}",
                    "detalle": " · ".join(
                        f"{lead.code} {MOTIVO_LABELS[lead.motivo_perdida].lower()}"
                        for lead in sin
                        if lead.motivo_perdida
                    ),
                    "puntos": 0,
                }
            )
        if con:
            ajustes.append(
                {
                    "tipo": "perdidos",
                    "titulo": f"Perdidos con descuento: {len(con)}",
                    "detalle": " · ".join(
                        f"{lead.code} {MOTIVO_LABELS[lead.motivo_perdida].lower()}"
                        for lead in con
                        if lead.motivo_perdida
                    ),
                    "puntos": -puntos["puntos_perdido"] * len(con),
                }
            )
        return ajustes

    def _coordinacion(self, user: User, areas: list[Area]) -> None:
        for a in areas:
            if a.key in SIN_MODULO:
                a.sin_datos = SIN_MODULO[a.key]
            elif a.key == "equipo":
                totals = [
                    t
                    for u in self.db.scalars(select(User).where(User.is_active)).unique()
                    if perfil(u) in ("asesor", "atencion")
                    and (t := self.resultado(u).total) is not None
                ]
                if not totals:
                    a.sin_datos = "Sin personas con resultado este mes."
                    continue
                prom = sum(totals) / len(totals)
                a.logrado, a.cumplimiento = round(prom, 1), round(prom)
                a.meta_txt = "Promedio del equipo"
                a.logrado_txt = f"{_n(prom)} % · {len(totals)} personas"
            elif a.key == "rutas":
                from app.services import rutas

                c = rutas.cumplimiento_coordinador(self.db, user, self.p.first, self.p.last)
                if c is None:
                    a.sin_datos = "Sin rutas calificadas este mes: Gerencia las califica de 1 a 5."
                    continue
                prom, n = c
                a.meta, a.meta_txt = (
                    5,
                    f"{n} ruta{'s' if n != 1 else ''} calificada{'s' if n != 1 else ''}",
                )
                a.logrado = round(prom, 1)
                a.cumplimiento = round(prom * 20)
                a.logrado_txt = f"{_n(prom)} de 5 en promedio"
            elif a.key == "plataformas":
                c = plataformas.cumplimiento(self.db, user, self.p.first, self.p.last)
                if c is None:
                    a.sin_datos = "Sin plataformas asignadas: Gerencia asigna el responsable."
                    continue
                ok, total, n = c
                a.meta, a.meta_txt = total, f"{n} plataforma{'s' if n != 1 else ''} al día"
                a.logrado = ok
                a.cumplimiento = _pct(ok, total)
                a.logrado_txt = f"Al día el {a.cumplimiento} % de los días"
                if ok < total:
                    a.falta = f"Atrasadas {total - ok} de {total} días (sumando tus plataformas)"
            elif a.key == "monitoreo":
                limite = fechas.now() - VERIFICACION_PLAZO
                caps = [
                    c
                    for c in self.db.scalars(
                        select(Captacion).where(
                            Captacion.enviada_at >= self.p.start,
                            Captacion.enviada_at < self.p.end,
                        )
                    ).unique()
                    if c.verificado_at is not None or c.enviada_at < limite
                ]
                if not caps:
                    a.sin_datos = "Sin captaciones por verificar este mes todavía."
                    continue
                ok = sum(
                    1
                    for c in caps
                    if c.verificado_at and c.verificado_at - c.enviada_at <= VERIFICACION_PLAZO
                )
                a.meta, a.meta_txt = len(caps), f"{len(caps)} captaciones"
                a.logrado = ok
                a.logrado_txt = f"{ok} de {len(caps)} verificadas en menos de 24 h"
                a.cumplimiento = _pct(ok, len(caps))
                if ok < len(caps):
                    a.falta = (
                        f"{len(caps) - ok} captaciones se verificaron tarde o siguen sin verificar"
                    )

    def _cumplir(self, a: Area, d: AreaDef) -> None:
        """Count areas against their goal: «Llevas 7 de 13 arriendos: te faltan 6»."""
        meta = a.meta or 0
        a.meta_txt = a.meta_txt or _cant(meta, d.unidad)
        if not meta:
            a.sin_datos = "Sin meta configurada."
            return
        a.cumplimiento = _pct(a.logrado, meta)
        if a.logrado >= meta:
            a.falta = f"Cumpliste la meta: {_n(a.logrado)} de {_cant(meta, d.unidad)}"
        else:
            faltan = meta - a.logrado
            a.falta = (
                f"Llevas {_n(a.logrado)} de {_cant(meta, d.unidad)}: "
                f"te falta{'n' if faltan != 1 else ''} {_n(faltan)}"
            )

    def _calificaciones(self, user: User):
        p = self.p
        regs = preop._registros(self.db, [user.id], p.first, p.last).get(user.id, {})
        activo = preop.activo_para(self.db, user)
        res, _ = preop.resumen_mes(user, regs, p.first, p.last, activo)
        rows = {
            c.indicador: c
            for c in self.db.scalars(
                select(Calificacion).where(
                    Calificacion.user_id == user.id, Calificacion.periodo == p.first
                )
            ).unique()
        }
        cal: list[dict[str, Any]] = [
            {
                "key": "preoperacional",
                "titulo": "Preoperacional",
                "valor": res.puntaje,
                "automatico": True,
                "quien": (
                    f"Calculado por el sistema · {res.cumplidos} de {res.dias_habiles} días hábiles"
                    if res.puntaje is not None
                    else "Calculado por el sistema · sin días hábiles todavía"
                ),
                "que_hacer": "Haz el preoperacional todos los días antes de salir.",
                "fecha": None,
            },
            {
                "key": "puntualidad",
                "titulo": "Puntualidad",
                "valor": None,
                "automatico": True,
                "quien": "Sin datos: se calcula con «Marcar entrada», que aún no existe",
                "que_hacer": "",
                "fecha": None,
            },
        ]
        for i in indicadores_de(user):
            c = rows.get(i.key)
            cal.append(
                {
                    "key": i.key,
                    "titulo": i.titulo,
                    "valor": c.valor if c else None,
                    "automatico": False,
                    "quien": (
                        f"Asignado por {c.calificado_por.full_name}"
                        if c and c.calificado_por
                        else "Sin calificar todavía"
                    ),
                    "que_hacer": i.que_hacer,
                    "fecha": c.updated_at if c else None,
                }
            )
        desc = [
            {
                "titulo": f"{c['titulo']}: {c['valor']} de 5",
                "detalle": "Calificación de 2 o menos · "
                + (c["quien"].removeprefix("Asignado por ") if not c["automatico"] else "sistema")
                + (f" · {fechas.fmt(c['fecha'])[:-6]}" if c["fecha"] else ""),
                "puntos": DESCUENTO_CALIFICACION,
            }
            for c in cal
            if c["valor"] is not None and c["valor"] <= 2
        ]
        # G-036: 1 point per GPS alert rejected or left unjustified past the deadline.
        desc += movimientos.descuentos(self.db, user, p.start, p.end)
        avisos = []
        hoy = preop.hoy()
        if (
            activo
            and p.en_curso
            and hoy.weekday() < 5
            and hoy not in regs
            and user.cargo != Cargo.GERENCIA
        ):
            avisos.append(
                {
                    "titulo": "Preoperacional de hoy pendiente",
                    "detalle": "Si no lo haces, baja tu nota del preoperacional del mes.",
                    "link": "/preoperacional",
                }
            )
        pend = len(movimientos.pendientes_de(self.db, user)) if p.en_curso else 0
        if pend and movimientos.perfil(user):
            avisos.append(
                {
                    "titulo": f"{pend} alerta{'s' if pend != 1 else ''} de GPS sin justificar",
                    "detalle": "Si no la justificas a tiempo o la rechazan, se descuenta 1 punto.",
                    "link": "/movimientos",
                }
            )
        return cal, desc, avisos


# ---------------------------------------------------------------- views


def mejoras(r: Resultado, anterior: Resultado | None) -> dict[str, Any]:
    """«Tus puntos de mejora»: the lowest areas against their goal, low ratings, what goes well."""
    con = sorted((a for a in r.areas if a.cumplimiento is not None), key=lambda a: a.cumplimiento)
    weak = [a for a in con if a.cumplimiento < 80]
    todo_verde = not weak
    if todo_verde:
        weak = [a for a in con if a.cumplimiento < 100]
    items = []
    for a in weak[:3]:
        prev = anterior.area(a.key) if anterior else None
        items.append(
            {
                "key": a.key,
                "titulo": a.titulo,
                "cumplimiento": a.cumplimiento,
                "falta": a.falta,
                "que_hacer": AREAS[a.key].que_hacer,
                "link": AREAS[a.key].link,
                "peso": a.peso,
                "anterior": prev.cumplimiento if prev else None,
            }
        )
    return {
        "items": items,
        "todo_verde": todo_verde,
        "calificaciones": [
            {
                "titulo": c["titulo"],
                "valor": c["valor"],
                "quien": c["quien"],
                "que_hacer": c["que_hacer"],
            }
            for c in r.calificaciones
            if c["valor"] is not None and c["valor"] <= 3
        ],
        "bien": [
            {"titulo": a.titulo, "cumplimiento": a.cumplimiento}
            for a in con
            if a.cumplimiento >= 90
        ][::-1][:3],
    }


def detalle_equipo(db: Session, r: Resultado) -> dict[str, Any]:
    """K18 detail: what's in progress and clients lost this month."""
    u, p = r.user, r.periodo
    en_proceso: list[dict[str, Any]] = []
    perdidos: list[dict[str, Any]] = []
    if perfil(u) == "atencion":
        for lead in db.scalars(
            select(Lead)
            .where(
                Lead.assigned_to_id == u.id,
                Lead.etapa.notin_((EtapaLead.GANADO, EtapaLead.PERDIDO)),
            )
            .order_by(Lead.updated_at.desc())
            .limit(8)
        ).unique():
            en_proceso.append(
                {
                    "code": lead.code,
                    "titulo": lead.full_name + (f" · {lead.negocio.value}" if lead.negocio else ""),
                    "detalle": lead.busca or "",
                    "estado": ETAPA_LABELS[lead.etapa],
                    "cls": "warn" if lead.etapa == EtapaLead.CITA_PROGRAMADA else "info",
                    "link": f"/leads/{lead.id}",
                }
            )
        for lead in db.scalars(
            select(Lead).where(
                Lead.assigned_to_id == u.id,
                Lead.etapa == EtapaLead.PERDIDO,
                Lead.cerrado_at >= p.start,
                Lead.cerrado_at < p.end,
            )
        ).unique():
            motivo = MOTIVO_LABELS[lead.motivo_perdida] if lead.motivo_perdida else "Perdido"
            perdidos.append(
                {
                    "cliente": f"{lead.code} · {lead.full_name}",
                    "motivo": motivo + ("" if lead.perdida_descuenta else " · sin descuento"),
                    "fecha": lead.cerrado_at,
                }
            )
    elif perfil(u) == "asesor":
        for pe in db.scalars(
            select(Pedido)
            .where(Pedido.responsable_id == u.id, Pedido.estado == EstadoPedido.ABIERTO)
            .order_by(Pedido.fecha_limite)
            .limit(8)
        ).unique():
            vencido = pe.fecha_limite < fechas.now()
            en_proceso.append(
                {
                    "code": pe.code,
                    "titulo": f"Pedido · {pe.cliente_nombre}",
                    "detalle": f"{pe.negocio.value.capitalize()} · {pe.zona} · "
                    f"vence {fechas.fmt(pe.fecha_limite)}",
                    "estado": "Vencido · sin decidir" if vencido else "Abierto",
                    "cls": "warn" if vencido else "info",
                    "link": "/pedidos",
                }
            )
        for pe in db.scalars(
            select(Pedido).where(
                Pedido.responsable_id == u.id,
                Pedido.estado == EstadoPedido.PERDIDO,
                Pedido.cerrado_at >= p.start,
                Pedido.cerrado_at < p.end,
            )
        ).unique():
            perdidos.append(
                {
                    "cliente": f"{pe.code} · {pe.cliente_nombre}",
                    "motivo": MOTIVO_PEDIDO_LABELS[pe.motivo_perdida]
                    if pe.motivo_perdida
                    else "Perdido",
                    "fecha": pe.cerrado_at,
                }
            )
    return {"en_proceso": en_proceso, "perdidos": perdidos}


def fila(r: Resultado, perdidos: int) -> dict[str, Any]:
    """One row of «Mi equipo» / «Rendimiento por empleado»."""
    u = r.user
    cum, tot = r.metas_cumplidas

    def lg(k: str) -> int | None:
        a = r.area(k)
        return int(a.logrado) if a else None

    conv = r.area("conversion")
    return {
        "id": u.id,
        "full_name": u.full_name,
        "perfil": perfil(u),
        "cargo_txt": cargo_txt(u),
        "total": r.total,
        "semaforo": semaforo(r.total),
        "metas_cumplidas": cum,
        "metas_total": tot,
        "ventas": lg("ventas"),
        "arriendos": lg("arriendos"),
        "captaciones": lg("captacion"),
        "leads": lg("leads_gestionados"),
        "citas": lg("citas_programadas"),
        "conversion": conv.logrado if conv and conv.cumplimiento is not None else None,
        "ganados": lg("cierres"),
        "perdidos": perdidos,
        "descuentos": r.puntos_descuento,
        "areas": [
            {"titulo": a.titulo, "cumplimiento": a.cumplimiento, "logrado_txt": a.logrado_txt}
            for a in r.areas
        ],
    }


def perdidos_count(db: Session, u: User, p: Periodo) -> int:
    if perfil(u) == "atencion":
        q = select(Lead.id).where(Lead.assigned_to_id == u.id, Lead.etapa == EtapaLead.PERDIDO)
        q = q.where(Lead.cerrado_at >= p.start, Lead.cerrado_at < p.end)
    elif perfil(u) == "asesor":
        q = select(Pedido.id).where(
            Pedido.responsable_id == u.id,
            Pedido.estado == EstadoPedido.PERDIDO,
            Pedido.cerrado_at >= p.start,
            Pedido.cerrado_at < p.end,
        )
    else:
        return 0
    return len(db.scalars(q).all())


def equipo(db: Session, viewer: User, p: Periodo) -> dict[str, Any]:
    calc = Calculo(db, p)
    personas = [fila(calc.resultado(u), perdidos_count(db, u, p)) for u in team(db, viewer)]
    return {"periodo": p, "personas": personas}


def _prom(xs: Iterable[int | None]) -> int | None:
    vals = [x for x in xs if x is not None]
    return round(sum(vals) / len(vals)) if vals else None


def empresa(db: Session, viewer: User, p: Periodo) -> dict[str, Any]:
    """G12: each area of the company = average of its people; the company = average of everyone."""
    if viewer.cargo != Cargo.GERENCIA:
        raise PermissionDeniedError("El rendimiento de la empresa lo ve Gerencia.")
    people = team(db, viewer)
    ant = p.anterior()
    cur, prev = Calculo(db, p), Calculo(db, ant)
    grupos = (
        ("comercial", "Comercial", "asesor"),
        ("atencion", "Atención y Preventa", "atencion"),
        ("coordinacion", "Coordinación", "coordinacion"),
    )
    metricas = {
        "comercial": (
            ("ventas", "Ventas cerradas"),
            ("arriendos", "Arriendos cerrados"),
            ("captacion", "Captaciones aprobadas"),
        ),
        "atencion": (
            ("leads_gestionados", "Leads seguidos"),
            ("citas_programadas", "Citas programadas"),
            ("cierres", "Leads ganados"),
        ),
        "coordinacion": (("monitoreo", "Captaciones verificadas a tiempo"),),
    }
    areas = []
    todos: list[int | None] = []
    peor: tuple[int, str] | None = None
    for key, titulo, perf in grupos:
        us = [u for u in people if perfil(u) == perf]
        rs = [cur.resultado(u) for u in us]
        todos += [r.total for r in rs]
        prom = _prom(r.total for r in rs)
        prom_ant = _prom(prev.resultado(u).total for u in us)
        mets = []
        for k, t in metricas[key]:
            arr = [a for r in rs if (a := r.area(k)) and a.cumplimiento is not None]
            if not arr:
                continue
            lo, meta = sum(a.logrado for a in arr), sum(a.meta or 0 for a in arr)
            pct = _pct(lo, meta)
            mets.append({"titulo": t, "logrado": int(lo), "meta": meta, "pct": pct})
            if pct < 100 and (peor is None or pct < peor[0]):
                peor = (pct, f"{t.lower()} ({int(lo)} de {meta}) en {titulo}")
        areas.append(
            {
                "key": key,
                "titulo": titulo,
                "personas": " · ".join(
                    f"{r.user.full_name.split()[0]} {r.total if r.total is not None else '—'}"
                    for r in rs
                ),
                "n": len(us),
                "total": prom,
                "semaforo": semaforo(prom),
                "metas": mets,
                "anterior": prom_ant,
            }
        )
    areas.append(
        {
            "key": "administrativa",
            "titulo": "Administrativa",
            "personas": "Sin datos: firmas, pólizas, novedades y pagos aún no están en el sistema",
            "n": 0,
            "total": None,
            "semaforo": None,
            "metas": [],
            "anterior": None,
        }
    )
    total = _prom(todos)
    n = len([t for t in todos if t is not None])
    avisos = [
        {
            "titulo": f"{a['titulo']} está en {a['total']} %",
            "detalle": f"{p.label.capitalize()} · por debajo del 60 %: tomar acciones o aplicar "
            "estrategias. El detalle por persona está en «Rendimiento por empleado».",
            "nivel": "bad",
        }
        for a in areas
        if a["total"] is not None and a["total"] < 60
    ] or [
        {
            "titulo": "Ningún área está por debajo del 60 %",
            "detalle": p.label.capitalize() + (" · va en curso" if p.en_curso else ""),
            "nivel": "ok",
        }
    ]
    return {
        "periodo": p,
        "total": total,
        "semaforo": semaforo(total),
        "personas": n,
        "anterior": _prom(prev.resultado(u).total for u in people),
        "texto": (
            f"Promedio de las {n} personas con resultado."
            + (f" Lo que más baja el resultado: {peor[1]}." if peor else "")
        ),
        "areas": areas,
        "avisos": avisos,
    }


def export_csv(db: Session, viewer: User, p: Periodo) -> str:
    import csv
    import io

    data = equipo(db, viewer, p)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "Persona",
            "Cargo",
            "Rendimiento %",
            "Semáforo",
            "Metas cumplidas",
            "Áreas",
            "Descuentos",
            "Clientes perdidos",
        ]
    )
    for f in data["personas"]:
        w.writerow(
            [
                f["full_name"],
                f["cargo_txt"],
                f["total"] if f["total"] is not None else "",
                f["semaforo"] or "",
                f"{f['metas_cumplidas']} de {f['metas_total']}",
                " · ".join(
                    f"{a['titulo']} {a['cumplimiento']}%"
                    if a["cumplimiento"] is not None
                    else f"{a['titulo']} sin datos"
                    for a in f["areas"]
                ),
                f["descuentos"],
                f["perdidos"],
            ]
        )
    return "﻿" + buf.getvalue()
