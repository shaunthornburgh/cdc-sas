<script setup lang="ts">
import type { Formulario, Historial, MedioTransporte, PreoperacionalT } from '~/types/preoperacional'

/** Mi preoperacional (prototypes M07 phone / C08 desktop): «Realizar hoy» and «Mi historial y puntaje». */
useHead({ title: 'Preoperacional · Casa Dolce Casa' })

const auth = useAuth()
const preop = usePreoperacional()
const me = computed(() => auth.user.value!)
const manager = computed(() => isManager(me.value))
const route = useRoute()

const tab = ref<'hoy' | 'his'>(route.query.tab === 'historial' ? 'his' : 'hoy')
const { data: form, refresh: refreshForm } = await useAsyncData('preop-form', () => preop.formulario())
const f = computed(() => form.value as Formulario)

// ---- «Realizar hoy» --------------------------------------------------------------
const medio = ref<MedioTransporte | null>(null)
const placa = ref('')
const resp = ref<(boolean | null)[]>([])
const obsOpen = ref(false)
const obs = ref('')
const error = ref<string | null>(null)
const sending = ref(false)
const enviado = ref<PreoperacionalT | null>(null)

const preguntas = computed(() => (medio.value ? f.value.preguntas[medio.value] ?? [] : []))
const vehiculo = computed(() => preguntas.value.length > 0)
watch(medio, () => {
  resp.value = preguntas.value.map(() => null)
  error.value = null
})
const respondidas = computed(() => resp.value.filter((r) => r !== null).length)
const noIdx = computed(() => resp.value.map((r, i) => (r === false ? i + 1 : 0)).filter(Boolean))
const listo = computed(() => !!medio.value && (!vehiculo.value || (placa.value.trim().length >= 5 && respondidas.value === preguntas.value.length)))
const registro = computed(() => enviado.value ?? f.value.registro_de_hoy)

const ahora = ref(new Date())
onMounted(() => {
  const t = setInterval(() => (ahora.value = new Date()), 30_000)
  onBeforeUnmount(() => clearInterval(t))
})
const fechaLarga = (d: Date | string) =>
  new Intl.DateTimeFormat('es-CO', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'America/Bogota' }).format(new Date(d))

async function enviar() {
  if (!listo.value || !medio.value) return
  sending.value = true
  error.value = null
  try {
    enviado.value = await preop.registrar({
      medio: medio.value,
      placa: vehiculo.value ? placa.value : null,
      respuestas: vehiculo.value ? (resp.value as boolean[]) : null,
      observaciones: obs.value.trim() || null,
    })
    await Promise.all([refreshForm(), refreshHist()])
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    sending.value = false
  }
}

