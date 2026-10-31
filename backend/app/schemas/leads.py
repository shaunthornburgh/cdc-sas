import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app.models.enums import (
    AccionSeguimiento,
    ActividadComercial,
    EstadoCita,
    EtapaLead,
    FuenteLead,
    MedioContacto,
    MotivoPerdida,
    ResultadoLlamada,
    TipoCita,
    TipoEventoLead,
    TipoNegocio,
)

Text200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
OptText200 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None
OptText100 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
OptLongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] | None
Phone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=7, max_length=40)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRef(ORM):
    id: uuid.UUID
    full_name: str


# ---------------------------------------------------------------- read models


class EventoRead(ORM):
    id: uuid.UUID
    tipo: TipoEventoLead
    titulo: str
    detalle: str | None
    datos: dict[str, Any]
    cita_id: uuid.UUID | None
    created_by_name: str | None
    created_at: datetime


class SeguimientoRead(ORM):
    id: uuid.UUID
    accion: AccionSeguimiento
    due_at: datetime
    nota: str | None
    done_at: datetime | None
    resultado: str | None


class CitaRef(ORM):
    id: uuid.UUID
    code: str
    tipo: TipoCita
    estado: EstadoCita
    scheduled_at: datetime
    asesor_id: uuid.UUID | None
    asesor_name: str | None
    inmueble: str | None
    requiere_accion: bool = False


class LeadSummary(ORM):
    id: uuid.UUID
    code: str
    full_name: str
    phone: str
    email: str | None
    fuente: FuenteLead
    fuente_detalle: str | None
    negocio: TipoNegocio | None
    busca: str | None
    etapa: EtapaLead
    motivo_perdida: MotivoPerdida | None
    perdida_descuenta: bool | None
    assigned_to: UserRef | None
    assigned_at: datetime | None
    created_at: datetime
    cerrado_at: datetime | None
    llamadas: int
    proximo_seguimiento: SeguimientoRead | None
    cita_activa: CitaRef | None
    ultimo_evento: EventoRead | None
    can_edit: bool


class LeadDetail(LeadSummary):
    presupuesto: str | None
    zona: str | None
    para_cuando: str | None
    notas: str | None
    llamadas_dias_seguidos: int
    eventos: list[EventoRead]
    seguimientos: list[SeguimientoRead]
    citas: list[CitaRef]


class LeadStats(BaseModel):
    recibidos: int
    sin_responsable: int
    seguidos: int
    llamadas: int
    llamadas_contestadas: int
    seguimientos: int
    seguimientos_realizados: int
    citas_programadas: int
    citas_realizadas: int


# ---------------------------------------------------------------- lead commands


class LeadCreate(BaseModel):
    full_name: Text200
    phone: Phone
    email: EmailStr | None = None
    fuente: FuenteLead
    fuente_detalle: OptText200 = None
    negocio: TipoNegocio | None = None
    busca: OptText200 = None
    presupuesto: OptText100 = None
    zona: OptText200 = None
    para_cuando: OptText100 = None
    notas: OptLongText = None
    seguir: bool = Field(False, description="Quedar como responsable al crearlo")


class LeadUpdate(BaseModel):
    """Partial update. `assigned_to_id` (reassign) is for Coordinación / Gerencia only."""

    full_name: Text200 | None = None
    phone: Phone | None = None
    email: EmailStr | None = None
    fuente: FuenteLead | None = None
    fuente_detalle: OptText200 = None
    negocio: TipoNegocio | None = None
    busca: OptText200 = None
    presupuesto: OptText100 = None
    zona: OptText200 = None
    para_cuando: OptText100 = None
    notas: OptLongText = None
    assigned_to_id: uuid.UUID | None = None

    @model_validator(mode="before")
    @classmethod
    def _required_not_null(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ("full_name", "phone", "fuente"):
                if key in data and data[key] is None:
                    raise ValueError(f"{key} no puede ser null")
        return data


class LlamadaIn(BaseModel):
    tipo: Literal["llamada"]
    resultado: ResultadoLlamada
    resumen: OptLongText = None
    duracion_min: int | None = Field(None, ge=0, le=600)


class MensajeIn(BaseModel):
    tipo: Literal["mensaje", "opciones"]
    medio: MedioContacto
    texto: str = Field("", max_length=4000)
    # «Enviar opciones»: properties picked from the catalog (C02).
    inmueble_ids: list[uuid.UUID] = Field(default_factory=list, max_length=12)


class ObservacionIn(BaseModel):
    tipo: Literal["observacion"]
    texto: LongText


AccionIn = Annotated[LlamadaIn | MensajeIn | ObservacionIn, Field(discriminator="tipo")]


class SeguimientoCreate(BaseModel):
    accion: AccionSeguimiento
    due_at: AwareDatetime
    nota: OptLongText = None


class SeguimientoComplete(BaseModel):
    resultado: LongText


class StageChange(BaseModel):
    etapa: EtapaLead
    motivo: MotivoPerdida | None = None


# ---------------------------------------------------------------- citas


class CitaLeadRef(ORM):
    id: uuid.UUID
    code: str
    full_name: str
    fuente: FuenteLead
    negocio: TipoNegocio | None


class CitaEventoRead(ORM):
    titulo: str
    detalle: str | None
    created_by_name: str | None
    created_at: datetime


class CitaRead(ORM):
    id: uuid.UUID
    code: str
    tipo: TipoCita
    estado: EstadoCita
    scheduled_at: datetime
    asesor: UserRef | None
    inmueble: str | None
    notas: str | None
    motivo: str | None
    created_at: datetime
    lead: CitaLeadRef
    requiere_accion: bool
    bucket: str
    historial: list[CitaEventoRead]


class CitaList(BaseModel):
    items: list[CitaRead]
    counts: dict[str, int]


class CitaCreate(BaseModel):
    lead_id: uuid.UUID
    tipo: TipoCita
    scheduled_at: AwareDatetime
    asesor_id: uuid.UUID
    inmueble: OptText200 = None
    notas: OptLongText = None


class CitaUpdate(BaseModel):
    inmueble: OptText200 = None
    notas: OptLongText = None


class CitaEstadoIn(BaseModel):
    estado: EstadoCita
    motivo: OptLongText = None


class CitaReasignar(BaseModel):
    asesor_id: uuid.UUID


class CitaReprogramar(BaseModel):
    scheduled_at: AwareDatetime
    motivo: LongText


class OcupadoRef(ORM):
    code: str
    scheduled_at: datetime


class AsesorOption(BaseModel):
    id: uuid.UUID
    full_name: str
    actividades: list[ActividadComercial]
    elegible: bool
    ocupado_con: OcupadoRef | None
