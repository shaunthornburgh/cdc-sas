export interface AsFila {
  id: string
  user_id: string
  nombre: string
  fecha: string
  asignada: string
  entrada: string | null
  entrada_lugar: string | null
  entrada_estado: string | null
  entrada_txt: string
  entrada_cls: string
  minutos_tarde: number
  tipo_tarde: 'leve' | 'grave' | null
  salida: string | null
  salida_tipo: string | null
  salida_estado: string | null
  salida_txt: string
  salida_cls: string
  minutos_descuento: number
  minutos_extra: number
  observacion: string
}

export interface AsMia {
  marca: boolean
  quien: string
  revisa: string
  fecha: string
  horario_hoy: string
  horario_txt: string
  ubicacion: string
  ubicacion_det: string
  puntualidad: { txt: string; dias: number; a_tiempo: number; pct: number | null; puntaje: number | null; minutos: number }
  mes: string
  hoy: AsFila | null
  entrada_txt: string
  entrada_cls: string
  salida_txt: string
  salida_cls: string
  puede_entrada: boolean
  puede_salida: boolean
  preop_pendiente: boolean
  limite: string | null
  fin: string | null
  pasado_limite: boolean
  recordar_salida: boolean
  registro: AsFila[]
  motivos_entrada: Record<string, string>
  motivos_salida: Record<string, string>
}

export interface AsMarcarRes {
  ok: boolean
  requiere_justificacion?: boolean
  titulo?: string
  detalle?: string
  opciones?: Record<string, string>
  marcacion?: AsFila
}

export interface AsPendiente {
  id: string
  que: 'entrada' | 'salida' | 'extra'
  tipo: string
  tcls: string
  nombre: string
  fecha: string
  detalle: string
  justificacion: string
  puede: boolean
  quien: string
  estado: string
}

export interface AsEquipo {
  desde: string
  hasta: string
  hoy: string
  entrada_hoy: string | null
  kpis: { marcaron: number; total: number; faltan: string[]; por_aprobar: number; pendientes: number; leves: number; graves: number; minutos: number; extra: number }
  por_aprobar: AsPendiente[]
  filas_hoy: { user_id: string; nombre: string; asignada: string; donde: string; entrada: string; estado: string; cls: string; salida: string }[]
  registro: AsFila[]
  puede_descargar: boolean
  rol: string
}

export interface AsConfig {
  config: {
    entrada_lv: string
    salida_lv: string
    entrada_sab: string
    salida_sab: string
    limite_min: number
    leve_max: number
    recordatorio_min: number
    extra_min: number
    radio_zona_m: number
    exigir_preoperacional: boolean
    marcan: Record<string, boolean>
  }
  puede_editar: boolean
  sedes: { id: string; nombre: string; direccion: string; lat: number; lng: number; radio_m: number; principal: boolean; activa: boolean; personas: number }[]
  personas: { id: string; nombre: string; cargo: string; sede_id: string | null; ubicacion: string; cambio: string | null; puede_cambiar: boolean }[]
  cargos: Record<string, string>
}
