<script setup lang="ts">
import type { PedidoQuery } from '~/composables/usePedidos'
import type { TipoNegocio } from '~/types/leads'
import type { Pedido, PedidoList, PedidoOpciones } from '~/types/pedidos'

/**
 * Pedidos.
 * - Coordinación / Gerencia: prototype K06 (KPIs, team table, «Vencidos», decide expired ones).
 * - Asesores (M06) and Atención y Preventa (C10): «Mis pedidos» and the team's pedidos.
 */
definePageMeta({ module: 'pedidos' })
useHead({ title: 'Pedidos · Casa Dolce Casa' })

const auth = useAuth()
const pedidos = usePedidos()
const me = computed(() => auth.user.value!)
const manager = computed(() => isManager(me.value))
const atencion = computed(() => me.value.funcion === 'atencion_cliente' || me.value.funcion === 'pre_ventas')

const { data: opc } = await useAsyncData('pedido-opciones', () => pedidos.opciones())
const opciones = computed(() => opc.value as PedidoOpciones)

type Vista = PedidoQuery['vista']
const vista = ref<Vista>(manager.value ? 'todos' : 'mis')
const filtros = reactive({ negocio: '' as TipoNegocio | '', rango: '', zona: '', proximos: false, responsable_id: '', q: '' })
const query = computed<PedidoQuery>(() => ({
  vista: vista.value,
  negocio: filtros.negocio || undefined,
  rango: filtros.rango || undefined,
  zona: filtros.zona || undefined,
  proximos: filtros.proximos || undefined,
  responsable_id: filtros.responsable_id || undefined,
  q: filtros.q.trim() || undefined,
}))
const { data, refresh, pending } = await useAsyncData('pedidos', () => pedidos.list(query.value), {
  watch: [query],
  default: (): PedidoList => ({ items: [], kpis: { abiertos: 0, proximos_a_vencer: 0, vencidos_mes: 0, vencidos_sin_decidir: 0 } }),
})

const flash = ref<string | null>(null)
const formOpen = ref(false)
const startWith = ref<{ code: string; f: string } | null>(null)
const expanded = ref<string | null>(null)

async function onCreated(p: Pedido) {
  formOpen.value = false
  flash.value = `Pedido ${p.code} creado · responsable ${p.responsable.full_name} · fecha límite ${fmtCuando(p.fecha_limite)}.`
  if (!manager.value) vista.value = p.responsable.id === me.value.id ? 'mis' : 'equipo'
  await refresh()
}
async function onChanged(_: Pedido, msg: string) {
  flash.value = msg
  startWith.value = null
  await refresh()
}
/** From the duplicate warning: open that pedido's «Actualizar». */
async function irAActualizar(code: string) {
  formOpen.value = false
  filtros.q = code
  startWith.value = { code, f: 'upd' }
  vista.value = manager.value ? 'todos' : 'mis'
  await nextTick()
  await refresh()
  if (!manager.value && !data.value.items.length) vista.value = 'equipo'
  expanded.value = data.value.items.find((p) => p.code === code)?.id ?? null
}
const TABS = computed<[Vista, string][]>(() =>
  manager.value
    ? [['todos', 'Pedidos del equipo'], ['vencidos', 'Vencidos']]
    : [['mis', 'Mis pedidos'], ['equipo', atencion.value ? 'Pedidos de los asesores' : 'Pedidos de mi equipo']],
)
const hayFiltros = computed(() => !!(filtros.negocio || filtros.rango || filtros.zona || filtros.proximos || filtros.responsable_id || filtros.q))
function limpiar() {
  Object.assign(filtros, { negocio: '', rango: '', zona: '', proximos: false, responsable_id: '', q: '' })
}
const k = computed(() => data.value.kpis)
</script>

