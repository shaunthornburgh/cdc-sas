import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TipoNegocio


class NegocioPatch(BaseModel):
    """Deal data (Auxiliar and Gerencia). Only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    negocio: TipoNegocio | None = None  # only when the lead didn't say
    inmueble_id: uuid.UUID | None = None
    valor: int | None = None
    pct_venta: float | None = None
    uso_comercial: bool | None = None
    arrendatario_juridica: bool | None = None
    referido: str | None = Field(None, max_length=200)
    docs_ubicacion: str | None = Field(None, max_length=300)
    contrato_adjunto: bool | None = None


class EtapaIn(BaseModel):
    etapa: str | None = Field(None, max_length=40)
    oferta: str | None = Field(None, max_length=250)
    observacion: str = Field(max_length=300)
    notaria: str | None = Field(None, max_length=200)
    notaria_at: datetime | None = None


class SolicitarIn(BaseModel):
    nota: str | None = Field(None, max_length=300)


class ConfirmarIn(BaseModel):
    fecha: date
    contrato_adjunto: bool = False
    observacion: str | None = Field(None, max_length=300)


class MotivoIn(BaseModel):
    motivo: str = Field(max_length=300)


class CaidaIn(BaseModel):
    motivo: str = Field(max_length=100)
    observacion: str = Field(max_length=300)


class AbonoIn(BaseModel):
    valor: int = Field(gt=0)
    fecha: date
    momento: str = Field("otro", max_length=20)
    soporte: bool = False
