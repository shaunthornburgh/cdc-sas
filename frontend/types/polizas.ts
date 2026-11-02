export type PolEstado = 'en_estudio' | 'aprobada' | 'negada' | 'activa' | 'terminada'

export interface PolAlerta {
  dias: number
  falta: number
  max: string
  st: 'v' | 'p' | 'o'
}

export interface PolFila {
  id: string
  negocio: string | null
  asesor: string | null
  inmueble: string
  aseguradora: string
  aseguradora_id: string
  tipo: string
  tipo_id: string
  precio_pct: number
  canon: number
  costo_mes: number
  estado: PolEstado
  estado_txt: string
  estado_cls: string
  radicado: string | null
  estudio_fecha: string
  decision_fecha: string | null
  motivo_negada: string | null
  estudios: number
  puede_retomar: boolean
  retomada_motivo: string | null
  recuperada: boolean
  firma_fecha: string | null
  activada_fecha: string | null
  numero_poliza: string | null
  soporte: boolean
  seguro_inmueble: boolean
  terminada_fecha: string | null
  tiempo_activa: string | null
  alerta: PolAlerta | null
  historial?: { accion: string; antes: string | null; despues: string | null; actor: string | null; at: string }[]
}

export interface PolTablero {
  desde: string
  hasta: string
  gerencia: boolean
  kpis: {
    activas: number
    costo_mes: number
    canon_mes: number
    nuevas: number
    por_activar: number
    vencidas: number
    por_vencer: number
    en_estudio: number
    recuperadas: number
  }
  por_aseguradora: {
    id: string
    nombre: string
    tipos: string
    activas: number
    costo_mes: number
    precio_prom: number | null
    activa_desde: string | null
    plazo: string
    nuevas: number
  }[]
  contratos: PolFila[]
  activas_total: number
  alertas: PolFila[]
  tramite: PolFila[]
  terminadas: PolFila[]
}

export interface PolTipo {
  id: string
  nombre: string
  precio_pct: number
  costo_estudio: number
  dias_respuesta: number | null
  coberturas: string[]
}

export interface PolAseguradora {
  id: string
  nombre: string
  nit: string | null
  contacto: string | null
  telefono: string | null
  activa: boolean
  dias_max: number
  aviso_dias: number
  ejemplo: boolean
  polizas: number
  puede_eliminar: boolean
  agregada: string
  tipos: PolTipo[]
}

export interface PolAseguradoras {
  items: PolAseguradora[]
  eliminadas: { nombre: string; txt: string }[]
  coberturas: Record<string, string>
  historial: { accion: string; registro: string; antes: string | null; despues: string | null; actor: string | null; at: string }[]
}

export interface PolOpciones {
  negocios: { id: string; t: string; asesor: string | null }[]
  inmuebles: { id: string; t: string; canon: number | null }[]
  aseguradoras: { id: string; nombre: string; tipos: { id: string; nombre: string; precio_pct: number }[] }[]
}

export interface PolCard {
  id: string
  aseguradora_id: string
  aseguradora: string
  tipo: string
  precio_pct: number
  costo_estudio: number
  dias_respuesta: number | null
  coberturas: string[]
  aprobados: number
  estudios: number
  aprobacion: number | null
  negados: number
  activas: number
  con_seguro: number
  canon_mes: number
  nueva: boolean
  inmuebles: { c: string; d: string; v: number }[]
}

export interface PolComparar {
  desde: string
  hasta: string
  cards: PolCard[]
  coberturas: Record<string, string>
}
