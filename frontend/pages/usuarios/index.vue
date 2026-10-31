<script setup lang="ts">
import type { Cargo, User } from '~/types/auth'

definePageMeta({ cargos: ['gerencia', 'coordinacion'] })
useHead({ title: 'Usuarios · Casa Dolce Casa' })

const auth = useAuth()
const users = useUsers()
const me = computed(() => auth.user.value!)

const { data: rows, error: loadError, refresh } = await useAsyncData('usuarios', users.list, {
  default: () => [] as User[],
})

// ---- filters (client-side; the team is small) ---------------------------------
const q = ref('')
const cargoFilter = ref<Cargo | ''>('')
const estado = ref<'activos' | 'inactivos' | 'todos'>('activos')

const visible = computed(() => {
  const term = q.value.trim().toLowerCase()
  return rows.value.filter(
    (u) =>
      (!term || u.full_name.toLowerCase().includes(term) || u.email.includes(term)) &&
      (!cargoFilter.value || u.cargo === cargoFilter.value) &&
      (estado.value === 'todos' || u.is_active === (estado.value === 'activos')),
  )
})

// ---- panels: one inline card at a time, as in the prototype --------------------
type Panel = { kind: 'create' } | { kind: 'edit' | 'acts'; user: User }
const panel = ref<Panel | null>(null)
const flash = ref<string | null>(null)
const error = ref<string | null>(null)

function open(p: Panel) {
  panel.value = p
  flash.value = null
  error.value = null
  if (import.meta.client) window.scrollTo({ top: 0, behavior: 'smooth' })
}

/** Mirrors the API: only Gerencia changes Gerencia users. */
const lockedFor = (u: User) => me.value.cargo !== 'gerencia' && u.cargo === 'gerencia'

function upsertRow(user: User) {
  if (rows.value.some((r) => r.id === user.id)) {
    rows.value = rows.value.map((r) => (r.id === user.id ? user : r))
  } else {
    rows.value = [...rows.value, user].sort((a, b) => a.full_name.localeCompare(b.full_name))
  }
  if (user.id === me.value.id) auth.fetchMe()
}

function onCreated(user: User) {
  upsertRow(user)
  panel.value = null
  flash.value = `Usuario creado: ${user.full_name} · ${CARGO_LABELS[user.cargo]} · ${resumen(user)}.`
}

function onEdited(user: User) {
  upsertRow(user)
  panel.value = null
  flash.value = `Datos de ${user.full_name} actualizados.`
}

// ---- activate / deactivate -----------------------------------------------------
const confirmUser = ref<User | null>(null)
const busy = ref(false)

async function setActive(user: User, isActive: boolean) {
  busy.value = true
  error.value = null
  try {
    upsertRow(await users.update(user.id, { is_active: isActive }))
    flash.value = `${user.full_name} ${isActive ? 'reactivado' : 'desactivado'} por ${me.value.full_name}.`
  } catch (e) {
    error.value = `${user.full_name}: ${apiErrorMessage(e)}`
  } finally {
    busy.value = false
    confirmUser.value = null
  }
}

function resumen(u: User): string {
  if (u.funcion) return FUNCION_LABELS[u.funcion]
  return u.actividades.map((a) => ACTIVIDAD_LABELS[a]).join(' + ') || 'Sin actividades'
}
</script>

