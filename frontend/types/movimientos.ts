import type { Cargo } from '~/types/auth'

export type TipoMovimiento = 'salida_ruta' | 'tiempo_detenido' | 'salida_zona' | 'trabajo_campo' | 'atencion_campo'
export type EstadoMovimiento = 'sin_justificar' | 'por_revisar' | 'aprobada' | 'rechazada' | 'registro'
export type MotivoMovimiento = 'cita_fuera_ruta' | 'permiso_personal' | 'cita_no_programada' | 'inventario' | 'imprevisto_personal'
export type TipoCampo = 'apoyo_cita' | 'acompanamiento_ruta' | 'salida_grupal' | 'otra'
export type ActividadCampo = 'captacion' | 'visita_propietario' | 'cita_venta' | 'cita_arriendo' | 'inventario' | 'otra'
export type PerfilGps = 'asesor' | 'coordinacion' | 'atencion'

export interface MovEmpleado {
  id: string
  full_name: string
  cargo: Cargo
  perfil_txt: string
}

export interface Movimiento {
  id: string
  code: string
  empleado: MovEmpleado
  tipo: TipoMovimiento
  tipo_txt: string
  es_alerta: boolean
  estado: EstadoMovimiento
  estado_txt: string
  vencida: boolean
  descuenta: boolean
  plazo_at: string | null
  ocurrido_at: string
  fin_at: string | null
  en_curso: boolean
  duracion_min: number | null
  duracion_txt: string | null
  minutos_umbral: number | null
  lugar: string | null
  tiene_ubicacion: boolean
  detalle_txt: string
  motivo: MotivoMovimiento | null
  motivo_txt: string | null
  inmueble_codigo: string | null
  inmueble_en_catalogo: boolean
  cliente: string | null
  motivo_texto: string | null
  autorizo: string | null
  autorizo_txt: string | null
  evidencias: number
  observacion: string | null
  justificada_at: string | null
  revisa: string | null
  revisado_por_name: string | null
  revisado_at: string | null
  nota_revision: string | null
  tipo_campo: TipoCampo | null
  tipo_campo_txt: string | null
  actividad_campo: ActividadCampo | null
  actividad_campo_txt: string | null
  cita_code: string | null
  acompanados: string[]
  detalle: string | null
  puede_justificar: boolean
  puede_revisar: boolean
  puede_finalizar: boolean
}

export interface MovKpis {
  alertas: number
  justificadas: number
  justificadas_pct: number | null
  sin_justificar: number
  vencidas: number
  por_revisar: number
  por_revisar_gerencia: number
  rechazadas: number
  coord_campo_min: number
  coord_campo_salidas: number
}

export interface MovPorEmpleado {
  empleado: MovEmpleado
  alertas: number
  justificadas: number
  sin_justificar: number
  rechazadas: number
  vencidas: number
  campo_min: number
}

export interface MovimientoList {
  items: Movimiento[]
  desde: string
  hasta: string
  kpis: MovKpis
  por_empleado: MovPorEmpleado[]
  pendientes: Movimiento[]
}

export interface MovConfig {
  minutos_alerta: number
  plazo_horas: number | null
  minutos_opciones: number[]
  updated_by_name: string | null
  updated_at: string | null
}

export interface MovEvento {
  id: string
  tipo: string
  tipo_txt: string
  actor_name: string | null
  estado_antes: string | null
  estado_despues: string | null
  detalle: string | null
  created_at: string
}

export interface MovOpciones {
  perfil: PerfilGps | null
  panel: boolean
  gerencia: boolean
  gps_activo: boolean
  tipos: Record<TipoMovimiento, string>
  estados: Record<EstadoMovimiento, string>
  motivos: Record<MotivoMovimiento, string>
  motivos_por_tipo: Partial<Record<TipoMovimiento, MotivoMovimiento[]>>
  motivos_con_inmueble: MotivoMovimiento[]
  autorizo: Record<string, string>
  tipos_campo: Partial<Record<TipoCampo, string>>
  actividades_campo: Record<ActividadCampo, string>
  alertas_propias: TipoMovimiento[]
  empleados: MovEmpleado[]
  asesores: { id: string; txt: string }[]
  citas: { id: string; txt: string }[]
  config: MovConfig
  desde: string
  hasta: string
  jornada: string
}

export interface MovMapaPunto {
  id: string
  code: string
  empleado: string
  tipo_txt: string
  estado: EstadoMovimiento
  hora: string
  lugar: string | null
  x: number
  y: number
}

export interface MovCampoAhora {
  abiertos: Movimiento[]
  ultimo: Movimiento | null
}

export interface MovPanel {
  config: MovConfig
  cambios_config: MovEvento[]
  con_gps: string[]
  sin_gps: string[]
  coordinador_campo: MovCampoAhora
  atencion_campo: MovCampoAhora
  hoy: Movimiento[]
  mapa: MovMapaPunto[]
}

export type MovQuery = { desde?: string; hasta?: string; empleado_id?: string; tipo?: string; estado?: string }
