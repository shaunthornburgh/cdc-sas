<script setup lang="ts">
import type { AdminQuery, AdminResumen, Inventario, Reparacion, Solicitud } from '~/types/administracion'

/**
 * X14 «Administración de inmuebles»: inventories, repairs and owner / tenant requests.
 * Same layout as the prototype: KPI cards that pick the tab, tabs + date / status filters,
 * a «nuevo» form, and cards that expand. Managers (Coordinación, Gerencia, Auxiliar) see
 * everything; anyone else sees only what's assigned to them.
 */
definePageMeta({ module: 'inmuebles' })
useHead({ title: 'Administración de inmuebles · Casa Dolce Casa' })

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const api = useAdministracion()
const me = computed(() => auth.user.value!)

const { data: res, refresh: refreshRes } = await useAsyncData('admin-resumen', () => api.resumen())
const R = computed(() => res.value as AdminResumen)
const puede = computed(() => !!R.value?.puede_gestionar)
const L = computed(() => R.value?.labels ?? {})

// ---- filters (X14: Desde, Hasta, Estado; plus the property when coming from the catalog)
type Tab = 'inv' | 'man' | 'pqr'
const tab = ref<Tab>((['inv', 'man', 'pqr'] as Tab[]).includes(route.query.tab as Tab) ? (route.query.tab as Tab) : 'inv')
const shift = (months: number, end = false) => {
  const [y, m] = localDate(0).split('-').map(Number)
  const d = new Date(Date.UTC(y!, m! - 1 + months + (end ? 1 : 0), end ? 0 : 1))
  return d.toISOString().slice(0, 10)
}
const f = reactive({ desde: shift(-2), hasta: shift(1, true), estado: '' })
const inmuebleId = computed(() => (typeof route.query.inmueble === 'string' ? route.query.inmueble : ''))
const fErr = computed(() => !!(f.desde && f.hasta && f.desde > f.hasta))
const query = computed<AdminQuery>(() => ({
  desde: fErr.value ? undefined : f.desde || undefined,
  hasta: fErr.value ? undefined : f.hasta || undefined,
  estado: f.estado || undefined,
  inmueble_id: inmuebleId.value || undefined,
}))
const { data: rows, refresh, pending } = await useAsyncData(
  'admin-rows',
  async () => {
    const q = query.value
    if (tab.value === 'inv') return { t: 'inv' as const, items: await api.inventarios(q) }
    if (tab.value === 'man') return { t: 'man' as const, items: await api.reparaciones(q) }
    return { t: 'pqr' as const, items: await api.solicitudes(q) }
  },
  { watch: [query, tab] },
)
const inmuebleTxt = computed(() => {
  const x = R.value?.inmuebles.find((i) => i.id === inmuebleId.value)
  const first = rows.value?.items[0] as { inmueble?: { codigo: string; titulo: string } } | undefined
  return x ? `${x.codigo} ${x.titulo}` : first?.inmueble ? `${first.inmueble.codigo} ${first.inmueble.titulo}` : 'este inmueble'
})
const quitarInmueble = () => router.replace({ query: { ...route.query, inmueble: undefined } })

function pick(t: Tab, estado = '') {
  tab.value = t
  f.estado = estado
  open.value = null
  form.on = false
}

// ---- KPIs (X14)
const KPIS = computed(() => {
  const k = R.value?.kpis
  if (!k) return []
  return [
    { tab: 'inv' as Tab, e: 'programado', t: 'Inventarios esta semana', v: k.inventarios_semana, d: 'programados en los próximos 7 días', bad: false },
    { tab: 'inv' as Tab, e: 'con_novedades', t: 'Inventarios con novedades', v: k.inventarios_novedades, d: 'daños o faltantes por resolver', bad: k.inventarios_novedades > 0 },
    { tab: 'man' as Tab, e: '', t: 'Reparaciones abiertas', v: k.reparaciones_abiertas, d: `${k.reparaciones_urgentes} urgente${k.reparaciones_urgentes === 1 ? '' : 's'}`, bad: k.reparaciones_urgentes > 0 },
    { tab: 'man' as Tab, e: 'terminada', t: 'Tiempo de reparación', v: `${String(k.reparacion_dias_promedio).replace('.', ',')} días`, d: 'promedio de las terminadas', bad: false },
    { tab: 'pqr' as Tab, e: '', t: 'Solicitudes y quejas abiertas', v: k.solicitudes_abiertas, d: 'de propietarios e inquilinos', bad: false },
    { tab: 'pqr' as Tab, e: 'fuera_de_plazo', t: 'Fuera de plazo', v: k.solicitudes_fuera_plazo, d: `más de ${R.value.plazo} días hábiles sin respuesta`, bad: k.solicitudes_fuera_plazo > 0 },
  ]
})
const TABS = computed<[Tab, string][]>(() => {
  const k = R.value?.kpis
  return [
    ['inv', `Inventarios (${k?.inventarios ?? 0})`],
    ['man', `Mantenimiento y reparaciones (${k?.reparaciones_abiertas ?? 0} abiertas)`],
    ['pqr', `Solicitudes y quejas (${k?.solicitudes_abiertas ?? 0} abiertas)`],
  ]
})
const estadosOp = computed(() => {
  const m = tab.value === 'inv' ? L.value.estado_inventario : tab.value === 'man' ? L.value.estado_reparacion : L.value.estado_solicitud
  return [...Object.entries(m ?? {}), ...(tab.value === 'pqr' ? [['fuera_de_plazo', 'Fuera de plazo']] : [])]
})

