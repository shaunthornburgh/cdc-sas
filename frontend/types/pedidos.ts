import type { TipoInmueble } from '~/types/captaciones'
import type { TipoNegocio, UserRef } from '~/types/leads'

export type EstadoPedido = 'abierto' | 'atendido' | 'perdido'
export type EstadoVisible = 'nuevo' | 'abierto' | 'urgente' | 'vence_hoy' | 'vencido' | 'atendido' | 'recuperado' | 'perdido'
export type Urgencia = 'normal' | 'alta' | 'urgente'
export type MotivoPerdidaPedido = 'no_interesaron' | 'compro_con_otro' | 'presupuesto' | 'no_responde' | 'otro'

export interface Pedido {
  id: string
  code: string
  cliente_nombre: string
  cliente_telefono: string | null
  lead_id: string | null
  negocio: TipoNegocio
  tipo_inmueble: TipoInmueble
  zona: string
  presupuesto: number
  observaciones: string | null
  fecha_limite: string
  urgencia: Urgencia
  estado: EstadoPedido
  vencio: boolean
  motivo_perdida: MotivoPerdidaPedido | null
  cerrado_at: string | null
  responsable: UserRef
  created_by_name: string | null
  created_at: string
  estado_visible: EstadoVisible
  vencido: boolean
  proximo_a_vencer: boolean
  can_edit: boolean
  eventos: { tipo: string; titulo: string; detalle: string | null; datos: Record<string, unknown>; created_by_name: string | null; created_at: string }[]
}

export interface PedidoList {
  items: Pedido[]
  kpis: { abiertos: number; proximos_a_vencer: number; vencidos_mes: number; vencidos_sin_decidir: number }
}

export interface PedidoOpciones {
  zonas: string[]
  rangos: Record<string, string>
  motivos: Record<MotivoPerdidaPedido, string>
  responsables: UserRef[]
}

export type PedidoIn = {
  cliente_nombre: string
  cliente_telefono?: string | null
  lead_id?: string | null
  negocio: TipoNegocio
  tipo_inmueble: TipoInmueble
  zona: string
  presupuesto: number
  fecha_limite: string
  urgencia?: Urgencia
  observaciones?: string | null
  responsable_id?: string | null
  otra_necesidad?: boolean
}
