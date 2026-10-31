<script setup lang="ts">
import type { ActividadComercial, Cargo, FuncionIndependiente, User } from '~/types/auth'

/** Inline "Agregar usuario" card (prototype K10). */
const emit = defineEmits<{ cancel: []; created: [user: User] }>()

const auth = useAuth()
const users = useUsers()
const isGerencia = computed(() => auth.user.value?.cargo === 'gerencia')
const cargoOptions = computed(() => CARGOS.filter((c) => c !== 'gerencia' || isGerencia.value))

const form = reactive({
  full_name: '',
  email: '',
  password: '',
  cargo: 'asesor' as Cargo,
  funcion: null as FuncionIndependiente | null,
  is_active: true,
})
const acts = reactive<Record<ActividadComercial, boolean>>({ captacion: false, ventas: false, arriendos: false })
const actividades = computed(() => ACTIVIDADES.filter((a) => acts[a]))
const gps = computed(() => acts.captacion)
const lockedFuncion = computed(() => form.cargo === 'atencion_cliente')

// Atención al Cliente always carries its function; a function excludes activities.
watch(
  () => form.cargo,
  (cargo) => {
    if (cargo === 'atencion_cliente') form.funcion = 'atencion_cliente'
    else if (form.funcion === 'atencion_cliente') form.funcion = null
  },
)
watch(
  () => form.funcion,
  (f) => {
    if (f) for (const a of ACTIVIDADES) acts[a] = false
  },
)

const firstField = ref<HTMLInputElement | null>(null)
onMounted(() => firstField.value?.focus())

const error = ref<string | null>(null)
const saving = ref(false)

async function save() {
  error.value = null
  saving.value = true
  try {
    emit('created', await users.create({ ...form, actividades: actividades.value }))
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
      <b class="card-title">Agregar usuario</b>
      <button type="button" class="btn bs sm" @click="emit('cancel')">Cancelar</button>
    </div>

    <div class="lbl">Datos personales</div>
    <div class="g3">
      <div class="fld">
        <label for="nu-name">Nombre completo <span class="req">*</span></label>
        <input id="nu-name" ref="firstField" v-model="form.full_name" class="in" placeholder="Nombres y apellidos" required maxlength="200">
      </div>
      <div class="fld">
        <label for="nu-email">Correo <span class="req">*</span></label>
        <input id="nu-email" v-model.trim="form.email" class="in" type="email" placeholder="nombre@correo.com" required autocomplete="off">
      </div>
      <div class="fld">
        <label for="nu-pass">Contraseña inicial <span class="req">*</span></label>
        <input id="nu-pass" v-model="form.password" class="in" type="password" placeholder="Mínimo 8 caracteres" required minlength="8" autocomplete="new-password">
      </div>
    </div>

    <div class="lbl">Cargo</div>
    <div class="row opts" role="radiogroup" aria-label="Cargo">
      <button
        v-for="c in cargoOptions"
        :key="c"
        type="button"
        class="opt"
        :class="{ on: form.cargo === c }"
        role="radio"
        :aria-checked="form.cargo === c"
        @click="form.cargo = c"
      >
        {{ CARGO_LABELS[c] }}
      </button>
    </div>

    <div class="lbl">Actividades comerciales</div>
    <div class="row opts">
      <div v-for="a in ACTIVIDADES" :key="a" class="sb tile">
        <b>{{ ACTIVIDAD_LABELS[a] }}</b>
        <AppSwitch v-model="acts[a]" :label="ACTIVIDAD_LABELS[a]" :disabled="!!form.funcion" />
      </div>
      <span class="chip gps" :class="gps ? 'ok' : 'gray'">{{ gps ? '● GPS activo (tiene Captación)' : '○ Sin GPS' }}</span>
    </div>

    <div class="lbl">Función independiente</div>
    <div class="row opts" role="radiogroup" aria-label="Función independiente">
      <button
        type="button"
        class="opt"
        :class="{ on: !form.funcion }"
        role="radio"
        :aria-checked="!form.funcion"
        :disabled="lockedFuncion"
        @click="form.funcion = null"
      >
        Ninguna
      </button>
      <button
        v-for="f in FUNCIONES"
        :key="f"
        type="button"
        class="opt"
        :class="{ on: form.funcion === f }"
        role="radio"
        :aria-checked="form.funcion === f"
        :disabled="lockedFuncion"
        @click="form.funcion = f"
      >
        {{ FUNCION_LABELS[f] }}
      </button>
    </div>
    <div v-if="form.funcion" class="note">
      {{ FUNCION_LABELS[form.funcion] }} es una función independiente: no se combina con Captación, Ventas o Arriendos.
    </div>

    <div class="lbl">Acceso</div>
    <div class="note">El usuario para entrar es el correo, con la contraseña inicial que definas aquí.</div>

    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
    <div><button type="submit" class="btn bp" :disabled="saving">{{ saving ? 'Guardando…' : 'Guardar usuario' }}</button></div>
  </form>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.card-title {
  font-size: 18px;
}
.opts {
  flex-wrap: wrap;
}
.tile {
  padding: 10px 12px;
  border: 1px solid var(--cdc-border);
  border-radius: 12px;
  min-width: 220px;
  flex-wrap: nowrap;
}
.gps {
  padding: 6px 12px;
}
@media (max-width: 760px) {
  .tile {
    min-width: 0;
    width: 100%;
  }
}
</style>
