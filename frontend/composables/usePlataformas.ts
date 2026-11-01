import type { PlActualizacion, PlEvento, PlHistorico, PlOpciones, PlQuery, PlResultados, PlTablero, PlataformaRow } from '~/types/plataformas'

/** K15 «Actualización de plataformas» / K15-ger «Plataformas tradicionales» API. */
export function usePlataformas() {
  const api = useApi()
  return {
    opciones: () => api<PlOpciones>('/plataformas/opciones'),
    tablero: (query: PlQuery) => api<PlTablero>('/plataformas', { query }),
    resultados: (query: PlQuery) => api<PlResultados>('/plataformas/resultados', { query }),
    historico: (query: PlQuery) => api<PlHistorico>('/plataformas/historico', { query }),
    cambios: () => api<PlEvento[]>('/plataformas/cambios'),
    registrar: (id: string, body: object) => api<PlActualizacion>(`/plataformas/${id}/actualizaciones`, { method: 'POST', body }),
    responsable: (id: string, responsable_id: string | null) =>
      api<PlataformaRow>(`/plataformas/${id}/responsable`, { method: 'PUT', body: { responsable_id } }),
    plan: (id: string, body: object) => api<PlataformaRow>(`/plataformas/${id}/planes`, { method: 'POST', body }),
    activa: (id: string, activa: boolean) => api<PlataformaRow>(`/plataformas/${id}/activa`, { method: 'PUT', body: { activa } }),
    regla: (dias_regla: number) => api<{ dias_regla: number }>('/plataformas/regla', { method: 'PUT', body: { dias_regla } }),
    async descargar(query: PlQuery) {
      const blob = await api<Blob>('/plataformas/historico.csv', { query, responseType: 'blob' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `CDC_Historico_Plataformas_${query.desde ?? ''}_a_${query.hasta ?? ''}.csv`
      a.click()
      URL.revokeObjectURL(url)
    },
  }
}
