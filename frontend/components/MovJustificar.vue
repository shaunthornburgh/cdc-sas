<script setup lang="ts">
import type { MotivoMovimiento, Movimiento, MovOpciones } from '~/types/movimientos'

/** M05 «Justificar»: salida de ruta / de la zona or tiempo detenido. */
const props = defineProps<{ m: Movimiento; o: MovOpciones }>()
const emit = defineEmits<{ done: [m: Movimiento]; cancel: [] }>()
const api = useMovimientos()

const salida = computed(() => props.m.tipo !== 'tiempo_detenido')
const motivos = computed(() => props.o.motivos_por_tipo[props.m.tipo] ?? [])
const f = reactive({
  motivo: motivos.value[0] as MotivoMovimiento,
  inmueble_codigo: '',
  cliente: '',
  observacion: '',
  motivo_texto: '',
  autorizo: 'coordinacion',
  evidencias: 0,
  err: '',
  busy: false,
})
const conInmueble = computed(() => props.o.motivos_con_inmueble.includes(f.motivo))
const aviso = computed(() =>
  props.m.tipo === 'tiempo_detenido'
    ? `Llevaste más de ${props.m.minutos_umbral ?? props.o.config.minutos_alerta} minutos en esta misma posición. Por favor, justifica este tiempo detenido.`
    : props.m.tipo === 'salida_zona'
      ? 'Saliste de la zona de tu actividad en campo. Por favor, justifica esta acción.'
      : 'Te saliste de tu ruta asignada. Por favor, justifica esta acción.',
)
const plazo = computed(() => (props.m.plazo_at ? fmtCuando(props.m.plazo_at) : 'PENDIENTE DE CONFIGURACIÓN'))

async function enviar() {
  f.err = ''
  if (conInmueble.value && (!f.inmueble_codigo.trim() || !f.cliente.trim() || !f.observacion.trim()))
    return (f.err = 'Escribe el código del inmueble, el cliente y la observación.')
  if (!conInmueble.value && f.motivo_texto.trim().length < 3) return (f.err = 'Escribe el motivo.')
  f.busy = true
  try {
    const body = conInmueble.value
      ? { motivo: f.motivo, inmueble_codigo: f.inmueble_codigo, cliente: f.cliente, observacion: f.observacion }
      : {
          motivo: f.motivo,
          motivo_texto: f.motivo_texto,
          observacion: f.observacion || null,
          ...(salida.value ? { autorizo: f.autorizo } : { evidencias: f.evidencias }),
        }
    emit('done', await api.justificar(props.m.id, body))
  } catch (e) {
    f.err = apiErrorMessage(e)
  } finally {
    f.busy = false
  }
}
</script>

<template>
  <div class="jf">
    <div class="avisojf">
      <b>{{ aviso }}</b>
      <div class="tiny">Se registró automáticamente: fecha, hora ({{ fmtHora(m.ocurrido_at) }}){{ m.lugar ? `, lugar (${m.lugar})` : '' }} y ubicación.</div>
      <div class="tiny"><b>Plazo para justificar:</b> {{ plazo }}. Si no justificas a tiempo o {{ m.revisa }} la rechaza, se descuenta 1 punto.</div>
    </div>
    <div class="lbl">¿Qué pasó?</div>
    <div class="row fw">
      <button v-for="mo in motivos" :key="mo" type="button" class="opt" :class="{ on: f.motivo === mo }" @click="f.motivo = mo">{{ o.motivos[mo] }}</button>
    </div>
    <div v-if="conInmueble" class="g3">
      <div class="fld"><label :for="`c1-${m.id}`">Código del inmueble <span class="req">*</span></label><input :id="`c1-${m.id}`" v-model="f.inmueble_codigo" class="in" placeholder="Ej: INM-0351"></div>
      <div class="fld"><label :for="`c2-${m.id}`">Cliente <span class="req">*</span></label><input :id="`c2-${m.id}`" v-model="f.cliente" class="in" placeholder="Nombre del cliente"></div>
      <div class="fld"><label :for="`c3-${m.id}`">Observación <span class="req">*</span></label><input :id="`c3-${m.id}`" v-model="f.observacion" class="in" placeholder="Qué estás haciendo aquí"></div>
    </div>
    <div v-else class="g3">
      <div class="fld"><label :for="`p1-${m.id}`">Motivo <span class="req">*</span></label><input :id="`p1-${m.id}`" v-model="f.motivo_texto" class="in" placeholder="Motivo"></div>
      <div v-if="salida" class="fld">
        <label :for="`p2-${m.id}`">¿Quién autorizó? <span class="req">*</span></label>
        <select :id="`p2-${m.id}`" v-model="f.autorizo" class="in">
          <option v-for="(t, k) in o.autorizo" :key="k" :value="k">{{ t }}</option>
        </select>
      </div>
      <div v-else class="fld">
        <span class="fld-label">Evidencia (si corresponde)</span>
        <button type="button" class="btn bs" @click="f.evidencias++">{{ f.evidencias ? `✓ ${f.evidencias} archivo${f.evidencias === 1 ? '' : 's'} · agregar otro` : 'Adjuntar foto o documento' }}</button>
      </div>
      <div class="fld"><label :for="`p3-${m.id}`">Observación</label><input :id="`p3-${m.id}`" v-model="f.observacion" class="in" placeholder="Detalles"></div>
    </div>
    <div v-if="f.err" class="note bad"><b>{{ f.err }}</b></div>
    <div class="row">
      <button type="button" class="btn bp" :disabled="f.busy" @click="enviar">Enviar justificación</button>
      <button type="button" class="btn bs" @click="emit('cancel')">Cancelar</button>
    </div>
  </div>
</template>

<style scoped>
.jf {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px 0 4px;
}
.avisojf {
  background: #fcf0d6;
  border: 1px solid #ebcb8b;
  border-radius: 14px;
  padding: 12px 14px;
  color: #5c3b00;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.tiny {
  font-size: 12px;
}
.fw {
  flex-wrap: wrap;
}
</style>
