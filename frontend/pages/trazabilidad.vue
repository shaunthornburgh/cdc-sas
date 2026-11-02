<script setup lang="ts">
import type { RcFila, RcOpciones } from '~/types/trazabilidad'

/**
 * G06 «Registro de cambios» (antes «Trazabilidad»): quién hizo qué, cuándo, y cómo estaba antes y
 * después. Reads the histories every module already keeps; nothing here can be edited or deleted.
 * Gerencia sees everything; Coordinación the operation of its team (G06-coord).
 */
definePageMeta({ cargos: ['gerencia', 'coordinacion'] })
useHead({ title: 'Registro de cambios · Casa Dolce Casa' })

const api = useTrazabilidad()
const { data: opc } = await useAsyncData('rc-opciones', () => api.opciones())
const O = computed(() => opc.value as RcOpciones)

const f = reactive({ modulo: '', usuario_id: '', q: '' })
const rg = reactive({ desde: O.value?.desde ?? localDate(-6), hasta: O.value?.hasta ?? localDate(0) })
const rgErr = computed(() => !rg.desde || !rg.hasta || rg.desde > rg.hasta)
const qDebounced = ref('')
let t: ReturnType<typeof setTimeout> | undefined
watch(
  () => f.q,
  (v) => {
    clearTimeout(t)
    t = setTimeout(() => (qDebounced.value = v.trim()), 300)
  },
)
const query = computed(() => ({
  ...(rgErr.value ? { desde: O.value?.desde, hasta: O.value?.hasta } : { desde: rg.desde, hasta: rg.hasta }),
  modulo: f.modulo || undefined,
  usuario_id: f.usuario_id || undefined,
  q: qDebounced.value || undefined,
}))

const PAGE = 50
const filas = ref<RcFila[]>([])
const total = ref(0)
const cargando = ref(false)
const err = ref('')
async function cargar(mas = false) {
  cargando.value = true
  err.value = ''
  try {
    const r = await api.list({ ...query.value, offset: mas ? filas.value.length : 0, limit: PAGE })
    filas.value = mas ? [...filas.value, ...r.items] : r.items
    total.value = r.total
  } catch (e) {
    err.value = apiErrorMessage(e)
  } finally {
    cargando.value = false
  }
}
await cargar()
watch(query, () => cargar())

const msg = ref('')
async function descargar() {
  try {
    await api.descargar(query.value)
    msg.value = `Archivo descargado con los filtros actuales (${total.value} registro${total.value === 1 ? '' : 's'}). La descarga queda en el registro de cambios.`
  } catch (e) {
    err.value = apiErrorMessage(e)
  }
}
const fecha = (iso: string) => diaMes(iso)
const rangoT = computed(() => (query.value.desde && query.value.hasta ? `${fmtFecha(query.value.desde)} al ${fmtFecha(query.value.hasta)}` : ''))
</script>

