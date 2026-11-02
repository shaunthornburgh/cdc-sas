import type { PolAseguradoras, PolComparar, PolFila, PolOpciones, PolTablero } from '~/types/polizas'

/** X11 «Pólizas» API (Auxiliar administrativa y Gerencia). */
export function usePolizas() {
  const api = useApi()
  const post = <T = PolFila>(url: string, body?: object) => api<T>(url, { method: 'POST', body })
  return {
    tablero: (query: { desde?: string; hasta?: string; aseguradora_id?: string }) => api<PolTablero>('/polizas', { query }),
    opciones: () => api<PolOpciones>('/polizas/opciones'),
    comparar: (query: { desde?: string; hasta?: string }) => api<PolComparar>('/polizas/comparar', { query }),
    ver: (id: string) => api<PolFila>(`/polizas/${id}`),
    crear: (body: object) => post('/polizas', body),
    editar: (id: string, body: object) => api<PolFila>(`/polizas/${id}`, { method: 'PATCH', body }),
    decidir: (id: string, aprobada: boolean, motivo?: string) => post(`/polizas/${id}/decidir`, { aprobada, motivo }),
    retomar: (id: string, motivo: string) => post(`/polizas/${id}/retomar`, { motivo }),
    firma: (id: string, fecha: string) => post(`/polizas/${id}/firma`, { fecha }),
    activar: (id: string, body: { fecha: string; numero: string; soporte: boolean }) => post(`/polizas/${id}/activar`, body),
    terminar: (id: string, fecha: string) => post(`/polizas/${id}/terminar`, { fecha }),
    eliminar: (id: string, motivo: string) => post<null>(`/polizas/${id}/eliminar`, { motivo }),
    aseguradoras: () => api<PolAseguradoras>('/polizas/aseguradoras'),
    crearAseguradora: (body: object) => post<{ id: string; nombre: string }>('/polizas/aseguradoras', body),
    editarAseguradora: (id: string, body: object) => api(`/polizas/aseguradoras/${id}`, { method: 'PATCH', body }),
    agregarTipo: (id: string, body: object) => post<{ id: string; nombre: string }>(`/polizas/aseguradoras/${id}/tipos`, body),
    eliminarAseguradora: (id: string) => api(`/polizas/aseguradoras/${id}`, { method: 'DELETE' }),
  }
}
