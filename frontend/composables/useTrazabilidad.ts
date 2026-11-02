import type { RcLista, RcOpciones, RcQuery } from '~/types/trazabilidad'

/** G06 «Registro de cambios» API. */
export function useTrazabilidad() {
  const api = useApi()
  return {
    opciones: () => api<RcOpciones>('/registro-cambios/opciones'),
    list: (query: RcQuery) => api<RcLista>('/registro-cambios', { query }),
    async descargar(query: RcQuery) {
      const blob = await api<Blob>('/registro-cambios/export.csv', { query, responseType: 'blob' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `CDC_Registro_de_cambios_${query.desde ?? ''}_a_${query.hasta ?? ''}.csv`
      a.click()
      URL.revokeObjectURL(url)
    },
  }
}
