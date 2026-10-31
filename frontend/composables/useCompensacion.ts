import type { CierreRead, CompItem, EventoComp, Mio, PagoRead, Salarios, Tablero } from '~/types/compensacion'

/** Compensación API (G05 · X04 · Z05 · M12–M14). */
export function useCompensacion() {
  const api = useApi()
  return {
    mio: () => api<Mio>('/compensacion/mio'),
    tablero: () => api<Tablero>('/compensacion'),
    crear: (clase: 'comisiones' | 'bonos', body: { beneficiario_id: string; concepto: string; valor: number; fecha?: string | null; detalle?: string | null; cierre_id?: string | null }) =>
      api<CompItem>(`/compensacion/${clase}`, { method: 'POST', body }),
    accion: (clase: 'comisiones' | 'bonos', id: string, accion: string, extra: { valor?: number; motivo?: string } = {}) =>
      api<CompItem>(`/compensacion/${clase}/${id}/accion`, { method: 'POST', body: { accion, ...extra } }),
    pagar: (id: string) => api<PagoRead>(`/compensacion/pagos/${id}/pagar`, { method: 'POST' }),
    ganancia: (id: string, ganancia: number, captador_id: string | null) =>
      api<CierreRead>(`/compensacion/cierres/${id}`, { method: 'PUT', body: { ganancia, captador_id } }),
    calcular: (periodo: string) => api<{ bonos: number; grupal: number }>('/compensacion/calcular', { method: 'POST', query: { periodo } }),
    config: (valores: Record<string, unknown>) => api<Record<string, unknown>>('/compensacion/config', { method: 'PUT', body: { valores } }),
    historial: (entidad: string, id: string) => api<EventoComp[]>(`/compensacion/historial/${entidad}/${id}`),
    salarios: (periodo: string, corte: number) => api<Salarios>('/compensacion/salarios', { query: { periodo, corte } }),
    accionSalarios: (accion: 'confirmar' | 'pagar', ids: string[]) =>
      api<{ actualizados: number }>('/compensacion/salarios/accion', { method: 'POST', body: { accion, ids } }),
    setSalario: (userId: string, salario_mensual: number) =>
      api<{ salario_mensual: number }>(`/compensacion/salarios/config/${userId}`, { method: 'PUT', body: { salario_mensual } }),
    async descargar(tab: 'comisiones' | 'bonos' | 'pagos') {
      const blob = await api<Blob>('/compensacion/export.csv', { query: { tab }, responseType: 'blob' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${tab}.csv`
      a.click()
      URL.revokeObjectURL(url)
    },
  }
}

/** Status chip colours (G05 / M12): generated = info, in the flow = warn, paid = ok. */
export const COMP_CLS: Record<string, string> = {
  generada: 'info',
  visto_bueno: 'warn',
  pendiente_pago: 'warn',
  pagada: 'ok',
  anulada: 'gray',
  en_proceso: 'warn',
  pagado: 'ok',
  por_confirmar: 'warn',
  confirmado: 'info',
}

/** «2 oct» */
export const diaMes = (iso: string) => {
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00-05:00` : iso)
  return new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', timeZone: 'America/Bogota' }).format(d).replace('.', '')
}
