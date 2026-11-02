import uuid
from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, Field


class Nota(BaseModel):
    id: uuid.UUID
    autor_name: str | None
    texto: str
    created_at: datetime


class AvisoRead(BaseModel):
    id: uuid.UUID
    origen: str  # sistema · comunicado
    tipo: str
    tipo_txt: str
    nivel: str  # bad · warn · info · gray
    titulo: str
    detalle: str | None
    que_hacer: str | None
    limite_at: datetime | None
    link: str | None
    accion_txt: str | None
    datos: list[dict[str, Any]]
    requiere_accion: bool
    estado: str  # por_atender · atendido
    atendido_at: datetime | None
    atendido_por_name: str | None
    resuelto_auto: bool
    leido_at: datetime | None
    enviado_por: str | None  # comunicados
    created_at: datetime
    notas: list[Nota]


class Conteo(BaseModel):
    por_atender: int
    resumen_sin_leer: int
    agenda_hoy: int


class AvisoList(BaseModel):
    items: list[AvisoRead]
    conteo: Conteo


class NotaIn(BaseModel):
    texto: str = Field(max_length=1000)


class AtenderIn(BaseModel):
    nota: str | None = Field(None, max_length=1000)


class LeidosIn(BaseModel):
    ids: list[uuid.UUID] = Field(max_length=200)


class AgendaIn(BaseModel):
    titulo: str = Field(max_length=200)
    fecha: date
    hora: time | None = None
    nota: str | None = Field(None, max_length=500)
    prioridad: str = "normal"


class AgendaRead(BaseModel):
    id: uuid.UUID
    fecha: date
    hora: time | None
    hora_txt: str
    titulo: str
    nota: str | None
    prioridad: str
    estado: str  # pendiente · hecha
    hecha_at: datetime | None
    aviso_id: uuid.UUID | None
    aviso_titulo: str | None
    created_at: datetime


class HechaIn(BaseModel):
    hecha: bool = True


class ComunicadoIn(BaseModel):
    titulo: str = Field(max_length=160)
    cuerpo: str = Field(max_length=4000)
    audiencia: list[str] = Field(max_length=5)
    prioridad: str = "normal"
    expira_el: date | None = None


class Lectura(BaseModel):
    nombre: str
    leido_at: datetime | None


class ComunicadoRead(BaseModel):
    id: uuid.UUID
    titulo: str
    cuerpo: str
    prioridad: str
    audiencia: list[str]
    audiencia_txt: str
    expira_el: date | None
    creado_por: str | None
    created_at: datetime
    total: int
    leidos: int
    lecturas: list[Lectura]


class Opciones(BaseModel):
    puede_comunicar: bool
    audiencias: dict[str, str]
    gerencia: bool
