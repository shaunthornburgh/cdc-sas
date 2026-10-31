<script setup lang="ts">
import type { OpcionLead } from '~/types/inmuebles'
import type { AccionSeguimiento, LeadDetail, MedioContacto, ResultadoLlamada } from '~/types/leads'

/** «Acciones sobre este lead» (C02): one inline form per action, then «¿Qué sigue?». */
const props = defineProps<{ lead: LeadDetail }>()
const emit = defineEmits<{ updated: [lead: LeadDetail] }>()
const leads = useLeads()

type F = 'llam' | 'msg' | 'opc' | 'seg' | 'obs' | 'cita'
const ACCIONES_UI: [F, string][] = [
  ['llam', 'Registrar llamada'],
  ['msg', 'Registrar mensaje'],
  ['opc', 'Enviar opciones'],
  ['seg', 'Seguimiento del cliente'],
  ['obs', 'Observación'],
  ['cita', 'Programar cita'],
]
type Last = 'llsi' | 'llno' | 'lleq' | 'msg' | 'opc' | 'obs' | 'seg' | 'cita'
const SIGUE: Partial<Record<Last, [F, string][]>> = {
  llsi: [['opc', 'Enviar opciones'], ['seg', 'Programar seguimiento'], ['cita', 'Programar cita']],
  llno: [['seg', 'Programar seguimiento (volver a llamar)'], ['msg', 'Registrar mensaje']],
  msg: [['llam', 'Registrar llamada'], ['seg', 'Programar seguimiento']],
  opc: [['seg', 'Programar seguimiento'], ['cita', 'Programar cita']],
  obs: [['seg', 'Programar seguimiento']],
}

const f = ref<F | null>(null)
const last = ref<Last | null>(null)
const message = ref<string | null>(null)
const error = ref<string | null>(null)
const busy = ref(false)

