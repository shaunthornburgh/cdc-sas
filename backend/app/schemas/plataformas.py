import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Cargo, FuenteLead, TipoEventoPlataforma


class Persona(BaseModel):
    id: uuid.UUID
    full_name: str
    cargo: Cargo


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    precio: int
    activacion: date
    vencimiento: date
    cupo_total: int
    destacados_total: int
    alarma_dias: int


class PlataformaRead(BaseModel):
    """One row of K15 (and the «Última actualización» table of K15-ger)."""

    id: uuid.UUID
    fuente: FuenteLead
    nombre: str
    color: str
    activa: bool
    responsable: Persona | None
    plan: PlanRead | None
    plan_estado: str  # sin_plan · activo · por_vencer · vencido
    plan_txt: str
    plan_cls: str
    cupo_total: int | None  # from the last update (or the plan)
    cupo_usado: int | None
    destacados_total: int | None
    destacados_usados: int | None
    ultima_at: datetime | None
    ultima_txt: str  # «Hace 2 días · 1 oct»
    ultima_por: str | None
    estado: str  # al_dia · atrasada · sin_actualizar
    estado_txt: str
    estado_cls: str
    puede_registrar: bool


class Kpis(BaseModel):
    al_dia: int
    total: int
    atrasadas: list[str]
    actualizaciones: int
    a_tiempo: int
    a_tiempo_pct: int | None
    del_responsable: int
    del_responsable_pct: int | None


class ActualizacionRead(BaseModel):
    id: uuid.UUID
    plataforma_id: uuid.UUID
    plataforma: str
    realizada_at: datetime
    actualizado_por: str | None
    actualizado_por_id: uuid.UUID | None
    responsable: str | None
    es_responsable: bool
    cupo_total: int
    cupo_usado: int
    destacados_total: int
    destacados_usados: int
    observacion: str | None
    dias_desde_anterior: int | None
    regla_dias: int
    a_tiempo: bool


class Tablero(BaseModel):
    """K15 (Coordinación) and the «Actualizaciones» tab of K15-ger."""

    plataformas: list[PlataformaRead]
    dias_regla: int
    regla_confirmada: bool
    mes_txt: str
    cupo_disponible: int
    destacados_disponibles: int
    desde: date
    hasta: date
    kpis: Kpis
    actualizaciones: list[ActualizacionRead]


class ResultadoFila(BaseModel):
    plataforma_id: uuid.UUID
    nombre: str
    color: str
    leads: int
    citas: int
    cierres: int
    costo: int
    costo_lead: int | None
    costo_cierre: int | None
    conversion: float | None
    plan_estado: str
    plan_txt: str
    plan_cls: str


class ResultadosKpis(BaseModel):
    leads: int
    cierres: int
    conversion: float | None
    costo: int
    costo_lead: int | None
    costo_cierre: int | None


class Barra(BaseModel):
    mes: str
    label: str
    valores: list[dict]


class Resultados(BaseModel):
    desde: date
    hasta: date
    filas: list[ResultadoFila]
    kpis: ResultadosKpis
    barras: list[Barra]


class Historico(BaseModel):
    columnas: list[str]
    filas: list[list[str]]  # preview: the first 5
    total: int


class Opciones(BaseModel):
    gerencia: bool
    puede_descargar: bool
    plataformas: list[dict]  # {id, nombre, activa}
    responsables: list[Persona]
    quienes: list[Persona]  # who has updated (filter)
    desde: date
    hasta: date


class ActualizacionIn(BaseModel):
    cupo_usado: int = Field(ge=0, le=10_000)  # «publicaciones activas»
    cupo_total: int = Field(ge=0, le=10_000)
    destacados_usados: int = Field(ge=0, le=1_000)
    destacados_total: int | None = Field(None, ge=0, le=1_000)  # only when there's no plan
    observacion: str | None = Field(None, max_length=300)


class ResponsableIn(BaseModel):
    responsable_id: uuid.UUID | None


class PlanIn(BaseModel):
    precio: int = Field(ge=0, le=1_000_000_000)
    activacion: date
    vencimiento: date
    cupo_total: int = Field(ge=0, le=10_000)
    destacados_total: int = Field(ge=0, le=1_000)
    alarma_dias: int = Field(10, ge=0, le=90)


class ActivaIn(BaseModel):
    activa: bool


class ReglaIn(BaseModel):
    dias_regla: int = Field(ge=1, le=60)


class Evento(BaseModel):
    id: uuid.UUID
    plataforma: str | None
    tipo: TipoEventoPlataforma
    actor_name: str | None
    antes: str | None
    despues: str | None
    detalle: str | None
    created_at: datetime
