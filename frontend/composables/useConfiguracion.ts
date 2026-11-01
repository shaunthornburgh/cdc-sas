import type { ConfigPagina, Marca, Pagos, Pendiente } from '~/types/configuracion'

/** Z02 «Configuración» API. */
export function useConfiguracion() {
  const api = useApi()
  return {
    pagina: () => api<ConfigPagina>('/configuracion'),
    marca: (body: Partial<Marca>) => api<Marca>('/configuracion/marca', { method: 'PUT', body }),
    restaurarMarca: () => api<Marca>('/configuracion/marca/restaurar', { method: 'POST' }),
    pagos: (body: Pagos) => api<Pagos>('/configuracion/pagos', { method: 'PUT', body }),
    seccion: (seccion: string, body: object) => api<Record<string, unknown>>(`/configuracion/${seccion}`, { method: 'PUT', body }),
    pendiente: (clave: string, resuelto: boolean) =>
      api<Pendiente[]>(`/configuracion/pendientes/${clave}`, { method: 'PUT', body: { resuelto } }),
    usoReal: () => api<Record<string, unknown>>('/configuracion/uso-real', { method: 'POST' }),
  }
}
