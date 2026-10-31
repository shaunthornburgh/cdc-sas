import type { Semaforo } from '~/types/rendimiento'

type Who = { cargo: string; funcion?: string | null; actividades: readonly string[]; is_active: boolean } | null | undefined

/** Who has a monthly result (services.rendimiento.perfil). */
export const perfilRendimiento = (u: Who): 'asesor' | 'atencion' | 'coordinacion' | null => {
  if (!u || !u.is_active) return null
  if (u.cargo === 'coordinacion') return 'coordinacion'
  if (u.funcion === 'atencion_cliente' || u.funcion === 'pre_ventas') return 'atencion'
  if (!u.funcion && u.actividades.length) return 'asesor'
  return null
}

/** «Mi equipo» / «Rendimiento por empleado»: Coordinación, Gerencia and the Auxiliar. */
export const canSeeTeamRendimiento = (u: Who) =>
  !!u && ['coordinacion', 'gerencia', 'auxiliar_administrativa'].includes(u.cargo)

export const SEM: Record<Semaforo, { cls: string; sym: string; color: string; t: string }> = {
  verde: { cls: 'ok', sym: '●', color: 'var(--sem-verde)', t: 'VERDE' },
  amarillo: { cls: 'warn', sym: '▲', color: 'var(--sem-amarillo)', t: 'AMARILLO' },
  naranja: { cls: 'nar', sym: '▲', color: 'var(--sem-naranja)', t: 'NARANJA' },
  rojo: { cls: 'bad', sym: '■', color: 'var(--sem-rojo)', t: 'ROJO' },
}

export const semDe = (r: number | null | undefined): Semaforo | null =>
  r == null ? null : r >= 80 ? 'verde' : r >= 70 ? 'amarillo' : r >= 60 ? 'naranja' : 'rojo'

/** 69.9 → «69,9» · 70 → «70». */
export const dec = (n: number) => (Math.round(n * 100) / 100).toString().replace('.', ',')

/** Month picker options: this month and the previous 5. */
export const ultimosMeses = (n = 6) => {
  const meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
  const [y, m] = localDate().split('-').map(Number) as [number, number]
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(y, m - 1 - i, 1)
    return { key: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`, t: `${meses[d.getMonth()]} ${d.getFullYear()}` }
  })
}
