import type { AsesorCita, AsesorInicio, MisCitas } from '~/types/asesor'

/** Asesor home (M01/M02) and their citas (M03). `asesorId` lets managers look at one. */
export function useAsesor() {
  const api = useApi()
  const q = (asesorId?: string | null) => (asesorId ? { asesor_id: asesorId } : undefined)
  const post = (url: string, body?: object) => api<AsesorCita>(url, { method: 'POST', body })
  return {
    inicio: (asesorId?: string | null) => api<AsesorInicio>('/asesor/inicio', { query: q(asesorId) }),
    citas: (asesorId?: string | null) => api<MisCitas>('/asesor/citas', { query: q(asesorId) }),
    aceptar: (id: string) => post(`/asesor/citas/${id}/aceptar`),
    rechazar: (id: string, motivo: string, observacion: string) => post(`/asesor/citas/${id}/rechazar`, { motivo, observacion }),
    tomar: (id: string) => post(`/asesor/citas/${id}/tomar`),
    cerrar: (id: string, resultado: string) => post(`/asesor/citas/${id}/cerrar`, { resultado }),
  }
}

/** Same list as services.citas.MOTIVOS_RECHAZO_ASESOR. */
export const MOTIVOS_RECHAZO_CITA = ['Choque con otra cita', 'La zona no me corresponde', 'Sin disponibilidad en ese horario', 'Otro']
