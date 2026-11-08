import type { CapEquipo, CapMias } from '~/types/capacitaciones'

/** Z03 / X07 API: everyone answers and registers; the Auxiliar, Coordinación and Gerencia program. */
export function useCapacitaciones() {
  const api = useApi()
  const post = <T = unknown>(url: string, body?: object) => api<T>(url, { method: 'POST', body })
  return {
    mias: () => api<CapMias>('/capacitaciones/mias'),
    equipo: (query: { desde?: string; hasta?: string }) => api<CapEquipo>('/capacitaciones/equipo', { query }),
    programar: (body: object) => post<{ id: string; code: string; participantes: number }>('/capacitaciones', body),
    registrar: (body: object) => post<{ id: string; code: string }>('/capacitaciones/registrar', body),
    responder: (id: string, body: { acepta: boolean; motivo?: string | null; detalle?: string | null }) => post(`/capacitaciones/${id}/responder`, body),
    completar: (id: string, asistentes: string[]) => post<{ participaron: number }>(`/capacitaciones/${id}/completar`, { asistentes }),
    cancelar: (id: string, motivo: string) => post(`/capacitaciones/${id}/cancelar`, { motivo }),
    aprendizaje: (id: string, aprendio: string, observaciones?: string | null) => post(`/capacitaciones/${id}/aprendizaje`, { aprendio, observaciones: observaciones || null }),
  }
}
