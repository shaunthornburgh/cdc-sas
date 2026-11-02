export type RutaEstado = 'por_aceptar' | 'aceptada' | 'rechazada' | 'cancelada'

export interface RutaZona {
  id?: string
  zona: string
  hora_inicio: string
  hora_fin: string
  dias: number[]
}

export interface Ruta {
  id: string
  asesor_id: string
  asesor: string
  desde: string
  hasta: string
  dias: number[]
  zonas: RutaZona[]
  periodo_txt: string
  dias_txt: string
  zonas_txt: string
  observacion: string | null
  origen: 'manual' | 'excel'
  estado: RutaEstado
  estado_txt: string
  estado_cls: string
  motivo_txt: string | null
  asignada: string
  calificacion: number | null
  puede_cancelar: boolean
  puede_reenviar: boolean
  puede_calificar: boolean
  puede_responder: boolean
}

export interface RutasOpciones {
  puede_programar: boolean
  puede_consultar: boolean
  puede_calificar: boolean
  es_captador: boolean
  asesores: { id: string; nombre: string }[]
  zonas: string[]
  motivos: Record<string, string>
  dias: Record<string, string>
  estados: Record<string, string>
  hoy: string
  proximo_lunes: string
}

export interface MiRuta {
  fecha: string
  timeline: { id: string; tipo: 'ruta' | 'cita' | 'mia'; hora: string; titulo: string; sub: string; estado_txt: string; estado_cls: string; link: string | null }[]
  hechos: number
  total: number
  siguiente: { id: string; zona: string; hora: string } | null
  por_aceptar: Ruta[]
  aceptadas: Ruta[]
  motivos: Record<string, string>
}

export interface Ubicacion {
  id: string
  nombre: string
  cargo: string
  donde: string
  cls: string
  nota: string | null
}

export interface ImportRev {
  filas: { fila: number; asesor: string; periodo: string; zonas: string; error: string | null }[]
  correctas: number
  total: number
  asignadas: number
}
