export type Semaforo = 'verde' | 'amarillo' | 'naranja' | 'rojo'
export type Perfil = 'asesor' | 'atencion' | 'coordinacion'

export interface PeriodoRead {
  key: string
  label: string
  en_curso: boolean
}

export interface AreaRead {
  key: string
  titulo: string
  descripcion: string
  peso: number
  peso_efectivo: number
  meta: number | null
  meta_txt: string
  logrado: number
  logrado_txt: string
  cumplimiento: number | null
  semaforo: Semaforo | null
  cumple: boolean
  aporte: number
  falta: string
  sin_datos: string | null
}

export interface CalificacionRead {
  key: string
  titulo: string
  valor: number | null
  automatico: boolean
  quien: string
  fecha: string | null
}

export interface Punto {
  titulo: string
  detalle: string
  puntos: number
}

export interface Resultado {
  user: { id: string; full_name: string }
  perfil: Perfil
  cargo_txt: string
  periodo: PeriodoRead
  total: number | null
  total_exacto: number | null
  semaforo: Semaforo | null
  por_areas: number | null
  peso_con_datos: number
  puntos_ajuste: number
  puntos_descuento: number
  anterior: number | null
  areas: AreaRead[]
  calificaciones: CalificacionRead[]
  descuentos: Punto[]
  ajustes: Punto[]
  avisos: { titulo: string; detalle: string; link: string }[]
  mejoras: {
    items: { key: string; titulo: string; cumplimiento: number; falta: string; que_hacer: string; link: string; peso: number; anterior: number | null }[]
    todo_verde: boolean
    calificaciones: { titulo: string; valor: number; quien: string; que_hacer: string }[]
    bien: { titulo: string; cumplimiento: number }[]
  }
  puede: { calificar: boolean; configurar: boolean }
  detalle: {
    en_proceso: { code: string; titulo: string; detalle: string; estado: string; cls: string; link: string }[]
    perdidos: { cliente: string; motivo: string; fecha: string | null }[]
  } | null
}

export interface FilaEquipo {
  id: string
  full_name: string
  perfil: Perfil
  cargo_txt: string
  total: number | null
  semaforo: Semaforo | null
  metas_cumplidas: number
  metas_total: number
  ventas: number | null
  arriendos: number | null
  captaciones: number | null
  leads: number | null
  citas: number | null
  conversion: number | null
  ganados: number | null
  perdidos: number
  descuentos: number
  areas: { titulo: string; cumplimiento: number | null; logrado_txt: string }[]
}

export interface Equipo {
  periodo: PeriodoRead
  personas: FilaEquipo[]
}

export interface Empresa {
  periodo: PeriodoRead
  total: number | null
  semaforo: Semaforo | null
  personas: number
  anterior: number | null
  texto: string
  areas: { key: string; titulo: string; personas: string; n: number; total: number | null; semaforo: Semaforo | null; metas: { titulo: string; logrado: number; meta: number; pct: number }[]; anterior: number | null }[]
  avisos: { titulo: string; detalle: string; nivel: string }[]
}

export interface ConfigRead {
  user: { id: string; full_name: string }
  perfil: Perfil
  cargo_txt: string
  areas: { key: string; titulo: string; descripcion: string; tiene_meta: boolean; unidad: string }[]
  pesos: Record<string, number>
  pesos_configurados: boolean
  metas: Record<string, number>
  metas_siguiente: Record<string, number>
  siguiente: string
  puede_configurar: boolean
}

export interface Cambio {
  tipo: 'pesos' | 'metas' | 'calificaciones'
  periodo: string
  antes: Record<string, number | null>
  despues: Record<string, number>
  created_by_name: string | null
  created_at: string
}
