<script setup lang="ts">
import type { Cargo, User, UserUpdate } from '~/types/auth'

/** Inline "Editar datos" card: name and cargo. Status has its own buttons in the table. */
const props = defineProps<{ user: User }>()
const emit = defineEmits<{ cancel: []; saved: [user: User] }>()

const auth = useAuth()
const users = useUsers()
const isSelf = computed(() => props.user.id === auth.user.value?.id)
const isGerencia = computed(() => auth.user.value?.cargo === 'gerencia')
const cargoOptions = computed(() => CARGOS.filter((c) => c !== 'gerencia' || isGerencia.value))

const form = reactive({ full_name: props.user.full_name, cargo: props.user.cargo as Cargo })

const firstField = ref<HTMLInputElement | null>(null)
onMounted(() => firstField.value?.focus())

const error = ref<string | null>(null)
const saving = ref(false)

async function save() {
  const changes: UserUpdate = {}
  if (form.full_name.trim() !== props.user.full_name) changes.full_name = form.full_name
  if (form.cargo !== props.user.cargo) changes.cargo = form.cargo
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
    <div class="note">
      <template v-if="isSelf">No puedes cambiar tu propio cargo. </template>
      El correo es el usuario para entrar y no se cambia aquí. Las actividades y la función se configuran con el botón «Actividades».
    </div>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>
    <div><button type="submit" class="btn bp" :disabled="saving">{{ saving ? 'Guardando…' : 'Guardar cambios' }}</button></div>
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
</style>
