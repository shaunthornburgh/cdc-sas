import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Marca(BaseModel):
    nombre: str
    lema: str
    color_principal: str
    color_oscuro: str
    color_claro: str
    logo: str | None


class MarcaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(None, max_length=40)
    lema: str | None = Field(None, max_length=80)
    color_principal: str | None = None
    color_oscuro: str | None = None
    color_claro: str | None = None
    logo: str | None = None  # send null to go back to the built-in logo


class Pagos(BaseModel):
    dia_corte_1: int = Field(ge=1, le=31)
    dia_corte_2: int = Field(ge=1, le=31)
    dia_pago: int = Field(ge=1, le=31)


class Pendiente(BaseModel):
    clave: str
    titulo: str
    detalle: str
    quien: str
    link: str | None
    resuelto: bool
    manual: bool


class PendienteIn(BaseModel):
    resuelto: bool


class Evento(BaseModel):
    id: uuid.UUID
    seccion: str
    seccion_txt: str
    actor_name: str | None
    antes: dict[str, Any]
    despues: dict[str, Any]
    detalle: str | None
    created_at: datetime


class Pagina(BaseModel):
    """Everything Z02 shows. Coordinación gets only what it may read."""

    gerencia: bool
    marca: Marca
    pagos: Pagos
    tarifas: dict[str, Any] | None
    automatizaciones: dict[str, Any] | None
    idioma: dict[str, Any] | None
    leads: dict[str, Any] | None
    produccion: dict[str, Any] | None
    pendientes: list[Pendiente]
    opciones: dict[str, Any]
    idiomas: dict[str, str]
    idiomas_disponibles: list[str]
    cambios: list[Evento]
