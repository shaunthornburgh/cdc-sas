<script setup lang="ts">
import type { FilaEquipo, Perfil } from '~/types/rendimiento'

/**
 * K18 «Mi equipo» (Coordinación: asesores and Atención y Preventa) ·
 * «Rendimiento por empleado» (Gerencia and the Auxiliar: also the Coordinador).
 */
definePageMeta({ cargos: ['coordinacion', 'gerencia', 'auxiliar_administrativa'] })

const auth = useAuth()
const rend = useRendimiento()
const coord = computed(() => auth.user.value?.cargo === 'coordinacion')
const titulo = computed(() => (coord.value ? 'Mi equipo' : 'Rendimiento por empleado'))
useHead(() => ({ title: `${titulo.value} · Casa Dolce Casa` }))

const meses = ultimosMeses()
const periodo = ref(meses[0]!.key)
const { data, error } = await useAsyncData('rend-equipo', () => rend.equipo(periodo.value), { watch: [periodo] })

const persona = ref('todos')
const cargo = ref<'todos' | Perfil>('todos')
const sel = ref<string | null>(null)
const n = ref(8)
const CARGOS = computed<[string, string][]>(() => [
  ['todos', 'Todos'],
  ['asesor', 'Asesores'],
  ['atencion', 'Atención y Preventa'],
  ...(coord.value ? [] : ([['coordinacion', 'Coordinación']] as [string, string][])),
])
const todos = computed(() => data.value?.personas ?? [])
const vis = computed(() =>
  todos.value
    .filter((p) => (persona.value === 'todos' || p.id === persona.value) && (cargo.value === 'todos' || p.perfil === cargo.value))
    .sort((a, b) => (b.total ?? -1) - (a.total ?? -1)),
)
const sp = computed(() => vis.value.find((p) => p.id === sel.value) ?? null)

const sum = (f: (p: FilaEquipo) => number | null) => vis.value.reduce((s, p) => s + (f(p) ?? 0), 0)
const prom = (L: FilaEquipo[]) => {
  const xs = L.map((p) => p.total).filter((x): x is number => x != null)
  return xs.length ? Math.round(xs.reduce((a, b) => a + b, 0) / xs.length) : null
}
const pct = (v: number | null) => (v == null ? '—' : `${v}%`)
const grupo = computed<Perfil | null>(() => {
  const gs = new Set(vis.value.map((p) => p.perfil))
  return gs.size === 1 ? [...gs][0]! : null
})
const conv = () => {
  const l = sum((p) => p.leads)
  return l ? `${dec(Math.round((1000 * sum((p) => p.citas)) / l) / 10)}%` : '—'
}
const kpis = computed(() => {
  const L = vis.value
  const base = [
    { t: `Rendimiento${L.length > 1 ? ' promedio' : ''}`, v: pct(prom(L)), d: `${L.length} persona${L.length === 1 ? '' : 's'}` },
    { t: 'Metas cumplidas', v: `${sum((p) => p.metas_cumplidas)} de ${sum((p) => p.metas_total)}`, d: 'áreas al 100 %' },
  ]
  const mes = data.value?.periodo.label.split(' ')[0] ?? ''
  if (grupo.value === 'atencion')
    return [...base,
      { t: 'Leads seguidos', v: String(sum((p) => p.leads)), d: mes },
      { t: 'Citas programadas', v: String(sum((p) => p.citas)), d: 'desde leads' },
      { t: 'Conversión lead → cita', v: conv(), d: 'meta 40 % (ejemplo)' },
      { t: 'Leads ganados · perdidos', v: `${sum((p) => p.ganados)} · ${sum((p) => p.perdidos)}`, d: mes }]
  if (grupo.value === 'asesor')
    return [...base,
      { t: 'Ventas cerradas', v: String(sum((p) => p.ventas)), d: mes },
      { t: 'Arriendos cerrados', v: String(sum((p) => p.arriendos)), d: mes },
      { t: 'Captaciones aprobadas', v: String(sum((p) => p.captaciones)), d: mes },
      { t: 'Clientes perdidos', v: String(sum((p) => p.perdidos)), d: mes }]
  if (grupo.value === 'coordinacion')
    return [...base, ...(L[0]?.areas ?? []).map((a) => ({ t: a.titulo, v: pct(a.cumplimiento), d: a.logrado_txt || 'sin datos' }))]
  const g = (k: Perfil) => prom(todos.value.filter((p) => p.perfil === k))
  return [...base,
    { t: 'Asesores', v: pct(g('asesor')), d: 'ventas, arriendos y captación' },
    { t: 'Atención y Preventa', v: pct(g('atencion')), d: 'leads, citas y conversión' },
    ...(coord.value
      ? [{ t: 'Ventas · arriendos', v: `${sum((p) => p.ventas)} · ${sum((p) => p.arriendos)}`, d: mes },
         { t: 'Leads seguidos', v: String(sum((p) => p.leads)), d: 'Atención y Preventa' }]
      : [{ t: 'Coordinación', v: pct(g('coordinacion')), d: 'equipo y obligaciones' },
         { t: 'Administrativa', v: '—', d: 'sin datos todavía' }])]
})
const na = (x: number | null) => (x == null ? 'no aplica' : String(x))
const res = (p: FilaEquipo): [string, string][] =>
  p.perfil === 'atencion'
    ? [['Leads seguidos', na(p.leads)], ['Citas programadas', na(p.citas)], ['Conversión lead → cita', p.conversion == null ? '—' : `${dec(p.conversion)}%`], ['Leads ganados · perdidos', `${p.ganados ?? 0} · ${p.perdidos}`]]
    : p.perfil === 'coordinacion'
      ? p.areas.map((a) => [a.titulo, a.cumplimiento == null ? 'sin datos' : `${a.cumplimiento}%`] as [string, string])
      : [['Ventas', na(p.ventas)], ['Arriendos', na(p.arriendos)], ['Captaciones aprobadas', na(p.captaciones)], ['Clientes perdidos', String(p.perdidos)]]
