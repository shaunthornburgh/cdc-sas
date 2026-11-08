<script setup lang="ts">
import type { AsesorInicio } from '~/types/asesor'

/** Inicio del asesor (prototypes M01-Asesor1 / M02-Asesor2). Cards follow the active activities. */
definePageMeta({ module: 'asesor' })

const route = useRoute()
const auth = useAuth()
const asesorApi = useAsesor()
const me = computed(() => auth.user.value!)
const viewing = computed(() => (isManager(me.value) && typeof route.query.asesor === 'string' ? route.query.asesor : null))
if (isManager(me.value) && !viewing.value && !hasCommercialActivity(me.value)) {
  await navigateTo('/coordinacion', { replace: true })
}

const { data, error, refresh } = await useAsyncData(
  () => `asesor-${viewing.value ?? 'me'}`,
  () => asesorApi.inicio(viewing.value),
  { watch: [viewing] },
)
const d = computed(() => data.value as AsesorInicio)
useHead(() => ({ title: `Inicio · ${data.value?.asesor.full_name ?? ''} · Casa Dolce Casa` }))

const hoy = new Intl.DateTimeFormat('es-CO', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'America/Bogota' }).format(new Date())
const mes = new Intl.DateTimeFormat('es-CO', { month: 'long', timeZone: 'America/Bogota' }).format(new Date())
const cargoTxt = computed(() => (d.value.asesor.cargo === 'asesor' ? 'Asesor comercial' : CARGO_LABELS[d.value.asesor.cargo]))
const soloLectura = computed(() => !!viewing.value)

type Tab = 'captacion' | 'ventas' | 'arriendos'
const TAB_LABELS: Record<Tab, string> = { captacion: 'Captación', ventas: 'Ventas', arriendos: 'Arriendos' }
const tabs = computed(() => (Object.keys(TAB_LABELS) as Tab[]).filter((t) => d.value.resultados[t]))
const tab = ref<Tab | null>(null)
const tabActual = computed<Tab | null>(() => (tab.value && tabs.value.includes(tab.value) ? tab.value : tabs.value[0] ?? null))
const kpis = computed(() => {
  const r = tabActual.value ? d.value.resultados[tabActual.value] : null
  if (!r) return []
  if (tabActual.value === 'captacion')
    return [
      ['Captaciones de venta aprobadas', r.aprobadas_venta],
      ['Captaciones de arriendo aprobadas', r.aprobadas_arriendo],
      ['Por verificar', r.por_verificar],
      ['Publicadas', r.publicadas],
    ]
  const neg = tabActual.value === 'ventas' ? 'venta' : 'arriendo'
  return [
    [`Citas de ${neg}`, r.citas],
    ['Realizadas', r.realizadas],
    ['Próximas aceptadas', r.proximas],
    ['Por responder', r.por_responder],
  ]
})
const capta = computed(() => d.value.asesor.actividades.includes('captacion'))

// «Mi puntaje del mes»: loads after the page, it doesn't block the home.
const rendApi = useRendimiento()
const { data: puntaje } = useLazyAsyncData('asesor-puntaje', () => rendApi.mio().catch(() => null), { server: false })
</script>

