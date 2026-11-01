import type { Movimiento } from '~/types/movimientos'

/** K05 status chips: sin justificar = warn, por revisar = info, aprobada = ok, rechazada / vencida = bad. */
export function movCls(m: Pick<Movimiento, 'estado' | 'vencida'>): string {
  if (m.vencida) return 'chip bad'
  return {
    sin_justificar: 'chip warn',
    por_revisar: 'chip info',
    aprobada: 'chip ok',
    rechazada: 'chip bad',
    registro: 'chip gray',
  }[m.estado]
}

export function movEstado(m: Movimiento, largo = false): string {
  if (m.vencida) return 'Sin justificar · venció el plazo · −1 punto'
  if (m.estado === 'sin_justificar' && largo) return 'Esperando justificación · si vence el plazo, −1 punto'
  if (m.estado === 'aprobada' && largo && m.revisado_por_name) return `✓ Aprobada por ${firstName(m.revisado_por_name)}`
  if (m.estado === 'registro') return m.en_curso ? 'En campo ahora' : 'Registro de campo'
  return m.estado_txt
}

/** 780 → «13:00 h» (K05-ger KPI). */
export const fmtHorasMin = (min: number) => `${Math.floor(min / 60)}:${String(min % 60).padStart(2, '0')} h`

/** GPS: asesores with Captación, Coordinación and Atención y Preventa (services.movimientos.perfil). */
export const perfilGps = (u: { cargo: string; funcion?: string | null; actividades: readonly string[]; is_active: boolean } | null | undefined) => {
  if (!u?.is_active) return null
  if (u.cargo === 'coordinacion') return 'coordinacion'
  if (u.funcion === 'atencion_cliente' || u.funcion === 'pre_ventas') return 'atencion'
  if (u.actividades.includes('captacion')) return 'asesor'
  return null
}
export const canUseMovimientos = (u: Parameters<typeof perfilGps>[0]) => !!u && (u.cargo === 'gerencia' || !!perfilGps(u))
