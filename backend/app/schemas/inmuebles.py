import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import EstadoInmueble, TipoInmueble, TipoNegocio


class InmuebleEventoRead(BaseModel):
    titulo: str
    detalle: str | None
    created_by_name: str | None
    created_at: datetime


class InmuebleRead(BaseModel):
    id: uuid.UUID
    codigo: str
    titulo: str  # «Apto Belén»
    negocio: TipoNegocio
    tipo_inmueble: TipoInmueble | None
    direccion: str
    zona: str | None
    barrio: str | None
    municipio: str | None
    precio: int | None
    administracion: int | None
    area_m2: Decimal | None
    habitaciones: int | None
    banos: int | None
    parqueadero: bool | None
    estrato: int | None
    descripcion: str | None
    propietario_nombre: str | None  # only for whoever may see it
    propietario_telefono: str | None
    ve_propietario: bool
    estado: EstadoInmueble
    estado_txt: str
    estado_at: datetime
    faltantes: list[str]
    captacion_code: str | None
    captacion_id: uuid.UUID | None
    captador_name: str | None
    can_edit: bool
    created_at: datetime
    eventos: list[InmuebleEventoRead]


class InmuebleList(BaseModel):
    items: list[InmuebleRead]
    kpis: dict[str, int]


class Opciones(BaseModel):
    zonas: list[str]
    rangos: dict[str, str]
    estados: dict[str, str]
    puede_crear: bool


class InmuebleBase(BaseModel):
    tipo_inmueble: TipoInmueble | None = None
    direccion: str | None = Field(None, max_length=300)
    zona: str | None = Field(None, max_length=60)
    barrio: str | None = Field(None, max_length=120)
    municipio: str | None = Field(None, max_length=120)
    precio: int | None = Field(None, ge=0)
    administracion: int | None = Field(None, ge=0)
    area_m2: Decimal | None = Field(None, gt=0, max_digits=10, decimal_places=2)
    habitaciones: int | None = Field(None, ge=0, le=30)
    banos: int | None = Field(None, ge=0, le=30)
    parqueadero: bool | None = None
    estrato: int | None = Field(None, ge=1, le=6)
    descripcion: str | None = Field(None, max_length=4000)
    propietario_nombre: str | None = Field(None, max_length=200)
    propietario_telefono: str | None = Field(None, max_length=40)


class InmuebleCreate(InmuebleBase):
    codigo: str = Field(min_length=3, max_length=40)
    negocio: TipoNegocio
    direccion: str = Field(min_length=5, max_length=300)


class InmuebleUpdate(InmuebleBase):
    codigo: str | None = Field(None, min_length=3, max_length=40)
    negocio: TipoNegocio | None = None


class EstadoIn(BaseModel):
    estado: EstadoInmueble
    nota: str | None = Field(None, max_length=500)


class OpcionLead(BaseModel):
    id: uuid.UUID
    codigo: str
    titulo: str
    detalle: str
    ya_enviado: bool
