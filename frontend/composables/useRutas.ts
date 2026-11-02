import type { ImportRev, MiRuta, Ruta, RutasOpciones, Ubicacion } from '~/types/rutas'

function bajar(blob: Blob, nombre: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nombre
  a.click()
  URL.revokeObjectURL(url)
}

/** G-083 rutas (Coordinación programa, Gerencia y Auxiliar consultan) y M04 «Mi ruta». */
export function useRutas() {
  const api = useApi()
  const post = <T = Ruta>(url: string, body?: object) => api<T>(url, { method: 'POST', body })
  return {
    opciones: () => api<RutasOpciones>('/rutas/opciones'),
    miRuta: () => api<MiRuta>('/rutas/mi-ruta'),
    llegada: (zona_id: string) => post<{ zona_id: string }>('/rutas/llegada', { zona_id }),
    listar: (query: { desde?: string; hasta?: string; asesor_id?: string; estado?: string }) => api<{ items: Ruta[]; total: number }>('/rutas', { query }),
    ubicaciones: () => api<Ubicacion[]>('/rutas/ubicaciones'),
    async plantilla() {
      bajar(await api<Blob>('/rutas/plantilla.csv', { responseType: 'blob' }), 'CDC_Plantilla_Rutas.csv')
    },
    /** X08 «Descargar Excel» of the locations (built here: it's the same list on screen). */
    bajarUbicaciones(rows: Ubicacion[]) {
      const esc = (v: string) => `"${v.replace(/"/g, '""')}"`
      const csv = ['Persona;Cargo;Dónde marca hoy;Nota', ...rows.map((r) => [r.nombre, CARGO_LABELS[r.cargo as keyof typeof CARGO_LABELS] ?? r.cargo, r.donde, r.nota ?? ''].map(esc).join(';'))].join('\n')
      bajar(new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' }), 'CDC_Ubicaciones_y_rutas.csv')
    },
    importar: (texto: string, confirmar: boolean) => post<ImportRev>('/rutas/importar', { texto, confirmar }),
    crear: (body: object) => post('/rutas', body),
    cancelar: (id: string) => post(`/rutas/${id}/cancelar`),
    responder: (id: string, acepta: boolean, motivo?: string, texto?: string) => post(`/rutas/${id}/responder`, { acepta, motivo, texto }),
    calificar: (id: string, puntos: number) => post(`/rutas/${id}/calificar`, { puntos }),
  }
}
