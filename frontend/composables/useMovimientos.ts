import type { MovConfig, MovEvento, Movimiento, MovimientoList, MovOpciones, MovPanel, MovQuery } from '~/types/movimientos'

/** K05 «Movimientos y GPS» API: alerts, justification, review, field work and config. */
export function useMovimientos() {
  const api = useApi()
  const post = (id: string, accion: string, body: object = {}) =>
    api<Movimiento>(`/movimientos/${id}/${accion}`, { method: 'POST', body })
  return {
    opciones: () => api<MovOpciones>('/movimientos/opciones'),
    list: (query: MovQuery) => api<MovimientoList>('/movimientos', { query }),
    panel: () => api<MovPanel>('/movimientos/panel'),
    historial: (id: string) => api<MovEvento[]>(`/movimientos/${id}/historial`),
    justificar: (id: string, body: object) => post(id, 'justificar', body),
    aprobar: (id: string, nota?: string | null) => post(id, 'aprobar', { nota: nota || null }),
    rechazar: (id: string, nota?: string | null) => post(id, 'rechazar', { nota: nota || null }),
    iniciarCampo: (body: object) => api<Movimiento>('/movimientos/campo', { method: 'POST', body }),
    finalizar: (id: string) => post(id, 'finalizar'),
    ubicacion: (id: string) => api<{ lat: number; lng: number; lugar: string | null }>(`/movimientos/${id}/ubicacion`, { method: 'POST' }),
    guardarConfig: (body: object) => api<MovConfig>('/movimientos/config', { method: 'PUT', body }),
    async descargar(query: MovQuery) {
      const blob = await api<Blob>('/movimientos/export.csv', { query, responseType: 'blob' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `CDC_Movimientos_GPS_${query.desde}_a_${query.hasta}.csv`
      a.click()
      URL.revokeObjectURL(url)
    },
  }
}
