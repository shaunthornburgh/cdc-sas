<script setup lang="ts">
import type { Captacion } from '~/types/captaciones'

/** Captación detail: data, verification, owner location, history; edit / reassign / delete. */
definePageMeta({ module: 'captaciones' })

const route = useRoute()
const auth = useAuth()
const caps = useCaptaciones()
const manager = computed(() => isManager(auth.user.value))

const id = computed(() => String(route.params.id))
const { data: cap, error: loadError } = await useAsyncData(`cap-${id.value}`, () => caps.get(id.value))
if (loadError.value) throw createError({ statusCode: 404, message: 'Captación no encontrada.' })
const c = computed(() => cap.value!)
useHead(() => ({ title: `${c.value.code} · ${c.value.codigo_inmueble} · Casa Dolce Casa` }))

const estado = computed(() => CAPTACION_ESTADO[c.value.estado])
const flash = ref<string | null>(null)
const error = ref<string | null>(null)
const set = (x: Captacion, msg?: string) => {
  cap.value = x
  flash.value = msg ?? null
  error.value = null
}
async function run(fn: () => Promise<Captacion>, msg: string) {
  try {
    set(await fn(), msg)
  } catch (e) {
    error.value = apiErrorMessage(e)
  }
}

// ---- edit ----------------------------------------------------------------------
const editing = ref(false)
const f = reactive<Record<string, string>>({})
const EDIT_KEYS = ['codigo_inmueble', 'direccion', 'tipo_inmueble', 'barrio', 'municipio', 'precio', 'area_m2', 'habitaciones', 'banos', 'parqueadero', 'propietario_nombre', 'propietario_telefono', 'observaciones'] as const
const keyLocked = computed(() => c.value.estado === 'rechazada' && !manager.value)
function startEdit() {
  for (const k of EDIT_KEYS) {
    const v = c.value[k]
    f[k] = k === 'parqueadero' ? (v ? 'si' : v === false ? 'no' : '') : v == null ? '' : String(v)
  }
  f.negocio = c.value.negocio
  f.modo = c.value.modo
  editing.value = true
}
const NUM = new Set(['precio', 'area_m2', 'habitaciones', 'banos'])
async function saveEdit() {
  const body: Record<string, unknown> = {}
  for (const k of [...EDIT_KEYS, 'negocio', 'modo'] as const) {
    if (keyLocked.value && (k === 'codigo_inmueble' || k === 'direccion')) continue
    const raw = (f[k] ?? '').trim()
    let v: unknown = raw || null
    if (NUM.has(k)) v = raw ? Number(raw.replace(/[^\d.]/g, '')) : null
    if (k === 'parqueadero') v = raw === '' ? null : raw === 'si'
    const cur = (c.value as unknown as Record<string, unknown>)[k]
    const same = k === 'codigo_inmueble' ? String(v ?? '').toUpperCase() === cur : NUM.has(k) ? Number(cur ?? NaN) === v || (cur == null && v == null) : (cur ?? null) === v
    if (!same) body[k] = v
  }
  if (!Object.keys(body).length) return (editing.value = false)
  try {
    set(await caps.update(c.value.id, body as never), 'Datos actualizados. Quedó en el historial.')
    editing.value = false
  } catch (e) {
    error.value = apiErrorMessage(e)
  }
}

// ---- verification / owner actions ---------------------------------------------------
const rechazo = reactive({ open: false, motivo: null as null | 'codigo_inexistente' | 'codigo_no_corresponde', obs: '' })
const aprobar = () => run(() => caps.verificar(c.value.id, 'aprobada'), `${c.value.code} aprobada: ya suma en la captación de ${c.value.asesor.full_name}.`)
const rechazar = () =>
  rechazo.motivo
    ? run(() => caps.verificar(c.value.id, 'rechazada', rechazo.motivo, rechazo.obs || null), `${c.value.code} rechazada: se avisó a ${c.value.asesor.full_name}.`)
    : (error.value = 'Elige el motivo del rechazo.')
const publicar = () => run(() => caps.publicar(c.value.id), 'Marcada como publicada.')

