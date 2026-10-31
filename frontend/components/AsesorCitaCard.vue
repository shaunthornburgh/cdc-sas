<script setup lang="ts">
import type { AsesorCita } from '~/types/asesor'

/** One cita on the asesor side (prototype M03): steps, details and the answer it needs. */
const props = defineProps<{ cita: AsesorCita; readonly?: boolean }>()
const emit = defineEmits<{ changed: [cita: AsesorCita, msg: string] }>()
const asesor = useAsesor()

const c = computed(() => props.cita)
const ask = ref<'aceptar' | 'tomar' | null>(null)
const form = ref<'rechazar' | 'cerrar' | null>(null)
const motivo = ref('')
const texto = ref('')
const busy = ref(false)
const error = ref<string | null>(null)

const PASOS = ['Pendiente de aceptación', 'Aceptada', 'Realizada']
const pasoIdx = computed(() => ({ pendiente: 0, rechazada: 0, aceptada: 1, realizada: 2, cancelada: -1 })[c.value.estado])
const disponible = computed(() => !c.value.mia && c.value.puede_tomar)
const chip = computed(() => (disponible.value ? { t: 'Disponible para tomar', cls: 'warn' } : citaChip(c.value.estado)))

async function run(fn: () => Promise<AsesorCita>, msg: string) {
  busy.value = true
  error.value = null
  try {
    emit('changed', await fn(), msg)
    form.value = null
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    busy.value = false
    ask.value = null
  }
}
const aceptar = () => run(() => asesor.aceptar(c.value.id), `Aceptaste ${c.value.code}. Recibirás un recordatorio 1 hora antes.`)
const tomar = () => run(() => asesor.tomar(c.value.id), `Tomaste ${c.value.code}: ahora eres el responsable y queda aceptada.`)
function rechazar() {
  if (!motivo.value || !texto.value.trim()) return (error.value = 'Elige el motivo y escribe la observación para rechazar.')
  run(() => asesor.rechazar(c.value.id, motivo.value, texto.value), `Rechazaste ${c.value.code}. Los asesores disponibles y Atención y Preventa recibieron el aviso.`)
}
function cerrar() {
  if (!texto.value.trim()) return (error.value = 'Escribe qué pasó en la visita.')
  run(() => asesor.cerrar(c.value.id, texto.value), `${c.value.code} cerrada. El resultado quedó en el historial del cliente.`)
}
function open(f: 'rechazar' | 'cerrar') {
  form.value = form.value === f ? null : f
  motivo.value = ''
  texto.value = ''
  error.value = null
}
</script>

