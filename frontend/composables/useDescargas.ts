import type { DsOpciones, DsQuery, DsVistaPrevia } from '~/types/descargas'

/** X10 «Descargas del personal» API (Auxiliar administrativa, Gerencia, Coordinación). */
export function useDescargas() {
  const api = useApi()
  return {
    opciones: () => api<DsOpciones>('/descargas'),
    vistaPrevia: (tipo: string, query: DsQuery) => api<DsVistaPrevia>(`/descargas/${tipo}/vista-previa`, { query }),
    async descargar(tipo: string, query: DsQuery, archivo: string) {
      const blob = await api<Blob>(`/descargas/${tipo}.csv`, { query, responseType: 'blob' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = archivo
      a.click()
      URL.revokeObjectURL(url)
    },
  }
}
