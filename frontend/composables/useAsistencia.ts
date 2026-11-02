import type { AsConfig, AsEquipo, AsFila, AsMarcarRes, AsMia } from '~/types/asistencia'

/** Browser location for «Marcar entrada / salida» (G-049). null when it isn't available. */
export function ubicacionActual(): Promise<{ lat: number; lng: number } | null> {
  return new Promise((resolve) => {
    if (!import.meta.client || !navigator.geolocation) return resolve(null)
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 30_000 },
    )
  })
}

/** Z04 · K17 · X08 asistencia API. */
export function useAsistencia() {
  const api = useApi()
  return {
    mia: () => api<AsMia>('/asistencia/mia'),
    entrada: (body: object) => api<AsMarcarRes>('/asistencia/entrada', { method: 'POST', body }),
    salida: (body: object) => api<AsMarcarRes>('/asistencia/salida', { method: 'POST', body }),
    equipo: (query: { desde?: string; hasta?: string }) => api<AsEquipo>('/asistencia/equipo', { query }),
    revisar: (id: string, que: string, acepta: boolean) => api<AsFila>(`/asistencia/${id}/revisar`, { method: 'POST', body: { que, acepta } }),
    config: () => api<AsConfig>('/asistencia/config'),
    guardarConfig: (valores: object) => api('/asistencia/config', { method: 'PUT', body: { valores } }),
    crearSede: (body: object) => api('/asistencia/sedes', { method: 'POST', body }),
    editarSede: (id: string, body: object) => api(`/asistencia/sedes/${id}`, { method: 'PATCH', body }),
    asignar: (userId: string, sedeId: string) => api(`/asistencia/ubicacion/${userId}`, { method: 'PUT', body: { sede_id: sedeId } }),
    async descargar(query: { desde: string; hasta: string }) {
      const blob = await api<Blob>('/asistencia/export.csv', { query, responseType: 'blob' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `CDC_Asistencia_${query.desde}_a_${query.hasta}.csv`
      a.click()
      URL.revokeObjectURL(url)
    },
  }
}
