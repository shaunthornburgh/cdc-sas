import uuid
from datetime import date, datetime

from pydantic import BaseModel


class Fila(BaseModel):
    id: str
    at: datetime
    actor_id: uuid.UUID | None
    actor: str | None
    modulo: str
    accion: str
    registro: str | None
    antes: str | None
    despues: str | None
    link: str | None


class Lista(BaseModel):
    items: list[Fila]
    total: int
    desde: date
    hasta: date
    gerencia: bool


class Opciones(BaseModel):
    modulos: list[str]
    usuarios: list[dict]
    desde: date
    hasta: date
    alcance: str | None
