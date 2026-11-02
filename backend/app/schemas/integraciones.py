from pydantic import BaseModel, ConfigDict, Field


class AgregarIn(BaseModel):
    nombre: str = Field(max_length=80)
    grupo: str
    como: str = "por_confirmar"
    usuario: str | None = Field(None, max_length=200)
    costo_mensual: int | None = Field(None, ge=0, le=1_000_000_000)


class DatosIn(BaseModel):
    valores: dict[str, str | None]


class AjustesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    costo_mensual: int | None = Field(None, ge=0, le=1_000_000_000)
    como: str | None = None
    avisar_falla: bool | None = None
