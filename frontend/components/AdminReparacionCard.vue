<script setup lang="ts">
import type { EstadoReparacion, Reparacion } from '~/types/administracion'

/** X14 «Mantenimiento y reparaciones» card: status chips, «Registrar avance», history. */
const props = defineProps<{ rep: Reparacion; open: boolean; labels: Record<string, Record<string, string>> }>()
const emit = defineEmits<{ toggle: []; changed: [msg: string]; error: [msg: string] }>()
const api = useAdministracion()

const ESTADOS: EstadoReparacion[] = ['recibida', 'cotizada', 'aprobada', 'en_ejecucion', 'terminada']
const r = computed(() => props.rep)
const av = reactive({ proveedor: '', valor: '', paga: '', comentario: '' })
const busy = ref(false)
watch(
  () => props.open,
  (o) => o && Object.assign(av, { proveedor: r.value.proveedor ?? '', valor: r.value.valor ? String(r.value.valor) : '', paga: r.value.paga, comentario: '' }),
  { immediate: true },
)

const datos = computed(() => [
  ['Prioridad', r.value.prioridad === 'urgente' ? 'Urgente' : 'Normal', r.value.prioridad === 'urgente' ? 'bad-txt' : ''],
  ['Fecha', fmtFecha(r.value.fecha), ''],
  ['Proveedor y valor', r.value.proveedor ? `${r.value.proveedor} · ${fmtCOP(r.value.valor)}` : 'Sin cotizar', ''],
  ['Quién paga', r.value.paga_txt, r.value.paga === 'por_definir' ? 'warn-txt' : ''],
  ['Sigue', r.value.responsable?.full_name ?? '—', ''],
  [r.value.estado === 'terminada' ? 'Se resolvió en' : 'Lleva', `${r.value.dias} ${r.value.dias === 1 ? 'día' : 'días'}`, r.value.estado !== 'terminada' && r.value.dias > 7 ? 'bad-txt' : ''],
])

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
const estado = (e: EstadoReparacion) =>
  run(
    () => api.estadoReparacion(r.value.id, e),
    `${r.value.code}: «${props.labels.estado_reparacion?.[e]}»${e === 'terminada' && r.value.paga === 'propietario' ? '. Paga el propietario: descuéntalo en su liquidación.' : '.'}`,
  )
function guardarAvance() {
  const body: Record<string, unknown> = {}
  if (av.proveedor.trim() && av.proveedor.trim() !== (r.value.proveedor ?? '')) body.proveedor = av.proveedor.trim()
  const v = Number(av.valor.replace(/\D/g, ''))
  if (av.valor.trim() && v !== r.value.valor) body.valor = v
  if (av.paga && av.paga !== r.value.paga) body.paga = av.paga
  if (av.comentario.trim()) body.comentario = av.comentario.trim()
  run(() => api.avance(r.value.id, body), `${r.value.code}: avance guardado.`)
}
const eliminar = () => run(() => api.eliminarReparacion(r.value.id), `${r.value.code} eliminada.`)
</script>

<template>
  <div class="card stack" :class="{ 'b-urg': r.prioridad === 'urgente' && r.estado !== 'terminada' }">
    <div class="sb top">
      <div>
        <b class="t15">{{ r.code }} · {{ r.titulo }}</b>
        <div class="mut small">{{ r.inmueble.codigo }} {{ r.inmueble.titulo }} · {{ r.categoria_txt }} · solicitó: {{ r.solicitante }}</div>
      </div>
      <span class="chip" :class="REP_CLS[r.estado]">{{ r.estado === 'terminada' ? '✓ ' : '' }}{{ r.estado_txt }}</span>
    </div>
    <div class="datos">
      <div v-for="[k, v, c] in datos" :key="k"><span class="mut">{{ k }}</span><br><b :class="c">{{ v }}</b></div>
    </div>
    <div class="row fw gap6">
      <button type="button" class="fch" @click="emit('toggle')">{{ open ? 'Cerrar' : r.puede_avance ? 'Registrar avance' : 'Ver historial' }}</button>
      <template v-if="r.puede_gestionar">
        <button v-for="e in ESTADOS" :key="e" type="button" class="fch" :class="{ on: r.estado === e }" :disabled="busy" @click="r.estado !== e && estado(e)">{{ labels.estado_reparacion?.[e] }}</button>
      </template>
    </div>

    <div v-if="open" class="panel">
      <template v-if="r.puede_avance">
        <div class="lbl">Avance (proveedor, valor de la cotización, quién paga o comentario)</div>
        <div class="avg">
          <div class="fld"><label :for="`pv-${r.id}`">Proveedor</label><input :id="`pv-${r.id}`" v-model="av.proveedor" class="in" placeholder="Ej.: Proveedor Ejemplo 3"></div>
          <div class="fld"><label :for="`vl-${r.id}`">Valor de la cotización</label><input :id="`vl-${r.id}`" v-model="av.valor" class="in" inputmode="numeric" placeholder="Ej.: 250000"></div>
          <div class="fld">
            <label :for="`pg-${r.id}`">Quién paga</label>
            <select :id="`pg-${r.id}`" v-model="av.paga" class="in">
              <option v-for="(t, k) in labels.paga" :key="k" :value="k">{{ t }}</option>
            </select>
          </div>
        </div>
        <div class="fld"><label :for="`cm-${r.id}`">Comentario</label><input :id="`cm-${r.id}`" v-model="av.comentario" class="in" placeholder="Ej.: El propietario aprobó por WhatsApp"></div>
        <div class="row gap6"><button type="button" class="btn bp sm" :disabled="busy" @click="guardarAvance">Guardar avance</button></div>
      </template>
      <div v-for="(e, n) in r.eventos" :key="n" class="mut tiny">· {{ e.titulo }}{{ e.detalle ? ` · ${e.detalle}` : '' }} · {{ e.created_by_name ?? 'Sistema' }} · {{ fmtCuando(e.created_at) }}</div>
      <div v-if="r.puede_gestionar && r.estado === 'recibida'" class="row"><button type="button" class="btn br sm" :disabled="busy" @click="eliminar">Eliminar</button></div>
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
.b-urg {
  border: 1.5px solid var(--cdc-bad);
}
.avg {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px;
}
</style>
