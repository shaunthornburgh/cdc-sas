<script setup lang="ts">
import type { Cita } from '~/types/leads'

/** One cita in «Control de citas» (C03): status, alert, history and the actions it allows. */
const props = defineProps<{ cita: Cita }>()
const emit = defineEmits<{ changed: [cita: Cita] }>()
const leads = useLeads()

type Form = 'asignar' | 'reprogramar' | 'cancelar' | 'rechazo' | 'realizada' | null
const form = ref<Form>(null)
const asesorId = ref<string | null>(null)
const fecha = ref('')
const hora = ref('')
const motivo = ref('')
const error = ref<string | null>(null)
const message = ref<string | null>(null)
const busy = ref(false)

const c = computed(() => props.cita)
const activa = computed(() => ['pendiente', 'aceptada', 'rechazada'].includes(c.value.estado))
const yaPaso = computed(() => minutesUntil(c.value.scheduled_at) < 0)
const chip = computed(() =>
  c.value.requiere_accion && c.value.estado === 'pendiente'
    ? { t: minutesUntil(c.value.scheduled_at) < 0 ? 'Sin aceptar · ya pasó la hora' : `Sin aceptar · faltan ${minutesUntil(c.value.scheduled_at)} min`, cls: 'bad' }
    : citaChip(c.value.estado, c.value.asesor?.full_name),
)
const alerta = computed(() => citaAlerta(c.value))
const newAt = computed(() => (fecha.value && hora.value ? toIso(fecha.value, hora.value) : null))

function toggle(f: Form) {
  form.value = form.value === f ? null : f
  error.value = null
  motivo.value = ''
  if (f === 'reprogramar') {
    const d = new Date(c.value.scheduled_at)
    fecha.value = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota' }).format(d)
    hora.value = fmtHora(c.value.scheduled_at).padStart(5, '0')
  }
}

async function run(action: () => Promise<Cita>, ok: string) {
  error.value = null
  busy.value = true
  try {
    const updated = await action()
    form.value = null
    message.value = ok
    emit('changed', updated)
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    busy.value = false
  }
}

const need = (fn: () => void) => () => (motivo.value.trim() ? fn() : (error.value = 'Escribe el motivo.'))
const aceptar = () => run(() => leads.citaStatus(c.value.id, 'aceptada'), 'Aceptación registrada.')
const rechazar = need(() => run(() => leads.citaStatus(c.value.id, 'rechazada', motivo.value), 'Rechazo registrado. Asigna otro asesor.'))
const cancelar = need(() => run(() => leads.citaStatus(c.value.id, 'cancelada', motivo.value), 'Cita cancelada. El lead vuelve a «En gestión».'))
const realizada = () => run(() => leads.citaStatus(c.value.id, 'realizada', motivo.value || null), 'Cita marcada como realizada.')
const asignar = () =>
  asesorId.value
    ? run(() => leads.citaReassign(c.value.id, asesorId.value!), 'Cita enviada al asesor. Queda pendiente de aceptación.')
    : (error.value = 'Elige un asesor libre.')
const reprogramar = need(() =>
  newAt.value
    ? run(() => leads.citaReschedule(c.value.id, newAt.value!, motivo.value), 'Cita reprogramada. El asesor debe aceptarla de nuevo.')
    : (error.value = 'Elige la nueva fecha y hora.'),
)
</script>

