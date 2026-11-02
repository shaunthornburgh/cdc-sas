import uuid
from datetime import date

from pydantic import BaseModel, Field


class ZonaIn(BaseModel):
    zona: str = Field(max_length=60)
    hora_inicio: str = Field(max_length=5)
    hora_fin: str = Field(max_length=5)
    dias: list[int]


class RutaIn(BaseModel):
    asesor_id: uuid.UUID
    desde: date
    hasta: date
    dias: list[int]
    zonas: list[ZonaIn] = Field(max_length=3)
    observacion: str | None = Field(None, max_length=300)
    reemplaza_id: uuid.UUID | None = None


class ResponderIn(BaseModel):
    acepta: bool
    motivo: str | None = None
    texto: str | None = Field(None, max_length=500)


class CalificarIn(BaseModel):
    puntos: int = Field(ge=1, le=5)


class LlegadaIn(BaseModel):
    zona_id: uuid.UUID
    nota: str | None = Field(None, max_length=300)


class ImportarIn(BaseModel):
    texto: str = Field(max_length=500_000)
    confirmar: bool = False
