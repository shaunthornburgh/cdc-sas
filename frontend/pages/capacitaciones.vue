<script setup lang="ts">
import type { CapEquipo, CapEquipoItem, CapMia, CapMias } from '~/types/capacitaciones'

/**
 * Z03 «Mis capacitaciones» (everyone) and X07 «Capacitaciones del equipo» (?tab=equipo: the
 * Auxiliar administrativa, Coordinación and Gerencia program trainings, see the answers, mark
 * attendance; the Auxiliar and Gerencia download the Excel).
 */
useHead({ title: 'Capacitaciones · Casa Dolce Casa' })

const api = useCapacitaciones()
const descargas = useDescargas()
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const hoy = localDate(0)
const cargo = computed(() => auth.user.value?.cargo)
const organiza = computed(() => ['auxiliar_administrativa', 'coordinacion', 'gerencia'].includes(cargo.value ?? ''))
const home = computed(() => (cargo.value === 'gerencia' || cargo.value === 'coordinacion' ? '/coordinacion' : cargo.value === 'asesor' ? '/asesor' : '/'))
const tab = ref<'mias' | 'equipo'>(route.query.tab === 'equipo' && organiza.value ? 'equipo' : 'mias')
watch(tab, (t) => {
  router.replace({ query: t === 'equipo' ? { tab: 'equipo' } : {} })
  msg.value = null
})
watch(
  () => route.query.tab,
  (t) => (tab.value = t === 'equipo' && organiza.value ? 'equipo' : 'mias'),
)

const msg = ref<{ t: string; ok: boolean } | null>(null)
const busy = ref(false)
async function run(fn: () => Promise<unknown>, t: string) {
  busy.value = true
  try {
    await fn()
    msg.value = { t, ok: true }
    await Promise.all([refreshM(), organiza.value ? refreshE() : Promise.resolve()])
    return true
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
    return false
  } finally {
    busy.value = false
  }
}

// ================= Z03 · Mis capacitaciones =================
const { data: mData, refresh: refreshM } = await useAsyncData('cap-mias', () => api.mias())
const M = computed(() => mData.value as CapMias | null)
const who = computed(() => (auth.user.value ? `${auth.user.value.full_name} · ${CARGO_LABELS[auth.user.value.cargo]}` : ''))

const R = reactive({ on: false, fecha: hoy, hora: '16:00', area: 'Comercial', tema: '', presenta: '', aprendio: '', obs: '', err: '' })
async function registrar() {
  R.err = ''
  try {
    await api.registrar({ fecha: R.fecha, hora: R.hora, area: R.area, tema: R.tema, presenta: R.presenta, aprendio: R.aprendio, observaciones: R.obs || null })
    Object.assign(R, { on: false, tema: '', presenta: '', aprendio: '', obs: '' })
    msg.value = { t: '✓ Enviada. Les llegó a la Auxiliar administrativa y a Gerencia, y quedó en tu histórico.', ok: true }
    await refreshM()
  } catch (e) {
    R.err = apiErrorMessage(e)
  }
}

const motivoDe = reactive<Record<string, { on: boolean; motivo: string; detalle: string }>>({})
const abrirMotivo = (c: CapMia) => (motivoDe[c.id] = { on: !motivoDe[c.id]?.on, motivo: M.value?.motivos[0] ?? '', detalle: '' })
const aceptar = (c: CapMia) => run(() => api.responder(c.id, { acepta: true }), `Aceptaste participar en «${c.tema}». Aparece en tu agenda.`)
async function noPodre(c: CapMia) {
  const m = motivoDe[c.id]!
  if (await run(() => api.responder(c.id, { acepta: false, motivo: m.motivo, detalle: m.detalle || null }), `Enviado: no participarás en «${c.tema}» (${m.motivo.toLowerCase()}).`)) m.on = false
}
const cambiar = reactive<Record<string, boolean>>({})

