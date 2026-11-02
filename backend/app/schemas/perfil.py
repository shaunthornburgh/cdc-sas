import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class Dato(BaseModel):
    k: str
    v: str


class Acceso(BaseModel):
    t: str
    href: str


class Resultados(BaseModel):
    href: str
    mes: str
    txt: str


class Perfil(BaseModel):
    id: uuid.UUID
    full_name: str
    cargo_txt: str
    area: str
    actividades: list[str]
    regla_nombre: str
    datos: list[Dato]
    resultados: Resultados | None
    accesos: list[Acceso]
    politica_aceptada_at: datetime | None
    tiene_foto: bool


class Foto(BaseModel):
    foto: str | None = Field(None, max_length=400_000)  # data URL; null removes it


class PasswordIn(BaseModel):
    actual: str = Field(max_length=128)
    nueva: str = Field(max_length=128)
