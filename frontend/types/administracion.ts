export type EstadoInventario = 'programado' | 'realizado' | 'con_novedades' | 'firmado'
export type EstadoAmbiente = 'bueno' | 'regular' | 'malo'
export type EstadoReparacion = 'recibida' | 'cotizada' | 'aprobada' | 'en_ejecucion' | 'terminada'
export type EstadoSolicitud = 'abierta' | 'en_tramite' | 'respondida' | 'cerrada'
export type Prioridad = 'normal' | 'urgente'
export type PagaReparacion = 'por_definir' | 'propietario' | 'inquilino' | 'empresa' | 'aseguradora'

export interface AdminEvento {
  titulo: string
  detalle: string | null
  created_by_name: string | null
  created_at: string
}
export interface InmuebleRef {
  id: string
  codigo: string
  titulo: string
}
export interface Persona {
  id: string
  full_name: string
}

export interface Ambiente {
  id: string
  nombre: string
  estado: EstadoAmbiente | null
  observacion: string | null
  fotos: number
}

export interface Inventario {
  id: string
  code: string
  inmueble: InmuebleRef
  tipo: 'entrega' | 'recepcion'
  tipo_txt: string
  fecha: string
  referencia: string
  responsable: Persona | null
  estado: EstadoInventario
  estado_txt: string
  firmado_at: string | null
  ambientes: Ambiente[]
  novedades: number
  fotos: number
  reparacion_code: string | null
  puede_llenar: boolean
  puede_gestionar: boolean
  eventos: AdminEvento[]
}

export interface Reparacion {
  id: string
  code: string
  inmueble: InmuebleRef
  titulo: string
  categoria: string
  categoria_txt: string
  prioridad: Prioridad
  solicitante: string
  fecha: string
  estado: EstadoReparacion
  estado_txt: string
  proveedor: string | null
  valor: number | null
  paga: PagaReparacion
  paga_txt: string
  fecha_fin: string | null
  dias: number
  responsable: Persona | null
  inventario_code: string | null
  puede_avance: boolean
  puede_gestionar: boolean
  eventos: AdminEvento[]
}

export interface Solicitud {
  id: string
  code: string
  inmueble: InmuebleRef
  tipo: string
  tipo_txt: string
  de: 'propietario' | 'inquilino'
  de_txt: string
  nombre: string | null
  canal: string
  canal_txt: string
  descripcion: string
  prioridad: Prioridad
  fecha: string
  estado: EstadoSolicitud
  estado_txt: string
  fuera_de_plazo: boolean
  dias_habiles: number
  plazo: number
  responsable: Persona | null
  respuesta: string | null
  fecha_respuesta: string | null
  puede_responder: boolean
  puede_gestionar: boolean
  eventos: AdminEvento[]
}

export interface AdminResumen {
  kpis: {
    inventarios_semana: number
    inventarios_novedades: number
    inventarios: number
    reparaciones_abiertas: number
    reparaciones_urgentes: number
    reparacion_dias_promedio: number
    solicitudes_abiertas: number
    solicitudes_fuera_plazo: number
  }
  puede_gestionar: boolean
  plazo: number
  inmuebles: InmuebleRef[]
  responsables: Persona[]
  labels: Record<string, Record<string, string>>
}

export type AdminQuery = { desde?: string; hasta?: string; estado?: string; inmueble_id?: string }
