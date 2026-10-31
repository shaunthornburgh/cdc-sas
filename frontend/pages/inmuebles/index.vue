<script setup lang="ts">
import type { InmuebleQuery } from '~/composables/useInmuebles'
import type { EstadoInmueble, Inmueble, InmuebleOpciones } from '~/types/inmuebles'

/**
 * Inmuebles: the property catalog, laid out like X14 (KPIs that filter, tabs, filter row,
 * expandable cards with their history). Approved captaciones join it on their own.
 */
definePageMeta({ module: 'inmuebles' })
useHead({ title: 'Inmuebles · Casa Dolce Casa' })

const auth = useAuth()
const api = useInmuebles()
const me = computed(() => auth.user.value!)
const manager = computed(() => isManager(me.value))
const captador = computed(() => canCapture(me.value))
const admin = computed(() => manager.value || me.value.cargo === 'auxiliar_administrativa')

const { data: opc } = await useAsyncData('inm-opciones', () => api.opciones())
const opciones = computed(() => opc.value as InmuebleOpciones)

type Tab = 'disponible' | 'separado' | 'cerrados' | 'retirado' | 'todos' | 'mios'
const tab = ref<Tab>('disponible')
const filtros = reactive({ negocio: '', tipo: '', zona: '', rango: '', habitaciones: '', incompletos: false, q: '' })
const query = computed<InmuebleQuery>(() => ({
  vista: tab.value === 'mios' ? 'mios' : 'todos',
  estado: ['disponible', 'separado', 'retirado'].includes(tab.value) ? tab.value : 'todos',
  negocio: filtros.negocio || undefined,
  tipo: filtros.tipo || undefined,
  zona: filtros.zona || undefined,
  rango: filtros.rango || undefined,
  habitaciones: filtros.habitaciones ? Number(filtros.habitaciones) : undefined,
  incompletos: filtros.incompletos || undefined,
  q: filtros.q.trim() || undefined,
}))
const { data, refresh, pending } = await useAsyncData('inmuebles', () => api.list(query.value), { watch: [query] })
const items = computed(() => {
  const all = data.value?.items ?? []
  return tab.value === 'cerrados' ? all.filter((i) => i.estado === 'arrendado' || i.estado === 'vendido') : all
})
const k = computed(() => data.value?.kpis)

const KPIS = computed(() => {
  if (!k.value) return []
  return [
    { t: 'Disponibles', v: k.value.disponibles, d: 'para ofrecer a clientes', go: () => pick('disponible') },
    { t: 'En arriendo', v: k.value.arriendo, d: 'disponibles', go: () => pick('disponible', { negocio: 'arriendo' }) },
    { t: 'En venta', v: k.value.venta, d: 'disponibles', go: () => pick('disponible', { negocio: 'venta' }) },
    { t: 'Separados', v: k.value.separados, d: 'un cliente los reservó', go: () => pick('separado') },
    { t: 'Arrendados y vendidos', v: k.value.cerrados_mes, d: 'este mes', go: () => pick('cerrados') },
    { t: 'Datos incompletos', v: k.value.incompletos, d: 'falta precio, área, zona…', bad: k.value.incompletos > 0, go: () => pick('todos', { incompletos: true }) },
  ]
})
function pick(t: Tab, f: Partial<typeof filtros> = {}) {
  tab.value = t
  Object.assign(filtros, { negocio: '', tipo: '', zona: '', rango: '', habitaciones: '', incompletos: false, q: '' }, f)
}
const TABS = computed<[Tab, string][]>(() => [
  ['disponible', 'Disponibles'],
  ['separado', 'Separados'],
  ['cerrados', 'Arrendados y vendidos'],
  ['retirado', 'Retirados'],
  ['todos', 'Todos'],
  ...(captador.value ? ([['mios', `Mis captaciones (${k.value?.mios ?? 0})`]] as [Tab, string][]) : []),
])
const hayFiltros = computed(() => !!(filtros.negocio || filtros.tipo || filtros.zona || filtros.rango || filtros.habitaciones || filtros.incompletos || filtros.q))

