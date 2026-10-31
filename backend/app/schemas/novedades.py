import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Cargo, EstadoNovedad, TipoNovedad


class Empleado(BaseModel):
    id: uuid.UUID
    full_name: str
    cargo: Cargo


class NovedadRead(BaseModel):
    id: uuid.UUID
    code: str
    empleado: Empleado
    tipo: TipoNovedad
    tipo_txt: str
    descuenta: bool
    desde: date
    hasta: date
    fechas_txt: str  # «1 y 2 oct»
    dias: int
    observacion: str | None
    soportes: int
    estado: EstadoNovedad
    estado_txt: str
    registrada_por_name: str | None
    created_at: datetime
    anulada_por_name: str | None
    anulada_at: datetime | None
    motivo_anulacion: str | None
    puede_editar: bool


class NovedadList(BaseModel):
    items: list[NovedadRead]
    desde: date
    hasta: date
    dias: dict[str, int]  # days of each type inside the range
    preop_sin_revisar: int


class NovedadCreate(BaseModel):
    empleado_id: uuid.UUID
    tipo: TipoNovedad
    desde: date
    hasta: date
    observacion: str | None = Field(None, max_length=500)
    soportes: int = Field(0, ge=0, le=20)


class NovedadCreated(BaseModel):
    novedad: NovedadRead
    avisos: list[str]  # pay periods already confirmed / paid


class NovedadUpdate(BaseModel):
    """Only the note and attachments. Dates or type wrong: annul it and register it again."""

    model_config = ConfigDict(extra="forbid")

    observacion: str | None = Field(None, max_length=500)
    soportes: int | None = Field(None, ge=0, le=20)


class AnularIn(BaseModel):
    motivo: str = Field(max_length=300)


class Opciones(BaseModel):
    tipos: dict[str, str]
    ayudas: dict[str, str]
    descontables: list[str]
    empleados: list[Empleado]
    puede_registrar: bool
    desde: date  # default range: this month
    hasta: date


class PreopNovedad(BaseModel):
    id: uuid.UUID
    empleado: Empleado
    fecha: date
    realizado_at: datetime
    medio: str  # «Moto · KLM78F»
    texto: str
    revisado: bool
    revisado_por_name: str | None
    revisado_at: datetime | None
    revision_nota: str | None
    puede_revisar: bool
