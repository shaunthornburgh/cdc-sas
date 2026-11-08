/** G11 «Pausas activas» (backend: app/services/pausas.py). */

export interface PaSlot {
  fecha: string
  turno: 'manana' | 'tarde'
  turno_txt: string
  programada: string
  estado: 'realizada' | 'no_realizada' | 'en_curso' | 'programada' | 'ausencia'
  estado_txt: string
  estado_cls: string
  realizada_at: string | null
}

export interface PaAhora {
  mensaje: string
  minutos: number
  activa: { turno: string; titulo: string; hasta: string } | null
  hoy: PaSlot[]
  horario: { manana: string; tarde: string }
}

export interface PaDia {
  fecha: string
  user_id: string
  full_name: string
  manana?: PaSlot
  tarde?: PaSlot
}

export interface PaMias {
  desde: string
  hasta: string
  resumen: { pct: number | null; realizadas: number; no_realizadas: number }
  dias: PaDia[]
  ve_equipo: boolean
}

export interface PaKpi {
  hechas: number
  total: number
  faltan: string[]
  estado: 'cerrada' | 'en_curso' | 'programada'
  hora: string
}

export interface PaEquipo {
  desde: string
  hasta: string
  hoy: string
  habil: boolean
  config: { hora_manana: string; hora_tarde: string; manana_txt: string; tarde_txt: string; minutos: number; mensaje: string }
  kpis: { manana: PaKpi; tarde: PaKpi; pct: number | null; faltas: number }
  hoy_filas: { user_id: string; full_name: string; cargo: string; manana: PaSlot; tarde: PaSlot }[]
  persona: { full_name: string; dias: PaDia[] } | null
  personas: { id: string; full_name: string }[]
  puede: { horario: boolean; mensaje: boolean; descargar: boolean }
  rol: string
}
