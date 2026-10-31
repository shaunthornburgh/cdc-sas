import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class PeriodoRead(BaseModel):
    key: str  # «2026-10»
    label: str  # «octubre 2026»
    en_curso: bool


class AreaRead(BaseModel):
    key: str
    titulo: str
    descripcion: str
    peso: int
    peso_efectivo: float  # weight over the areas with data
    meta: int | None
    meta_txt: str
    logrado: float
    logrado_txt: str
    cumplimiento: int | None  # None: no data, doesn't count
    semaforo: str | None
    cumple: bool
    aporte: float
    falta: str
    sin_datos: str | None


class CalificacionRead(BaseModel):
    key: str
    titulo: str
    valor: int | None
    automatico: bool
    quien: str
    fecha: datetime | None


class Punto(BaseModel):
    titulo: str
    detalle: str
    puntos: float


class Aviso(BaseModel):
    titulo: str
    detalle: str
    link: str


class Mejora(BaseModel):
    key: str
    titulo: str
    cumplimiento: int
    falta: str
    que_hacer: str
    link: str
    peso: int
    anterior: int | None


class MejoraCalificacion(BaseModel):
    titulo: str
    valor: int
    quien: str
    que_hacer: str


class Bien(BaseModel):
    titulo: str
    cumplimiento: int


class Mejoras(BaseModel):
    items: list[Mejora]
    todo_verde: bool
    calificaciones: list[MejoraCalificacion]
    bien: list[Bien]


class EnProceso(BaseModel):
    code: str
    titulo: str
    detalle: str
    estado: str
    cls: str
    link: str


class Perdido(BaseModel):
    cliente: str
    motivo: str
    fecha: datetime | None


class Detalle(BaseModel):
    en_proceso: list[EnProceso]
    perdidos: list[Perdido]


class Persona(BaseModel):
    id: uuid.UUID
    full_name: str


class Puede(BaseModel):
    calificar: bool
    configurar: bool


class ResultadoRead(BaseModel):
    user: Persona
    perfil: str
    cargo_txt: str
    periodo: PeriodoRead
    total: int | None
    total_exacto: float | None
    semaforo: str | None
    por_areas: float | None
    peso_con_datos: int
    puntos_ajuste: float
    puntos_descuento: float
    anterior: int | None  # last month's result
    areas: list[AreaRead]
    calificaciones: list[CalificacionRead]
    descuentos: list[Punto]
    ajustes: list[Punto]
    avisos: list[Aviso]
    mejoras: Mejoras
    puede: Puede
    detalle: Detalle | None = None


class AreaFila(BaseModel):
    titulo: str
    cumplimiento: int | None
    logrado_txt: str


class FilaEquipo(BaseModel):
    id: uuid.UUID
    full_name: str
    perfil: str
    cargo_txt: str
    total: int | None
    semaforo: str | None
    metas_cumplidas: int
    metas_total: int
    ventas: int | None
    arriendos: int | None
    captaciones: int | None
    leads: int | None
    citas: int | None
    conversion: float | None
    ganados: int | None
    perdidos: int
    descuentos: float
    areas: list[AreaFila]


class Equipo(BaseModel):
    periodo: PeriodoRead
    personas: list[FilaEquipo]


class MetaEmpresa(BaseModel):
    titulo: str
    logrado: int
    meta: int
    pct: int


class AreaEmpresa(BaseModel):
    key: str
    titulo: str
    personas: str
    n: int
    total: int | None
    semaforo: str | None
    metas: list[MetaEmpresa]
    anterior: int | None


class AvisoEmpresa(BaseModel):
    titulo: str
    detalle: str
    nivel: str


class Empresa(BaseModel):
    periodo: PeriodoRead
    total: int | None
    semaforo: str | None
    personas: int
    anterior: int | None
    texto: str
    areas: list[AreaEmpresa]
    avisos: list[AvisoEmpresa]


class AreaConfig(BaseModel):
    key: str
    titulo: str
    descripcion: str
    tiene_meta: bool
    unidad: str


class ConfigRead(BaseModel):
    user: Persona
    perfil: str
    cargo_txt: str
    areas: list[AreaConfig]
    pesos: dict[str, int]
    pesos_configurados: bool
    metas: dict[str, int]  # this month (fixed)
    metas_siguiente: dict[str, int]  # from next month (editable)
    siguiente: str  # «noviembre 2026»
    puede_configurar: bool


class PesosIn(BaseModel):
    pesos: dict[str, int]


class MetasIn(BaseModel):
    metas: dict[str, int]


class CalificacionesIn(BaseModel):
    valores: dict[str, int] = Field(min_length=1)


class CambioRead(BaseModel):
    tipo: str
    periodo: date
    antes: dict[str, Any]
    despues: dict[str, Any]
    created_by_name: str | None
    created_at: datetime
