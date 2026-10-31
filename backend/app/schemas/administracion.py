import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    CanalSolicitud,
    CategoriaReparacion,
    EstadoAmbiente,
    EstadoInventario,
    EstadoReparacion,
    EstadoSolicitud,
    PagaReparacion,
    Prioridad,
    Solicitante,
    TipoInventario,
    TipoSolicitud,
)


class EventoRead(BaseModel):
    titulo: str
    detalle: str | None
    created_by_name: str | None
    created_at: datetime


class InmuebleRef(BaseModel):
    id: uuid.UUID
    codigo: str
    titulo: str  # «Apto Belén»


class Persona(BaseModel):
    id: uuid.UUID
    full_name: str


# ---------------------------------------------------------------- inventarios


class AmbienteRead(BaseModel):
    id: uuid.UUID
    nombre: str
    estado: EstadoAmbiente | None
    observacion: str | None
    fotos: int


class InventarioRead(BaseModel):
    id: uuid.UUID
    code: str
    inmueble: InmuebleRef
    tipo: TipoInventario
    tipo_txt: str
    fecha: date
    referencia: str
    responsable: Persona | None
    estado: EstadoInventario
    estado_txt: str
    firmado_at: datetime | None
    ambientes: list[AmbienteRead]
    novedades: int
    fotos: int
    reparacion_code: str | None
    puede_llenar: bool
    puede_gestionar: bool
    eventos: list[EventoRead]


class InventarioCreate(BaseModel):
    inmueble_id: uuid.UUID
    tipo: TipoInventario
    fecha: date
    referencia: str = Field(max_length=300)
    responsable_id: uuid.UUID


class InventarioUpdate(BaseModel):
    tipo: TipoInventario | None = None
    fecha: date | None = None
    referencia: str | None = Field(None, max_length=300)
    responsable_id: uuid.UUID | None = None


class AmbienteIn(BaseModel):
    estado: EstadoAmbiente | None = None
    observacion: str | None = Field(None, max_length=500)
    fotos: int | None = Field(None, ge=0, le=50)


# ---------------------------------------------------------------- reparaciones


class ReparacionRead(BaseModel):
    id: uuid.UUID
    code: str
    inmueble: InmuebleRef
    titulo: str
    categoria: CategoriaReparacion
    categoria_txt: str
    prioridad: Prioridad
    solicitante: str
    fecha: date
    estado: EstadoReparacion
    estado_txt: str
    proveedor: str | None
    valor: int | None
    paga: PagaReparacion
    paga_txt: str
    fecha_fin: date | None
    dias: int  # «lleva» / «se resolvió en»
    responsable: Persona | None
    inventario_code: str | None
    puede_avance: bool
    puede_gestionar: bool
    eventos: list[EventoRead]


class ReparacionCreate(BaseModel):
    inmueble_id: uuid.UUID
    titulo: str = Field(max_length=500)
    categoria: CategoriaReparacion
    prioridad: Prioridad = Prioridad.NORMAL
    solicitante: str | None = Field(None, max_length=200)
    fecha: date
    responsable_id: uuid.UUID | None = None


class ReparacionUpdate(BaseModel):
    titulo: str | None = Field(None, max_length=500)
    categoria: CategoriaReparacion | None = None
    prioridad: Prioridad | None = None
    solicitante: str | None = Field(None, max_length=200)
    fecha: date | None = None
    responsable_id: uuid.UUID | None = None


class AvanceIn(BaseModel):
    proveedor: str | None = Field(None, max_length=200)
    valor: int | None = None
    paga: PagaReparacion | None = None
    comentario: str | None = Field(None, max_length=1000)


class EstadoReparacionIn(BaseModel):
    estado: EstadoReparacion
    nota: str | None = Field(None, max_length=500)


# ---------------------------------------------------------------- solicitudes


class SolicitudRead(BaseModel):
    id: uuid.UUID
    code: str
    inmueble: InmuebleRef
    tipo: TipoSolicitud
    tipo_txt: str
    de: Solicitante
    de_txt: str
    nombre: str | None
    canal: CanalSolicitud
    canal_txt: str
    descripcion: str
    prioridad: Prioridad
    fecha: date
    estado: EstadoSolicitud
    estado_txt: str
    fuera_de_plazo: bool
    dias_habiles: int
    plazo: int
    responsable: Persona | None
    respuesta: str | None
    fecha_respuesta: date | None
    puede_responder: bool
    puede_gestionar: bool
    eventos: list[EventoRead]


class SolicitudCreate(BaseModel):
    inmueble_id: uuid.UUID
    tipo: TipoSolicitud
    de: Solicitante
    nombre: str | None = Field(None, max_length=200)
    canal: CanalSolicitud
    descripcion: str = Field(max_length=1000)
    prioridad: Prioridad = Prioridad.NORMAL
    fecha: date
    responsable_id: uuid.UUID | None = None


class SolicitudUpdate(BaseModel):
    tipo: TipoSolicitud | None = None
    de: Solicitante | None = None
    nombre: str | None = Field(None, max_length=200)
    canal: CanalSolicitud | None = None
    descripcion: str | None = Field(None, max_length=1000)
    prioridad: Prioridad | None = None
    fecha: date | None = None
    responsable_id: uuid.UUID | None = None


class RespuestaIn(BaseModel):
    respuesta: str = Field(max_length=4000)


class EstadoSolicitudIn(BaseModel):
    estado: EstadoSolicitud
    nota: str | None = Field(None, max_length=500)


# ---------------------------------------------------------------- page


class Resumen(BaseModel):
    kpis: dict[str, int | float]
    puede_gestionar: bool
    plazo: int
    inmuebles: list[InmuebleRef]
    responsables: list[Persona]
    labels: dict[str, dict[str, str]]
