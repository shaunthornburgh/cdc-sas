import type { ActividadComercial, Cargo } from '~/types/auth'
import type { Captacion, EstadoCaptacion, MotivoRechazoCaptacion, TipoInmueble } from '~/types/captaciones'

type Who = { cargo: Cargo; actividades: readonly ActividadComercial[]; is_active: boolean } | null | undefined

/** Has the Captación activity (mirrors policies.can_capture). */
export const canCapture = (u: Who) => !!u && u.is_active && u.actividades.includes('captacion')

/** Captadores plus Coordinación / Gerencia (mirrors policies.can_use_captaciones). */
export const canUseCaptaciones = (u: Who) => !!u && (USER_MANAGER_CARGOS.includes(u.cargo) || canCapture(u))

/** K12 chips: «Por verificar» warn · «✓ Aprobada» ok · «Rechazada» bad. */
export const CAPTACION_ESTADO: Record<EstadoCaptacion, { t: string; cls: string }> = {
  por_verificar: { t: 'Por verificar', cls: 'warn' },
  aprobada: { t: '✓ Aprobada', cls: 'ok' },
  rechazada: { t: 'Rechazada', cls: 'bad' },
}
export const CAPTACION_TABS: [EstadoCaptacion, string][] = [
  ['por_verificar', 'Por verificar'],
  ['aprobada', 'Aprobadas'],
  ['rechazada', 'Rechazadas'],
]

export const MOTIVO_RECHAZO_LABELS: Record<MotivoRechazoCaptacion, string> = {
  codigo_inexistente: 'Código inexistente',
  codigo_no_corresponde: 'El código no corresponde a esa dirección',
}
export const MOTIVOS_RECHAZO = Object.keys(MOTIVO_RECHAZO_LABELS) as MotivoRechazoCaptacion[]

export const TIPO_INMUEBLE_LABELS: Record<TipoInmueble, string> = {
  apartamento: 'Apartamento',
  casa: 'Casa',
  local: 'Local',
  oficina: 'Oficina',
  lote: 'Lote',
  bodega: 'Bodega',
}
export const TIPOS_INMUEBLE = Object.keys(TIPO_INMUEBLE_LABELS) as TipoInmueble[]
export const MUNICIPIOS = ['Medellín', 'Envigado', 'Itagüí', 'Sabaneta', 'Bello', 'La Estrella', 'Rionegro']

export const modoTxt = (c: Pick<Captacion, 'modo'>) => (c.modo === 'rapido' ? 'Registro rápido' : 'Formulario completo')

const cop = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })
export const fmtCOP = (n: number | null | undefined) => (n == null ? '—' : cop.format(n))

/** «Ubicación del asesor» line of K12. Distance to the address needs geocoding (pending). */
export function ubicacionTxt(c: Captacion): string {
  if (!c.gps_at) return 'Sin ubicación registrada'
  const prec = c.gps_precision_m != null ? ` · precisión ±${c.gps_precision_m} m` : ''
  return `Ubicación tomada al enviar${prec} · ${fmtHora(c.gps_at)}`
}
export const mapaUrl = (c: Captacion) =>
  c.gps_lat && c.gps_lng
    ? `https://www.openstreetmap.org/?mlat=${c.gps_lat}&mlon=${c.gps_lng}#map=18/${c.gps_lat}/${c.gps_lng}`
    : null

/** Short status line under each captación (K12 / M15). */
export function captacionDetalle(c: Captacion): string {
  const quien = firstName(c.asesor.full_name)
  if (c.estado === 'aprobada') {
    const por = c.verificado_por_name ? `por ${c.verificado_por_name} ` : ''
    const cuando = c.verificado_at ? `el ${fmtCuando(c.verificado_at)} ` : ''
    return `Aprobada ${por}${cuando}· suma en la captación de ${quien}`
  }
  if (c.estado === 'rechazada') {
    const mot = c.motivo_rechazo ? MOTIVO_RECHAZO_LABELS[c.motivo_rechazo].toLowerCase() : ''
    const obs = c.observacion_rechazo ? ` («${c.observacion_rechazo}»)` : ''
    return `Rechazada${c.verificado_at ? ` el ${fmtCuando(c.verificado_at)}` : ''} · motivo: ${mot}${obs} · ${quien} debe corregirla y volver a enviarla`
  }
  return c.reenvios ? `Corregida y reenviada · esperando a Coordinación` : `${modoTxt(c)} · esperando a Coordinación`
}

/** Asesor: has Captación, Ventas or Arriendos and no independent function (policies). */
export const hasCommercialActivity = (u: (Who & { funcion?: string | null }) | null | undefined) =>
  !!u && u.is_active && !u.funcion && u.actividades.length > 0

/** Pedidos: asesores, Atención / Pre-ventas, Coordinación and Gerencia (policies.can_use_pedidos). */
export const canUsePedidos = (u: (Who & { funcion?: string | null }) | null | undefined) =>
  !!u && (hasCommercialActivity(u) || u.funcion === 'atencion_cliente' || u.funcion === 'pre_ventas' || USER_MANAGER_CARGOS.includes(u.cargo))

/** Property catalog: commercial team, Auxiliar and managers (services.inmuebles.can_view). */
export const canUseInmuebles = (u: (Who & { funcion?: string | null }) | null | undefined) =>
  !!u && (canUsePedidos(u) || u.cargo === 'auxiliar_administrativa')
