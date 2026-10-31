import type { Cargo } from '~/types/auth'

export type MedioTransporte = 'carro' | 'moto' | 'bicicleta' | 'transporte_publico' | 'a_pie' | 'otro'
export type EstadoDia = 'realizado' | 'novedad' | 'no_realizado' | 'pendiente' | 'futuro' | 'fin_de_semana' | 'sin_contar'
export type EstadoEquipo = 'realizado' | 'reporte' | 'novedad' | 'sin_realizar' | 'desactivado' | 'fin_de_semana'

export interface PreoperacionalT {
  id: string
  fecha: string
  realizado_at: string
  medio: MedioTransporte
  placa: string | null
  respuestas: { pregunta: string; si: boolean }[]
  respuestas_no: number[]
  observaciones: string | null
  tiene_novedad: boolean
  revisado_por_name: string | null
  revisado_at: string | null
  revision_nota: string | null
  user: { id: string; full_name: string }
}

export interface Formulario {
  activo: boolean
  medios: Record<MedioTransporte, string>
  preguntas: Partial<Record<MedioTransporte, string[]>>
  hoy: string
  registro_de_hoy: PreoperacionalT | null
  destinatario: string
}

export interface ResumenMes {
  dias_habiles: number
  cumplidos: number
  novedades: number
  pct: number | null
  puntaje: number | null
  descuento: number
}

export interface Historial {
  mes: string
  activo: boolean
  resumen: ResumenMes
  dias: { fecha: string; estado: EstadoDia }[]
  eventos: { fecha: string; tipo: 'novedad' | 'no_realizado'; registro: PreoperacionalT | null }[]
  registros: PreoperacionalT[]
}

export interface EquipoPreop {
  fecha: string
  mes: string
  config: Record<Cargo, boolean>
  kpis: { total: number; realizados: number; con_novedad: number; novedades_sin_revisar: number; sin_realizar: number; cumplimiento_mes_anterior: number | null }
  filas: { user: { id: string; full_name: string; cargo: Cargo }; estado: EstadoEquipo; registro: PreoperacionalT | null }[]
  mes_rows: { user: { id: string; full_name: string; cargo: Cargo }; resumen: ResumenMes }[]
}