// ---- «Mi historial y puntaje» -----------------------------------------------------
const mes = ref(localDate().slice(0, 7))
const { data: hist, refresh: refreshHist } = await useAsyncData('preop-hist', () => preop.historial(mes.value), { watch: [mes] })
const h = computed(() => hist.value as Historial)
function moverMes(delta: number) {
  const [y, m] = mes.value.split('-').map(Number)
  const d = new Date(Date.UTC(y!, m! - 1 + delta, 1))
  mes.value = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`
}
const mesTxt = computed(() => {
  const [y, m] = mes.value.split('-').map(Number)
  const t = new Intl.DateTimeFormat('es-CO', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(y!, m! - 1, 15)))
  return t.charAt(0).toUpperCase() + t.slice(1)
})
const mesCorto = (delta: number) => {
  const [y, m] = mes.value.split('-').map(Number)
  return new Intl.DateTimeFormat('es-CO', { month: 'short', timeZone: 'UTC' }).format(new Date(Date.UTC(y!, m! - 1 + delta, 15))).replace('.', '')
}
const esMesActual = computed(() => mes.value === localDate().slice(0, 7))
/** Leading blanks so the 1st falls on its weekday (calendar starts Monday). */
const blancos = computed(() => {
  const first = h.value?.dias[0]?.fecha
  if (!first) return 0
  return (new Date(`${first}T12:00:00Z`).getUTCDay() + 6) % 7
})
const DIA: Record<string, { cls: string; m: string }> = {
  realizado: { cls: 'd-ok', m: '✓' },
  novedad: { cls: 'd-warn', m: '!' },
  no_realizado: { cls: 'd-bad', m: '✕' },
  pendiente: { cls: 'd-pend', m: 'hoy' },
  futuro: { cls: 'd-off', m: '' },
  fin_de_semana: { cls: 'd-off', m: '' },
  sin_contar: { cls: 'd-off', m: '' },
}
const fechaCorta = (iso: string) =>
  new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(`${iso}T12:00:00Z`)).replace('.', '')
const home = computed(() => (manager.value ? '/coordinacion' : hasCommercialActivity(me.value) ? '/asesor' : '/'))
</script>

<template>
  <PageBar title="Preoperacional" :subtitle="`${me.full_name} · ${CARGO_LABELS[me.cargo]}`" :back="home">
    <div class="tabs">
      <button type="button" class="tab" :class="{ on: tab === 'hoy' }" @click="tab = 'hoy'">Realizar hoy</button>
      <button type="button" class="tab" :class="{ on: tab === 'his' }" @click="tab = 'his'">Mi historial y puntaje</button>
    </div>
  </PageBar>

  <div class="cnt narrow">
    <div class="card status">
      <span class="chip" :class="f.activo ? 'ok' : 'gray'">{{ f.activo ? '✓ Activo para tu cargo' : 'Desactivado para tu cargo' }}</span>
      <span class="mut small grow">
        {{ f.activo ? `Lo hace todo el equipo, incluida Gerencia. ${f.destinatario}` : 'Gerencia desactivó el preoperacional para tu cargo: no aparece el aviso, no cuenta ni descuenta.' }}
      </span>
      <NuxtLink v-if="manager" class="btn bs sm" to="/preoperacionales">Preoperacionales del equipo ›</NuxtLink>
    </div>

    <!-- ============ Realizar hoy ============ -->
    <template v-if="tab === 'hoy'">
      <div v-if="!f.activo" class="card stack">
        <div class="lbl">Preoperacional desactivado</div>
        <div>Hoy no tienes que hacerlo. Tu historial se conserva.</div>
      </div>

      <div v-else-if="registro" class="card done">
        <div class="ok-icon" aria-hidden="true">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7" /></svg>
        </div>
        <b class="done-t">Registrado · {{ fmtHora(registro.realizado_at) }}</b>
        <div class="kv">
          <div class="sb"><span class="mut">Empleado</span><b>{{ registro.user.full_name }}</b></div>
          <div class="sb"><span class="mut">Fecha y hora</span><b>{{ fmtCuando(registro.realizado_at) }}</b></div>
          <div class="sb"><span class="mut">Medio</span><b>{{ f.medios[registro.medio] }}</b></div>
          <div v-if="registro.placa" class="sb"><span class="mut">Placa</span><b>{{ registro.placa }}</b></div>
          <div class="sb">
            <span class="mut">Novedades</span>
            <b>{{ registro.respuestas_no.length ? `NO en pregunta ${registro.respuestas_no.join(', ')}` : registro.observaciones ? 'Observación' : 'Ninguna' }}</b>
          </div>
        </div>
        <div class="mut small">{{ f.destinatario }}</div>
        <div v-if="registro.tiene_novedad" class="note warn full">
          Quedó registrado como novedad del día.
          <template v-if="registro.revisado_at"> ✓ Revisada por {{ registro.revisado_por_name }}.</template>
        </div>
        <div class="g2 full">
          <button type="button" class="btn bs" @click="tab = 'his'">Ver mi historial</button>
          <NuxtLink class="btn bp" :to="home">Volver al inicio</NuxtLink>
        </div>
      </div>

      <form v-else class="stack" @submit.prevent="enviar">
        <div class="note">{{ me.full_name }} · {{ fechaLarga(ahora) }} · {{ fmtHora(ahora.toISOString()) }} (se guardan solos)</div>
        <div class="fld">
          <span class="fld-label">¿Cómo te desplazas hoy? <span class="req">*</span></span>
          <div class="medios" role="radiogroup" aria-label="Medio de transporte">
            <button
              v-for="(t, k) in f.medios"
              :key="k"
              type="button"
              class="opt"
              :class="{ on: medio === k }"
              role="radio"
              :aria-checked="medio === k"
              @click="medio = k"
            >
              {{ t }}
            </button>
          </div>
        </div>

        <template v-if="vehiculo">
          <div class="fld">
            <label for="pl">Placa del vehículo <span class="req">*</span></label>
            <input id="pl" v-model="placa" class="in placa" :placeholder="medio === 'moto' ? 'XYZ45E' : 'ABC123'" maxlength="8" autocomplete="off">
          </div>
          <div class="card qs">
            <div v-for="(q, i) in preguntas" :key="i" class="q">
              <span class="q-t"><b>{{ i + 1 }}.</b> {{ q }}</span>
              <span class="row yn" role="radiogroup" :aria-label="`Pregunta ${i + 1}`">
                <button type="button" class="opt" :class="{ on: resp[i] === true }" role="radio" :aria-checked="resp[i] === true" @click="resp[i] = true">SÍ</button>
                <button type="button" class="opt" :class="{ on: resp[i] === false, bajo: resp[i] === false }" role="radio" :aria-checked="resp[i] === false" @click="resp[i] = false">NO</button>
              </span>
            </div>
          </div>
          <div class="mut small">Respondidas: {{ respondidas }} de {{ preguntas.length }}</div>
          <div v-if="noIdx.length" class="note warn">
            Respondiste NO en la pregunta {{ noIdx.join(', ') }}. Queda registrado como novedad del día y se le avisa a Coordinación.
            Puedes ampliar la información en «Observaciones y novedades».
          </div>
        </template>

        <div v-else-if="medio" class="card stack report">
          <div class="lbl">Reporte de desplazamiento</div>
          <div class="sb"><span class="mut">Empleado</span><b>{{ me.full_name }}</b></div>
          <div class="sb"><span class="mut">Fecha y hora</span><b>{{ fmtCuando(ahora.toISOString()) }}</b></div>
          <div class="sb"><span class="mut">Medio de transporte</span><b>{{ f.medios[medio] }}</b></div>
          <div class="mut small">Sin cuestionario ni placa para este medio.</div>
        </div>

        <button type="button" class="btn bs" :aria-expanded="obsOpen" @click="obsOpen = !obsOpen">Observaciones y novedades</button>
        <div v-if="obsOpen" class="fld">
          <label for="ob">Observaciones y novedades</label>
          <textarea id="ob" v-model="obs" class="in" placeholder="Escribe aquí si hay algo para informar" />
        </div>
        <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
        <button type="submit" class="btn bp send" :disabled="!listo || sending">{{ sending ? 'Enviando…' : 'Enviar' }}</button>
        <div v-if="!listo" class="mut small center">
          {{ !medio ? 'Para enviar: elige cómo te desplazas.' : 'Para enviar: escribe la placa y responde las 8 preguntas.' }}
        </div>
      </form>
    </template>

    <!-- ============ Mi historial y puntaje ============ -->
    <template v-else-if="h">
      <div class="card score">
        <div class="score-box" :class="h.resumen.puntaje == null ? 'sb-gray' : h.resumen.puntaje <= 2 ? 'sb-bad' : h.resumen.puntaje === 3 ? 'sb-warn' : 'sb-ok'">
          <template v-if="h.resumen.puntaje != null"><span class="kn num">{{ h.resumen.puntaje }}</span><span class="of">de 5</span></template>
          <span v-else class="of">{{ me.cargo === 'gerencia' ? 'Registro' : 'Sin datos' }}</span>
        </div>
        <div>
          <div class="lbl">Puntaje de {{ mesTxt.toLowerCase() }}{{ esMesActual ? ' (hasta hoy)' : '' }}</div>
          <div class="small">
            <template v-if="me.cargo === 'gerencia'">El preoperacional de Gerencia queda como registro: no tiene puntaje.</template>
            <template v-else-if="h.resumen.pct != null">
              Lo calcula el sistema según tu cumplimiento: <b>{{ h.resumen.cumplidos }} de {{ h.resumen.dias_habiles }}</b> días hábiles ({{ h.resumen.pct }}%).
            </template>
            <template v-else>Aún no hay días hábiles para calcular.</template>
          </div>
          <div class="mut tiny">No puedes modificarlo.<template v-if="h.resumen.descuento"> Con nota de 2 o 1 se descuentan {{ h.resumen.descuento }} puntos.</template></div>
        </div>
      </div>

      <div class="card">
        <div class="sb cal-head">
          <b>{{ mesTxt }}</b>
          <span class="row nav">
            <button type="button" class="fch" @click="moverMes(-1)">‹ {{ mesCorto(-1) }}</button>
            <button type="button" class="fch" :disabled="esMesActual" @click="moverMes(1)">{{ mesCorto(1) }} ›</button>
          </span>
        </div>
        <div class="cal dow mut"><span>L</span><span>M</span><span>M</span><span>J</span><span>V</span><span>S</span><span>D</span></div>
        <div class="cal">
          <span v-for="i in blancos" :key="`b${i}`" />
          <div v-for="d in h.dias" :key="d.fecha" class="day" :class="DIA[d.estado]?.cls" :title="d.estado.replace('_', ' ')">
            <span>{{ Number(d.fecha.slice(8)) }}</span><span class="m">{{ DIA[d.estado]?.m }}</span>
          </div>
        </div>
        <div class="legend">
          <span class="row"><i class="sw-ok" />Realizado</span>
          <span class="row"><i class="sw-warn" />Realizado con novedad</span>
          <span class="row"><i class="sw-bad" />No realizado</span>
        </div>
      </div>

      <div class="card list">
        <div class="lbl lhead">Novedades y días no realizados</div>
        <div v-for="(e, i) in h.eventos" :key="i" class="li">
          <div>
            <b>{{ fechaCorta(e.fecha) }} · {{ e.tipo === 'novedad' ? 'novedad' : 'no realizado' }}</b>
            <div class="mut tiny">
              <template v-if="e.tipo === 'novedad' && e.registro">
                {{ e.registro.observaciones ?? (e.registro.respuestas_no.length ? `NO en pregunta ${e.registro.respuestas_no.join(', ')}` : 'Novedad') }}
                · {{ e.registro.revisado_at ? `${e.registro.revisado_por_name ?? 'Coordinación'} la revisó` : 'pendiente de revisión' }}
              </template>
              <template v-else>Bajó tu cumplimiento del mes</template>
            </div>
          </div>
          <span class="chip" :class="e.tipo === 'novedad' ? 'warn' : 'bad'">{{ e.tipo === 'novedad' ? 'Novedad' : 'No realizado' }}</span>
        </div>
        <p v-if="!h.eventos.length" class="mut small pad">Sin novedades ni días sin realizar este mes.</p>
      </div>
      <div class="note">Hacerlo no suma puntos: queda como cumplimiento. No hacerlo baja tu nota del mes. Si la nota queda en 2 o 1, se descuentan 5 puntos.</div>
    </template>
  </div>
</template>

<style scoped>
.narrow {
  max-width: 760px;
  width: 100%;
}
.status {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  padding: 12px 16px;
}
.grow {
  flex: 1;
  min-width: 240px;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.center {
  text-align: center;
}
.medios {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.placa {
  text-transform: uppercase;
}
.qs {
  padding: 4px 14px;
}
.q {
  padding: 10px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  display: flex;
  gap: 10px;
  align-items: center;
}
.q:last-child {
  border-bottom: 0;
}
.q-t {
  font-size: 13px;
  flex: 1;
}
.yn {
  gap: 4px;
  flex: none;
}
.yn .opt {
  min-height: 38px;
  min-width: 50px;
  padding: 0;
}
.opt.on.bajo {
  background: var(--cdc-bad);
  border-color: var(--cdc-bad);
}
.report {
  gap: 6px;
  font-size: 13px;
}
.send {
  min-height: 46px;
}
.done {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
  text-align: center;
  padding: 22px 16px;
}
.ok-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: var(--cdc-ok-bg);
  color: var(--cdc-ok);
  display: flex;
  align-items: center;
  justify-content: center;
}
.done-t {
  font-size: 17px;
}
.kv {
  font-size: 13px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
}
.full {
  width: 100%;
}
.score {
  display: flex;
  gap: 14px;
  align-items: center;
}
.score-box {
  width: 84px;
  height: 84px;
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: none;
}
.sb-ok {
  background: var(--cdc-ok-bg);
  color: var(--cdc-ok);
}
.sb-warn {
  background: var(--cdc-warn-bg);
  color: var(--cdc-warn);
}
.sb-bad {
  background: var(--cdc-bad-bg);
  color: var(--cdc-bad);
}
.sb-gray {
  background: var(--cdc-gray-bg);
  color: var(--cdc-gray);
}
.of {
  font-size: 11px;
  font-weight: 700;
}
.cal-head {
  margin-bottom: 10px;
}
.nav {
  gap: 6px;
}
.cal {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 4px;
  margin-top: 4px;
}
.dow {
  font-size: 11px;
  text-align: center;
}
.day {
  height: 40px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}
.day .m {
  font-size: 9px;
}
.d-ok {
  background: var(--cdc-ok-bg);
  color: var(--cdc-ok);
}
.d-warn {
  background: var(--cdc-warn-bg);
  color: var(--cdc-warn);
}
.d-bad {
  background: var(--cdc-bad-bg);
  color: var(--cdc-bad);
}
.d-pend {
  background: #fff;
  border: 1.5px dashed var(--cdc-green);
  color: var(--cdc-green);
}
.d-off {
  background: var(--cdc-bg);
  color: #939598;
}
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
  font-size: 11px;
}
.legend .row {
  gap: 4px;
}
.legend i {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  display: inline-block;
}
.sw-ok {
  background: var(--cdc-ok-bg);
  border: 1px solid var(--cdc-ok);
}
.sw-warn {
  background: var(--cdc-warn-bg);
  border: 1px solid #b7791f;
}
.sw-bad {
  background: var(--cdc-bad-bg);
  border: 1px solid var(--cdc-bad);
}
.list {
  padding: 4px 14px;
}
.lhead {
  padding-top: 10px;
}
.pad {
  padding: 8px 0;
}
@media (max-width: 640px) {
  .medios {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
