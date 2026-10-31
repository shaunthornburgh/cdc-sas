<script setup lang="ts">
import type { Inmueble } from '~/types/inmuebles'
import type { Pedido, PedidoOpciones } from '~/types/pedidos'

/**
 * Everything you can do on one pedido (M06 / K06):
 * responsable or Coordinación → Actualizar · Atendido · Perdido (and Extender / Marcar perdido
 * when it expired); everyone else → Proponer un inmueble · Comentar al responsable;
 * managers → Reasignar. Plus the history (before / after).
 */
const props = defineProps<{ pedido: Pedido; opciones: PedidoOpciones; manager?: boolean; startWith?: string | null }>()
const emit = defineEmits<{ changed: [p: Pedido, msg: string] }>()
const pedidos = usePedidos()

type F = 'upd' | 'aten' | 'per' | 'ext' | 'prop' | 'com' | 'reas' | 'his'
const form = ref<F | null>(null)
const p = computed(() => props.pedido)
const abierto = computed(() => p.value.estado === 'abierto')
const busy = ref(false)
const error = ref<string | null>(null)

const upd = reactive({ presupuesto: '', zona: '', fecha: '', hora: '18:00', urgencia: '', que: '' })
const ext = reactive({ fecha: localDate(3), hora: '18:00', motivo: '' })
const per = reactive({ motivo: '' as string, nota: '' })
const nota = ref('')
const prop = reactive({ inmueble: '', nota: '' })
const reas = ref(p.value.responsable.id)
// «Proponer un inmueble»: pick an available property of the same business type.
const inmApi = useInmuebles()
const catalogo = ref<Inmueble[] | null>(null)
async function cargarCatalogo() {
  try {
    catalogo.value = (await inmApi.list({ estado: 'disponible', negocio: p.value.negocio, zona: p.value.zona })).items
    if (!catalogo.value.length) catalogo.value = (await inmApi.list({ estado: 'disponible', negocio: p.value.negocio })).items
  } catch {
    catalogo.value = []
  }
}
function elegir(e: Event) {
  const i = catalogo.value?.find((x) => x.id === (e.target as HTMLSelectElement).value)
  if (i) prop.inmueble = `${i.codigo} · ${i.titulo} · ${i.direccion}${i.precio ? ` · ${fmtCOP(i.precio)}` : ''}`
}

function toggle(f: F) {
  form.value = form.value === f ? null : f
  error.value = null
  if (f === 'prop' && form.value === 'prop' && catalogo.value === null) cargarCatalogo()
  if (f === 'upd') {
    Object.assign(upd, {
      presupuesto: String(p.value.presupuesto),
      zona: p.value.zona,
      fecha: new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota' }).format(new Date(p.value.fecha_limite)),
      hora: fmtHora(p.value.fecha_limite).padStart(5, '0'),
      urgencia: p.value.urgencia,
      que: '',
    })
  }
}

// Opened from elsewhere (e.g. «Actualizar PED-031» in the duplicate warning): open that form, prefilled.
watch(
  () => props.startWith,
  (f) => {
    if (f && form.value !== f) toggle(f as F)
  },
  { immediate: true },
)

async function run(fn: () => Promise<Pedido>, msg: string) {
  busy.value = true
  error.value = null
  try {
    emit('changed', await fn(), msg)
    form.value = null
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    busy.value = false
  }
}

function guardarUpd() {
  if (!upd.que.trim()) return (error.value = 'Escribe qué cambió.')
  const body: Record<string, unknown> = { que_cambio: upd.que }
  const pres = parsePesos(upd.presupuesto)
  if (pres && pres !== p.value.presupuesto) body.presupuesto = pres
  if (upd.zona !== p.value.zona) body.zona = upd.zona
  if (upd.urgencia !== p.value.urgencia) body.urgencia = upd.urgencia
  const fl = toIso(upd.fecha, upd.hora)
  if (new Date(fl).getTime() !== new Date(p.value.fecha_limite).getTime()) body.fecha_limite = fl
  run(() => pedidos.actualizar(p.value.id, body as never), `${p.value.code} actualizado. El historial guarda lo de antes y lo de después.`)
}
const guardarExt = () =>
  ext.motivo.trim()
    ? run(() => pedidos.extender(p.value.id, toIso(ext.fecha, ext.hora), ext.motivo), `${p.value.code}: nueva fecha límite guardada.`)
    : (error.value = 'Escribe el motivo.')
const guardarPer = () =>
  per.motivo
    ? run(() => pedidos.perdido(p.value.id, per.motivo as never, per.nota || null), `${p.value.code} marcado como perdido. Sale de tu lista y queda para Gerencia.`)
    : (error.value = 'Elige el motivo.')
