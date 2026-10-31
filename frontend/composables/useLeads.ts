import type {
  AccionIn,
  AccionSeguimiento,
  AsesorOption,
  Cita,
  CitaBucket,
  EstadoCita,
  EtapaLead,
  LeadDetail,
  LeadFields,
  LeadStats,
  LeadSummary,
  MotivoPerdida,
  TipoCita,
  UserRef,
} from '~/types/leads'

export type LeadQuery = {
  etapa?: EtapaLead[]
  abiertos?: boolean
  assigned?: string
  fuente?: string
  desde?: string
  hasta?: string
  q?: string
}

/** Atención y Preventa API (leads + citas). */
export function useLeads() {
  const api = useApi()
  const post = <T>(url: string, body?: object) => api<T>(url, { method: 'POST', body })
  return {
    list: (query: LeadQuery) => api<LeadSummary[]>('/leads', { query }),
    stats: (periodo: 'hoy' | 'semana' | 'mes') => api<LeadStats>('/leads/stats', { query: { periodo } }),
    responsables: () => api<UserRef[]>('/leads/responsables'),
    get: (id: string) => api<LeadDetail>(`/leads/${id}`),
    create: (body: Partial<LeadFields> & { seguir?: boolean }) => post<LeadDetail>('/leads', body),
    update: (id: string, body: Partial<LeadFields> & { assigned_to_id?: string | null }) =>
      api<LeadDetail>(`/leads/${id}`, { method: 'PATCH', body }),
    follow: (id: string) => post<LeadDetail>(`/leads/${id}/follow`),
    action: (id: string, body: AccionIn) => post<LeadDetail>(`/leads/${id}/actions`, body),
    followup: (id: string, body: { accion: AccionSeguimiento; due_at: string; nota?: string | null }) =>
      post<LeadDetail>(`/leads/${id}/followups`, body),
    completeFollowup: (id: string, segId: string, resultado: string) =>
      post<LeadDetail>(`/leads/${id}/followups/${segId}/complete`, { resultado }),
    stage: (id: string, etapa: EtapaLead, motivo?: MotivoPerdida | null) =>
      post<LeadDetail>(`/leads/${id}/stage`, { etapa, motivo }),

    citas: (query: { bucket?: CitaBucket; lead_id?: string }) =>
      api<{ items: Cita[]; counts: Record<CitaBucket, number> }>('/citas', { query }),
    asesores: (tipo: TipoCita, scheduled_at?: string, exclude?: string) =>
      api<AsesorOption[]>('/citas/asesores', { query: { tipo, scheduled_at, exclude } }),
    createCita: (body: {
      lead_id: string
      tipo: TipoCita
      scheduled_at: string
      asesor_id: string
      inmueble?: string | null
      notas?: string | null
    }) => post<Cita>('/citas', body),
    citaStatus: (id: string, estado: EstadoCita, motivo?: string | null) =>
      post<Cita>(`/citas/${id}/status`, { estado, motivo }),
    citaReassign: (id: string, asesor_id: string) => post<Cita>(`/citas/${id}/reassign`, { asesor_id }),
    citaReschedule: (id: string, scheduled_at: string, motivo: string) =>
      post<Cita>(`/citas/${id}/reschedule`, { scheduled_at, motivo }),
  }
}
