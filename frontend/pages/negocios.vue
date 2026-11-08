<script setup lang="ts">
import type { NegCategoria, NegDetalle, NegItem, NegTablero } from '~/types/negocios'

/**
 * X02 «Negocios» (Auxiliar administrativa; Gerencia and Coordinación see it, Coordinación without
 * money) and M16 «Detalle del negocio» as «Mis negocios» for the asesor who closes each deal.
 * The deals are the NEG-… created when a lead is marked «Ganado» (see Compensación).
 */
definePageMeta({ cargos: ['gerencia', 'coordinacion', 'auxiliar_administrativa', 'asesor'] })
useHead({ title: 'Negocios · Casa Dolce Casa' })

const api = useNegocios()
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const hoy = localDate(0)
const home = computed(() => {
  const c = auth.user.value?.cargo
  return c === 'gerencia' || c === 'coordinacion' ? '/coordinacion' : c === 'asesor' ? '/asesor' : '/'
})

// ---- filters (X02 · G-091)
const desdeDef = (() => {
  const d = new Date(`${hoy}T00:00:00`)
  d.setMonth(d.getMonth() - 3, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`
})()
const f = reactive({ desde: desdeDef, hasta: hoy, tipo: '' })
const fErr = computed(() => !f.desde || !f.hasta || f.desde > f.hasta)
const q = computed(() => (fErr.value ? { desde: desdeDef, hasta: hoy } : { desde: f.desde, hasta: f.hasta, ...(f.tipo ? { tipo: f.tipo } : {}) }))
const { data, refresh, error } = await useAsyncData('negocios', () => api.tablero(q.value), { watch: [q] })
if (error.value && (error.value as { statusCode?: number }).statusCode === 403) {
  throw createError({ statusCode: 403, statusMessage: 'Los negocios los ven la Auxiliar administrativa, Gerencia, Coordinación y los asesores que los cierran.', fatal: true })
}
const T = computed(() => data.value as NegTablero | null)
const asesor = computed(() => T.value?.modo === 'asesor')
const dinero = computed(() => T.value?.modo === 'auxiliar' || T.value?.modo === 'gerencia')
const gestiona = computed(() => !!T.value?.puede?.gestionar)
const datos = computed(() => !!T.value?.puede?.datos)

type Tab = 'sol' | 'proc' | 'cer' | 'cai'
const tab = ref<Tab>((['sol', 'proc', 'cer', 'cai'].includes(String(route.query.tab)) ? route.query.tab : 'proc') as Tab)
watch(tab, (t) => router.replace({ query: t === 'proc' ? {} : { tab: t } }))
const kpi = ref<'' | 'tot' | 'gan' | NegCategoria>('')
const tabs = computed<[Tab, string][]>(() => {
  const c = T.value?.counts
  return [
    ['sol', `Firmas por confirmar (${c?.sol ?? 0})`],
    ['proc', `En proceso (${c?.proc ?? 0})`],
    ['cer', `Cerrados (${c?.cer ?? 0})`],
    ['cai', `Caídos (${c?.cai ?? 0})`],
  ]
})
function pickTab(t: Tab) {
  tab.value = t
  kpi.value = ''
  msg.value = null
}
const rows = computed(() => {
  const L = T.value?.items ?? []
  if (asesor.value) return L
  if (kpi.value && kpi.value !== 'tot' && kpi.value !== 'gan') return L.filter((n) => n.categoria === kpi.value)
  if (kpi.value) return L
  if (tab.value === 'sol') return L.filter((n) => n.situacion === 'por_confirmar')
  if (tab.value === 'cer') return L.filter((n) => n.situacion === 'cerrado')
  if (tab.value === 'cai') return L.filter((n) => n.situacion === 'caido')
  return L.filter((n) => n.abierto)
})

const fd = (iso: string | null | undefined) => (iso ? fmtFecha(iso) : '—')
const mf = (v: number) => {
  const a = Math.abs(v)
  const s = a >= 1e6 ? `$${(a / 1e6).toFixed(1).replace('.', ',')} M` : fmtCOP(a)
  return v < 0 ? `−${s}` : s
}
const pct = (v: number | null | undefined) => (v == null ? '—' : `${String(Math.round(v * 100) / 100).replace('.', ',')} %`)
const rango = computed(() => `${fd(q.value.desde)} al ${fd(q.value.hasta)}`)

const kpis = computed(() => {
  const k = T.value?.kpis
  if (!k) return []
  const out: { k: typeof kpi.value; t: string; v: string; d: string; cls?: string }[] = [
    { k: 'tot', t: 'Total de negocios', v: String(k.total), d: 'en el rango' },
    { k: 'neg', t: 'En negociación', v: String(k.neg), d: 'sin firmas todavía' },
    { k: 'pc', t: 'Por cerrar', v: String(k.pc), d: 'firma por confirmar o promesa firmada' },
    { k: 'cer', t: 'Cerrados', v: String(k.cer), d: 'con firma confirmada' },
    { k: 'cai', t: 'Caídos', v: String(k.cai), d: `${k.cai_reportadas} reportado${k.cai_reportadas === 1 ? '' : 's'} por confirmar`, cls: 'red' },
  ]
  if (k.ganancia != null) out.push({ k: 'gan', t: 'Ganancia', v: mf(k.ganancia), d: `de los cerrados · ${mf(k.proyectada ?? 0)} proyectada en proceso`, cls: k.ganancia < 0 ? 'red' : 'green' })
  return out
})
const maxTipo = computed(() => Math.max(1, ...(T.value?.por_tipo ?? []).map((t) => t.n)))
const CAT: Record<NegCategoria, [string, string]> = { neg: ['En negociación', 'info'], pc: ['Por cerrar', 'warn'], cer: ['Cerrado', 'ok'], cai: ['Caído', 'bad'] }

// ---- messages and actions
const msg = ref<{ t: string; ok: boolean } | null>(null)
const busy = ref(false)
async function run(fn: () => Promise<unknown>, t: string | ((r: NegDetalle) => string)) {
  busy.value = true
  try {
    const r = (await fn()) as NegDetalle
    msg.value = { t: typeof t === 'string' ? t : t(r), ok: true }
    if (hist[r?.id]) hist[r.id] = r.historial
    await refresh()
    return true
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
    return false
  } finally {
    busy.value = false
  }
}

// One open form per deal
type Form = '' | 'docs' | 'caida' | 'din' | 'cer' | 'dev' | 'etapa' | 'valor'
const open = reactive<Record<string, Form>>({})
const F = reactive({
  docs: '',
  motivo: '',
  obs: '',
  valor: '',
  fecha: hoy,
  momento: 'promesa',
  soporte: false,
  contrato: false,
  etapa: '',
  oferta: '',
  notaria: '',
  nfecha: '',
  nhora: '10:00',
  pct: '',
  canon: '',
  inmueble: '',
  referido: '',
})
function toggle(n: NegItem, form: Form) {
  const cur = open[n.id]
  for (const k of Object.keys(open)) delete open[k]
  if (cur === form) return
  open[n.id] = form
  msg.value = null
  Object.assign(F, {
    docs: n.docs_ubicacion ?? '',
    motivo: form === 'dev' ? (T.value?.motivos_devolver?.[0] ?? '') : '',
    obs: '',
    valor: '',
    fecha: hoy,
    momento: n.promesa_fecha ? 'escritura' : 'promesa',
    soporte: false,
    contrato: n.contrato_adjunto,
    etapa: siguiente(n) ?? n.etapa,
    oferta: '',
    notaria: '',
    nfecha: '',
    nhora: '10:00',
    pct: n.pct_venta != null ? String(n.pct_venta).replace('.', ',') : '',
    canon: n.valor ? String(n.valor) : '',
    inmueble: n.inmueble_id ?? '',
    referido: n.referido ?? '',
  })
}
const isOpen = (n: NegItem, form: Form) => open[n.id] === form
const motivosCaida = (n: NegItem) => (T.value?.motivos_caida ?? []).filter((m) => n.negocio !== 'venta' || m !== 'Póliza negada')

// Stages (M16): the next one, never the last (that one comes with the signature)
function siguiente(n: NegItem): string | null {
  const i = n.etapas.indexOf(n.etapa)
  const s = n.etapas[i + 1]
  return s && i + 1 < n.etapas.length - 1 ? s : null
}
const stepCls = (n: NegItem, i: number) => {
  const j = n.etapas.indexOf(n.etapa)
  if (n.situacion === 'cerrado') return 'done'
  if (n.situacion === 'caido') return i <= j ? 'bad' : ''
  return i === j ? 'on' : i < j ? 'done' : ''
}

// Copy for the signature buttons (G-033: sales have two)
const cerTxt = (n: NegItem) => (n.paso_promesa ? 'Confirmar firma de la promesa' : n.negocio === 'venta' ? 'Confirmar firma de la escritura y dar negocio cerrado' : 'Confirmar firma y dar negocio cerrado')
const firmaLbl = (n: NegItem) => (n.paso_promesa ? 'Fecha de firma de la promesa' : n.negocio === 'venta' ? 'Fecha de firma de la escritura' : 'Fecha de firma')
const solTxt = (n: NegItem) => {
  if (n.situacion === 'cerrado') return 'Confirmado'
  if (n.situacion === 'caido') return '—'
  if (n.solicitud) return `${n.solicitud === 'promesa' ? 'Firma de la promesa' : 'Sí'} · ${n.solicitud_at ? fmtCuando(n.solicitud_at) : ''}${n.asesor ? ` · ${firstName(n.asesor.full_name)} dice que el cliente firmó` : ''}`
  if (n.devuelto_motivo) return `Devuelto al asesor · ${n.devuelto_motivo}`
  return 'No'
}
const firma1 = (n: NegItem): [string, string] =>
  n.promesa_fecha ? [`✓ Confirmada ${fd(n.promesa_fecha)}`, 'ok'] : n.solicitud === 'promesa' ? ['Solicitada · por confirmar', 'warn'] : ['Pendiente', 'gray']
const firma2 = (n: NegItem): [string, string] =>
  n.firma_fecha ? [`✓ Confirmada ${fd(n.firma_fecha)}`, 'ok'] : n.notaria_at ? [`Cita en notaría ${fmtCuando(n.notaria_at)}`, 'info'] : n.solicitud === 'cierre' ? ['Solicitada · por confirmar', 'warn'] : ['Pendiente', 'gray']
const valorTxt = (n: NegItem) => (n.valor ? (n.negocio === 'venta' ? fmtCOP(n.valor) : `Canon ${fmtCOP(n.valor)}`) : 'Valor sin registrar')
const cardCls = (n: NegItem) => (n.abierto && n.caida?.reportada_at ? 'b-bad' : n.situacion === 'por_confirmar' ? 'b-warn' : '')

// Ganancia detail
const gOn = reactive<Record<string, boolean>>({})
const gLbl = (n: NegItem) => (n.situacion === 'cerrado' ? 'Ganancia que dejó el negocio' : n.situacion === 'caido' ? 'Ganancia · negocio caído (no genera ingreso)' : 'Ganancia proyectada (si se cierra)')
const gSub = (n: NegItem) =>
  !n.ganancia?.con_valor
    ? 'registra el valor del negocio para calcularla'
    : n.negocio === 'venta'
      ? `después de comisiones e IVA recaudado · ${pct(n.ganancia.pct)} + IVA`
      : 'después de comisiones, póliza, IVA recaudado y referidos'
const tarifasTxt = computed(() => {
  const t = T.value?.tarifas
  if (!t) return ''
  return `Tarifas de Gerencia (Configuración): arriendo ${pct(t.arriendo_pct)} + IVA y papelería ${fmtCOP(t.papeleria)} con IVA · venta ${pct(t.venta_pct)} + IVA por defecto · IVA ${pct(t.iva_pct)} · referidos ${pct(t.referidos_pct)} del canon. Esta ganancia es la base de las comisiones en «Comisiones, bonos y pagos».`
})
const inmueblesDe = (n: NegItem) => (T.value?.inmuebles ?? []).filter((i) => !n.negocio || i.negocio === n.negocio)

async function guardar(n: NegItem, body: object, t: string) {
  if (await run(() => api.editar(n.id, body), t)) delete open[n.id]
}
const guardarDocs = (n: NegItem) => guardar(n, { docs_ubicacion: F.docs }, `${n.code}: ubicación de documentos guardada. Queda en el registro de cambios.`)
const togContrato = (n: NegItem) => run(() => api.editar(n.id, { contrato_adjunto: !n.contrato_adjunto }), `${n.code}: ${n.contrato_adjunto ? 'se quitó el contrato adjunto' : 'contrato marcado como adjunto'}.`)
function guardarValor(n: NegItem) {
  const body: Record<string, unknown> = { valor: F.canon ? Number(String(F.canon).replace(/\D/g, '')) : null, inmueble_id: F.inmueble || null }
  if (n.negocio === 'venta') body.pct_venta = F.pct ? Number(F.pct.replace(',', '.')) : null
  else body.referido = F.referido || null
  return guardar(n, body, `${n.code}: datos guardados. Se recalculó la ganancia${n.situacion === 'cerrado' ? ' y las comisiones del negocio' : ''}. Queda en el registro de cambios.`)
}
const setUso = (n: NegItem, k: 'uso_comercial' | 'arrendatario_juridica', v: boolean) => {
  if (!datos.value || n[k] === v || n.situacion === 'caido') return
  return run(() => api.editar(n.id, { [k]: v }), `${n.code}: guardado.`)
}

// Auxiliar actions
const conf = ref<NegItem | null>(null)
async function confirmar() {
  const n = conf.value!
  conf.value = null
  const ok = await run(
    () => api.confirmar(n.id, { fecha: F.fecha, contrato_adjunto: F.contrato, observacion: F.obs || null }),
    (r) => {
      const res = typeof r.resultado === 'object' ? r.resultado : null
      if (!res?.cerrado) return `${n.code}: firma de la promesa confirmada el ${fd(F.fecha)}. La venta cuenta en la meta del mes; falta la escritura para dar «negocio cerrado».`
      return [
        `${n.code}: negocio cerrado (firma del ${fd(F.fecha)}).`,
        res.comisiones ? 'Se registró la ganancia y se generaron las comisiones para visto bueno.' : n.valor ? '' : 'Registra el valor del negocio para calcular la ganancia y generar las comisiones.',
        res.poliza ? 'Se registró la firma del contrato en «Pólizas»: corre el plazo para activar la póliza.' : '',
        n.asesor ? `${n.asesor.full_name} recibe el aviso.` : '',
      ]
        .filter(Boolean)
        .join(' ')
    },
  )
  if (ok) delete open[n.id]
}
async function devolver(n: NegItem) {
  if (await run(() => api.devolver(n.id, F.motivo), `${n.code} devuelto${n.asesor ? ` a ${n.asesor.full_name}` : ''} con el motivo. Le llega el aviso.`)) delete open[n.id]
}
async function caida(n: NegItem) {
  const ok = await run(
    () => api.caida(n.id, F.motivo, F.obs),
    asesor.value
      ? 'Enviado a la Auxiliar administrativa: confirma la caída del negocio. Te llega el aviso cuando lo haga.'
      : `${n.code}: negocio caído. Salió de «En proceso», no genera comisión y sus comisiones sin pagar se anularon. ${n.asesor ? `${n.asesor.full_name} y ` : ''}Gerencia reciben el aviso.`,
  )
  if (ok) delete open[n.id]
}
const descartar = (n: NegItem) => run(() => api.descartarCaida(n.id), `${n.code}: la caída se descartó; el negocio sigue en proceso.`)
async function abono(n: NegItem) {
  const v = Number(String(F.valor).replace(/\D/g, ''))
  const ok = await run(
    () => api.abono(n.id, { valor: v, fecha: F.fecha, momento: F.momento, soporte: F.soporte }),
    `${n.code}: dinero recibido registrado (${fmtCOP(v)}). Queda en el registro de cambios.`,
  )
  if (ok) delete open[n.id]
}

// Asesor actions (M16)
async function pasarEtapa(n: NegItem) {
  const esc = F.etapa === 'Escrituración' && n.etapa !== 'Escrituración'
  const ok = await run(
    () =>
      api.etapa(n.id, {
        etapa: F.etapa,
        oferta: F.oferta || null,
        observacion: F.obs,
        notaria: esc ? F.notaria : null,
        notaria_at: esc && F.nfecha ? `${F.nfecha}T${F.nhora || '10:00'}:00` : null,
      }),
    F.etapa === n.etapa ? 'Nueva oferta registrada. Queda en el historial.' : esc ? `Etapa actualizada a «Escrituración». Te llega el recordatorio de la cita en notaría.` : `Etapa actualizada a «${F.etapa}». Queda en el historial.`,
  )
  if (ok) delete open[n.id]
}
const sol = ref<NegItem | null>(null)
async function solicitar() {
  const n = sol.value!
  sol.value = null
  await run(() => api.solicitar(n.id), `Enviado a la Auxiliar administrativa: confirma la firma${n.paso_promesa ? ' de la promesa' : ''} y da «negocio cerrado». Solo entonces cuenta en tu rendimiento.`)
}

// History (loaded on demand)
const hist = reactive<Record<string, NegDetalle['historial']>>({})
const verHist = reactive<Record<string, boolean>>({})
async function toggleHist(n: NegItem) {
  verHist[n.id] = !verHist[n.id]
  if (verHist[n.id] && !hist[n.id]) {
    try {
      hist[n.id] = (await api.ver(n.id)).historial
    } catch (e) {
      msg.value = { t: apiErrorMessage(e), ok: false }
    }
  }
}
// The asesor opens one deal at a time
const sel = ref<string | null>((route.query.id as string) || null)
watch(
  () => T.value?.items,
  (L) => {
    if (asesor.value && L?.length && !sel.value) sel.value = L.find((n) => n.abierto)?.id ?? L[0]!.id
  },
  { immediate: true },
)
watch(sel, (id) => {
  if (id && asesor.value && !hist[id]) {
    verHist[id] = true
    api.ver(id).then((d) => (hist[id] = d.historial)).catch(() => {})
  }
}, { immediate: true })
const actual = computed(() => (asesor.value ? T.value?.items.find((n) => n.id === sel.value) ?? null : null))
const estadoAsesor = (n: NegItem): [string, string] =>
  n.situacion === 'caido' ? ['Negocio caído', 'bad'] : n.caida?.reportada_at ? ['Caída por confirmar', 'bad'] : n.situacion === 'cerrado' ? ['✓ Negocio cerrado', 'ok'] : n.solicitud ? ['Cierre solicitado', 'info'] : n.devuelto_motivo ? ['Devuelto', 'warn'] : ['En proceso', 'warn']
</script>

<template>
  <!-- ================= Asesor · M16 ================= -->
  <template v-if="asesor && T">
    <PageBar title="Mis negocios" subtitle="Tus negocios en proceso y cerrados · pasa la etapa, registra la oferta y solicita el cierre cuando el cliente firme" :back="home" />
    <div class="cnt">
      <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.t }}</b></div>
      <div v-if="!T.items.length" class="note">Aún no tienes negocios. Cuando un lead que atendiste en una cita queda «Ganado», el negocio aparece aquí.</div>
      <div v-else class="mlay">
        <div class="mlist">
          <button v-for="n in T.items" :key="n.id" type="button" class="card mit" :class="{ sel: sel === n.id }" @click="sel = n.id; msg = null">
            <div class="sb gp8"><b>{{ n.code }} · {{ n.tipo }}</b><span class="chip" :class="estadoAsesor(n)[1]">{{ estadoAsesor(n)[0] }}</span></div>
            <div class="mut tiny">{{ n.inmueble }} · {{ n.cliente }}</div>
            <div class="mut tiny">{{ n.etapa }}</div>
          </button>
        </div>

        <div v-if="actual" :key="actual.id" class="col12">
          <div class="card col10">
            <div class="sb"><b class="t17">{{ actual.code }} · {{ actual.tipo }}</b><span class="chip" :class="estadoAsesor(actual)[1]">{{ estadoAsesor(actual)[0] }}</span></div>
            <div class="kv">
              <span class="mut">Inmueble</span><b>{{ actual.inmueble }}</b>
              <span class="mut">Cliente</span><b>{{ actual.cliente }}</b>
              <span class="mut">Valor</span><b>{{ valorTxt(actual) }}</b>
              <span class="mut">Origen</span><b>{{ actual.origen }}</b>
              <span class="mut">Captó</span><b>{{ actual.captador?.full_name ?? '—' }}</b>
              <span class="mut">Cierra</span><b>{{ actual.asesor?.full_name ?? '—' }}</b>
              <span class="mut">Cita generada por</span><b>{{ actual.filtro ? `${actual.filtro.full_name} · Atención y Preventa` : '—' }}</b>
              <span class="mut">Última oferta</span><b>{{ actual.oferta ?? '—' }}</b>
            </div>
          </div>

          <div class="card col8">
            <div class="sb"><span class="lbl">Etapa del negocio</span><span class="chip pend t10">Etapas: ejemplo</span></div>
            <div class="stp fw"><div v-for="(e, i) in actual.etapas" :key="e" :class="stepCls(actual, i)">{{ e }}</div></div>
            <div class="mut tiny">Las etapas definitivas de venta y de arriendo: PENDIENTE DE CONFIGURACIÓN.</div>
          </div>

          <div v-if="actual.devuelto_motivo && actual.abierto && !actual.solicitud" class="note warn"><b>La Auxiliar administrativa devolvió el cierre:</b> {{ actual.devuelto_motivo }}. Cuando el cliente firme, vuelve a solicitarlo.</div>
          <div v-if="actual.solicitud && actual.abierto" class="note"><b>Cierre solicitado {{ actual.solicitud_at ? fmtCuando(actual.solicitud_at) : '' }}.</b> La Auxiliar administrativa confirma la firma{{ actual.solicitud === 'promesa' ? ' de la promesa' : '' }}; te llega el aviso.</div>
          <div v-if="actual.caida?.reportada_at && actual.abierto" class="note bad"><b>Reportaste la caída del negocio:</b> {{ actual.caida.motivo }} · {{ actual.caida.obs }}. La Auxiliar administrativa la confirma.</div>
          <div v-if="actual.situacion === 'caido'" class="note bad"><b>Negocio caído confirmado:</b> {{ actual.caida?.motivo }} · {{ actual.caida?.obs }}. No genera comisión.</div>
          <div v-if="actual.situacion === 'cerrado'" class="note ok"><b>Negocio cerrado · firma confirmada el {{ fd(actual.firma_fecha) }}.</b> Cuenta en tus resultados del mes; la comisión se paga el 5 del mes siguiente.</div>

          <div v-if="actual.abierto" class="card col10">
            <div class="lbl">Avance del negocio</div>
            <div class="g2">
              <button type="button" class="opt" :class="{ on: isOpen(actual, 'etapa') }" @click="toggle(actual, 'etapa')">Pasar etapa</button>
              <button v-if="!actual.caida?.reportada_at" type="button" class="opt red-o" :class="{ on: isOpen(actual, 'caida') }" @click="toggle(actual, 'caida')">Negocio caído</button>
            </div>
            <div v-if="isOpen(actual, 'etapa')" class="col10">
              <div class="fld">
                <label for="m-et">Nueva etapa <span class="req">*</span></label>
                <select id="m-et" v-model="F.etapa" class="in">
                  <option v-if="siguiente(actual)" :value="siguiente(actual)">{{ siguiente(actual) }}</option>
                  <option :value="actual.etapa">Sigue en «{{ actual.etapa }}» · registrar nueva oferta</option>
                </select>
              </div>
              <div v-if="F.etapa === 'Escrituración' && actual.etapa !== 'Escrituración'" class="sub col10">
                <b class="small">Pasa de promesa de compraventa a escrituración: programa la cita en notaría</b>
                <div class="g2">
                  <div class="fld"><label for="m-nf">Fecha de la cita <span class="req">*</span></label><input id="m-nf" v-model="F.nfecha" class="in" type="date" :min="hoy"></div>
                  <div class="fld"><label for="m-nh">Hora <span class="req">*</span></label><input id="m-nh" v-model="F.nhora" class="in" type="time" step="900"></div>
                </div>
                <div class="fld"><label for="m-nn">Notaría <span class="req">*</span></label><input id="m-nn" v-model="F.notaria" class="in" placeholder="Ej.: Notaría 2 de Envigado"></div>
                <div class="mut tiny">Te llega el recordatorio de la cita en notaría en la campana. Con cuánta anticipación: PENDIENTE DE CONFIGURACIÓN (hoy, 2 días antes).</div>
              </div>
              <div class="fld"><label for="m-of">Valor ofrecido o condición negociada</label><input id="m-of" v-model="F.oferta" class="in" maxlength="250" placeholder="Ej.: ofrece $410.000.000 · entrega en 60 días"></div>
              <div class="fld"><label for="m-ob">Observación <span class="req">*</span></label><textarea id="m-ob" v-model="F.obs" class="in ta" maxlength="300" placeholder="Qué pasó" /></div>
              <button type="button" class="btn bp" :disabled="busy" @click="pasarEtapa(actual)">Guardar avance</button>
            </div>
            <div v-if="isOpen(actual, 'caida')" class="col10">
              <div class="fld">
                <label for="m-cm">Motivo <span class="req">*</span></label>
                <select id="m-cm" v-model="F.motivo" class="in"><option value="" disabled>Elige un motivo…</option><option v-for="m in motivosCaida(actual)" :key="m">{{ m }}</option></select>
              </div>
              <div class="fld"><label for="m-co">Observación <span class="req">*</span></label><textarea id="m-co" v-model="F.obs" class="in ta" maxlength="300" placeholder="Qué pasó" /></div>
              <div class="mut tiny">Se envía a la Auxiliar administrativa, que confirma la caída. Al confirmarla, el negocio sale de «En proceso» y no genera comisión.</div>
              <button type="button" class="btn br" :disabled="busy" @click="caida(actual)">Enviar a la Auxiliar</button>
            </div>
          </div>

          <div v-if="actual.notaria_at" class="card col10 focus">
            <div class="sb"><span class="lbl">Escrituración · cita en notaría</span><span class="chip ok">Programada</span></div>
            <div class="kv k110">
              <span class="mut">Notaría</span><b>{{ actual.notaria }}</b>
              <span class="mut">Fecha y hora</span><b>{{ fmtCuando(actual.notaria_at) }}</b>
              <span class="mut">Recordatorio</span><b>En la campana antes de la cita</b>
            </div>
          </div>

          <div class="card hcard">
            <div class="lbl pt10">Historial del negocio</div>
            <div v-for="(h, i) in hist[actual.id] ?? []" :key="i" class="tl">
              <span class="tm">{{ fmtCuando(h.at) }}</span>
              <div><b class="small">{{ h.accion }}</b><div class="mut tiny">{{ [h.por, h.detalle].filter(Boolean).join(' · ') }}</div></div>
            </div>
            <div v-if="!hist[actual.id]?.length" class="mut tiny pb10">Sin movimientos todavía.</div>
          </div>

          <button v-if="actual.abierto && !actual.solicitud && !actual.caida?.reportada_at" type="button" class="btn bp" :disabled="busy" @click="sol = actual">Solicitar cierre</button>
        </div>
      </div>
    </div>
    <ConfirmDialog v-if="sol" title="¿El cliente ya firmó?" confirm-label="Sí, confirmar" :busy="busy" @confirm="solicitar" @cancel="sol = null">
      {{ sol.code }} · {{ sol.inmueble }}. Se envía a la Auxiliar administrativa, que confirma la firma{{ sol.paso_promesa ? ' de la promesa' : '' }} y da «negocio cerrado». Solo entonces cuenta en tu rendimiento.
    </ConfirmDialog>
  </template>

  <!-- ================= X02 · Auxiliar, Gerencia, Coordinación ================= -->
  <template v-else-if="T">
    <PageBar
      title="Negocios"
      subtitle="Arriendos y ventas · aseguradora de cada arriendo, ubicación de los documentos y ganancia de cada negocio · la Auxiliar administrativa confirma la firma y da «negocio cerrado» · las pólizas tienen su propia sección («Pólizas»)"
      :back="home"
    >
      <div class="tabs">
        <button v-for="[k, t] in tabs" :key="k" type="button" class="tab" :class="{ on: tab === k && !(kpi && kpi !== 'tot' && kpi !== 'gan') }" @click="pickTab(k)">{{ t }}</button>
      </div>
    </PageBar>

    <div class="cnt">
      <!-- Indicadores (G-091) -->
      <div class="card col12 ind">
        <div class="sb fw gp10">
          <span class="lbl">Indicadores de negocios · {{ rango }}</span>
          <div class="row fw gp8">
            <label class="row gp6 flt">Desde<input v-model="f.desde" class="in dt" type="date" aria-label="Negocios desde"></label>
            <label class="row gp6 flt">Hasta<input v-model="f.hasta" class="in dt" type="date" aria-label="Negocios hasta"></label>
            <label class="row gp6 flt">Tipo
              <select v-model="f.tipo" class="sel" aria-label="Tipo de negocio"><option value="">Todos</option><option value="arriendo">Arriendos</option><option value="venta">Ventas</option></select>
            </label>
          </div>
        </div>
        <div v-if="fErr" class="note bad"><b>La fecha «Desde» no puede ser posterior a «Hasta».</b></div>
        <div class="g6" :class="{ g5: !dinero }">
          <button v-for="k in kpis" :key="k.k" type="button" class="kb" :class="{ on: kpi === k.k }" @click="kpi = kpi === k.k ? '' : k.k; msg = null">
            <span class="lbl">{{ k.t }}</span>
            <span class="kn num k30" :class="k.cls">{{ k.v }}</span>
            <span class="mut t115">{{ k.d }}</span>
          </button>
        </div>
        <div class="g2b" :class="{ one: !dinero }">
          <div>
            <div class="lbl mb6">Por tipo de negocio</div>
            <div v-for="b in T.por_tipo ?? []" :key="b.tipo" class="bar3">
              <b>{{ b.t }}</b>
              <div class="track"><div class="fill" :class="b.tipo" :style="{ width: `${Math.round((b.n / maxTipo) * 100)}%` }" /></div>
              <span class="num">{{ b.n }}{{ b.ganancia != null ? ` · ganancia ${mf(b.ganancia)}` : '' }}</span>
            </div>
          </div>
          <div v-if="dinero">
            <div class="sb mb6"><span class="lbl">Ganancia de cada negocio</span><span class="mut t115">de mayor a menor · después de comisiones, póliza, IVA y referidos</span></div>
            <div class="glist">
              <div v-for="g in T.ganancias ?? []" :key="g.id" class="grow">
                <b>{{ g.code }}</b><span class="mut">{{ g.tipo }}</span>
                <span class="chip js" :class="CAT[g.categoria][1]">{{ CAT[g.categoria][0] }}{{ g.categoria === 'neg' || g.categoria === 'pc' ? ' · proyectada' : '' }}</span>
                <b class="num ra" :class="{ red: g.neta < 0 }">{{ g.con_valor ? mf(g.neta) : 'Sin valor' }}</b>
              </div>
              <div v-if="!T.ganancias?.length" class="note">No hay negocios con estos filtros.</div>
            </div>
          </div>
        </div>
        <div class="mut t115">
          «En negociación» = todavía sin ninguna firma (oferta, estudio de la póliza). «Por cerrar» = con firma pendiente de confirmar o promesa firmada. La fecha es la del cierre en los cerrados y la
          de inicio (lead ganado) en los demás. Toca un indicador para ver esos negocios abajo.<template v-if="!dinero"> Coordinación ve los negocios sin cifras de dinero.</template>
        </div>
      </div>

      <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.t }}</b></div>

      <div v-for="n in rows" :key="n.id" class="card col10" :class="cardCls(n)">
        <div class="sb gp8">
          <div>
            <b class="t16">{{ n.code }} · {{ n.tipo }}</b>
            <div class="mut small">{{ n.inmueble }} · {{ n.cliente }} · {{ valorTxt(n) }} · asesor {{ n.asesor?.full_name ?? 'sin asignar' }}</div>
          </div>
          <span class="chip big" :class="n.estado_cls">{{ n.estado_txt }}</span>
        </div>

        <div class="g3">
          <div class="box"><div class="lbl">Etapa</div><b class="small">{{ n.etapa }}</b></div>
          <div class="box"><div class="lbl">Solicitud de cierre</div><b class="small">{{ solTxt(n) }}</b></div>
          <template v-if="n.negocio === 'venta'">
            <div class="box"><div class="lbl">Firma de la promesa</div><span class="chip" :class="firma1(n)[1]">{{ firma1(n)[0] }}</span></div>
            <div class="box"><div class="lbl">Firma de la escritura</div><span class="chip" :class="firma2(n)[1]">{{ firma2(n)[0] }}</span></div>
            <div v-if="dinero" class="box"><div class="lbl">Dinero recibido del negocio</div><b class="small">{{ n.recibido ? fmtCOP(n.recibido) : 'Aún no se ha recibido' }}</b></div>
            <div class="box"><div class="lbl">Aseguradora</div><b class="small">No aplica · venta</b></div>
          </template>
          <template v-else>
            <div class="box"><div class="lbl">Póliza</div><span class="chip" :class="n.poliza?.estado_cls ?? 'gray'">{{ n.poliza?.estado_txt ?? 'Sin registrar' }}</span></div>
            <div class="box"><div class="lbl">Tipo de póliza</div><b class="small">{{ n.poliza?.tipo ?? '—' }}</b></div>
            <div class="box"><div class="lbl">Aseguradora</div><b class="small">{{ n.poliza?.aseguradora ?? '—' }}</b></div>
            <div class="box"><div class="lbl">N.º de radicado</div><b class="small">{{ n.poliza?.radicado ?? '—' }}</b></div>
          </template>
        </div>

        <!-- Documentos (G-087) -->
        <div class="docs">
          <div class="grow1">
            <div class="lbl">Ubicación de documentos de la negociación</div>
            <b class="small">{{ n.docs_ubicacion ?? 'Sin registrar · indica dónde quedan los documentos' }}</b>
            <div class="mut tiny">{{ n.contrato_adjunto ? '✓ Contrato adjunto' : 'Contrato sin adjuntar · no es obligatorio' }}</div>
          </div>
          <div v-if="datos && n.situacion !== 'caido'" class="row fw gp8">
            <button type="button" class="btn bs h36" @click="toggle(n, 'docs')">{{ isOpen(n, 'docs') ? 'Cerrar' : n.docs_ubicacion ? 'Cambiar ubicación' : 'Registrar ubicación' }}</button>
            <button type="button" class="btn bs h36" :disabled="busy" @click="togContrato(n)">{{ n.contrato_adjunto ? 'Quitar contrato' : 'Subir contrato (opcional)' }}</button>
          </div>
        </div>
        <div v-if="isOpen(n, 'docs')" class="row fw gp8 end">
          <div class="fld grow1 w280"><label :for="`d-${n.id}`">¿Dónde quedan los documentos? <span class="req">*</span></label><input :id="`d-${n.id}`" v-model="F.docs" class="in" maxlength="300" placeholder="Ej.: Carpeta física A-12 · archivador de la oficina principal · o enlace de Drive"></div>
          <button type="button" class="btn bp" :disabled="busy" @click="guardarDocs(n)">Guardar ubicación</button>
        </div>

        <!-- Ganancia (G-087) -->
        <div v-if="dinero && n.ganancia" class="gbox" :class="{ loss: n.ganancia.perdida }">
          <div class="sb fw gp8">
            <div>
              <div class="lbl">{{ gLbl(n) }}</div>
              <b class="t16" :class="n.ganancia.neta < 0 ? 'red' : 'green'">{{ n.situacion === 'caido' ? '$0' : n.ganancia.con_valor ? fmtCOP(n.ganancia.neta) : '—' }}</b>
              <span class="mut tiny gsub">{{ gSub(n) }}</span>
            </div>
            <button type="button" class="fch" @click="gOn[n.id] = !gOn[n.id]">{{ gOn[n.id] ? 'Ocultar detalle' : 'Ver detalle' }}</button>
          </div>
          <div v-if="n.ganancia.perdida" class="note bad"><b>⚠ Este negocio deja pérdida: lo que se paga supera lo que cobró la empresa. Revisa las comisiones antes de aprobarlas.</b></div>
          <div v-if="gOn[n.id]" class="col8">
            <div v-if="n.negocio !== 'venta'" class="row fw gp14 small">
              <span class="row gp6"><b>Uso del inmueble:</b>
                <button type="button" class="fch" :class="{ on: !n.uso_comercial }" :disabled="!datos" @click="setUso(n, 'uso_comercial', false)">Vivienda</button>
                <button type="button" class="fch" :class="{ on: n.uso_comercial }" :disabled="!datos" @click="setUso(n, 'uso_comercial', true)">Comercial</button>
              </span>
              <span class="row gp6"><b>Arrendatario:</b>
                <button type="button" class="fch" :class="{ on: !n.arrendatario_juridica }" :disabled="!datos" @click="setUso(n, 'arrendatario_juridica', false)">Persona natural</button>
                <button type="button" class="fch" :class="{ on: n.arrendatario_juridica }" :disabled="!datos" @click="setUso(n, 'arrendatario_juridica', true)">Persona jurídica</button>
              </span>
            </div>
            <div v-if="datos && n.situacion !== 'caido'" class="row fw gp8 end">
              <template v-if="isOpen(n, 'valor')">
                <div class="fld w200"><label :for="`v-${n.id}`">{{ n.negocio === 'venta' ? 'Valor de la venta' : 'Canon mensual' }}</label><input :id="`v-${n.id}`" v-model="F.canon" class="in" inputmode="numeric" placeholder="$"></div>
                <div class="fld w240">
                  <label :for="`i-${n.id}`">Inmueble</label>
                  <select :id="`i-${n.id}`" v-model="F.inmueble" class="in"><option value="">Sin inmueble registrado</option><option v-for="i in inmueblesDe(n)" :key="i.id" :value="i.id">{{ i.t }}</option></select>
                </div>
                <div v-if="n.negocio === 'venta'" class="fld w200"><label :for="`p-${n.id}`">% de comisión de esta venta (+ IVA)</label><input :id="`p-${n.id}`" v-model="F.pct" class="in" inputmode="decimal" :placeholder="`Por defecto ${pct(T.tarifas?.venta_pct)}`"></div>
                <div v-else class="fld w200"><label :for="`r-${n.id}`">Referido (si lo hubo)</label><input :id="`r-${n.id}`" v-model="F.referido" class="in" maxlength="200" placeholder="Nombre"></div>
                <button type="button" class="btn bp" :disabled="busy" @click="guardarValor(n)">Guardar</button>
                <button type="button" class="btn bs" @click="toggle(n, 'valor')">Cancelar</button>
              </template>
              <button v-else type="button" class="btn bs h36" @click="toggle(n, 'valor')">{{ n.negocio === 'venta' ? 'Editar valor, inmueble y % de la venta' : 'Editar canon, inmueble y referido' }}</button>
              <span v-if="n.negocio === 'venta' && !isOpen(n, 'valor')" class="mut tiny">Comisión de esta venta: {{ pct(n.pct_venta) }} + IVA{{ n.pct_venta_propio ? '' : ' (por defecto)' }} · la ponen Gerencia o la Auxiliar administrativa</span>
            </div>
            <div class="lines">
              <div v-for="(l, i) in n.ganancia.lineas" :key="i" class="line" :class="{ strong: l.fuerte, total: l.total, red: l.total && l.v < 0 }">
                <span>{{ l.t }}<br><span class="mut t115 fw4">{{ l.d }}</span></span>
                <span class="num ra">{{ l.v < 0 ? `− ${fmtCOP(-l.v)}` : fmtCOP(l.v) }}</span>
              </div>
            </div>
            <div class="lbl">Lo que no es ganancia de la empresa</div>
            <div v-for="(x, i) in n.ganancia.no_ganancia" :key="i" class="sb nrow small">
              <span>{{ x.t }}<br><span class="mut t115">{{ x.d }}</span></span><b class="num">{{ x.v }}</b>
            </div>
            <div class="mut t115">
              {{ tarifasTxt }}
              <template v-if="n.ganancia_efectiva"> Ganancia efectiva registrada: <b>{{ fmtCOP(n.ganancia_efectiva) }}</b>.</template>
              Comisiones y referidos: DATOS DE EJEMPLO.
            </div>
          </div>
        </div>

        <!-- Activación de la póliza (cerrado · arriendo) -->
        <div v-if="n.situacion === 'cerrado' && n.negocio !== 'venta'" class="pbox" :class="n.poliza?.estado === 'activa' ? 'ok' : n.poliza ? 'warn' : ''">
          <div class="grow1">
            <div class="lbl">Activación de la póliza · solo arriendos · <NuxtLink to="/polizas?tab=ale" class="lnk">ver en «Pólizas» ›</NuxtLink></div>
            <b class="small">
              {{ n.poliza?.estado === 'activa' ? `✓ Póliza activada · ${n.poliza.aseguradora}${n.poliza.numero ? ` · ${n.poliza.numero}` : ''} · ${fd(n.poliza.activada_fecha)}` : n.poliza ? `Póliza ${n.poliza.estado_txt.toLowerCase()} · por activar con ${n.poliza.aseguradora}` : 'Sin póliza registrada' }}
            </b>
            <div class="mut tiny">Cada aseguradora tiene su plazo máximo para activar la póliza desde la firma del contrato; las alertas están en «Pólizas».</div>
          </div>
        </div>

        <!-- Acciones de la Auxiliar -->
        <div v-if="gestiona && n.abierto" class="row fw gp8">
          <NuxtLink v-if="n.negocio !== 'venta'" class="opt" to="/polizas?tab=tra">Actualizar póliza</NuxtLink>
          <button v-else type="button" class="opt" :class="{ on: isOpen(n, 'din') }" @click="toggle(n, 'din')">Registrar dinero recibido</button>
          <template v-if="(n.situacion === 'por_confirmar' || !n.asesor) && !n.caida?.reportada_at">
            <button type="button" class="btn bp" @click="toggle(n, 'cer')">{{ cerTxt(n) }}</button>
            <button v-if="n.solicitud" type="button" class="btn br" @click="toggle(n, 'dev')">Devolver al asesor</button>
          </template>
          <button type="button" class="btn" :class="isOpen(n, 'caida') ? 'br' : 'bs'" @click="toggle(n, 'caida')">Negocio caído</button>
        </div>
        <div v-if="n.abierto && n.caida?.reportada_at" class="note bad row fw gp8">
          <span class="grow1"><b>{{ n.caida.por ?? 'El asesor' }} reportó que el negocio se cayó:</b> {{ n.caida.motivo }} · {{ n.caida.obs }}{{ n.caida.reportada_at ? ` · ${fmtCuando(n.caida.reportada_at)}` : '' }}. {{ gestiona ? 'Confírmalo con «Negocio caído» o sigue con el negocio.' : 'La Auxiliar administrativa lo confirma.' }}</span>
          <button v-if="gestiona" type="button" class="btn bs h36" :disabled="busy" @click="descartar(n)">Seguir con el negocio</button>
        </div>

        <div v-if="isOpen(n, 'caida')" class="form">
          <div class="g3">
            <div class="fld">
              <label :for="`cm-${n.id}`">Motivo <span class="req">*</span></label>
              <select :id="`cm-${n.id}`" v-model="F.motivo" class="in"><option value="" disabled>Elige un motivo…</option><option v-for="m in motivosCaida(n)" :key="m">{{ m }}</option></select>
            </div>
            <div class="fld span2"><label :for="`co-${n.id}`">Observación <span class="req">*</span></label><input :id="`co-${n.id}`" v-model="F.obs" class="in" maxlength="300" placeholder="Qué pasó"></div>
          </div>
          <div class="mut tiny">Al confirmarlo, el negocio sale de «En proceso» y de la proyección, no genera comisión (se anulan las que no se han pagado) y el asesor y Gerencia reciben el aviso. Queda en el registro de cambios.</div>
          <div><button type="button" class="btn br" :disabled="busy" @click="caida(n)">Confirmar negocio caído</button></div>
        </div>
        <div v-if="isOpen(n, 'din')" class="form">
          <div class="g4">
            <div class="fld"><label :for="`dv-${n.id}`">Valor recibido <span class="req">*</span></label><input :id="`dv-${n.id}`" v-model="F.valor" class="in" inputmode="numeric" placeholder="$"></div>
            <div class="fld"><label :for="`df-${n.id}`">Fecha <span class="req">*</span></label><input :id="`df-${n.id}`" v-model="F.fecha" class="in" type="date" :max="hoy"></div>
            <div class="fld">
              <label :for="`dm-${n.id}`">Momento</label>
              <select :id="`dm-${n.id}`" v-model="F.momento" class="in"><option v-for="(t, k) in T.momentos" :key="k" :value="k">{{ t }}</option></select>
            </div>
            <div class="fld"><span class="flbl">Soporte</span><label class="row gp6 chk"><input v-model="F.soporte" type="checkbox"> Soporte adjunto</label></div>
          </div>
          <div v-if="n.abonos?.length" class="mut tiny">Registrado: {{ n.abonos.map((a) => `${fmtCOP(a.valor)} · ${fd(a.fecha)} (${a.momento_txt.toLowerCase()})`).join(' · ') }}</div>
          <div class="mut tiny">Comisión parcial por cada pago recibido: PENDIENTE DE CONFIGURACIÓN (la comisión se genera al dar «negocio cerrado»).</div>
          <div><button type="button" class="btn bp" :disabled="busy" @click="abono(n)">Guardar dinero recibido</button></div>
        </div>
        <div v-if="isOpen(n, 'cer')" class="form">
          <div class="g3">
            <div class="fld"><label :for="`cf-${n.id}`">{{ firmaLbl(n) }} <span class="req">*</span></label><input :id="`cf-${n.id}`" v-model="F.fecha" class="in" type="date" :max="hoy"></div>
            <div class="fld"><span class="flbl">Contrato o documento firmado (opcional)</span><label class="row gp6 chk"><input v-model="F.contrato" type="checkbox"> Adjunto</label></div>
            <div class="fld"><label :for="`co2-${n.id}`">Observación</label><input :id="`co2-${n.id}`" v-model="F.obs" class="in" maxlength="300" placeholder="Opcional"></div>
          </div>
          <div class="mut tiny">Subir el contrato no es obligatorio. Registra dónde quedan los documentos en «Ubicación de documentos de la negociación».</div>
          <div><button type="button" class="btn bp" :disabled="busy || !F.fecha" @click="conf = n">{{ n.paso_promesa ? 'Confirmar firma de la promesa' : 'Dar negocio cerrado' }}</button></div>
        </div>
        <div v-if="isOpen(n, 'dev')" class="form">
          <div class="fld w360">
            <label :for="`dm2-${n.id}`">Motivo <span class="req">*</span></label>
            <select :id="`dm2-${n.id}`" v-model="F.motivo" class="in"><option v-for="m in T.motivos_devolver" :key="m">{{ m }}</option></select>
          </div>
          <div><button type="button" class="btn br" :disabled="busy" @click="devolver(n)">Devolver al asesor</button></div>
        </div>

        <div v-if="n.situacion === 'cerrado'" class="note">Negocio cerrado · firma confirmada el {{ fd(n.firma_fecha) }}{{ n.promesa_fecha && n.negocio === 'venta' ? ` · promesa el ${fd(n.promesa_fecha)}` : '' }}. Queda en el registro de cambios.</div>
        <div v-if="n.situacion === 'caido'" class="note bad">Negocio caído confirmado{{ n.caida?.confirmada_at ? ` el ${fmtCuando(n.caida.confirmada_at)}` : '' }}{{ n.caida?.motivo ? ` · ${n.caida.motivo}` : ' · el lead dejó de estar «Ganado»' }}{{ n.caida?.obs ? ` · ${n.caida.obs}` : '' }}. No genera comisión.</div>

        <div>
          <button type="button" class="fch" @click="toggleHist(n)">{{ verHist[n.id] ? 'Ocultar historial' : 'Ver historial' }}</button>
        </div>
        <div v-if="verHist[n.id]" class="hist">
          <div v-for="(h, i) in hist[n.id] ?? []" :key="i" class="tl">
            <span class="tm">{{ fmtCuando(h.at) }}</span>
            <div><b class="small">{{ h.accion }}</b><div class="mut tiny">{{ [h.por, h.detalle].filter(Boolean).join(' · ') }}</div></div>
          </div>
        </div>
      </div>
      <div v-if="!rows.length" class="note">No hay negocios en esta lista.</div>
      <div class="note">
        En arriendos la Auxiliar confirma una firma (el contrato). En ventas confirma dos: la promesa de compraventa (con ella la venta cuenta en la meta del mes) y la escritura (con ella da
        «negocio cerrado»). Al dar «negocio cerrado» se registra la ganancia y se generan las comisiones; se pagan el 5 del mes siguiente. Cada cambio queda en el registro de cambios.
      </div>
    </div>

    <ConfirmDialog v-if="conf" :title="conf.paso_promesa ? `¿Confirmas la firma de la promesa de ${conf.code}?` : `¿Das ${conf.code} como negocio cerrado?`" :confirm-label="conf.paso_promesa ? 'Sí, confirmar la promesa' : 'Sí, negocio cerrado'" :busy="busy" @confirm="confirmar" @cancel="conf = null">
      <template v-if="conf.paso_promesa">Firma del {{ fd(F.fecha) }}. La venta cuenta en la meta del mes del asesor; falta la escritura.</template>
      <template v-else>Firma del {{ fd(F.fecha) }}. Cuenta en el rendimiento del asesor, se registra la ganancia y se generan las comisiones para visto bueno.</template>
    </ConfirmDialog>
  </template>
</template>

<style scoped>
.fw {
  flex-wrap: wrap;
}
.gp6 {
  gap: 6px;
  align-items: center;
}
.gp8 {
  gap: 8px;
}
.gp10 {
  gap: 10px;
}
.gp14 {
  gap: 14px;
}
.end {
  align-items: flex-end;
}
.col8,
.col10,
.col12 {
  display: flex;
  flex-direction: column;
}
.col8 {
  gap: 8px;
}
.col10 {
  gap: 10px;
}
.col12 {
  gap: 12px;
}
.grow1 {
  flex: 1;
  min-width: 0;
}
.flt {
  font-size: 13px;
  font-weight: 700;
}
.dt {
  min-height: 38px;
  width: auto;
}
.h36 {
  min-height: 36px;
}
.tiny {
  font-size: 12px;
}
.small {
  font-size: 13px;
}
.t10 {
  font-size: 10px;
}
.t115 {
  font-size: 11.5px;
}
.t16 {
  font-size: 16px;
}
.t17 {
  font-size: 17px;
}
.k30 {
  font-size: 30px;
}
.fw4 {
  font-weight: 400;
}
.mb6 {
  margin-bottom: 6px;
}
.pt10 {
  padding-top: 10px;
}
.pb10 {
  padding-bottom: 10px;
}
.w200 {
  width: 200px;
}
.w240 {
  width: 240px;
}
.w280 {
  min-width: 280px;
}
.w360 {
  max-width: 360px;
}
.ra {
  text-align: right;
}
.js {
  justify-self: start;
}
.red {
  color: var(--cdc-bad);
}
.green {
  color: var(--cdc-ok);
}
.lnk {
  color: var(--cdc-green);
}
.gsub {
  margin-left: 6px;
}
.chip.big {
  font-size: 12.5px;
  padding: 5px 12px;
}

/* Indicadores */
.ind {
  border: 2px solid var(--cdc-green);
}
.g6 {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}
.g6.g5 {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}
.kb {
  all: unset;
  cursor: pointer;
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--cdc-bg);
  border: 2px solid transparent;
}
.kb.on {
  background: var(--cdc-info-bg);
  border-color: var(--cdc-green);
}
.kb:focus-visible {
  outline: 2px solid var(--cdc-green);
}
.g2b {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr);
  gap: 18px;
}
.g2b.one {
  grid-template-columns: minmax(0, 1fr);
}
.bar3 {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr) 190px;
  gap: 10px;
  align-items: center;
  font-size: 13px;
  padding: 5px 0;
}
.track {
  background: var(--cdc-gray-bg);
  border-radius: 6px;
  height: 14px;
}
.fill {
  background: var(--cdc-green);
  border-radius: 6px;
  height: 14px;
}
.fill.venta {
  background: #6b4fa0;
}
.glist {
  max-height: 260px;
  overflow-y: auto;
}
.grow {
  display: grid;
  grid-template-columns: 86px 70px minmax(0, 1fr) 110px;
  gap: 8px;
  align-items: center;
  font-size: 12.5px;
  padding: 5px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
}

/* Deal cards */
.b-warn {
  border: 2px solid var(--sem-amarillo);
}
.b-bad {
  border: 2px solid var(--cdc-bad);
}
.box {
  background: var(--cdc-bg);
  border-radius: 10px;
  padding: 10px;
}
.docs {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  border: 1px solid var(--cdc-border);
  border-radius: 10px;
  padding: 10px 12px;
}
.docs .grow1 {
  min-width: 240px;
}
.gbox {
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--cdc-bg);
}
.gbox.loss {
  background: #fff5f3;
  border: 1.5px solid var(--cdc-bad);
}
.lines {
  background: #fff;
  border-radius: 10px;
  padding: 4px 12px;
}
.line {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px;
  gap: 10px;
  padding: 7px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  font-size: 13px;
  align-items: center;
}
.line:last-child {
  border-bottom: 0;
}
.line.strong {
  font-weight: 700;
}
.line.total {
  font-weight: 800;
  color: var(--cdc-ok);
}
.line.total.red {
  color: var(--cdc-bad);
}
.nrow {
  padding: 4px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  gap: 10px;
}
.pbox {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  border-radius: 10px;
  padding: 10px 12px;
  background: var(--cdc-bg);
}
.pbox.ok {
  background: var(--cdc-ok-bg);
}
.pbox.warn {
  background: var(--cdc-warn-bg);
}
.form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-top: 1px solid var(--cdc-border-soft);
  padding-top: 10px;
}
.span2 {
  grid-column: span 2;
}
.flbl {
  font-size: 13px;
  font-weight: 700;
}
.chk {
  min-height: 44px;
  font-size: 13px;
}
.hist {
  border-top: 1px solid var(--cdc-border-soft);
}
.tl {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.tl:last-child {
  border-bottom: 0;
}
.tm {
  font-size: 12px;
  color: var(--cdc-muted);
  font-weight: 700;
}
a.opt {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
}

/* Asesor (M16) */
.mlay {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.mlist {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.mit {
  all: unset;
  cursor: pointer;
  background: var(--cdc-card);
  border: 1px solid var(--cdc-border);
  border-radius: var(--radius-card);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.mit.sel {
  border: 2px solid var(--cdc-green);
}
.mit:focus-visible {
  outline: 2px solid var(--cdc-green);
}
.kv {
  font-size: 13px;
  display: grid;
  grid-template-columns: 130px minmax(0, 1fr);
  gap: 5px 8px;
}
.kv.k110 {
  grid-template-columns: 110px minmax(0, 1fr);
}
.sub {
  background: var(--cdc-bg);
  border-radius: 12px;
  padding: 12px;
}
.hcard {
  padding: 4px 14px;
}
.red-o {
  color: var(--cdc-bad);
  border-color: #e8b4ac;
}

@media (max-width: 1100px) {
  .g6,
  .g6.g5 {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .g2b {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 760px) {
  .g6,
  .g6.g5 {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .mlay {
    grid-template-columns: minmax(0, 1fr);
  }
  .bar3 {
    grid-template-columns: 70px minmax(0, 1fr) 110px;
  }
  .grow {
    grid-template-columns: 76px minmax(0, 1fr) 96px;
  }
  .grow .mut {
    display: none;
  }
  .span2 {
    grid-column: auto;
  }
  .tl {
    grid-template-columns: 1fr;
    gap: 2px;
  }
}
</style>
