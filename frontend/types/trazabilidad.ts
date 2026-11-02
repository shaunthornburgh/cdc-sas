export interface RcFila {
  id: string
  at: string
  actor_id: string | null
  actor: string | null
  modulo: string
  accion: string
  registro: string | null
  antes: string | null
  despues: string | null
  link: string | null
}

export interface RcLista {
  items: RcFila[]
  total: number
  desde: string
  hasta: string
  gerencia: boolean
}

export interface RcOpciones {
  modulos: string[]
  usuarios: { id: string; full_name: string }[]
  desde: string
  hasta: string
  alcance: string | null
}

export type RcQuery = { desde?: string; hasta?: string; modulo?: string; usuario_id?: string; q?: string; offset?: number; limit?: number }
