import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.enums import (
    EstadoPedido,
    MotivoPerdidaPedido,
    TipoEventoPedido,
    TipoInmueble,
    TipoNegocio,
    UrgenciaPedido,
)
from app.schemas.leads import UserRef

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=7, max_length=40)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
OptText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
Zona = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Budget = Annotated[int, Field(gt=0, le=100_000_000_000)]


class PedidoEventoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tipo: TipoEventoPedido
    titulo: str
    detalle: str | None
    datos: dict[str, Any]
    created_by_name: str | None
    created_at: datetime


class PedidoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    cliente_nombre: str
    cliente_telefono: str | None
    lead_id: uuid.UUID | None
    negocio: TipoNegocio
    tipo_inmueble: TipoInmueble
    zona: str
    presupuesto: int
    observaciones: str | None
    fecha_limite: datetime
    urgencia: UrgenciaPedido
    estado: EstadoPedido
    vencio: bool
    motivo_perdida: MotivoPerdidaPedido | None
    cerrado_at: datetime | None
    responsable: UserRef
    created_by_name: str | None
    created_at: datetime
    # Derived
    estado_visible: str = ""
    vencido: bool = False
    proximo_a_vencer: bool = False
    can_edit: bool = False
    eventos: list[PedidoEventoRead] = []


class PedidoList(BaseModel):
    items: list[PedidoRead]
    kpis: dict[str, int]


class PedidoCreate(BaseModel):
    cliente_nombre: Name
    cliente_telefono: Phone | None = None
    lead_id: uuid.UUID | None = None
    negocio: TipoNegocio
    tipo_inmueble: TipoInmueble
    zona: Zona
    presupuesto: Budget
    fecha_limite: AwareDatetime
    urgencia: UrgenciaPedido = UrgenciaPedido.NORMAL
    observaciones: OptText = None
    responsable_id: uuid.UUID | None = Field(None, description="Default: quien lo crea")
    otra_necesidad: bool = Field(False, description="Crear aunque el cliente ya tenga uno abierto")


class PedidoUpdate(BaseModel):
    """«Actualizar»: the changed fields plus «¿Qué cambió?»."""

    que_cambio: Text
    cliente_nombre: Name | None = None
    cliente_telefono: Phone | None = None
    negocio: TipoNegocio | None = None
    tipo_inmueble: TipoInmueble | None = None
    zona: Zona | None = None
    presupuesto: Budget | None = None
    fecha_limite: AwareDatetime | None = None
    urgencia: UrgenciaPedido | None = None
    observaciones: OptText = None

    @model_validator(mode="before")
    @classmethod
    def _no_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for k in (
                "cliente_nombre",
                "negocio",
                "tipo_inmueble",
                "zona",
                "presupuesto",
                "fecha_limite",
                "urgencia",
            ):
                if k in data and data[k] is None:
                    raise ValueError(f"{k} no puede ser null")
        return data


class ExtenderIn(BaseModel):
    fecha_limite: AwareDatetime
    motivo: Text


class AtenderIn(BaseModel):
    nota: OptText = None


class PerdidoIn(BaseModel):
    motivo: MotivoPerdidaPedido
    nota: OptText = None


class PropuestaIn(BaseModel):
    inmueble: Text
    nota: OptText = None


class ComentarioIn(BaseModel):
    texto: Text


class ReasignarIn(BaseModel):
    responsable_id: uuid.UUID


class Opciones(BaseModel):
    zonas: list[str]
    rangos: dict[str, str]
    motivos: dict[MotivoPerdidaPedido, str]
    responsables: list[UserRef]
