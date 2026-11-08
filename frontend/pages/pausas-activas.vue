<script setup lang="ts">
import type { PaDia, PaEquipo, PaMias } from '~/types/pausas'

/**
 * G11 «Pausas activas». Everyone: «Mis pausas activas» (today's two, history and compliance; the
 * reminder itself is in each Inicio). The Auxiliar, Coordinación and Gerencia: the team view
 * (?tab=equipo) with the schedule (Auxiliar), the message (Auxiliar and Gerencia), today's record,
 * a person's history and the Excel.
 */
useHead({ title: 'Pausas activas · Casa Dolce Casa' })

const api = usePausas()
const descargas = useDescargas()
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const hoy = localDate(0)
const cargo = computed(() => auth.user.value?.cargo)
const veEquipo = computed(() => ['auxiliar_administrativa', 'coordinacion', 'gerencia'].includes(cargo.value ?? ''))
const home = computed(() => (cargo.value === 'gerencia' || cargo.value === 'coordinacion' ? '/coordinacion' : cargo.value === 'asesor' ? '/asesor' : '/'))
const tab = ref<'mias' | 'equipo'>(route.query.tab === 'equipo' && veEquipo.value ? 'equipo' : 'mias')
watch(tab, (t) => {
  router.replace({ query: t === 'equipo' ? { tab: 'equipo' } : {} })
  msg.value = null
})
watch(
  () => route.query.tab,
  (t) => (tab.value = t === 'equipo' && veEquipo.value ? 'equipo' : 'mias'),
)

const inicioMes = `${hoy.slice(0, 8)}01`
const f = reactive({ desde: inicioMes, hasta: hoy, user: '' })
const fErr = computed(() => !f.desde || !f.hasta || f.desde > f.hasta)
const q = computed(() => (fErr.value ? { desde: inicioMes, hasta: hoy } : { desde: f.desde, hasta: f.hasta }))
const msg = ref<{ t: string; ok: boolean } | null>(null)
const fd = (iso: string) => {
  const d = new Date(`${iso}T00:00:00`)
  return `${['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'][d.getDay()]} ${fmtFecha(iso)}`
}

// ---- mine
const { data: mData, refresh: refreshM } = await useAsyncData('pausas-mias', () => api.mias(q.value), { watch: [q] })
const M = computed(() => mData.value as PaMias | null)

// ---- team (G11)
const eq = computed(() => ({ ...q.value, ...(f.user ? { user_id: f.user } : {}) }))
const { data: eData, refresh: refreshE } = await useAsyncData('pausas-equipo', () => (veEquipo.value ? api.equipo(eq.value) : Promise.resolve(null)), { watch: [eq] })
const E = computed(() => eData.value as PaEquipo | null)
const H = reactive({ m: '10:00', t: '15:00', dur: 15, msg: '', ok: false, okMsg: false })
watch(
  E,
  (e) => {
    if (!e) return
    Object.assign(H, { m: e.config.hora_manana, t: e.config.hora_tarde, dur: e.config.minutos, msg: e.config.mensaje })
  },
  { immediate: true },
)
async function guardarHorario() {
  msg.value = null
  try {
    await api.horario({ hora_manana: H.m, hora_tarde: H.t, minutos: Number(H.dur) })
    H.ok = true
    msg.value = { t: `Horario guardado: mañana ${H.m}, tarde ${H.t}, el aviso queda ${H.dur} minutos. Aplica desde la próxima pausa y queda en el registro de cambios.`, ok: true }
    await refreshE()
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  }
}
async function guardarMensaje() {
  msg.value = null
  try {
    await api.mensaje(H.msg)
    H.okMsg = true
    msg.value = { t: 'Mensaje guardado. Es el que ven todos en su Inicio a la hora de la pausa.', ok: true }
    await refreshE()
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  }
}
const quien = computed(() => (E.value?.puede.horario ? 'Tú lo configuras' : E.value?.rol === 'gerencia' ? 'Gerencia solo consulta y descarga' : 'Coordinación solo consulta'))
async function descargar() {
  const persona = E.value?.personas.find((p) => p.id === f.user)?.full_name.replace(/\s+/g, '') ?? 'Todos'
  const archivo = `CDC_Pausas_activas_${persona}_${q.value.desde}_a_${q.value.hasta}.csv`
  try {
    await descargas.descargar('pau', { desde: q.value.desde, hasta: q.value.hasta, alcance: f.user ? 'emp' : 'tod', ...(f.user ? { user_id: f.user } : {}) }, archivo)
    msg.value = { t: `Descargado: ${archivo}. Una fila por persona, día y pausa: hora programada, hora en que marcó «Realizada», o «No realizada». La descarga queda en el registro de cambios.`, ok: true }
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  }
}
const kpiTxt = (k: PaEquipo['kpis']['manana']) =>
  k.estado === 'programada' ? `programada ${k.hora}` : k.estado === 'en_curso' ? `en curso · ${k.total - k.hechas} por marcar` : k.faltan.length ? `falta${k.faltan.length === 1 ? '' : 'n'} ${k.faltan.slice(0, 3).join(', ')}${k.faltan.length > 3 ? '…' : ''}` : 'todos la hicieron'
