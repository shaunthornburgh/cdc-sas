<script setup lang="ts">
import type { IntDetalle, IntTablero } from '~/types/integraciones'

/**
 * G07 «Integraciones» (solo Gerencia): results of each platform (leads, costs, cost per lead,
 * closed deals) and the data to connect it. There are no real connectors yet: saving the data
 * leaves the integration «Por confirmar conexión», and «Probar conexión» says so.
 */
definePageMeta({ cargos: ['gerencia'] })
useHead({ title: 'Integraciones · Casa Dolce Casa' })

const api = useIntegraciones()
const rg = reactive({ desde: localDate(-89), hasta: localDate(0) })
const rgErr = computed(() => !rg.desde || !rg.hasta || rg.desde > rg.hasta)
const rango = computed(() => (rgErr.value ? { desde: localDate(-89), hasta: localDate(0) } : { ...rg }))
const { data, refresh } = await useAsyncData('integraciones', () => api.tablero(rango.value), { watch: [rango] })
const T = computed(() => data.value as IntTablero)
const sel = ref<string | null>(T.value?.grupos[1]?.items[0]?.id ?? T.value?.grupos[0]?.items[0]?.id ?? null)
const { data: det, refresh: refreshDet } = await useAsyncData(
  'integracion',
  () => (sel.value ? api.detalle(sel.value, rango.value) : Promise.resolve(null)),
  { watch: [sel, rango] },
)
const D = computed(() => det.value as IntDetalle | null)
const tab = ref<'res' | 'con'>('res')
const msg = ref<{ t: string; ok: boolean } | null>(null)
const say = (t: string, ok = true) => (msg.value = { t, ok })
function elegir(id: string) {
  sel.value = id
  msg.value = null
}
const pct = (v: number | null) => (v === null ? '—' : `${String(v).replace('.', ',')}%`)

// ---- connection form
const vals = reactive<Record<string, string>>({})
const aj = reactive({ como: '', costo: '' })
watch(
  D,
  (d) => {
    if (!d) return
    for (const k of Object.keys(vals)) delete vals[k]
    for (const c of d.conexion.campos) vals[c.key] = c.secreto ? '' : (c.valor ?? '')
    aj.como = d.conexion.como
    aj.costo = d.conexion.costo_mensual == null ? '' : String(d.conexion.costo_mensual)
  },
  { immediate: true },
)
async function run(fn: () => Promise<unknown>, t: string) {
  try {
    await fn()
    say(t)
    await Promise.all([refresh(), refreshDet()])
  } catch (e) {
    say(apiErrorMessage(e), false)
  }
}
const guardar = () =>
  run(
    () => api.guardar(D.value!.id, { ...vals }),
    `${D.value!.nombre}: datos guardados. Queda «Por confirmar conexión» hasta que exista el conector. Quedó en el registro de cambios.`,
  )
async function probar() {
  try {
    const r = await api.probar(D.value!.id)
    say(r.txt, r.ok)
    await refreshDet()
  } catch (e) {
    say(apiErrorMessage(e), false)
  }
}
const conf = ref(false)
const desconectar = () => {
  conf.value = false
  return run(() => api.desconectar(D.value!.id), `${D.value!.nombre} desconectado. Los datos de conexión se borraron; lo que ya había llegado se conserva.`)
}
const guardarAjustes = () =>
  run(
    () => api.ajustes(D.value!.id, { como: aj.como, costo_mensual: aj.costo === '' ? null : Number(aj.costo) }),
    'Ajustes guardados. Quedaron en el registro de cambios.',
  )
async function avisar(v: boolean) {
  await run(() => api.ajustes(D.value!.id, { avisar_falla: v }), v ? 'Gerencia recibirá el aviso si la conexión falla.' : 'Ya no se avisará si la conexión falla.')
}
const aviso = computed({ get: () => !!D.value?.conexion.avisar_falla, set: (v: boolean) => avisar(v) })

// ---- add
const N = reactive({ on: false, nombre: '', grupo: 'trad', como: 'por_confirmar', usuario: '', costo: '', err: '' })
async function agregar() {
  N.err = ''
  try {
    const d = await api.agregar({ nombre: N.nombre, grupo: N.grupo, como: N.como, usuario: N.usuario || null, costo_mensual: N.costo === '' ? null : Number(N.costo) })
    say(`${d.nombre} agregada a «${T.value.grupos_txt[N.grupo]}». Completa los datos de conexión. Quedó en el registro de cambios.`)
    Object.assign(N, { on: false, nombre: '', usuario: '', costo: '' })
    await refresh()
    sel.value = d.id
    tab.value = 'con'
  } catch (e) {
    N.err = apiErrorMessage(e)
  }
}
</script>