<template>
  <div class="cnt home">
    <PausaBanner v-if="!viewing" />
    <div v-if="error" class="note bad"><b>No se pudo cargar tu inicio.</b> {{ apiErrorMessage(error) }}</div>
    <template v-else-if="data">
      <div v-if="viewing" class="note warn">
        Estás viendo el inicio de <b>{{ d.asesor.full_name }}</b> (solo lectura). <NuxtLink to="/coordinacion">Volver al tablero ›</NuxtLink>
      </div>

      <div>
        <h1 class="ttl">Hola, {{ firstName(d.asesor.full_name) }}</h1>
        <div class="mut sub">{{ cargoTxt }} · {{ hoy }}</div>
      </div>

      <NuxtLink v-if="!soloLectura && puntaje" class="card puntaje" to="/resultados">
        <ScoreRing :value="puntaje.total" :size="74" />
        <div>
          <div class="lbl">Mi puntaje del mes</div>
          <div class="small">{{ puntaje.mejoras.items[0] ? `Por mejorar: ${puntaje.mejoras.items[0].titulo} (${puntaje.mejoras.items[0].cumplimiento} %)` : 'Vas bien en todas tus áreas' }}</div>
          <span class="mut tiny">Ver mis resultados ›</span>
        </div>
      </NuxtLink>
      <PreopBanner v-if="!soloLectura" :activo="d.preoperacional.activo" :realizado-at="d.preoperacional.realizado_at" :novedad="d.preoperacional.tiene_novedad" />
      <span v-else-if="d.preoperacional.activo" class="chip self-start" :class="d.preoperacional.realizado_at ? 'ok' : 'bad'">
        {{ d.preoperacional.realizado_at ? `✓ Preoperacional realizado ${fmtHora(d.preoperacional.realizado_at)}` : 'Preoperacional de hoy: falta' }}
      </span>

      <div class="card list">
        <div class="sb lhead"><span class="lbl">Mis pendientes y recordatorios</span><span class="chip" :class="d.pendientes.length ? 'warn' : 'ok'">{{ d.pendientes.length }}</span></div>
        <NuxtLink v-for="(p, i) in d.pendientes" :key="i" class="li" :to="p.cita_id && !soloLectura ? `/mis-citas#cita-${p.cita_id}` : p.link">
          <div><b>{{ p.titulo }}</b><div class="mut tiny">{{ p.detalle }}</div></div>
          <span class="chip" :class="p.cls">{{ p.chip }}</span>
        </NuxtLink>
        <p v-if="!d.pendientes.length" class="mut small pad">Estás al día: no tienes pendientes.</p>
        <div class="mut tiny foot">Aquí aparecen las citas por responder o por cerrar, las que otro asesor rechazó y puedes tomar{{ capta ? ', y tus captaciones por corregir o publicar' : '' }}.</div>
      </div>

      <div class="card list">
        <div class="sb lhead"><span class="lbl">Mis citas de hoy</span><NuxtLink :to="soloLectura ? `/mis-citas?asesor=${viewing}` : '/mis-citas'" class="lnk">Ver todas ›</NuxtLink></div>
        <NuxtLink v-for="c in d.citas_hoy" :key="c.id" class="li" :to="soloLectura ? `/mis-citas?asesor=${viewing}` : `/mis-citas#cita-${c.id}`">
          <div><b>{{ fmtHora(c.scheduled_at) }} · {{ c.code }} · {{ CITA_TIPO_CORTO[c.tipo] }}</b><div class="mut tiny">{{ c.inmueble ? `${c.inmueble} · ` : '' }}{{ c.cliente }}</div></div>
          <span class="chip" :class="citaChip(c.estado).cls">{{ citaChip(c.estado).t }}</span>
        </NuxtLink>
        <p v-if="!d.citas_hoy.length" class="mut small pad">No tienes citas hoy.</p>
      </div>

      <div class="card stack">
        <span class="lbl">Mis actividades</span>
        <div class="row wrap">
          <span v-for="a in d.asesor.actividades" :key="a" class="act on1">✓ {{ ACTIVIDAD_LABELS[a] }}</span>
        </div>
        <div v-if="d.asesor.gps_checkin_enabled" class="gps">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z" /><circle cx="12" cy="9.5" r="2.5" /></svg>
          <span><b>GPS activo</b> · porque tienes Captación activa · solo en jornada 8:00 a. m.–6:00 p. m.</span>
        </div>
        <div v-else class="note">Sin GPS: se activa solo con Captación.</div>
      </div>

      <template v-if="tabs.length">
        <div class="lbl">Mis resultados de {{ mes }}</div>
        <div v-if="tabs.length > 1" class="tabs" role="tablist">
          <button v-for="t in tabs" :key="t" type="button" class="tab grow" :class="{ on: tabActual === t }" role="tab" :aria-selected="tabActual === t" @click="tab = t">{{ TAB_LABELS[t] }}</button>
        </div>
        <div class="card stack">
          <div class="g2 tiles">
            <div v-for="[t, v] in kpis" :key="t" class="st"><div class="lbl">{{ t }}</div><div class="kn num">{{ v }}</div></div>
          </div>
          <span class="chip pend self-start">Meta del mes y cumplimiento: pendiente de configuración</span>
        </div>
      </template>

      <div v-if="!soloLectura" class="g2 qas">
        <NuxtLink class="qa" to="/pedidos">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3h9l3 3v15H6z" /><path d="M9 11h6" /><path d="M9 15h6" /></svg>
          Pedidos
        </NuxtLink>
        <NuxtLink v-if="capta" class="qa" to="/captaciones">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 11l9-8 9 8" /><path d="M5 10v10h14V10" /><path d="M12 13v5" /><path d="M9.5 15.5h5" /></svg>
          Nueva captación
        </NuxtLink>
        <NuxtLink class="qa" to="/mis-citas">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18" /><path d="M8 3v4" /><path d="M16 3v4" /></svg>
          Mis citas{{ d.citas_counts.responder ? ` · ${d.citas_counts.responder} por responder` : '' }}
        </NuxtLink>
        <NuxtLink v-if="capta" class="qa" to="/captaciones">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 11l3 3 8-8" /><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9" /></svg>
          Mis captaciones enviadas
        </NuxtLink>
        <NuxtLink class="qa" to="/preoperacional">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></svg>
          Mi preoperacional
        </NuxtLink>
        <button type="button" class="qa qa-btn" @click="refresh()">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-3-6.7L21 8" /><path d="M21 3v5h-5" /></svg>
          Actualizar
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.home {
  max-width: 760px;
  width: 100%;
}
.sub {
  font-size: 13px;
  margin-top: 2px;
}
.list {
  padding: 4px 14px;
}
.lhead {
  padding-top: 10px;
}
.lnk {
  font-weight: 700;
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.small {
  font-size: 12.5px;
}
.pad {
  padding: 8px 0;
}
.foot {
  padding: 8px 0 10px;
  font-size: 11.5px;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.wrap {
  flex-wrap: wrap;
  gap: 6px;
}
.gps {
  display: flex;
  gap: 8px;
  align-items: center;
  background: var(--cdc-info-bg);
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 12px;
  color: var(--cdc-green-dark);
}
.grow {
  flex: 1;
}
.tiles {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.st .kn {
  font-size: 32px;
}
.self-start {
  align-self: flex-start;
}
.qas {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.qa-btn {
  border: 0;
  font-family: inherit;
  cursor: pointer;
}
.puntaje {
  display: flex;
  gap: 14px;
  align-items: center;
  color: inherit;
  text-decoration: none;
}
.puntaje :deep(.big) {
  font-size: 24px;
}
</style>
