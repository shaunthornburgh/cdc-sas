import type { Cargo } from '~/types/auth'

declare module '#app' {
  interface PageMeta {
    /** Page is reachable without logging in. */
    public?: boolean
    /** Only these cargos may open the page (others get a 403 page). */
    cargos?: Cargo[]
    /** Module whose access rule applies (see middleware/auth.global.ts). */
    module?: 'leads' | 'captaciones' | 'asesor' | 'pedidos' | 'resultados' | 'inmuebles' | 'movimientos'
  }
}

export {}
