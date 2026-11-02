import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class TipoIn(BaseModel):
    nombre: str = Field(max_length=120)
    precio_pct: float
    costo_estudio: int | None = Field(None, ge=0)
    dias_respuesta: int | None = Field(None, ge=0, le=60)
    coberturas: list[str] = []


class AseguradoraIn(BaseModel):
    nombre: str = Field(max_length=120)
    nit: str | None = Field(None, max_length=40)
    contacto: str | None = Field(None, max_length=120)
    telefono: str | None = Field(None, max_length=200)
    dias_max: int | None = None
    aviso_dias: int | None = None
    poliza: TipoIn


class AseguradoraPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nit: str | None = Field(None, max_length=40)
    contacto: str | None = Field(None, max_length=120)
    telefono: str | None = Field(None, max_length=200)
    dias_max: int | None = None
    aviso_dias: int | None = None
    activa: bool | None = None


class PolizaIn(BaseModel):
    cierre_id: uuid.UUID | None = None
    inmueble_id: uuid.UUID | None = None
    descripcion: str | None = Field(None, max_length=200)
    tipo_id: uuid.UUID
    canon: int | None = None
    radicado: str | None = Field(None, max_length=80)
    estudio_fecha: date | None = None
    seguro_inmueble: bool = False


class PolizaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo_id: uuid.UUID | None = None
    canon: int | None = None
    radicado: str | None = Field(None, max_length=80)
    seguro_inmueble: bool | None = None


class DecidirIn(BaseModel):
    aprobada: bool
    motivo: str | None = Field(None, max_length=300)


class MotivoIn(BaseModel):
    motivo: str = Field(max_length=300)


class FechaIn(BaseModel):
    fecha: date


class ActivarIn(BaseModel):
    fecha: date
    numero: str = Field(max_length=80)
    soporte: bool = False
