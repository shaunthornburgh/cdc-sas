<script setup lang="ts">
import type { LeadDetail, MotivoPerdida } from '~/types/leads'

/** «¿Marcar el lead como perdido?» (C01 / C02): reason + whether it costs performance points. */
const props = defineProps<{ leadId: string; title: string }>()
const emit = defineEmits<{ done: [lead: LeadDetail]; cancel: [] }>()

const leads = useLeads()
const detail = ref<LeadDetail | null>(null)
const motivo = ref<MotivoPerdida | ''>('')
const error = ref<string | null>(null)
const busy = ref(false)

onMounted(async () => {
  try {
    detail.value = await leads.get(props.leadId)
  } catch (e) {
    error.value = apiErrorMessage(e)
  }
})

/** Same rule as the API (G-045): 3 calls on 3 consecutive days, wrong number never counts. */
const aviso = computed(() => {
  if (!motivo.value || !detail.value) return null
  const n = detail.value.llamadas
  const d = detail.value.llamadas_dias_seguidos
  if (motivo.value === 'numero_equivocado') return { cls: 'ok', t: '«Número equivocado» nunca descuenta.' }
  if (motivo.value === 'no_contesta') {
    if (n >= 3 && d >= 3) return { cls: 'ok', t: `No descuenta: tiene ${llamadasTxt(n)} en ${d} días seguidos.` }
    return {
      cls: 'warn',
      t: `Este lead tiene ${llamadasTxt(n)} registradas. Si eliges «No contesta», descuenta: para que no descuente se necesitan mínimo 3 llamadas en 3 días seguidos.`,
    }
  }
  return { cls: 'warn', t: 'Este motivo descuenta en el rendimiento.' }
})

async function confirm() {
  if (!motivo.value) {
    error.value = 'Elige un motivo.'
    return
  }
  busy.value = true
  error.value = null
  try {
    emit('done', await leads.stage(props.leadId, 'perdido', motivo.value))
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <ConfirmDialog
    :title="`¿Marcar ${title} como perdido?`"
    confirm-label="Sí, marcar perdido"
    danger
    :busy="busy || !detail"
    @confirm="confirm"
    @cancel="emit('cancel')"
  >
    <div class="body">
      <span>El lead sale de «Mis leads» y queda archivado para Gerencia con el motivo, la fecha y tu nombre.</span>
      <select v-model="motivo" class="in" aria-label="Motivo">
        <option value="" disabled>Elige un motivo…</option>
        <option v-for="m in MOTIVOS" :key="m" :value="m">{{ MOTIVO_LABELS[m] }}</option>
      </select>
      <div v-if="aviso" class="note" :class="aviso.cls">{{ aviso.t }}</div>
      <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
    </div>
  </ConfirmDialog>
</template>

<style scoped>
.body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