<template>
  <PageBar title="Usuarios" subtitle="Crear, editar o desactivar personas del equipo" back="/">
    <button type="button" class="btn bp" @click="open({ kind: 'create' })">+ Agregar usuario</button>
  </PageBar>

  <div class="cnt">
    <UserCreateCard v-if="panel?.kind === 'create'" @cancel="panel = null" @created="onCreated" />
    <UserEditCard
      v-else-if="panel?.kind === 'edit'"
      :key="`e-${panel.user.id}`"
      :user="panel.user"
      @cancel="panel = null"
      @saved="onEdited"
    />
    <UserActivitiesCard
      v-else-if="panel?.kind === 'acts'"
      :key="`a-${panel.user.id}`"
      :user="panel.user"
      @close="panel = null"
      @changed="upsertRow"
    />

    <div v-if="flash" class="note ok" role="status"><b>{{ flash }}</b></div>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>

    <div class="card">
      <div class="sb head">
        <span class="lbl">Personas del equipo</span>
        <div class="row filters">
          <input v-model="q" class="in search" type="search" placeholder="Buscar nombre o correo" aria-label="Buscar">
          <select v-model="cargoFilter" class="sel" aria-label="Cargo">
            <option value="">Todos los cargos</option>
            <option v-for="c in CARGOS" :key="c" :value="c">{{ CARGO_LABELS[c] }}</option>
          </select>
          <select v-model="estado" class="sel" aria-label="Estado">
            <option value="activos">Activos</option>
            <option value="inactivos">Inactivos</option>
            <option value="todos">Todos</option>
          </select>
        </div>
      </div>

      <div v-if="loadError" class="note bad sb">
        <b>No se pudo cargar la lista de usuarios.</b>
        <button type="button" class="btn bs sm" @click="refresh()">Reintentar</button>
      </div>

      <div v-else class="wrap">
        <table class="tbl users">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Cargo</th>
              <th>Actividades / funciones</th>
              <th>Estado</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in visible" :key="u.id" :class="{ inactive: !u.is_active }">
              <td>
                <div class="row person">
                  <span class="av">{{ initials(u.full_name) }}</span>
                  <span>
                    <b>{{ u.full_name }}</b>
                    <span v-if="u.id === me.id" class="chip info you">Tú</span>
                    <br><span class="mut email">{{ u.email }}</span>
                  </span>
                </div>
              </td>
              <td>{{ CARGO_LABELS[u.cargo] }}</td>
              <td>
                <div class="row pills">
                  <span v-if="u.funcion" class="chip info">{{ FUNCION_LABELS[u.funcion] }}</span>
                  <template v-else-if="u.actividades.length">
                    <span v-for="a in u.actividades" :key="a" class="act on1">{{ ACTIVIDAD_LABELS[a] }}</span>
                  </template>
                  <span v-else class="mut">Sin actividades</span>
                  <span v-if="u.gps_checkin_enabled" class="chip ok">● GPS</span>
                </div>
              </td>
              <td>
                <span class="chip" :class="u.is_active ? 'ok' : 'gray'">{{ u.is_active ? 'Activo' : 'Inactivo' }}</span>
              </td>
              <td>
                <div v-if="lockedFor(u)" class="mut locked">Solo Gerencia</div>
                <div v-else class="row actions">
                  <button type="button" class="btn bs sm" @click="open({ kind: 'edit', user: u })">Editar datos</button>
                  <button type="button" class="btn bs sm" @click="open({ kind: 'acts', user: u })">Actividades</button>
                  <button
                    v-if="u.is_active"
                    type="button"
                    class="btn br sm"
                    :disabled="u.id === me.id"
                    :title="u.id === me.id ? 'No puedes desactivar tu propio usuario' : undefined"
                    @click="confirmUser = u"
                  >
                    Desactivar
                  </button>
                  <button v-else type="button" class="btn bs sm" :disabled="busy" @click="setActive(u, true)">
                    Reactivar
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="!visible.length">
              <td colspan="5" class="mut empty">No hay personas que coincidan con los filtros.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="note foot">
        Coordinación y Gerencia administran los usuarios. Solo Gerencia modifica a otros usuarios de Gerencia y nadie
        puede desactivarse a sí mismo. Cada cambio de actividades queda con fecha, hora y quién lo hizo.
      </div>
    </div>
  </div>

  <ConfirmDialog
    v-if="confirmUser"
    :title="`¿Desactivar a ${confirmUser.full_name}?`"
    confirm-label="Sí, desactivar"
    danger
    :busy="busy"
    @confirm="setActive(confirmUser, false)"
    @cancel="confirmUser = null"
  >
    No podrá entrar al sistema y su sesión se cierra. Su historial se conserva. Puedes reactivarlo cuando quieras.
  </ConfirmDialog>
</template>

<style scoped>
.head {
  margin-bottom: 6px;
}
.filters {
  flex-wrap: wrap;
  gap: 8px;
}
.search {
  min-height: 40px;
  width: 240px;
  font-size: 13.5px;
}
.users {
  min-width: 940px;
}
.person {
  gap: 8px;
  align-items: center;
}
.email {
  font-size: 11px;
}
.you {
  margin-left: 6px;
  padding: 1px 8px;
  font-size: 10.5px;
}
.pills {
  flex-wrap: wrap;
  gap: 6px;
}
.actions {
  gap: 6px;
  flex-wrap: nowrap;
}
.locked {
  font-size: 12px;
}
tr.inactive td:not(:nth-child(4)):not(:nth-child(5)) {
  opacity: 0.6;
}
.empty {
  text-align: center;
  padding: 28px 10px;
}
.foot {
  margin-top: 10px;
}
@media (max-width: 760px) {
  .search {
    width: 100%;
  }
  .filters {
    width: 100%;
  }
}
</style>
