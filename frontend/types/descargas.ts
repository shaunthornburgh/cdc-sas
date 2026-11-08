/** X10 «Descargas del personal» (backend: app/services/descargas.py). */

export type DsGrupo = 'ase' | 'ate' | 'coo' | 'aux' | 'ger'
export type DsAlcance = 'tod' | 'car' | 'emp'

export interface DsOpciones {
  tipos: { key: string; titulo: string; contenido: string; disponible: boolean; grupos: DsGrupo[] }[]
  grupos: Record<DsGrupo, string>
  personas: { id: string; full_name: string; grupo: DsGrupo }[]
  recientes: { at: string; archivo: string | null; texto: string; filas: string | null }[]
}

export interface DsQuery {
  desde: string
  hasta: string
  alcance: DsAlcance
  grupo?: string
  user_id?: string
}

export interface DsVistaPrevia {
  filas: number
  texto: string
  archivo: string
}
