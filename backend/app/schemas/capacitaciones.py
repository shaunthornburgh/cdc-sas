import uuid
from datetime import date, time

from pydantic import BaseModel, Field


class ProgramarIn(BaseModel):
    fecha: date
    hora: time
    area: str = Field(max_length=60)
    tema: str = Field(max_length=200)
    presenta: str = Field(max_length=200)
    lugar: str | None = Field(None, max_length=300)
    participantes: str = Field("todo", max_length=10)  # todo · com · ate · adm · per
    personas: list[uuid.UUID] = []


class RegistrarIn(BaseModel):
    fecha: date
    hora: time
    area: str = Field(max_length=60)
    tema: str = Field(max_length=200)
    presenta: str = Field(max_length=200)
    aprendio: str = Field(max_length=2000)
    observaciones: str | None = Field(None, max_length=2000)


class ResponderIn(BaseModel):
    acepta: bool
    motivo: str | None = Field(None, max_length=60)
    detalle: str | None = Field(None, max_length=300)


class CompletarIn(BaseModel):
    asistentes: list[uuid.UUID]


class MotivoIn(BaseModel):
    motivo: str = Field(max_length=300)


class AprendizajeIn(BaseModel):
    aprendio: str = Field(max_length=2000)
    observaciones: str | None = Field(None, max_length=2000)
