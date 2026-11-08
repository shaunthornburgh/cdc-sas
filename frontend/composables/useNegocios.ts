import type { NegDetalle, NegTablero } from '~/types/negocios'

/** X02 «Negocios» / M16 API (Auxiliar, Gerencia, Coordinación and the asesor's own deals). */
export function useNegocios() {
  const api = useApi()
  const post = (url: string, body?: object) => api<NegDetalle>(url, { method: 'POST', body })
  return {
    tablero: (query: { desde?: string; hasta?: string; tipo?: string }) => api<NegTablero>('/negocios', { query }),
    ver: (id: string) => api<NegDetalle>(`/negocios/${id}`),
    editar: (id: string, body: object) => api<NegDetalle>(`/negocios/${id}`, { method: 'PATCH', body }),
    etapa: (id: string, body: { etapa?: string | null; oferta?: string | null; observacion: string; notaria?: string | null; notaria_at?: string | null }) =>
      post(`/negocios/${id}/etapa`, body),
    solicitar: (id: string, nota?: string) => post(`/negocios/${id}/solicitar`, { nota: nota || null }),
    confirmar: (id: string, body: { fecha: string; contrato_adjunto: boolean; observacion?: string | null }) => post(`/negocios/${id}/confirmar`, body),
    devolver: (id: string, motivo: string) => post(`/negocios/${id}/devolver`, { motivo }),
    caida: (id: string, motivo: string, observacion: string) => post(`/negocios/${id}/caida`, { motivo, observacion }),
    descartarCaida: (id: string) => post(`/negocios/${id}/caida/descartar`),
    abono: (id: string, body: { valor: number; fecha: string; momento: string; soporte: boolean }) => post(`/negocios/${id}/abonos`, body),
  }
}
