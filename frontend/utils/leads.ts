import type {
  AccionSeguimiento,
  Cita,
  EstadoCita,
  EtapaLead,
  FuenteLead,
  LeadSummary,
  MedioContacto,
  MotivoPerdida,
  TipoCita,
  TipoEventoLead,
  TipoNegocio,
} from '~/types/leads'
import type { User } from '~/types/auth'

type Who = Pick<User, 'cargo' | 'funcion'> | null | undefined

/** Cargos/funciones with access to Atención y Preventa (mirrors policies.can_use_leads). */
export const canUseLeads = (u: Who) =>
  !!u && (USER_MANAGER_CARGOS.includes(u.cargo) || u.funcion === 'atencion_cliente' || u.funcion === 'pre_ventas')

export const isManager = (u: Who) => !!u && USER_MANAGER_CARGOS.includes(u.cargo)

export const ETAPA_LABELS: Record<EtapaLead, string> = {
  nuevo: 'Nuevo',
  en_gestion: 'En gestión',
  seguimiento: 'Seguimiento',
  cita_programada: 'Cita programada',
  ganado: 'Ganado',
  perdido: 'Perdido',
}

/** Two groups, as in the decisions (G-0xx «Fuentes de leads en dos grupos»). */
export const FUENTE_GRUPOS: { label: string; fuentes: FuenteLead[] }[] = [
  { label: 'Plataformas tradicionales', fuentes: ['ciencuadras', 'espacio_urbano', 'proppi', 'finca_raiz', 'metrocuadrado'] },
  { label: 'Redes sociales', fuentes: ['facebook', 'instagram', 'tiktok'] },
  { label: 'Otros', fuentes: ['otro'] },
]
export const FUENTE_LABELS: Record<FuenteLead, string> = {
  ciencuadras: 'Ciencuadras',
  espacio_urbano: 'Espacio Urbano',
  proppi: 'Proppi',
  finca_raiz: 'Finca Raíz',
  metrocuadrado: 'Metrocuadrado',
  facebook: 'Facebook',
  instagram: 'Instagram',
  tiktok: 'TikTok',
  otro: 'Otra fuente',
}
export const NEGOCIO_LABELS: Record<TipoNegocio, string> = { arriendo: 'Arriendo', venta: 'Venta' }
export const MOTIVO_LABELS: Record<MotivoPerdida, string> = {
  no_contesta: 'No contesta',
  numero_equivocado: 'Número equivocado',
  no_interesado: 'No interesado',
  compro_con_otro: 'Compró o arrendó con otro',
  presupuesto: 'Presupuesto no alcanza',
}
export const MOTIVOS = Object.keys(MOTIVO_LABELS) as MotivoPerdida[]
export const MEDIO_LABELS: Record<MedioContacto, string> = { whatsapp: 'WhatsApp', correo: 'Correo', sms: 'Mensaje de texto' }
export const ACCION_LABELS: Record<AccionSeguimiento, string> = {
  llamar: 'Llamar',
  enviar_opciones: 'Enviar opciones',
  enviar_informacion: 'Enviar información',
  confirmar_cita: 'Confirmar cita',
  seguimiento_propuesta: 'Hacer seguimiento a una propuesta',
  volver_a_contactar: 'Volver a contactar',
}
export const ACCIONES = Object.keys(ACCION_LABELS) as AccionSeguimiento[]

export const CITA_TIPO_LABELS: Record<TipoCita, string> = {
  visita_arriendo: 'Visita a inmueble · arriendo',
  visita_venta: 'Visita a inmueble · venta',
  captacion: 'Captación',
  visita_control: 'Visita de control al inmueble',
  inventario: 'Inventario',
  reunion_asesoria: 'Reunión de asesoría',
}
export const CITA_TIPOS = Object.keys(CITA_TIPO_LABELS) as TipoCita[]
/** Which activity an asesor needs (mirrors services.citas.REQUISITOS). */
export const CITA_REQUISITO: Record<TipoCita, string | null> = {
  visita_arriendo: 'Arriendos',
  visita_venta: 'Ventas',
  captacion: 'Captación',
  reunion_asesoria: 'Ventas o Arriendos',
  visita_control: null,
  inventario: null,
}
/** Short type for card titles: «CIT-0418 · Arriendo». */
export const CITA_TIPO_CORTO: Record<TipoCita, string> = {
  visita_arriendo: 'Arriendo',
  visita_venta: 'Venta',
  captacion: 'Captación',
  visita_control: 'Control',
  inventario: 'Inventario',
  reunion_asesoria: 'Asesoría',
}

