<script setup lang="ts">
import type { PolAseguradoras, PolCard, PolComparar, PolFila, PolOpciones, PolTablero } from '~/types/polizas'

/**
 * X11 «Pólizas» (Auxiliar administrativa y Gerencia; G-087): only rentals. Indicadores por
 * aseguradora, contratos activos, the policies in progress (study → approved → signed), alerts to
 * activate in time and the insurers. Gerencia also has «Comparar pólizas» (G-072).
 */
definePageMeta({ cargos: ['gerencia', 'auxiliar_administrativa'] })
useHead({ title: 'Pólizas · Casa Dolce Casa' })

const api = usePolizas()
const auth = useAuth()
const home = computed(() => (auth.user.value?.cargo === 'gerencia' ? '/coordinacion' : '/'))
const route = useRoute()
const router = useRouter()
const hoy = localDate(0)
const inicioAno = `${hoy.slice(0, 4)}-01-01`

type Tab = 'ind' | 'con' | 'tra' | 'ale' | 'ase' | 'cmp'
const tab = ref<Tab>((['ind', 'con', 'tra', 'ale', 'ase', 'cmp'].includes(String(route.query.tab)) ? route.query.tab : 'ind') as Tab)
watch(tab, (t) => router.replace({ query: t === 'ind' ? {} : { tab: t } }))

// ---- board
const f = reactive({ desde: inicioAno, hasta: hoy, ase: '' })
const fErr = computed(() => !f.desde || !f.hasta || f.desde > f.hasta)
const q = computed(() => (fErr.value ? { desde: inicioAno, hasta: hoy } : { desde: f.desde, hasta: f.hasta, ...(f.ase ? { aseguradora_id: f.ase } : {}) }))
const { data, refresh } = await useAsyncData('polizas', () => api.tablero(q.value), { watch: [q] })
const T = computed(() => data.value as PolTablero)
const { data: asData, refresh: refreshAs } = await useAsyncData('polizas-ase', () => api.aseguradoras())
const AS = computed(() => asData.value as PolAseguradoras)
const COB = computed(() => AS.value?.coberturas ?? {})

const tabs = computed(() => {
  const t: [Tab, string][] = [
    ['ind', 'Indicadores'],
    ['con', 'Contratos activos'],
    ['tra', `En trámite (${T.value?.tramite.length ?? 0})`],
    ['ale', `Alertas de activación (${T.value?.alertas.length ?? 0})`],
    ['ase', 'Aseguradoras'],
  ]
  if (T.value?.gerencia) t.push(['cmp', 'Comparar pólizas'])
  return t
})

const msg = ref<{ t: string; ok: boolean } | null>(null)
const say = (t: string, ok = true) => (msg.value = { t, ok })
async function run(fn: () => Promise<unknown>, t: string | (() => string)) {
  try {
    await fn()
    say(typeof t === 'string' ? t : t())
    await Promise.all([refresh(), refreshAs()])
    return true
  } catch (e) {
    say(apiErrorMessage(e), false)
    return false
  }
}
const pct = (v: number | null | undefined) => (v == null ? '—' : `${v.toFixed(1).replace('.', ',')} %`)
const fd = (iso: string | null | undefined) => (iso ? fmtFecha(iso) : '—')
const aleTop = computed(() => {
  const k = T.value?.kpis
  if (!k || tab.value === 'ale' || !(k.vencidas + k.por_vencer)) return ''
  return [k.vencidas ? `${k.vencidas} ${k.vencidas === 1 ? 'póliza vencida' : 'pólizas vencidas'} sin activar` : '', k.por_vencer ? `${k.por_vencer} por vencer` : ''].filter(Boolean).join(' · ')
})
const maxAct = computed(() => Math.max(1, ...(T.value?.por_aseguradora.map((r) => r.activas) ?? [1])))
const tot = computed(() => {
  const r = T.value?.por_aseguradora ?? []
  return { act: r.reduce((s, x) => s + x.activas, 0), costo: r.reduce((s, x) => s + x.costo_mes, 0), nuevas: r.reduce((s, x) => s + x.nuevas, 0) }
})

// ---- register a policy
const opc = ref<PolOpciones | null>(null)
const R = reactive({ on: false, cierre: '', inmueble: '', desc: '', ase: '', tipo: '', canon: '', radicado: '', fecha: hoy, seguro: false, err: '' })
async function abrirRegistro() {
  R.on = !R.on
  if (R.on) opc.value = await api.opciones()
}
const tiposR = computed(() => opc.value?.aseguradoras.find((a) => a.id === R.ase)?.tipos ?? [])
watch(
  () => R.inmueble,
  (id) => {
    const c = opc.value?.inmuebles.find((i) => i.id === id)?.canon
    if (c && !R.canon) R.canon = String(c)
  },
)
async function registrar() {
  R.err = ''
  try {
    const p = await api.crear({
      cierre_id: R.cierre || null,
      inmueble_id: R.inmueble || null,
      descripcion: R.desc || null,
      tipo_id: R.tipo || null,
      canon: R.canon ? Number(R.canon) : null,
      radicado: R.radicado || null,
      estudio_fecha: R.fecha,
      seguro_inmueble: R.seguro,
    })
    Object.assign(R, { on: false, cierre: '', inmueble: '', desc: '', ase: '', tipo: '', canon: '', radicado: '', fecha: hoy, seguro: false })
    say(`${p.negocio ?? p.inmueble}: estudio registrado con ${p.aseguradora}. Queda «En estudio». Quedó en el registro de cambios.`)
    await refresh()
  } catch (e) {
    R.err = apiErrorMessage(e)
  }
}

// ---- actions on a policy in progress
const open = ref<string | null>(null)
const A = reactive({ modo: '' as '' | 'negar' | 'retomar' | 'firma' | 'editar' | 'terminar', motivo: '', fecha: hoy, canon: '', radicado: '', seguro: false })
function abrir(p: PolFila, modo: typeof A.modo) {
  if (open.value === p.id && A.modo === modo) return cerrar()
  open.value = p.id
  Object.assign(A, { modo, motivo: '', fecha: hoy, canon: String(p.canon), radicado: p.radicado ?? '', seguro: p.seguro_inmueble })
}
const cerrar = () => {
  open.value = null
  A.modo = ''
}
const BTN: Record<string, string> = { negar: 'Guardar · negada', retomar: 'Retomar el estudio', firma: 'Guardar firma', editar: 'Guardar cambios', terminar: 'Terminar' }
const nom = (p: PolFila) => p.negocio ?? p.inmueble
async function aprobar(p: PolFila) {
  await run(() => api.decidir(p.id, true), `${nom(p)}: póliza aprobada${p.estudios > 1 ? ' en el segundo estudio · cuenta como póliza recuperada' : ''}. ${p.asesor ? `Se avisó a ${p.asesor}. ` : ''}Falta registrar la firma del contrato.`)
  cerrar()
}
async function confirmar(p: PolFila) {
  const fns: Record<string, [() => Promise<unknown>, string]> = {
    negar: [() => api.decidir(p.id, false, A.motivo), `${nom(p)}: póliza negada. Puedes retomar el estudio si cambia el asegurado o el codeudor.`],
    retomar: [() => api.retomar(p.id, A.motivo), `${nom(p)}: estudio retomado. Si se aprueba, cuenta como póliza recuperada.`],
    firma: [() => api.firma(p.id, A.fecha), `${nom(p)}: firma del contrato registrada el ${fd(A.fecha)}. Corre el plazo de ${p.aseguradora} para activar la póliza.`],
    editar: [() => api.editar(p.id, { canon: Number(A.canon), radicado: A.radicado, seguro_inmueble: A.seguro }), `${nom(p)}: cambios guardados.`],
    terminar: [() => api.terminar(p.id, A.fecha), `${nom(p)}: póliza terminada el ${fd(A.fecha)}. Sale de «Contratos activos».`],
  }
  const [fn, t] = fns[A.modo]!
  if (await run(fn, t)) cerrar()
}
const del = reactive({ p: null as PolFila | null, motivo: '' })
async function eliminar() {
  const p = del.p!
  if (await run(() => api.eliminar(p.id, del.motivo), `${nom(p)}: póliza eliminada. Queda registrado quién la eliminó y cuándo.`)) del.p = null
}

