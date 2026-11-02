<script setup lang="ts">
const auth = useAuth()
const marca = useMarca()
const route = useRoute()

const user = computed(() => auth.user.value)
const manager = computed(() => !!user.value && USER_MANAGER_CARGOS.includes(user.value.cargo))
const hasLeads = computed(() => canUseLeads(user.value))
const hasCaptaciones = computed(() => canUseCaptaciones(user.value))
const hasPedidos = computed(() => canUsePedidos(user.value))
const hasInmuebles = computed(() => canUseInmuebles(user.value))
const asesor = computed(() => !manager.value && hasCommercialActivity(user.value))
const conResultado = computed(() => !!perfilRendimiento(user.value))
const gerencia = computed(() => user.value?.cargo === 'gerencia')
const auxiliar = computed(() => user.value?.cargo === 'auxiliar_administrativa')
const gps = computed(() => perfilGps(user.value))
const home = computed(() => (manager.value ? '/coordinacion' : asesor.value ? '/asesor' : '/'))
const { conteo, refrescar } = useAvisosConteo()
const { foto, cargar: cargarFoto } = useMiFoto()
// Someone else signs in on the same tab: forget the previous photo
watch(
  () => user.value?.id,
  (id) => {
    foto.value = undefined
    if (id && import.meta.client) cargarFoto()
  },
)
const nAvisos = computed(() => conteo.value?.por_atender ?? 0)
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  cargarFoto()
  refrescar()
  timer = setInterval(refrescar, 60_000)
})
onBeforeUnmount(() => clearInterval(timer))
watch(() => route.path, () => refrescar())
const isOn = (to: string) => (to === '/' ? route.path === '/' : route.path.startsWith(to))
</script>

