<script setup lang="ts">
import type { Cita, TipoCita, TipoNegocio } from '~/types/leads'

/** «Programar cita» from the lead (C02): type, day and time, an available asesor, notes. */
const props = defineProps<{ leadId: string; negocio: TipoNegocio | null }>()
const emit = defineEmits<{ cancel: []; created: [cita: Cita] }>()
const leads = useLeads()

const tipo = ref<TipoCita>(props.negocio === 'venta' ? 'visita_venta' : 'visita_arriendo')
const fecha = ref(localDate(1))
const hora = ref('10:00')
const asesorId = ref<string | null>(null)
const inmueble = ref('')
const notas = ref('')
const error = ref<string | null>(null)
const saving = ref(false)

const scheduledAt = computed(() => (fecha.value && hora.value ? toIso(fecha.value, hora.value) : null))
const tipoNota = computed(() =>
  CITA_REQUISITO[tipo.value]
    ? `Solo pueden recibirla asesores con ${CITA_REQUISITO[tipo.value]} activo.`
    : 'La puede recibir cualquier asesor libre.',
)

async function save() {
  if (!scheduledAt.value || !asesorId.value) {
    error.value = 'Elige el día, la hora y un asesor libre.'
    return
  }
  error.value = null
  saving.value = true
  try {
    emit(
      'created',
      await leads.createCita({
        lead_id: props.leadId,
        tipo: tipo.value,
        scheduled_at: scheduledAt.value,
        asesor_id: asesorId.value,
        inmueble: inmueble.value.trim() || null,
        notas: notas.value.trim() || null,
      }),
    )
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="panel">
    <b>Programar cita · elige el tipo, el día y un asesor libre</b>
    <div class="fld">
      <span class="fld-label">Tipo de cita <span class="req">*</span></span>
      <div class="row opts" role="radiogroup" aria-label="Tipo de cita">
        <button
          v-for="t in CITA_TIPOS"
          :key="t"
          type="button"
          class="opt"
          :class="{ on: tipo === t }"
          role="radio"
          :aria-checked="tipo === t"
          @click="tipo = t"
        >
          {{ CITA_TIPO_LABELS[t] }}
        </button>
      </div>
      <span class="mut small">{{ tipoNota }}</span>
    </div>
    <div class="g4">
      <div class="fld"><label for="ct-fecha">Fecha <span class="req">*</span></label><input id="ct-fecha" v-model="fecha" class="in" type="date" :min="localDate()"></div>
      <div class="fld"><label for="ct-hora">Hora <span class="req">*</span></label><input id="ct-hora" v-model="hora" class="in" type="time" step="900"></div>
    </div>
    <div class="lbl">Asesor</div>
    <AsesorPicker v-model="asesorId" :tipo="tipo" :scheduled-at="scheduledAt" />
    <div class="g2">
      <div class="fld"><label for="ct-inm">Inmueble</label><input id="ct-inm" v-model="inmueble" class="in" placeholder="INM-0333 · Apto Laureles"></div>
      <div class="fld"><label for="ct-notas">Observaciones para el asesor</label><input id="ct-notas" v-model="notas" class="in" placeholder="Prefiere visitas después de las 3 p. m."></div>
    </div>
    <div class="note">La cita le llega al asesor «Pendiente de aceptación». Si falta 1 hora y nadie la ha aceptado, aparece en «Citas que requieren acción».</div>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
    <div class="row">
      <button type="button" class="btn bp" :disabled="saving || !asesorId" @click="save">
        {{ saving ? 'Programando…' : 'Programar y enviar al asesor' }}
      </button>
      <button type="button" class="btn bs" @click="emit('cancel')">Cancelar</button>
    </div>
  </div>
</template>

<style scoped>
.opts {
  flex-wrap: wrap;
  gap: 6px;
}
.small {
  font-size: 12px;
}
</style>
