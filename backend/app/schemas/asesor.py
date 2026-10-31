import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models.enums import ActividadComercial, Cargo, EstadoCita, TipoCita

LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class AsesorRef(BaseModel):
    id: uuid.UUID
    full_name: str
    cargo: Cargo
    actividades: list[ActividadComercial]
    gps_checkin_enabled: bool


class AsesorCita(BaseModel):
    id: uuid.UUID
    code: str
    tipo: TipoCita
    estado: EstadoCita
    scheduled_at: datetime
    inmueble: str | None
    notas: str | None
    motivo: str | None
    cliente: str
    fuente: str
    programada_por: str | None
    asesor_name: str | None
    mia: bool
    puede_aceptar: bool
    puede_tomar: bool
    puede_cerrar: bool


class Pendiente(BaseModel):
    titulo: str
    detalle: str
    cls: str  # chip class
    chip: str
    link: str
    cita_id: uuid.UUID | None = None
    captacion_id: uuid.UUID | None = None


class CaptacionesAsesor(BaseModel):
    counts: dict[str, int]
    aprobadas_venta_mes: int
    aprobadas_arriendo_mes: int
    publicadas_mes: int
    sin_publicar: int


class PreopEstado(BaseModel):
    activo: bool
    realizado_at: datetime | None
    tiene_novedad: bool


class AsesorInicio(BaseModel):
    preoperacional: PreopEstado
    asesor: AsesorRef
    pendientes: list[Pendiente]
    citas_hoy: list[AsesorCita]
    citas_counts: dict[str, int]
    captaciones: CaptacionesAsesor | None  # None = no Captación activity
    resultados: dict[str, dict[str, int]]  # keys: captacion | ventas | arriendos (active only)


class MisCitas(BaseModel):
    responder: list[AsesorCita]
    proximas: list[AsesorCita]
    por_cerrar: list[AsesorCita]
    cerradas: list[AsesorCita]
    counts: dict[str, int]


class RechazoIn(BaseModel):
    motivo: str
    observacion: LongText


class CierreIn(BaseModel):
    resultado: LongText
