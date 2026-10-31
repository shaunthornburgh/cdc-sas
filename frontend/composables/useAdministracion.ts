import type {
  AdminQuery,
  AdminResumen,
  EstadoReparacion,
  EstadoSolicitud,
  Inventario,
  Reparacion,
  Solicitud,
} from '~/types/administracion'

/** Administración de inmuebles API (X14): inventories, repairs and owner / tenant requests. */
export function useAdministracion() {
  const api = useApi()
  const B = '/administracion-inmuebles'
  const post = <T>(url: string, body?: object) => api<T>(url, { method: 'POST', body })
  const patch = <T>(url: string, body: object) => api<T>(url, { method: 'PATCH', body })
  return {
    resumen: () => api<AdminResumen>(`${B}/resumen`),

    inventarios: (query: AdminQuery) => api<Inventario[]>(`${B}/inventarios`, { query }),
    crearInventario: (body: object) => post<Inventario>(`${B}/inventarios`, body),
    ambiente: (id: string, ambienteId: string, body: object) =>
      patch<Inventario>(`${B}/inventarios/${id}/ambientes/${ambienteId}`, body),
    firmar: (id: string) => post<Inventario>(`${B}/inventarios/${id}/firmar`),
    reparacionDesde: (id: string) => post<Reparacion>(`${B}/inventarios/${id}/reparacion`),
    eliminarInventario: (id: string) => api(`${B}/inventarios/${id}`, { method: 'DELETE' }),

    reparaciones: (query: AdminQuery) => api<Reparacion[]>(`${B}/reparaciones`, { query }),
    crearReparacion: (body: object) => post<Reparacion>(`${B}/reparaciones`, body),
    avance: (id: string, body: object) => post<Reparacion>(`${B}/reparaciones/${id}/avance`, body),
    estadoReparacion: (id: string, estado: EstadoReparacion) =>
      post<Reparacion>(`${B}/reparaciones/${id}/estado`, { estado }),
    eliminarReparacion: (id: string) => api(`${B}/reparaciones/${id}`, { method: 'DELETE' }),

    solicitudes: (query: AdminQuery) => api<Solicitud[]>(`${B}/solicitudes`, { query }),
    crearSolicitud: (body: object) => post<Solicitud>(`${B}/solicitudes`, body),
    responder: (id: string, respuesta: string) =>
      post<Solicitud>(`${B}/solicitudes/${id}/responder`, { respuesta }),
    estadoSolicitud: (id: string, estado: EstadoSolicitud, nota?: string | null) =>
      post<Solicitud>(`${B}/solicitudes/${id}/estado`, { estado, nota }),
    eliminarSolicitud: (id: string) => api(`${B}/solicitudes/${id}`, { method: 'DELETE' }),
  }
}

/** Chip colour per status (X14). */
export const INV_CLS: Record<string, string> = { programado: 'info', realizado: 'warn', con_novedades: 'bad', firmado: 'ok' }
export const REP_CLS: Record<string, string> = { recibida: 'warn', cotizada: 'info', aprobada: 'info', en_ejecucion: 'info', terminada: 'ok' }
export const SOL_CLS: Record<string, string> = { abierta: 'warn', en_tramite: 'info', respondida: 'ok', cerrada: 'gray' }

