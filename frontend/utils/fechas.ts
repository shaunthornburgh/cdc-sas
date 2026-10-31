/** Dates shown and entered in Colombia time (UTC-5, no daylight saving). */
const TZ = 'America/Bogota'
const OFFSET = '-05:00'

const dayKey = (d: Date) =>
  new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d)

/** 'YYYY-MM-DD' for today (+days) in Bogotá — for <input type="date">. */
export function localDate(days = 0): string {
  return dayKey(new Date(Date.now() + days * 86_400_000))
}

/** Combine <input type="date"> + <input type="time"> into an ISO string with the Bogotá offset. */
export function toIso(date: string, time: string): string {
  return `${date}T${time}:00${OFFSET}`
}

/** '9:14' */
export function fmtHora(iso: string): string {
  return new Intl.DateTimeFormat('es-CO', { timeZone: TZ, hour: 'numeric', minute: '2-digit', hour12: false }).format(new Date(iso))
}

/** 'hoy 16:00' · 'mañana 10:00' · 'ayer 9:12' · 'lun 6 oct 11:00' */
export function fmtCuando(iso: string): string {
  const d = new Date(iso)
  const k = dayKey(d)
  const rel = k === localDate(0) ? 'hoy' : k === localDate(1) ? 'mañana' : k === localDate(-1) ? 'ayer' : null
  if (rel) return `${rel} ${fmtHora(iso)}`
  const day = new Intl.DateTimeFormat('es-CO', { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' })
    .format(d)
    .replace(/\./g, '')
    .replace(',', '')
  return `${day} ${fmtHora(iso)}`
}

/** Minutes from now until `iso` (negative if past). */
export const minutesUntil = (iso: string) => Math.round((new Date(iso).getTime() - Date.now()) / 60_000)

export const isToday = (iso: string) => dayKey(new Date(iso)) === localDate(0)

const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
/** '2026-10-03' → '3 oct 2026' */
export function fmtFecha(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return `${d} ${MESES_CORTOS[m! - 1]} ${y}`
}
/** Whole days from today to `iso` (negative if past). */
export function diasHasta(iso: string): number {
  const a = new Date(`${localDate(0)}T00:00:00`)
  const b = new Date(`${iso.slice(0, 10)}T00:00:00`)
  return Math.round((b.getTime() - a.getTime()) / 86_400_000)
}