<template>
  <div class="card stack" :class="{ alert: c.requiere_accion }">
    <div class="sb">
      <div>
        <b class="cita-title">{{ c.code }} · {{ CITA_TIPO_CORTO[c.tipo] }}</b>
        <div class="mut sub">
          {{ fmtCuando(c.scheduled_at) }}<template v-if="c.inmueble"> · {{ c.inmueble }}</template>
          · {{ c.lead.full_name }} · lead <NuxtLink :to="`/leads/${c.lead.id}`">{{ c.lead.code }}</NuxtLink>
        </div>
      </div>
      <span class="chip big" :class="chip.cls">{{ chip.t }}</span>
    </div>

    <div v-if="alerta" class="note bad"><b>{{ alerta }}</b></div>
    <div v-if="c.notas" class="mut small">Observaciones: {{ c.notas }}</div>

    <div class="row hist">
      <span v-for="(h, i) in c.historial" :key="i" class="chip gray" :title="h.detalle ?? undefined">
        {{ fmtCuando(h.created_at) }} · {{ h.titulo.replace(`Cita ${c.code} `, '') }}
      </span>
    </div>

    <template v-if="activa">
      <div class="row actions">
        <template v-if="c.estado === 'pendiente'">
          <button type="button" class="btn bs sm" :disabled="busy" @click="aceptar">Aceptada por el asesor</button>
          <button type="button" class="opt sm-opt" :class="{ on: form === 'rechazo' }" @click="toggle('rechazo')">Rechazada por el asesor</button>
        </template>
        <button v-if="c.estado === 'aceptada' && yaPaso" type="button" class="opt sm-opt" :class="{ on: form === 'realizada' }" @click="toggle('realizada')">Marcar realizada</button>
        <button type="button" class="opt sm-opt" :class="{ on: form === 'asignar' }" @click="toggle('asignar')">Asignar otro asesor</button>
        <button type="button" class="opt sm-opt" :class="{ on: form === 'reprogramar' }" @click="toggle('reprogramar')">Reprogramar</button>
        <button type="button" class="btn br sm" @click="toggle('cancelar')">Cancelar cita</button>
      </div>
      <div v-if="c.estado === 'pendiente' && form !== 'rechazo'" class="mut small">
        Mientras el asesor no tenga su propia pantalla, registra aquí lo que respondió.
      </div>

      <div v-if="form === 'asignar'" class="panel">
        <div class="lbl">Asesores con la actividad y libres a esa hora</div>
        <AsesorPicker v-model="asesorId" :tipo="c.tipo" :scheduled-at="c.scheduled_at" :exclude="c.id" />
        <div><button type="button" class="btn bp" :disabled="busy || !asesorId" @click="asignar">Enviar al asesor</button></div>
      </div>

      <div v-if="form === 'reprogramar'" class="panel">
        <div class="g3">
          <div class="fld"><label :for="`rf-${c.id}`">Nueva fecha <span class="req">*</span></label><input :id="`rf-${c.id}`" v-model="fecha" class="in" type="date" :min="localDate()"></div>
          <div class="fld"><label :for="`rh-${c.id}`">Nueva hora <span class="req">*</span></label><input :id="`rh-${c.id}`" v-model="hora" class="in" type="time" step="900"></div>
          <div class="fld"><label :for="`rm-${c.id}`">Motivo <span class="req">*</span></label><input :id="`rm-${c.id}`" v-model="motivo" class="in" placeholder="Ej.: el cliente pidió cambiar el día"></div>
        </div>
        <div><button type="button" class="btn bp" :disabled="busy" @click="reprogramar">Reprogramar</button></div>
      </div>

      <div v-if="form === 'cancelar' || form === 'rechazo' || form === 'realizada'" class="panel">
        <div class="fld">
          <label :for="`mo-${c.id}`">
            {{ form === 'realizada' ? 'Resultado de la cita' : 'Motivo' }}
            <span v-if="form !== 'realizada'" class="req">*</span>
          </label>
          <input
            :id="`mo-${c.id}`"
            v-model="motivo"
            class="in"
            :placeholder="form === 'cancelar' ? 'Ej.: el cliente canceló' : form === 'rechazo' ? 'Ej.: choque con otra cita' : 'Ej.: le gustó, pasa a negocio'"
          >
        </div>
        <div>
          <button v-if="form === 'cancelar'" type="button" class="btn br" :disabled="busy" @click="cancelar">Confirmar cancelación</button>
          <button v-else-if="form === 'rechazo'" type="button" class="btn br" :disabled="busy" @click="rechazar">Registrar rechazo</button>
          <button v-else type="button" class="btn bp" :disabled="busy" @click="realizada">Guardar resultado</button>
        </div>
      </div>
    </template>

    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
    <div v-if="message" class="note ok" role="status"><b>{{ message }}</b></div>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.card.alert {
  border: 2px solid var(--cdc-bad);
}
.cita-title {
  font-size: 16px;
}
.sub {
  font-size: 13px;
}
.small {
  font-size: 12px;
}
.chip.big {
  font-size: 12.5px;
  padding: 5px 12px;
}
.hist {
  flex-wrap: wrap;
  gap: 6px;
}
.actions {
  flex-wrap: wrap;
  gap: 8px;
}
.sm-opt {
  min-height: 32px;
  padding: 0 10px;
  font-size: 12.5px;
}
</style>
