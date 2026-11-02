export interface Perfil {
  id: string
  full_name: string
  cargo_txt: string
  area: string
  actividades: string[]
  regla_nombre: string
  datos: { k: string; v: string }[]
  resultados: { href: string; mes: string; txt: string } | null
  accesos: { t: string; href: string }[]
  politica_aceptada_at: string | null
  tiene_foto: boolean
}
