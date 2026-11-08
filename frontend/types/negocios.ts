/** X02 «Negocios» · M16 «Detalle del negocio» (backend: app/services/negocios.py). */

export type NegModo = 'auxiliar' | 'gerencia' | 'coordinacion' | 'asesor'
export type NegSituacion = 'en_proceso' | 'por_confirmar' | 'cerrado' | 'caido'
export type NegCategoria = 'neg' | 'pc' | 'cer' | 'cai'

export interface NegPersona {
  id: string
  full_name: string
}

export interface NegLinea {
  t: string
  d: string
  v: number
  fuerte?: boolean
  total?: boolean
}

export interface NegGanancia {
  con_valor: boolean
  pct: number
  efectiva: number
  neta: number
  perdida: boolean
  estimadas: boolean
  lineas: NegLinea[]
  no_ganancia: { t: string; d: string; v: string }[]
}

export interface NegAbono {
  id: string
  valor: number
  fecha: string
  momento: string
  momento_txt: string
  soporte: boolean
  por: string | null
}

export interface NegItem {
  id: string
  code: string
  negocio: 'arriendo' | 'venta' | null
  tipo: 'Arriendo' | 'Venta'
  lead_id: string
  lead_code: string
  cliente: string
  origen: string
  inmueble: string
  inmueble_id: string | null
  valor: number | null
  asesor: NegPersona | null
  captador: NegPersona | null
  filtro: NegPersona | null
  situacion: NegSituacion
  categoria: NegCategoria
  estado_txt: string
  estado_cls: string
  fecha: string
  inicio: string
  etapa: string
  etapas: string[]
  oferta: string | null
  solicitud: 'promesa' | 'cierre' | null
  solicitud_at: string | null
  solicitud_nota: string | null
  devuelto_motivo: string | null
  promesa_fecha: string | null
  firma_fecha: string | null
  paso_promesa: boolean
  notaria: string | null
  notaria_at: string | null
  caida: { motivo: string | null; obs: string | null; reportada_at: string | null; por: string | null; confirmada_at: string | null } | null
  docs_ubicacion: string | null
  contrato_adjunto: boolean
  poliza: {
    id: string
    estado: string
    estado_txt: string
    estado_cls: string
    tipo: string
    aseguradora: string
    radicado: string | null
    firma_fecha: string | null
    activada_fecha: string | null
    numero: string | null
  } | null
  abierto: boolean
  // Only for the Auxiliar and Gerencia
  ganancia?: NegGanancia
  ganancia_efectiva?: number | null
  pct_venta?: number | null
  pct_venta_propio?: boolean
  uso_comercial?: boolean
  arrendatario_juridica?: boolean
  referido?: string | null
  recibido?: number
  abonos?: NegAbono[]
}

export interface NegDetalle extends NegItem {
  historial: { at: string; accion: string; por: string; detalle: string | null }[]
  resultado?: { cerrado: boolean; comisiones: boolean; poliza: boolean } | 'reportada' | 'confirmada'
}

export interface NegTablero {
  modo: NegModo
  items: NegItem[]
  motivos_caida: string[]
  // Not for asesores
  desde?: string
  hasta?: string
  kpis?: { total: number; neg: number; pc: number; cer: number; cai: number; cai_reportadas: number; ganancia?: number; proyectada?: number }
  por_tipo?: { tipo: string; t: string; n: number; ganancia?: number }[]
  counts?: { sol: number; proc: number; cer: number; cai: number }
  motivos_devolver?: string[]
  momentos?: Record<string, string>
  puede?: { gestionar: boolean; datos: boolean }
  ganancias?: { id: string; code: string; tipo: string; categoria: NegCategoria; con_valor: boolean; neta: number }[]
  tarifas?: { arriendo_pct: number; papeleria: number; iva_pct: number; venta_pct: number; referidos_pct: number; retencion_pct: number | null }
  inmuebles?: { id: string; negocio: string; t: string; precio: number | null }[]
}