<template>
  <PageBar title="Registro de cambios" subtitle="Quién hizo qué, cuándo, y cómo estaba antes y después · no se puede borrar ni modificar" back="/coordinacion">
    <NuxtLink class="btn bs" to="/configuracion">‹ Configuración</NuxtLink>
    <button type="button" class="btn bs" @click="descargar">Descargar (Excel)</button>
  </PageBar>

  <div class="cnt">
    <div v-if="rgErr" class="note bad"><b>La fecha «Desde» no puede ser posterior a «Hasta». Se muestran los últimos 7 días mientras lo corriges.</b></div>
    <div v-if="msg" class="note ok"><b>{{ msg }}</b></div>
    <div v-if="err" class="note bad"><b>{{ err }}</b></div>

    <div class="card col">
      <div class="row fw gp6">
        <button type="button" class="fch" :class="{ on: !f.modulo }" @click="f.modulo = ''">Todos</button>
        <button v-for="m in O?.modulos ?? []" :key="m" type="button" class="fch" :class="{ on: f.modulo === m }" @click="f.modulo = m">{{ m }}</button>
      </div>
      <div class="row fw gp8">
        <select v-model="f.usuario_id" class="sel" aria-label="Usuario">
          <option value="">Todos los usuarios</option>
          <option v-for="u in O?.usuarios ?? []" :key="u.id" :value="u.id">{{ u.full_name }}</option>
        </select>
        <div class="row fw gp8">
          <label class="row gp6 flt">Desde<input v-model="rg.desde" class="in dt" type="date" aria-label="Fecha desde"></label>
          <label class="row gp6 flt">Hasta<input v-model="rg.hasta" class="in dt" type="date" aria-label="Fecha hasta"></label>
        </div>
        <input v-model="f.q" class="in buscar" placeholder="Buscar por código (LD-, CIT-, NEG-…) o nombre" aria-label="Buscar">
      </div>
    </div>
    <div v-if="O?.alcance" class="note">{{ O.alcance }}</div>

    <div class="card">
      <div class="sb mb8"><span class="lbl">{{ rangoT }} · {{ total }} registro{{ total === 1 ? '' : 's' }}</span><span class="mut tiny">los más recientes primero</span></div>
      <div class="wrap">
        <div class="min1040">
          <div class="gt hd"><span>Fecha</span><span>Hora</span><span>Usuario</span><span>Módulo</span><span>Acción</span><span>Registro</span><span>Antes</span><span>Después</span></div>
          <div v-for="r in filas" :key="r.id" class="gt rw">
            <span>{{ fecha(r.at) }}</span>
            <span class="num">{{ fmtHora(r.at) }}</span>
            <b>{{ r.actor ?? 'Sistema' }}</b>
            <span><span class="chip gray">{{ r.modulo }}</span></span>
            <span>{{ r.accion }}</span>
            <b><NuxtLink v-if="r.link && r.registro" :to="r.link" class="reg">{{ r.registro }}</NuxtLink><template v-else>{{ r.registro ?? '—' }}</template></b>
            <span class="mut">{{ r.antes ?? '—' }}</span>
            <span>{{ r.despues ?? '—' }}</span>
          </div>
        </div>
      </div>
      <div v-if="!filas.length && !cargando" class="note mt10">No hay registros con este filtro.</div>
      <div class="sb mt10 small">
        <span class="mut">Mostrando {{ filas.length }} de {{ total }}</span>
        <button v-if="filas.length < total" type="button" class="btn bs sm" :disabled="cargando" @click="cargar(true)">{{ cargando ? 'Cargando…' : 'Ver más' }}</button>
      </div>
      <div class="mut tiny mt10">Tiempo que se guardan estos registros: PENDIENTE DE CONFIGURACIÓN.</div>
    </div>
  </div>
</template>

<style scoped>
.col {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.fw {
  flex-wrap: wrap;
}
.gp6 {
  gap: 6px;
}
.gp8 {
  gap: 8px;
  align-items: center;
}
.flt {
  font-size: 13px;
  font-weight: 700;
}
.dt {
  min-height: 38px;
  width: auto;
}
.buscar {
  max-width: 300px;
}
.mb8 {
  margin-bottom: 8px;
}
.mt10 {
  margin-top: 10px;
}
.small {
  font-size: 12.5px;
}
.tiny {
  font-size: 12px;
}
.wrap {
  overflow-x: auto;
}
.min1040 {
  min-width: 1040px;
}
.gt {
  display: grid;
  grid-template-columns: 80px 60px 130px 120px minmax(0, 1.3fr) 130px minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
  padding: 9px 6px;
  border-bottom: 1px solid var(--cdc-border-soft);
  font-size: 12.5px;
  align-items: center;
  overflow-wrap: anywhere;
}
.hd {
  padding: 8px 6px;
  border-bottom: 1px solid var(--cdc-border);
  font-size: 10.5px;
  color: var(--cdc-muted);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.reg {
  color: var(--cdc-text);
}
</style>
