<script setup lang="ts">
import type { DsAlcance, DsGrupo, DsOpciones, DsQuery, DsVistaPrevia } from '~/types/descargas'

/**
 * X10 «Descargas del personal» (Auxiliar administrativa, Gerencia, Coordinación): preoperacionales,
 * asistencia, ausencias, pausas activas and capacitaciones as CSV files Excel opens, for everyone,
 * one cargo or one person.
 */
definePageMeta({ cargos: ['auxiliar_administrativa', 'gerencia', 'coordinacion'] })
useHead({ title: 'Descargas del personal · Casa Dolce Casa' })

const api = useDescargas()
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const home = computed(() => (auth.user.value?.cargo === 'auxiliar_administrativa' ? '/' : '/coordinacion'))
const hoy = localDate(0)

const { data, refresh } = await useAsyncData('descargas', () => api.opciones())
const O = computed(() => data.value as DsOpciones | null)

const tab = ref(String(route.query.tab ?? 'pre'))
watch(tab, (t) => router.replace({ query: t === 'pre' ? {} : { tab: t } }))
const T = computed(() => O.value?.tipos.find((t) => t.key === tab.value) ?? O.value?.tipos[0])

const f = reactive({ alcance: 'tod' as DsAlcance, grupo: '' as DsGrupo | '', user: '', desde: `${hoy.slice(0, 8)}01`, hasta: hoy, formato: 'csv' })
const grupos = computed(() => (T.value?.grupos ?? []).map((g) => [g, O.value?.grupos[g] ?? g] as const))
const personas = computed(() => (O.value?.personas ?? []).filter((p) => T.value?.grupos.includes(p.grupo)))
// Keep the selection valid when the tab changes
watch(
  [T, O],
  () => {
    if (!grupos.value.some(([g]) => g === f.grupo)) f.grupo = grupos.value[0]?.[0] ?? ''
    if (!personas.value.some((p) => p.id === f.user)) f.user = personas.value[0]?.id ?? ''
  },
  { immediate: true },
)
const fErr = computed(() => (!f.desde || !f.hasta || f.desde > f.hasta ? 'Revisa las fechas: «Desde» debe ser anterior o igual a «Hasta».' : ''))
const query = computed<DsQuery>(() => ({
  desde: f.desde,
  hasta: f.hasta,
  alcance: f.alcance,
  ...(f.alcance === 'car' ? { grupo: f.grupo } : {}),
  ...(f.alcance === 'emp' ? { user_id: f.user } : {}),
}))

// «Se descargará: …» with the real number of rows
const prev = ref<DsVistaPrevia | null>(null)
const err = ref('')
const ok = ref('')
let seq = 0
watch(
  [query, () => T.value?.key],
  async () => {
    prev.value = null
    err.value = ''
    if (!T.value?.disponible || !T.value.grupos.length || fErr.value) return
    const n = ++seq
    try {
      const p = await api.vistaPrevia(T.value.key, query.value)
      if (n === seq) prev.value = p
    } catch (e) {
      if (n === seq) err.value = apiErrorMessage(e)
    }
  },
  { immediate: true },
)

const busy = ref(false)
async function descargar() {
  ok.value = ''
  if (fErr.value) return (err.value = fErr.value)
  if (!T.value || !prev.value) return
  busy.value = true
  try {
    await api.descargar(T.value.key, query.value, prev.value.archivo)
    ok.value = `Se descargó ${prev.value.archivo} (${prev.value.filas} filas). Queda en el registro de cambios.`
    await refresh()
  } catch (e) {
    err.value = apiErrorMessage(e)
  } finally {
    busy.value = false
  }
}
const pickTab = (k: string) => {
  tab.value = k
  ok.value = ''
}
const ALCANCES: [DsAlcance, string][] = [
  ['tod', 'Todo el personal (grupal)'],
  ['car', 'Por cargo'],
  ['emp', 'Por empleado'],
]
</script>