const hd = computed(() => (grupo.value && vis.value[0] ? res(vis.value[0]).map((x) => x[0]) : ['Resultados según el cargo']))
const semChip = (v: number | null) => {
  const s = semDe(v)
  return s ? { cls: SEM[s].cls, t: `${SEM[s].sym} ${v}%` } : { cls: 'gray', t: 'Sin datos' }
}
const descargando = ref(false)
async function descargar() {
  descargando.value = true
  try {
    await rend.descargar(periodo.value)
  } finally {
    descargando.value = false
  }
}
</script>

<template>
  <PageBar
    :title="titulo"
    :subtitle="coord ? 'Cómo va cada persona a tu cargo · asesores y Atención y Preventa' : 'Cómo va cada persona de la empresa · filtra por nombre o por cargo'"
    :back="auth.user.value?.cargo === 'auxiliar_administrativa' ? '/' : '/coordinacion'"
  >
    <button type="button" class="btn bs" :disabled="descargando" @click="descargar">Descargar (Excel)</button>
  </PageBar>

  <div class="cnt">
    <div v-if="error" class="note bad"><b>No se pudo cargar.</b> {{ apiErrorMessage(error) }}</div>
    <template v-else-if="data">
      <div class="card filters">
        <div class="fld">
          <label for="eq-p">Empleado</label>
          <select id="eq-p" v-model="persona" class="sel">
            <option value="todos">Todos</option>
            <option v-for="p in todos" :key="p.id" :value="p.id">{{ p.full_name }}</option>
          </select>
        </div>
        <div class="row fw gap6">
          <button v-for="[k, t] in CARGOS" :key="k" type="button" class="fch" :class="{ on: cargo === k }" @click="cargo = k as never">{{ t }}</button>
        </div>
        <div class="fld">
          <label for="eq-m">Mes</label>
          <select id="eq-m" v-model="periodo" class="sel">
            <option v-for="m in meses" :key="m.key" :value="m.key">{{ m.t }}</option>
          </select>
        </div>
        <span class="mut tiny">{{ coord ? `${todos.filter((p) => p.perfil === 'asesor').length} asesores y ${todos.filter((p) => p.perfil === 'atencion').length} de Atención y Preventa` : `toda la empresa · ${todos.length} personas` }}</span>
      </div>

      <div class="g6">
        <div v-for="k in kpis" :key="k.t" class="card">
          <div class="lbl">{{ k.t }}</div>
          <div class="kn num">{{ k.v }}</div>
          <div class="mut tiny">{{ k.d }}</div>
        </div>
      </div>

      <div class="card">
        <div class="wrap-x">
          <table class="tbl t-eq">
            <thead>
              <tr><th>Persona</th><th>Rendimiento</th><th>Metas cumplidas</th><th v-for="h in hd" :key="h" :colspan="grupo ? 1 : 4">{{ h }}</th><th /></tr>
            </thead>
            <tbody>
              <tr v-for="p in vis.slice(0, n)" :key="p.id" :class="{ open: sel === p.id }">
                <td><b>{{ p.full_name }}</b><br><span class="mut tiny">{{ p.cargo_txt }}</span></td>
                <td><span class="chip" :class="semChip(p.total).cls">{{ semChip(p.total).t }}</span></td>
                <td class="num">{{ p.metas_cumplidas }} de {{ p.metas_total }}</td>
                <td v-for="[l, v] in res(p).slice(0, 4)" :key="l">
                  <span v-if="!grupo" class="mut tiny">{{ l }}</span><br v-if="!grupo">
                  <b class="num">{{ v }}</b>
                </td>
                <td v-for="i in Math.max(0, 4 - res(p).length)" :key="`e${i}`" />
                <td><button type="button" class="btn bs sm" @click="sel = sel === p.id ? null : p.id">{{ sel === p.id ? 'Cerrar' : 'Ver detalle' }}</button></td>
              </tr>
              <tr v-if="!vis.length"><td colspan="8" class="mut empty">No hay personas con este filtro.</td></tr>
            </tbody>
          </table>
        </div>
        <div class="sb foot">
          <span class="mut tiny">Mostrando {{ Math.min(n, vis.length) }} de {{ vis.length }}</span>
          <button v-if="vis.length > n" type="button" class="btn bs sm" @click="n += 8">Ver más</button>
        </div>
      </div>

      <div v-if="sp" class="card stack">
        <div class="sb">
          <div>
            <div class="lbl">Detalle · {{ data.periodo.label.split(' ')[0] }}</div>
            <b>{{ sp.full_name }}</b> <span class="mut small">· {{ sp.cargo_txt }}</span>
          </div>
          <div class="row gap6">
            <span class="chip" :class="semChip(sp.total).cls">{{ semChip(sp.total).t }}</span>
            <NuxtLink class="btn bp sm" :to="`/resultados/${sp.id}?periodo=${periodo}`">{{ sp.perfil === 'coordinacion' ? 'Calificar y ver detalle completo ›' : 'Ver detalle completo ›' }}</NuxtLink>
            <button type="button" class="btn bs sm" @click="sel = null">Cerrar</button>
          </div>
        </div>
        <div class="lbl">Áreas: meta y cumplimiento</div>
        <div v-for="a in sp.areas" :key="a.titulo" class="sb it row-it">
          <div><b class="small">{{ a.titulo }}</b><div class="mut tiny">{{ a.logrado_txt || 'Sin datos todavía' }}</div></div>
          <div class="row gap6">
            <b class="num">{{ pct(a.cumplimiento) }}</b>
            <span v-if="a.cumplimiento != null" class="chip" :class="a.cumplimiento >= 100 ? 'ok' : 'gray'">{{ a.cumplimiento >= 100 ? '✓ Cumplió' : 'No cumplió' }}</span>
          </div>
        </div>
        <div v-if="sp.descuentos" class="sb"><span class="small">Descuentos del mes</span><span class="chip bad">−{{ dec(sp.descuentos) }}</span></div>
      </div>

      <div class="note">
        {{ coord ? 'Ves a los asesores y a Atención y Preventa.' : 'Ves a todas las personas con rendimiento. Para calificar o ver el detalle completo, abre el detalle de cada una.' }}
        Las cifras salen solas de lo que registra cada persona; no se editan aquí. Una meta se da por cumplida cuando el área
        llega al 100 %. La Auxiliar administrativa y Gerencia todavía no tienen indicadores propios: PENDIENTE DE CONFIGURACIÓN.
      </div>
    </template>
  </div>
</template>

<style scoped>
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
}
.filters .fld {
  min-width: 200px;
}
.gap6 {
  gap: 6px;
}
.fw {
  flex-wrap: wrap;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.t-eq {
  min-width: 900px;
}
.wrap-x {
  overflow-x: auto;
}
tr.open td {
  background: var(--cdc-bg);
}
.empty {
  text-align: center;
  padding: 24px 10px;
}
.foot {
  margin-top: 8px;
}
</style>
