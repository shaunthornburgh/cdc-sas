import type { Cargo } from '~/types/auth'
import type { EquipoPreop, Formulario, Historial, MedioTransporte, PreoperacionalT } from '~/types/preoperacional'

/** Preoperacional API (prototypes M07 / C08 / K09). */
export function usePreoperacional() {
  const api = useApi()
  return {
    formulario: () => api<Formulario>('/preoperacional/formulario'),
    registrar: (body: { medio: MedioTransporte; placa?: string | null; respuestas?: boolean[] | null; observaciones?: string | null }) =>
      api<PreoperacionalT>('/preoperacional', { method: 'POST', body }),
    historial: (mes?: string) => api<Historial>('/preoperacional/mios', { query: mes ? { mes } : undefined }),
    equipo: (fecha?: string) => api<EquipoPreop>('/preoperacional/equipo', { query: fecha ? { fecha } : undefined }),
    revisar: (id: string, nota?: string | null) => api<PreoperacionalT>(`/preoperacional/${id}/revisar`, { method: 'POST', body: { nota } }),
    setConfig: (cargo: Cargo, activo: boolean) => api<Record<Cargo, boolean>>(`/preoperacional/config/${cargo}`, { method: 'PUT', body: { activo } }),
    /** Download the month as CSV (opens in Excel). Goes through the API so the token is sent. */
    async descargar(mes: string, userId?: string) {
      const blob = await api<Blob>('/preoperacional/export.csv', { query: { mes, user_id: userId }, responseType: 'blob' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `preoperacionales-${mes}.csv`
      a.click()
      URL.revokeObjectURL(url)
    },
  }
}

/** Chip for one person's day in K09. */
export const PREOP_ESTADO: Record<string, { t: string; cls: string }> = {
  realizado: { t: '✓ Realizado', cls: 'ok' },
  reporte: { t: '✓ Reporte', cls: 'ok' },
  novedad: { t: 'Con novedad', cls: 'warn' },
  sin_realizar: { t: 'Sin realizar', cls: 'bad' },
  desactivado: { t: 'Desactivado', cls: 'gray' },
  fin_de_semana: { t: 'Fin de semana', cls: 'gray' },
}

/** One line describing a record: «7:52 · moto · placa XYZ45E». */
export function preopDetalle(p: PreoperacionalT, medios?: Record<string, string>): string {
  const medio = (medios?.[p.medio] ?? p.medio.replace('_', ' ')).toLowerCase()
  return `${fmtHora(p.realizado_at)} · ${medio}${p.placa ? ` · placa ${p.placa}` : ''}`
}

export const MEDIO_LABELS_PREOP: Record<MedioTransporte, string> = {
  carro: 'Carro',
  moto: 'Moto',
  bicicleta: 'Bicicleta',
  transporte_publico: 'Transporte público',
  a_pie: 'A pie',
  otro: 'Otro',
}

/** K09 «Reporte de …» text. */
export function preopReporte(estado: string, p: PreoperacionalT | null): string {
  if (estado === 'desactivado') return 'El preoperacional está desactivado para este cargo: no cuenta ni descuenta.'
  if (estado === 'fin_de_semana' && !p) return 'Fin de semana: no se cuenta.'
  if (!p) return 'Aún no ha realizado el preoperacional. Si no lo hace hoy, baja su nota del preoperacional del mes.'
  const medio = MEDIO_LABELS_PREOP[p.medio]
  if (!p.respuestas.length) return `Reporte de desplazamiento: ${medio.toLowerCase()}. Sin cuestionario ni placa.`
  const si = p.respuestas.filter((r) => r.si).length
  const no = p.respuestas.length - si
  return `${medio} · placa ${p.placa} · ${no ? `${si} SÍ y ${no} NO` : `${si} de ${p.respuestas.length} preguntas en SÍ`}.`
}
