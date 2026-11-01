export interface Marca {
  nombre: string
  lema: string
  color_principal: string
  color_oscuro: string
  color_claro: string
  logo: string | null
}

export interface Pagos {
  dia_corte_1: number
  dia_corte_2: number
  dia_pago: number
}

export interface Pendiente {
  clave: string
  titulo: string
  detalle: string
  quien: string
  link: string | null
  resuelto: boolean
  manual: boolean
}

export interface ConfigEvento {
  id: string
  seccion: string
  seccion_txt: string
  actor_name: string | null
  antes: Record<string, unknown>
  despues: Record<string, unknown>
  detalle: string | null
  created_at: string
}

export interface Tarifas {
  arriendo_pct: number
  papeleria: number
  iva_pct: number
  venta_pct: number
  referidos_pct: number
  retencion_pct: number | null
}

export interface Automatizaciones {
  lead_sin_responsable_min: number
  resumen_diario: string
  escalar_urgentes: boolean
}

export interface ReglasLeads {
  puntos_ganado: number
  puntos_perdido: number
  llamadas_minimas: number
  dias_seguidos: number
}

export interface ConfigPagina {
  gerencia: boolean
  marca: Marca
  pagos: Pagos
  tarifas: Tarifas | null
  automatizaciones: Automatizaciones | null
  idioma: { idioma: string } | null
  leads: ReglasLeads | null
  produccion: { resueltos: string[]; uso_real: boolean; uso_real_at: string | null; uso_real_por: string | null } | null
  pendientes: Pendiente[]
  opciones: Record<string, (number | string)[]>
  idiomas: Record<string, string>
  idiomas_disponibles: string[]
  cambios: ConfigEvento[]
}