const fix = reactive({ open: false, codigo: '', direccion: '' })
function openFix() {
  Object.assign(fix, { open: true, codigo: c.value.codigo_inmueble, direccion: c.value.direccion })
}
const reenviar = () => run(() => caps.reenviar(c.value.id, fix.codigo, fix.direccion), 'Corregida y enviada a verificación otra vez.').then(() => (fix.open = !!error.value))

const { data: captadores } = await useAsyncData('captadores', () => (manager.value ? caps.captadores() : Promise.resolve([])))
const reasignarA = ref(c.value.asesor.id)
const reasignar = () => run(() => caps.reasignar(c.value.id, reasignarA.value), 'Captación reasignada. Quedó en el historial.')

const confirmDelete = ref(false)
const canDelete = computed(() => manager.value || (c.value.asesor.id === auth.user.value?.id && c.value.estado === 'por_verificar'))
async function eliminar() {
  try {
    await caps.remove(c.value.id)
    await navigateTo('/captaciones')
  } catch (e) {
    error.value = apiErrorMessage(e)
    confirmDelete.value = false
  }
}

const datos = computed(() => [
  ['Para', NEGOCIO_LABELS[c.value.negocio]],
  ['Código de la propiedad', c.value.codigo_inmueble],
  ['Dirección', c.value.direccion],
  ['Tipo de inmueble', c.value.tipo_inmueble ? TIPO_INMUEBLE_LABELS[c.value.tipo_inmueble] : '—'],
  ['Barrio · municipio', [c.value.barrio, c.value.municipio].filter(Boolean).join(' · ') || '—'],
  [c.value.negocio === 'venta' ? 'Precio de venta' : 'Canon de arriendo', fmtCOP(c.value.precio)],
  ['Área', c.value.area_m2 != null ? `${Number(c.value.area_m2)} m²` : '—'],
  ['Habitaciones · baños', [c.value.habitaciones, c.value.banos].map((x) => x ?? '—').join(' · ')],
  ['Parqueadero', c.value.parqueadero == null ? '—' : c.value.parqueadero ? 'Sí' : 'No'],
])
const mapa = computed(() => mapaUrl(c.value))
</script>

