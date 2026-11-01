<script setup lang="ts">
import type { ActividadCampo, Movimiento, MovOpciones, TipoCampo } from '~/types/movimientos'

/** K16 / C09 «Trabajo en campo»: start it (the GPS turns on) and finish it (it turns off). */
const props = defineProps<{ o: MovOpciones; abierto: Movimiento | null }>()
const emit = defineEmits<{ changed: [msg: string] }>()
const api = useMovimientos()

const TIPOS = computed(() => Object.keys(props.o.tipos_campo) as TipoCampo[])
const quienVe = computed(() => (props.o.perfil === 'coordinacion' ? 'Gerencia ve' : 'Coordinación y Gerencia ven'))
const f = reactive({
  tipo_campo: TIPOS.value[0] as TipoCampo,
  actividad_campo: 'captacion' as ActividadCampo,
  cita_id: '',
  acompanados: [] as string[],
  detalle: '',
  err: '',
  busy: false,
})
function toggleAsesor(id: string) {
  if (f.tipo_campo === 'acompanamiento_ruta') f.acompanados = [id]
  else f.acompanados = f.acompanados.includes(id) ? f.acompanados.filter((x) => x !== id) : [...f.acompanados, id]
}
watch(() => f.tipo_campo, () => (f.acompanados = []))

async function iniciar() {
  f.err = ''
  f.busy = true
  try {
    await api.iniciarCampo({
      tipo_campo: f.tipo_campo,
      actividad_campo: f.actividad_campo,
      cita_id: f.tipo_campo === 'apoyo_cita' ? f.cita_id || null : null,
      acompanados_ids: f.acompanados,
      detalle: f.detalle || null,
    })
    emit('changed', `Trabajo en campo iniciado. GPS activo: ${quienVe.value} tu ubicación.`)
  } catch (e) {
    f.err = apiErrorMessage(e)
  } finally {
    f.busy = false
  }
}
async function finalizar() {
  if (!props.abierto) return
  f.busy = true
  try {
    const m = await api.finalizar(props.abierto.id)
    emit('changed', `Trabajo en campo finalizado (${m.duracion_txt}). El GPS se apagó. Quedó en tu historial.`)
  } catch (e) {
    f.err = apiErrorMessage(e)
  } finally {
    f.busy = false
  }
}
</script>

<template>
  <div v-if="abierto" class="card focus col">
    <div class="sb"><span class="lbl">En campo ahora</span><span class="chip ok">● GPS activo desde {{ fmtHora(abierto.ocurrido_at) }}</span></div>
    <b class="t17">{{ abierto.tipo_campo_txt }}</b>
    <div class="kv">
      <template v-if="abierto.cita_code || abierto.acompanados.length"><span class="mut">Con</span><b>{{ abierto.cita_code ?? abierto.acompanados.join(', ') }}</b></template>
      <span class="mut">Actividad</span><b>{{ abierto.actividad_campo_txt }}</b>
      <template v-if="abierto.detalle"><span class="mut">Observación</span><span>{{ abierto.detalle }}</span></template>
    </div>
    <div v-if="f.err" class="note bad"><b>{{ f.err }}</b></div>
    <button type="button" class="btn br self-start" :disabled="f.busy" @click="finalizar">Finalizar trabajo en campo</button>
  </div>
  <div v-else class="card col">
    <div class="sb"><span class="lbl">Iniciar trabajo en campo</span><span class="chip gray">GPS apagado</span></div>
    <div class="fld">
      <span class="fld-label">Tipo <span class="req">*</span></span>
      <div class="row fw"><button v-for="t in TIPOS" :key="t" type="button" class="opt" :class="{ on: f.tipo_campo === t }" @click="f.tipo_campo = t">{{ o.tipos_campo[t] }}</button></div>
    </div>
    <div v-if="f.tipo_campo === 'apoyo_cita'" class="fld">
      <label for="mc-cita">Cita que apoya <span class="req">*</span></label>
      <select id="mc-cita" v-model="f.cita_id" class="in">
        <option value="" disabled>{{ o.citas.length ? 'Elige la cita' : 'No hay citas en los próximos 7 días' }}</option>
        <option v-for="c in o.citas" :key="c.id" :value="c.id">{{ c.txt }}</option>
      </select>
    </div>
    <div v-if="f.tipo_campo === 'acompanamiento_ruta' || f.tipo_campo === 'salida_grupal'" class="fld">
      <span class="fld-label">{{ f.tipo_campo === 'salida_grupal' ? 'Asesores de la salida grupal' : 'Asesor que acompaña' }} <span class="req">*</span></span>
      <div class="row fw"><button v-for="a in o.asesores" :key="a.id" type="button" class="opt" :class="{ on: f.acompanados.includes(a.id) }" @click="toggleAsesor(a.id)">{{ a.txt }}</button></div>
    </div>
    <div class="g2">
      <div class="fld">
        <label for="mc-act">Actividad <span class="req">*</span></label>
        <select id="mc-act" v-model="f.actividad_campo" class="in"><option v-for="(t, k) in o.actividades_campo" :key="k" :value="k">{{ t }}</option></select>
      </div>
      <div class="fld"><label for="mc-obs">Observación</label><input id="mc-obs" v-model="f.detalle" class="in" placeholder="Opcional"></div>
    </div>
    <div class="note">Al iniciar se activa el GPS. {{ quienVe }} tu ubicación mientras estés en campo; al finalizar se apaga. Solo en la jornada ({{ o.jornada }}).</div>
    <div v-if="f.err" class="note bad"><b>{{ f.err }}</b></div>
    <button type="button" class="btn bp self-start" :disabled="f.busy" @click="iniciar">Iniciar trabajo en campo</button>
  </div>
</template>

<style scoped>
.col {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.t17 {
  font-size: 17px;
}
.kv {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 12px;
  font-size: 13px;
}
.fw {
  flex-wrap: wrap;
}
.self-start {
  align-self: flex-start;
}
</style>
