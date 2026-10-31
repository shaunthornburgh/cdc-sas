import type { MotivoPerdidaPedido, Pedido, PedidoIn, PedidoList, PedidoOpciones } from '~/types/pedidos'
import type { TipoNegocio } from '~/types/leads'

export type PedidoQuery = {
  vista: 'mis' | 'equipo' | 'todos' | 'vencidos'
  negocio?: TipoNegocio
  zona?: string
  rango?: string
  proximos?: boolean
  responsable_id?: string
  cerrados?: boolean
  q?: string
}

/** Pedidos API (prototypes K06 / M06 / C10). */
export function usePedidos() {
  const api = useApi()
  const post = (url: string, body?: object) => api<Pedido>(url, { method: 'POST', body })
  return {
    opciones: () => api<PedidoOpciones>('/pedidos/opciones'),
    list: (query: PedidoQuery) => api<PedidoList>('/pedidos', { query }),
    create: (body: PedidoIn) => post('/pedidos', body),
    actualizar: (id: string, body: Partial<PedidoIn> & { que_cambio: string }) => api<Pedido>(`/pedidos/${id}`, { method: 'PATCH', body }),
    extender: (id: string, fecha_limite: string, motivo: string) => post(`/pedidos/${id}/extender`, { fecha_limite, motivo }),
    atendido: (id: string, nota?: string | null) => post(`/pedidos/${id}/atendido`, { nota }),
    perdido: (id: string, motivo: MotivoPerdidaPedido, nota?: string | null) => post(`/pedidos/${id}/perdido`, { motivo, nota }),
    proponer: (id: string, inmueble: string, nota?: string | null) => post(`/pedidos/${id}/proponer`, { inmueble, nota }),
    comentar: (id: string, texto: string) => post(`/pedidos/${id}/comentar`, { texto }),
    reasignar: (id: string, responsable_id: string) => post(`/pedidos/${id}/reasignar`, { responsable_id }),
  }
}

/** K06 / M06 status chips. */
export const PEDIDO_ESTADO: Record<string, { t: string; cls: string }> = {
  nuevo: { t: 'Nuevo · abierto', cls: 'ok' },
  abierto: { t: 'Abierto', cls: 'gray' },
  urgente: { t: 'Urgente', cls: 'bad' },
  vence_hoy: { t: 'Vence hoy', cls: 'warn' },
  vencido: { t: 'Vencido · sin decidir', cls: 'warn' },
  atendido: { t: 'Atendido', cls: 'ok' },
  recuperado: { t: 'Recuperado', cls: 'info' },
  perdido: { t: '■ Cliente perdido', cls: 'bad' },
}

/** «hasta $2.000.000» */
export const presupuestoTxt = (n: number) => `hasta ${fmtCOP(n)}`

/** Parse «$2.500.000» / «2500000» typed by a person. */
export const parsePesos = (v: string) => Number(v.replace(/[^\d]/g, '')) || 0