<template>
  <div class="app">
    <!-- Desktop: dark green sidebar -->
    <nav class="side" aria-label="Menú">
      <div class="brand">
        <BrandLogo :size="38" />
        <div>
          <div class="wm">{{ marca.nombre }}</div>
          <div v-if="marca.lema" class="lema">{{ marca.lema }}</div>
        </div>
      </div>

      <NuxtLink v-if="user" to="/perfil" class="role" aria-label="Mi perfil">
        <img v-if="foto" :src="foto" alt="" class="rav rimg">
        <span v-else class="rav">{{ initials(user.full_name) }}</span>
        <span class="rname">{{ user.full_name }} · <b>{{ CARGO_LABELS[user.cargo] }}</b></span>
        <span class="rcam" aria-hidden="true">›</span>
      </NuxtLink>

      <NuxtLink class="nav" :class="{ on: isOn(home) }" :to="home">Inicio</NuxtLink>
      <NuxtLink class="nav" :class="{ on: isOn('/avisos') }" to="/avisos">
        {{ gerencia ? 'Avisos y agenda' : 'Notificaciones' }}
        <span v-if="nAvisos" class="badge" :aria-label="`${nAvisos} por atender`">{{ nAvisos }}</span>
      </NuxtLink>
      <NuxtLink v-if="!gerencia" class="nav" :class="{ on: isOn('/agenda') }" to="/agenda">
        {{ user?.cargo === 'coordinacion' ? 'Agenda' : 'Mi agenda' }}
        <span v-if="conteo?.agenda_hoy" class="badge gray" :aria-label="`${conteo.agenda_hoy} pendientes hoy`">{{ conteo.agenda_hoy }}</span>
      </NuxtLink>
      <NuxtLink v-if="conResultado" class="nav" :class="{ on: isOn('/resultados') && route.path === '/resultados' }" to="/resultados">Mis resultados</NuxtLink>
      <NuxtLink v-if="gerencia" class="nav" :class="{ on: isOn('/rendimiento-empresa') }" to="/rendimiento-empresa">Rendimiento de la empresa</NuxtLink>
      <NuxtLink v-if="!gerencia" class="nav" :class="{ on: isOn('/mis-pagos') }" to="/mis-pagos">Mis pagos y bonos</NuxtLink>
      <div class="sect">MI DÍA</div>
      <NuxtLink v-if="asesor" class="nav" :class="{ on: isOn('/mis-citas') }" to="/mis-citas">Mis citas</NuxtLink>
      <NuxtLink class="nav" :class="{ on: route.path === '/preoperacional' }" to="/preoperacional">Mi preoperacional</NuxtLink>
      <NuxtLink v-if="gps && !manager" class="nav" :class="{ on: isOn('/movimientos') }" to="/movimientos">{{ gps === 'atencion' ? 'Trabajo en campo y GPS' : 'Mis alertas de GPS' }}</NuxtLink>
      <template v-if="hasLeads">
        <div class="sect">LEADS Y CITAS</div>
        <NuxtLink class="nav" :class="{ on: isOn('/leads') }" to="/leads">Atención y Preventa</NuxtLink>
        <NuxtLink class="nav" :class="{ on: isOn('/citas') }" to="/citas">Control de citas</NuxtLink>
      </template>
      <template v-if="hasPedidos">
        <div class="sect">COMERCIAL</div>
        <NuxtLink class="nav" :class="{ on: isOn('/pedidos') }" to="/pedidos">Pedidos</NuxtLink>
        <NuxtLink class="nav" :class="{ on: route.path === '/inmuebles' }" to="/inmuebles">Inmuebles</NuxtLink>
        <NuxtLink class="nav" :class="{ on: isOn('/inmuebles/administracion') }" to="/inmuebles/administracion">Administración de inmuebles</NuxtLink>
        <NuxtLink v-if="manager" class="nav" :class="{ on: isOn('/plataformas') }" to="/plataformas">{{ gerencia ? 'Plataformas tradicionales' : 'Actualización de plataformas' }}</NuxtLink>
        <NuxtLink v-if="gerencia" class="nav" :class="{ on: isOn('/polizas') }" to="/polizas">Pólizas</NuxtLink>
      </template>
      <template v-if="auxiliar">
        <div class="sect">NEGOCIOS</div>
        <NuxtLink class="nav" :class="{ on: isOn('/polizas') }" to="/polizas">Pólizas</NuxtLink>
      </template>
      <template v-if="!hasPedidos && hasInmuebles">
        <div class="sect">INMUEBLES</div>
        <NuxtLink class="nav" :class="{ on: route.path === '/inmuebles' }" to="/inmuebles">Inmuebles</NuxtLink>
        <NuxtLink class="nav" :class="{ on: isOn('/inmuebles/administracion') }" to="/inmuebles/administracion">Administración de inmuebles</NuxtLink>
      </template>
      <template v-if="hasCaptaciones">
        <div class="sect">CAPTACIONES</div>
        <NuxtLink class="nav" :class="{ on: isOn('/captaciones') }" to="/captaciones">
          {{ manager ? 'Verificar captaciones' : 'Nueva captación' }}
        </NuxtLink>
      </template>
      <template v-if="manager">
        <div class="sect">EQUIPO</div>
        <NuxtLink class="nav" :class="{ on: isOn('/usuarios') }" to="/usuarios">Usuarios</NuxtLink>
        <NuxtLink class="nav" :class="{ on: isOn('/preoperacionales') }" to="/preoperacionales">Preoperacionales</NuxtLink>
        <NuxtLink class="nav" :class="{ on: isOn('/novedades') }" to="/novedades">Ausencias y permisos</NuxtLink>
        <NuxtLink class="nav" :class="{ on: isOn('/movimientos') }" to="/movimientos">Movimientos y GPS</NuxtLink>
        <NuxtLink class="nav" :class="{ on: isOn('/equipo') || (isOn('/resultados/') && route.path !== '/resultados') }" to="/equipo">{{ gerencia ? 'Rendimiento por empleado' : 'Mi equipo' }}</NuxtLink>
        <NuxtLink class="nav" :class="{ on: route.path === '/rendimiento' }" to="/rendimiento">{{ gerencia ? 'Indicadores, metas y pesos' : 'Rendimiento e indicadores' }}</NuxtLink>
      </template>
      <template v-if="gerencia || auxiliar">
        <div class="sect">PAGOS AL PERSONAL</div>
        <NuxtLink class="nav" :class="{ on: isOn('/salarios') }" to="/salarios">Salarios del mes</NuxtLink>
        <NuxtLink class="nav" :class="{ on: isOn('/compensacion') }" to="/compensacion">Comisiones, bonos y pagos</NuxtLink>
      </template>
      <template v-if="auxiliar">
        <div class="sect">PERSONAL</div>
        <NuxtLink class="nav" :class="{ on: isOn('/equipo') || isOn('/resultados/') }" to="/equipo">Rendimiento y calificaciones</NuxtLink>
        <NuxtLink class="nav" :class="{ on: isOn('/novedades') }" to="/novedades">Ausencias y permisos</NuxtLink>
        <NuxtLink class="nav" :class="{ on: isOn('/plataformas') }" to="/plataformas">Actualización de plataformas</NuxtLink>
      </template>

      <template v-if="manager">
        <div class="sect">CONTROL Y AJUSTES</div>
        <NuxtLink class="nav" :class="{ on: isOn('/trazabilidad') }" to="/trazabilidad">Registro de cambios</NuxtLink>
        <NuxtLink v-if="gerencia" class="nav" :class="{ on: isOn('/integraciones') }" to="/integraciones">Integraciones</NuxtLink>
        <NuxtLink class="nav" :class="{ on: isOn('/configuracion') }" to="/configuracion">Configuración</NuxtLink>
      </template>

      <div class="side-foot">
        <NuxtLink class="nav" :class="{ on: isOn('/perfil') }" to="/perfil">Mi perfil</NuxtLink>
        <button type="button" class="nav nav-btn" @click="auth.logout()">Cerrar sesión</button>
      </div>
    </nav>

    <!-- Mobile: white top bar -->
    <header class="top">
      <div class="brand">
        <BrandLogo :size="36" />
        <div>
          <div class="wm">{{ marca.nombre }}</div>
          <div v-if="marca.lema" class="lema">{{ marca.lema }}</div>
        </div>
      </div>
      <div class="row top-r">
        <NuxtLink to="/avisos" class="bell" :aria-label="nAvisos ? `Avisos: ${nAvisos} por atender` : 'Avisos'">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></svg>
          <span v-if="nAvisos" class="badge bdot">{{ nAvisos > 9 ? '9+' : nAvisos }}</span>
        </NuxtLink>
        <NuxtLink v-if="user" to="/perfil" class="av av-top" :title="`Mi perfil · ${user.full_name}`" aria-label="Mi perfil">
          <img v-if="foto" :src="foto" alt="" class="topimg">
          <template v-else>{{ initials(user.full_name) }}</template>
        </NuxtLink>
      </div>
    </header>

    <div class="main">
      <slot />
    </div>

    <!-- Mobile: bottom navigation -->
    <nav class="bn" aria-label="Menú principal">
      <NuxtLink :class="{ on: isOn(home) }" :to="home">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 11l9-8 9 8" /><path d="M5 10v10h14V10" /></svg>
        Inicio
      </NuxtLink>
      <NuxtLink v-if="asesor" :class="{ on: isOn('/mis-citas') }" to="/mis-citas">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18" /><path d="M8 3v4" /><path d="M16 3v4" /></svg>
        Citas
      </NuxtLink>
      <NuxtLink v-if="hasLeads" :class="{ on: isOn('/leads') }" to="/leads">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
        Leads
      </NuxtLink>
      <NuxtLink v-if="hasLeads" :class="{ on: isOn('/citas') }" to="/citas">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18" /><path d="M8 3v4" /><path d="M16 3v4" /></svg>
        Citas
      </NuxtLink>
      <NuxtLink v-if="hasCaptaciones" :class="{ on: isOn('/captaciones') }" to="/captaciones">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z" /><path d="M12 7v6" /><path d="M9 10h6" /></svg>
        Captar
      </NuxtLink>
      <NuxtLink v-if="manager || auxiliar" :class="{ on: isOn('/equipo') }" to="/equipo">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20V10" /><path d="M10 20V4" /><path d="M16 20v-7" /><path d="M22 20H2" /></svg>
        Equipo
      </NuxtLink>
      <NuxtLink v-if="manager" :class="{ on: isOn('/usuarios') }" to="/usuarios">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="9" cy="8" r="4" /><path d="M2 21a7 7 0 0 1 14 0" /><path d="M16 4a4 4 0 0 1 0 8" /><path d="M22 21a7 7 0 0 0-4-6.3" /></svg>
        Usuarios
      </NuxtLink>
      <NuxtLink v-if="hasPedidos && !manager" :class="{ on: isOn('/pedidos') }" to="/pedidos">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3h9l3 3v15H6z" /><path d="M9 11h6" /><path d="M9 15h6" /></svg>
        Pedidos
      </NuxtLink>
      <NuxtLink v-if="gps && !manager" :class="{ on: isOn('/movimientos') }" to="/movimientos">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z" /><circle cx="12" cy="9.5" r="2.5" /></svg>
        {{ gps === 'atencion' ? 'Campo' : 'GPS' }}
      </NuxtLink>
      <NuxtLink v-if="!manager" :class="{ on: route.path === '/preoperacional' }" to="/preoperacional">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></svg>
        Preop.
      </NuxtLink>
      <NuxtLink v-if="auxiliar" :class="{ on: isOn('/novedades') }" to="/novedades">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18" /><path d="M9 14l6 4" /><path d="M15 14l-6 4" /></svg>
        Ausencias
      </NuxtLink>
      <NuxtLink v-if="auxiliar" :class="{ on: isOn('/compensacion') || isOn('/salarios') }" to="/compensacion">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="6" width="20" height="12" rx="2" /><circle cx="12" cy="12" r="2.5" /></svg>
        Pagos
      </NuxtLink>
      <NuxtLink v-if="conResultado && !manager" :class="{ on: route.path === '/resultados' }" to="/resultados">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
        Puntaje
      </NuxtLink>
      <button type="button" @click="auth.logout()">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="M16 17l5-5-5-5" /><path d="M21 12H9" /></svg>
        Salir
      </button>
    </nav>
  </div>
