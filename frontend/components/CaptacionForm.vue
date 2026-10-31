<script setup lang="ts">
import type { Captacion, ModoCaptacion, TipoInmueble } from '~/types/captaciones'
import type { TipoNegocio, UserRef } from '~/types/leads'

/**
 * «Nueva captación» (prototype M15): Registro rápido or Formulario completo.
 * Captadores send their own (with browser location); managers pick the captador.
 */
const props = defineProps<{ captadores?: UserRef[] | null; cancelable?: boolean }>()
const emit = defineEmits<{ created: [cap: Captacion]; cancel: [] }>()

const auth = useAuth()
const caps = useCaptaciones()
const forOthers = computed(() => !!props.captadores)

const modo = ref<ModoCaptacion>('rapido')
const f = reactive({
  asesor_id: '',
  negocio: 'venta' as TipoNegocio,
  codigo_inmueble: '',
  direccion: '',
  tipo_inmueble: '' as TipoInmueble | '',
  barrio: '',
  municipio: 'Medellín',
  precio: '',
  area_m2: '',
  habitaciones: '',
  banos: '',
  parqueadero: 'no',
  propietario_nombre: '',
  propietario_telefono: '',
  observaciones: '',
})
const precioLbl = computed(() => (f.negocio === 'venta' ? 'Precio de venta' : 'Canon de arriendo'))

const confirmOpen = ref(false)
const sending = ref(false)
const dup = ref<string | null>(null)
const error = ref<string | null>(null)
const sinUbicacion = ref(false)

const num = (v: string) => (v.trim() ? Number(v.replace(/[^\d.]/g, '')) : null)
const txt = (v: string) => v.trim() || null

function ask() {
  error.value = null
  dup.value = null
  if (forOthers.value && !f.asesor_id) return (error.value = 'Elige el asesor que hizo la captación.')
  if (!f.codigo_inmueble.trim() || !f.direccion.trim()) return (error.value = 'Escribe el código de la propiedad y la dirección.')
  confirmOpen.value = true
}

