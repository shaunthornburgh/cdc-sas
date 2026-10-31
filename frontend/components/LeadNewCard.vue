<script setup lang="ts">
import type { FuenteLead, LeadDetail, TipoNegocio } from '~/types/leads'

/** Register a lead by hand (phone call, walk-in…). Integrations will create the rest. */
const emit = defineEmits<{ cancel: []; created: [lead: LeadDetail] }>()
const leads = useLeads()

const form = reactive({
  full_name: '',
  phone: '',
  email: '',
  fuente: 'facebook' as FuenteLead,
  fuente_detalle: '',
  negocio: 'arriendo' as TipoNegocio,
  busca: '',
  presupuesto: '',
  zona: '',
  para_cuando: '',
  seguir: true,
})
const error = ref<string | null>(null)
const saving = ref(false)
const first = ref<HTMLInputElement | null>(null)
onMounted(() => first.value?.focus())

const opt = (v: string) => v.trim() || null

async function save() {
  error.value = null
  saving.value = true
  try {
    emit(
      'created',
      await leads.create({
        full_name: form.full_name,
        phone: form.phone,
        email: opt(form.email),
        fuente: form.fuente,
        fuente_detalle: opt(form.fuente_detalle),
        negocio: form.negocio,
        busca: opt(form.busca),
        presupuesto: opt(form.presupuesto),
        zona: opt(form.zona),
        para_cuando: opt(form.para_cuando),
        seguir: form.seguir,
      }),
    )
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <form class="card focus stack" @submit.prevent="save">
    <div class="sb">
      <b class="title">Registrar lead</b>
      <button type="button" class="btn bs sm" @click="emit('cancel')">Cancelar</button>
    </div>
    <div class="note">Los leads de plataformas y redes llegan solos. Usa esto para un cliente que llamó o vino a la oficina.</div>

    <div class="lbl">Cliente</div>
    <div class="g3">
      <div class="fld">
        <label for="nl-name">Nombre <span class="req">*</span></label>
        <input id="nl-name" ref="first" v-model="form.full_name" class="in" required maxlength="200">
      </div>
      <div class="fld">
        <label for="nl-phone">Teléfono <span class="req">*</span></label>
        <input id="nl-phone" v-model="form.phone" class="in" type="tel" placeholder="300 000 0000" required minlength="7">
      </div>
      <div class="fld">
        <label for="nl-email">Correo</label>
        <input id="nl-email" v-model.trim="form.email" class="in" type="email" placeholder="nombre@correo.com">
      </div>
    </div>

    <div class="lbl">Qué busca</div>
    <div class="row opts" role="radiogroup" aria-label="Negocio">
      <button
        v-for="n in (['arriendo', 'venta'] as const)"
        :key="n"
        type="button"
        class="opt"
        :class="{ on: form.negocio === n }"
        role="radio"
        :aria-checked="form.negocio === n"
        @click="form.negocio = n"
      >
        {{ NEGOCIO_LABELS[n] }}
      </button>
    </div>
    <div class="g4">
      <div class="fld"><label for="nl-busca">Inmueble</label><input id="nl-busca" v-model="form.busca" class="in" placeholder="Apartamento de 2 habitaciones"></div>
      <div class="fld"><label for="nl-zona">Zona</label><input id="nl-zona" v-model="form.zona" class="in" placeholder="Laureles o Belén"></div>
      <div class="fld"><label for="nl-pres">Presupuesto</label><input id="nl-pres" v-model="form.presupuesto" class="in" placeholder="Hasta $2.500.000"></div>
      <div class="fld"><label for="nl-cuando">¿Para cuándo?</label><input id="nl-cuando" v-model="form.para_cuando" class="in" placeholder="Este mes"></div>
    </div>

    <div class="lbl">Llegó desde</div>
    <div class="g3">
      <div class="fld">
        <label for="nl-fuente">Fuente <span class="req">*</span></label>
        <select id="nl-fuente" v-model="form.fuente" class="in">
          <optgroup v-for="g in FUENTE_GRUPOS" :key="g.label" :label="g.label">
            <option v-for="f in g.fuentes" :key="f" :value="f">{{ FUENTE_LABELS[f] }}</option>
          </optgroup>
        </select>
      </div>
      <div class="fld">
        <label for="nl-fdet">Detalle</label>
        <input id="nl-fdet" v-model="form.fuente_detalle" class="in" placeholder="Campaña, anuncio, referido…">
      </div>
    </div>

    <label class="check"><input v-model="form.seguir" type="checkbox"> Seguir este lead (quedo como responsable)</label>

    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
    <div><button type="submit" class="btn bp" :disabled="saving">{{ saving ? 'Guardando…' : 'Guardar lead' }}</button></div>
  </form>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.title {
  font-size: 18px;
}
.opts {
  flex-wrap: wrap;
}
.check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
</style>
