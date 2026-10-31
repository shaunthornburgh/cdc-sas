import type { Novedad, NovedadList, NovedadOpciones, NovedadQuery, PreopNovedad } from '~/types/novedades'

/** K13 «Ausencias y permisos» API. Preoperacional novedades are reviewed in that module. */
export function useNovedades() {
  const api = useApi()
  return {
    opciones: () => api<NovedadOpciones>('/novedades/opciones'),
    list: (query: NovedadQuery) => api<NovedadList>('/novedades', { query }),
    create: (body: object) => api<{ novedad: Novedad; avisos: string[] }>('/novedades', { method: 'POST', body }),
    update: (id: string, body: object) => api<Novedad>(`/novedades/${id}`, { method: 'PATCH', body }),
    anular: (id: string, motivo: string) =>
      api<{ novedad: Novedad; avisos: string[] }>(`/novedades/${id}/anular`, { method: 'POST', body: { motivo } }),
    preoperacional: (query: NovedadQuery) => api<PreopNovedad[]>('/novedades/preoperacional', { query }),
    revisar: (preId: string, nota?: string | null) => api(`/preoperacional/${preId}/revisar`, { method: 'POST', body: { nota } }),
  }
}

/** K13 chips: incapacidad and permiso no remunerado discount (warn), the paid permit is gray. */
export const NOV_CLS: Record<string, string> = {
  incapacidad: 'warn',
  permiso_no_remunerado: 'warn',
  permiso_remunerado: 'gray',
}
