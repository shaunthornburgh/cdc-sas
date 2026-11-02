import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field


class Persona(BaseModel):
    id: uuid.UUID
    full_name: str
    rol_txt: str
    yo: bool
    puede_agregar: bool


class Acciones(BaseModel):
    hecha: bool = False
    rechazar: bool = False
    justificar: bool = False
    eliminar: bool = False


class Entrada(BaseModel):
    """One item of the agenda: an activity added by hand (`k = man`) or a system one (`sys`)."""

    id: str
    k: str
    tipo: str  # cita · seg · ped · ctl · mia · asg
    fecha: date
    hora: time | None
    hora_txt: str
    titulo: str
    sub: str | None
    nota: str | None = None
    prioridad: str = "normal"
    estado: str | None = None  # manual: pendiente · atrasada · hecha · rechazada · justificada
    estado_txt: str
    estado_cls: str
    link: str | None = None
    por_name: str | None = None
    por_yo: bool = False
    created_at: datetime | None = None
    motivo: str | None = None
    respondida_at: datetime | None = None
    aviso_titulo: str | None = None
    acciones: Acciones = Acciones()


class Eliminada(BaseModel):
    titulo: str
    fecha: date
    por_name: str | None
    created_at: datetime
    eliminada_por: str | None
    eliminado_at: datetime


class Vista(BaseModel):
    persona: Persona
    desde: date
    hasta: date
    items: list[Entrada]
    eliminadas: list[Eliminada]
    tipos: dict[str, str]


class AgendaIn(BaseModel):
    para_id: uuid.UUID | None = None
    titulo: str = Field(max_length=200)
    fecha: date
    hora: time | None = None
    nota: str | None = Field(None, max_length=500)
    prioridad: str = "normal"


class MotivoIn(BaseModel):
    motivo: str = Field(max_length=500)
