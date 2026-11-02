export interface IntItem {
  id: string
  clave: string
  nombre: string
  grupo: 'trad' | 'red' | 'otro'
  estado: 'sin_conectar' | 'por_confirmar' | 'conectado'
  estado_txt: string
  estado_cls: string
  es_lead: boolean
  res: string
}

export interface IntTablero {
  desde: string
  hasta: string
  kpis: { leads: number; costos: number; costo_lead: number | null; cerrados: number; conversion: number | null }
  grupos: { grupo: string; titulo: string; items: IntItem[] }[]
  como: Record<string, string>
  grupos_txt: Record<string, string>
}

export interface IntCampo {
  key: string
  label: string
  ph: string
  secreto: boolean
  valor: string | null
  guardado: string | null
}

export interface IntDetalle extends IntItem {
  resultados: {
    leads: number
    costo: number
    costo_lead: number | null
    cerrados: number
    arriendos: number
    ventas: number
    sin_negocio: number
    conversion: number | null
    costo_cierre: number | null
    en_proceso: number
    ultimo: string | null
  } | null
  costo: number
  origen_costo: string
  nota: string | null
  uso_t: string | null
  uso: string | null
  conexion: {
    que: string
    donde: string
    ultimo_dato: string
    campos: IntCampo[]
    nota_campos: string | null
    como: string
    como_txt: string
    costo_mensual: number | null
    avisar_falla: boolean
    prueba_at: string | null
    prueba_txt: string | null
    plataforma: string | null
  }
  historial: { accion: string; antes: string | null; despues: string | null; actor: string | null; at: string }[]
}
