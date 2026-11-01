<script setup lang="ts">
import type { MovEvento, Movimiento } from '~/types/movimientos'

/** Row detail: the justification, the review, the location (logged) and the history. */
const props = defineProps<{ m: Movimiento }>()
const emit = defineEmits<{ error: [msg: string] }>()
const api = useMovimientos()

const hist = ref<MovEvento[] | null>(null)
const ubic = ref<{ lat: number; lng: number; lugar: string | null } | null>(null)
onMounted(async () => {
  try {
    hist.value = await api.historial(props.m.id)
  } catch (e) {
    emit('error', apiErrorMessage(e))
  }
})
async function verUbicacion() {
  try {
    ubic.value = await api.ubicacion(props.m.id)
    hist.value = await api.historial(props.m.id)
  } catch (e) {
    emit('error', apiErrorMessage(e))
  }
}
const osm = computed(() => (ubic.value ? `https://www.openstreetmap.org/?mlat=${ubic.value.lat}&mlon=${ubic.value.lng}#map=17/${ubic.value.lat}/${ubic.value.lng}` : ''))
</script>

<template>
  <div class="det">
    <div class="datos">
      <div><span class="mut tiny">Código</span><br><b class="small">{{ m.code }}</b></div>
      <div><span class="mut tiny">Empleado</span><br><b class="small">{{ m.empleado.full_name }}</b><br><span class="mut tiny">{{ m.empleado.perfil_txt }}</span></div>
      <div v-if="m.es_alerta"><span class="mut tiny">Revisa</span><br><b class="small">{{ m.revisa }}</b></div>
      <div v-if="m.es_alerta"><span class="mut tiny">Plazo para justificar</span><br><b class="small">{{ m.plazo_at ? fmtCuando(m.plazo_at) : 'Pendiente de configuración' }}</b></div>
      <div v-if="!m.es_alerta"><span class="mut tiny">Duración</span><br><b class="small">{{ m.en_curso ? `En curso · ${m.duracion_txt}` : m.duracion_txt }}</b></div>
      <div v-if="m.motivo"><span class="mut tiny">Justificación</span><br><b class="small">{{ m.motivo_txt }}</b>
        <span v-if="m.inmueble_codigo" class="mut tiny"><br>{{ m.inmueble_codigo }}{{ m.inmueble_en_catalogo ? ' (en el catálogo)' : '' }} · {{ m.cliente }}</span>
        <span v-if="m.autorizo_txt" class="mut tiny"><br>Autorizó: {{ m.autorizo_txt }}</span>
        <span v-if="m.evidencias" class="mut tiny"><br>{{ m.evidencias }} archivo{{ m.evidencias === 1 ? '' : 's' }}</span>
      </div>
      <div v-if="m.observacion"><span class="mut tiny">Observación</span><br><span class="small">{{ m.observacion }}</span></div>
      <div v-if="m.nota_revision"><span class="mut tiny">Nota de la revisión</span><br><span class="small">{{ m.nota_revision }}</span></div>
    </div>
    <div v-if="m.tiene_ubicacion" class="row fw gap8">
      <button v-if="!ubic" type="button" class="btn bs sm" @click="verUbicacion">Ver ubicación</button>
      <span v-else class="small">📍 {{ ubic.lugar ?? '' }} {{ ubic.lat.toFixed(5) }}, {{ ubic.lng.toFixed(5) }} · <a :href="osm" target="_blank" rel="noopener">abrir mapa</a></span>
      <span class="mut tiny">Queda registrado quién consultó la ubicación y cuándo.</span>
    </div>
    <div>
      <div class="lbl">Historial</div>
      <div v-for="e in hist ?? []" :key="e.id" class="ev small">
        <span class="num mut">{{ fmtCuando(e.created_at) }}</span>
        <span><b>{{ e.tipo_txt }}</b>{{ e.actor_name ? ` · ${e.actor_name}` : '' }}{{ e.estado_antes && e.estado_despues && e.estado_antes !== e.estado_despues ? ` · ${e.estado_antes.replace('_', ' ')} → ${e.estado_despues.replace('_', ' ')}` : '' }}<span v-if="e.detalle" class="mut"> · {{ e.detalle }}</span></span>
      </div>
      <div v-if="hist && !hist.length" class="mut tiny">Sin eventos.</div>
    </div>
  </div>
</template>

<style scoped>
.det {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px 6px 14px;
  background: var(--cdc-bg);
  border-bottom: 1px solid var(--cdc-border-soft);
}
.datos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 8px;
}
.ev {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 8px;
  padding: 3px 0;
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
.gap8 {
  gap: 8px;
}
</style>
