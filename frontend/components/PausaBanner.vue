<script setup lang="ts">
import type { PaAhora } from '~/types/pausas'

/**
 * G-041 / G-060: the active-pause reminder on each person's Inicio. It shows only while the
 * pause is on screen (scheduled time + configured minutes) and goes away on «Realizada».
 */
const emit = defineEmits<{ marcada: [] }>()
const api = usePausas()
const data = ref<PaAhora | null>(null)
const hecho = ref('')
const err = ref('')
const busy = ref(false)
async function cargar() {
  try {
    data.value = await api.ahora()
  } catch {
    data.value = null
  }
}
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  cargar()
  timer = setInterval(cargar, 60_000)
})
onBeforeUnmount(() => clearInterval(timer))
async function realizada() {
  busy.value = true
  err.value = ''
  try {
    const r = await api.realizada()
    hecho.value = `✓ Pausa activa de la ${r.turno === 'tarde' ? 'tarde' : 'mañana'} realizada · ${fmtHora(r.realizada_at)}`
    await cargar()
    emit('marcada')
  } catch (e) {
    err.value = apiErrorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="data?.activa" class="card pausa" role="status">
    <span class="txt">
      <b class="t15">Es hora de tu {{ data.activa.titulo }}</b><br>
      <span class="mut tiny">{{ data.mensaje }}<br>El aviso se ve {{ data.minutos }} minutos desde la hora programada · al terminar toca «Realizada»</span>
      <span v-if="err" class="chip bad">{{ err }}</span>
    </span>
    <button type="button" class="btn bp h44" :disabled="busy" @click="realizada">Realizada</button>
  </div>
  <div v-else-if="hecho" class="note ok"><b>{{ hecho }}</b></div>
</template>

<style scoped>
.pausa {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  border: 2px solid var(--cdc-green-lime);
  background: #f6fbef;
}
.txt {
  flex: 1;
  min-width: 170px;
}
.t15 {
  font-size: 15px;
}
.tiny {
  font-size: 12px;
}
.h44 {
  min-height: 44px;
}
</style>
