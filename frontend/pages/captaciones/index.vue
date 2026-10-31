<script setup lang="ts">
import type { Captacion, CaptacionList, EstadoCaptacion } from '~/types/captaciones'
import type { CaptacionQuery } from '~/composables/useCaptaciones'

/**
 * Captaciones.
 * - Coordinación / Gerencia: «Verificar captaciones» (prototype K12) with indicators and filters.
 * - Captadores: «Nueva captación» + «Mis captaciones enviadas» (prototype M15).
 */
definePageMeta({ module: 'captaciones' })

const auth = useAuth()
const caps = useCaptaciones()
const me = computed(() => auth.user.value!)
const manager = computed(() => isManager(me.value))
useHead(() => ({ title: `${manager.value ? 'Verificar captaciones' : 'Captaciones'} · Casa Dolce Casa` }))

const flash = ref<string | null>(null)

// ---- Manager view (K12) ------------------------------------------------------
const tab = ref<EstadoCaptacion>('por_verificar')
const filtros = reactive({ asesor_id: '', negocio: '', desde: '', hasta: '', q: '' })
const query = computed<CaptacionQuery>(() => ({
  estado: manager.value ? [tab.value] : undefined,
  asesor_id: filtros.asesor_id || undefined,
  negocio: (filtros.negocio || undefined) as CaptacionQuery['negocio'],
  desde: filtros.desde || undefined,
  hasta: filtros.hasta || undefined,
  q: filtros.q.trim() || undefined,
}))
const { data, refresh, pending } = await useAsyncData('captaciones', () => caps.list(query.value), {
  watch: [query],
  default: (): CaptacionList => ({ items: [], counts: { por_verificar: 0, aprobada: 0, rechazada: 0 }, aprobacion_pct: null }),
})
const { data: captadores } = await useAsyncData('captadores', () =>
  manager.value ? caps.captadores() : Promise.resolve([]),
)
const hayFiltros = computed(() => Object.values(filtros).some((v) => v))
function limpiar() {
  Object.assign(filtros, { asesor_id: '', negocio: '', desde: '', hasta: '', q: '' })
}
const kpis = computed(() => {
  const c = data.value.counts
  const total = c.por_verificar + c.aprobada + c.rechazada
  return [
    { t: 'Registradas', v: total, d: hayFiltros.value ? 'con los filtros' : 'todas' },
    { t: 'Aprobadas', v: c.aprobada, d: 'suman en Captación' },
    { t: 'Por verificar', v: c.por_verificar, d: 'esperando revisión' },
    { t: 'Rechazadas', v: c.rechazada, d: 'el asesor debe corregirlas' },
    { t: '% de aprobación', v: data.value.aprobacion_pct == null ? '—' : `${data.value.aprobacion_pct}%`, d: 'de las verificadas' },
  ]
})

async function onChanged(_: Captacion, msg: string) {
  flash.value = msg
  await refresh()
}

// ---- Create (captador, or manager on behalf) -----------------------------------
const createOpen = ref(false)
async function onCreated(cap: Captacion) {
  createOpen.value = false
  flash.value = `Enviada a verificación: ${cap.code} · ${cap.codigo_inmueble}. Coordinación la revisa en la otra plataforma; cuando la apruebe, suma a ${manager.value ? `la captación de ${cap.asesor.full_name}` : 'tu indicador de Captación'}.`
  await refresh()
}
</script>