// ---- activate (alerts)
const act = reactive({ id: '', fecha: hoy, numero: '', soporte: false, err: '' })
function abrirActivar(p: PolFila) {
  Object.assign(act, { id: act.id === p.id ? '' : p.id, fecha: hoy, numero: '', soporte: false, err: '' })
}
async function activar(p: PolFila) {
  act.err = ''
  if (!act.fecha || !act.numero.trim()) return (act.err = 'Completa la fecha de activación y el número de póliza.')
  if (await run(() => api.activar(p.id, { fecha: act.fecha, numero: act.numero, soporte: act.soporte }), `${nom(p)}: póliza ${act.numero} activada con ${p.aseguradora} el ${fd(act.fecha)}. Pasó a «Contratos activos» y se apagó la alerta. Quedó en el registro de cambios.`)) act.id = ''
}
const aleBox = (st?: string) => (st === 'v' ? 'abox v' : st === 'p' ? 'abox p' : 'abox')
const aleChip = (st?: string) => (st === 'v' ? ['■ Vencida · activar ya', 'bad'] : st === 'p' ? ['Por vencer', 'warn'] : ['En plazo', 'info'])

// ---- insurers
const N = reactive({ on: false, list: false, nombre: '', nit: '', contacto: '', tel: '', tp: '', pct: '', est: '', resp: '', dm: '', av: '', cob: [] as string[], err: '' })
function togCob(k: string) {
  N.cob = N.cob.includes(k) ? N.cob.filter((x) => x !== k) : [...N.cob, k]
}
async function guardarAseguradora() {
  N.err = ''
  try {
    const a = await api.crearAseguradora({
      nombre: N.nombre,
      nit: N.nit || null,
      contacto: N.contacto || null,
      telefono: N.tel || null,
      dias_max: N.dm === '' ? null : Number(N.dm),
      aviso_dias: N.av === '' ? null : Number(N.av),
      poliza: { nombre: N.tp, precio_pct: Number(N.pct.replace(',', '.')), costo_estudio: N.est === '' ? 0 : Number(N.est), dias_respuesta: N.resp === '' ? null : Number(N.resp), coberturas: N.cob },
    })
    say(`${a.nombre} quedó agregada y activa. Ya aparece al registrar pólizas, en las alertas de activación${T.value.gerencia ? ' y en el comparador' : ''}. Quedó en el registro de cambios.`)
    Object.assign(N, { on: false, list: true, nombre: '', nit: '', contacto: '', tel: '', tp: '', pct: '', est: '', resp: '', dm: '', av: '', cob: [] })
    await Promise.all([refresh(), refreshAs()])
  } catch (e) {
    N.err = apiErrorMessage(e)
  }
}
const delAs = ref<string | null>(null)
const tipoN = reactive({ id: '', nombre: '', pct: '', est: '', resp: '', cob: [] as string[], err: '' })
async function guardarTipo() {
  tipoN.err = ''
  try {
    await api.agregarTipo(tipoN.id, { nombre: tipoN.nombre, precio_pct: Number(tipoN.pct.replace(',', '.')), costo_estudio: tipoN.est === '' ? 0 : Number(tipoN.est), dias_respuesta: tipoN.resp === '' ? null : Number(tipoN.resp), coberturas: tipoN.cob })
    say(`Póliza «${tipoN.nombre}» agregada.`)
    Object.assign(tipoN, { id: '', nombre: '', pct: '', est: '', resp: '', cob: [] })
    await refreshAs()
  } catch (e) {
    tipoN.err = apiErrorMessage(e)
  }
}
const asDesc = (a: PolAseguradoras['items'][number]) =>
  [
    `Activar máx. ${a.dias_max} días después de la firma`,
    a.nit ? `NIT ${a.nit}` : '',
    a.contacto ?? '',
    a.telefono ?? '',
    a.tipos.map((t) => `${t.nombre} · ${pct(t.precio_pct)} del canon`).join(' · '),
    `${a.polizas} póliza${a.polizas === 1 ? '' : 's'}`,
    a.ejemplo ? 'datos reales: PENDIENTE DE CONFIGURACIÓN' : `agregada por ${a.agregada}`,
  ]
    .filter(Boolean)
    .join(' · ')
// plazo editor
const pz = reactive<Record<string, { dm: number | string; av: number | string; ok?: boolean }>>({})
watch(
  AS,
  (v) => {
    for (const a of v?.items ?? []) pz[a.id] = { dm: a.dias_max, av: a.aviso_dias }
  },
  { immediate: true },
)
async function guardarPlazo(a: PolAseguradoras['items'][number]) {
  const z = pz[a.id]!
  if (await run(() => api.editarAseguradora(a.id, { dias_max: Number(z.dm), aviso_dias: Number(z.av) }), `${a.nombre}: plazo para activar ${z.dm} días, aviso ${z.av} días antes. Ya aplica en las alertas.`)) pz[a.id]!.ok = true
}

