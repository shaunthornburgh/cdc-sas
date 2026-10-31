import type { Cargo } from '~/types/auth'

export type TipoNovedad = 'incapacidad' | 'permiso_no_remunerado' | 'permiso_remunerado'
export type EstadoNovedad = 'registrada' | 'anulada'

export interface Empleado {
  id: string
  full_name: string
  cargo: Cargo
}

export interface Novedad {
  id: string
  code: string
  empleado: Empleado
  tipo: TipoNovedad
  tipo_txt: string
  descuenta: boolean
  desde: string
  hasta: string
  fechas_txt: string
  dias: number
  observacion: string | null
  soportes: number
  estado: EstadoNovedad
  estado_txt: string
  registrada_por_name: string | null
  created_at: string
  anulada_por_name: string | null
  anulada_at: string | null
  motivo_anulacion: string | null
  puede_editar: boolean
}

export interface NovedadList {
  items: Novedad[]
  desde: string
  hasta: string
  dias: Record<TipoNovedad, number>
  preop_sin_revisar: number
}

export interface NovedadOpciones {
  tipos: Record<TipoNovedad, string>
  ayudas: Record<TipoNovedad, string>
  descontables: TipoNovedad[]
  empleados: Empleado[]
  puede_registrar: boolean
  desde: string
  hasta: string
}

export interface PreopNovedad {
  id: string
  empleado: Empleado
  fecha: string
  realizado_at: string
  medio: string
  texto: string
  revisado: boolean
  revisado_por_name: string | null
  revisado_at: string | null
  revision_nota: string | null
  puede_revisar: boolean
}

export type NovedadQuery = { desde?: string; hasta?: string; tipo?: string; empleado_id?: string; anuladas?: boolean }
