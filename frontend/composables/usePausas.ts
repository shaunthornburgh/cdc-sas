import type { PaAhora, PaEquipo, PaMias } from '~/types/pausas'

/** G11 «Pausas activas» API: everyone marks theirs; the Auxiliar, Coordinación and Gerencia see the team. */
export function usePausas() {
  const api = useApi()
  return {
    ahora: () => api<PaAhora>('/pausas-activas/ahora'),
    realizada: () => api<{ turno: string; realizada_at: string }>('/pausas-activas/realizada', { method: 'POST' }),
    mias: (query: { desde?: string; hasta?: string }) => api<PaMias>('/pausas-activas/mias', { query }),
    equipo: (query: { desde?: string; hasta?: string; user_id?: string }) => api<PaEquipo>('/pausas-activas/equipo', { query }),
    horario: (body: { hora_manana: string; hora_tarde: string; minutos: number }) => api('/pausas-activas/horario', { method: 'PUT', body }),
    mensaje: (mensaje: string) => api('/pausas-activas/mensaje', { method: 'PUT', body: { mensaje } }),
  }
}