<template>
  <PageBar
    title="Pedidos"
    :subtitle="manager
      ? 'Coordinación ve los pedidos de su equipo · Gerencia, los de toda la empresa · los vencidos se conservan'
      : atencion
        ? 'Lo que buscan tus clientes: tus pedidos y los de los asesores · mismo sistema que los asesores'
        : 'Lo que buscan tus clientes · si cambia lo que busca, actualiza su pedido'"
    :back="manager ? '/coordinacion' : atencion ? '/leads' : '/asesor'"
  >
    <button type="button" class="btn bp" @click="formOpen = !formOpen">+ Nuevo pedido</button>
  </PageBar>

  <div class="cnt" :class="{ narrow: !manager }">
    <div v-if="manager" class="g4 kpis">
      <div class="card"><div class="lbl">Abiertos</div><div class="kn num">{{ k.abiertos }}</div></div>
      <div class="card"><div class="lbl">Próximos a vencer</div><div class="kn num">{{ k.proximos_a_vencer }}</div><div class="mut tiny">en los próximos 3 días</div></div>
      <div class="card" :class="{ 'tint-bad': k.vencidos_mes }"><div class="lbl">Vencidos este mes</div><div class="kn num">{{ k.vencidos_mes }}</div></div>
      <div class="card" :class="{ 'tint-bad': k.vencidos_sin_decidir }"><div class="lbl">Vencidos sin decidir</div><div class="kn num">{{ k.vencidos_sin_decidir }}</div><div class="mut tiny">extender fecha o marcar perdido</div></div>
    </div>

    <PedidoForm v-if="formOpen && opciones" :opciones="opciones" @created="onCreated" @cancel="formOpen = false" @actualizar="irAActualizar" />
    <div v-if="flash" class="note ok" role="status"><b>✓ {{ flash }}</b></div>

    <div class="sb bar2">
      <div class="tabs">
        <button v-for="[v, t] in TABS" :key="v" type="button" class="tab" :class="{ on: vista === v }" @click="vista = v">{{ t }}</button>
      </div>
      <div class="row filters">
        <button type="button" class="fch" :class="{ on: !filtros.negocio }" @click="filtros.negocio = ''">Todos</button>
        <button type="button" class="fch" :class="{ on: filtros.negocio === 'venta' }" @click="filtros.negocio = 'venta'">Venta</button>
        <button type="button" class="fch" :class="{ on: filtros.negocio === 'arriendo' }" @click="filtros.negocio = 'arriendo'">Arriendo</button>
        <select v-model="filtros.rango" class="fsel" aria-label="Presupuesto">
          <option value="">Todos los presupuestos</option>
          <option v-for="(t, key) in opciones?.rangos ?? {}" :key="key" :value="key">{{ t }}</option>
        </select>
        <select v-model="filtros.zona" class="fsel" aria-label="Zona">
          <option value="">Todas las zonas</option>
          <option v-for="z in opciones?.zonas ?? []" :key="z">{{ z }}</option>
        </select>
        <select v-if="manager" v-model="filtros.responsable_id" class="fsel" aria-label="Responsable">
          <option value="">Todos los responsables</option>
          <option v-for="r in opciones?.responsables ?? []" :key="r.id" :value="r.id">{{ r.full_name }}</option>
        </select>
        <button type="button" class="fch" :class="{ on: filtros.proximos }" @click="filtros.proximos = !filtros.proximos">Próximos a vencer</button>
        <input v-model="filtros.q" class="in q" type="search" placeholder="Cliente, teléfono o PED-…" aria-label="Buscar">
        <button v-if="hayFiltros" type="button" class="fch" @click="limpiar">✕ Quitar filtros</button>
      </div>
    </div>

    <!-- ============ Coordinación / Gerencia: K06 table ============ -->
    <div v-if="manager" class="card">
      <div class="wrap">
        <table class="tbl t-ped">
          <thead>
            <tr><th>Cliente</th><th>Negocio</th><th>Inmueble</th><th>Zona</th><th>Presupuesto</th><th>Observaciones</th><th>Pedido</th><th>Fecha límite</th><th>Responsable</th><th>Estado</th></tr>
          </thead>
          <tbody>
            <template v-for="p in data.items" :key="p.id">
              <tr class="row-click" :class="{ hl: p.estado_visible === 'nuevo', open: expanded === p.id }" @click="expanded = expanded === p.id ? null : p.id">
                <td><b>{{ p.cliente_nombre }}</b><br><span class="mut tiny">{{ p.code }}</span></td>
                <td>{{ NEGOCIO_LABELS[p.negocio] }}</td>
                <td>{{ TIPO_INMUEBLE_LABELS[p.tipo_inmueble] }}</td>
                <td>{{ p.zona }}</td>
                <td>{{ presupuestoTxt(p.presupuesto) }}</td>
                <td class="mut obs">{{ p.observaciones }}</td>
                <td>{{ fmtCuando(p.created_at).replace(/ \d+:\d+$/, '') }}</td>
                <td>{{ fmtCuando(p.fecha_limite) }}</td>
                <td>{{ p.responsable.full_name }}</td>
                <td><span class="chip" :class="PEDIDO_ESTADO[p.estado_visible]?.cls">{{ PEDIDO_ESTADO[p.estado_visible]?.t }}</span></td>
              </tr>
              <tr v-if="expanded === p.id || (p.vencido && vista === 'vencidos')" class="detail">
                <td colspan="10">
                  <PedidoActions
                    :pedido="p"
                    :opciones="opciones"
                    manager
                    :start-with="startWith?.code === p.code ? startWith.f : null"
                    @changed="onChanged"
                  />
                </td>
              </tr>
            </template>
            <tr v-if="!data.items.length"><td colspan="10" class="mut empty">{{ pending ? 'Cargando…' : 'No hay pedidos con estos filtros.' }}</td></tr>
          </tbody>
        </table>
      </div>
      <div class="mut tiny foot">Toca un pedido para actualizarlo, atenderlo, marcarlo perdido, reasignarlo o ver su historial.</div>
      <div v-if="vista === 'vencidos'" class="note foot">
        Un pedido vencido no se marca perdido solo: el responsable o Coordinación extiende la fecha o lo marca perdido con motivo.
        Los que ya tienen resultado se conservan aquí para Gerencia.
      </div>
    </div>

    <!-- ============ Asesor (M06) / Atención (C10): cards ============ -->
    <template v-else>
      <PedidoCard
        v-for="p in data.items"
        :key="p.id + p.estado + p.eventos.length"
        :pedido="p"
        :opciones="opciones"
        :start-with="startWith?.code === p.code ? startWith.f : null"
        @changed="onChanged"
      />
      <div v-if="!data.items.length" class="note">{{ pending ? 'Cargando…' : 'No hay pedidos con estos filtros.' }}</div>
      <div class="note">
        Si el cliente cambia lo que busca, actualiza su pedido; no crees otro. Cada cambio queda en el historial del pedido con lo de
        antes y lo de después. Un pedido atendido o perdido sale de tu lista y queda para Gerencia. En los pedidos de
        {{ atencion ? 'los asesores' : 'tu equipo' }} puedes proponer un inmueble o comentar al responsable; actualizar, atender o
        marcar perdido lo hace solo el responsable o Coordinación.
      </div>
    </template>
  </div>
</template>

<style scoped>
.narrow {
  max-width: 980px;
  width: 100%;
}
.tiny {
  font-size: 12px;
}
.bar2 {
  gap: 10px;
}
.filters {
  flex-wrap: wrap;
  gap: 6px;
}
.q {
  min-height: 32px;
  width: 200px;
  font-size: 12.5px;
  border-radius: var(--radius-pill);
}
.t-ped {
  min-width: 1080px;
}
.row-click {
  cursor: pointer;
}
.row-click:hover td,
.row-click.open td {
  background: var(--cdc-bg);
}
.row-click.hl td {
  background: #f0f8ee;
}
.obs {
  max-width: 220px;
}
.detail td {
  background: #fafbf9;
  padding: 10px 12px 14px;
}
.empty {
  text-align: center;
  padding: 24px 10px;
}
.foot {
  margin-top: 8px;
}
@media (max-width: 760px) {
  .kpis {
    grid-template-columns: 1fr 1fr;
  }
  .q {
    width: 100%;
  }
}
</style>
