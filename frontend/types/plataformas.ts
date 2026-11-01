import type { Cargo } from '~/types/auth'

export interface PlPersona {
  id: string
  full_name: string
  cargo: Cargo
}

export interface PlPlan {
  id: string
  precio: number
  activacion: string
  vencimiento: string
  cupo_total: number
  destacados_total: number
  alarma_dias: number
}

export interface PlataformaRow {
  id: string
  fuente: string
  nombre: string
  color: string
  activa: boolean
  responsable: PlPersona | null
  plan: PlPlan | null
  plan_estado: 'sin_plan' | 'activo' | 'por_vencer' | 'vencido' | 'renovado'
  plan_txt: string
  plan_cls: string
  cupo_total: number | null
  cupo_usado: number | null
  destacados_total: number | null
  destacados_usados: number | null
  ultima_at: string | null
  ultima_txt: string
  ultima_por: string | null
  estado: 'al_dia' | 'atrasada' | 'sin_actualizar'
  estado_txt: string
  estado_cls: string
  puede_registrar: boolean
}

export interface PlActualizacion {
  id: string
  plataforma_id: string
  plataforma: string
  realizada_at: string
  actualizado_por: string | null
  actualizado_por_id: string | null
  responsable: string | null
  es_responsable: boolean
  cupo_total: number
  cupo_usado: number
  destacados_total: number
  destacados_usados: number
  observacion: string | null
  dias_desde_anterior: number | null
  regla_dias: number
  a_tiempo: boolean
}

export interface PlTablero {
  plataformas: PlataformaRow[]
  dias_regla: number
  regla_confirmada: boolean
  mes_txt: string
  cupo_disponible: number
  destacados_disponibles: number
  desde: string
  hasta: string
  kpis: {
    al_dia: number
    total: number
    atrasadas: string[]
    actualizaciones: number
    a_tiempo: number
    a_tiempo_pct: number | null
    del_responsable: number
    del_responsable_pct: number | null
  }
  actualizaciones: PlActualizacion[]
}

export interface PlResultadoFila {
  plataforma_id: string
  nombre: string
  color: string
  leads: number
  citas: number
  cierres: number
  costo: number
  costo_lead: number | null
  costo_cierre: number | null
  conversion: number | null
  plan_estado: string
  plan_txt: string
  plan_cls: string
}

export interface PlResultados {
  desde: string
  hasta: string
  filas: PlResultadoFila[]
  kpis: { leads: number; cierres: number; conversion: number | null; costo: number; costo_lead: number | null; costo_cierre: number | null }
  barras: { mes: string; label: string; valores: { plataforma_id: string; leads: number }[] }[]
}

export interface PlHistorico {
  columnas: string[]
  filas: string[][]
  total: number
}

export interface PlOpciones {
  gerencia: boolean
  puede_descargar: boolean
  plataformas: { id: string; nombre: string; activa: boolean }[]
  responsables: PlPersona[]
  quienes: PlPersona[]
  desde: string
  hasta: string
}

export interface PlEvento {
  id: string
  plataforma: string | null
  tipo: string
  actor_name: string | null
  antes: string | null
  despues: string | null
  detalle: string | null
  created_at: string
}

export type PlQuery = { desde?: string; hasta?: string; plataforma_id?: string; quien_id?: string }
