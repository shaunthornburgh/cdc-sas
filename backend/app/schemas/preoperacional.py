import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import Cargo, MedioTransporte
from app.schemas.leads import UserRef

OptText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None


class Respuesta(BaseModel):
    pregunta: str
    si: bool


class PreoperacionalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fecha: date
    realizado_at: datetime
    medio: MedioTransporte
    placa: str | None
    respuestas: list[Respuesta]
    respuestas_no: list[int]
    observaciones: str | None
    tiene_novedad: bool
    revisado_por_name: str | None
    revisado_at: datetime | None
    revision_nota: str | None
    user: UserRef


class Formulario(BaseModel):
    activo: bool
    medios: dict[MedioTransporte, str]
    preguntas: dict[MedioTransporte, list[str]]
    hoy: date
    registro_de_hoy: PreoperacionalRead | None
    destinatario: str


class PreoperacionalIn(BaseModel):
    medio: MedioTransporte
    placa: Annotated[str, StringConstraints(strip_whitespace=True, max_length=12)] | None = None
    respuestas: list[bool] | None = Field(None, description="8 answers, only for carro / moto")
    observaciones: OptText = None


class RevisionIn(BaseModel):
    nota: OptText = None


class ResumenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dias_habiles: int
    cumplidos: int
    novedades: int
    pct: int | None
    puntaje: int | None
    descuento: int


class Dia(BaseModel):
    fecha: date
    estado: (
        str  # realizado | novedad | no_realizado | pendiente | futuro | fin_de_semana | sin_contar
    )


class Evento(BaseModel):
    fecha: date
    tipo: str  # novedad | no_realizado
    registro: PreoperacionalRead | None


class Historial(BaseModel):
    mes: str
    activo: bool
    resumen: ResumenRead
    dias: list[Dia]
    eventos: list[Evento]
    registros: list[PreoperacionalRead]


class PersonaRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    cargo: Cargo


class FilaEquipo(BaseModel):
    user: PersonaRef
    estado: str  # realizado | reporte | novedad | sin_realizar | desactivado | fin_de_semana
    registro: PreoperacionalRead | None


class FilaMes(BaseModel):
    user: PersonaRef
    resumen: ResumenRead


class KpisEquipo(BaseModel):
    total: int
    realizados: int
    con_novedad: int
    novedades_sin_revisar: int
    sin_realizar: int
    cumplimiento_mes_anterior: int | None


class Equipo(BaseModel):
    fecha: date
    mes: str
    config: dict[Cargo, bool]
    kpis: KpisEquipo
    filas: list[FilaEquipo]
    mes_rows: list[FilaMes]


class ConfigIn(BaseModel):
    activo: bool