<template>
  <PageBar title="Descargas del personal" subtitle="Preoperacionales, asistencia, ausencias, pausas activas y capacitaciones de todos · por fecha y por empleado, cargo o grupal" :back="home" />

  <div v-if="O && T" class="cnt">
    <div class="tabs self-start">
      <button v-for="t in O.tipos" :key="t.key" type="button" class="tab" :class="{ on: tab === t.key }" @click="pickTab(t.key)">
        {{ t.titulo }}<span v-if="!t.disponible" class="pend-dot"> · pendiente</span>
      </button>
    </div>

    <div class="card focus col14">
      <div>
        <div class="lbl">Descargar {{ T.titulo.toLowerCase() }}</div>
        <div class="mut small">Elige si es de una persona, de un cargo o de todo el personal, y entre qué fechas.</div>
      </div>

      <template v-if="T.disponible && !T.grupos.length">
        <div class="note"><b>El archivo trae:</b> {{ T.contenido }}</div>
        <div class="note warn"><b>La descarga de {{ T.titulo.toLowerCase() }} es de la Auxiliar administrativa y Gerencia.</b></div>
      </template>
      <template v-else-if="T.disponible">
        <div class="row fw gp6">
          <button v-for="[k, t] in ALCANCES" :key="k" type="button" class="fch" :class="{ on: f.alcance === k }" @click="f.alcance = k">{{ t }}</button>
        </div>
        <div class="grid">
          <div v-if="f.alcance === 'emp'" class="fld">
            <label for="d-emp">Empleado <span class="req">*</span></label>
            <select id="d-emp" v-model="f.user" class="in">
              <option v-for="p in personas" :key="p.id" :value="p.id">{{ p.full_name }} · {{ O.grupos[p.grupo] }}</option>
            </select>
          </div>
          <div v-if="f.alcance === 'car'" class="fld">
            <label for="d-car">Cargo <span class="req">*</span></label>
            <select id="d-car" v-model="f.grupo" class="in">
              <option v-for="[g, t] in grupos" :key="g" :value="g">{{ t }}</option>
            </select>
          </div>
          <div class="fld"><label for="d-d1">Desde <span class="req">*</span></label><input id="d-d1" v-model="f.desde" class="in" type="date"></div>
          <div class="fld"><label for="d-d2">Hasta <span class="req">*</span></label><input id="d-d2" v-model="f.hasta" class="in" type="date"></div>
          <div class="fld">
            <label for="d-fmt">Formato</label>
            <select id="d-fmt" v-model="f.formato" class="in">
              <option value="csv">Excel (CSV)</option>
              <option value="pdf" disabled>PDF (con resumen) · pendiente</option>
            </select>
          </div>
        </div>
        <div class="note"><b>El archivo trae:</b> {{ T.contenido }}</div>
        <span v-if="prev" class="mut small">Se descargará: {{ prev.texto }} · {{ prev.filas }} fila{{ prev.filas === 1 ? '' : 's' }} · {{ prev.archivo }}</span>
        <div v-if="fErr || err" class="note bad"><b>{{ fErr || err }}</b></div>
        <div v-if="ok" class="note ok" role="status"><b>{{ ok }}</b></div>
        <div><button type="button" class="btn bp" :disabled="busy || !prev || !!fErr" @click="descargar">Descargar</button></div>
      </template>
      <template v-else>
        <div class="note"><b>El archivo trae:</b> {{ T.contenido }}</div>
        <div class="note warn"><b>«{{ T.titulo }}» todavía no existe en el software:</b> no hay datos que descargar. Se habilita cuando se construya ese módulo.</div>
      </template>
    </div>

    <div class="card">
      <div class="sb mb6"><span class="lbl">Descargas recientes</span><span class="mut tiny">cada descarga queda en el registro de cambios</span></div>
      <div v-for="(h, i) in O.recientes" :key="i" class="sb hrow">
        <span><b>{{ h.archivo }}</b><br><span class="mut tiny">{{ h.texto }} · {{ h.filas }} · {{ fmtCuando(h.at) }}</span></span>
        <span class="chip ok">Excel</span>
      </div>
      <div v-if="!O.recientes.length" class="note">Todavía no has descargado nada.</div>
    </div>

    <div class="note">
      El archivo se descarga a tu equipo en CSV, que se abre en Excel. Los datos son los mismos que ven Coordinación y Gerencia en cada módulo; aquí solo se consultan y descargan.
      Coordinación descarga a su equipo.
    </div>
  </div>
</template>

<style scoped>
.self-start {
  align-self: flex-start;
}
.col14 {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.fw {
  flex-wrap: wrap;
}
.gp6 {
  gap: 6px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}
.small {
  font-size: 12.5px;
}
.tiny {
  font-size: 12px;
}
.mb6 {
  margin-bottom: 6px;
}
.hrow {
  font-size: 13px;
  padding: 8px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  gap: 10px;
}
.pend-dot {
  font-weight: 600;
  font-size: 11.5px;
  color: var(--cdc-muted);
}
</style>
