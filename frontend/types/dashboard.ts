import type { ActividadComercial, FuncionIndependiente } from '~/types/auth'
import type { EstadoCita, TipoCita, TipoNegocio } from '~/types/leads'

export interface DashCita {
  id: string
  code: string
  tipo: TipoCita
  estado: EstadoCita
  scheduled_at: string
  asesor_name: string | null
  lead_id: string
  lead_code: string
  lead_name: string
  motivo: string | null
  requiere_accion: boolean
}

export interface DashboardCoordinacion {
  generado_at: string
  leads: {
    por_etapa: Record<string, number>
    abiertos: number
    abiertos_por_negocio: Record<string, number>
    sin_responsable: number
    sin_responsable_alerta: number
    nuevos_hoy: number
    nuevos_semana: number
    seguimientos_vencidos: number
    ganados_mes: number
    perdidos_mes: number
    perdidos_con_descuento_mes: number
  }
  citas: {
    pendientes: number
    pendientes_menos_1h: number
    rechazadas: number
    requieren_accion: number
    hoy_total: number
    hoy_aceptadas: number
    hoy_realizadas: number
    realizadas_mes: number
    lista_accion: DashCita[]
    lista_hoy: DashCita[]
    lista_proximas: DashCita[]
  }
  captaciones: {
    counts: Record<'por_verificar' | 'aprobada' | 'rechazada', number>
    aprobacion_pct: number | null
    registradas_mes: number
    aprobadas_mes: number
    rechazadas_mes: number
    sin_publicar: number
    lista_por_verificar: { id: string; code: string; codigo_inmueble: string; negocio: TipoNegocio; asesor_name: string; enviada_at: string; reenvios: number }[]
  }
  equipo: {
    usuarios_activos: number
    asesores_activos: number
    atencion_activos: number
    con_captacion: number
    asesores: {
      id: string
      full_name: string
      actividades: ActividadComercial[]
      gps_checkin_enabled: boolean
      citas_sin_aceptar: number
      cita_sin_aceptar_code: string | null
      cita_sin_aceptar_urgente: boolean
      citas_hoy: number
      citas_aceptadas_activas: number
      citas_realizadas_mes: number
      captaciones_venta_mes: number | null
      captaciones_arriendo_mes: number | null
      captaciones_por_verificar: number | null
      captaciones_rechazadas: number | null
    }[]
    atencion: {
      id: string
      full_name: string
      funcion: FuncionIndependiente | null
      leads_seguidos_mes: number
      primera_respuesta_min: number | null
      llamadas_mes: number
      llamadas_contestadas_mes: number
      seguimientos_mes: number
      seguimientos_a_tiempo_mes: number
      seguimientos_vencidos: number
      citas_programadas_mes: number
      citas_realizadas_mes: number
      citas_requieren_accion: number
      leads_abiertos: number
      ganados_mes: number
      perdidos_mes: number
    }[]
  }
  preoperacional: {
    total: number
    realizados: number
    con_novedad: number
    novedades_sin_revisar: number
    sin_realizar: number
    cumplimiento_mes_anterior: number | null
    faltan: string[]
    por_persona: Record<string, string>
  } | null
  pedidos: {
    abiertos: number
    proximos_a_vencer: number
    vencidos_mes: number
    vencidos_sin_decidir: number
    por_persona: Record<string, { por_vencer: number; hoy: number; vencidos: number }>
    lista_sin_decidir: { id: string; code: string; cliente: string; responsable: string; fecha_limite: string }[]
  }
  alertas: { nivel: 'bad' | 'warn'; titulo: string; detalle: string; que_hacer: string; link: string; accion: string }[]
}
