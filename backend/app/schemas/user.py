import uuid
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.models.enums import ActividadComercial, Cargo, FuncionIndependiente


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    cargo: Cargo
    funcion: FuncionIndependiente | None
    actividades: list[ActividadComercial]
    gps_checkin_enabled: bool
    is_active: bool
    telefono: str | None = None
    documento: str | None = None
    fecha_ingreso: date | None = None


FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: FullName
    cargo: Cargo
    funcion: FuncionIndependiente | None = None
    actividades: list[ActividadComercial] = []
    is_active: bool = True


class UserUpdate(BaseModel):
    """Partial update. Send only the fields to change; `funcion: null` clears it."""

    full_name: FullName | None = None
    cargo: Cargo | None = None
    is_active: bool | None = None
    funcion: FuncionIndependiente | None = None
    telefono: str | None = Field(None, max_length=40)  # null or "" clears it
    documento: str | None = Field(None, max_length=30)
    fecha_ingreso: date | None = None

    @model_validator(mode="before")
    @classmethod
    def _no_null_for_required(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ("full_name", "cargo", "is_active"):
                if key in data and data[key] is None:
                    raise ValueError(f"{key} no puede ser null")
        return data


class ActividadesUpdate(BaseModel):
    actividades: list[ActividadComercial]


class FuncionUpdate(BaseModel):
    funcion: FuncionIndependiente | None


class ActividadEventoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    actividad: ActividadComercial
    activada: bool
    changed_by_id: uuid.UUID | None
    changed_by_name: str | None
    created_at: datetime


class UserCambioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campo: str
    campo_txt: str
    antes: str | None
    despues: str | None
    actor_name: str | None
    created_at: datetime