/** History chip per event type (prototype C02 «TIP»): label, chip class, bubble background. */
export const EVENTO_TIPO: Record<TipoEventoLead, { t: string; cls: string; bg: string; grupo: string }> = {
  recibido: { t: 'Acción', cls: 'gray', bg: 'ev-acc', grupo: 'acc' },
  seguir: { t: 'Acción', cls: 'gray', bg: 'ev-acc', grupo: 'acc' },
  asignacion: { t: 'Acción', cls: 'gray', bg: 'ev-acc', grupo: 'acc' },
  etapa: { t: 'Acción', cls: 'gray', bg: 'ev-acc', grupo: 'acc' },
  datos: { t: 'Acción', cls: 'gray', bg: 'ev-acc', grupo: 'acc' },
  mensaje: { t: 'Conversación', cls: 'info', bg: 'ev-std', grupo: 'con' },
  llamada: { t: 'Llamada', cls: 'ok', bg: 'ev-std', grupo: 'lla' },
  opciones: { t: 'Opciones', cls: 'pend', bg: 'ev-std', grupo: 'opc' },
  seguimiento: { t: 'Seguimiento', cls: 'warn', bg: 'ev-warn', grupo: 'seg' },
  cita: { t: 'Cita', cls: 'ok', bg: 'ev-ok', grupo: 'cit' },
  observacion: { t: 'Observación', cls: 'gray', bg: 'ev-std', grupo: 'obs' },
}
export const EVENTO_FILTROS: [string, string][] = [
  ['todo', 'Todo'],
  ['con', 'Conversación'],
  ['lla', 'Llamadas'],
  ['opc', 'Opciones'],
  ['seg', 'Seguimientos'],
  ['cit', 'Citas'],
  ['obs', 'Observaciones'],
]

type Chip = { t: string; cls: string }

export function citaChip(estado: EstadoCita, asesor?: string | null): Chip {
  const quien = asesor ? ` · ${firstName(asesor)}` : ''
  switch (estado) {
    case 'pendiente':
      return { t: `Pendiente de aceptación${quien}`, cls: 'warn' }
    case 'aceptada':
      return { t: `Aceptada${quien}`, cls: 'ok' }
    case 'rechazada':
      return { t: `Rechazada${quien}`, cls: 'bad' }
    case 'realizada':
      return { t: 'Realizada', cls: 'info' }
    case 'cancelada':
      return { t: 'Cancelada', cls: 'gray' }
  }
}

/** «Estado» column of «Mis leads» (prototype C01). */
export function leadEstado(l: LeadSummary): Chip {
  switch (l.etapa) {
    case 'nuevo':
      return { t: l.assigned_to ? 'Nuevo · sin acciones aún' : 'Nuevo · sin responsable', cls: 'warn' }
    case 'en_gestion':
      return { t: 'En gestión', cls: 'info' }
    case 'seguimiento':
      return { t: 'Seguimiento', cls: 'gray' }
    case 'cita_programada': {
      const e = l.cita_activa?.estado
      if (e === 'aceptada') return { t: 'Cita aceptada', cls: 'ok' }
      if (e === 'rechazada') return { t: 'Cita rechazada', cls: 'bad' }
      return { t: 'Cita pendiente de aceptación', cls: 'warn' }
    }
    case 'ganado':
      return { t: 'Ganado', cls: 'ok' }
    case 'perdido':
      return { t: 'Perdido', cls: 'gray' }
  }
}

/** «Próxima acción o resultado» column. */
export function leadProxima(l: LeadSummary): string {
  if (l.etapa === 'perdido') return `Perdido · ${l.motivo_perdida ? MOTIVO_LABELS[l.motivo_perdida] : ''}`
  if (l.etapa === 'ganado') return 'Ganado'
  if (l.cita_activa) {
    const c = l.cita_activa
    return `${c.code} · ${c.asesor_name ?? 'sin asesor'} · ${fmtCuando(c.scheduled_at)}`
  }
  if (l.proximo_seguimiento) {
    const s = l.proximo_seguimiento
    return `Seguimiento ${fmtCuando(s.due_at)} · ${ACCION_LABELS[s.accion]}`
  }
  if (l.ultimo_evento && l.ultimo_evento.tipo !== 'recibido' && l.ultimo_evento.tipo !== 'seguir')
    return `Última acción: ${l.ultimo_evento.titulo}`
  return 'Registra la primera acción'
}

export const llamadasTxt = (n: number) => `${n} ${n === 1 ? 'llamada' : 'llamadas'}`

/** Why a cita needs action (red note of C03). */
export function citaAlerta(c: Cita): string | null {
  if (!c.requiere_accion) return null
  if (c.estado === 'rechazada')
    return `${c.asesor?.full_name ?? 'El asesor'} la rechazó${c.motivo ? ` («${c.motivo}»)` : ''}. Asigna otro asesor, reprográmala o cancélala.`
  if (!c.asesor) return 'La cita no tiene asesor. Asigna uno, reprográmala o cancélala.'
  const min = minutesUntil(c.scheduled_at)
  if (min < 0) return `La hora de la cita ya pasó y ${c.asesor.full_name} no la aceptó.`
  return `Faltan ${min} min para la cita y ${c.asesor.full_name} no la ha aceptado.`
}
