export type EtapaLead = 'nuevo' | 'en_gestion' | 'seguimiento' | 'cita_programada' | 'ganado' | 'perdido'
export type FuenteLead =
  | 'ciencuadras' | 'espacio_urbano' | 'proppi' | 'finca_raiz' | 'metrocuadrado'
  | 'facebook' | 'instagram' | 'tiktok' | 'otro'
export type TipoNegocio = 'arriendo' | 'venta'
export type MotivoPerdida = 'no_contesta' | 'numero_equivocado' | 'no_interesado' | 'compro_con_otro' | 'presupuesto'
export type TipoEventoLead =
  | 'recibido' | 'seguir' | 'asignacion' | 'llamada' | 'mensaje' | 'opciones'
  | 'seguimiento' | 'observacion' | 'cita' | 'etapa' | 'datos'
export type ResultadoLlamada = 'contesto' | 'no_contesto' | 'numero_equivocado'
export type MedioContacto = 'whatsapp' | 'correo' | 'sms'
export type AccionSeguimiento =
  | 'llamar' | 'enviar_opciones' | 'enviar_informacion' | 'confirmar_cita'
  | 'seguimiento_propuesta' | 'volver_a_contactar'
export type TipoCita =
  | 'visita_arriendo' | 'visita_venta' | 'captacion' | 'visita_control' | 'inventario' | 'reunion_asesoria'
export type EstadoCita = 'pendiente' | 'aceptada' | 'rechazada' | 'realizada' | 'cancelada'
export type CitaBucket = 'accion' | 'pendientes' | 'aceptadas' | 'realizadas' | 'canceladas'

export interface UserRef {
  id: string
  full_name: string
}

export interface Evento {
  id: string
  tipo: TipoEventoLead
  titulo: string
  detalle: string | null
  datos: Record<string, unknown>
  cita_id: string | null
  created_by_name: string | null
  created_at: string
}

export interface SeguimientoT {
  id: string
  accion: AccionSeguimiento
  due_at: string
  nota: string | null
  done_at: string | null
  resultado: string | null
}

export interface CitaRef {
  id: string
  code: string
  tipo: TipoCita
  estado: EstadoCita
  scheduled_at: string
  asesor_id: string | null
  asesor_name: string | null
  inmueble: string | null
  requiere_accion: boolean
}

export interface LeadSummary {
  id: string
  code: string
  full_name: string
  phone: string
  email: string | null
  fuente: FuenteLead
  fuente_detalle: string | null
  negocio: TipoNegocio | null
  busca: string | null
  etapa: EtapaLead
  motivo_perdida: MotivoPerdida | null
  perdida_descuenta: boolean | null
  assigned_to: UserRef | null
  assigned_at: string | null
  created_at: string
  cerrado_at: string | null
  llamadas: number
  proximo_seguimiento: SeguimientoT | null
  cita_activa: CitaRef | null
  ultimo_evento: Evento | null
  can_edit: boolean
}

export interface LeadDetail extends LeadSummary {
  presupuesto: string | null
  zona: string | null
  para_cuando: string | null
  notas: string | null
  llamadas_dias_seguidos: number
  eventos: Evento[]
  seguimientos: SeguimientoT[]
  citas: CitaRef[]
}

export interface LeadStats {
  recibidos: number
  sin_responsable: number
  seguidos: number
  llamadas: number
  llamadas_contestadas: number
  seguimientos: number
  seguimientos_realizados: number
  citas_programadas: number
  citas_realizadas: number
}

export type LeadFields = {
  full_name: string
  phone: string
  email: string | null
  fuente: FuenteLead
  fuente_detalle: string | null
  negocio: TipoNegocio | null
  busca: string | null
  presupuesto: string | null
  zona: string | null
  para_cuando: string | null
  notas: string | null
}

export type AccionIn =
  | { tipo: 'llamada'; resultado: ResultadoLlamada; resumen?: string | null; duracion_min?: number | null }
  | { tipo: 'mensaje' | 'opciones'; medio: MedioContacto; texto: string; inmueble_ids?: string[] }
  | { tipo: 'observacion'; texto: string }

export interface Cita {
  id: string
  code: string
  tipo: TipoCita
  estado: EstadoCita
  scheduled_at: string
  asesor: UserRef | null
  inmueble: string | null
  notas: string | null
  motivo: string | null
  created_at: string
  lead: { id: string; code: string; full_name: string; fuente: FuenteLead; negocio: TipoNegocio | null }
  requiere_accion: boolean
  bucket: CitaBucket
  historial: { titulo: string; detalle: string | null; created_by_name: string | null; created_at: string }[]
}

export interface AsesorOption {
  id: string
  full_name: string
  actividades: ('captacion' | 'ventas' | 'arriendos')[]
  elegible: boolean
  ocupado_con: { code: string; scheduled_at: string } | null
}