// ---- messages and refresh
const msg = ref<{ t: string; ok: boolean } | null>(null)
const open = ref<string | null>(null)
async function changed(t: string) {
  if (t) msg.value = { t, ok: true }
  await Promise.all([refresh(), refreshRes()])
}
const fail = (t: string) => (msg.value = { t, ok: false })

// ---- «nuevo» form (X14: inmueble, two or three selects, fecha, detalle)
const form = reactive({
  on: false,
  err: '',
  busy: false,
  inmueble_id: '',
  fecha: localDate(0),
  detalle: '',
  a: '',
  b: '',
  c: '',
  nombre: '',
  prioridad: 'normal',
  responsable_id: '',
})
const nuevoT = computed(() =>
  form.on ? 'Cancelar' : tab.value === 'inv' ? '+ Programar inventario' : tab.value === 'man' ? '+ Nueva solicitud de reparación' : '+ Registrar solicitud o queja',
)
const fTit = computed(() =>
  tab.value === 'inv' ? 'Programar inventario' : tab.value === 'man' ? 'Nueva solicitud de mantenimiento o reparación' : 'Registrar solicitud, queja o reclamo',
)
function nuevo() {
  if (form.on) return (form.on = false)
  const t = tab.value
  Object.assign(form, {
    on: true,
    err: '',
    inmueble_id: inmuebleId.value || '',
    fecha: localDate(0),
    detalle: '',
    a: t === 'inv' ? 'entrega' : t === 'man' ? 'plomeria' : 'peticion',
    b: t === 'pqr' ? 'whatsapp' : '',
    c: 'inquilino',
    nombre: '',
    prioridad: 'normal',
    responsable_id: t === 'inv' ? '' : me.value.id,
  })
}
const campos = computed(() => {
  if (tab.value === 'inv') return [{ l: 'Tipo', k: 'a' as const, op: L.value.tipo_inventario }]
  if (tab.value === 'man') return [{ l: 'Tipo de trabajo', k: 'a' as const, op: L.value.categoria }]
  return [
    { l: 'Tipo', k: 'a' as const, op: L.value.tipo_solicitud },
    { l: 'Canal', k: 'b' as const, op: L.value.canal },
    { l: 'Quién la hace', k: 'c' as const, op: L.value.de },
  ]
})
const fDetL = computed(() => (tab.value === 'inv' ? 'Referencia (contrato o negocio y cliente)' : tab.value === 'man' ? 'Qué hay que reparar' : 'Qué pide o de qué se queja'))
const fDetP = computed(() => (tab.value === 'inv' ? 'Ej.: CTO-0102 · Cliente Ejemplo 42' : tab.value === 'man' ? 'Ej.: Fuga en el lavaplatos' : 'Ej.: Copia del contrato'))

async function guardar() {
  form.err = ''
  if (!form.inmueble_id || !form.fecha || !form.detalle.trim() || (tab.value === 'inv' && !form.responsable_id)) {
    form.err = tab.value === 'inv' ? 'Completa el inmueble, el responsable, la fecha y el detalle.' : 'Completa el inmueble, la fecha y el detalle.'
    return
  }
  form.busy = true
  const base = { inmueble_id: form.inmueble_id, fecha: form.fecha }
  const resp = form.responsable_id || null
  try {
    let id: string
    let t: string
    if (tab.value === 'inv') {
      const x: Inventario = await api.crearInventario({ ...base, tipo: form.a, referencia: form.detalle, responsable_id: resp })
      id = x.id
      t = `${x.code} programado para el ${fmtFecha(x.fecha)} con ${x.responsable?.full_name}.`
    } else if (tab.value === 'man') {
      const x: Reparacion = await api.crearReparacion({ ...base, categoria: form.a, prioridad: form.prioridad, titulo: form.detalle, solicitante: form.nombre || null, responsable_id: resp })
      id = x.id
      t = `${x.code} registrada${x.prioridad === 'urgente' ? ' como URGENTE' : ''}.`
    } else {
      const x: Solicitud = await api.crearSolicitud({ ...base, tipo: form.a, canal: form.b, de: form.c, nombre: form.nombre || null, descripcion: form.detalle, prioridad: form.prioridad, responsable_id: resp })
      id = x.id
      t = `${x.code} registrada. Plazo de respuesta: ${x.plazo} días hábiles.`
    }
    form.on = false
    open.value = id
    await changed(t)
  } catch (e) {
    form.err = apiErrorMessage(e)
  } finally {
    form.busy = false
  }
}

