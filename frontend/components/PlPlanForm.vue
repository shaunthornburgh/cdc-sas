<script setup lang="ts">
import type { PlataformaRow } from '~/types/plataformas'

/** Gerencia: register the portal's plan (renewal) or correct the current one, and switch it on/off. */
const props = defineProps<{ p: PlataformaRow }>()
const emit = defineEmits<{ saved: [msg: string]; cancel: [] }>()
const api = usePlataformas()

const plus = (iso: string, d: number) => new Date(new Date(`${iso}T12:00:00`).getTime() + d * 86_400_000).toISOString().slice(0, 10)
const pl = props.p.plan
const f = reactive({
  precio: pl ? String(pl.precio) : '',
  activacion: pl && props.p.plan_estado !== 'vencido' ? pl.activacion : localDate(0),
  vencimiento: pl && props.p.plan_estado !== 'vencido' ? pl.vencimiento : plus(localDate(0), 91),
  cupo_total: pl ? String(pl.cupo_total) : '',
  destacados_total: pl ? String(pl.destacados_total) : '',
  alarma_dias: pl ? String(pl.alarma_dias) : '10',
  err: '',
  busy: false,
})
function renovar() {
  if (!pl) return
  const act = plus(pl.vencimiento, 1)
  Object.assign(f, { activacion: act, vencimiento: plus(act, 91) })
}
const esCorreccion = computed(() => !!pl && f.activacion === pl.activacion)

async function guardar() {
  f.err = ''
  const nums = [f.precio, f.cupo_total, f.destacados_total, f.alarma_dias].map(Number)
  if (nums.some((x, i) => Number.isNaN(x) || [f.precio, f.cupo_total, f.destacados_total, f.alarma_dias][i] === ''))
    return (f.err = 'Completa precio, cupo, destacados y alarma.')
  f.busy = true
  try {
    await api.plan(props.p.id, {
      precio: nums[0],
      activacion: f.activacion,
      vencimiento: f.vencimiento,
      cupo_total: nums[1],
      destacados_total: nums[2],
      alarma_dias: nums[3],
    })
    emit('saved', `${props.p.nombre}: ${esCorreccion.value ? 'plan corregido' : 'plan registrado'}. Queda en el registro de cambios.`)
  } catch (e) {
    f.err = apiErrorMessage(e)
  } finally {
    f.busy = false
  }
}
async function toggle() {
  f.busy = true
  try {
    await api.activa(props.p.id, !props.p.activa)
    emit('saved', `${props.p.nombre} ${props.p.activa ? 'desactivada: ya no se actualiza ni cuenta' : 'activada: aparece en «Actualización de plataformas»'}.`)
  } catch (e) {
    f.err = apiErrorMessage(e)
  } finally {
    f.busy = false
  }
}
</script>

<template>
  <div class="frm">
    <div class="sb">
      <b class="small">Plan de {{ p.nombre }}</b>
      <button v-if="pl" type="button" class="btn bs sm" @click="renovar">Renovar (siguiente periodo)</button>
    </div>
    <div class="g3">
      <div class="fld"><label :for="`pp-${p.id}`">Precio del periodo (COP) <span class="req">*</span></label><input :id="`pp-${p.id}`" v-model="f.precio" class="in" inputmode="numeric" placeholder="Ej: 800000"></div>
      <div class="fld"><label :for="`pa-${p.id}`">Activación <span class="req">*</span></label><input :id="`pa-${p.id}`" v-model="f.activacion" class="in" type="date"></div>
      <div class="fld"><label :for="`pv-${p.id}`">Vencimiento <span class="req">*</span></label><input :id="`pv-${p.id}`" v-model="f.vencimiento" class="in" type="date" :min="f.activacion"></div>
      <div class="fld"><label :for="`pc-${p.id}`">Cupo total <span class="req">*</span></label><input :id="`pc-${p.id}`" v-model="f.cupo_total" class="in" inputmode="numeric"></div>
      <div class="fld"><label :for="`pd-${p.id}`">Destacados <span class="req">*</span></label><input :id="`pd-${p.id}`" v-model="f.destacados_total" class="in" inputmode="numeric"></div>
      <div class="fld"><label :for="`pl-${p.id}`">Alarma (días antes de vencer)</label><input :id="`pl-${p.id}`" v-model="f.alarma_dias" class="in" inputmode="numeric"></div>
    </div>
    <div class="mut tiny">{{ esCorreccion ? 'Misma fecha de activación: se corrige el plan actual.' : 'Otra fecha de activación: queda como un plan nuevo; los anteriores siguen contando en el costo de su periodo.' }}</div>
    <div v-if="f.err" class="note bad"><b>{{ f.err }}</b></div>
    <div class="row fw">
      <button type="button" class="btn bp" :disabled="f.busy" @click="guardar">{{ esCorreccion ? 'Guardar cambios' : 'Registrar plan' }}</button>
      <button type="button" class="btn bs" @click="emit('cancel')">Cancelar</button>
      <button type="button" class="btn ml-auto" :class="p.activa ? 'br' : 'bs'" :disabled="f.busy" @click="toggle">{{ p.activa ? 'Desactivar plataforma' : 'Activar plataforma' }}</button>
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
.tiny {
  font-size: 12px;
}
.fw {
  flex-wrap: wrap;
}
.ml-auto {
  margin-left: auto;
}
</style>
