import type { Cambio, ConfigRead, Empresa, Equipo, Resultado } from '~/types/rendimiento'

/** Rendimiento API (K07 · K14 · K18 · M08 · C04 · G12). */
export function useRendimiento() {
  const api = useApi()
  const q = (periodo?: string | null) => (periodo ? { periodo } : {})
  return {
    mio: (periodo?: string | null) => api<Resultado>('/rendimiento/mio', { query: q(periodo) }),
    persona: (id: string, periodo?: string | null) => api<Resultado>(`/rendimiento/personas/${id}`, { query: q(periodo) }),
    equipo: (periodo?: string | null) => api<Equipo>('/rendimiento/equipo', { query: q(periodo) }),
    empresa: (periodo?: string | null) => api<Empresa>('/rendimiento/empresa', { query: q(periodo) }),
    config: (id: string) => api<ConfigRead>(`/rendimiento/config/${id}`),
    guardarPesos: (id: string, pesos: Record<string, number>) => api<ConfigRead>(`/rendimiento/config/${id}/pesos`, { method: 'PUT', body: { pesos } }),
    guardarMetas: (id: string, metas: Record<string, number>) => api<ConfigRead>(`/rendimiento/config/${id}/metas`, { method: 'PUT', body: { metas } }),
    calificar: (id: string, valores: Record<string, number>) => api<Resultado>(`/rendimiento/calificaciones/${id}`, { method: 'PUT', body: { valores } }),
    cambios: (id: string) => api<Cambio[]>(`/rendimiento/cambios/${id}`),
    /** Download the team as CSV (opens in Excel). Goes through the API so the token is sent. */
    async descargar(periodo: string) {
      const blob = await api<Blob>('/rendimiento/equipo.csv', { query: q(periodo), responseType: 'blob' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `rendimiento-${periodo}.csv`
      a.click()
      URL.revokeObjectURL(url)
    },
  }
}