const llamada = reactive({ resultado: 'contesto' as ResultadoLlamada, duracion: '', resumen: '' })
const mensaje = reactive({ medio: 'whatsapp' as MedioContacto, texto: '' })
// «Enviar opciones» (C02): pick properties from the catalog.
const inmApi = useInmuebles()
const inms = ref<OpcionLead[] | null>(null)
const sel = ref<Set<string>>(new Set())
const verTodos = ref(false)
async function cargarInmuebles() {
  sel.value = new Set()
  verTodos.value = false
  inms.value = null
  try {
    inms.value = await inmApi.paraLead(props.lead.id)
  } catch {
    inms.value = []
  }
}
function toggleInm(id: string) {
  const s = new Set(sel.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  sel.value = s
}
const seg = reactive({ accion: 'llamar' as AccionSeguimiento, fecha: localDate(1), hora: '09:00', nota: '' })
const obs = ref('')

function open(which: F | null, preset?: Partial<typeof seg>) {
  f.value = f.value === which ? null : which
  error.value = null
  if (which !== null) message.value = null
  mensaje.texto = ''
  llamada.resumen = ''
  obs.value = ''
  if (which === 'opc' && f.value === 'opc') cargarInmuebles()
  if (which === 'seg') Object.assign(seg, { accion: 'llamar', fecha: localDate(1), hora: '09:00', nota: '' }, preset)
}
defineExpose({ open })

async function run(call: () => Promise<LeadDetail>, done: Last, ok: string) {
  error.value = null
  busy.value = true
  try {
    emit('updated', await call())
    f.value = null
    last.value = done
    message.value = ok
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    busy.value = false
  }
}

function saveLlamada() {
  if (llamada.resultado === 'contesto' && !llamada.resumen.trim()) return (error.value = 'Escribe el resumen de la llamada: qué se habló.')
  const r = llamada.resultado
  run(
    () =>
      leads.action(props.lead.id, {
        tipo: 'llamada',
        resultado: r,
        resumen: llamada.resumen.trim() || null,
        duracion_min: llamada.duracion ? Number(llamada.duracion) : null,
      }),
    r === 'contesto' ? 'llsi' : r === 'no_contesto' ? 'llno' : 'lleq',
    r === 'no_contesto'
      ? 'Llamada sin respuesta registrada. Programa el siguiente intento.'
      : r === 'numero_equivocado'
        ? 'Llamada registrada · número equivocado. Puedes marcarlo como perdido sin descuento.'
        : 'Llamada registrada en el historial.',
  )
}
function saveMensaje(tipo: 'mensaje' | 'opciones') {
  const ids = tipo === 'opciones' ? [...sel.value] : []
  if (!mensaje.texto.trim() && !ids.length)
    return (error.value = tipo === 'mensaje' ? 'Escribe el mensaje que enviaste.' : 'Elige los inmuebles o escribe qué información enviaste.')
  run(
    () => leads.action(props.lead.id, { tipo, medio: mensaje.medio, texto: mensaje.texto.trim(), inmueble_ids: ids }),
    tipo === 'mensaje' ? 'msg' : 'opc',
    tipo === 'mensaje'
      ? 'Mensaje guardado en la conversación.'
      : ids.length
        ? `${ids.length} ${ids.length === 1 ? 'opción enviada' : 'opciones enviadas'} por ${MEDIO_LABELS[mensaje.medio]} y registradas.`
        : 'Información enviada y guardada en el historial.',
  )
}
function saveSeguimiento() {
  if (!seg.fecha || !seg.hora) return (error.value = 'Elige la fecha y la hora.')
  run(
    () => leads.followup(props.lead.id, { accion: seg.accion, due_at: toIso(seg.fecha, seg.hora), nota: seg.nota.trim() || null }),
    'seg',
    `Seguimiento guardado: ${fmtCuando(toIso(seg.fecha, seg.hora))} · ${ACCION_LABELS[seg.accion]}.`,
  )
}
function saveObs() {
  if (!obs.value.trim()) return (error.value = 'Escribe la observación.')
  run(() => leads.action(props.lead.id, { tipo: 'observacion', texto: obs.value.trim() }), 'obs', 'Observación guardada en el historial.')
}
async function onCita() {
  f.value = null
  last.value = 'cita'
  message.value = 'Cita programada y enviada al asesor. Queda pendiente de aceptación.'
  emit('updated', await leads.get(props.lead.id))
}

function pickSigue(next: F) {
  if (next === 'seg' && last.value === 'llno') open('seg', { accion: 'llamar', fecha: localDate(1), hora: '09:00', nota: 'Volver a llamar' })
  else open(next)
}
</script>

<template>
  <div class="card stack">
    <div class="lbl">Acciones sobre este lead</div>
    <div class="row wrap">
      <button
        v-for="[k, t] in ACCIONES_UI"
        :key="k"
        type="button"
        class="opt"
        :class="{ on: f === k }"
        :aria-pressed="f === k"
        @click="open(k)"
      >
        {{ t }}
      </button>
    </div>

    <div v-if="f === 'llam'" class="panel">
      <b>Registrar llamada</b>
      <div class="row wrap" role="radiogroup" aria-label="Resultado de la llamada">
        <button
          v-for="[k, t] in ([['contesto', 'Contestó'], ['no_contesto', 'No contestó'], ['numero_equivocado', 'Número equivocado']] as const)"
          :key="k"
          type="button"
          class="opt"
          :class="{ on: llamada.resultado === k }"
          role="radio"
          :aria-checked="llamada.resultado === k"
          @click="llamada.resultado = k"
        >
          {{ t }}
        </button>
      </div>
      <div v-if="llamada.resultado === 'contesto'" class="g3">
        <div class="fld"><label for="la-dur">Duración (min)</label><input id="la-dur" v-model="llamada.duracion" class="in" type="number" min="0" max="600" placeholder="5"></div>
        <div class="fld span2"><label for="la-res">Resumen de la llamada <span class="req">*</span></label><input id="la-res" v-model="llamada.resumen" class="in" placeholder="Qué se habló"></div>
      </div>
      <div v-else class="mut small">Cada llamada cuenta como intento. Si no contesta, programa volver a llamar mañana (mínimo 3 llamadas en 3 días seguidos).</div>
      <div class="row"><button type="button" class="btn bp" :disabled="busy" @click="saveLlamada">Guardar llamada</button><button type="button" class="btn bs" @click="open(null)">Cancelar</button></div>
    </div>

    <div v-if="f === 'msg' || f === 'opc'" class="panel">
      <b>{{ f === 'msg' ? 'Registrar mensaje enviado' : 'Enviar opciones inmobiliarias o información' }}</b>
      <template v-if="f === 'opc'">
        <div v-if="inms === null" class="mut small">Cargando inmuebles disponibles…</div>
        <div v-else-if="!inms.length" class="note">No hay inmuebles disponibles para {{ lead.negocio ? NEGOCIO_LABELS[lead.negocio].toLowerCase() : 'este cliente' }}. Puedes escribir la información que enviaste.</div>
        <template v-else>
          <div class="mut small">Disponibles para {{ lead.negocio ? NEGOCIO_LABELS[lead.negocio].toLowerCase() : 'venta o arriendo' }}{{ lead.zona ? ` · primero los de ${lead.zona}` : '' }}</div>
          <div class="g2 picks">
            <button
              v-for="i in verTodos ? inms : inms.slice(0, 6)"
              :key="i.id"
              type="button"
              class="pick"
              :class="{ on: sel.has(i.id) }"
              :disabled="i.ya_enviado"
              :aria-pressed="sel.has(i.id)"
              @click="toggleInm(i.id)"
            >
              <span><b>{{ i.codigo }}</b> · {{ i.titulo }}<br><span class="mut tiny">{{ i.detalle }}</span></span>
              <span class="chip" :class="i.ya_enviado ? 'gray' : sel.has(i.id) ? 'ok' : 'info'">{{ i.ya_enviado ? 'Ya enviado' : sel.has(i.id) ? '✓ Elegido' : 'Elegir' }}</span>
            </button>
          </div>
          <button v-if="inms.length > 6" type="button" class="btn bs sm self-start" @click="verTodos = !verTodos">{{ verTodos ? 'Ver menos' : `Ver los ${inms.length} disponibles` }}</button>
        </template>
      </template>
      <div class="g3">
        <div class="fld">
          <label for="me-medio">Medio <span class="req">*</span></label>
          <select id="me-medio" v-model="mensaje.medio" class="in">
            <option v-for="(t, k) in MEDIO_LABELS" :key="k" :value="k">{{ t }}</option>
          </select>
        </div>
        <div class="fld span2">
          <label for="me-txt">Mensaje <span v-if="f === 'msg'" class="req">*</span></label>
          <input id="me-txt" v-model="mensaje.texto" class="in" :placeholder="f === 'msg' ? 'Lo que le escribiste al cliente' : 'Hola, te comparto estas opciones…'">
        </div>
      </div>
      <div class="row">
        <button type="button" class="btn bp" :disabled="busy" @click="saveMensaje(f === 'msg' ? 'mensaje' : 'opciones')">{{ f === 'msg' ? 'Guardar mensaje' : sel.size ? `Enviar ${sel.size} ${sel.size === 1 ? 'opción' : 'opciones'}` : 'Guardar información enviada' }}</button>
        <button type="button" class="btn bs" @click="open(null)">Cancelar</button>
      </div>
    </div>

    <div v-if="f === 'seg'" class="panel">
      <b>Seguimiento del cliente · programar una acción futura</b>
      <div class="g4">
        <div class="fld">
          <label for="sg-acc">Acción <span class="req">*</span></label>
          <select id="sg-acc" v-model="seg.accion" class="in">
            <option v-for="a in ACCIONES" :key="a" :value="a">{{ ACCION_LABELS[a] }}</option>
          </select>
        </div>
        <div class="fld"><label for="sg-f">Fecha <span class="req">*</span></label><input id="sg-f" v-model="seg.fecha" class="in" type="date" :min="localDate()"></div>
        <div class="fld"><label for="sg-h">Hora <span class="req">*</span></label><input id="sg-h" v-model="seg.hora" class="in" type="time" step="900"></div>
        <div class="fld"><label for="sg-n">Observación</label><input id="sg-n" v-model="seg.nota" class="in" placeholder="Qué hay que hacer"></div>
      </div>
      <div class="note">Queda en «Próximas acciones» y en «Mis recordatorios de hoy». Cuando la hagas, márcala como realizada y queda en el historial.</div>
      <div class="row"><button type="button" class="btn bp" :disabled="busy" @click="saveSeguimiento">Programar seguimiento</button><button type="button" class="btn bs" @click="open(null)">Cancelar</button></div>
    </div>

    <div v-if="f === 'obs'" class="panel">
      <b>Registrar observación</b>
      <textarea v-model="obs" class="in" placeholder="Escribe la observación" aria-label="Observación" />
      <div class="row"><button type="button" class="btn bp" :disabled="busy" @click="saveObs">Guardar observación</button><button type="button" class="btn bs" @click="open(null)">Cancelar</button></div>
    </div>

    <CitaScheduler v-if="f === 'cita'" :lead-id="lead.id" :negocio="lead.negocio" @cancel="open(null)" @created="onCita" />

    <div v-if="message" class="note ok sigue">
      <b>{{ message }}</b>
      <div v-if="last && SIGUE[last]" class="row wrap">
        <span class="sigue-lbl">¿Qué sigue?</span>
        <button v-for="[k, t] in SIGUE[last]" :key="k" type="button" class="btn bs sm" @click="pickSigue(k)">{{ t }}</button>
      </div>
    </div>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.wrap {
  flex-wrap: wrap;
  gap: 8px;
}
.span2 {
  grid-column: span 2;
}
.small {
  font-size: 12px;
}
.sigue {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sigue-lbl {
  font-weight: 700;
}
@media (max-width: 640px) {
  .span2 {
    grid-column: auto;
  }
}
.picks {
  gap: 8px;
}
.self-start {
  align-self: flex-start;
}
.tiny {
  font-size: 12px;
}
</style>
