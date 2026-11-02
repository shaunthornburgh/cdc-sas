import type { AgEntrada, AgPersona, AgVista } from '~/types/agenda'

/** Agenda API (G09, M17 / C07 / X06, K19; G-088, G-089). */
export function useAgenda() {
  const api = useApi()
  return {
    personas: () => api<AgPersona[]>('/agenda/personas'),
    vista: (query: { user_id?: string; desde: string; hasta: string }) => api<AgVista>('/agenda', { query }),
    agregar: (body: object) => api<AgEntrada>('/agenda', { method: 'POST', body }),
    hecha: (id: string) => api<AgEntrada>(`/agenda/${id}/hecha`, { method: 'POST' }),
    rechazar: (id: string, motivo: string) => api<AgEntrada>(`/agenda/${id}/rechazar`, { method: 'POST', body: { motivo } }),
    justificar: (id: string, motivo: string) => api<AgEntrada>(`/agenda/${id}/justificar`, { method: 'POST', body: { motivo } }),
    eliminar: (id: string) => api(`/agenda/${id}`, { method: 'DELETE' }),
  }
}

/** G09's legend colours (one per kind of item). */
export const AG_COLOR: Record<string, string> = {
  cita: '#6B4FA0',
  seg: '#B7791F',
  ped: '#A3271B',
  ctl: '#2F6F9F',
  mia: '#0F766E',
  asg: '#C2410C',
  ruta: '#00843D',
}
