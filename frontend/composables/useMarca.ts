import type { Marca } from '~/types/configuracion'

export const MARCA_CDC: Marca = {
  nombre: 'CASA DOLCE CASA',
  lema: 'Confianza que construye hogares',
  color_principal: '#00843D',
  color_oscuro: '#0B3D23',
  color_claro: '#8DC63F',
  logo: null,
}

/** The company brand (Configuración · Marca). Loaded once by plugins/marca.ts, without login. */
export const useMarca = () => useState<Marca>('marca', () => ({ ...MARCA_CDC }))

/** Mix a #RRGGBB colour with white (amt > 0) or black (amt < 0). */
export function shade(hex: string, amt: number): string {
  const n = Number.parseInt(hex.slice(1), 16)
  const ch = [n >> 16, (n >> 8) & 255, n & 255].map((c) =>
    Math.round(amt >= 0 ? c + (255 - c) * amt : c * (1 + amt)),
  )
  return `#${ch.map((c) => c.toString(16).padStart(2, '0')).join('')}`
}

/** CSS variables of the greens. The traffic-light / status colours never change. */
export function marcaVars(m: Marca): string {
  return [
    `--cdc-green:${m.color_principal}`,
    `--cdc-green-hover:${shade(m.color_principal, -0.19)}`,
    `--cdc-green-dark:${m.color_oscuro}`,
    `--cdc-green-side-2:${shade(m.color_oscuro, 0.07)}`,
    `--cdc-green-side-hover:${shade(m.color_oscuro, 0.14)}`,
    `--cdc-green-lime:${m.color_claro}`,
  ].join(';')
}
