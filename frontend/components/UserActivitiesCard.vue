<script setup lang="ts">
import type { ActividadComercial, ActividadEvento, FuncionIndependiente, User } from '~/types/auth'

/** "Configurando a …" card (prototype K02): activity switches, independent function, GPS, history. */
const props = defineProps<{ user: User }>()
const emit = defineEmits<{ close: []; changed: [user: User] }>()

const users = useUsers()

const DESCRIPTIONS: Record<ActividadComercial, string> = {
  captacion: 'Consigue inmuebles nuevos. Activa el GPS y el control de ruta.',
  ventas: 'Atiende clientes y negocios de venta.',
  arriendos: 'Atiende clientes y negocios de arriendo.',
}

// Working copy; `current` is the last saved state from the API.
const current = ref<User>(props.user)
const acts = reactive<Record<ActividadComercial, boolean>>({ captacion: false, ventas: false, arriendos: false })
const funcion = ref<FuncionIndependiente | null>(null)

function reset() {
  for (const a of ACTIVIDADES) acts[a] = current.value.actividades.includes(a)
  funcion.value = current.value.funcion
}
reset()

const lockedFuncion = computed(() => current.value.cargo === 'atencion_cliente')
const selected = computed(() => ACTIVIDADES.filter((a) => acts[a]))
const gps = computed(() => acts.captacion)
const resumen = computed(() =>
  funcion.value
    ? FUNCION_LABELS[funcion.value]
    : selected.value.map((a) => ACTIVIDAD_LABELS[a]).join(' + ') || 'Sin actividades',
)
const dirty = computed(
  () =>
    funcion.value !== current.value.funcion ||
    selected.value.join() !== current.value.actividades.join(),
)

watch(funcion, (f) => {
  if (f) for (const a of ACTIVIDADES) acts[a] = false
})

const error = ref<string | null>(null)
const message = ref<string | null>(null)
const saving = ref(false)

/** Apply in an order the API accepts: clear one side before setting the other. */
async function save() {
  error.value = null
  message.value = null
  saving.value = true
  const apply = (u: User) => {
    current.value = u
    emit('changed', u)
  }
  try {
    const u = current.value
    if (funcion.value) {
      if (u.actividades.length) apply(await users.setActividades(u.id, []))
      if (current.value.funcion !== funcion.value) apply(await users.setFuncion(u.id, funcion.value))
    } else {
      if (u.funcion) apply(await users.setFuncion(u.id, null))
      if (selected.value.join() !== current.value.actividades.join())
        apply(await users.setActividades(u.id, selected.value))
    }
    message.value = `Cambios guardados para ${current.value.full_name}. Quedaron en el historial.`
    await loadHistory()
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    saving.value = false
    reset()
  }
}

const history = ref<ActividadEvento[] | null>(null)
async function loadHistory() {
  try {
    history.value = await users.history(props.user.id)
  } catch {
    history.value = []
  }
}
onMounted(loadHistory)

const dateFmt = new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium', timeStyle: 'short' })
</script>

<template>
  <div class="card focus stack">
    <div class="sb">
      <div>
        <div class="lbl">Configurando a</div>
        <div class="who">{{ current.full_name }}</div>
        <div class="mut small">Cargo: {{ CARGO_LABELS[current.cargo] }} · el cargo no cambia aquí</div>
      </div>
      <div class="row">
        <span class="act on1 resumen">{{ resumen }}</span>
        <button type="button" class="btn bs sm" @click="emit('close')">Cerrar</button>
      </div>
    </div>

    <div v-for="a in ACTIVIDADES" :key="a" class="sb tile">
      <div>
        <b class="tile-name">{{ ACTIVIDAD_LABELS[a] }}</b>
        <div class="mut small">{{ DESCRIPTIONS[a] }}</div>
      </div>
      <AppSwitch v-model="acts[a]" :label="ACTIVIDAD_LABELS[a]" :disabled="!!funcion || saving" />
    </div>

    <div>
      <div class="lbl fn-lbl">Función independiente</div>
      <div class="row opts" role="radiogroup" aria-label="Función independiente">
        <button
          type="button"
          class="opt"
          :class="{ on: !funcion }"
          role="radio"
          :aria-checked="!funcion"
          :disabled="lockedFuncion || saving"
          @click="funcion = null"
        >
          Ninguna
        </button>
        <button
          v-for="f in FUNCIONES"
          :key="f"
          type="button"
          class="opt"
          :class="{ on: funcion === f }"
          role="radio"
          :aria-checked="funcion === f"
          :disabled="lockedFuncion || saving"
          @click="funcion = f"
        >
          {{ FUNCION_LABELS[f] }}
        </button>
      </div>
    </div>
    <div v-if="lockedFuncion" class="note">El cargo Atención al Cliente siempre tiene la función Atención al Cliente y no recibe actividades comerciales.</div>
    <div v-else-if="funcion" class="note">
      {{ FUNCION_LABELS[funcion] }} es una función independiente: no se combina con Captación, Ventas o Arriendos. Al guardar se quitan sus actividades comerciales.
    </div>

    <div class="sb tile gps-row">
      <div>
        <b class="tile-name">GPS y control de ruta</b>
        <div class="mut small">No se activa a mano: depende de Captación</div>
      </div>
      <span class="chip gps-chip" :class="gps ? 'ok' : 'gray'">{{ gps ? '● GPS activo (tiene Captación)' : '○ Sin GPS' }}</span>
    </div>

    <div v-if="dirty && !funcion && !selected.length" class="note warn">
      {{ current.full_name }} quedaría sin actividades ni función. Puedes guardar, pero no tendrá módulos de trabajo.
    </div>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>

    <div class="row">
      <button type="button" class="btn bp" :disabled="!dirty || saving" @click="save">
        {{ saving ? 'Guardando…' : 'Guardar cambios' }}
      </button>
      <button type="button" class="btn bs" :disabled="!dirty || saving" @click="reset">Deshacer</button>
    </div>
    <div v-if="message" class="note ok" role="status"><b>{{ message }}</b></div>

    <div>
      <div class="lbl">Historial de actividades · quién y cuándo</div>
      <p v-if="history === null" class="mut small">Cargando…</p>
      <p v-else-if="!history.length" class="mut small">Sin cambios registrados.</p>
      <div v-for="(h, i) in history ?? []" :key="i" class="sb log">
        <span>
          <span class="chip" :class="h.activada ? 'ok' : 'bad'">{{ h.activada ? 'Activó' : 'Quitó' }}</span>
          <b>{{ ACTIVIDAD_LABELS[h.actividad] }}</b>
        </span>
        <span class="mut small">{{ dateFmt.format(new Date(h.created_at)) }} · {{ h.changed_by_name ?? 'Sistema' }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.who {
  font-weight: 800;
  font-size: 20px;
}
.small {
  font-size: 12px;
}
.resumen {
  font-size: 12px;
}
.tile {
  padding: 12px;
  border: 1px solid var(--cdc-border);
  border-radius: 12px;
  flex-wrap: nowrap;
}
.tile-name {
  font-size: 15px;
}
.gps-row {
  border: 0;
  background: var(--cdc-bg);
}
.gps-chip {
  font-size: 13px;
  padding: 6px 12px;
}
.fn-lbl {
  margin-bottom: 8px;
}
.opts {
  flex-wrap: wrap;
}
.log {
  font-size: 12.5px;
  padding: 6px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.log b {
  margin-left: 4px;
}
</style>