const apr = reactive<Record<string, { on: boolean; t: string; obs: string }>>({})
const abrirApr = (c: CapMia) => (apr[c.id] = { on: !apr[c.id]?.on, t: c.aprendio ?? '', obs: c.observaciones ?? '' })
async function guardarApr(c: CapMia) {
  const a = apr[c.id]!
  if (await run(() => api.aprendizaje(c.id, a.t, a.obs), 'Guardado en tu histórico.')) a.on = false
}

// ================= X07 · Capacitaciones del equipo =================
const inicioMes = `${hoy.slice(0, 8)}01`
const finMes = (() => {
  const d = new Date(`${inicioMes}T00:00:00`)
  d.setMonth(d.getMonth() + 1, 0)
  return localDate(Math.round((d.getTime() - new Date(`${hoy}T00:00:00`).getTime()) / 864e5))
})()
const f = reactive({ desde: inicioMes, hasta: finMes })
const fErr = computed(() => !f.desde || !f.hasta || f.desde > f.hasta)
const q = computed(() => (fErr.value ? { desde: inicioMes, hasta: finMes } : { desde: f.desde, hasta: f.hasta }))
const { data: eData, refresh: refreshE } = await useAsyncData('cap-equipo', () => (organiza.value ? api.equipo(q.value) : Promise.resolve(null)), { watch: [q] })
const E = computed(() => eData.value as CapEquipo | null)
const rango = computed(() => `${fmtFecha(q.value.desde)} al ${fmtFecha(q.value.hasta)}`)

const P = reactive({ on: false, fecha: localDate(1), hora: '08:00', area: 'Todas las áreas', tema: '', presenta: '', lugar: '', part: 'todo', personas: [] as string[], err: '' })
function togPersona(id: string) {
  P.personas = P.personas.includes(id) ? P.personas.filter((x) => x !== id) : [...P.personas, id]
}
async function programar() {
  P.err = ''
  try {
    const c = await api.programar({ fecha: P.fecha, hora: P.hora, area: P.area, tema: P.tema, presenta: P.presenta, lugar: P.lugar || null, participantes: P.part, personas: P.part === 'per' ? P.personas : [] })
    msg.value = { t: `✓ Programada (${c.code}). A cada participante (${c.participantes}) le llegó la notificación para aceptar su participación o decir el motivo si no puede. Aparece en su agenda y en su histórico.`, ok: true }
    Object.assign(P, { on: false, tema: '', presenta: '', lugar: '', part: 'todo', personas: [] })
    await Promise.all([refreshE(), refreshM()])
  } catch (e) {
    P.err = apiErrorMessage(e)
  }
}

const ver = ref<string | null>(null)
const asis = reactive<Record<string, { on: boolean; ids: string[] }>>({})
function abrirAsis(c: CapEquipoItem) {
  ver.value = c.id
  asis[c.id] = { on: !asis[c.id]?.on, ids: c.gente.filter((g) => g.respuesta === 'acepta').map((g) => g.user_id) }
}
function togAsis(c: CapEquipoItem, id: string) {
  const a = asis[c.id]!
  a.ids = a.ids.includes(id) ? a.ids.filter((x) => x !== id) : [...a.ids, id]
}
async function completar(c: CapEquipoItem) {
  const a = asis[c.id]!
  if (await run(() => api.completar(c.id, a.ids), `${c.code}: asistencia guardada (${a.ids.length} de ${c.gente.length} participaron). Queda como realizada.`)) a.on = false
}
const canc = reactive<Record<string, { on: boolean; motivo: string }>>({})
async function cancelar(c: CapEquipoItem) {
  const x = canc[c.id]!
  if (await run(() => api.cancelar(c.id, x.motivo), `${c.code} cancelada. Queda en el registro de cambios.`)) x.on = false
}
async function descargarExcel() {
  const archivo = `CDC_Capacitaciones_Todos_${q.value.desde}_a_${q.value.hasta}.csv`
  await run(() => descargas.descargar('cap', { desde: q.value.desde, hasta: q.value.hasta, alcance: 'tod' }, archivo), `Descargado: ${archivo}. Una fila por persona y capacitación. La descarga queda en el registro de cambios.`)
}
const siT = (c: CapEquipoItem) => (c.estado === 'realizada' ? 'participaron' : 'aceptaron')
</script>