</template>

<style scoped>
.app {
  display: flex;
  min-height: 100vh;
}

/* ---- Sidebar ---- */
.side {
  flex: 0 0 var(--side-width);
  max-width: var(--side-width);
  background: var(--cdc-green-dark);
  color: #e3efe6;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.side .brand {
  padding: 4px 6px 14px;
}
.wm {
  font-family: var(--font-display);
  font-size: 22px;
  letter-spacing: 0.04em;
  line-height: 1;
  color: #fff;
}
.lema {
  font-size: 9.5px;
  color: var(--cdc-side-lema);
  font-weight: 600;
}
.role {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 6px 10px;
  padding: 8px 10px;
  border-radius: 10px;
  background: var(--cdc-green-side-2);
  font-size: 12px;
  color: var(--cdc-avatar-bg);
}
.role {
  text-decoration: none;
}
.role:hover {
  background: var(--cdc-green-side-hover);
}
.rname {
  flex: 1;
  min-width: 0;
}
.rcam {
  font-weight: 800;
  color: var(--cdc-side-muted);
}
.rimg {
  object-fit: cover;
  padding: 0;
}
.topimg {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
}
.av-top {
  text-decoration: none;
  overflow: hidden;
}
.rav {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--cdc-avatar-bg);
  color: var(--cdc-green-dark);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 13px;
  flex: none;
  border: 2px solid var(--cdc-green-lime);
}
.nav {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 10px;
  color: var(--cdc-side-text);
  text-decoration: none;
  font-weight: 600;
  font-size: 13.5px;
  min-height: 40px;
}
.nav.on,
.nav:hover {
  background: var(--cdc-green-side-hover);
  color: #fff;
}
.nav-btn {
  width: 100%;
  background: none;
  border: 0;
  font-family: inherit;
  cursor: pointer;
  text-align: left;
}
.sect {
  font-size: 10.5px;
  letter-spacing: 0.09em;
  color: var(--cdc-side-muted);
  font-weight: 700;
  padding: 14px 12px 4px;
}
.side-foot {
  margin-top: auto;
  padding-top: 12px;
}

