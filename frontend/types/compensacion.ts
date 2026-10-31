export interface Persona {
  id: string
  full_name: string
}

export interface CompItem {
  id: string
  clase: 'comision' | 'bono'
  tipo: string
  beneficiario: Persona
  concepto: string
  detalle: string | null
  fecha: string
  periodo: string
  valor: number
  base: number | null
  porcentaje: string | null
  cierre_code: string | null
  estado: 'generada' | 'visto_bueno' | 'pendiente_pago' | 'pagada' | 'anulada'
  estado_txt: string
  se_paga: string
}

export interface PagoRead {
  id: string
  beneficiario: Persona
  tipo: 'comision' | 'bono' | 'salario'
  concepto: string
  valor: number
  fecha_programada: string
  estado: 'en_proceso' | 'pagado'
  estado_txt: string
  pagado_at: string | null
}

export interface CierreRead {
  id: string
  code: string
  lead_code: string
  cliente: string
  negocio: 'venta' | 'arriendo' | null
  cerrado_at: string
  estado: 'cerrado' | 'caido'
  ganancia: number | null
  cerrador: Persona | null
  filtro: Persona | null
  captador: Persona | null
}

export interface Tablero {
  comisiones: CompItem[]
  bonos: CompItem[]
  pagos: PagoRead[]
  cierres: CierreRead[]
  totales: Record<'comision' | 'bono' | 'pago', Record<string, number>>
  config: Record<string, number | string>
  config_labels: Record<string, string>
  personas: Persona[]
  captadores: Persona[]
  es_gerencia: boolean
  es_auxiliar: boolean
}

export interface MioItem {
  id: string
  clase: 'comision' | 'bono' | 'salario'
  concepto: string
  detalle: string
  fecha: string
  valor: number
  se_paga: string
  estado: string
  estado_txt: string
}

export interface Mio {
  perfil: 'asesor' | 'atencion' | 'coordinacion' | null
  como_ganas: { titulo: string; detalle: string }[]
  salario_mensual: number | null
  kpis: { pagado: number; por_pagar: number; comisiones_bonos: number; proximo: string | null; proximo_txt: string | null }
  items: MioItem[]
  pagos: { id: string; concepto: string; detalle: string; fecha: string; valor: number; tipo: string; estado: string; estado_txt: string }[]
}

export interface Liquidacion {
  id: string
  user: Persona
  cargo_txt: string
  salario_mensual: number
  salario_corte: number
  descuento: number
  a_pagar: number
  novedades: string
  estado: 'por_confirmar' | 'confirmado' | 'pagado'
  estado_txt: string
}

export interface Salarios {
  periodo: string
  label: string
  corte: number
  fecha_pago: string
  filas: Liquidacion[]
  sin_salario: Persona[]
  es_gerencia: boolean
  es_auxiliar: boolean
}

export interface EventoComp {
  accion: string
  antes: Record<string, unknown>
  despues: Record<string, unknown>
  created_by_name: string | null
  created_at: string
}