<template>
  <!-- ================= Coordinación / Gerencia: K12 ================= -->
  <template v-if="manager">
    <PageBar title="Verificar captaciones" subtitle="Solo las aprobadas suman en la captación del asesor" back="/">
      <div class="tabs">
        <button v-for="[k, t] in CAPTACION_TABS" :key="k" type="button" class="tab" :class="{ on: tab === k }" @click="tab = k">
          {{ t }} ({{ data.counts[k] }})
        </button>
      </div>
      <button type="button" class="btn bs" @click="createOpen = !createOpen">+ Registrar captación</button>
    </PageBar>

    <div class="cnt">
      <div v-if="createOpen" class="card focus">
        <CaptacionForm :captadores="captadores" cancelable @created="onCreated" @cancel="createOpen = false" />
      </div>

      <div class="g5">
        <div v-for="k in kpis" :key="k.t" class="card kpi">
          <div class="lbl">{{ k.t }}</div>
          <div class="kn num">{{ k.v }}</div>
          <div class="mut tiny">{{ k.d }}</div>
        </div>
      </div>

      <div class="filters">
        <label class="row f">Persona
          <select v-model="filtros.asesor_id" class="sel" aria-label="Filtrar por persona">
            <option value="">Todas</option>
            <option v-for="c in captadores ?? []" :key="c.id" :value="c.id">{{ c.full_name }}</option>
          </select>
        </label>
        <label class="row f">Tipo
          <select v-model="filtros.negocio" class="sel" aria-label="Filtrar por tipo">
            <option value="">Venta y arriendo</option>
            <option value="venta">Venta</option>
            <option value="arriendo">Arriendo</option>
          </select>
        </label>
        <label class="row f">Desde <input v-model="filtros.desde" class="in d" type="date" aria-label="Desde"></label>
        <label class="row f">Hasta <input v-model="filtros.hasta" class="in d" type="date" aria-label="Hasta"></label>
        <input v-model="filtros.q" class="in q" type="search" placeholder="Código, dirección, barrio…" aria-label="Buscar">
        <button v-if="hayFiltros" type="button" class="fch" @click="limpiar">✕ Quitar filtros</button>
      </div>

      <div v-if="flash" class="note ok" role="status"><b>{{ flash }}</b></div>
      <CaptacionVerifyCard v-for="c in data.items" :key="c.id + c.estado" :cap="c" @changed="onChanged" />
      <div v-if="!data.items.length" class="note">{{ pending ? 'Cargando…' : 'No hay captaciones en esta lista.' }}</div>

      <div class="note">
        El sistema no deja enviar un código ya registrado («Inmueble ya registrado»). Si rechazas, el asesor ve el motivo,
        la captación no le cuenta y debe corregirla y volver a enviarla. Cada aprobación y rechazo queda en el registro de cambios.
      </div>
    </div>
  </template>

  <!-- ================= Captador: M15 ================= -->
  <template v-else>
    <PageBar title="Nueva captación" subtitle="Registra el inmueble; Coordinación lo verifica y, al aprobarlo, suma en tu Captación" back="/" />
    <div class="cnt">
      <div v-if="flash" class="note ok" role="status"><b>{{ flash }}</b></div>
      <div class="split">
        <CaptacionForm @created="onCreated" />
        <div class="card mine">
          <div class="sb">
            <span class="lbl">Mis captaciones enviadas</span>
            <span class="row counts">
              <span class="chip warn">{{ data.counts.por_verificar }} por verificar</span>
              <span class="chip ok">{{ data.counts.aprobada }} aprobadas</span>
              <span v-if="data.counts.rechazada" class="chip bad">{{ data.counts.rechazada }} rechazadas</span>
            </span>
          </div>
          <input v-model="filtros.q" class="in q-mine" type="search" placeholder="Buscar código o dirección" aria-label="Buscar">
          <CaptacionMineItem v-for="c in data.items" :key="c.id + c.estado + c.publicada_at" :cap="c" @changed="onChanged" />
          <p v-if="!data.items.length" class="mut small">{{ pending ? 'Cargando…' : 'Aún no has enviado captaciones.' }}</p>
          <div class="mut tiny foot">
            Solo cuentan en tu rendimiento las captaciones aprobadas por Coordinación. Una rechazada no cuenta hasta que la
            corrijas y sea aprobada.
          </div>
        </div>
      </div>
    </div>
  </template>
</template>

<style scoped>
.g5 {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}
.kpi {
  padding: 14px 16px;
}
.tiny {
  font-size: 11.5px;
}
.small {
  font-size: 12.5px;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  background: var(--cdc-bg);
  border: 1px solid var(--cdc-border);
  border-radius: 12px;
  padding: 10px 12px;
}
.f {
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
}
.d {
  width: auto;
  min-height: 38px;
  font-size: 13px;
}
.q {
  width: 240px;
  min-height: 38px;
  font-size: 13px;
}
.mine {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.counts {
  gap: 6px;
  flex-wrap: wrap;
}
.q-mine {
  min-height: 38px;
  font-size: 13px;
  margin: 6px 0 2px;
}
.foot {
  padding-top: 8px;
}
@media (max-width: 1100px) {
  .g5 {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 640px) {
  .g5 {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .q {
    width: 100%;
  }
}
</style>
