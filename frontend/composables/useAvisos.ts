import type { AgendaItem, Aviso, AvisoConteo, AvisoNota, AvisoOpciones, Comunicado, VistaAvisos } from '~/types/avisos'

/** G09 «Avisos y agenda» / M10 / C05 «Notificaciones» API. */
export function useAvisos() {
  const api = useApi()
  return {
    opciones: () => api<AvisoOpciones>('/avisos/opciones'),
    conteo: () => api<AvisoConteo>('/avisos/conteo'),
    list: (vista: VistaAvisos) => api<{ items: Aviso[]; conteo: AvisoConteo }>('/avisos', { query: { vista } }),
    leidos: (ids: string[]) => api<AvisoConteo>('/avisos/leidos', { method: 'POST', body: { ids } }),
    atender: (id: string, nota?: string | null) => api<Aviso>(`/avisos/${id}/atender`, { method: 'POST', body: { nota: nota || null } }),
    reabrir: (id: string) => api<Aviso>(`/avisos/${id}/reabrir`, { method: 'POST' }),
    nota: (id: string, texto: string) => api<AvisoNota>(`/avisos/${id}/notas`, { method: 'POST', body: { texto } }),
    agendar: (id: string, body: object) => api<AgendaItem>(`/avisos/${id}/agendar`, { method: 'POST', body }),
    comunicados: () => api<Comunicado[]>('/avisos/comunicados'),
    enviar: (body: object) => api<Comunicado>('/avisos/comunicados', { method: 'POST', body }),
  }
}

/**
 * The bell: what waits for the signed-in person. Shared by the layout (sidebar badge, mobile bell)
 * and the page, polled every minute while the app is open.
 */
export function useAvisosConteo() {
  const conteo = useState<AvisoConteo | null>('avisos:conteo', () => null)
  const api = useAvisos()
  async function refrescar() {
    try {
      conteo.value = await api.conteo()
    } catch {
      // offline or signed out: keep the last count
    }
  }
  return { conteo, refrescar }
}