// ---- cards
const open = ref<string | null>(null)
const editando = ref<Inmueble | null>(null)
const formNuevo = ref(false)
const msg = ref<{ t: string; ok: boolean } | null>(null)
const est = reactive({ id: '', estado: '' as EstadoInmueble | '', nota: '' })
const busy = ref(false)

async function onSaved(i: Inmueble, t: string) {
  formNuevo.value = false
  editando.value = null
  msg.value = { t, ok: true }
  open.value = i.id
  await refresh()
}
function abrirEstado(i: Inmueble) {
  Object.assign(est, { id: est.id === i.id ? '' : i.id, estado: '', nota: '' })
}
const destinos = (i: Inmueble): EstadoInmueble[] =>
  (['disponible', 'separado', i.negocio === 'venta' ? 'vendido' : 'arrendado', 'retirado'] as EstadoInmueble[]).filter((e) => e !== i.estado)
async function guardarEstado(i: Inmueble) {
  if (!est.estado) return
  busy.value = true
  try {
    const out = await api.estado(i.id, est.estado, est.nota || null)
    msg.value = { t: `${out.codigo} ahora está «${out.estado_txt}».`, ok: true }
    est.id = ''
    await refresh()
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  } finally {
    busy.value = false
  }
}
async function eliminar(i: Inmueble) {
  busy.value = true
  try {
    await api.remove(i.id)
    msg.value = { t: `${i.codigo} eliminado.`, ok: true }
    await refresh()
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  } finally {
    busy.value = false
  }
}
const precioTxt = (i: Inmueble) => (i.precio ? `${fmtCOP(i.precio)}${i.negocio === 'arriendo' ? ' / mes' : ''}` : 'Sin precio')
const datos = (i: Inmueble) => [
  ['Precio', precioTxt(i)],
  ['Área', i.area_m2 ? `${Number(i.area_m2).toLocaleString('es-CO')} m²` : '—'],
  ['Habitaciones', i.habitaciones ?? '—'],
  ['Baños', i.banos ?? '—'],
  ['Parqueadero', i.parqueadero == null ? '—' : i.parqueadero ? 'Sí' : 'No'],
  ['Captó', i.captador_name ?? 'Registrado a mano'],
]
</script>

