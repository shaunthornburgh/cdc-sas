import uuid
from typing import Any

from pydantic import BaseModel, Field


class MarcarIn(BaseModel):
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    motivo: str | None = None
    texto: str | None = Field(None, max_length=500)


class RevisarIn(BaseModel):
    que: str  # entrada · salida · extra
    acepta: bool


class SedeIn(BaseModel):
    nombre: str | None = Field(None, max_length=120)
    direccion: str | None = Field(None, max_length=300)
    lat: float | None = None
    lng: float | None = None
    radio_m: int | None = None
    activa: bool | None = None
    principal: bool | None = None


class AsignarIn(BaseModel):
    sede_id: uuid.UUID


class ConfigIn(BaseModel):
    valores: dict[str, Any]
