import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.enums import (
    EstadoCaptacion,
    ModoCaptacion,
    MotivoRechazoCaptacion,
    TipoEventoCaptacion,
    TipoInmueble,
    TipoNegocio,
)
from app.schemas.leads import UserRef

Codigo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=40)]
Direccion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=300)]
Opt120 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None
Opt200 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None
OptPhone = (
    Annotated[str, StringConstraints(strip_whitespace=True, min_length=7, max_length=40)] | None
)
OptLong = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] | None


class GpsIn(BaseModel):
    """Browser geolocation at submission time (only stored for the captador's own sends)."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    precision_m: int | None = Field(None, ge=0, le=100_000)


class _Detalles(BaseModel):
    tipo_inmueble: TipoInmueble | None = None
    barrio: Opt120 = None
    municipio: Opt120 = None
    precio: int | None = Field(None, ge=0, le=1_000_000_000_000)
    area_m2: Decimal | None = Field(None, ge=0, le=1_000_000, max_digits=10, decimal_places=2)
    habitaciones: int | None = Field(None, ge=0, le=50)
    banos: int | None = Field(None, ge=0, le=50)
    parqueadero: bool | None = None
    propietario_nombre: Opt200 = None
    propietario_telefono: OptPhone = None
    observaciones: OptLong = None


class CaptacionCreate(_Detalles):
    modo: ModoCaptacion = ModoCaptacion.RAPIDO
    negocio: TipoNegocio
    codigo_inmueble: Codigo
    direccion: Direccion
    asesor_id: uuid.UUID | None = Field(None, description="Solo Coordinación / Gerencia")
    gps: GpsIn | None = None


class CaptacionUpdate(_Detalles):
    """Partial update. Send only what changes."""

    modo: ModoCaptacion | None = None
    negocio: TipoNegocio | None = None
    codigo_inmueble: Codigo | None = None
    direccion: Direccion | None = None

    @model_validator(mode="before")
    @classmethod
    def _required_not_null(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ("modo", "negocio", "codigo_inmueble", "direccion"):
                if key in data and data[key] is None:
                    raise ValueError(f"{key} no puede ser null")
        return data


class VerificarIn(BaseModel):
    estado: EstadoCaptacion
    motivo: MotivoRechazoCaptacion | None = None
    observacion: OptLong = None


class ReenviarIn(BaseModel):
    codigo_inmueble: Codigo
    direccion: Direccion


class ReasignarIn(BaseModel):
    asesor_id: uuid.UUID


class CaptacionEventoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tipo: TipoEventoCaptacion
    titulo: str
    detalle: str | None
    created_by_name: str | None
    created_at: datetime


class CaptacionRead(_Detalles):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    modo: ModoCaptacion
    negocio: TipoNegocio
    codigo_inmueble: str
    direccion: str
    estado: EstadoCaptacion
    enviada_at: datetime
    reenvios: int
    motivo_rechazo: MotivoRechazoCaptacion | None
    observacion_rechazo: str | None
    verificado_por_name: str | None
    verificado_at: datetime | None
    publicada_at: datetime | None
    gps_lat: Decimal | None
    gps_lng: Decimal | None
    gps_precision_m: int | None
    gps_at: datetime | None
    asesor: UserRef
    created_at: datetime
    can_edit: bool = False
    eventos: list[CaptacionEventoRead] = []


class CaptacionList(BaseModel):
    items: list[CaptacionRead]
    counts: dict[str, int]
    aprobacion_pct: int | None