const nota = computed(() => {
  const p = R.value?.plazo ?? 15
  if (tab.value === 'inv')
    return 'El inventario lo hace el asesor responsable en el inmueble, ambiente por ambiente, y se cierra con la firma del propietario y del inquilino. Si tiene novedades, se crea la solicitud de reparación con un toque. Fotos: por ahora solo se cuentan (la carga de archivos está pendiente). Formato del acta: PENDIENTE DE CONFIGURACIÓN.'
  if (tab.value === 'man')
    return 'Flujo: recibida → cotizada → aprobada (por el propietario si paga él) → en ejecución → terminada. Para pasar de «recibida» se necesitan proveedor y valor; para terminarla, saber quién paga. Si paga el propietario, se descuenta en su liquidación (% de gestión y paso al Software Financiero: PENDIENTE DE CONFIGURACIÓN).'
  return `Plazo de respuesta: ${p} días hábiles (lunes a viernes, sin festivos · PENDIENTE DE CONFIGURACIÓN). Si una solicitud pasa el plazo sin respuesta, se pone en rojo. Cada respuesta queda con fecha, hora y quién la envió.`
})
</script>

<template>
  <PageBar
    title="Administración de inmuebles"
    subtitle="Inventarios de entrega y recepción, mantenimiento y reparaciones, y solicitudes y quejas de propietarios e inquilinos"
    :back="puede && me.cargo !== 'auxiliar_administrativa' ? '/coordinacion' : '/'"
  >
    <NuxtLink class="btn bs" to="/inmuebles">Catálogo</NuxtLink>
    <button v-if="puede" type="button" class="btn bp" @click="nuevo">{{ nuevoT }}</button>
  </PageBar>

  <div class="cnt">
    <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.t }}</b></div>
    <div v-if="!puede" class="note">Ves los inventarios, reparaciones y solicitudes que tienes a cargo.</div>

    <div class="g6 kpis">
      <button v-for="x in KPIS" :key="x.t" type="button" class="card kpi" :class="{ focus: tab === x.tab }" @click="pick(x.tab, x.e)">
        <span class="lbl tiny">{{ x.t }}</span>
        <span class="kn num" :class="{ 'bad-txt': x.bad }">{{ x.v }}</span>
        <span class="mut tiny">{{ x.d }}</span>
      </button>
    </div>

    <div class="sb fw">
      <div class="tabs scroll-x">
        <button v-for="[t, l] in TABS" :key="t" type="button" class="tab" :class="{ on: tab === t }" @click="pick(t)">{{ l }}</button>
      </div>
      <div class="row fw gap8">
        <label class="row gap6 flt">Desde<input v-model="f.desde" class="in dt" type="date" aria-label="Desde"></label>
        <label class="row gap6 flt">Hasta<input v-model="f.hasta" class="in dt" type="date" aria-label="Hasta"></label>
        <label class="row gap6 flt">
          Estado
          <select v-model="f.estado" class="sel dt" aria-label="Filtrar por estado">
            <option value="">Todos</option>
            <option v-for="[k, t] in estadosOp" :key="k" :value="k">{{ t }}</option>
          </select>
        </label>
      </div>
    </div>
    <div v-if="fErr" class="note bad"><b>La fecha «Desde» no puede ser posterior a «Hasta».</b></div>
    <div v-if="inmuebleId" class="row gap6">
      <span class="chip gray">Solo {{ inmuebleTxt }}</span>
      <button type="button" class="fch" @click="quitarInmueble">✕ Ver todos</button>
    </div>

    <div v-if="form.on" class="card focus stack">
      <b class="t16">{{ fTit }}</b>
      <div class="fgrid">
        <div class="fld">
          <label for="f-inm">Inmueble <span class="req">*</span></label>
          <select id="f-inm" v-model="form.inmueble_id" class="in">
            <option value="" disabled>Elige el inmueble</option>
            <option v-for="i in R.inmuebles" :key="i.id" :value="i.id">{{ i.codigo }} {{ i.titulo }}</option>
          </select>
        </div>
        <div v-for="c in campos" :key="c.l" class="fld">
          <label :for="`f-${c.k}`">{{ c.l }}</label>
          <select :id="`f-${c.k}`" v-model="form[c.k]" class="in">
            <option v-for="(t, k) in c.op" :key="k" :value="k">{{ t }}</option>
          </select>
        </div>
        <div v-if="tab !== 'inv'" class="fld">
          <label for="f-pri">Prioridad</label>
          <select id="f-pri" v-model="form.prioridad" class="in">
            <option v-for="(t, k) in L.prioridad" :key="k" :value="k">{{ t }}</option>
          </select>
        </div>
        <div class="fld">
          <label for="f-resp">{{ tab === 'inv' ? 'Responsable (asesor)' : 'Responsable' }}<span v-if="tab === 'inv'" class="req"> *</span></label>
          <select id="f-resp" v-model="form.responsable_id" class="in">
            <option v-if="tab === 'inv'" value="" disabled>Elige quién lo hace</option>
            <option v-for="u in R.responsables" :key="u.id" :value="u.id">{{ u.id === me.id ? `${u.full_name} (yo)` : u.full_name }}</option>
          </select>
        </div>
        <div class="fld">
          <label for="f-fecha">{{ tab === 'pqr' ? 'Recibida el' : 'Fecha' }} <span class="req">*</span></label>
          <input id="f-fecha" v-model="form.fecha" class="in" type="date" :max="tab === 'pqr' ? localDate(0) : undefined">
        </div>
        <div v-if="tab !== 'inv'" class="fld">
          <label for="f-nom">{{ tab === 'man' ? 'Quién la pidió' : 'Nombre de quien la hace' }}</label>
          <input id="f-nom" v-model="form.nombre" class="in" :placeholder="tab === 'man' ? 'Ej.: Inquilino · Cliente Ejemplo 12' : 'Ej.: Cliente Ejemplo 44'">
        </div>
      </div>
      <div class="fld">
        <label for="f-det">{{ fDetL }} <span class="req">*</span></label>
        <input id="f-det" v-model="form.detalle" class="in" :placeholder="fDetP">
      </div>
      <div v-if="form.err" class="note bad"><b>{{ form.err }}</b></div>
      <div class="row gap8">
        <button type="button" class="btn bp" :disabled="form.busy" @click="guardar">Guardar</button>
        <button type="button" class="btn bs" @click="form.on = false">Cancelar</button>
      </div>
    </div>

    <template v-if="rows?.t === 'inv'">
      <AdminInventarioCard v-for="x in rows.items" :key="x.id" :inv="x" :open="open === x.id" @toggle="open = open === x.id ? null : x.id" @changed="changed" @error="fail" />
    </template>
    <template v-else-if="rows?.t === 'man'">
      <AdminReparacionCard v-for="x in rows.items" :key="x.id" :rep="x" :labels="L" :open="open === x.id" @toggle="open = open === x.id ? null : x.id" @changed="changed" @error="fail" />
    </template>
    <template v-else-if="rows?.t === 'pqr'">
      <AdminSolicitudCard v-for="x in rows.items" :key="x.id" :sol="x" :open="open === x.id" @toggle="open = open === x.id ? null : x.id" @changed="changed" @error="fail" />
    </template>
    <div v-if="!rows?.items.length" class="note">{{ pending ? 'Cargando…' : 'No hay registros con estos filtros.' }}</div>
    <div class="note">{{ nota }}</div>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.tiny {
  font-size: 10.5px;
}
.bad-txt {
  color: var(--cdc-bad);
}
.fw {
  flex-wrap: wrap;
}
.gap6 {
  gap: 6px;
}
.gap8 {
  gap: 8px;
}
.kpi {
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
  font: inherit;
  cursor: pointer;
  padding: 12px;
  border-radius: 12px;
}
.kpi .kn {
  font-size: 28px;
}
.kpi:hover {
  border-color: var(--cdc-green);
}
.flt {
  font-size: 13px;
  font-weight: 700;
}
.dt {
  min-height: 38px;
  width: auto;
}
.fgrid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px;
}
.t16 {
  font-size: 16px;
}
.scroll-x {
  overflow-x: auto;
  max-width: 100%;
}
@media (max-width: 760px) {
  .kpis {
    grid-template-columns: 1fr 1fr;
  }
  .tab {
    white-space: nowrap;
    flex: none;
  }
  .tabs {
    flex-wrap: nowrap;
  }
}
</style>
