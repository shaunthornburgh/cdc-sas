import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import (
    ActividadComercial,
    EstadoCita,
    FuncionIndependiente,
    TipoCita,
    TipoNegocio,
)


class LeadsSummary(BaseModel):
    por_etapa: dict[str, int]  # open stages now; ganado / perdido = this month
    abiertos: int
    abiertos_por_negocio: dict[str, int]
    sin_responsable: int
    sin_responsable_alerta: int  # waiting > 15 min
    nuevos_hoy: int
    nuevos_semana: int
    seguimientos_vencidos: int
    ganados_mes: int
    perdidos_mes: int
    perdidos_con_descuento_mes: int


class CitaItem(BaseModel):
    id: uuid.UUID
    code: str
    tipo: TipoCita
    estado: EstadoCita
    scheduled_at: datetime
    asesor_name: str | None
    lead_id: uuid.UUID
    lead_code: str
    lead_name: str
    motivo: str | None
    requiere_accion: bool


class CitasSummary(BaseModel):
    pendientes: int
    pendientes_menos_1h: int
    rechazadas: int
    requieren_accion: int
    hoy_total: int
    hoy_aceptadas: int
    hoy_realizadas: int
    realizadas_mes: int
    lista_accion: list[CitaItem]
    lista_hoy: list[CitaItem]
    lista_proximas: list[CitaItem]


class CaptacionItem(BaseModel):
    id: uuid.UUID
    code: str
    codigo_inmueble: str
    negocio: TipoNegocio
    asesor_name: str
    enviada_at: datetime
    reenvios: int


class CaptacionesSummary(BaseModel):
    counts: dict[str, int]
    aprobacion_pct: int | None
    registradas_mes: int
    aprobadas_mes: int
    rechazadas_mes: int
    sin_publicar: int
    lista_por_verificar: list[CaptacionItem]


class AsesorRow(BaseModel):
    id: uuid.UUID
    full_name: str
    actividades: list[ActividadComercial]
    gps_checkin_enabled: bool
    citas_sin_aceptar: int
    cita_sin_aceptar_code: str | None
    cita_sin_aceptar_urgente: bool
    citas_hoy: int
    citas_aceptadas_activas: int
    citas_realizadas_mes: int
    # None = the person doesn't have Captación («no aplica»)
    captaciones_venta_mes: int | None
    captaciones_arriendo_mes: int | None
    captaciones_por_verificar: int | None
    captaciones_rechazadas: int | None


class AtencionRow(BaseModel):
    id: uuid.UUID
    full_name: str
    funcion: FuncionIndependiente | None
    leads_seguidos_mes: int
    primera_respuesta_min: int | None
    llamadas_mes: int
    llamadas_contestadas_mes: int
    seguimientos_mes: int
    seguimientos_a_tiempo_mes: int
    seguimientos_vencidos: int
    citas_programadas_mes: int
    citas_realizadas_mes: int
    citas_requieren_accion: int
    leads_abiertos: int
    ganados_mes: int
    perdidos_mes: int


class Equipo(BaseModel):
    usuarios_activos: int
    asesores_activos: int
    atencion_activos: int
    con_captacion: int
    asesores: list[AsesorRow]
    atencion: list[AtencionRow]


class Alerta(BaseModel):
    nivel: str  # bad | warn
    titulo: str
    detalle: str
    que_hacer: str
    link: str
    accion: str


class PreopHoy(BaseModel):
    total: int
    realizados: int
    con_novedad: int
    novedades_sin_revisar: int
    sin_realizar: int
    cumplimiento_mes_anterior: int | None
    faltan: list[str]
    por_persona: dict[uuid.UUID, str]  # realizado | reporte | novedad | sin_realizar | …


class PedidoVencido(BaseModel):
    id: uuid.UUID
    code: str
    cliente: str
    responsable: str
    fecha_limite: datetime


class PedidosHoy(BaseModel):
    abiertos: int
    proximos_a_vencer: int
    vencidos_mes: int
    vencidos_sin_decidir: int
    por_persona: dict[str, dict[str, int]]  # user id → por_vencer · hoy · vencidos
    lista_sin_decidir: list[PedidoVencido]


class DashboardCoordinacion(BaseModel):
    generado_at: datetime
    leads: LeadsSummary
    citas: CitasSummary
    captaciones: CaptacionesSummary
    equipo: Equipo
    preoperacional: PreopHoy | None
    pedidos: PedidosHoy
    alertas: list[Alerta]