<template>
  <PageBar :title="`${c.code} · ${c.codigo_inmueble}`" :subtitle="`${NEGOCIO_LABELS[c.negocio]} · ${c.asesor.full_name} · enviada ${fmtCuando(c.enviada_at)} · ${modoTxt(c)}`" back="/captaciones">
    <span class="chip big" :class="estado.cls">{{ estado.t }}</span>
    <span v-if="c.publicada_at" class="chip ok big">✓ Publicada</span>
    <button v-if="c.can_edit && !editing" type="button" class="btn bs" @click="startEdit">Editar</button>
    <button v-if="canDelete" type="button" class="btn br" @click="confirmDelete = true">{{ manager ? 'Eliminar' : 'Retirar' }}</button>
  </PageBar>

  <div class="cnt">
    <div v-if="flash" class="note ok" role="status"><b>✓ {{ flash }}</b></div>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>

    <div class="split">
      <div class="col">
        <div class="card stack">
          <div class="lbl">Datos del inmueble</div>
          <template v-if="!editing">
            <div v-for="[k, v] in datos" :key="k" class="sb kv"><span class="mut">{{ k }}</span><b>{{ v }}</b></div>
          </template>
          <form v-else class="stack" @submit.prevent="saveEdit">
            <div class="g2">
              <div class="fld">
                <label for="e-neg">Para</label>
                <select id="e-neg" v-model="f.negocio" class="in"><option value="venta">Venta</option><option value="arriendo">Arriendo</option></select>
              </div>
              <div class="fld">
                <label for="e-modo">Registro</label>
                <select id="e-modo" v-model="f.modo" class="in"><option value="rapido">Registro rápido</option><option value="completo">Formulario completo</option></select>
              </div>
            </div>
            <div class="g2">
              <div class="fld"><label for="e-cod">Código</label><input id="e-cod" v-model="f.codigo_inmueble" class="in" :disabled="keyLocked"></div>
              <div class="fld"><label for="e-dir">Dirección</label><input id="e-dir" v-model="f.direccion" class="in" :disabled="keyLocked"></div>
            </div>
            <div v-if="keyLocked" class="note">El código y la dirección se cambian con «Corregir y volver a enviar».</div>
            <div class="g3">
              <div class="fld">
                <label for="e-tipo">Tipo de inmueble</label>
                <select id="e-tipo" v-model="f.tipo_inmueble" class="in"><option value="">—</option><option v-for="t in TIPOS_INMUEBLE" :key="t" :value="t">{{ TIPO_INMUEBLE_LABELS[t] }}</option></select>
              </div>
              <div class="fld"><label for="e-bar">Barrio</label><input id="e-bar" v-model="f.barrio" class="in"></div>
              <div class="fld">
                <label for="e-mun">Municipio</label>
                <select id="e-mun" v-model="f.municipio" class="in"><option value="">—</option><option v-for="m in MUNICIPIOS" :key="m">{{ m }}</option></select>
              </div>
            </div>
            <div class="g4">
              <div class="fld"><label for="e-pre">Precio / canon</label><input id="e-pre" v-model="f.precio" class="in" inputmode="numeric"></div>
              <div class="fld"><label for="e-area">Área (m²)</label><input id="e-area" v-model="f.area_m2" class="in" inputmode="decimal"></div>
              <div class="fld"><label for="e-hab">Habitaciones</label><input id="e-hab" v-model="f.habitaciones" class="in" inputmode="numeric"></div>
              <div class="fld"><label for="e-ban">Baños</label><input id="e-ban" v-model="f.banos" class="in" inputmode="numeric"></div>
            </div>
            <div class="g3">
              <div class="fld">
                <label for="e-par">Parqueadero</label>
                <select id="e-par" v-model="f.parqueadero" class="in"><option value="">—</option><option value="si">Sí</option><option value="no">No</option></select>
              </div>
              <div class="fld"><label for="e-pn">Propietario</label><input id="e-pn" v-model="f.propietario_nombre" class="in"></div>
              <div class="fld"><label for="e-pt">Teléfono del propietario</label><input id="e-pt" v-model="f.propietario_telefono" class="in" type="tel"></div>
            </div>
            <div class="fld"><label for="e-obs">Observaciones</label><textarea id="e-obs" v-model="f.observaciones" class="in" /></div>
            <div class="row"><button type="submit" class="btn bp">Guardar cambios</button><button type="button" class="btn bs" @click="editing = false">Cancelar</button></div>
          </form>
        </div>

        <div class="card stack">
          <div class="lbl">Propietario y observaciones</div>
          <div class="sb kv"><span class="mut">Propietario</span><b>{{ c.propietario_nombre ?? '—' }}</b></div>
          <div class="sb kv"><span class="mut">Teléfono</span><b>{{ c.propietario_telefono ?? '—' }}</b></div>
          <div v-if="c.observaciones" class="note">{{ c.observaciones }}</div>
          <span class="chip pend self-start">Fotos y documentos: pendiente de configuración</span>
        </div>
      </div>

      <div class="col">
        <div class="card stack" :class="{ 'warn-card': c.estado === 'por_verificar' }">
          <div class="lbl">Verificación</div>
          <div class="note" :class="c.estado === 'aprobada' ? 'ok' : c.estado === 'rechazada' ? 'bad' : ''">{{ captacionDetalle(c) }}</div>

          <template v-if="manager && c.estado === 'por_verificar'">
            <div class="mut small">Revisa en la otra plataforma que el código exista y que corresponda a esa dirección.</div>
            <div class="row">
              <button type="button" class="btn bp" @click="aprobar">Aprobar</button>
              <button type="button" class="opt" :class="{ on: rechazo.open }" @click="rechazo.open = !rechazo.open">Rechazar</button>
            </div>
            <div v-if="rechazo.open" class="panel">
              <div class="row wrap">
                <button v-for="m in MOTIVOS_RECHAZO" :key="m" type="button" class="opt" :class="{ on: rechazo.motivo === m, bajo: rechazo.motivo === m }" @click="rechazo.motivo = m">{{ MOTIVO_RECHAZO_LABELS[m] }}</button>
              </div>
              <input v-model="rechazo.obs" class="in" placeholder="Observación para el asesor (opcional)" aria-label="Observación">
              <div><button type="button" class="btn br" :disabled="!rechazo.motivo" @click="rechazar">Rechazar captación</button></div>
            </div>
          </template>

          <template v-if="c.estado === 'rechazada' && (manager || c.asesor.id === auth.user.value?.id)">
            <button v-if="!fix.open" type="button" class="btn bp self-start" @click="openFix">Corregir y volver a enviar</button>
            <div v-else class="fix">
              <div class="fld"><label for="fx-c">Código de la propiedad <span class="req">*</span></label><input id="fx-c" v-model="fix.codigo" class="in"></div>
              <div class="fld"><label for="fx-d">Dirección <span class="req">*</span></label><input id="fx-d" v-model="fix.direccion" class="in"></div>
              <div class="g2"><button type="button" class="btn bs" @click="fix.open = false">Cancelar</button><button type="button" class="btn bp" @click="reenviar">Volver a enviar</button></div>
            </div>
          </template>

          <div v-if="c.estado === 'aprobada' && !c.publicada_at" class="sb">
            <span class="chip warn">Aprobada · aún no publicada</span>
            <button type="button" class="btn bs sm" @click="publicar">Marcar publicada</button>
          </div>
        </div>

        <div class="card stack">
          <div class="lbl">Ubicación del asesor</div>
          <b class="small">{{ ubicacionTxt(c) }}</b>
          <a v-if="mapa" :href="mapa" target="_blank" rel="noopener noreferrer" class="small">Ver en el mapa ›</a>
          <div class="mut tiny">Se toma del navegador al enviar, solo si quien envía tiene Captación activa. La distancia a la dirección se calculará cuando se configure la geocodificación.</div>
        </div>

        <div v-if="manager" class="card stack">
          <div class="lbl">Responsable</div>
          <div class="row">
            <select v-model="reasignarA" class="in" aria-label="Responsable">
              <option v-for="p in captadores ?? []" :key="p.id" :value="p.id">{{ p.full_name }}</option>
            </select>
            <button type="button" class="btn bs" :disabled="reasignarA === c.asesor.id" @click="reasignar">Reasignar</button>
          </div>
        </div>

        <div class="card stack">
          <div class="lbl">Registro de cambios</div>
          <div v-for="(e, i) in [...c.eventos].reverse()" :key="i" class="it">
            <div class="sb"><b class="small">{{ e.titulo }}</b><span class="mut tiny">{{ fmtCuando(e.created_at) }}</span></div>
            <span v-if="e.detalle" class="mut small">{{ e.detalle }}</span>
            <span class="mut tiny">{{ e.created_by_name ?? 'Sistema' }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <ConfirmDialog
    v-if="confirmDelete"
    :title="manager ? `¿Eliminar ${c.code}?` : `¿Retirar ${c.code}?`"
    :confirm-label="manager ? 'Sí, eliminar' : 'Sí, retirar'"
    danger
    @confirm="eliminar"
    @cancel="confirmDelete = false"
  >
    {{ manager ? 'Se borra la captación y su registro de cambios. No se puede deshacer.' : 'La captación sale de verificación y se borra. Puedes enviarla de nuevo después.' }}
  </ConfirmDialog>
</template>

<style scoped>
.chip.big {
  font-size: 13px;
  padding: 6px 12px;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.kv {
  font-size: 13px;
  padding: 3px 0;
  flex-wrap: nowrap;
}
.kv b {
  text-align: right;
}
.small {
  font-size: 12.5px;
}
.tiny {
  font-size: 11.5px;
}
.wrap {
  flex-wrap: wrap;
}
.self-start {
  align-self: flex-start;
}
.warn-card {
  border: 2px solid #b7791f;
}
.opt.on.bajo {
  background: var(--cdc-bad);
  border-color: var(--cdc-bad);
}
.fix {
  background: var(--cdc-warn-bg);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
