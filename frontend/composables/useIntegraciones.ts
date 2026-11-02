import type { IntDetalle, IntTablero } from '~/types/integraciones'

/** G07 «Integraciones» API (Gerencia). */
export function useIntegraciones() {
  const api = useApi()
  return {
    tablero: (query: { desde?: string; hasta?: string }) => api<IntTablero>('/integraciones', { query }),
    detalle: (id: string, query: { desde?: string; hasta?: string }) => api<IntDetalle>(`/integraciones/${id}`, { query }),
    agregar: (body: object) => api<IntDetalle>('/integraciones', { method: 'POST', body }),
    guardar: (id: string, valores: Record<string, string | null>) =>
      api<{ estado: string; estado_txt: string }>(`/integraciones/${id}/datos`, { method: 'PUT', body: { valores } }),
    probar: (id: string) => api<{ ok: boolean; txt: string }>(`/integraciones/${id}/probar`, { method: 'POST' }),
    desconectar: (id: string) => api(`/integraciones/${id}/desconectar`, { method: 'POST' }),
    ajustes: (id: string, body: object) => api(`/integraciones/${id}`, { method: 'PATCH', body }),
  }
}