<template>
  <PageBar title="Integraciones" subtitle="Resultados de cada plataforma (leads, costos, costo por lead y cierres) y los datos para conectarla" back="/coordinacion">
    <div class="row fw gp8">
      <label class="row gp6 flt">Desde<input v-model="rg.desde" class="in dt" type="date" aria-label="Fecha desde"></label>
      <label class="row gp6 flt">Hasta<input v-model="rg.hasta" class="in dt" type="date" aria-label="Fecha hasta"></label>
    </div>
  </PageBar>

  <div v-if="T" class="cnt">
    <div v-if="rgErr" class="note bad"><b>La fecha «Desde» no puede ser posterior a «Hasta». Se muestran los últimos tres meses mientras lo corriges.</b></div>

    <div class="g4">
      <div class="card"><div class="lbl">Leads generados</div><div class="kn num">{{ T.kpis.leads }}</div><div class="mut tiny">por todas las plataformas</div></div>
      <div class="card"><div class="lbl">Costos pagados</div><div class="kn num">{{ fmtCOP(T.kpis.costos) }}</div><div class="mut tiny">todas las plataformas</div></div>
      <div class="card"><div class="lbl">Costo promedio por lead</div><div class="kn num">{{ fmtCOP(T.kpis.costo_lead) }}</div></div>
      <div class="card dark"><div class="lbl">Leads cerrados</div><div class="kn num">{{ T.kpis.cerrados }}</div><div class="tiny">{{ pct(T.kpis.conversion) }} de los leads</div></div>
    </div>

    <div class="split">
      <div class="col12">
        <button type="button" class="btn bp self-start" @click="N.on = !N.on">{{ N.on ? 'Cancelar' : '+ Agregar integración' }}</button>
        <div v-if="N.on" class="card col10 focus">
          <b class="t16">Nueva integración</b>
          <div class="fld"><label for="n-nom">Nombre de la plataforma <span class="req">*</span></label><input id="n-nom" v-model="N.nombre" class="in" placeholder="Ej.: YouTube, Mercado Libre Inmuebles"></div>
          <div class="fld">
            <span class="fld-label">Grupo <span class="req">*</span></span>
            <div class="row fw"><button v-for="(t, k) in T.grupos_txt" :key="k" type="button" class="opt" :class="{ on: N.grupo === k }" @click="N.grupo = String(k)">{{ t }}</button></div>
          </div>
          <div class="fld">
            <label for="n-como">Cómo llegan los datos</label>
            <select id="n-como" v-model="N.como" class="in"><option v-for="(t, k) in T.como" :key="k" :value="k">{{ t }}</option></select>
          </div>
          <div class="g2">
            <div class="fld"><label for="n-us">Usuario o código de cliente</label><input id="n-us" v-model="N.usuario" class="in" placeholder="Lo da la plataforma"></div>
            <div class="fld"><label for="n-co">Costo mensual</label><input id="n-co" v-model="N.costo" class="in" inputmode="numeric" placeholder="$"></div>
          </div>
          <div v-if="N.err" class="note bad"><b>{{ N.err }}</b></div>
          <div class="row"><button type="button" class="btn bp" @click="agregar">Agregar</button><button type="button" class="btn bs" @click="N.on = false">Cancelar</button></div>
          <div class="mut tiny">
            Queda «Por confirmar conexión» hasta probarla. Sus leads se cuentan cuando existan como fuente de leads (hoy: los portales de Plataformas tradicionales y las redes de la lista).
          </div>
        </div>
        <div v-for="g in T.grupos" :key="g.grupo" class="card col4">
          <div class="lbl mb4">{{ g.titulo }}</div>
          <button v-for="i in g.items" :key="i.id" type="button" class="pick" :class="{ on: i.id === sel }" @click="elegir(i.id)">
            <span><b>{{ i.nombre }}</b><br><span class="tiny">{{ i.res }}</span></span>
            <span class="chip" :class="i.estado_cls">{{ i.estado_txt }}</span>
          </button>
        </div>
      </div>

      <div v-if="D" class="card col12">
        <div class="sb"><b class="t18">{{ D.nombre }}</b><span class="chip big" :class="D.estado_cls">{{ D.estado_txt }}</span></div>
        <div class="tabs self-start">
          <button type="button" class="tab" :class="{ on: tab === 'res' }" @click="tab = 'res'">Resultados</button>
          <button type="button" class="tab" :class="{ on: tab === 'con' }" @click="tab = 'con'">Conexión</button>
        </div>
        <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'warn'" role="status"><b>{{ msg.t }}</b></div>

        <!-- Resultados -->
        <template v-if="tab === 'res'">
          <template v-if="D.resultados">
            <div class="g2">
              <div class="box"><div class="lbl">Leads generados</div><div class="kn num k26">{{ D.resultados.leads }}</div></div>
              <div class="box"><div class="lbl">Costos pagados</div><div class="kn num k26">{{ fmtCOP(D.resultados.costo) }}</div></div>
              <div class="box"><div class="lbl">Costo por lead</div><div class="kn num k26">{{ fmtCOP(D.resultados.costo_lead) }}</div></div>
              <div class="box verde">
                <div class="lbl">Leads cerrados</div><div class="kn num k26">{{ D.resultados.cerrados }}</div>
                <div class="tiny">{{ D.resultados.arriendos }} arriendos · {{ D.resultados.ventas }} ventas</div>
              </div>
            </div>
            <div class="sb fila"><span class="mut">Conversión lead → cierre</span><b>{{ pct(D.resultados.conversion) }}</b></div>
            <div class="sb fila"><span class="mut">Costo por negocio cerrado</span><b>{{ fmtCOP(D.resultados.costo_cierre) }}</b></div>
            <div class="sb fila"><span class="mut">En proceso (aún pueden cerrarse)</span><b>{{ D.resultados.en_proceso }} lead{{ D.resultados.en_proceso === 1 ? '' : 's' }}</b></div>
            <div class="sb fila"><span class="mut">Último lead recibido</span><b>{{ D.resultados.ultimo ?? '—' }}</b></div>
            <div class="sb fila sinb"><span class="mut">Origen del costo</span><b>{{ D.origen_costo }}</b></div>
            <NuxtLink v-if="D.grupo === 'trad'" to="/plataformas" class="btn bs self-start">Ver en Plataformas tradicionales</NuxtLink>
          </template>
          <template v-else>
            <div v-if="D.nota" class="note">{{ D.nota }}</div>
            <div class="g2">
              <div class="box"><div class="lbl">Costos pagados</div><div class="kn num k26">{{ fmtCOP(D.costo) }}</div></div>
              <div class="box"><div class="lbl">{{ D.uso_t ?? 'Uso' }}</div><div class="kn num k26">{{ D.uso ?? '—' }}</div></div>
            </div>
            <div class="sb fila sinb"><span class="mut">Origen del costo</span><b>{{ D.origen_costo }}</b></div>
          </template>
        </template>

        <!-- Conexión -->
        <template v-else>
          <div class="kv">
            <span class="mut">Qué trae o envía</span><b>{{ D.conexion.que }}</b>
            <span class="mut">Dónde se usa</span><b>{{ D.conexion.donde }}</b>
            <span class="mut">Último dato</span><b>{{ D.conexion.ultimo_dato }}</b>
          </div>
          <div v-if="D.conexion.plataforma" class="mut tiny">{{ D.conexion.plataforma }}</div>
          <div class="g2">
            <div class="fld">
              <label for="c-como">Cómo llegan los datos</label>
              <select id="c-como" v-model="aj.como" class="in"><option v-for="(t, k) in T.como" :key="k" :value="k">{{ t }}</option></select>
            </div>
            <div class="fld">
              <label for="c-cos">Costo mensual {{ D.grupo === 'trad' ? '(si no tiene plan)' : '' }}</label>
              <input id="c-cos" v-model="aj.costo" class="in" inputmode="numeric" placeholder="$">
            </div>
          </div>
          <div><button type="button" class="btn bs sm" @click="guardarAjustes">Guardar ajustes</button></div>

          <div class="lbl">Datos para conectar</div>
          <div v-for="c in D.conexion.campos" :key="c.key" class="fld">
            <label :for="`f-${c.key}`">{{ c.label }}</label>
            <input
              :id="`f-${c.key}`"
              v-model="vals[c.key]"
              class="in"
              :type="c.secreto ? 'password' : 'text'"
              autocomplete="off"
              :placeholder="c.secreto && c.guardado ? `Guardada (${c.guardado}) · escribe para cambiarla` : c.ph"
            >
          </div>
          <div v-if="D.conexion.nota_campos" class="note">{{ D.conexion.nota_campos }}</div>
          <span v-if="D.estado === 'por_confirmar'" class="chip pend self-start">Falta el conector: hay que confirmar con la plataforma si ofrece conexión</span>
          <div class="row fw gp8">
            <button v-if="D.conexion.campos.length" type="button" class="btn bp" @click="guardar">Guardar y conectar</button>
            <template v-if="D.estado !== 'sin_conectar'">
              <button type="button" class="btn bs" @click="probar">Probar conexión</button>
              <button type="button" class="btn br" @click="conf = true">Desconectar</button>
            </template>
          </div>
          <div v-if="D.conexion.prueba_txt" class="mut tiny">Última prueba · {{ fmtCuando(D.conexion.prueba_at!) }}: {{ D.conexion.prueba_txt }}</div>
          <div class="sb aviso">
            <div><b class="t14">Avisar a Gerencia si la conexión falla</b><div class="mut tiny">Llega a la campana y queda en el registro de cambios</div></div>
            <AppSwitch v-model="aviso" label="Avisar si la conexión falla" />
          </div>
          <div class="note">
            Solo Gerencia conecta o desconecta. Las claves no se guardan: solo queda una pista («••••1234») para saber que se escribieron. Cada conexión, prueba y desconexión
            queda en el registro de cambios.
          </div>
          <div v-if="D.historial.length">
            <div class="lbl">Historial</div>
            <div v-for="(h, k) in D.historial" :key="k" class="hist">
              <span class="mut">{{ fmtCuando(h.at) }}</span>
              <span><b>{{ h.accion }}</b> · {{ h.actor ?? 'Sistema' }}<span v-if="h.despues" class="mut"> · {{ h.antes ? `${h.antes} → ` : '' }}{{ h.despues }}</span></span>
            </div>
          </div>
        </template>
      </div>
    </div>

    <div class="note">
      Los leads, cierres y «en proceso» salen de los leads que entraron por cada fuente. El costo de los portales sale de sus planes en «Plataformas tradicionales»; el de las
      redes y los servicios, del costo mensual registrado aquí, repartido en los días del rango. Todavía no hay conectores: los leads se registran a mano en Atención y Preventa.
    </div>
  </div>

  <ConfirmDialog v-if="conf && D" :title="`¿Desconectar ${D.nombre}?`" confirm-label="Sí, desconectar" danger @confirm="desconectar" @cancel="conf = false">
    Deja de llegar información desde esta plataforma. Lo que ya llegó se conserva y puedes volver a conectarla.
  </ConfirmDialog>