async function send() {
  sending.value = true
  sinUbicacion.value = false
  try {
    // Location is taken only when the captador sends their own captación (G-002: GPS ⇔ Captación).
    const ownSend = !forOthers.value || f.asesor_id === auth.user.value?.id
    const gps = ownSend ? await tomarUbicacion() : null
    if (ownSend && !gps) sinUbicacion.value = true
    const completo = modo.value === 'completo'
    const cap = await caps.create({
      modo: modo.value,
      negocio: f.negocio,
      codigo_inmueble: f.codigo_inmueble,
      direccion: f.direccion,
      asesor_id: forOthers.value ? f.asesor_id || null : null,
      gps,
      ...(completo
        ? {
            tipo_inmueble: f.tipo_inmueble || null,
            barrio: txt(f.barrio),
            municipio: txt(f.municipio),
            precio: num(f.precio),
            area_m2: num(f.area_m2),
            habitaciones: num(f.habitaciones),
            banos: num(f.banos),
            parqueadero: f.parqueadero === 'si',
            propietario_nombre: txt(f.propietario_nombre),
            propietario_telefono: txt(f.propietario_telefono),
            observaciones: txt(f.observaciones),
          }
        : {}),
    })
    confirmOpen.value = false
    emit('created', cap)
    Object.assign(f, { codigo_inmueble: '', direccion: '', barrio: '', precio: '', area_m2: '', habitaciones: '', banos: '', propietario_nombre: '', propietario_telefono: '', observaciones: '' })
  } catch (e) {
    confirmOpen.value = false
    const msg = apiErrorMessage(e)
    if (msg.startsWith('Inmueble ya registrado')) dup.value = msg.replace(/^Inmueble ya registrado:\s*/, '')
    else error.value = msg
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <div class="stack">
    <div class="sb">
      <div class="tabs">
        <button type="button" class="tab" :class="{ on: modo === 'rapido' }" @click="modo = 'rapido'">Registro rápido</button>
        <button type="button" class="tab" :class="{ on: modo === 'completo' }" @click="modo = 'completo'">Formulario completo</button>
      </div>
      <button v-if="cancelable" type="button" class="btn bs sm" @click="emit('cancel')">Cancelar</button>
    </div>

    <form class="card stack" novalidate @submit.prevent="ask">
      <div class="mut small">
        {{ modo === 'rapido'
          ? 'Para inmuebles que ya están en la otra plataforma: solo el tipo, el código y la dirección.'
          : 'Para registrar todos los datos del inmueble.' }}
      </div>

      <div v-if="forOthers" class="fld">
        <label for="cf-ase">Asesor que captó <span class="req">*</span></label>
        <select id="cf-ase" v-model="f.asesor_id" class="in">
          <option value="" disabled>Elige…</option>
          <option v-for="c in captadores ?? []" :key="c.id" :value="c.id">{{ c.full_name }}</option>
        </select>
      </div>

      <div class="fld">
        <span class="fld-label">Para <span class="req">*</span></span>
        <div class="pair" role="radiogroup" aria-label="Para">
          <button v-for="n in (['venta', 'arriendo'] as const)" :key="n" type="button" class="opt" :class="{ on: f.negocio === n }" role="radio" :aria-checked="f.negocio === n" @click="f.negocio = n">
            {{ NEGOCIO_LABELS[n] }}
          </button>
        </div>
      </div>

      <div class="fld">
        <label for="cf-cod">Código de la propiedad <span class="req">*</span></label>
        <input id="cf-cod" v-model="f.codigo_inmueble" class="in" placeholder="Ej: INM-0362" autocomplete="off">
      </div>

      <template v-if="modo === 'completo'">
        <div class="fld">
          <label for="cf-tipo">Tipo de inmueble <span class="req">*</span></label>
          <select id="cf-tipo" v-model="f.tipo_inmueble" class="in">
            <option value="" disabled>Elige…</option>
            <option v-for="t in TIPOS_INMUEBLE" :key="t" :value="t">{{ TIPO_INMUEBLE_LABELS[t] }}</option>
          </select>
        </div>
      </template>

      <div class="fld">
        <label for="cf-dir">Dirección <span class="req">*</span></label>
        <input id="cf-dir" v-model="f.direccion" class="in" :placeholder="modo === 'rapido' ? 'Calle, número, barrio, municipio' : 'Calle, número, unidad'">
      </div>

      <template v-if="modo === 'completo'">
        <div class="g2">
          <div class="fld"><label for="cf-bar">Barrio <span class="req">*</span></label><input id="cf-bar" v-model="f.barrio" class="in" placeholder="Laureles"></div>
          <div class="fld">
            <label for="cf-mun">Municipio <span class="req">*</span></label>
            <select id="cf-mun" v-model="f.municipio" class="in"><option v-for="m in MUNICIPIOS" :key="m">{{ m }}</option></select>
          </div>
        </div>
        <div class="fld"><label for="cf-pre">{{ precioLbl }} <span class="req">*</span></label><input id="cf-pre" v-model="f.precio" class="in" inputmode="numeric" placeholder="$"></div>
        <div class="g4">
          <div class="fld"><label for="cf-area">Área (m²)</label><input id="cf-area" v-model="f.area_m2" class="in" inputmode="decimal" placeholder="72"></div>
          <div class="fld"><label for="cf-hab">Habitaciones</label><input id="cf-hab" v-model="f.habitaciones" class="in" inputmode="numeric" placeholder="3"></div>
          <div class="fld"><label for="cf-ban">Baños</label><input id="cf-ban" v-model="f.banos" class="in" inputmode="numeric" placeholder="2"></div>
          <div class="fld">
            <label for="cf-par">Parqueadero</label>
            <select id="cf-par" v-model="f.parqueadero" class="in"><option value="no">No</option><option value="si">Sí</option></select>
          </div>
        </div>
        <div class="g2">
          <div class="fld"><label for="cf-pn">Nombre del propietario <span class="req">*</span></label><input id="cf-pn" v-model="f.propietario_nombre" class="in" placeholder="Nombre completo"></div>
          <div class="fld"><label for="cf-pt">Teléfono del propietario <span class="req">*</span></label><input id="cf-pt" v-model="f.propietario_telefono" class="in" type="tel" placeholder="300 000 0000"></div>
        </div>
        <div class="fld"><label for="cf-obs">Observaciones</label><textarea id="cf-obs" v-model="f.observaciones" class="in" placeholder="Estado del inmueble, disponibilidad, condiciones del propietario" /></div>
        <div class="row wrap">
          <span class="chip pend">Fotos y documentos: pendiente de configuración</span>
        </div>
      </template>

      <div class="mut tiny">
        {{ forOthers && f.asesor_id !== auth.user.value?.id ? 'Se guardan solos: quién la registró, fecha y hora (sin ubicación).' : 'Se guardan solos: tu nombre, ubicación, fecha y hora.' }}
      </div>
      <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
      <button type="submit" class="btn bp send">Enviar</button>
    </form>

    <div v-if="dup" class="dup" role="alert">
      <b>Inmueble ya registrado</b>
      <span>{{ dup }}</span>
    </div>
    <div v-if="sinUbicacion" class="note warn">No se pudo tomar tu ubicación (permiso del navegador). La captación se envió sin ella.</div>

    <ConfirmDialog v-if="confirmOpen" title="¿Enviar la captación?" confirm-label="Sí, enviar" :busy="sending" @confirm="send" @cancel="confirmOpen = false">
      Coordinación la verifica en la otra plataforma y la aprueba o la rechaza. Solo cuenta cuando está aprobada.
    </ConfirmDialog>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.wrap {
  flex-wrap: wrap;
}
.send {
  min-height: 44px;
}
.pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.dup {
  background: var(--cdc-bad-bg);
  border: 1.5px solid var(--cdc-bad);
  border-radius: 14px;
  padding: 14px;
  color: #7a1d14;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}
.dup b {
  font-size: 14px;
}
</style>
