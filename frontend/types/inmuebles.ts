import type { TipoInmueble } from '~/types/captaciones'
import type { TipoNegocio } from '~/types/leads'

export type EstadoInmueble = 'disponible' | 'separado' | 'arrendado' | 'vendido' | 'retirado'

export interface Inmueble {
  id: string
  codigo: string
  titulo: string
  negocio: TipoNegocio
  tipo_inmueble: TipoInmueble | null
  direccion: string
  zona: string | null
  barrio: string | null
  municipio: string | null
  precio: number | null
  administracion: number | null
  area_m2: string | null
  habitaciones: number | null
  banos: number | null
  parqueadero: boolean | null
  estrato: number | null
  descripcion: string | null
  propietario_nombre: string | null
  propietario_telefono: string | null
  ve_propietario: boolean
  estado: EstadoInmueble
  estado_txt: string
  estado_at: string
  faltantes: string[]
  captacion_code: string | null
  captacion_id: string | null
  captador_name: string | null
  can_edit: boolean
  created_at: string
  eventos: { titulo: string; detalle: string | null; created_by_name: string | null; created_at: string }[]
}

export interface InmuebleList {
  items: Inmueble[]
  kpis: { disponibles: number; arriendo: number; venta: number; separados: number; cerrados_mes: number; incompletos: number; mios: number }
}

export interface InmuebleOpciones {
  zonas: string[]
  rangos: Record<string, string>
  estados: Record<EstadoInmueble, string>
  puede_crear: boolean
}

export interface OpcionLead {
  id: string
  codigo: string
  titulo: string
  detalle: string
  ya_enviado: boolean
}

export type InmuebleIn = Partial<Omit<Inmueble, 'id' | 'titulo' | 'estado' | 'estado_txt' | 'estado_at' | 'faltantes' | 'captacion_code' | 'captacion_id' | 'captador_name' | 'can_edit' | 'created_at' | 'eventos' | 've_propietario'>>