.badge {
  margin-left: auto;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: #a3271b;
  color: #fff;
  font-size: 11px;
  font-weight: 800;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.badge.gray {
  background: var(--cdc-side-muted);
  color: var(--cdc-green-dark);
}
.top-r {
  gap: 10px;
  align-items: center;
}
.bell {
  position: relative;
  display: inline-flex;
  color: var(--cdc-text);
  padding: 6px;
}
.bdot {
  position: absolute;
  top: -2px;
  right: -4px;
  margin: 0;
}

/* ---- Main ---- */
.main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* ---- Mobile-only chrome ---- */
.top,
.bn {
  display: none;
}

@media (max-width: 760px) {
  .app {
    flex-direction: column;
  }
  .side {
    display: none;
  }
  .top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 14px;
    background: #fff;
    border-bottom: 1px solid var(--cdc-border);
    min-height: 64px;
    position: sticky;
    top: 0;
    z-index: 15;
  }
  .top .wm {
    font-size: 21px;
    color: var(--cdc-green-dark);
  }
  .top .lema {
    font-size: 9px;
    color: var(--cdc-muted);
  }
  .av-top {
    width: 36px;
    height: 36px;
    font-size: 13px;
  }
  .main {
    padding-bottom: var(--bottom-nav-height);
  }
  .bn {
    display: flex;
    align-items: center;
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    height: var(--bottom-nav-height);
    padding-bottom: env(safe-area-inset-bottom);
    background: #fff;
    border-top: 1px solid var(--cdc-border);
    z-index: 15;
  }
  .bn > a,
  .bn > button {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    min-height: 60px;
    font-family: inherit;
    font-size: 10.5px;
    font-weight: 700;
    color: var(--cdc-muted);
    text-decoration: none;
    background: none;
    border: 0;
    cursor: pointer;
  }
  .bn > a.on {
    color: var(--cdc-green);
  }
}
</style>
