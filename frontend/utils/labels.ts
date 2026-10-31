import type { FetchError } from 'ofetch'
import type { ActividadComercial, Cargo, FuncionIndependiente } from '~/types/auth'

export const CARGO_LABELS: Record<Cargo, string> = {
  gerencia: 'Gerencia',
  coordinacion: 'Coordinación',
  asesor: 'Asesor',
  auxiliar_administrativa: 'Auxiliar administrativa',
  atencion_cliente: 'Atención al Cliente',
}

export const CARGOS = Object.keys(CARGO_LABELS) as Cargo[]

export const ACTIVIDAD_LABELS: Record<ActividadComercial, string> = {
  captacion: 'Captación',
  ventas: 'Ventas',
  arriendos: 'Arriendos',
}

export const ACTIVIDADES = Object.keys(ACTIVIDAD_LABELS) as ActividadComercial[]

export const FUNCION_LABELS: Record<FuncionIndependiente, string> = {
  atencion_cliente: 'Atención al Cliente',
  pre_ventas: 'Pre-ventas',
}

export const FUNCIONES = Object.keys(FUNCION_LABELS) as FuncionIndependiente[]

/** Cargos that can manage users (mirrors USER_MANAGERS in the API). */
export const USER_MANAGER_CARGOS: Cargo[] = ['gerencia', 'coordinacion']

/** Only allow same-site relative paths after login (no open redirects). */
export function safeRedirect(value: unknown, fallback = '/'): string {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')
    ? value
    : fallback
}

/** A readable message from an API error (string detail or FastAPI validation list). */
export function apiErrorMessage(e: unknown, fallback = 'Ocurrió un error.'): string {
  const err = e as FetchError<{ detail?: unknown }>
  if (!err?.response) return 'No se pudo conectar con el servidor.'
  const detail = err.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const msgs = detail.map((d: { msg?: string }) => d?.msg).filter(Boolean)
    if (msgs.length) return msgs.join(' · ')
  }
  return fallback
}

/** "Laura Gómez Ruiz" -> "LG" (avatar initials). */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? (parts[1]?.[0] ?? '') : '')).toUpperCase()
}

export const firstName = (name: string) => name.trim().split(/\s+/)[0] ?? name
