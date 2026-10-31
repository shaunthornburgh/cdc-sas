import type { Captacion, CaptacionCreate, CaptacionDetalles, CaptacionList, EstadoCaptacion, MotivoRechazoCaptacion } from '~/types/captaciones'
import type { TipoNegocio, UserRef } from '~/types/leads'

export type CaptacionQuery = {
  estado?: EstadoCaptacion[]
  asesor_id?: string
  negocio?: TipoNegocio
  publicada?: boolean
  desde?: string
  hasta?: string
  q?: string
}

/** Captaciones API (prototypes K12 / M15). */
export function useCaptaciones() {
  const api = useApi()
  const post = <T>(url: string, body?: object) => api<T>(url, { method: 'POST', body })
  return {
    list: (query: CaptacionQuery) => api<CaptacionList>('/captaciones', { query }),
    captadores: () => api<UserRef[]>('/captaciones/captadores'),
    get: (id: string) => api<Captacion>(`/captaciones/${id}`),
    create: (body: CaptacionCreate) => post<Captacion>('/captaciones', body),
    update: (id: string, body: Partial<CaptacionDetalles & { negocio: TipoNegocio; codigo_inmueble: string; direccion: string; modo: string }>) =>
      api<Captacion>(`/captaciones/${id}`, { method: 'PATCH', body }),
    remove: (id: string) => api<void>(`/captaciones/${id}`, { method: 'DELETE' }),
    verificar: (id: string, estado: EstadoCaptacion, motivo?: MotivoRechazoCaptacion | null, observacion?: string | null) =>
      post<Captacion>(`/captaciones/${id}/status`, { estado, motivo, observacion }),
    reenviar: (id: string, codigo_inmueble: string, direccion: string) =>
      post<Captacion>(`/captaciones/${id}/resubmit`, { codigo_inmueble, direccion }),
    publicar: (id: string) => post<Captacion>(`/captaciones/${id}/publish`),
    reasignar: (id: string, asesor_id: string) => post<Captacion>(`/captaciones/${id}/reassign`, { asesor_id }),
  }
}

/** Browser location for a captación (null if unavailable or refused). */
export function tomarUbicacion(timeoutMs = 8000): Promise<{ lat: number; lng: number; precision_m: number } | null> {
  if (import.meta.server || !('geolocation' in navigator)) return Promise.resolve(null)
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude, precision_m: Math.round(p.coords.accuracy) }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60_000 },
    )
  })
}
