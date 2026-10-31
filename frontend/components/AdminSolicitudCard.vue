<script setup lang="ts">
import type { Solicitud } from '~/types/administracion'

/** X14 «Solicitudes y quejas» card: deadline in business days, «Responder», «En trámite», «Cerrar». */
const props = defineProps<{ sol: Solicitud; open: boolean }>()
const emit = defineEmits<{ toggle: []; changed: [msg: string]; error: [msg: string] }>()
const api = useAdministracion()

const s = computed(() => props.sol)
const texto = ref('')
const motivo = ref('')
const cerrando = ref(false)
const busy = ref(false)
watch(
  () => props.open,
  (o) => {
    if (o) return
    texto.value = ''
    motivo.value = ''
    cerrando.value = false
  },
)

const viva = computed(() => s.value.estado === 'abierta' || s.value.estado === 'en_tramite')
const cerca = computed(() => viva.value && !s.value.fuera_de_plazo && s.value.dias_habiles > s.value.plazo - 3)
const datos = computed(() => [
  ['Recibida', fmtFecha(s.value.fecha), ''],
  ['Responsable', s.value.responsable?.full_name ?? '—', ''],
  ['Prioridad', s.value.prioridad === 'urgente' ? 'Urgente' : 'Normal', s.value.prioridad === 'urgente' ? 'bad-txt' : ''],
  [viva.value ? 'Lleva' : 'Respondida en', `${s.value.dias_habiles} días hábiles de ${s.value.plazo}`, s.value.fuera_de_plazo ? 'bad-txt' : cerca.value ? 'warn-txt' : ''],
])
const quien = computed(() => (s.value.de === 'propietario' ? 'propietario' : 'inquilino'))

async function run(fn: () => Promise<unknown>, ok: string) {
  busy.value = true
  try {
    await fn()
    emit('changed', ok)
  } catch (e) {
    emit('error', apiErrorMessage(e))
  } finally {
    busy.value = false
  }
}
const responder = () => run(() => api.responder(s.value.id, texto.value), `${s.value.code}: respuesta enviada a ${s.value.nombre ?? `el ${quien.value}`}.`)
const enTramite = () => run(() => api.estadoSolicitud(s.value.id, 'en_tramite'), `${s.value.code}: «En trámite».`)
function cerrar() {
  if (s.value.estado !== 'respondida' && !cerrando.value) {
    cerrando.value = true
    if (!props.open) emit('toggle')
    return
  }
  run(() => api.estadoSolicitud(s.value.id, 'cerrada', motivo.value || null), `${s.value.code}: «Cerrada».`)
}
const eliminar = () => run(() => api.eliminarSolicitud(s.value.id), `${s.value.code} eliminada.`)
</script>

<template>
  <div class="card stack" :class="{ 'b-venc': s.fuera_de_plazo }">
    <div class="sb top">
      <div>
        <b class="t15">{{ s.code }} · {{ s.tipo_txt }} · {{ s.descripcion }}</b>
        <div class="mut small">{{ s.de_txt }}{{ s.nombre ? ` · ${s.nombre}` : '' }} · {{ s.inmueble.codigo }} {{ s.inmueble.titulo }} · por {{ s.canal_txt }}</div>
      </div>
      <span class="chip" :class="s.fuera_de_plazo ? 'bad' : SOL_CLS[s.estado]">{{ s.fuera_de_plazo ? 'Fuera de plazo' : `${s.estado === 'respondida' ? '✓ ' : ''}${s.estado_txt}` }}</span>
    </div>
    <div class="datos">
      <div v-for="[k, v, c] in datos" :key="k"><span class="mut">{{ k }}</span><br><b :class="c">{{ v }}</b></div>
    </div>
    <div v-if="s.respuesta" class="mut tiny">Respuesta: {{ s.respuesta }}</div>
    <div class="row fw gap6">
      <button type="button" class="fch" @click="emit('toggle')">{{ open ? 'Cerrar' : s.puede_responder ? 'Responder' : 'Ver historial' }}</button>
      <template v-if="s.puede_gestionar">
        <button v-if="s.estado === 'abierta'" type="button" class="fch" :disabled="busy" @click="enTramite">En trámite</button>
        <button type="button" class="fch" :disabled="busy" @click="cerrar">Cerrar</button>
      </template>
    </div>

    <div v-if="open" class="panel">
      <template v-if="s.puede_responder && !cerrando">
        <div class="fld">
          <label :for="`rs-${s.id}`">Respuesta al {{ quien }}</label>
          <textarea :id="`rs-${s.id}`" v-model="texto" class="in ta" rows="2" placeholder="Escribe la respuesta que se le envía" />
        </div>
        <div class="row gap6"><button type="button" class="btn bp sm" :disabled="busy || !texto.trim()" @click="responder">Enviar respuesta</button></div>
      </template>
      <template v-if="cerrando">
        <div class="fld">
          <label :for="`mt-${s.id}`">Motivo para cerrarla sin respuesta <span class="req">*</span></label>
          <input :id="`mt-${s.id}`" v-model="motivo" class="in" placeholder="Ej.: Se resolvió en la oficina">
        </div>
        <div class="row gap6">
          <button type="button" class="btn bp sm" :disabled="busy || !motivo.trim()" @click="cerrar">Cerrar sin respuesta</button>
          <button type="button" class="btn bs sm" @click="cerrando = false">Cancelar</button>
        </div>
      </template>
      <div v-for="(e, n) in s.eventos" :key="n" class="mut tiny">· {{ e.titulo }}{{ e.detalle && !e.titulo.startsWith('Respondida') ? ` · ${e.detalle}` : '' }} · {{ fmtCuando(e.created_at) }}</div>
      <div v-if="s.puede_gestionar && s.estado === 'abierta' && !s.respuesta" class="row"><button type="button" class="btn br sm" :disabled="busy" @click="eliminar">Eliminar</button></div>
    </div>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.top {
  align-items: flex-start;
  gap: 8px;
}
.t15 {
  font-size: 15px;
}
.datos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
  font-size: 12.5px;
}
.small {
  font-size: 12.5px;
}
.tiny {
  font-size: 12px;
}
.bad-txt {
  color: var(--cdc-bad);
}
.warn-txt {
  color: #b7791f;
}
.fw {
  flex-wrap: wrap;
}
.gap6 {
  gap: 6px;
}
.b-venc {
  border: 1.5px solid var(--cdc-bad);
}
.ta {
  min-height: 64px;
  padding-top: 8px;
  resize: vertical;
}
</style>