const guardarAten = () => run(() => pedidos.atendido(p.value.id, nota.value || null), `${p.value.code} atendido. Sale de tu lista y queda para Gerencia.`)
const guardarProp = () =>
  prop.inmueble.trim()
    ? run(() => pedidos.proponer(p.value.id, prop.inmueble, prop.nota || null), `Propuesta enviada a ${p.value.responsable.full_name}. Quedó en el historial.`)
    : (error.value = 'Escribe el inmueble que propones.')
const guardarCom = () =>
  nota.value.trim()
    ? run(() => pedidos.comentar(p.value.id, nota.value), `Comentario enviado a ${p.value.responsable.full_name}.`)
    : (error.value = 'Escribe el comentario.')
const guardarReas = () => run(() => pedidos.reasignar(p.value.id, reas.value), `${p.value.code} reasignado.`)
</script>

<template>
  <div class="acts">
    <template v-if="abierto && p.can_edit">
      <div v-if="p.vencido" class="venc">
        <b>Pedido vencido: revisa y decide qué pasa con el cliente.</b>
        <span class="tiny">{{ p.code }} · {{ p.cliente_nombre }} · {{ NEGOCIO_LABELS[p.negocio] }} · {{ p.zona }} · venció {{ fmtCuando(p.fecha_limite) }}</span>
        <div class="g2">
          <button type="button" class="btn bs sm" :class="{ on: form === 'ext' }" @click="toggle('ext')">Extender fecha</button>
          <button type="button" class="btn br sm" @click="toggle('per')">Marcar perdido</button>
        </div>
      </div>
      <div v-else class="row wrap">
        <button type="button" class="btn bs sm" @click="toggle('upd')">Actualizar</button>
        <button type="button" class="btn bs sm" @click="toggle('aten')">Atendido</button>
        <button type="button" class="btn br sm" @click="toggle('per')">Perdido</button>
        <button type="button" class="btn bs sm ghost" @click="toggle('his')">Historial ({{ p.eventos.length }})</button>
      </div>
    </template>
    <template v-else-if="abierto">
      <div class="g2 grow2">
        <button type="button" class="btn bp sm" @click="toggle('prop')">Proponer un inmueble</button>
        <button type="button" class="btn bs sm" @click="toggle('com')">Comentar al responsable</button>
      </div>
      <button type="button" class="btn bs sm ghost self-start" @click="toggle('his')">Historial ({{ p.eventos.length }})</button>
    </template>
    <button v-else type="button" class="btn bs sm ghost self-start" @click="toggle('his')">Historial ({{ p.eventos.length }})</button>
    <div v-if="manager && abierto" class="row wrap reas">
      <select v-model="reas" class="sel" aria-label="Responsable">
        <option v-for="r in opciones.responsables" :key="r.id" :value="r.id">{{ r.full_name }}</option>
      </select>
      <button type="button" class="btn bs sm" :disabled="busy || reas === p.responsable.id" @click="guardarReas">Reasignar</button>
    </div>

    <div v-if="form === 'upd'" class="panel">
      <div class="g4">
        <div class="fld"><label :for="`u-p-${p.id}`">Presupuesto del cliente</label><input :id="`u-p-${p.id}`" v-model="upd.presupuesto" class="in" inputmode="numeric"></div>
        <div class="fld"><label :for="`u-z-${p.id}`">Zona</label><select :id="`u-z-${p.id}`" v-model="upd.zona" class="in"><option v-for="z in opciones.zonas" :key="z">{{ z }}</option></select></div>
        <div class="fld"><label :for="`u-f-${p.id}`">Fecha límite</label><input :id="`u-f-${p.id}`" v-model="upd.fecha" class="in" type="date" :min="localDate()"></div>
        <div class="fld"><label :for="`u-u-${p.id}`">Urgencia</label><select :id="`u-u-${p.id}`" v-model="upd.urgencia" class="in"><option value="normal">Normal</option><option value="alta">Alta</option><option value="urgente">Urgente</option></select></div>
      </div>
      <div class="fld"><label :for="`u-q-${p.id}`">¿Qué cambió? <span class="req">*</span></label><input :id="`u-q-${p.id}`" v-model="upd.que" class="in" placeholder="Ej.: ahora busca 3 habitaciones"></div>
      <div><button type="button" class="btn bp" :disabled="busy" @click="guardarUpd">Guardar cambios</button></div>
    </div>
    <div v-if="form === 'aten'" class="panel">
      <div class="fld"><label :for="`a-${p.id}`">Qué se hizo (opcional)</label><input :id="`a-${p.id}`" v-model="nota" class="in" placeholder="Ej.: se enviaron 4 opciones · cita agendada"></div>
      <div><button type="button" class="btn bp" :disabled="busy" @click="guardarAten">Marcar atendido</button></div>
    </div>
    <div v-if="form === 'ext'" class="panel">
      <div class="g3">
        <div class="fld"><label :for="`e-f-${p.id}`">Nueva fecha límite <span class="req">*</span></label><input :id="`e-f-${p.id}`" v-model="ext.fecha" class="in" type="date" :min="localDate()"></div>
        <div class="fld"><label :for="`e-h-${p.id}`">Hora</label><input :id="`e-h-${p.id}`" v-model="ext.hora" class="in" type="time" step="900"></div>
        <div class="fld"><label :for="`e-m-${p.id}`">Motivo <span class="req">*</span></label><input :id="`e-m-${p.id}`" v-model="ext.motivo" class="in" placeholder="Ej.: el cliente pidió más tiempo"></div>
      </div>
      <div><button type="button" class="btn bp" :disabled="busy" @click="guardarExt">Guardar nueva fecha</button></div>
    </div>
    <div v-if="form === 'per'" class="panel">
      <div class="g2">
        <div class="fld">
          <label :for="`p-m-${p.id}`">Motivo <span class="req">*</span></label>
          <select :id="`p-m-${p.id}`" v-model="per.motivo" class="in"><option value="" disabled>Elige…</option><option v-for="(t, k) in opciones.motivos" :key="k" :value="k">{{ t }}</option></select>
        </div>
        <div class="fld"><label :for="`p-n-${p.id}`">Nota</label><input :id="`p-n-${p.id}`" v-model="per.nota" class="in" placeholder="Opcional"></div>
      </div>
      <div><button type="button" class="btn br" :disabled="busy" @click="guardarPer">Confirmar perdido</button></div>
    </div>
    <div v-if="form === 'prop'" class="panel">
      <div v-if="catalogo?.length" class="fld">
        <label :for="`pr-c-${p.id}`">Elegir del catálogo ({{ catalogo.length }} disponibles)</label>
        <select :id="`pr-c-${p.id}`" class="in" @change="elegir">
          <option value="">Elige un inmueble…</option>
          <option v-for="i in catalogo" :key="i.id" :value="i.id">{{ i.codigo }} · {{ i.titulo }}{{ i.precio ? ` · ${fmtCOP(i.precio)}` : '' }}</option>
        </select>
      </div>
      <div class="fld"><label :for="`pr-i-${p.id}`">Inmueble que propones <span class="req">*</span></label><input :id="`pr-i-${p.id}`" v-model="prop.inmueble" class="in" placeholder="INM-0351 · Cl 33 # 80-20, Belén"></div>
      <div class="fld"><label :for="`pr-n-${p.id}`">Nota para {{ p.responsable.full_name }}</label><input :id="`pr-n-${p.id}`" v-model="prop.nota" class="in" placeholder="Ej.: el propietario acepta mascotas"></div>
      <div><button type="button" class="btn bp" :disabled="busy" @click="guardarProp">Enviar propuesta</button></div>
    </div>
    <div v-if="form === 'com'" class="panel">
      <div class="fld"><label :for="`c-${p.id}`">Comentario <span class="req">*</span></label><input :id="`c-${p.id}`" v-model="nota" class="in" placeholder="Ej.: conozco al cliente, prefiere visitas en la tarde"></div>
      <div><button type="button" class="btn bp" :disabled="busy" @click="guardarCom">Enviar comentario</button></div>
    </div>
    <div v-if="form === 'his'" class="panel">
      <div v-for="(e, i) in [...p.eventos].reverse()" :key="i" class="it">
        <div class="sb"><b class="small">{{ e.titulo }}</b><span class="mut tiny">{{ fmtCuando(e.created_at) }}</span></div>
        <span v-if="e.detalle" class="mut small">{{ e.detalle }}</span>
        <span class="mut tiny">{{ e.created_by_name ?? 'Sistema' }}</span>
      </div>
    </div>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
  </div>
</template>

<style scoped>
.acts {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.wrap {
  flex-wrap: wrap;
  gap: 6px;
}
.tiny {
  font-size: 12px;
}
.small {
  font-size: 12.5px;
}
.ghost {
  border-color: var(--cdc-border);
  color: var(--cdc-muted);
}
.self-start {
  align-self: flex-start;
}
.grow2 {
  gap: 6px;
}
.reas {
  gap: 6px;
}
.venc {
  background: var(--cdc-bad-bg);
  border: 1.5px solid var(--cdc-bad);
  border-radius: 14px;
  padding: 12px;
  color: #7a1d14;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
}
</style>
