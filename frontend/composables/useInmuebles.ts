import type { EstadoInmueble, Inmueble, InmuebleIn, InmuebleList, InmuebleOpciones, OpcionLead } from '~/types/inmuebles'

export type InmuebleQuery = {
  vista?: 'todos' | 'mios'
  estado?: string
  negocio?: string
  tipo?: string
  zona?: string
  rango?: string
  habitaciones?: number
  incompletos?: boolean
  q?: string
}

/** Property catalog API. */
export function useInmuebles() {
  const api = useApi()
  return {
    opciones: () => api<InmuebleOpciones>('/inmuebles/opciones'),
    list: (query: InmuebleQuery) => api<InmuebleList>('/inmuebles', { query }),
    get: (id: string) => api<Inmueble>(`/inmuebles/${id}`),
    create: (body: InmuebleIn) => api<Inmueble>('/inmuebles', { method: 'POST', body }),
    update: (id: string, body: InmuebleIn) => api<Inmueble>(`/inmuebles/${id}`, { method: 'PATCH', body }),
    estado: (id: string, estado: EstadoInmueble, nota?: string | null) =>
      api<Inmueble>(`/inmuebles/${id}/estado`, { method: 'POST', body: { estado, nota } }),
    remove: (id: string) => api(`/inmuebles/${id}`, { method: 'DELETE' }),
    paraLead: (leadId: string) => api<OpcionLead[]>(`/inmuebles/para-lead/${leadId}`),
  }
}

export const INM_ESTADO_CLS: Record<EstadoInmueble, string> = {
  disponible: 'ok',
  separado: 'warn',
  arrendado: 'info',
  vendido: 'info',
  retirado: 'gray',
}