</template>

<style scoped>
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
.tiny {
  font-size: 12px;
}
.t14 {
  font-size: 14px;
}
.t16 {
  font-size: 16px;
}
.t18 {
  font-size: 18px;
}
.col4,
.col10,
.col12 {
  display: flex;
  flex-direction: column;
}
.col4 {
  gap: 4px;
}
.col10 {
  gap: 10px;
}
.col12 {
  gap: 12px;
}
.mb4 {
  margin-bottom: 4px;
}
.self-start {
  align-self: flex-start;
}
.col4 .pick {
  margin-bottom: 6px;
  text-align: left;
}
.dark {
  background: var(--cdc-green-dark);
  color: #fff;
  border-color: var(--cdc-green-dark);
}
.dark .lbl {
  color: var(--cdc-side-lema);
}
.chip.big {
  font-size: 12.5px;
  padding: 5px 12px;
}
.box {
  background: var(--cdc-bg);
  border-radius: 12px;
  padding: 12px;
}
.box.verde {
  background: var(--cdc-ok-bg);
}
.k26 {
  font-size: 26px;
}
.fila {
  font-size: 13px;
  padding: 6px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  gap: 12px;
}
.fila.sinb {
  border-bottom: 0;
}
.kv {
  font-size: 13px;
  display: grid;
  grid-template-columns: 130px minmax(0, 1fr);
  gap: 6px 10px;
}
.aviso {
  padding: 10px 12px;
  border: 1px solid var(--cdc-border);
  border-radius: 12px;
  gap: 12px;
}
.hist {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 8px;
  font-size: 12.5px;
  padding: 5px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
}
</style>
