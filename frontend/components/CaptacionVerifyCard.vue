<script setup lang="ts">
import type { Captacion, MotivoRechazoCaptacion } from '~/types/captaciones'

/** One captación in «Verificar captaciones» (prototype K12). */
const props = defineProps<{ cap: Captacion }>()
const emit = defineEmits<{ changed: [cap: Captacion, msg: string] }>()
const caps = useCaptaciones()

const rechazoOpen = ref(false)
const motivo = ref<MotivoRechazoCaptacion | null>(null)
const observacion = ref('')
const ask = ref<'a' | 'r' | null>(null)
const busy = ref(false)
const error = ref<string | null>(null)

const c = computed(() => props.cap)
const estado = computed(() => CAPTACION_ESTADO[c.value.estado])
const mapa = computed(() => mapaUrl(c.value))

async function confirm() {
  busy.value = true
  error.value = null
  try {
    const aprobar = ask.value === 'a'
    const updated = await caps.verificar(c.value.id, aprobar ? 'aprobada' : 'rechazada', aprobar ? null : motivo.value, aprobar ? null : observacion.value || null)
    emit(
      'changed',
      updated,
      aprobar
        ? `${c.value.code} aprobada: ya suma en la captación de ${c.value.asesor.full_name}. Quedó en el registro de cambios.`
        : `${c.value.code} rechazada: se avisó a ${c.value.asesor.full_name}. Quedó en el registro de cambios.`,
    )
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    busy.value = false
    ask.value = null
  }
}
</script>

<template>
  <div class="card stack">
    <div class="sb">
      <div>
        <NuxtLink :to="`/captaciones/${c.id}`" class="title">{{ c.code }} · {{ c.codigo_inmueble }} · {{ NEGOCIO_LABELS[c.negocio] }}</NuxtLink>
        <div class="mut sub">{{ c.asesor.full_name }} · {{ fmtCuando(c.enviada_at) }} · {{ modoTxt(c) }}<template v-if="c.reenvios"> · corregida {{ c.reenvios }} {{ c.reenvios === 1 ? 'vez' : 'veces' }}</template></div>
      </div>
      <span class="chip big" :class="estado.cls">{{ estado.t }}</span>
    </div>

    <div class="kv">
      <span class="mut">Dirección enviada</span><b>{{ c.direccion }}</b>
      <span class="mut">Ubicación del asesor</span>
      <b>{{ ubicacionTxt(c) }}<template v-if="mapa"> · <a :href="mapa" target="_blank" rel="noopener noreferrer">ver en el mapa</a></template></b>
      <template v-if="c.modo === 'completo'">
        <span class="mut">Inmueble</span>
        <b>{{ c.tipo_inmueble ? TIPO_INMUEBLE_LABELS[c.tipo_inmueble] : '—' }} · {{ c.barrio }}, {{ c.municipio }} · {{ fmtCOP(c.precio) }}</b>
      </template>
    </div>

    <div v-if="c.estado !== 'por_verificar'" class="note">{{ captacionDetalle(c) }}</div>
    <div v-else-if="c.reenvios" class="note warn">{{ c.eventos.at(-1)?.detalle }}</div>

    <template v-if="c.estado === 'por_verificar'">
      <div class="mut hint">Revisa en la otra plataforma que el código exista y que corresponda a esa dirección.</div>
      <div class="row">
        <button type="button" class="btn bp" @click="ask = 'a'">Aprobar</button>
        <button type="button" class="opt" :class="{ on: rechazoOpen }" @click="rechazoOpen = !rechazoOpen">Rechazar</button>
      </div>
      <div v-if="rechazoOpen" class="panel">
        <div class="lbl">Motivo del rechazo</div>
        <div class="row wrap" role="radiogroup" aria-label="Motivo del rechazo">
          <button v-for="m in MOTIVOS_RECHAZO" :key="m" type="button" class="opt" :class="{ on: motivo === m, bajo: motivo === m }" role="radio" :aria-checked="motivo === m" @click="motivo = m">
            {{ MOTIVO_RECHAZO_LABELS[m] }}
          </button>
        </div>
        <input v-model="observacion" class="in" placeholder="Observación para el asesor (opcional)" aria-label="Observación">
        <div><button type="button" class="btn br" :disabled="!motivo" @click="ask = 'r'">Rechazar captación</button></div>
      </div>
    </template>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>

    <ConfirmDialog
      v-if="ask"
      :title="ask === 'a' ? `¿Aprobar ${c.code}?` : `¿Rechazar ${c.code}?`"
      confirm-label="Sí, confirmar"
      :danger="ask === 'r'"
      :busy="busy"
      @confirm="confirm"
      @cancel="ask = null"
    >
      <template v-if="ask === 'a'">Suma una captación de {{ NEGOCIO_LABELS[c.negocio].toLowerCase() }} a {{ c.asesor.full_name }}.</template>
      <template v-else>
        {{ c.asesor.full_name }} recibe el motivo ({{ motivo ? MOTIVO_RECHAZO_LABELS[motivo].toLowerCase() : '' }}). No le cuenta como captación hasta que la corrija y la apruebes.
      </template>
    </ConfirmDialog>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.title {
  font-size: 16px;
  font-weight: 700;
  color: var(--cdc-text);
  text-decoration: none;
}
.title:hover {
  color: var(--cdc-green);
  text-decoration: underline;
}
.sub {
  font-size: 13px;
}
.chip.big {
  font-size: 12.5px;
  padding: 5px 12px;
}
.kv {
  font-size: 13px;
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 4px 10px;
}
.hint {
  font-size: 12.5px;
}
.wrap {
  flex-wrap: wrap;
}
.opt.on.bajo {
  background: var(--cdc-bad);
  border-color: var(--cdc-bad);
}
@media (max-width: 640px) {
  .kv {
    grid-template-columns: minmax(0, 1fr);
  }
  .kv b {
    margin-bottom: 6px;
  }
}
</style>
