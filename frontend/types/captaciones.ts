import type { TipoNegocio, UserRef } from '~/types/leads'

export type EstadoCaptacion = 'por_verificar' | 'aprobada' | 'rechazada'
export type ModoCaptacion = 'rapido' | 'completo'
export type TipoInmueble = 'apartamento' | 'casa' | 'local' | 'oficina' | 'lote' | 'bodega'
export type MotivoRechazoCaptacion = 'codigo_inexistente' | 'codigo_no_corresponde'
export type TipoEventoCaptacion =
  | 'enviada' | 'editada' | 'aprobada' | 'rechazada' | 'reenviada' | 'publicada' | 'reasignada'

export type CaptacionDetalles = {
  tipo_inmueble: TipoInmueble | null
  barrio: string | null
  municipio: string | null
  precio: number | null
  area_m2: string | number | null
  habitaciones: number | null
  banos: number | null
  parqueadero: boolean | null
  propietario_nombre: string | null
  propietario_telefono: string | null
  observaciones: string | null
}

export interface Captacion extends CaptacionDetalles {
  id: string
  code: string
  modo: ModoCaptacion
  negocio: TipoNegocio
  codigo_inmueble: string
  direccion: string
  estado: EstadoCaptacion
  enviada_at: string
  reenvios: number
  motivo_rechazo: MotivoRechazoCaptacion | null
  observacion_rechazo: string | null
  verificado_por_name: string | null
  verificado_at: string | null
  publicada_at: string | null
  gps_lat: string | null
  gps_lng: string | null
  gps_precision_m: number | null
  gps_at: string | null
  asesor: UserRef
  created_at: string
  can_edit: boolean
  eventos: { tipo: TipoEventoCaptacion; titulo: string; detalle: string | null; created_by_name: string | null; created_at: string }[]
}

export interface CaptacionList {
  items: Captacion[]
  counts: Record<EstadoCaptacion, number>
  aprobacion_pct: number | null
}

export type CaptacionCreate = Partial<CaptacionDetalles> & {
  modo: ModoCaptacion
  negocio: TipoNegocio
  codigo_inmueble: string
  direccion: string
  asesor_id?: string | null
  gps?: { lat: number; lng: number; precision_m?: number | null } | null
}
