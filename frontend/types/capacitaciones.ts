/** Z03 «Mis capacitaciones» · X07 «Capacitaciones del equipo» (backend: app/services/capacitaciones.py). */

export interface CapBase {
  id: string
  code: string
  origen: 'programada' | 'registrada'
  origen_txt: string
  tema: string
  area: string
  presenta: string
  lugar: string | null
  inicio_at: string
  cuando: string
  estado: 'programada' | 'realizada' | 'cancelada'
  cancelada_motivo: string | null
  participantes_txt: string | null
  creada_por: { id: string; full_name: string } | null
}

export interface CapMia extends CapBase {
  respuesta: 'pendiente' | 'acepta' | 'no'
  motivo: string | null
  motivo_detalle: string | null
  estado_txt: string
  estado_cls: string
  motivo_txt: string
  asistio: boolean | null
  aprendio: string | null
  observaciones: string | null
  empezo: boolean
}

export interface CapMias {
  persona: { full_name: string; cargo: string }
  programadas: CapMia[]
  por_responder: number
  historico: CapMia[]
  areas: string[]
  motivos: string[]
  organiza: boolean
}

export interface CapEquipoItem extends CapBase {
  si: number
  pe: number
  no: number
  puede_completar: boolean
  gente: { user_id: string; full_name: string; grupo: string; respuesta: string; estado_txt: string; estado_cls: string; motivo_txt: string; asistio: boolean | null; aprendio: string | null }[]
}

export interface CapEquipo {
  desde: string
  hasta: string
  kpis: { programadas: number; por_responder: number; registradas: number; no_participaron: number; con_motivo: number }
  programadas: CapEquipoItem[]
  registradas: (CapBase & { persona: { id: string; full_name: string } | null; aprendio: string | null; observaciones: string | null })[]
  puede_descargar: boolean
  areas: string[]
  participantes: Record<string, string>
  personas: { id: string; full_name: string; grupo: string }[]
}
