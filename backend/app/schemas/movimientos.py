import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    ActividadCampo,
    Cargo,
    EstadoMovimiento,
    MotivoMovimiento,
    TipoCampo,
    TipoEventoMovimiento,
    TipoMovimiento,
)


class Empleado(BaseModel):
    id: uuid.UUID
    full_name: str
    cargo: Cargo
    perfil_txt: str  # «Asesor · Captación»


class MovimientoRead(BaseModel):
    id: uuid.UUID
    code: str
    empleado: Empleado
    tipo: TipoMovimiento
    tipo_txt: str
    es_alerta: bool
    estado: EstadoMovimiento
    estado_txt: str
    vencida: bool
    descuenta: bool
    plazo_at: datetime | None
    ocurrido_at: datetime
    fin_at: datetime | None
    en_curso: bool
    duracion_min: int | None  # field work (open: until now)
    duracion_txt: str | None
    minutos_umbral: int | None
    lugar: str | None
    tiene_ubicacion: bool  # coordinates only via POST /{id}/ubicacion (logged)
    detalle_txt: str
    # justification
    motivo: MotivoMovimiento | None
    motivo_txt: str | None
    inmueble_codigo: str | None
    inmueble_en_catalogo: bool
    cliente: str | None
    motivo_texto: str | None
    autorizo: str | None
    autorizo_txt: str | None
    evidencias: int
    observacion: str | None
    justificada_at: datetime | None
    # review
    revisa: str | None  # «Coordinación» / «Gerencia»
    revisado_por_name: str | None
    revisado_at: datetime | None
    nota_revision: str | None
    # field work
    tipo_campo: TipoCampo | None
    tipo_campo_txt: str | None
    actividad_campo: ActividadCampo | None
    actividad_campo_txt: str | None
    cita_code: str | None
    acompanados: list[str]
    detalle: str | None
    # what the viewer can do
    puede_justificar: bool
    puede_revisar: bool
    puede_finalizar: bool


class Kpis(BaseModel):
    alertas: int
    justificadas: int
    justificadas_pct: int | None
    sin_justificar: int
    vencidas: int
    por_revisar: int
    por_revisar_gerencia: int
    rechazadas: int
    coord_campo_min: int
    coord_campo_salidas: int


class PorEmpleado(BaseModel):
    empleado: Empleado
    alertas: int
    justificadas: int
    sin_justificar: int
    rechazadas: int
    vencidas: int
    campo_min: int


class MovimientoList(BaseModel):
    items: list[MovimientoRead]
    desde: date
    hasta: date
    kpis: Kpis
    por_empleado: list[PorEmpleado]
    pendientes: list[MovimientoRead]  # the viewer's own alerts to justify (any date)


class AlertaIn(BaseModel):
    """Reported by the person's phone."""

    tipo: TipoMovimiento
    ocurrido_at: datetime | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    lugar: str | None = Field(None, max_length=120)


class JustificarIn(BaseModel):
    motivo: MotivoMovimiento
    inmueble_codigo: str | None = Field(None, max_length=40)
    cliente: str | None = Field(None, max_length=200)
    motivo_texto: str | None = Field(None, max_length=300)
    autorizo: str | None = Field(None, max_length=20)
    evidencias: int = Field(0, ge=0, le=10)
    observacion: str | None = Field(None, max_length=500)


class RevisarIn(BaseModel):
    nota: str | None = Field(None, max_length=300)


class CampoIn(BaseModel):
    tipo_campo: TipoCampo
    actividad_campo: ActividadCampo
    cita_id: uuid.UUID | None = None
    acompanados_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    detalle: str | None = Field(None, max_length=300)
    lugar: str | None = Field(None, max_length=120)
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)


class ConfigIn(BaseModel):
    minutos_alerta: int | None = Field(None, ge=5, le=240)
    plazo_horas: int | None = Field(None, ge=1, le=168)  # send null to set it back to «pendiente»


class ConfigRead(BaseModel):
    minutos_alerta: int
    plazo_horas: int | None
    minutos_opciones: list[int]
    updated_by_name: str | None
    updated_at: datetime | None


class Evento(BaseModel):
    id: uuid.UUID
    tipo: TipoEventoMovimiento
    tipo_txt: str
    actor_name: str | None
    estado_antes: str | None
    estado_despues: str | None
    detalle: str | None
    created_at: datetime


class Ubicacion(BaseModel):
    lat: float
    lng: float
    lugar: str | None


class Opcion(BaseModel):
    id: uuid.UUID
    txt: str


class Opciones(BaseModel):
    perfil: str | None  # asesor · coordinacion · atencion · None (Gerencia)
    panel: bool  # Coordinación / Gerencia view
    gerencia: bool
    gps_activo: bool
    tipos: dict[str, str]
    estados: dict[str, str]
    motivos: dict[str, str]
    motivos_por_tipo: dict[str, list[str]]
    motivos_con_inmueble: list[str]
    autorizo: dict[str, str]
    tipos_campo: dict[str, str]  # the ones this person can start
    actividades_campo: dict[str, str]
    alertas_propias: list[str]  # alert types that apply to this person
    empleados: list[Empleado]  # filter (panel only)
    asesores: list[Opcion]  # acompañamiento / salida grupal
    citas: list[Opcion]  # apoyo en cita
    config: ConfigRead
    desde: date
    hasta: date
    jornada: str


class CampoAhora(BaseModel):
    abiertos: list[MovimientoRead]
    ultimo: MovimientoRead | None


class MapaPunto(BaseModel):
    id: uuid.UUID
    code: str
    empleado: str
    tipo_txt: str
    estado: EstadoMovimiento
    hora: datetime
    lugar: str | None
    x: float  # 0–1, relative position of today's points (schematic map)
    y: float


class Panel(BaseModel):
    """K05 «Configuración y mapa» (the Coordinación page, and Gerencia's second tab)."""

    config: ConfigRead
    cambios_config: list[Evento]
    con_gps: list[str]
    sin_gps: list[str]
    coordinador_campo: CampoAhora
    atencion_campo: CampoAhora
    hoy: list[MovimientoRead]  # today's alerts
    mapa: list[MapaPunto]
