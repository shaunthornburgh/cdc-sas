<script setup lang="ts">
import type { EstadoAmbiente, Inventario } from '~/types/administracion'

/** X14 «Inventarios» card: rooms checklist (bueno / regular / malo, note, photos), signatures, repair. */
const props = defineProps<{ inv: Inventario; open: boolean }>()
const emit = defineEmits<{ toggle: []; changed: [msg: string]; error: [msg: string] }>()
const api = useAdministracion()

const AMB: [EstadoAmbiente, string][] = [['bueno', 'Bueno'], ['regular', 'Regular'], ['malo', 'Malo']]
const AMB_COLOR: Record<EstadoAmbiente, string> = { bueno: 'var(--cdc-ok)', regular: '#b7791f', malo: 'var(--cdc-bad)' }
const obs = reactive<Record<string, string>>({})
const busy = ref(false)

const i = computed(() => props.inv)
const faltan = computed(() => diasHasta(i.value.fecha))
const nov = computed(() => i.value.ambientes.filter((a) => a.estado === 'regular' || a.estado === 'malo'))
const datos = computed(() => [
  ['Fecha', fmtFecha(i.value.fecha), ''],
  ['Responsable', i.value.responsable?.full_name ?? '—', ''],
  ['Ambientes revisados', `${i.value.ambientes.filter((a) => a.estado).length} de ${i.value.ambientes.length} · ${i.value.novedades} con novedad`, i.value.novedades ? 'bad-txt' : ''],
  ['Fotos', `${i.value.fotos} fotos`, ''],
  ...(i.value.estado === 'programado'
    ? [['Faltan', faltan.value < 0 ? `atrasado ${-faltan.value} días` : `${faltan.value} días`, faltan.value < 0 ? 'bad-txt' : '']]
    : []),
])
const firmas = computed(() =>
  i.value.estado === 'firmado' || i.value.estado === 'con_novedades'
    ? '✓ Firmado por propietario e inquilino'
    : i.value.estado === 'programado'
      ? 'Al marcar los ambientes queda «realizado»; luego se registran las firmas.'
      : 'Falta registrar las firmas del propietario y del inquilino.',
)

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
const marcar = (id: string, estado: EstadoAmbiente) =>
  run(() => api.ambiente(i.value.id, id, { estado, ...(obs[id] !== undefined ? { observacion: obs[id] } : {}) }), '')
const guardarObs = (id: string) => run(() => api.ambiente(i.value.id, id, { observacion: obs[id] ?? '' }), '')
const foto = (id: string, n: number) => run(() => api.ambiente(i.value.id, id, { fotos: n + 1 }), '')
const firmar = () =>
  run(() => api.firmar(i.value.id), `${i.value.code}: firmas registradas${i.value.novedades ? ' con novedades. Crea la solicitud de reparación.' : '. Inventario cerrado.'}`)
const aReparacion = async () => {
  busy.value = true
  try {
    const r = await api.reparacionDesde(i.value.id)
    emit('changed', `${r.code} creada con las novedades de ${i.value.code}. Está en «Mantenimiento y reparaciones».`)
  } catch (e) {
    emit('error', apiErrorMessage(e))
  } finally {
    busy.value = false
  }
}
const eliminar = () => run(() => api.eliminarInventario(i.value.id), `${i.value.code} eliminado.`)
</script>

<template>
  <div class="card stack" :class="{ 'b-nov': i.estado === 'con_novedades' }">
    <div class="sb top">
      <div>
        <b class="t15">{{ i.code }} · {{ i.tipo_txt }} · {{ i.inmueble.codigo }} {{ i.inmueble.titulo }}</b>
        <div class="mut small">{{ i.referencia }}</div>
      </div>
      <span class="chip" :class="INV_CLS[i.estado]">{{ i.estado === 'firmado' ? '✓ ' : '' }}{{ i.estado_txt }}</span>
    </div>
    <div class="datos">
      <div v-for="[k, v, c] in datos" :key="k"><span class="mut">{{ k }}</span><br><b :class="c">{{ v }}</b></div>
    </div>
    <div v-if="nov.length" class="mut tiny">
      Novedades: {{ nov.map((a) => `${a.nombre} (${a.estado}${a.observacion ? `: ${a.observacion}` : ''})`).join(' · ') }}
    </div>
    <div class="row fw gap6">
      <button type="button" class="fch" @click="emit('toggle')">{{ open ? 'Cerrar' : i.estado === 'programado' || i.estado === 'realizado' ? 'Abrir inventario' : 'Ver inventario' }}</button>
      <span v-if="i.reparacion_code" class="chip gray">Reparación {{ i.reparacion_code }}</span>
    </div>

    <div v-if="open" class="panel">
      <div class="lbl">Estado de cada ambiente</div>
      <div v-for="a in i.ambientes" :key="a.id" class="amb">
        <div class="amb-n">
          <b>{{ a.nombre }}</b>
          <span v-if="!i.puede_llenar && a.observacion" class="mut tiny"> · {{ a.observacion }}</span>
          <span v-if="!a.estado" class="mut tiny"> · sin revisar</span>
          <input
            v-if="i.puede_llenar"
            v-model="obs[a.id]"
            class="in obs"
            :placeholder="a.observacion ?? 'Observación (obligatoria si es regular o malo)'"
            :aria-label="`Observación de ${a.nombre}`"
            @change="a.estado && guardarObs(a.id)"
          >
        </div>
        <span class="row gap4 fw">
          <button
            v-for="[k, l] in AMB"
            :key="k"
            type="button"
            class="fch"
            :class="{ on: a.estado === k }"
            :style="a.estado === k ? { background: AMB_COLOR[k], borderColor: AMB_COLOR[k] } : {}"
            :disabled="!i.puede_llenar || busy"
            @click="marcar(a.id, k)"
          >{{ l }}</button>
          <button type="button" class="fch" :disabled="!i.puede_llenar || busy" :title="i.puede_llenar ? 'Agregar una foto' : ''" @click="foto(a.id, a.fotos)">📷 {{ a.fotos }}</button>
        </span>
      </div>
      <div class="row fw gap8 small">
        <span>{{ firmas }}</span>
        <button v-if="i.puede_gestionar && i.estado === 'realizado'" type="button" class="btn bp sm" :disabled="busy" @click="firmar">Registrar firmas y cerrar el inventario</button>
        <button v-if="i.puede_gestionar && i.novedades && !i.reparacion_code && i.estado !== 'programado'" type="button" class="btn bs sm" :disabled="busy" @click="aReparacion">Crear solicitud de reparación con las novedades</button>
      </div>
      <div v-for="(e, n) in i.eventos" :key="n" class="mut tiny">· {{ e.titulo }}{{ e.detalle ? ` · ${e.detalle}` : '' }} · {{ fmtCuando(e.created_at) }}</div>
      <div v-if="i.puede_gestionar && i.estado === 'programado'" class="row"><button type="button" class="btn br sm" :disabled="busy" @click="eliminar">Eliminar</button></div>
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
.amb {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
  padding: 5px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.amb-n {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  flex: 1 1 260px;
  min-width: 0;
}
.obs {
  min-height: 32px;
  font-size: 12.5px;
  flex: 1 1 200px;
  max-width: 340px;
}
.b-nov {
  border: 1.5px solid #e8b4ac;
}
.gap4 {
  gap: 4px;
}
.gap8 {
  gap: 8px;
}
</style>
