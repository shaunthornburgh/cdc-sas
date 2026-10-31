<script setup lang="ts">
import type { Inmueble, InmuebleIn, InmuebleOpciones } from '~/types/inmuebles'

/** Register a property by hand (Coordinación / Gerencia) or edit its data. */
const props = defineProps<{ opciones: InmuebleOpciones; inmueble?: Inmueble | null; manager: boolean }>()
const emit = defineEmits<{ saved: [i: Inmueble, msg: string]; cancel: [] }>()
const api = useInmuebles()
const i = props.inmueble
const f = reactive({
  codigo: i?.codigo ?? '',
  negocio: i?.negocio ?? 'arriendo',
  tipo_inmueble: i?.tipo_inmueble ?? 'apartamento',
  direccion: i?.direccion ?? '',
  zona: i?.zona ?? '',
  barrio: i?.barrio ?? '',
  municipio: i?.municipio ?? 'Medellín',
  precio: i?.precio ? i.precio.toLocaleString('es-CO') : '',
  administracion: i?.administracion ? i.administracion.toLocaleString('es-CO') : '',
  area_m2: i?.area_m2 ?? '',
  habitaciones: i?.habitaciones ?? ('' as number | ''),
  banos: i?.banos ?? ('' as number | ''),
  parqueadero: i?.parqueadero ?? false,
  estrato: i?.estrato ?? ('' as number | ''),
  descripcion: i?.descripcion ?? '',
  propietario_nombre: i?.propietario_nombre ?? '',
  propietario_telefono: i?.propietario_telefono ?? '',
})
const error = ref<string | null>(null)
const busy = ref(false)
const n = (v: number | string | '') => (v === '' || v === null ? null : Number(v))

async function guardar() {
  error.value = null
  if (!f.codigo.trim() || f.direccion.trim().length < 5) return (error.value = 'Completa el código y la dirección.')
  const body: InmuebleIn = {
    tipo_inmueble: f.tipo_inmueble,
    direccion: f.direccion,
    zona: f.zona || null,
    barrio: f.barrio || null,
    municipio: f.municipio || null,
    precio: parsePesos(f.precio) || null,
    administracion: parsePesos(f.administracion) || null,
    area_m2: f.area_m2 ? String(f.area_m2).replace(',', '.') : null,
    habitaciones: n(f.habitaciones),
    banos: n(f.banos),
    parqueadero: f.parqueadero,
    estrato: n(f.estrato),
    descripcion: f.descripcion || null,
  }
  if (!i || i.ve_propietario) Object.assign(body, { propietario_nombre: f.propietario_nombre || null, propietario_telefono: f.propietario_telefono || null })
  if (!i || props.manager) Object.assign(body, { codigo: f.codigo, negocio: f.negocio })
  busy.value = true
  try {
    const out = i ? await api.update(i.id, body) : await api.create(body)
    emit('saved', out, i ? `${out.codigo}: datos guardados. El cambio queda en su historial.` : `${out.codigo} registrado como disponible.`)
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="card stack" @submit.prevent="guardar">
    <div class="sb">
      <b>{{ i ? `Editar ${i.codigo}` : 'Registrar inmueble' }}</b>
      <button type="button" class="btn bs sm" @click="emit('cancel')">Cancelar</button>
    </div>
    <div class="g4">
      <div class="fld"><label for="if-c">Código <span class="req">*</span></label><input id="if-c" v-model="f.codigo" class="in" placeholder="INM-0360" :disabled="!!i && !manager"></div>
      <div class="fld">
        <label for="if-n">Negocio <span class="req">*</span></label>
        <select id="if-n" v-model="f.negocio" class="in" :disabled="!!i && !manager"><option value="arriendo">Arriendo</option><option value="venta">Venta</option></select>
      </div>
      <div class="fld">
        <label for="if-t">Tipo de inmueble</label>
        <select id="if-t" v-model="f.tipo_inmueble" class="in"><option v-for="t in TIPOS_INMUEBLE" :key="t" :value="t">{{ TIPO_INMUEBLE_LABELS[t] }}</option></select>
      </div>
      <div class="fld">
        <label for="if-z">Zona</label>
        <select id="if-z" v-model="f.zona" class="in"><option value="">Sin zona</option><option v-for="z in opciones.zonas" :key="z">{{ z }}</option></select>
      </div>
      <div class="fld span2"><label for="if-d">Dirección <span class="req">*</span></label><input id="if-d" v-model="f.direccion" class="in" placeholder="Cl 33 # 80-20 apto 402"></div>
      <div class="fld"><label for="if-b">Barrio</label><input id="if-b" v-model="f.barrio" class="in"></div>
      <div class="fld"><label for="if-m">Municipio</label><input id="if-m" v-model="f.municipio" class="in"></div>
      <div class="fld"><label for="if-p">{{ f.negocio === 'venta' ? 'Precio de venta' : 'Canon mensual' }}</label><input id="if-p" v-model="f.precio" class="in" inputmode="numeric" placeholder="$0"></div>
      <div class="fld"><label for="if-a">Administración</label><input id="if-a" v-model="f.administracion" class="in" inputmode="numeric" placeholder="$0"></div>
      <div class="fld"><label for="if-ar">Área (m²)</label><input id="if-ar" v-model="f.area_m2" class="in" inputmode="decimal"></div>
      <div class="fld"><label for="if-e">Estrato</label><input id="if-e" v-model="f.estrato" class="in" type="number" min="1" max="6"></div>
      <div class="fld"><label for="if-h">Habitaciones</label><input id="if-h" v-model="f.habitaciones" class="in" type="number" min="0" max="30"></div>
      <div class="fld"><label for="if-ba">Baños</label><input id="if-ba" v-model="f.banos" class="in" type="number" min="0" max="30"></div>
      <div class="fld">
        <span class="fld-label">Parqueadero</span>
        <div class="pair">
          <button type="button" class="opt" :class="{ on: f.parqueadero }" @click="f.parqueadero = true">Sí</button>
          <button type="button" class="opt" :class="{ on: !f.parqueadero }" @click="f.parqueadero = false">No</button>
        </div>
      </div>
      <template v-if="!i || i.ve_propietario">
        <div class="fld"><label for="if-po">Propietario</label><input id="if-po" v-model="f.propietario_nombre" class="in"></div>
        <div class="fld"><label for="if-pt">Teléfono del propietario</label><input id="if-pt" v-model="f.propietario_telefono" class="in" type="tel"></div>
      </template>
    </div>
    <div class="fld"><label for="if-de">Descripción</label><textarea id="if-de" v-model="f.descripcion" class="in" placeholder="Lo que hay que saber para ofrecerlo" /></div>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
    <div><button type="submit" class="btn bp" :disabled="busy">{{ busy ? 'Guardando…' : 'Guardar' }}</button></div>
  </form>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.span2 {
  grid-column: span 2;
}
.pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
@media (max-width: 760px) {
  .span2 {
    grid-column: auto;
  }
}
</style>
