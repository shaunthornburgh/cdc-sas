<script setup lang="ts">
import type { FetchError } from 'ofetch'
import type { TipoInmueble } from '~/types/captaciones'
import type { TipoNegocio } from '~/types/leads'
import type { Pedido, PedidoOpciones, Urgencia } from '~/types/pedidos'

/** «Nuevo pedido» (K06 / M06): one form; warns if the client already has an open pedido. */
const props = defineProps<{ opciones: PedidoOpciones }>()
const emit = defineEmits<{ created: [p: Pedido]; cancel: []; actualizar: [code: string] }>()
const auth = useAuth()
const pedidos = usePedidos()

const f = reactive({
  cliente_nombre: '',
  cliente_telefono: '',
  negocio: 'arriendo' as TipoNegocio,
  tipo_inmueble: 'apartamento' as TipoInmueble,
  zona: props.opciones.zonas[0] ?? '',
  presupuesto: '',
  fecha: localDate(5),
  hora: '18:00',
  urgencia: 'normal' as Urgencia,
  responsable_id: '',
  observaciones: '',
})
const error = ref<string | null>(null)
const dup = ref<string | null>(null)
const saving = ref(false)
const first = ref<HTMLInputElement | null>(null)
onMounted(() => first.value?.focus())

const dupCode = computed(() => dup.value?.match(/PED-\d+/)?.[0] ?? null)

async function save(otra = false) {
  error.value = null
  if (!f.cliente_nombre.trim() || !parsePesos(f.presupuesto) || !f.fecha) {
    error.value = 'Completa el cliente, el presupuesto y la fecha límite.'
    return
  }
  saving.value = true
  try {
    const p = await pedidos.create({
      cliente_nombre: f.cliente_nombre,
      cliente_telefono: f.cliente_telefono.trim() || null,
      negocio: f.negocio,
      tipo_inmueble: f.tipo_inmueble,
      zona: f.zona,
      presupuesto: parsePesos(f.presupuesto),
      fecha_limite: toIso(f.fecha, f.hora || '18:00'),
      urgencia: f.urgencia,
      observaciones: f.observaciones.trim() || null,
      responsable_id: f.responsable_id || null,
      otra_necesidad: otra,
    })
    dup.value = null
    emit('created', p)
  } catch (e) {
    if ((e as FetchError)?.response?.status === 409) dup.value = apiErrorMessage(e)
    else error.value = apiErrorMessage(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <form class="card focus stack" @submit.prevent="save()">
    <div class="sb">
      <b class="title">Nuevo pedido</b>
      <button type="button" class="btn bs sm" @click="emit('cancel')">Cancelar</button>
    </div>
    <div class="g4">
      <div class="fld"><label for="pf-c">Cliente <span class="req">*</span></label><input id="pf-c" ref="first" v-model="f.cliente_nombre" class="in" placeholder="Nombre del cliente"></div>
      <div class="fld"><label for="pf-t">Teléfono</label><input id="pf-t" v-model="f.cliente_telefono" class="in" type="tel" placeholder="300 000 0000"></div>
      <div class="fld">
        <span class="fld-label">Tipo de negocio <span class="req">*</span></span>
        <div class="pair" role="radiogroup" aria-label="Tipo de negocio">
          <button v-for="n in (['venta', 'arriendo'] as const)" :key="n" type="button" class="opt" :class="{ on: f.negocio === n }" role="radio" :aria-checked="f.negocio === n" @click="f.negocio = n">{{ NEGOCIO_LABELS[n] }}</button>
        </div>
      </div>
      <div class="fld">
        <label for="pf-i">Tipo de inmueble <span class="req">*</span></label>
        <select id="pf-i" v-model="f.tipo_inmueble" class="in"><option v-for="t in TIPOS_INMUEBLE" :key="t" :value="t">{{ TIPO_INMUEBLE_LABELS[t] }}</option></select>
      </div>
      <div class="fld">
        <label for="pf-z">Zona <span class="req">*</span></label>
        <select id="pf-z" v-model="f.zona" class="in"><option v-for="z in opciones.zonas" :key="z">{{ z }}</option></select>
      </div>
      <div class="fld"><label for="pf-p">Presupuesto del cliente <span class="req">*</span></label><input id="pf-p" v-model="f.presupuesto" class="in" inputmode="numeric" :placeholder="f.negocio === 'venta' ? 'Ej: hasta $500.000.000' : 'Ej: hasta $2.500.000'"></div>
      <div class="fld"><label for="pf-f">Fecha límite <span class="req">*</span></label><input id="pf-f" v-model="f.fecha" class="in" type="date" :min="localDate()"></div>
      <div class="fld"><label for="pf-h">Hora límite</label><input id="pf-h" v-model="f.hora" class="in" type="time" step="900"></div>
      <div class="fld">
        <label for="pf-u">Urgencia</label>
        <select id="pf-u" v-model="f.urgencia" class="in"><option value="normal">Normal</option><option value="alta">Alta</option><option value="urgente">Urgente</option></select>
      </div>
      <div class="fld">
        <label for="pf-r">Responsable</label>
        <select id="pf-r" v-model="f.responsable_id" class="in">
          <option value="">{{ canUsePedidos(auth.user.value) && !isManager(auth.user.value) ? 'Yo' : 'Elige…' }}</option>
          <option v-for="r in opciones.responsables.filter((x) => x.id !== auth.user.value?.id)" :key="r.id" :value="r.id">{{ r.full_name }}</option>
        </select>
      </div>
    </div>
    <div class="fld"><label for="pf-o">Observaciones</label><textarea id="pf-o" v-model="f.observaciones" class="in" placeholder="Qué busca el cliente" /></div>

    <div v-if="dup" class="dup" role="alert">
      <b>{{ dup.split(':')[0] }}</b>
      <span>{{ dup.split(':').slice(1).join(':').trim() }}</span>
      <div class="g2">
        <button v-if="dupCode" type="button" class="btn bp sm" @click="emit('actualizar', dupCode)">Actualizar {{ dupCode }}</button>
        <button type="button" class="btn bs sm" :disabled="saving" @click="save(true)">Es otra necesidad</button>
      </div>
    </div>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
    <div class="mut tiny">Antes de guardar, el sistema revisa si el cliente ya tiene un pedido abierto y propone actualizarlo en lugar de crear otro.</div>
    <div><button type="submit" class="btn bp" :disabled="saving">{{ saving ? 'Guardando…' : 'Guardar pedido' }}</button></div>
  </form>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.title {
  font-size: 17px;
}
.tiny {
  font-size: 12px;
}
.pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.pair .opt {
  min-height: 42px;
}
.dup {
  background: var(--cdc-warn-bg);
  border: 1.5px solid #b7791f;
  border-radius: 12px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
  color: #5c3b00;
}
</style>