// ---- comparator (Gerencia)
const C = reactive({ desde: inicioAno, hasta: hoy, e: '', t: '', o: 'pre', canon: 1_600_000, sel: [] as string[], ver: '' })
const cErr = computed(() => !C.desde || !C.hasta || C.desde > C.hasta)
const cq = computed(() => (cErr.value ? { desde: inicioAno, hasta: hoy } : { desde: C.desde, hasta: C.hasta }))
const { data: cmpData } = await useAsyncData('polizas-cmp', () => (tab.value === 'cmp' && T.value?.gerencia ? api.comparar(cq.value) : Promise.resolve(null)), { watch: [cq, tab] })
const CM = computed(() => cmpData.value as PolComparar | null)
const ORD: [string, string, (a: PolCard, b: PolCard) => number][] = [
  ['pre', 'Más económica', (a, b) => a.precio_pct - b.precio_pct],
  ['act', 'Más pólizas activas', (a, b) => b.activas - a.activas],
  ['apr', 'Mayor % de aprobación', (a, b) => (b.aprobacion ?? -1) - (a.aprobacion ?? -1)],
  ['res', 'Respuesta más rápida', (a, b) => (a.dias_respuesta ?? 99) - (b.dias_respuesta ?? 99)],
  ['cob', 'Más coberturas', (a, b) => b.coberturas.length - a.coberturas.length],
]
const tiposCmp = computed(() => [...new Set((CM.value?.cards ?? []).map((c) => c.tipo))])
const entsCmp = computed(() => {
  const m = new Map<string, string>()
  for (const c of CM.value?.cards ?? []) m.set(c.aseguradora_id, c.aseguradora)
  return [...m]
})
const cards = computed(() =>
  (CM.value?.cards ?? []).filter((c) => (!C.e || c.aseguradora_id === C.e) && (!C.t || c.tipo === C.t)).sort(ORD.find((o) => o[0] === C.o)![2]),
)
const anual = (c: PolCard) => (C.canon * c.precio_pct * 12) / 100 + c.costo_estudio
const badge = (c: PolCard) => {
  const L = cards.value
  if (c.nueva) return 'Nueva'
  if (c.precio_pct === Math.min(...L.map((x) => x.precio_pct))) return 'Más económica'
  if (c.activas && c.activas === Math.max(...L.map((x) => x.activas))) return 'Más usada'
  if (c.coberturas.length === 5) return 'Más completa'
  return ''
}
const cKpis = computed(() => {
  const L = cards.value
  const neg = L.reduce((s, c) => s + c.negados, 0)
  const est = L.reduce((s, c) => s + c.estudios, 0)
  return [
    ['Pólizas activas', String(L.reduce((s, c) => s + c.activas, 0)), 'contratos vigentes'],
    ['Inmuebles con seguro', String(L.reduce((s, c) => s + c.con_seguro, 0)), 'con las entidades filtradas'],
    ['Canon asegurado al mes', fmtCOP(L.reduce((s, c) => s + c.canon_mes, 0)), 'suma de cánones con póliza'],
    ['Estudios negados', String(neg), `de ${est} estudios en el rango`],
    ['Precio promedio', L.length ? pct(L.reduce((s, c) => s + c.precio_pct, 0) / L.length) : '—', 'del canon, cada mes'],
  ]
})
function togSel(id: string) {
  C.sel = C.sel.includes(id) ? C.sel.filter((x) => x !== id) : [...C.sel, id].slice(-3)
}
const sel = computed(() => (CM.value?.cards ?? []).filter((c) => C.sel.includes(c.id)))
const cmpRows = computed(() => {
  const S = sel.value
  if (S.length < 2) return []
  const row = (t: string, vals: number[], show: (v: number, i: number) => string, low: boolean | null) => {
    const b = low === null ? null : low ? Math.min(...vals) : Math.max(...vals)
    const unico = vals.filter((v) => v === b).length < vals.length
    return { t, c: vals.map((v, i) => ({ v: show(v, i), best: b !== null && v === b && unico })) }
  }
  return [
    row('Precio (del canon)', S.map((c) => c.precio_pct), (v) => pct(v), true),
    row(`Costo al mes · canon ${fmtCOP(C.canon)}`, S.map((c) => (C.canon * c.precio_pct) / 100), (v) => fmtCOP(v), true),
    row('Costo el primer año (con estudio)', S.map(anual), (v) => fmtCOP(v), true),
    row('Costo del estudio', S.map((c) => c.costo_estudio), (v) => (v ? fmtCOP(v) : 'Sin costo'), true),
    row('Respuesta del estudio', S.map((c) => c.dias_respuesta ?? 99), (v) => (v === 99 ? 'Sin dato' : `${v} d hábiles`), true),
    row('% de aprobación', S.map((c) => c.aprobacion ?? -1), (v) => (v < 0 ? 'Sin estudios' : `${v}%`), false),
    row('Coberturas', S.map((c) => c.coberturas.length), (_v, i) => S[i]!.coberturas.map((k) => COB.value[k]).join(', '), false),
    row('Pólizas activas', S.map((c) => c.activas), (v) => String(v), null),
    row('Inmuebles con seguro', S.map((c) => c.con_seguro), (v) => String(v), null),
  ]
})
const cmpGrid = computed(() => ({ gridTemplateColumns: `190px repeat(${Math.max(sel.value.length, 1)}, minmax(0, 1fr))` }))
</script>

