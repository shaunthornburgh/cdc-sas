<script setup lang="ts">
import type { Captacion } from '~/types/captaciones'

/** One row of «Mis captaciones enviadas» (prototype M15): correct & resend, mark published. */
const props = defineProps<{ cap: Captacion }>()
const emit = defineEmits<{ changed: [cap: Captacion, msg: string] }>()
const caps = useCaptaciones()

const c = computed(() => props.cap)
const estado = computed(() => CAPTACION_ESTADO[c.value.estado])
const editing = ref(false)
const codigo = ref('')
const direccion = ref('')
const error = ref<string | null>(null)
const busy = ref(false)

function startEdit() {
  codigo.value = c.value.codigo_inmueble
  direccion.value = c.value.direccion
  error.value = null
  editing.value = true
}

async function run(fn: () => Promise<Captacion>, msg: string) {
  busy.value = true
  error.value = null
  try {
    emit('changed', await fn(), msg)
    editing.value = false
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    busy.value = false
  }
}
function reenviar() {
  if (codigo.value.trim().toUpperCase() === c.value.codigo_inmueble && direccion.value.trim() === c.value.direccion)
    return (error.value = 'Cambia el código o la dirección antes de volver a enviar.')
  run(() => caps.reenviar(c.value.id, codigo.value, direccion.value), `Enviada a verificación otra vez: ${c.value.code}.`)
}
</script>

<template>
  <div class="item">
    <div class="sb">
      <NuxtLink :to="`/captaciones/${c.id}`" class="t">{{ c.code }} · {{ c.codigo_inmueble }} · {{ NEGOCIO_LABELS[c.negocio] }}</NuxtLink>
      <span class="chip" :class="estado.cls">{{ estado.t }}</span>
    </div>
    <span class="mut small">{{ c.direccion }} · {{ fmtCuando(c.enviada_at) }}</span>
    <span class="small">{{ captacionDetalle(c) }}</span>

    <button v-if="c.estado === 'rechazada' && !editing" type="button" class="btn bp sm self-start" @click="startEdit">Corregir y volver a enviar</button>
    <div v-if="editing" class="fix">
      <div class="fix-note"><b>Corrige los datos.</b> Motivo del rechazo: {{ c.motivo_rechazo ? MOTIVO_RECHAZO_LABELS[c.motivo_rechazo].toLowerCase() : '' }}.</div>
      <div class="fld"><label :for="`fc-${c.id}`">Código de la propiedad <span class="req">*</span></label><input :id="`fc-${c.id}`" v-model="codigo" class="in"></div>
      <div class="fld"><label :for="`fd-${c.id}`">Dirección <span class="req">*</span></label><input :id="`fd-${c.id}`" v-model="direccion" class="in"></div>
      <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
      <div class="g2">
        <button type="button" class="btn bs" @click="editing = false">Cancelar</button>
        <button type="button" class="btn bp" :disabled="busy" @click="reenviar">Volver a enviar</button>
      </div>
    </div>

    <div v-if="c.estado === 'aprobada'" class="sb small">
      <span class="chip" :class="c.publicada_at ? 'ok' : 'warn'">{{ c.publicada_at ? `✓ Publicada ${fmtCuando(c.publicada_at)}` : 'Aprobada · aún no publicada' }}</span>
      <button v-if="!c.publicada_at" type="button" class="btn bs sm" :disabled="busy" @click="run(() => caps.publicar(c.id), `${c.code} marcada como publicada.`)">Marcar publicada</button>
    </div>
    <div v-if="error && !editing" class="note bad" role="alert"><b>{{ error }}</b></div>
  </div>
</template>

<style scoped>
.item {
  padding: 11px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.item:last-of-type {
  border-bottom: 0;
}
.t {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--cdc-text);
  text-decoration: none;
}
.t:hover {
  color: var(--cdc-green);
}
.small {
  font-size: 12px;
}
.self-start {
  align-self: flex-start;
}
.fix {
  background: var(--cdc-warn-bg);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.fix-note {
  font-size: 12.5px;
  color: #5c3b00;
}
</style>
