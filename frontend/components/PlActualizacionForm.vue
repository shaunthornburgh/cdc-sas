<script setup lang="ts">
import type { PlActualizacion, PlataformaRow } from '~/types/plataformas'

/** K15 «Registrar actualización»: what the portal shows today. Date, time and who are saved alone. */
const props = defineProps<{ p: PlataformaRow }>()
const emit = defineEmits<{ saved: [a: PlActualizacion]; cancel: [] }>()
const api = usePlataformas()

const f = reactive({ usado: '', total: '', dest: '', destTotal: '', obs: '', err: '', busy: false })
const sinPlan = computed(() => !props.p.plan)
const n = (v: string) => (v.trim() === '' ? NaN : Number(v))

async function guardar() {
  f.err = ''
  const usado = n(f.usado)
  const total = n(f.total || String(props.p.plan?.cupo_total ?? props.p.cupo_total ?? ''))
  const dest = n(f.dest)
  const destTotal = sinPlan.value ? n(f.destTotal) : undefined
  if ([usado, total, dest].some(Number.isNaN) || (sinPlan.value && Number.isNaN(destTotal)))
    return (f.err = 'Completa los campos obligatorios con números.')
  if (usado > total) return (f.err = 'Las publicaciones activas no pueden pasar del cupo total del plan.')
  f.busy = true
  try {
    const a = await api.registrar(props.p.id, {
      cupo_usado: usado,
      cupo_total: total,
      destacados_usados: dest,
      ...(sinPlan.value ? { destacados_total: destTotal } : {}),
      observacion: f.obs || null,
    })
    emit('saved', a)
  } catch (e) {
    f.err = apiErrorMessage(e)
  } finally {
    f.busy = false
  }
}
</script>

<template>
  <div class="frm">
    <b class="small">Actualización de {{ p.nombre }} · hoy</b>
    <div class="g4">
      <div class="fld"><label :for="`u-${p.id}`">Publicaciones activas <span class="req">*</span></label><input :id="`u-${p.id}`" v-model="f.usado" class="in" inputmode="numeric" :placeholder="String(p.cupo_usado ?? '')"></div>
      <div class="fld"><label :for="`t-${p.id}`">Cupo total del plan <span class="req">*</span></label><input :id="`t-${p.id}`" v-model="f.total" class="in" inputmode="numeric" :placeholder="String(p.plan?.cupo_total ?? p.cupo_total ?? '')"></div>
      <div class="fld"><label :for="`d-${p.id}`">Destacados usados <span class="req">*</span></label><input :id="`d-${p.id}`" v-model="f.dest" class="in" inputmode="numeric" :placeholder="String(p.destacados_usados ?? '')"></div>
      <div v-if="sinPlan" class="fld"><label :for="`dt-${p.id}`">Destacados del plan <span class="req">*</span></label><input :id="`dt-${p.id}`" v-model="f.destTotal" class="in" inputmode="numeric" placeholder="Sin plan registrado"></div>
      <div class="fld"><label :for="`o-${p.id}`">Observación</label><input :id="`o-${p.id}`" v-model="f.obs" class="in" placeholder="Opcional"></div>
    </div>
    <div v-if="f.err" class="note bad"><b>{{ f.err }}</b></div>
    <div class="row">
      <button type="button" class="btn bp" :disabled="f.busy" @click="guardar">Guardar actualización</button>
      <button type="button" class="btn bs" @click="emit('cancel')">Cancelar</button>
    </div>
  </div>
</template>

<style scoped>
.frm {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--cdc-bg);
  border-radius: 12px;
  padding: 12px;
  margin: 8px 0;
}
.small {
  font-size: 13px;
}
</style>
