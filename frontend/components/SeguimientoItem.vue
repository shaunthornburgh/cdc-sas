<script setup lang="ts">
import type { LeadDetail, SeguimientoT } from '~/types/leads'

/** One pending follow-up in «Próximas acciones» (C02) with its «Marcar como realizada» form. */
const props = defineProps<{ leadId: string; seg: SeguimientoT; canEdit: boolean }>()
const emit = defineEmits<{ done: [lead: LeadDetail, next: 'seg' | 'cita' | null] }>()
const leads = useLeads()

const HECHO = ['Llamé · contestó', 'Llamé · no contestó', 'Envié mensaje', 'Envié opciones', 'Envié información', 'Otra acción']
const SIGUIENTE = [
  ['seg', 'Programar otro seguimiento'],
  ['cita', 'Programar cita'],
  ['nada', 'Sin siguiente paso por ahora'],
] as const

const open = ref(false)
const hecho = ref<string | null>(null)
const texto = ref('')
const siguiente = ref<'seg' | 'cita' | 'nada' | null>(null)
const error = ref<string | null>(null)
const busy = ref(false)

const vencido = computed(() => minutesUntil(props.seg.due_at) < 0)

async function save() {
  if (!hecho.value) return (error.value = 'Elige qué hiciste.')
  if (!texto.value.trim()) return (error.value = 'Escribe qué pasó o qué se habló.')
  if (!siguiente.value) return (error.value = 'Elige el siguiente paso.')
  error.value = null
  busy.value = true
  try {
    const lead = await leads.completeFollowup(props.leadId, props.seg.id, `${hecho.value} · ${texto.value.trim()}`)
    emit('done', lead, siguiente.value === 'nada' ? null : siguiente.value)
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="item">
    <div class="sb">
      <b class="t">{{ ACCION_LABELS[seg.accion] }}</b>
      <span class="chip" :class="vencido ? 'bad' : 'warn'">{{ vencido ? 'Vencido · ' : '' }}{{ fmtCuando(seg.due_at) }}</span>
    </div>
    <span v-if="seg.nota" class="mut small">{{ seg.nota }}</span>
    <button v-if="canEdit && !open" type="button" class="btn bs sm self-start" @click="open = true">Marcar como realizada</button>

    <div v-if="open" class="done-form">
      <b class="t">¿Qué hiciste? <span class="req">*</span></b>
      <div class="row wrap">
        <button v-for="h in HECHO" :key="h" type="button" class="fch" :class="{ on: hecho === h }" @click="hecho = h">{{ h }}</button>
      </div>
      <div class="fld">
        <label :for="`sr-${seg.id}`">Qué pasó o qué se habló <span class="req">*</span></label>
        <textarea :id="`sr-${seg.id}`" v-model="texto" class="in" placeholder="Ej.: le gustó el de Laureles y quiere verlo el lunes" />
      </div>
      <b class="t">Siguiente paso <span class="req">*</span></b>
      <div class="row wrap">
        <button v-for="[k, t] in SIGUIENTE" :key="k" type="button" class="fch" :class="{ on: siguiente === k }" @click="siguiente = k">{{ t }}</button>
      </div>
      <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
      <div class="g2">
        <button type="button" class="btn bs" @click="open = false">Cancelar</button>
        <button type="button" class="btn bp" :disabled="busy" @click="save">Guardar</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.item {
  padding: 8px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.t {
  font-size: 13.5px;
}
.small {
  font-size: 12px;
}
.self-start {
  align-self: flex-start;
}
.wrap {
  flex-wrap: wrap;
  gap: 6px;
}
.done-form {
  border: 1.5px solid var(--cdc-green);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #f7fbf7;
}
</style>
