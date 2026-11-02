export interface AvisoNota {
  id: string
  autor_name: string | null
  texto: string
  created_at: string
}

export interface AvisoDato {
  lbl: string
  val?: string
  sub?: string
  rojo?: boolean
}

export interface Aviso {
  id: string
  origen: 'sistema' | 'comunicado'
  tipo: string
  tipo_txt: string
  nivel: 'bad' | 'warn' | 'info' | 'gray'
  titulo: string
  detalle: string | null
  que_hacer: string | null
  limite_at: string | null
  link: string | null
  accion_txt: string | null
  datos: AvisoDato[]
  requiere_accion: boolean
  estado: 'por_atender' | 'atendido'
  atendido_at: string | null
  atendido_por_name: string | null
  resuelto_auto: boolean
  leido_at: string | null
  enviado_por: string | null
  created_at: string
  notas: AvisoNota[]
}

export interface AvisoConteo {
  por_atender: number
  resumen_sin_leer: number
  agenda_hoy: number
}

export interface AgendaItem {
  id: string
  fecha: string
  hora: string | null
  hora_txt: string
  titulo: string
  nota: string | null
  prioridad: 'normal' | 'alta'
  estado: 'pendiente' | 'hecha'
  hecha_at: string | null
  aviso_id: string | null
  aviso_titulo: string | null
  created_at: string
}

export interface Comunicado {
  id: string
  titulo: string
  cuerpo: string
  prioridad: 'normal' | 'alta'
  audiencia: string[]
  audiencia_txt: string
  expira_el: string | null
  creado_por: string | null
  created_at: string
  total: number
  leidos: number
  lecturas: { nombre: string; leido_at: string | null }[]
}

export interface AvisoOpciones {
  puede_comunicar: boolean
  audiencias: Record<string, string>
  gerencia: boolean
}

export type VistaAvisos = 'por_atender' | 'atendidos' | 'resumen'