const pctTxt = (p: number | null) => (p == null ? '—' : `${p}%`)
const rangoTxt = computed(() => `${fmtFecha(q.value.desde)} al ${fmtFecha(q.value.hasta)}`)
const celda = (d: PaDia, t: 'manana' | 'tarde') => d[t]
</script>

<template>
  <!-- ================= Team (G11) ================= -->
  <template v-if="tab === 'equipo' && E">
    <PageBar title="Pausas activas" subtitle="Dos pausas al día, mañana y tarde, para todos los cargos · aparece en el Inicio de cada persona solo a la hora de la pausa" :back="home">
      <div class="row fw gp8 ac">
        <label class="row gp6 flt">Desde<input v-model="f.desde" class="in dt" type="date" aria-label="Fecha desde"></label>
        <label class="row gp6 flt">Hasta<input v-model="f.hasta" class="in dt" type="date" aria-label="Fecha hasta"></label>
      </div>
      <select v-model="f.user" class="sel" aria-label="Persona">
        <option value="">Todo el equipo</option>
        <option v-for="p in E.personas" :key="p.id" :value="p.id">{{ p.full_name }}</option>
      </select>
      <button type="button" class="btn bp" @click="descargar">Descargar Excel</button>
    </PageBar>
    <div class="cnt">
      <div class="tabs self-start">
        <button type="button" class="tab" @click="tab = 'mias'">Mis pausas activas</button>
        <button type="button" class="tab on">Del equipo</button>
      </div>
      <div v-if="fErr" class="note bad"><b>La fecha «Desde» no puede ser posterior a «Hasta». Se muestra este mes mientras lo corriges.</b></div>
      <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.t }}</b></div>

      <div class="card col10">
        <div class="sb"><span class="lbl">Horario de las pausas · lo configura la Auxiliar administrativa</span><span class="chip gray">{{ quien }}</span></div>
        <div class="grid end">
          <div class="fld"><label for="pm">Pausa de la mañana <span class="req">*</span></label><input id="pm" v-model="H.m" class="in" type="time" step="900" :disabled="!E.puede.horario" @input="H.ok = false"></div>
          <div class="fld"><label for="pt">Pausa de la tarde <span class="req">*</span></label><input id="pt" v-model="H.t" class="in" type="time" step="900" :disabled="!E.puede.horario" @input="H.ok = false"></div>
          <div class="fld"><label for="pd">Tiempo que el aviso queda en pantalla (minutos) <span class="req">*</span></label><input id="pd" v-model.number="H.dur" class="in" type="number" min="5" max="60" step="5" :disabled="!E.puede.horario" @input="H.ok = false"></div>
          <div class="fld"><span class="flbl">Aplica a</span><div class="mut small pad10">Todos los cargos, incluida Gerencia</div></div>
          <button v-if="E.puede.horario" type="button" class="btn bp self-end" @click="guardarHorario">{{ H.ok ? '✓ Horario guardado' : 'Guardar horario' }}</button>
        </div>
        <div class="note lime">
          La misma regla para todos los usuarios: el aviso de pausa activa <b>no está siempre en pantalla</b>. Aparece solo a la hora programada y se queda durante el tiempo configurado ({{ E.config.minutos }} minutos), o hasta que la persona toque «Realizada».
        </div>
        <div class="fld">
          <label for="pmsg">Mensaje que ve cada persona en su Inicio <span class="req">*</span></label>
          <textarea id="pmsg" v-model="H.msg" class="in ta" maxlength="300" :disabled="!E.puede.mensaje" aria-label="Mensaje de la pausa activa" @input="H.okMsg = false" />
          <span class="mut tiny">Lo pueden cambiar la Auxiliar administrativa y Gerencia. Aplica a todos los usuarios y queda en el registro de cambios.</span>
        </div>
        <div v-if="E.puede.mensaje" class="row fw gp8">
          <button type="button" class="btn bp" @click="guardarMensaje">{{ H.okMsg ? '✓ Mensaje guardado' : 'Guardar mensaje' }}</button>
          <span v-if="!H.msg.trim()" class="chip bad">Escribe el mensaje</span>
        </div>
        <div class="note">
          Las horas se eligen en el reloj, no se escriben. A esa hora a cada persona le aparece en su Inicio (celular y navegador) el aviso de pausa activa con el botón «Realizada»; al tocarlo, el
          aviso desaparece. Solo en días hábiles (lunes a viernes). La pausa activa no cuenta en los indicadores: es un registro de cumplimiento.
        </div>
      </div>

      <div class="g4">
        <div class="card"><div class="lbl">Mañana · hoy</div><div class="kn num">{{ E.habil ? `${E.kpis.manana.hechas} / ${E.kpis.manana.total}` : '—' }}</div><div class="mut tiny">{{ E.habil ? kpiTxt(E.kpis.manana) : 'hoy no hay pausas' }}</div></div>
        <div class="card"><div class="lbl">Tarde · hoy</div><div class="kn num">{{ E.habil ? `${E.kpis.tarde.hechas} / ${E.kpis.tarde.total}` : '—' }}</div><div class="mut tiny">{{ E.habil ? kpiTxt(E.kpis.tarde) : 'hoy no hay pausas' }}</div></div>
        <div class="card"><div class="lbl">Cumplimiento del periodo</div><div class="kn num">{{ pctTxt(E.kpis.pct) }}</div><div class="mut tiny">{{ rangoTxt }}</div></div>
        <div class="card"><div class="lbl">Sin realizar en el periodo</div><div class="kn num">{{ E.kpis.faltas }}</div><div class="mut tiny">hasta hoy</div></div>
      </div>

      <div v-if="E.persona" class="card">
        <div class="lbl mb8">Pausas de {{ E.persona.full_name }} · {{ rangoTxt }}</div>
        <div class="wrap">
          <div class="tblr">
            <div class="th c3"><span>Fecha</span><span>Mañana ({{ E.config.manana_txt }})</span><span>Tarde ({{ E.config.tarde_txt }})</span></div>
            <div v-for="d in E.persona.dias" :key="d.fecha" class="tr c3">
              <b>{{ fd(d.fecha) }}</b>
              <span v-for="t in (['manana', 'tarde'] as const)" :key="t"><span v-if="celda(d, t)" class="chip" :class="celda(d, t)!.estado_cls">{{ celda(d, t)!.estado_txt }}</span></span>
            </div>
          </div>
        </div>
        <div v-if="!E.persona.dias.length" class="note">No hay pausas en el periodo.</div>
      </div>

      <div class="card">
        <div class="lbl mb8">Registro de hoy · {{ fd(E.hoy) }}</div>
        <div v-if="!E.habil" class="note">Hoy no es día hábil: no hay pausas programadas.</div>
        <div v-else class="wrap">
          <div class="tblr">
            <div class="th c4"><span>Persona</span><span>Cargo</span><span>Mañana ({{ E.config.manana_txt }})</span><span>Tarde ({{ E.config.tarde_txt }})</span></div>
            <div v-for="r in E.hoy_filas" :key="r.user_id" class="tr c4">
              <b>{{ r.full_name }}</b><span class="mut">{{ r.cargo }}</span>
              <span class="chip js" :class="r.manana.estado_cls">{{ r.manana.estado_txt }}</span>
              <span class="chip js" :class="r.tarde.estado_cls">{{ r.tarde.estado_txt }}</span>
            </div>
          </div>
        </div>
      </div>
      <div class="note">
        La Auxiliar administrativa y Gerencia ven y descargan el registro de todo el personal; Coordinación, el de su equipo (asesores y Atención y Preventa). Cada persona ve sus propias pausas
        en su Inicio y en «Mis pausas activas». Los días con una ausencia registrada no cuentan.
      </div>
    </div>
  </template>

  <!-- ================= Mine ================= -->
  <template v-else-if="M">
    <PageBar title="Mis pausas activas" subtitle="Dos pausas al día, mañana y tarde · el aviso aparece en tu Inicio solo a la hora de la pausa" :back="home">
      <div class="row fw gp8 ac">
        <label class="row gp6 flt">Desde<input v-model="f.desde" class="in dt" type="date" aria-label="Fecha desde"></label>
        <label class="row gp6 flt">Hasta<input v-model="f.hasta" class="in dt" type="date" aria-label="Fecha hasta"></label>
      </div>
    </PageBar>
    <div class="cnt">
      <div v-if="veEquipo" class="tabs self-start">
        <button type="button" class="tab on">Mis pausas activas</button>
        <button type="button" class="tab" @click="tab = 'equipo'">Del equipo</button>
      </div>
      <div v-if="fErr" class="note bad"><b>La fecha «Desde» no puede ser posterior a «Hasta». Se muestra este mes mientras lo corriges.</b></div>
      <PausaBanner @marcada="refreshM" />
      <div class="g3">
        <div class="card"><div class="lbl">Cumplimiento</div><div class="kn num">{{ pctTxt(M.resumen.pct) }}</div><div class="mut tiny">{{ rangoTxt }}</div></div>
        <div class="card"><div class="lbl">Realizadas</div><div class="kn num">{{ M.resumen.realizadas }}</div></div>
        <div class="card"><div class="lbl">No realizadas</div><div class="kn num">{{ M.resumen.no_realizadas }}</div></div>
      </div>
      <div class="card">
        <div class="lbl mb8">Mis pausas · {{ rangoTxt }}</div>
        <div class="wrap">
          <div class="tblr sm">
            <div class="th c3"><span>Fecha</span><span>Mañana</span><span>Tarde</span></div>
            <div v-for="d in M.dias" :key="d.fecha" class="tr c3">
              <b>{{ fd(d.fecha) }}</b>
              <span v-for="t in (['manana', 'tarde'] as const)" :key="t">
                <span v-if="celda(d, t)" class="chip" :class="celda(d, t)!.estado_cls">{{ celda(d, t)!.estado_txt }}</span>
                <span v-if="celda(d, t)" class="mut tiny"> {{ celda(d, t)!.programada }}</span>
              </span>
            </div>
          </div>
        </div>
        <div v-if="!M.dias.length" class="note">No hay pausas en el periodo.</div>
      </div>
      <div class="note">Solo días hábiles (lunes a viernes). Los días con una ausencia registrada no cuentan. La pausa activa no cuenta en los indicadores: es un registro de cumplimiento.</div>
    </div>
  </template>
