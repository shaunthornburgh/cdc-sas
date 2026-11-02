export interface AgPersona {
  id: string
  full_name: string
  rol_txt: string
  yo: boolean
  puede_agregar: boolean
}

export interface AgAcciones {
  hecha: boolean
  rechazar: boolean
  justificar: boolean
  eliminar: boolean
}

export type AgTipo = 'cita' | 'seg' | 'ped' | 'ctl' | 'mia' | 'asg'

export interface AgEntrada {
  id: string
  k: 'man' | 'sys'
  tipo: AgTipo
  fecha: string
  hora: string | null
  hora_txt: string
  titulo: string
  sub: string | null
  nota: string | null
  prioridad: 'normal' | 'alta'
  estado: 'pendiente' | 'atrasada' | 'hecha' | 'rechazada' | 'justificada' | null
  estado_txt: string
  estado_cls: string
  link: string | null
  por_name: string | null
  por_yo: boolean
  created_at: string | null
  motivo: string | null
  respondida_at: string | null
  aviso_titulo: string | null
  acciones: AgAcciones
}

export interface AgEliminada {
  titulo: string
  fecha: string
  por_name: string | null
  created_at: string
  eliminada_por: string | null
  eliminado_at: string
}

export interface AgVista {
  persona: AgPersona
  desde: string
  hasta: string
  items: AgEntrada[]
  eliminadas: AgEliminada[]
  tipos: Record<AgTipo, string>
}
