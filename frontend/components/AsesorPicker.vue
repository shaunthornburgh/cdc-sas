<script setup lang="ts">
import type { AsesorOption, TipoCita } from '~/types/leads'

/** Asesores for a cita type and time: who has the activity and who is free (C02 / C03). */
const props = defineProps<{ tipo: TipoCita; scheduledAt: string | null; exclude?: string }>()
const model = defineModel<string | null>({ required: true })

const leads = useLeads()
const options = ref<AsesorOption[] | null>(null)
const error = ref<string | null>(null)

async function load() {
  error.value = null
  try {
    options.value = await leads.asesores(props.tipo, props.scheduledAt ?? undefined, props.exclude)
    const current = options.value.find((o) => o.id === model.value)
    if (current && (!current.elegible || current.ocupado_con)) model.value = null
  } catch (e) {
    error.value = apiErrorMessage(e)
  }
}
watch(() => [props.tipo, props.scheduledAt], load, { immediate: true })

const ACT = { captacion: 'Captación', ventas: 'Ventas', arriendos: 'Arriendos' } as const

function estado(o: AsesorOption) {
  if (!o.elegible) return { t: `No tiene ${CITA_REQUISITO[props.tipo]}`, cls: 'gray' }
  if (o.ocupado_con) return { t: `Ocupado · ${o.ocupado_con.code} ${fmtHora(o.ocupado_con.scheduled_at)}`, cls: 'gray' }
  return { t: props.scheduledAt ? 'Libre a esa hora' : 'Elige la hora', cls: props.scheduledAt ? 'ok' : 'gray' }
}
</script>

<template>
  <div>
    <p v-if="options === null && !error" class="mut small">Cargando asesores…</p>
    <div v-if="error" class="note bad"><b>{{ error }}</b></div>
    <div v-else-if="options && !options.length" class="note">No hay asesores activos con actividades comerciales.</div>
    <div v-else class="g3">
      <button
        v-for="o in options"
        :key="o.id"
        type="button"
        class="pick"
        :class="{ on: model === o.id }"
        :aria-pressed="model === o.id"
        :disabled="!o.elegible || !!o.ocupado_con"
        @click="model = o.id"
      >
        <span>
          <b>{{ o.full_name }}</b><br>
          <span class="small">{{ o.actividades.map((a) => ACT[a]).join(' + ') }}</span>
        </span>
        <span class="chip" :class="estado(o).cls">{{ estado(o).t }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.small {
  font-size: 12px;
}
</style>