</template>

<style scoped>
.fw {
  flex-wrap: wrap;
}
.ac {
  align-items: center;
}
.gp6 {
  gap: 6px;
}
.gp8 {
  gap: 8px;
}
.col10 {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.self-start {
  align-self: flex-start;
}
.self-end {
  align-self: end;
}
.flt,
.flbl {
  font-size: 13px;
  font-weight: 700;
}
.dt {
  min-height: 38px;
  width: auto;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.pad10 {
  padding: 10px 0;
}
.mb8 {
  margin-bottom: 8px;
}
.js {
  justify-self: start;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.grid.end {
  align-items: end;
}
.note.lime {
  background: #f6fbef;
  color: var(--cdc-text);
}
.tblr {
  min-width: 640px;
}
.tblr.sm {
  min-width: 480px;
}
.th,
.tr {
  display: grid;
  gap: 8px;
  padding: 9px 10px;
  border-bottom: 1px solid var(--cdc-border-soft);
  font-size: 13px;
  align-items: center;
}
.th {
  padding: 8px 10px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #6b6e70;
  text-transform: uppercase;
  border-bottom-color: #dadbd7;
}
.c4 {
  grid-template-columns: 1.4fr 1.4fr 1fr 1fr;
}
.c3 {
  grid-template-columns: 1.2fr 1fr 1fr;
}
</style>
