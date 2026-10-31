import type { ActividadComercial, Cargo } from '~/types/auth'
import type { EstadoCita, TipoCita } from '~/types/leads'

export interface AsesorCita {
  id: string
  code: string
  tipo: TipoCita
  estado: EstadoCita
  scheduled_at: string
  inmueble: string | null
  notas: string | null
  motivo: string | null
  cliente: string
  fuente: string
  programada_por: string | null
  asesor_name: string | null
  mia: boolean
  puede_aceptar: boolean
  puede_tomar: boolean
  puede_cerrar: boolean
}

export type CitasBucket = 'responder' | 'proximas' | 'por_cerrar' | 'cerradas'

export interface AsesorInicio {
  preoperacional: { activo: boolean; realizado_at: string | null; tiene_novedad: boolean }
  asesor: { id: string; full_name: string; cargo: Cargo; actividades: ActividadComercial[]; gps_checkin_enabled: boolean }
  pendientes: { titulo: string; detalle: string; cls: string; chip: string; link: string; cita_id: string | null; captacion_id: string | null }[]
  citas_hoy: AsesorCita[]
  citas_counts: Record<CitasBucket, number>
  captaciones: {
    counts: Record<'por_verificar' | 'aprobada' | 'rechazada', number>
    aprobadas_venta_mes: number
    aprobadas_arriendo_mes: number
    publicadas_mes: number
    sin_publicar: number
  } | null
  resultados: Partial<Record<'captacion' | 'ventas' | 'arriendos', Record<string, number>>>
}

export type MisCitas = Record<CitasBucket, AsesorCita[]> & { counts: Record<CitasBucket, number> }
