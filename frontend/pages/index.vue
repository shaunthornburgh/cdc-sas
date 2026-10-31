<script setup lang="ts">
const auth = useAuth()
const user = computed(() => auth.user.value!)

// Coordinación and Gerencia start on their dashboard (prototype K01).
if (USER_MANAGER_CARGOS.includes(user.value.cargo)) await navigateTo('/coordinacion', { replace: true })
// Asesores start on their own home (prototypes M01 / M02).
else if (hasCommercialActivity(user.value)) await navigateTo('/asesor', { replace: true })
const manager = computed(() => USER_MANAGER_CARGOS.includes(user.value.cargo))

const { data: preopForm } = await useAsyncData('home-preop', () => usePreoperacional().formulario())

const today = new Intl.DateTimeFormat('es-CO', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  timeZone: 'America/Bogota',
}).format(new Date())
</script>

<template>
  <PageBar :title="`Hola, ${firstName(user.full_name)}`" :subtitle="`${CARGO_LABELS[user.cargo]} · ${today}`" />

  <div class="cnt">
    <PreopBanner v-if="preopForm" :activo="preopForm.activo" :realizado-at="preopForm.registro_de_hoy?.realizado_at ?? null" :novedad="preopForm.registro_de_hoy?.tiene_novedad" />
    <div class="g3">
      <div class="card stack">
        <div class="lbl">Cargo</div>
        <div class="big-value">{{ CARGO_LABELS[user.cargo] }}</div>
        <div class="mut small">Define tu perfil general.</div>
      </div>

      <div class="card stack">
        <div class="lbl">{{ user.funcion ? 'Función' : 'Actividades activas' }}</div>
        <div v-if="user.funcion" class="stack">
          <span><span class="chip info">{{ FUNCION_LABELS[user.funcion] }}</span></span>
          <div class="mut small">Función independiente: no se combina con Captación, Ventas o Arriendos.</div>
        </div>
        <template v-else>
          <div class="row wrap-row">
            <span v-for="a in ACTIVIDADES" :key="a" class="act" :class="user.actividades.includes(a) ? 'on1' : 'off1'">
              {{ ACTIVIDAD_LABELS[a] }}
              <span class="sr-only">{{ user.actividades.includes(a) ? '(activa)' : '(inactiva)' }}</span>
            </span>
          </div>
          <div class="mut small">Coordinación activa o quita tus actividades.</div>
        </template>
      </div>

      <div class="card stack">
        <div class="lbl">GPS y control de ruta</div>
        <span>
          <span class="chip" :class="user.gps_checkin_enabled ? 'ok' : 'gray'">
            {{ user.gps_checkin_enabled ? '● GPS activo (tiene Captación)' : '○ Sin GPS' }}
          </span>
        </span>
        <div class="mut small">No se activa a mano: depende de Captación.</div>
      </div>
    </div>

    <NuxtLink v-if="canUseLeads(user)" to="/leads" class="card link-card">
      <div>
        <div class="lbl">Atención y Preventa</div>
        <div class="mut small">Leads nuevos, tus leads en gestión, recordatorios y citas que requieren acción</div>
      </div>
      <span class="go">Abrir ›</span>
    </NuxtLink>

    <NuxtLink v-if="canUseCaptaciones(user)" to="/captaciones" class="card link-card">
      <div>
        <div class="lbl">{{ manager ? 'Verificar captaciones' : 'Captaciones' }}</div>
        <div class="mut small">{{ manager ? 'Aprueba o rechaza las captaciones del equipo' : 'Registra un inmueble y sigue la verificación de tus captaciones' }}</div>
      </div>
      <span class="go">Abrir ›</span>
    </NuxtLink>

    <NuxtLink v-if="manager" to="/usuarios" class="card link-card">
      <div>
        <div class="lbl">Usuarios del equipo</div>
        <div class="mut small">Crear, editar o desactivar personas y configurar sus actividades</div>
      </div>
      <span class="go">Abrir ›</span>
    </NuxtLink>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.big-value {
  font-weight: 800;
  font-size: 20px;
}
.small {
  font-size: 12px;
}
.wrap-row {
  flex-wrap: wrap;
  gap: 6px;
}
.link-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  text-decoration: none;
  color: var(--cdc-text);
}
.link-card:hover {
  border-color: var(--cdc-green);
  color: var(--cdc-text);
}
.go {
  font-weight: 800;
  color: var(--cdc-green);
  white-space: nowrap;
}
</style>
