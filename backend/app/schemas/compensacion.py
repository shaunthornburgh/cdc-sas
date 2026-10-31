import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class Persona(BaseModel):
    id: uuid.UUID
    full_name: str


class CierreRead(BaseModel):
    id: uuid.UUID
    code: str
    lead_code: str
    cliente: str
    negocio: str | None
    cerrado_at: datetime
    estado: str
    ganancia: int | None
    cerrador: Persona | None
    filtro: Persona | None
    captador: Persona | None


class ItemRead(BaseModel):
    """A commission or a bonus as G05 shows it."""

    id: uuid.UUID
    clase: str
    tipo: str
    beneficiario: Persona
    concepto: str
    detalle: str | None
    fecha: datetime
    periodo: date
    valor: int
    base: int | None = None
    porcentaje: Decimal | None = None
    cierre_code: str | None = None
    estado: str
    estado_txt: str
    se_paga: str


class PagoRead(BaseModel):
    id: uuid.UUID
    beneficiario: Persona
    tipo: str
    concepto: str
    valor: int
    fecha_programada: date
    estado: str
    estado_txt: str
    pagado_at: datetime | None


class Tablero(BaseModel):
    """G05 «Comisiones, bonos y pagos»."""

    comisiones: list[ItemRead]
    bonos: list[ItemRead]
    pagos: list[PagoRead]
    cierres: list[CierreRead]
    totales: dict[str, dict[str, int]]
    config: dict[str, Any]
    config_labels: dict[str, str]
    personas: list[Persona]
    captadores: list[Persona]
    es_gerencia: bool
    es_auxiliar: bool


class ManualIn(BaseModel):
    beneficiario_id: uuid.UUID
    concepto: str = Field(min_length=3, max_length=300)
    detalle: str | None = Field(default=None, max_length=500)
    valor: int = Field(gt=0)
    fecha: datetime | None = None
    cierre_id: uuid.UUID | None = None


class AccionIn(BaseModel):
    accion: str  # visto_bueno · aprobar · pagar · ajustar · anular
    valor: int | None = None
    motivo: str | None = Field(default=None, max_length=300)


class GananciaIn(BaseModel):
    ganancia: int
    captador_id: uuid.UUID | None = None


class ConfigIn(BaseModel):
    valores: dict[str, Any]


class Evento(BaseModel):
    accion: str
    antes: dict[str, Any]
    despues: dict[str, Any]
    created_by_name: str | None
    created_at: datetime


class CalculoOut(BaseModel):
    bonos: int
    grupal: int


class MioItem(BaseModel):
    id: uuid.UUID
    clase: str
    concepto: str
    detalle: str
    fecha: datetime
    valor: int
    se_paga: str
    estado: str
    estado_txt: str


class MioPago(BaseModel):
    id: uuid.UUID
    concepto: str
    detalle: str
    fecha: date
    valor: int
    tipo: str
    estado: str
    estado_txt: str


class Mio(BaseModel):
    perfil: str | None
    como_ganas: list[dict[str, str]]
    salario_mensual: int | None
    kpis: dict[str, Any]
    items: list[MioItem]
    pagos: list[MioPago]


class LiquidacionRead(BaseModel):
    id: uuid.UUID
    user: Persona
    cargo_txt: str
    salario_mensual: int
    salario_corte: int
    descuento: int
    a_pagar: int
    novedades: str
    estado: str
    estado_txt: str


class Salarios(BaseModel):
    periodo: str
    label: str
    corte: int
    fecha_pago: date
    filas: list[LiquidacionRead]
    sin_salario: list[Persona]  # active people without a salary configured
    es_gerencia: bool
    es_auxiliar: bool


class SalarioIn(BaseModel):
    salario_mensual: int = Field(gt=0)


class SalarioAccionIn(BaseModel):
    accion: str  # confirmar · pagar
    ids: list[uuid.UUID] = Field(min_length=1)