<template>
  <PageBar title="Pólizas" subtitle="Solo arriendos · indicadores por aseguradora, contratos activos, alertas para activar a tiempo y aseguradoras · separado de «Negocios»" :back="home">
    <div class="tabs">
      <button v-for="[k, t] in tabs" :key="k" type="button" class="tab" :class="{ on: tab === k }" @click="tab = k; msg = null">{{ t }}</button>
    </div>
  </PageBar>

  <div v-if="T" class="cnt">
    <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.t }}</b></div>
    <a v-if="aleTop" href="#" class="note bad top" @click.prevent="tab = 'ale'"><b>■ {{ aleTop }}</b> · Ver alertas de activación ›</a>

    <template v-if="tab === 'ind' || tab === 'con'">
      <div class="row fw gp10">
        <label class="row gp6 flt">Desde<input v-model="f.desde" class="in dt" type="date" aria-label="Activadas desde"></label>
        <label class="row gp6 flt">Hasta<input v-model="f.hasta" class="in dt" type="date" aria-label="Activadas hasta"></label>
        <label class="row gp6 flt">Aseguradora
          <select v-model="f.ase" class="sel" aria-label="Filtrar por aseguradora">
            <option value="">Todas</option>
            <option v-for="a in AS?.items ?? []" :key="a.id" :value="a.id">{{ a.nombre }}</option>
          </select>
        </label>
        <span class="mut tiny">Pólizas activadas del {{ fd(T.desde) }} al {{ fd(T.hasta) }}</span>
      </div>
      <div v-if="fErr" class="note bad"><b>La fecha «Desde» no puede ser posterior a «Hasta».</b></div>
    </template>

    <!-- Indicadores -->
    <template v-if="tab === 'ind'">
      <div class="kpis">
        <div class="card"><div class="lbl">Pólizas activas</div><div class="kn num k26">{{ T.kpis.activas }}</div><div class="mut tiny">contratos de arriendo vigentes</div></div>
        <div class="card"><div class="lbl">Cuánto valen al mes</div><div class="kn num k26">{{ fmtCOP(T.kpis.costo_mes) }}</div><div class="mut tiny">suma de lo que cobran las aseguradoras</div></div>
        <div class="card"><div class="lbl">Canon asegurado al mes</div><div class="kn num k26">{{ fmtCOP(T.kpis.canon_mes) }}</div><div class="mut tiny">suma de los cánones con póliza</div></div>
        <div class="card"><div class="lbl">Activadas en el rango</div><div class="kn num k26">{{ T.kpis.nuevas }}</div><div class="mut tiny">nuevas pólizas</div></div>
        <div class="card" :class="{ roja: T.kpis.por_activar }">
          <div class="lbl">Por activar</div><div class="kn num k26">{{ T.kpis.por_activar }}</div>
          <div class="mut tiny">{{ T.kpis.vencidas }} vencida{{ T.kpis.vencidas === 1 ? '' : 's' }} · {{ T.kpis.por_vencer }} por vencer</div>
        </div>
      </div>
      <div class="card">
        <div class="sb mb6"><span class="lbl">Por aseguradora</span><span class="mut tiny">costo = canon × precio de la póliza, cada mes</span></div>
        <div class="wrap">
          <div class="tbl t7">
            <div class="th"><span>Aseguradora</span><span>Contratos activos</span><span>Cuánto vale al mes</span><span>Precio promedio</span><span>Activa desde</span><span>Plazo para activar</span><span>Nuevas en el rango</span></div>
            <div v-for="r in T.por_aseguradora" :key="r.id" class="tr">
              <span><b>{{ r.nombre }}</b><br><span class="mut tiny">{{ r.tipos }}</span></span>
              <b class="num">{{ r.activas }}</b>
              <span class="num">{{ r.costo_mes ? fmtCOP(r.costo_mes) : '—' }}</span>
              <span>{{ r.precio_prom ? `${pct(r.precio_prom)} del canon` : '—' }}</span>
              <span>{{ r.activa_desde ? fd(r.activa_desde) : 'Sin pólizas aún' }}</span>
              <span>{{ r.plazo }}</span>
              <span class="num">{{ r.nuevas }}</span>
            </div>
            <div class="tr tot"><span>Total</span><span class="num">{{ tot.act }}</span><span class="num">{{ fmtCOP(tot.costo) }}</span><span /><span /><span /><span class="num">{{ tot.nuevas }}</span></div>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="lbl mb8">Contratos activos por aseguradora</div>
        <div v-for="r in T.por_aseguradora" :key="r.id" class="hbar">
          <span>{{ r.nombre }}</span>
          <div class="track"><div class="fill" :style="{ width: `${Math.round((r.activas / maxAct) * 100)}%` }" /></div>
          <b class="num">{{ r.activas }}</b>
        </div>
      </div>
      <div class="note">
        «Contratos activos» = arriendos vigentes con la póliza activada. «Activa desde» = fecha de la primera póliza vigente con esa aseguradora. El rango de fechas filtra las pólizas
        activadas en ese periodo («Nuevas en el rango»). Quién asume la póliza: la empresa (se descuenta en la ganancia de cada negocio).
        <template v-if="T.kpis.recuperadas"> Pólizas recuperadas en el rango (aprobadas en el segundo estudio): <b>{{ T.kpis.recuperadas }}</b>.</template>
      </div>
    </template>

    <!-- Contratos activos -->
    <div v-if="tab === 'con'" class="card">
      <div class="sb mb6 fw gp8">
        <span class="lbl">Contratos con póliza activa ({{ T.contratos.length }})</span>
        <span class="mut tiny">Activadas del {{ fd(T.desde) }} al {{ fd(T.hasta) }} · {{ T.activas_total }} activas en total</span>
      </div>
      <div class="wrap">
        <div class="tbl t8">
          <div class="th"><span>Negocio</span><span>Inmueble</span><span>Aseguradora · póliza</span><span>Canon</span><span>Póliza al mes</span><span>Activa desde</span><span>Tiempo activa</span><span /></div>
          <template v-for="c in T.contratos" :key="c.id">
            <div class="tr">
              <b>{{ c.negocio ?? '—' }}</b>
              <span>{{ c.inmueble }}<span v-if="c.seguro_inmueble" class="mut tiny"><br>con seguro del inmueble</span></span>
              <span>{{ c.aseguradora }}<br><span class="mut tiny">{{ c.tipo }} · {{ c.numero_poliza }}</span></span>
              <span class="num">{{ fmtCOP(c.canon) }}</span>
              <span class="num">{{ fmtCOP(c.costo_mes) }}</span>
              <span>{{ fd(c.activada_fecha) }}</span>
              <span :class="{ 'chip info': (c.tiempo_activa ?? '').includes('meses') && parseInt(c.tiempo_activa!) >= 24 }">{{ c.tiempo_activa }}</span>
              <button type="button" class="fch" @click="abrir(c, 'terminar')">Terminar</button>
            </div>
            <div v-if="open === c.id && A.modo === 'terminar'" class="panel row fw gp8">
              <div class="fld"><label :for="`t-${c.id}`">Fecha en que terminó el contrato <span class="req">*</span></label><input :id="`t-${c.id}`" v-model="A.fecha" class="in dt" type="date"></div>
              <button type="button" class="btn br" @click="confirmar(c)">Terminar póliza</button>
              <button type="button" class="btn bs" @click="cerrar">Cancelar</button>
            </div>
          </template>
        </div>
      </div>
      <div v-if="!T.contratos.length" class="note">No hay pólizas activadas con estos filtros.</div>
      <div v-if="T.terminadas.length" class="mt10">
        <div class="lbl">Terminadas</div>
        <div v-for="c in T.terminadas" :key="c.id" class="mut tiny hrow">{{ c.negocio ?? '' }} {{ c.inmueble }} · {{ c.aseguradora }} · activa del {{ fd(c.activada_fecha) }} al {{ fd(c.terminada_fecha) }}</div>
      </div>
    </div>

    <!-- En trámite -->
    <template v-if="tab === 'tra'">
      <div class="card col10">
        <div class="sb fw gp8">
          <div><div class="lbl">Pólizas en trámite</div><div class="mut small">Estudios en curso, aprobadas sin firma del contrato y negadas · al registrar la firma pasan a «Alertas de activación»</div></div>
          <button type="button" class="btn bp h36" @click="abrirRegistro">{{ R.on ? 'Cancelar' : '+ Registrar póliza' }}</button>
        </div>
        <div v-if="R.on && opc" class="form col10">
          <b>Registrar el estudio de una póliza</b>
          <div class="g2">
            <div class="fld">
              <label for="r-neg">Negocio de arriendo</label>
              <select id="r-neg" v-model="R.cierre" class="in"><option value="">Sin negocio (contrato anterior)</option><option v-for="n in opc.negocios" :key="n.id" :value="n.id">{{ n.t }}</option></select>
            </div>
            <div class="fld">
              <label for="r-inm">Inmueble</label>
              <select id="r-inm" v-model="R.inmueble" class="in"><option value="">Sin inmueble registrado</option><option v-for="i in opc.inmuebles" :key="i.id" :value="i.id">{{ i.t }}</option></select>
            </div>
          </div>
          <div v-if="!R.cierre && !R.inmueble" class="fld"><label for="r-desc">Descripción <span class="req">*</span></label><input id="r-desc" v-model="R.desc" class="in" placeholder="Ej.: Apto Belén, contrato de 2024"></div>
          <div class="g2">
            <div class="fld">
              <label for="r-ase">Aseguradora <span class="req">*</span></label>
              <select id="r-ase" v-model="R.ase" class="in" @change="R.tipo = ''"><option value="">Elige</option><option v-for="a in opc.aseguradoras" :key="a.id" :value="a.id">{{ a.nombre }}</option></select>
            </div>
            <div class="fld">
              <label for="r-tipo">Tipo de póliza <span class="req">*</span></label>
              <select id="r-tipo" v-model="R.tipo" class="in" :disabled="!R.ase"><option value="">Elige</option><option v-for="t in tiposR" :key="t.id" :value="t.id">{{ t.nombre }} · {{ pct(t.precio_pct) }}</option></select>
            </div>
          </div>
          <div class="g3">
            <div class="fld"><label for="r-can">Canon mensual <span class="req">*</span></label><input id="r-can" v-model="R.canon" class="in" inputmode="numeric" placeholder="$"></div>
            <div class="fld"><label for="r-rad">N.º de radicado</label><input id="r-rad" v-model="R.radicado" class="in" placeholder="Lo da la aseguradora"></div>
            <div class="fld"><label for="r-fec">Fecha del estudio</label><input id="r-fec" v-model="R.fecha" class="in" type="date" :max="hoy"></div>
          </div>
          <label class="row gp8 small"><input v-model="R.seguro" type="checkbox"> Incluye seguro del inmueble</label>
          <div v-if="R.err" class="note bad"><b>{{ R.err }}</b></div>
          <div class="row gp8"><button type="button" class="btn bp" @click="registrar">Registrar estudio</button><button type="button" class="btn bs" @click="R.on = false">Cancelar</button></div>
          <div class="mut tiny">Solo arriendos: las ventas no llevan póliza. Queda «En estudio» y en el registro de cambios.</div>
        </div>

        <div v-for="p in T.tramite" :key="p.id" class="it2">
          <div class="sb fw gp8">
            <div>
              <b class="t15">{{ p.negocio ? `${p.negocio} · ` : '' }}{{ p.inmueble }}</b>
              <div class="mut small">
                {{ p.aseguradora }} · {{ p.tipo }} · canon {{ fmtCOP(p.canon) }} · {{ fmtCOP(p.costo_mes) }} al mes{{ p.radicado ? ` · radicado ${p.radicado}` : '' }}{{ p.asesor ? ` · asesor ${p.asesor}` : '' }}
              </div>
              <div class="mut tiny">
                Estudio del {{ fd(p.estudio_fecha) }}{{ p.estudios > 1 ? ' (segundo estudio)' : '' }}
                <template v-if="p.decision_fecha"> · respuesta el {{ fd(p.decision_fecha) }}</template>
                <template v-if="p.firma_fecha"> · contrato firmado el {{ fd(p.firma_fecha) }}</template>
                <template v-if="p.motivo_negada"> · negada: {{ p.motivo_negada }}</template>
                <template v-if="p.retomada_motivo"> · retomado: {{ p.retomada_motivo }}</template>
              </div>
            </div>
            <span class="row gp6"><span v-if="p.recuperada" class="chip info">Recuperada</span><span class="chip" :class="p.estado_cls">{{ p.estado_txt }}</span></span>
          </div>
          <div class="row fw gp6">
            <template v-if="p.estado === 'en_estudio'">
              <button type="button" class="fch" @click="aprobar(p)">✓ Aprobada</button>
              <button type="button" class="fch" @click="abrir(p, 'negar')">Negada</button>
            </template>
            <button v-if="p.puede_retomar" type="button" class="fch" @click="abrir(p, 'retomar')">Retomar el estudio</button>
            <button v-if="p.estado === 'aprobada'" type="button" class="fch" @click="abrir(p, 'firma')">{{ p.firma_fecha ? 'Corregir firma' : 'Registrar firma del contrato' }}</button>
            <button v-if="p.estado === 'aprobada' && p.firma_fecha" type="button" class="fch" @click="tab = 'ale'; abrirActivar(p)">Activar póliza</button>
            <button type="button" class="fch" @click="abrir(p, 'editar')">Editar</button>
            <button type="button" class="fch rojo" @click="del.p = p; del.motivo = ''">Eliminar</button>
          </div>
          <div v-if="open === p.id" class="panel col8">
            <template v-if="A.modo === 'negar' || A.modo === 'retomar'">
              <div class="fld">
                <label :for="`m-${p.id}`">{{ A.modo === 'negar' ? 'Por qué la negó la aseguradora' : 'Por qué se retoma (cambió el asegurado o el codeudor, o se convenció al cliente)' }} <span class="req">*</span></label>
                <input :id="`m-${p.id}`" v-model="A.motivo" class="in">
              </div>
            </template>
            <div v-else-if="A.modo === 'firma'" class="fld"><label :for="`f-${p.id}`">Fecha de firma del contrato <span class="req">*</span></label><input :id="`f-${p.id}`" v-model="A.fecha" class="in dt" type="date" :max="hoy"></div>
            <template v-else-if="A.modo === 'editar'">
              <div class="g2">
                <div class="fld"><label :for="`c-${p.id}`">Canon mensual</label><input :id="`c-${p.id}`" v-model="A.canon" class="in" inputmode="numeric"></div>
                <div class="fld"><label :for="`r-${p.id}`">N.º de radicado</label><input :id="`r-${p.id}`" v-model="A.radicado" class="in"></div>
              </div>
              <label class="row gp8 small"><input v-model="A.seguro" type="checkbox"> Incluye seguro del inmueble</label>
            </template>
            <div class="row gp8">
              <button type="button" class="btn bp" @click="confirmar(p)">{{ BTN[A.modo] }}</button>
              <button type="button" class="btn bs" @click="cerrar">Cancelar</button>
            </div>
          </div>
        </div>
        <div v-if="!T.tramite.length" class="note ok"><b>✓ No hay pólizas en trámite.</b></div>
        <div class="note">
          Si la póliza fue negada se puede retomar el estudio una vez, indicando por qué. Si el segundo estudio se aprueba cuenta como póliza recuperada. Al aprobarla se avisa al
          asesor del negocio para que coordine la firma del contrato.
        </div>
      </div>
    </template>

    <!-- Alertas de activación -->
    <div v-if="tab === 'ale'" class="card col10">
      <div><div class="lbl">Pólizas por activar</div><div class="mut small">Arriendos con contrato firmado y póliza aprobada que aún no se activan · cada aseguradora tiene su plazo máximo (días desde la firma del contrato)</div></div>
      <div v-for="p in T.alertas" :key="p.id" :class="aleBox(p.alerta?.st)">
        <div class="sb fw gp8">
          <div><b class="t15">{{ p.negocio ? `${p.negocio} · ` : '' }}{{ p.inmueble }}</b><div class="mut small">Arriendo{{ p.asesor ? ` · asesor ${p.asesor}` : '' }} · canon {{ fmtCOP(p.canon) }} · {{ p.tipo }}</div></div>
          <span class="chip big" :class="aleChip(p.alerta?.st)[1]">{{ aleChip(p.alerta?.st)[0] }}</span>
        </div>
        <div class="mini">
          <div><div class="lbl">Aseguradora</div><b>{{ p.aseguradora }}</b></div>
          <div><div class="lbl">Firma del contrato</div><b>{{ fd(p.firma_fecha) }}</b></div>
          <div><div class="lbl">Fecha máxima para activar</div><b>{{ fd(p.alerta?.max) }}</b></div>
          <div>
            <div class="lbl">Días</div>
            <b>van {{ p.alerta?.dias }} · {{ (p.alerta?.falta ?? 0) < 0 ? `vencida hace ${-(p.alerta?.falta ?? 0)}` : `faltan ${p.alerta?.falta}` }}</b>
          </div>
        </div>
        <div><button type="button" class="btn bp" @click="abrirActivar(p)">{{ act.id === p.id ? 'Cerrar' : 'Activar póliza' }}</button></div>
        <div v-if="act.id === p.id" class="actf col8">
          <div class="g3">
            <div class="fld"><label :for="`af-${p.id}`">Fecha de activación <span class="req">*</span></label><input :id="`af-${p.id}`" v-model="act.fecha" class="in" type="date" :max="hoy"></div>
            <div class="fld"><label :for="`an-${p.id}`">N.º de póliza o certificado <span class="req">*</span></label><input :id="`an-${p.id}`" v-model="act.numero" class="in" placeholder="Ej.: POL-000000"></div>
            <div class="fld">
              <span class="fld-label">Soporte (opcional)</span>
              <button type="button" class="btn bs" @click="act.soporte = !act.soporte">{{ act.soporte ? '✓ Soporte marcado' : 'Marcar que hay soporte' }}</button>
            </div>
          </div>
          <div v-if="act.err" class="note bad"><b>{{ act.err }}</b></div>
          <div><button type="button" class="btn bp" @click="activar(p)">Guardar · póliza activada</button></div>
        </div>
      </div>
      <div v-if="!T.alertas.length" class="note ok"><b>✓ No hay pólizas por activar.</b></div>
      <div class="note">
        La alerta sale cuando faltan los días de aviso configurados para cada aseguradora (pestaña «Aseguradoras»), y se pone en rojo si pasa la fecha máxima. Le llega a la Auxiliar
        administrativa y, si se vence, también a Gerencia (en Avisos). Al activar, la póliza pasa a «Contratos activos» y se apaga la alerta.
      </div>
    </div>

    <!-- Aseguradoras -->
    <template v-if="tab === 'ase' && AS">
      <div class="card col10">
        <div class="sb fw gp8">
          <div>
            <div class="lbl">Aseguradoras ({{ AS.items.filter((a) => a.activa).length }} activas)</div>
            <div class="mut small">Empresas con las que se toman pólizas de arrendamiento y seguros del inmueble · las agregan Gerencia y la Auxiliar administrativa</div>
          </div>
          <div class="row fw gp8">
            <button type="button" class="btn bs h36" @click="N.list = !N.list">{{ N.list ? 'Ocultar lista' : 'Ver lista' }}</button>
            <button type="button" class="btn bp h36" @click="N.on = true; N.list = true; N.err = ''">+ Agregar aseguradora</button>
          </div>
        </div>
        <div v-if="N.list || AS.eliminadas.length">
          <template v-for="a in AS.items" :key="a.id">
            <div class="sb arow fw gp6">
              <span><b>{{ a.nombre }}</b> <span class="chip" :class="a.activa ? 'ok' : 'gray'">{{ a.activa ? 'Activa' : 'Inactiva' }}</span><br><span class="mut tiny">{{ asDesc(a) }}</span></span>
              <span class="row gp6">
                <button type="button" class="fch" @click="tipoN.id = tipoN.id === a.id ? '' : a.id; tipoN.err = ''">+ Póliza</button>
                <button type="button" class="fch" @click="run(() => api.editarAseguradora(a.id, { activa: !a.activa }), `${a.nombre} ${a.activa ? 'desactivada: no aparece en pólizas nuevas' : 'activada'}.`)">{{ a.activa ? 'Desactivar' : 'Activar' }}</button>
                <button type="button" class="fch rojo" @click="delAs = delAs === a.id ? null : a.id">{{ delAs === a.id ? 'Cancelar' : 'Eliminar' }}</button>
              </span>
            </div>
            <div v-if="delAs === a.id" class="note bad row fw gp8">
              <b v-if="a.puede_eliminar">¿Eliminar {{ a.nombre }}? Deja de aparecer al registrar pólizas, en las alertas y en el comparador. Queda registrado quién la eliminó y cuándo.</b>
              <b v-else>{{ a.nombre }} tiene {{ a.polizas }} póliza{{ a.polizas === 1 ? '' : 's' }}: no se puede eliminar para no perder su historial. Puedes desactivarla para que no aparezca en pólizas nuevas.</b>
              <button v-if="a.puede_eliminar" type="button" class="btn br h34" @click="run(() => api.eliminarAseguradora(a.id), `${a.nombre} se eliminó. Queda en el registro de cambios.`).then(() => (delAs = null))">Sí, eliminar</button>
              <button type="button" class="btn bs h34" @click="delAs = null">Cancelar</button>
            </div>
            <div v-if="tipoN.id === a.id" class="form col10">
              <b>Nueva póliza de {{ a.nombre }}</b>
              <div class="g2">
                <div class="fld"><label for="tn-n">Nombre o tipo de póliza <span class="req">*</span></label><input id="tn-n" v-model="tipoN.nombre" class="in"></div>
                <div class="fld"><label for="tn-p">Precio (% del canon, cada mes) <span class="req">*</span></label><input id="tn-p" v-model="tipoN.pct" class="in" inputmode="decimal" placeholder="Ej.: 2,2"></div>
                <div class="fld"><label for="tn-e">Costo del estudio ($)</label><input id="tn-e" v-model="tipoN.est" class="in" inputmode="numeric" placeholder="0 si no tiene costo"></div>
                <div class="fld"><label for="tn-r">Días hábiles de respuesta</label><input id="tn-r" v-model="tipoN.resp" class="in" inputmode="numeric"></div>
              </div>
              <div class="row fw gp6">
                <button v-for="(t, k) in COB" :key="k" type="button" class="fch" :class="{ on: tipoN.cob.includes(String(k)) }" @click="tipoN.cob = tipoN.cob.includes(String(k)) ? tipoN.cob.filter((x) => x !== k) : [...tipoN.cob, String(k)]">{{ tipoN.cob.includes(String(k)) ? '✓ ' : '' }}{{ t }}</button>
              </div>
              <div v-if="tipoN.err" class="note bad"><b>{{ tipoN.err }}</b></div>
              <div class="row gp8"><button type="button" class="btn bp" @click="guardarTipo">Guardar póliza</button><button type="button" class="btn bs" @click="tipoN.id = ''">Cancelar</button></div>
            </div>
          </template>
          <div v-if="AS.eliminadas.length" class="mt8">
            <div class="lbl">Aseguradoras eliminadas</div>
            <div v-for="x in AS.eliminadas" :key="x.nombre + x.txt" class="mut tiny hrow">{{ x.nombre }} · {{ x.txt }}</div>
          </div>
        </div>
        <div v-if="N.on" class="form col10">
          <b>Nueva aseguradora</b>
          <div class="g2">
            <div class="fld"><label for="na-n">Nombre de la aseguradora <span class="req">*</span></label><input id="na-n" v-model="N.nombre" class="in" placeholder="Ej.: Aseguradora Ejemplo 4"></div>
            <div class="fld"><label for="na-nit">NIT</label><input id="na-nit" v-model="N.nit" class="in" placeholder="Ej.: 900.000.000-0"></div>
            <div class="fld"><label for="na-c">Persona de contacto</label><input id="na-c" v-model="N.contacto" class="in"></div>
            <div class="fld"><label for="na-t">Teléfono o correo</label><input id="na-t" v-model="N.tel" class="in"></div>
          </div>
          <div class="lbl">Primera póliza que ofrece (luego se pueden agregar más)</div>
          <div class="g2">
            <div class="fld"><label for="na-tp">Nombre o tipo de póliza <span class="req">*</span></label><input id="na-tp" v-model="N.tp" class="in" placeholder="Ej.: Póliza de arrendamiento básica"></div>
            <div class="fld"><label for="na-p">Precio (% del canon, cada mes) <span class="req">*</span></label><input id="na-p" v-model="N.pct" class="in" inputmode="decimal" placeholder="Ej.: 2,2"></div>
            <div class="fld"><label for="na-e">Costo del estudio ($)</label><input id="na-e" v-model="N.est" class="in" inputmode="numeric" placeholder="0 si no tiene costo"></div>
            <div class="fld"><label for="na-r">Días hábiles de respuesta</label><input id="na-r" v-model="N.resp" class="in" inputmode="numeric" placeholder="Ej.: 2"></div>
          </div>
          <div class="g2">
            <div class="fld"><label for="na-dm">Días máximos para activar la póliza (desde la firma del contrato) <span class="req">*</span></label><input id="na-dm" v-model="N.dm" class="in" inputmode="numeric" placeholder="Ej.: 60"></div>
            <div class="fld"><label for="na-av">Avisar con (días de anticipación)</label><input id="na-av" v-model="N.av" class="in" inputmode="numeric" placeholder="10 si lo dejas vacío"></div>
          </div>
          <div class="fld">
            <span class="fld-label">Coberturas y beneficios</span>
            <div class="row fw gp6"><button v-for="(t, k) in COB" :key="k" type="button" class="fch" :class="{ on: N.cob.includes(String(k)) }" @click="togCob(String(k))">{{ N.cob.includes(String(k)) ? '✓ ' : '' }}{{ t }}</button></div>
          </div>
          <div v-if="N.err" class="note bad"><b>{{ N.err }}</b></div>
          <div class="row gp8"><button type="button" class="btn bs" @click="N.on = false">Cancelar</button><button type="button" class="btn bp" @click="guardarAseguradora">Guardar aseguradora</button></div>
          <div class="mut tiny">Al guardar queda en el registro de cambios, aparece al registrar pólizas, en las alertas de activación y, para Gerencia, en el comparador.</div>
        </div>
      </div>
      <div class="card col10">
        <div><div class="lbl">Plazo máximo para activar la póliza</div><div class="mut small">Días desde la firma del contrato que permite cada aseguradora, y con cuántos días de anticipación avisar · los pone Gerencia o la Auxiliar administrativa</div></div>
        <div class="wrap">
          <div class="tbl t4">
            <div class="th"><span>Aseguradora</span><span>Días máximos</span><span>Avisar con (días antes)</span><span /></div>
            <div v-for="a in AS.items.filter((x) => x.activa)" :key="a.id" class="tr">
              <span><b>{{ a.nombre }}</b><br><span class="mut tiny">{{ a.ejemplo ? 'Plazo de ejemplo · real: PENDIENTE DE CONFIGURACIÓN' : `Agregada por ${a.agregada}` }}</span></span>
              <input v-model="pz[a.id]!.dm" class="in h38" type="number" min="1" :aria-label="`Días máximos para activar · ${a.nombre}`" @input="pz[a.id]!.ok = false">
              <input v-model="pz[a.id]!.av" class="in h38" type="number" min="0" :aria-label="`Días de aviso · ${a.nombre}`" @input="pz[a.id]!.ok = false">
              <button type="button" class="fch" @click="guardarPlazo(a)">{{ pz[a.id]?.ok ? '✓ Guardado' : 'Guardar' }}</button>
            </div>
          </div>
        </div>
        <div class="note">Plazos de ejemplo: los reales los da cada aseguradora y quedan PENDIENTE DE CONFIGURACIÓN hasta que se registren. Cada cambio queda en el registro de cambios.</div>
        <div v-if="AS.historial.length">
          <div class="lbl">Cambios recientes</div>
          <div v-for="(h, k) in AS.historial.slice(0, 8)" :key="k" class="mut tiny hrow">{{ fmtCuando(h.at) }} · <b>{{ h.accion }}</b> · {{ h.registro }} · {{ h.actor ?? 'Sistema' }}<template v-if="h.despues"> · {{ h.antes ? `${h.antes} → ` : '' }}{{ h.despues }}</template></div>
        </div>
      </div>
    </template>

    <!-- Comparar pólizas (Gerencia) -->
    <div v-if="tab === 'cmp' && CM" class="card col14 verde">
      <div class="sb fw gp10">
        <div><div class="lbl">Comparar pólizas y entidades · solo arriendos</div><div class="mut small">Precio, coberturas, costos e inmuebles activos con cada póliza · estudios del {{ fd(CM.desde) }} al {{ fd(CM.hasta) }}</div></div>
        <div class="row fw gp8 end">
          <div class="fld"><label for="c-d1">Desde</label><input id="c-d1" v-model="C.desde" class="in h38" type="date"></div>
          <div class="fld"><label for="c-d2">Hasta</label><input id="c-d2" v-model="C.hasta" class="in h38" type="date"></div>
        </div>
      </div>
      <div v-if="cErr" class="note bad"><b>La fecha «Desde» no puede ser posterior a «Hasta». Se muestra el año en curso mientras lo corriges.</b></div>
      <span class="chip pend self-start wrapchip">Precios, coberturas, costos del estudio y entidades reales: PENDIENTE DE CONFIGURACIÓN · las entidades «(ejemplo)» son DATOS DE EJEMPLO</span>
      <div class="ckpis">
        <div v-for="k in cKpis" :key="k[0]" class="ck"><div class="lbl">{{ k[0] }}</div><div class="kn num k28">{{ k[1] }}</div><div class="mut tiny">{{ k[2] }}</div></div>
      </div>
      <div class="row fw gp12 filt">
        <label class="row gp6 flt">Entidad<select v-model="C.e" class="sel" aria-label="Filtrar por entidad"><option value="">Todas</option><option v-for="[id, n] in entsCmp" :key="id" :value="id">{{ n }}</option></select></label>
        <label class="row gp6 flt">Tipo de póliza<select v-model="C.t" class="sel" aria-label="Filtrar por tipo de póliza"><option value="">Todos</option><option v-for="t in tiposCmp" :key="t" :value="t">{{ t }}</option></select></label>
        <label class="row gp6 flt">Ordenar por<select v-model="C.o" class="sel" aria-label="Ordenar pólizas"><option v-for="o in ORD" :key="o[0]" :value="o[0]">{{ o[1] }}</option></select></label>
        <button v-if="C.e || C.t" type="button" class="fch" @click="C.e = ''; C.t = ''">✕ Quitar filtros</button>
      </div>
      <div class="row fw gp6">
        <span class="lbl w110">Canon de ejemplo</span>
        <button v-for="c in [1_200_000, 1_600_000, 2_000_000, 3_000_000]" :key="c" type="button" class="fch" :class="{ on: C.canon === c }" @click="C.canon = c">{{ fmtCOP(c) }}</button>
      </div>
      <div class="cards">
        <div v-for="c in cards" :key="c.id" class="pc" :class="{ sel: C.sel.includes(c.id) }">
          <div class="sb"><div><b class="t15">{{ c.aseguradora }}</b><div class="mut tiny">{{ c.tipo }}</div></div><span v-if="badge(c)" class="chip ok">{{ badge(c) }}</span></div>
          <div class="g2">
            <div class="mbox"><div class="lbl">Precio</div><b class="num t18">{{ pct(c.precio_pct) }}</b><div class="mut t115">del canon, cada mes</div></div>
            <div class="mbox"><div class="lbl">Con canon {{ fmtCOP(C.canon) }}</div><b class="num t18">{{ fmtCOP((C.canon * c.precio_pct) / 100) }}</b><div class="mut t115">al mes · {{ fmtCOP(anual(c)) }} al año</div></div>
          </div>
          <div class="kvs">
            <div class="sb"><span>Costo del estudio</span><b>{{ c.costo_estudio ? fmtCOP(c.costo_estudio) : 'Sin costo' }}</b></div>
            <div class="sb"><span>Respuesta del estudio</span><b>{{ c.dias_respuesta ? `${c.dias_respuesta} ${c.dias_respuesta === 1 ? 'día hábil' : 'días hábiles'}` : 'Sin dato' }}</b></div>
            <div class="sb"><span>Estudios aprobados · en el rango</span><b>{{ c.estudios ? `${c.aprobados} de ${c.estudios} (${c.aprobacion}%)` : 'Sin estudios' }}</b></div>
            <div class="sb"><span>Reclamaciones</span><b class="mut">No se registran todavía</b></div>
            <div class="sb"><span>Pólizas activas hoy</span><b>{{ c.activas }}</b></div>
            <div class="sb"><span>Inmuebles con seguro</span><b>{{ c.con_seguro }}</b></div>
            <div class="sb"><span>Canon asegurado al mes</span><b>{{ fmtCOP(c.canon_mes) }}</b></div>
          </div>
          <div>
            <div class="lbl mb4">Coberturas y beneficios</div>
            <div class="row fw gp4"><span v-for="(t, k) in COB" :key="k" class="chip" :class="c.coberturas.includes(String(k)) ? 'ok' : 'gray'">{{ c.coberturas.includes(String(k)) ? '✓' : '✗' }} {{ t }}</span></div>
          </div>
          <div class="row fw gp6">
            <button type="button" class="fch" :class="{ on: C.sel.includes(c.id) }" @click="togSel(c.id)">{{ C.sel.includes(c.id) ? '✓ En la comparación' : 'Comparar' }}</button>
            <button type="button" class="btn bs h34" @click="C.ver = C.ver === c.id ? '' : c.id">{{ C.ver === c.id ? 'Ocultar inmuebles' : 'Ver inmuebles activos' }}</button>
          </div>
          <div v-if="C.ver === c.id" class="inms">
            <div v-for="(i, k) in c.inmuebles" :key="k" class="sb small"><span><b>{{ i.c }}</b> · {{ i.d }}</span><span class="num">{{ fmtCOP(i.v) }}</span></div>
            <div v-if="!c.inmuebles.length" class="mut tiny">Sin pólizas activas todavía.</div>
            <div v-if="c.activas > c.inmuebles.length" class="mut tiny">y {{ c.activas - c.inmuebles.length }} más en «Contratos activos»</div>
          </div>
        </div>
      </div>
      <div v-if="sel.length >= 2" class="lado">
        <div class="sb mb6"><span class="lbl">Comparación lado a lado</span><button type="button" class="fch" @click="C.sel = []">Quitar comparación</button></div>
        <div class="wrap">
          <div class="minw640">
            <div class="cgrid head" :style="cmpGrid"><span /><span v-for="s in sel" :key="s.id">{{ s.aseguradora }} · {{ s.tipo.replace(' (ejemplo)', '') }}</span></div>
            <div v-for="r in cmpRows" :key="r.t" class="cgrid" :style="cmpGrid"><span class="mut">{{ r.t }}</span><span v-for="(x, i) in r.c" :key="i" :class="{ best: x.best }">{{ x.v }}</span></div>
          </div>
        </div>
        <div class="mut tiny mt6">En verde, la mejor opción de cada fila.</div>
      </div>
      <div v-else class="mut small">Marca «Comparar» en 2 o 3 pólizas para verlas lado a lado.</div>
      <div class="note">
        Póliza de arrendamiento y seguro del inmueble aplican solo a arriendos. «Pólizas activas» = contratos de arriendo vigentes con esa póliza; «Inmuebles con seguro» = los que además
        tienen seguro del inmueble. Quién paga el estudio: PENDIENTE DE CONFIGURACIÓN.
      </div>
    </div>
  </div>

  <ConfirmDialog v-if="del.p" :title="`¿Eliminar la póliza de ${nom(del.p)}?`" confirm-label="Sí, eliminar" danger @confirm="eliminar" @cancel="del.p = null">
    <p class="mb8">Queda registrado quién la eliminó, cuándo y por qué.</p>
    <div class="fld"><label for="del-m">Motivo <span class="req">*</span></label><input id="del-m" v-model="del.motivo" class="in" placeholder="Ej.: registro duplicado"></div>
  </ConfirmDialog>
