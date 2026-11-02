export type Cargo =
  | 'gerencia'
  | 'coordinacion'
  | 'asesor'
  | 'auxiliar_administrativa'
  | 'atencion_cliente'

export type ActividadComercial = 'captacion' | 'ventas' | 'arriendos'

export type FuncionIndependiente = 'atencion_cliente' | 'pre_ventas'

export interface User {
  id: string
  email: string
  full_name: string
  cargo: Cargo
  funcion: FuncionIndependiente | null
  actividades: ActividadComercial[]
  gps_checkin_enabled: boolean
  is_active: boolean
  telefono?: string | null
  documento?: string | null
  fecha_ingreso?: string | null
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number
  refresh_expires_in: number
}

export interface LoginResponse extends TokenPair {
  user: User
}

export type UserCreate = {
  email: string
  password: string
  full_name: string
  cargo: Cargo
  funcion: FuncionIndependiente | null
  actividades: ActividadComercial[]
  is_active: boolean
}

export type UserUpdate = Partial<Pick<User, 'full_name' | 'cargo' | 'is_active' | 'funcion' | 'telefono' | 'documento' | 'fecha_ingreso'>>

export interface UserCambio {
  campo: string
  campo_txt: string
  antes: string | null
  despues: string | null
  actor_name: string | null
  created_at: string
}

export interface ActividadEvento {
  actividad: ActividadComercial
  activada: boolean
  changed_by_id: string | null
  changed_by_name: string | null
  created_at: string
}