<template>
  <div :id="`cita-${c.id}`" class="card stack" :class="{ focus: c.puede_aceptar || disponible || c.puede_cerrar }">
    <div class="sb">
      <b class="title">{{ c.code }} · {{ CITA_TIPO_CORTO[c.tipo] }}</b>
      <span class="chip" :class="chip.cls">{{ chip.t }}</span>
    </div>
    <div v-if="pasoIdx >= 0 && !disponible" class="stp">
      <div v-for="(t, i) in PASOS" :key="t" :class="{ on: i === pasoIdx, done: i < pasoIdx }">{{ t }}</div>
    </div>

    <div class="kv">
      <span class="mut">Inmueble</span><b>{{ c.inmueble ?? '—' }}</b>
      <span class="mut">Cliente</span><b>{{ c.cliente }}</b>
      <span class="mut">Fecha y hora</span><b>{{ fmtCuando(c.scheduled_at) }}</b>
      <span class="mut">Tipo de cita</span><b>{{ CITA_TIPO_LABELS[c.tipo] }}</b>
      <span class="mut">Programada por</span><b>{{ c.programada_por ?? '—' }}</b>
      <span class="mut">Llegó desde</span><b>{{ c.fuente }}</b>
      <span v-if="c.notas" class="mut">Observaciones</span><b v-if="c.notas">{{ c.notas }}</b>
      <template v-if="c.motivo && (c.estado === 'realizada' || c.estado === 'cancelada')">
        <span class="mut">{{ c.estado === 'realizada' ? 'Resultado' : 'Motivo' }}</span><b>{{ c.motivo }}</b>
      </template>
    </div>

    <template v-if="!readonly">
      <template v-if="c.puede_aceptar">
        <div class="note warn"><b>Responde lo antes posible.</b> Si a 1 hora de la cita nadie la ha aceptado, Atención y Preventa recibe una alerta.</div>
        <div class="g2 pair">
          <button type="button" class="btn bp" :disabled="busy" @click="ask = 'aceptar'">Aceptar cita</button>
          <button type="button" class="btn br" @click="open('rechazar')">Rechazar cita</button>
        </div>
      </template>
      <template v-else-if="disponible">
        <div class="note warn">
          <b>El asesor ha rechazado esta cita. ¿Deseas tomar esta cita?</b><br>
          La rechazó {{ c.asesor_name ?? 'otro asesor' }}{{ c.motivo ? ` (motivo: ${c.motivo})` : '' }}. El primero que la tome queda como responsable.
        </div>
        <button type="button" class="btn bp" :disabled="busy" @click="ask = 'tomar'">Tomar cita</button>
      </template>
      <template v-else-if="c.puede_cerrar">
        <div class="note">La hora de la cita ya pasó. Cuéntanos qué pasó en la visita para cerrarla.</div>
        <button v-if="form !== 'cerrar'" type="button" class="btn bp" @click="open('cerrar')">Cerrar cita</button>
      </template>
      <div v-else-if="c.estado === 'aceptada'" class="note ok"><b>Aceptada.</b> Recibirás un recordatorio 1 hora antes.</div>

      <div v-if="form === 'rechazar'" class="panel">
        <div class="fld">
          <label :for="`rm-${c.id}`">Motivo del rechazo <span class="req">*</span></label>
          <select :id="`rm-${c.id}`" v-model="motivo" class="in">
            <option value="" disabled>Elige un motivo…</option>
            <option v-for="m in MOTIVOS_RECHAZO_CITA" :key="m">{{ m }}</option>
          </select>
        </div>
        <div class="fld">
          <label :for="`ro-${c.id}`">Observación <span class="req">*</span></label>
          <textarea :id="`ro-${c.id}`" v-model="texto" class="in" placeholder="Explica brevemente" />
        </div>
        <div class="g2 pair">
          <button type="button" class="btn bs" @click="form = null">Volver</button>
          <button type="button" class="btn br" :disabled="busy" @click="rechazar">Rechazar</button>
        </div>
      </div>
      <div v-if="form === 'cerrar'" class="panel">
        <div class="fld">
          <label :for="`rc-${c.id}`">Notas de la cita <span class="req">*</span></label>
          <textarea :id="`rc-${c.id}`" v-model="texto" class="in" placeholder="Qué pasó en la visita" />
        </div>
        <div class="g2 pair">
          <button type="button" class="btn bs" @click="form = null">Volver</button>
          <button type="button" class="btn bp" :disabled="busy" @click="cerrar">Cerrar cita</button>
        </div>
      </div>
    </template>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>

    <ConfirmDialog
      v-if="ask"
      :title="ask === 'aceptar' ? `¿Aceptar ${c.code}?` : `¿Tomar ${c.code}?`"
      :confirm-label="ask === 'aceptar' ? 'Sí, aceptar' : 'Sí, tomarla'"
      :busy="busy"
      @confirm="ask === 'aceptar' ? aceptar() : tomar()"
      @cancel="ask = null"
    >
      {{ CITA_TIPO_LABELS[c.tipo] }} · {{ fmtCuando(c.scheduled_at) }} · {{ c.cliente }}. Queda en tu agenda como aceptada.
    </ConfirmDialog>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.title {
  font-size: 15px;
}
.kv {
  font-size: 13px;
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 4px 8px;
}
.pair {
  grid-template-columns: 1fr 1fr;
}
</style>