</template>

<style scoped>
.fw {
  flex-wrap: wrap;
}
.gp4 {
  gap: 4px;
}
.gp6 {
  gap: 6px;
}
.gp8 {
  gap: 8px;
}
.gp10 {
  gap: 10px;
  align-items: center;
}
.gp12 {
  gap: 12px;
  align-items: center;
}
.end {
  align-items: flex-end;
}
.flt {
  font-size: 13px;
  font-weight: 700;
}
.dt {
  min-height: 38px;
  width: auto;
}
.h34 {
  min-height: 34px;
}
.h36 {
  min-height: 36px;
}
.h38 {
  min-height: 38px;
}
.tiny {
  font-size: 12px;
}
.small {
  font-size: 12.5px;
}
.t115 {
  font-size: 11.5px;
}
.t15 {
  font-size: 15px;
}
.t18 {
  font-size: 18px;
}
.k26 {
  font-size: 26px;
}
.k28 {
  font-size: 28px;
}
.mb4 {
  margin-bottom: 4px;
}
.mb6 {
  margin-bottom: 6px;
}
.mb8 {
  margin-bottom: 8px;
}
.mt6 {
  margin-top: 6px;
}
.mt8 {
  margin-top: 8px;
}
.mt10 {
  margin-top: 10px;
}
.w110 {
  min-width: 110px;
}
.self-start {
  align-self: flex-start;
}
.wrapchip {
  white-space: normal;
}
.col8,
.col10,
.col14 {
  display: flex;
  flex-direction: column;
}
.col8 {
  gap: 8px;
}
.col10 {
  gap: 10px;
}
.col14 {
  gap: 14px;
}
.top {
  display: block;
  text-decoration: none;
}
.kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
}
.roja {
  border: 2px solid var(--cdc-bad);
  background: var(--cdc-bad-bg);
}
.tbl {
  display: grid;
}
.t7 {
  min-width: 900px;
}
.t8 {
  min-width: 1000px;
}
.t4 {
  min-width: 680px;
}
.th,
.tr {
  display: grid;
  gap: 10px;
  padding: 9px 6px;
  align-items: center;
  font-size: 13px;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.th {
  font-size: 10.5px;
  color: var(--cdc-gray);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom-color: var(--cdc-border);
}
.t7 .th,
.t7 .tr {
  grid-template-columns: minmax(0, 1.4fr) 110px 130px 120px 130px 140px 120px;
}
.t8 .th,
.t8 .tr {
  grid-template-columns: 100px minmax(0, 1.3fr) minmax(0, 1.1fr) 120px 110px 110px 110px 80px;
}
.t4 .th,
.t4 .tr {
  grid-template-columns: minmax(0, 1.4fr) 170px 170px 120px;
}
.tr.tot {
  font-weight: 800;
  border-bottom: 0;
}
.hbar {
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr) 60px;
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
.panel,
.form {
  border: 1.5px solid var(--cdc-green);
  border-radius: 12px;
  padding: 12px;
  background: var(--cdc-ok-bg);
  margin: 6px 0;
}
.panel {
  background: var(--cdc-bg);
  border: 1px solid var(--cdc-border);
}
.it2 {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.fch.rojo {
  color: var(--cdc-bad);
  border-color: var(--cdc-bad);
}
.abox {
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--cdc-bg);
}
.abox.v {
  background: var(--cdc-bad-bg);
  border: 1.5px solid var(--cdc-bad);
}
.abox.p {
  background: var(--cdc-warn-bg);
  border: 1.5px solid var(--cdc-warn);
}
.chip.big {
  font-size: 12.5px;
  padding: 5px 12px;
}
.mini {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 8px;
}
.mini > div {
  background: #fff;
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 13px;
}
.actf {
  border-top: 1px solid var(--cdc-border);
  padding-top: 10px;
}
.arow {
  font-size: 13px;
  padding: 8px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.hrow {
  padding: 4px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.verde {
  border: 2px solid var(--cdc-green);
}
.ckpis {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
}
.ck {
  border: 1px solid var(--cdc-border);
  border-radius: 12px;
  padding: 10px 12px;
}
.filt {
  background: var(--cdc-bg);
  border-radius: 12px;
  padding: 10px 12px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: 12px;
}
.pc {
  border-radius: 14px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #fff;
  border: 1px solid var(--cdc-border);
}
.pc.sel {
  border: 2px solid var(--cdc-green);
}
.mbox {
  background: var(--cdc-bg);
  border-radius: 10px;
  padding: 8px;
}
.kvs {
  font-size: 12.5px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.inms {
  border-top: 1px solid var(--cdc-border-soft);
  padding-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.lado {
  border: 2px solid var(--cdc-green);
  border-radius: 12px;
  padding: 12px;
}
.minw640 {
  min-width: 640px;
}
.cgrid {
  display: grid;
  gap: 8px;
  font-size: 13px;
  padding: 7px 4px;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.cgrid.head {
  font-size: 12px;
  font-weight: 800;
  border-bottom-color: var(--cdc-border);
}
.best {
  color: var(--cdc-ok);
  font-weight: 800;
}
</style>