<template>
  <!-- ================= X07 ================= -->
  <template v-if="tab === 'equipo' && E">
    <PageBar title="Capacitaciones del equipo" subtitle="Programa capacitaciones, revisa quién aceptó o por qué no participa y descarga el registro · Auxiliar administrativa, Coordinación y Gerencia programan · Auxiliar y Gerencia descargan" :back="home">
      <div class="row fw gp8 ac">
        <label class="row gp6 flt">Desde<input v-model="f.desde" class="in dt" type="date" aria-label="Fecha desde"></label>
        <label class="row gp6 flt">Hasta<input v-model="f.hasta" class="in dt" type="date" aria-label="Fecha hasta"></label>
      </div>
      <button v-if="E.puede_descargar" type="button" class="btn bs" :disabled="busy" @click="descargarExcel">Descargar Excel</button>
      <button type="button" class="btn bp" @click="P.on = !P.on; msg = null">+ Programar capacitación</button>
    </PageBar>
    <div class="cnt">
      <div class="tabs self-start">
        <button type="button" class="tab" @click="tab = 'mias'">Mis capacitaciones</button>
        <button type="button" class="tab on">Del equipo</button>
      </div>
      <div v-if="fErr" class="note bad"><b>La fecha «Desde» no puede ser posterior a «Hasta». Se muestra este mes mientras lo corriges.</b></div>
      <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.t }}</b></div>

      <div v-if="P.on" class="card focus col12">
        <div class="sb"><span class="lbl">Programar capacitación</span><button type="button" class="btn bs h36" @click="P.on = false">Cerrar</button></div>
        <div class="grid">
          <div class="fld"><label for="pf">Fecha <span class="req">*</span></label><input id="pf" v-model="P.fecha" class="in" type="date" :min="hoy"></div>
          <div class="fld"><label for="ph">Hora <span class="req">*</span></label><input id="ph" v-model="P.hora" class="in" type="time" step="900"></div>
          <div class="fld"><label for="pa">Área <span class="req">*</span></label><select id="pa" v-model="P.area" class="in"><option v-for="a in E.areas" :key="a">{{ a }}</option></select></div>
        </div>
        <div class="grid">
          <div class="fld"><label for="pt">Tema <span class="req">*</span></label><input id="pt" v-model="P.tema" class="in" maxlength="200" placeholder="Ej.: Requisitos para estudio de arrendatario"></div>
          <div class="fld"><label for="pq">¿Quién la presenta? <span class="req">*</span></label><input id="pq" v-model="P.presenta" class="in" maxlength="200" placeholder="Nombre de la persona o entidad"></div>
          <div class="fld"><label for="pl">Lugar o enlace</label><input id="pl" v-model="P.lugar" class="in" maxlength="300" placeholder="Sala de reuniones o enlace de videollamada"></div>
        </div>
        <div class="fld">
          <span class="flbl">¿Quiénes deben participar? <span class="req">*</span></span>
          <div class="row fw gp6"><button v-for="(t, k) in E.participantes" :key="k" type="button" class="opt" :class="{ on: P.part === k }" @click="P.part = k">{{ t }}</button></div>
        </div>
        <div v-if="P.part === 'per'" class="row fw gp6">
          <button v-for="x in E.personas" :key="x.id" type="button" class="fch" :class="{ on: P.personas.includes(x.id) }" @click="togPersona(x.id)">{{ x.full_name }}</button>
        </div>
        <div v-if="P.err" class="note bad"><b>{{ P.err }}</b></div>
        <button type="button" class="btn bp self-start" @click="programar">Programar y avisar al equipo</button>
      </div>

      <div class="g4">
        <div class="card"><div class="lbl">Programadas · {{ rango }}</div><div class="kn num">{{ E.kpis.programadas }}</div></div>
        <div class="card k-warn"><div class="lbl">Por responder</div><div class="kn num">{{ E.kpis.por_responder }}</div><div class="mut tiny">personas que no han aceptado</div></div>
        <div class="card"><div class="lbl">Registradas por el equipo</div><div class="kn num">{{ E.kpis.registradas }}</div><div class="mut tiny">en el periodo</div></div>
        <div class="card k-bad">
          <div class="lbl">No participaron</div><div class="kn num">{{ E.kpis.no_participaron }}</div>
          <div class="mut tiny">{{ E.kpis.no_participaron && E.kpis.con_motivo === E.kpis.no_participaron ? 'todas con motivo' : `${E.kpis.con_motivo} con motivo` }}</div>
        </div>
      </div>

      <div class="card col8">
        <div class="lbl">Programadas · respuestas del equipo</div>
        <div v-for="c in E.programadas" :key="c.id" class="box col8" :class="{ dim: c.estado === 'cancelada' }">
          <div class="sb fw gp10">
            <span>
              <b>{{ c.code }} · {{ c.tema }}</b><br>
              <span class="mut small">{{ c.cuando }}{{ c.estado === 'realizada' ? ' · realizada' : c.estado === 'cancelada' ? ' · cancelada' : '' }} · {{ c.area }} · presenta {{ c.presenta }} · {{ c.origen_txt.toLowerCase() }}</span>
            </span>
            <span class="row fw gp6 ac">
              <template v-if="c.estado !== 'cancelada'">
                <span class="chip ok">{{ c.si }} {{ siT(c) }}</span>
                <span v-if="c.estado === 'programada'" class="chip warn">{{ c.pe }} por responder</span>
                <span class="chip bad">{{ c.no }} no participa{{ c.no === 1 ? '' : 'n' }}</span>
              </template>
              <span v-else class="chip gray">Cancelada</span>
              <button type="button" class="btn bs sm" @click="ver = ver === c.id ? null : c.id">{{ ver === c.id ? 'Ocultar' : 'Ver respuestas' }}</button>
            </span>
          </div>
          <div v-if="c.estado === 'cancelada' && c.cancelada_motivo" class="mut small">Motivo: {{ c.cancelada_motivo }}</div>
          <div v-if="ver === c.id" class="col">
            <div v-for="g in c.gente" :key="g.user_id" class="sb prow">
              <span>{{ g.full_name }}<span v-if="g.aprendio" class="mut tiny"> · aprendió: {{ g.aprendio }}</span></span>
              <span class="row gp6 ac">
                <label v-if="asis[c.id]?.on" class="row gp6 small"><input type="checkbox" :checked="asis[c.id]!.ids.includes(g.user_id)" @change="togAsis(c, g.user_id)"> Participó</label>
                <template v-else><span class="chip" :class="g.estado_cls">{{ g.estado_txt }}</span> <span class="mut tiny">{{ g.motivo_txt }}</span></template>
              </span>
            </div>
          </div>
          <div v-if="c.estado === 'programada'" class="row fw gp8">
            <template v-if="c.puede_completar">
              <button v-if="!asis[c.id]?.on" type="button" class="btn bp sm" @click="abrirAsis(c)">Marcar asistencia</button>
              <template v-else>
                <button type="button" class="btn bp sm" :disabled="busy" @click="completar(c)">Guardar asistencia · realizada</button>
                <button type="button" class="btn bs sm" @click="asis[c.id]!.on = false">Cancelar</button>
                <span class="mut tiny">Quienes aceptaron vienen marcados; ajusta según quién asistió.</span>
              </template>
            </template>
            <template v-else>
              <button v-if="!canc[c.id]?.on" type="button" class="btn bs sm" @click="canc[c.id] = { on: true, motivo: '' }">Cancelar capacitación</button>
              <template v-else>
                <input v-model="canc[c.id]!.motivo" class="in grow1 h36" maxlength="300" placeholder="Motivo de la cancelación" aria-label="Motivo de la cancelación">
                <button type="button" class="btn br sm" :disabled="busy" @click="cancelar(c)">Confirmar cancelación</button>
                <button type="button" class="btn bs sm" @click="canc[c.id]!.on = false">Volver</button>
              </template>
            </template>
          </div>
        </div>
        <div v-if="!E.programadas.length" class="note">No hay capacitaciones programadas en el periodo.</div>
      </div>

      <div class="card">
        <div class="lbl mb8">Registradas por el equipo · enviadas desde «Mis capacitaciones»</div>
        <div class="wrap">
          <div class="tblr">
            <div class="th r6"><span>Persona</span><span>Fecha</span><span>Tema</span><span>Área</span><span>Presentó</span><span>Qué aprendió</span></div>
            <div v-for="r in E.registradas" :key="r.id" class="tr r6">
              <b>{{ r.persona?.full_name ?? '—' }}</b><span class="num">{{ r.cuando }}</span><span>{{ r.tema }}</span><span>{{ r.area }}</span><span>{{ r.presenta }}</span>
              <span class="mut">{{ r.aprendio }}<template v-if="r.observaciones"> · {{ r.observaciones }}</template></span>
            </div>
          </div>
        </div>
        <div v-if="!E.registradas.length" class="note">Nadie ha registrado capacitaciones en el periodo.</div>
      </div>
      <div class="note">
        La Auxiliar administrativa, Coordinación y Gerencia pueden programar capacitaciones; la Auxiliar y Gerencia además descargan el Excel (también en «Descargas del personal»). Cada persona
        ve su propio histórico en «Mis capacitaciones», tanto las que registró ella como las programadas.
      </div>
    </div>
  </template>

  <!-- ================= Z03 ================= -->
  <template v-else-if="M">
    <PageBar title="Mis capacitaciones" :subtitle="`${who} · registra tu participación, responde las programadas y consulta tu histórico`" :back="home">
      <button type="button" class="btn bp" @click="R.on = !R.on; msg = null">+ Registrar participación</button>
    </PageBar>
    <div class="cnt">
      <div v-if="organiza" class="tabs self-start">
        <button type="button" class="tab on">Mis capacitaciones</button>
        <button type="button" class="tab" @click="tab = 'equipo'">Del equipo</button>
      </div>
      <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.t }}</b></div>

      <div v-if="R.on" class="card focus col12">
        <div class="sb"><span class="lbl">Registrar participación en una capacitación</span><button type="button" class="btn bs h36" @click="R.on = false">Cerrar</button></div>
        <div class="grid">
          <div class="fld"><label for="cf">Fecha <span class="req">*</span></label><input id="cf" v-model="R.fecha" class="in" type="date" :max="hoy"></div>
          <div class="fld"><label for="ch">Hora <span class="req">*</span></label><input id="ch" v-model="R.hora" class="in" type="time" step="900"></div>
          <div class="fld"><label for="ca">Área <span class="req">*</span></label><select id="ca" v-model="R.area" class="in"><option v-for="a in M.areas" :key="a">{{ a }}</option></select></div>
        </div>
        <div class="g2">
          <div class="fld"><label for="ct">Tema <span class="req">*</span></label><input id="ct" v-model="R.tema" class="in" maxlength="200" placeholder="Ej.: Cómo tomar fotos que venden en portales"></div>
          <div class="fld"><label for="cp">¿Quién presentó la capacitación? <span class="req">*</span></label><input id="cp" v-model="R.presenta" class="in" maxlength="200" placeholder="Nombre de la persona o entidad"></div>
        </div>
        <div class="fld"><label for="cq">¿Qué aprendiste? <span class="req">*</span></label><textarea id="cq" v-model="R.aprendio" class="in ta" maxlength="2000" placeholder="Escribe lo más importante que aprendiste" /></div>
        <div class="fld"><label for="co">Observaciones</label><textarea id="co" v-model="R.obs" class="in ta" maxlength="2000" placeholder="Opcional" /></div>
        <div v-if="R.err" class="note bad"><b>{{ R.err }}</b></div>
        <button type="button" class="btn bp self-start" @click="registrar">Enviar</button>
      </div>

      <div class="card col8">
        <div class="sb"><span class="lbl">Programadas para ti · acepta tu participación</span><span class="chip warn">{{ M.por_responder }} por responder</span></div>
        <div v-for="c in M.programadas" :key="c.id" class="box col8">
          <div class="sb fw gp10">
            <span>
              <b>{{ c.tema }}</b><br>
              <span class="mut small">{{ c.cuando }} · {{ c.area }} · presenta {{ c.presenta }}{{ c.lugar ? ` · ${c.lugar}` : '' }}</span><br>
              <span class="mut tiny">{{ c.origen_txt }}</span>
            </span>
            <span class="chip" :class="c.estado_cls">{{ c.estado_txt }}{{ c.respuesta === 'no' && c.motivo ? ` · ${c.motivo.toLowerCase()}` : '' }}</span>
          </div>
          <div v-if="(c.respuesta === 'pendiente' || cambiar[c.id]) && !motivoDe[c.id]?.on" class="row fw gp8">
            <button type="button" class="btn bp" :disabled="busy" @click="aceptar(c); cambiar[c.id] = false">Aceptar participación</button>
            <button type="button" class="btn bs" @click="abrirMotivo(c)">No podré participar</button>
          </div>
          <button v-else-if="c.respuesta !== 'pendiente' && !motivoDe[c.id]?.on" type="button" class="fch self-start" @click="cambiar[c.id] = true">Cambiar mi respuesta</button>
          <div v-if="motivoDe[c.id]?.on" class="mbox col6">
            <b class="small">Motivo por el que no participarás <span class="req">*</span></b>
            <div class="row fw gp6"><button v-for="m in M.motivos" :key="m" type="button" class="opt" :class="{ on: motivoDe[c.id]!.motivo === m }" @click="motivoDe[c.id]!.motivo = m">{{ m }}</button></div>
            <input v-if="motivoDe[c.id]!.motivo === 'Otro motivo'" v-model="motivoDe[c.id]!.detalle" class="in" maxlength="300" placeholder="Cuéntanos el motivo" aria-label="Detalle del motivo">
            <div class="row gp8">
              <button type="button" class="btn bp" :disabled="busy" @click="noPodre(c); cambiar[c.id] = false">Enviar motivo</button>
              <button type="button" class="btn bs" @click="motivoDe[c.id]!.on = false">Cancelar</button>
            </div>
          </div>
        </div>
        <div v-if="!M.programadas.length" class="note">No tienes capacitaciones programadas.</div>
      </div>

      <div class="card">
        <div class="sb mb8 fw gp8"><span class="lbl">Mi histórico de capacitaciones</span><span class="mut tiny">las que registraste tú y las que programaron la Auxiliar administrativa, Coordinación o Gerencia</span></div>
        <div class="wrap">
          <div class="tblr">
            <div class="th h6"><span>Fecha</span><span>Tema · qué aprendí</span><span>Área</span><span>Presentó</span><span>Origen</span><span>Participación</span></div>
            <template v-for="h in M.historico" :key="h.id">
              <div class="tr h6">
                <span class="num">{{ h.cuando }}</span>
                <span>
                  <b>{{ h.tema }}</b><br>
                  <span class="mut tiny">{{ h.aprendio ?? (h.estado === 'realizada' && h.asistio ? '' : '—') }}</span>
                  <button v-if="h.estado === 'realizada' && h.asistio && h.origen === 'programada'" type="button" class="lnkb" @click="abrirApr(h)">{{ h.aprendio ? 'Editar qué aprendí' : 'Escribir qué aprendí' }}</button>
                </span>
                <span>{{ h.area }}</span>
                <span>{{ h.presenta }}</span>
                <span class="mut small">{{ h.origen_txt }}</span>
                <span><span class="chip" :class="h.estado_cls">{{ h.estado_txt }}</span><br><span class="mut tiny">{{ h.motivo_txt }}</span></span>
              </div>
              <div v-if="apr[h.id]?.on" class="row fw gp8 end apr">
                <div class="fld grow1"><label :for="`a-${h.id}`">¿Qué aprendiste? <span class="req">*</span></label><input :id="`a-${h.id}`" v-model="apr[h.id]!.t" class="in" maxlength="2000"></div>
                <div class="fld grow1"><label :for="`o-${h.id}`">Observaciones</label><input :id="`o-${h.id}`" v-model="apr[h.id]!.obs" class="in" maxlength="2000" placeholder="Opcional"></div>
                <button type="button" class="btn bp" :disabled="busy" @click="guardarApr(h)">Guardar</button>
              </div>
            </template>
          </div>
        </div>
        <div v-if="!M.historico.length" class="note">Todavía no tienes capacitaciones en tu histórico.</div>
      </div>
      <div class="note">
        Cada capacitación queda con fecha, hora, tema, área, quién la presentó, qué aprendiste y observaciones. La Auxiliar administrativa, Coordinación y Gerencia programan capacitaciones; la
        Auxiliar y Gerencia descargan el Excel de todo el equipo.
      </div>
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
.end {
  align-items: flex-end;
}
.gp6 {
  gap: 6px;
}
.gp8 {
  gap: 8px;
}
.gp10 {
  gap: 10px;
}
.col,
.col6,
.col8,
.col12 {
  display: flex;
  flex-direction: column;
}
.col6 {
  gap: 6px;
}
.col8 {
  gap: 8px;
}
.col12 {
  gap: 12px;
}
.self-start {
  align-self: flex-start;
}
.grow1 {
  flex: 1;
  min-width: 200px;
}
.flt {
  font-size: 13px;
  font-weight: 700;
}
.flbl {
  font-size: 13px;
  font-weight: 700;
}
.dt {
  min-height: 38px;
  width: auto;
}
.h36 {
  min-height: 36px;
}
.small {
  font-size: 12.5px;
}
.tiny {
  font-size: 12px;
}
.mb8 {
  margin-bottom: 8px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.k-warn {
  background: #fffbf1;
  border-color: #ebcb8b;
}
.k-bad {
  background: #fff5f3;
  border-color: #e8b4ac;
}
.box {
  border: 1px solid #dadbd7;
  border-radius: 12px;
  padding: 12px;
}
.box.dim {
  opacity: 0.7;
}
.mbox {
  border: 1.5px solid #e8b4ac;
  border-radius: 10px;
  padding: 10px;
}
.prow {
  padding: 6px 0;
  border-top: 1px solid var(--cdc-border-soft);
  font-size: 13px;
  gap: 10px;
}
.tblr {
  min-width: 820px;
}
.th,
.tr {
  display: grid;
  gap: 10px;
  padding: 10px 6px;
  border-bottom: 1px solid var(--cdc-border-soft);
  font-size: 13px;
  align-items: start;
}
.th {
  padding: 8px 6px;
  border-bottom-color: var(--cdc-border);
  font-size: 10.5px;
  color: var(--cdc-muted);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.r6 {
  grid-template-columns: 150px 110px minmax(0, 1.2fr) 150px 160px minmax(0, 1fr);
}
.h6 {
  grid-template-columns: 120px minmax(0, 1.4fr) 150px 150px 170px 190px;
}
.apr {
  padding: 8px 6px 12px;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.lnkb {
  all: unset;
  cursor: pointer;
  color: var(--cdc-green);
  font-weight: 700;
  font-size: 12px;
  display: block;
  margin-top: 2px;
}
.lnkb:focus-visible {
  outline: 2px solid var(--cdc-green);
}
</style>
