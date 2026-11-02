<script setup lang="ts">
import type { Cargo, User, UserCambio, UserUpdate } from '~/types/auth'

/**
 * Inline "Editar datos" card: name, cargo and personal data (teléfono, cédula, fecha de ingreso),
 * with the change history. Only Coordinación / Gerencia change these; the person sees them in
 * «Mi perfil». Status has its own buttons in the table.
 */
const props = defineProps<{ user: User }>()
const emit = defineEmits<{ cancel: []; saved: [user: User] }>()

const auth = useAuth()
const users = useUsers()
const isSelf = computed(() => props.user.id === auth.user.value?.id)
const isGerencia = computed(() => auth.user.value?.cargo === 'gerencia')
const cargoOptions = computed(() => CARGOS.filter((c) => c !== 'gerencia' || isGerencia.value))

const form = reactive({
  full_name: props.user.full_name,
  cargo: props.user.cargo as Cargo,
  telefono: props.user.telefono ?? '',
  documento: props.user.documento ?? '',
  fecha_ingreso: props.user.fecha_ingreso ?? '',
})
const historial = ref<UserCambio[]>([])
onMounted(async () => {
  try {
    historial.value = await users.cambios(props.user.id)
  } catch {
    historial.value = []
  }
})

const firstField = ref<HTMLInputElement | null>(null)
onMounted(() => firstField.value?.focus())

const error = ref<string | null>(null)
const saving = ref(false)

async function save() {
  const changes: UserUpdate = {}
  if (form.full_name.trim() !== props.user.full_name) changes.full_name = form.full_name
  if (form.cargo !== props.user.cargo) changes.cargo = form.cargo
  if (form.telefono.trim() !== (props.user.telefono ?? '')) changes.telefono = form.telefono.trim() || null
  if (form.documento.trim() !== (props.user.documento ?? '')) changes.documento = form.documento.trim() || null
  if (form.fecha_ingreso !== (props.user.fecha_ingreso ?? '')) changes.fecha_ingreso = form.fecha_ingreso || null
  if (!Object.keys(changes).length) return emit('cancel')

  error.value = null
  saving.value = true
  try {
    emit('saved', await users.update(props.user.id, changes))
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
      <b class="card-title">Editar datos de {{ user.full_name }}</b>
      <button type="button" class="btn bs sm" @click="emit('cancel')">Cancelar</button>
    </div>
    <div class="g3">
      <div class="fld">
        <label for="ed-name">Nombre completo <span class="req">*</span></label>
        <input id="ed-name" ref="firstField" v-model="form.full_name" class="in" required maxlength="200">
      </div>
      <div class="fld">
        <label for="ed-email">Correo (usuario)</label>
        <input id="ed-email" class="in" :value="user.email" disabled>
      </div>
      <div class="fld">
        <label for="ed-cargo">Cargo</label>
        <select id="ed-cargo" v-model="form.cargo" class="in" :disabled="isSelf">
          <option v-for="c in cargoOptions" :key="c" :value="c">{{ CARGO_LABELS[c] }}</option>
        </select>
      </div>
    </div>
    <div class="g3">
      <div class="fld">
        <label for="ed-tel">Teléfono</label>
        <input id="ed-tel" v-model="form.telefono" class="in" maxlength="40" inputmode="tel" placeholder="300 000 0000">
      </div>
      <div class="fld">
        <label for="ed-doc">Cédula</label>
        <input id="ed-doc" v-model="form.documento" class="in" maxlength="30" inputmode="numeric">
      </div>
      <div class="fld">
        <label for="ed-ing">Fecha de ingreso</label>
        <input id="ed-ing" v-model="form.fecha_ingreso" class="in" type="date" :max="localDate(0)">
      </div>
    </div>
    <div class="note">
      La persona ve estos datos en «Mi perfil» (la cédula, oculta salvo los últimos 4 números) y solo cambia su foto y su contraseña.
      <template v-if="isSelf">No puedes cambiar tu propio cargo. </template>
      El correo es el usuario para entrar y no se cambia aquí. Las actividades y la función se configuran con el botón «Actividades».
    </div>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
    <div><button type="submit" class="btn bp" :disabled="saving">{{ saving ? 'Guardando…' : 'Guardar cambios' }}</button></div>
    <div v-if="historial.length">
      <div class="lbl">Cambios en sus datos</div>
      <div v-for="(c, i) in historial" :key="i" class="hist">
        <span class="mut">{{ fmtCuando(c.created_at) }}</span>
        <span><b>{{ c.campo_txt }}</b>: {{ c.antes ?? '—' }} → {{ c.despues ?? '—' }}<span class="mut"> · {{ c.actor_name ?? 'sistema' }}</span></span>
      </div>
    </div>
  </form>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card-title {
  font-size: 18px;
}
.hist {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 10px;
  font-size: 12.5px;
  padding: 5px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
}
</style>