<template>
  <PageBar title="Inmuebles" subtitle="Catálogo de inmuebles en venta y arriendo · las captaciones aprobadas entran solas · los disponibles se envían como opciones a los clientes" :back="manager ? '/coordinacion' : '/'">
    <button v-if="opciones?.puede_crear" type="button" class="btn bp" @click="formNuevo = !formNuevo; editando = null">{{ formNuevo ? 'Cancelar' : '+ Registrar inmueble' }}</button>
    <NuxtLink v-else-if="captador" class="btn bp" to="/captaciones">+ Nueva captación</NuxtLink>
    <NuxtLink class="btn bs" to="/inmuebles/administracion">Administración</NuxtLink>
  </PageBar>

  <div class="cnt">
    <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.ok ? '✓ ' : '' }}{{ msg.t }}</b></div>

    <div class="g6 kpis">
      <button v-for="x in KPIS" :key="x.t" type="button" class="card kpi" @click="x.go">
        <span class="lbl">{{ x.t }}</span>
        <span class="kn num" :class="{ 'kn-bad': x.bad }">{{ x.v }}</span>
        <span class="mut tiny">{{ x.d }}</span>
      </button>
    </div>

    <InmuebleForm v-if="formNuevo && opciones" :opciones="opciones" :manager="manager" @saved="onSaved" @cancel="formNuevo = false" />

    <div class="tabs scroll-x">
      <button v-for="[t, l] in TABS" :key="t" type="button" class="tab" :class="{ on: tab === t }" @click="tab = t">{{ l }}</button>
    </div>
    <div class="row fw gap6">
      <button type="button" class="fch" :class="{ on: !filtros.negocio }" @click="filtros.negocio = ''">Todos</button>
      <button type="button" class="fch" :class="{ on: filtros.negocio === 'arriendo' }" @click="filtros.negocio = 'arriendo'">Arriendo</button>
      <button type="button" class="fch" :class="{ on: filtros.negocio === 'venta' }" @click="filtros.negocio = 'venta'">Venta</button>
      <select v-model="filtros.tipo" class="fsel" aria-label="Tipo de inmueble">
        <option value="">Todos los tipos</option>
        <option v-for="t in TIPOS_INMUEBLE" :key="t" :value="t">{{ TIPO_INMUEBLE_LABELS[t] }}</option>
      </select>
      <select v-model="filtros.zona" class="fsel" aria-label="Zona">
        <option value="">Todas las zonas</option>
        <option v-for="z in opciones?.zonas ?? []" :key="z">{{ z }}</option>
      </select>
      <select v-model="filtros.rango" class="fsel" aria-label="Precio">
        <option value="">Todos los precios</option>
        <option v-for="(t, key) in opciones?.rangos ?? {}" :key="key" :value="key">{{ t }}</option>
      </select>
      <select v-model="filtros.habitaciones" class="fsel" aria-label="Habitaciones">
        <option value="">Habitaciones</option>
        <option v-for="h in [1, 2, 3, 4]" :key="h" :value="h">{{ h }}+ hab.</option>
      </select>
      <button type="button" class="fch" :class="{ on: filtros.incompletos }" @click="filtros.incompletos = !filtros.incompletos">Datos incompletos</button>
      <input v-model="filtros.q" class="in q" type="search" placeholder="Código, dirección o barrio" aria-label="Buscar">
      <button v-if="hayFiltros" type="button" class="fch" @click="pick(tab)">✕ Quitar filtros</button>
    </div>

    <div v-for="i in items" :key="i.id" class="card stack" :class="{ warn: i.faltantes.length && i.estado !== 'retirado' }">
      <div class="sb top">
        <div>
          <b>{{ i.codigo }} · {{ i.titulo }}</b>
          <div class="mut small">{{ i.direccion }}{{ i.barrio ? ` · ${i.barrio}` : '' }}{{ i.municipio ? ` · ${i.municipio}` : '' }}</div>
        </div>
        <div class="row gap6">
          <span class="chip gray">{{ NEGOCIO_LABELS[i.negocio] }}</span>
          <span class="chip" :class="INM_ESTADO_CLS[i.estado]">{{ i.estado === 'disponible' ? '● ' : '' }}{{ i.estado_txt }}</span>
        </div>
      </div>
      <div class="datos">
        <div v-for="[l, v] in datos(i)" :key="l">
          <div class="mut tiny">{{ l }}</div>
          <b class="small">{{ v }}</b>
        </div>
      </div>
      <div v-if="i.faltantes.length" class="mut small bad-txt">Datos incompletos: falta {{ i.faltantes.join(', ') }}.</div>
      <div class="row fw gap6">
        <button type="button" class="btn bs sm" @click="open = open === i.id ? null : i.id">{{ open === i.id ? 'Cerrar' : 'Ver detalle' }}</button>
        <button v-if="i.can_edit" type="button" class="btn bs sm" @click="editando = editando?.id === i.id ? null : i; open = i.id">Editar datos</button>
        <button v-if="manager" type="button" class="btn bs sm" @click="abrirEstado(i)">Cambiar estado</button>
        <NuxtLink v-if="i.captacion_id && (manager || i.can_edit)" class="btn bs sm ghost" :to="`/captaciones/${i.captacion_id}`">Ver captación {{ i.captacion_code }}</NuxtLink>
        <NuxtLink v-if="admin" class="btn bs sm ghost" :to="`/inmuebles/administracion?inmueble=${i.id}`">Inventarios y reparaciones</NuxtLink>
      </div>

      <div v-if="est.id === i.id" class="panel">
        <div class="row fw gap6">
          <button v-for="e in destinos(i)" :key="e" type="button" class="opt" :class="{ on: est.estado === e }" @click="est.estado = e">{{ opciones.estados[e] }}</button>
        </div>
        <div class="fld">
          <label :for="`en-${i.id}`">Nota {{ est.estado === 'separado' || est.estado === 'retirado' ? '(obligatoria)' : '(opcional)' }}</label>
          <input :id="`en-${i.id}`" v-model="est.nota" class="in" :placeholder="est.estado === 'separado' ? 'Quién lo separó y hasta cuándo' : est.estado === 'retirado' ? 'Por qué se retira' : ''">
        </div>
        <div class="row gap6"><button type="button" class="btn bp" :disabled="busy || !est.estado" @click="guardarEstado(i)">Guardar estado</button></div>
      </div>

      <InmuebleForm v-if="editando?.id === i.id && opciones" :opciones="opciones" :inmueble="i" :manager="manager" @saved="onSaved" @cancel="editando = null" />

      <div v-if="open === i.id" class="panel">
        <div v-if="i.descripcion" class="small">{{ i.descripcion }}</div>
        <div class="datos">
          <div><div class="mut tiny">Administración</div><b class="small">{{ i.administracion ? fmtCOP(i.administracion) : '—' }}</b></div>
          <div><div class="mut tiny">Estrato</div><b class="small">{{ i.estrato ?? '—' }}</b></div>
          <div><div class="mut tiny">Zona</div><b class="small">{{ i.zona ?? '—' }}</b></div>
          <div v-if="i.ve_propietario"><div class="mut tiny">Propietario</div><b class="small">{{ i.propietario_nombre ?? '—' }}</b></div>
          <div v-if="i.ve_propietario"><div class="mut tiny">Teléfono</div><b class="small">{{ i.propietario_telefono ?? '—' }}</b></div>
          <div><div class="mut tiny">Estado desde</div><b class="small">{{ fmtCuando(i.estado_at) }}</b></div>
        </div>
        <div v-if="!i.ve_propietario" class="mut tiny">Los datos del propietario los ven Coordinación, Gerencia, la Auxiliar y quien lo captó.</div>
        <div class="lbl">Historial</div>
        <div v-for="(e, n) in [...i.eventos].reverse()" :key="n" class="small">
          <span class="mut">· </span>{{ e.titulo }}<span v-if="e.detalle" class="mut"> · {{ e.detalle }}</span>
          <span class="mut tiny"> · {{ e.created_by_name ?? 'Sistema' }} · {{ fmtCuando(e.created_at) }}</span>
        </div>
        <div v-if="manager && !i.captacion_id" class="row"><button type="button" class="btn br sm" :disabled="busy" @click="eliminar(i)">Eliminar</button></div>
      </div>
    </div>
    <div v-if="!items.length" class="note">{{ pending ? 'Cargando…' : 'No hay inmuebles con estos filtros.' }}</div>

    <div class="note">
      Las captaciones aprobadas por Coordinación entran solas al catálogo con su captador; una captación rápida queda con «datos incompletos»
      hasta que se completen. Solo los inmuebles disponibles se envían como opciones a los clientes. El estado lo cambian Coordinación y
      Gerencia; quien captó el inmueble puede completar sus datos. Cada cambio queda en el historial.
    </div>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.top {
  align-items: flex-start;
  gap: 10px;
}
.kpi {
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
  font: inherit;
  cursor: pointer;
}
.kpi:hover {
  border-color: var(--cdc-green);
}
.kn-bad {
  color: var(--sem-rojo);
}
.warn {
  border: 1.5px solid #e8c48a;
}
.bad-txt {
  color: var(--sem-rojo);
}
.datos {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
}
.fw {
  flex-wrap: wrap;
}
.gap6 {
  gap: 6px;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.q {
  min-height: 32px;
  width: 220px;
  font-size: 12.5px;
  border-radius: var(--radius-pill);
}
.scroll-x {
  overflow-x: auto;
}
.ghost {
  border-color: var(--cdc-border);
  color: var(--cdc-muted);
}
@media (max-width: 760px) {
  .kpis {
    grid-template-columns: 1fr 1fr;
  }
  .datos {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .q {
    width: 100%;
  }
}
</style>
