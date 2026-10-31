<script setup lang="ts">
import type { Cita, LeadSummary } from '~/types/leads'
import type { LeadQuery } from '~/composables/useLeads'

/** Atención y Preventa · inicio (prototype C01). */
definePageMeta({ module: 'leads' })
useHead({ title: 'Atención y Preventa · Casa Dolce Casa' })

const auth = useAuth()
const leads = useLeads()
const me = computed(() => auth.user.value!)
const manager = computed(() => isManager(me.value))

// ---- KPIs ------------------------------------------------------------------
const periodo = ref<'mes' | 'semana' | 'hoy'>('mes')
const PERIODOS = { mes: 'Este mes', semana: 'Esta semana', hoy: 'Hoy' } as const
const { data: stats, refresh: refreshStats } = await useAsyncData('lead-stats', () => leads.stats(periodo.value), {
  watch: [periodo],
})
const kpis = computed(() => {
  const s = stats.value
  if (!s) return []
  const quien = manager.value ? 'del equipo' : 'tuyos'
  return [
    { t: 'Leads recibidos', v: s.recibidos, d: `del área · ${s.sin_responsable} sin responsable` },
    { t: manager.value ? 'Leads tomados' : 'Leads que seguí', v: s.seguidos, d: 'con «Seguir lead»' },
    { t: 'Llamadas', v: s.llamadas, d: `${s.llamadas_contestadas} contestadas` },
    { t: 'Seguimientos', v: s.seguimientos, d: `${s.seguimientos_realizados} realizados · ${quien}` },
    { t: 'Citas programadas', v: s.citas_programadas, d: quien },
    { t: 'Citas realizadas', v: s.citas_realizadas, d: quien },
  ]
})

// ---- Leads nuevos (sin responsable) ----------------------------------------
const { data: nuevos, refresh: refreshNuevos } = await useAsyncData(
  'leads-nuevos',
  () => leads.list({ assigned: 'none', abiertos: true }),
  { default: () => [] as LeadSummary[] },
)

// ---- Citas que requieren acción ---------------------------------------------
const { data: citasAccion, refresh: refreshCitas } = await useAsyncData(
  'citas-accion',
  () => leads.citas({ bucket: 'accion' }),
)

// ---- Mis leads / leads del equipo ---------------------------------------------
type Tab = 'todo' | 'ges' | 'cita' | 'arch'
const tab = ref<Tab>('todo')
const filtros = reactive({ q: '', assigned: '', fuente: '', desde: '', hasta: '' })
const TABS = computed<[Tab, string][]>(() => [
  ['todo', manager.value ? 'Todos abiertos' : 'Todos los que sigo'],
  ['ges', 'En gestión'],
  ['cita', 'Con cita'],
  ...(manager.value ? ([['arch', 'Ganados y perdidos']] as [Tab, string][]) : []),
])

const query = computed<LeadQuery>(() => {
  const q: LeadQuery = {
    q: filtros.q.trim() || undefined,
    fuente: filtros.fuente || undefined,
    desde: filtros.desde || undefined,
    hasta: filtros.hasta || undefined,
    assigned: manager.value ? filtros.assigned || undefined : 'me',
  }
  if (tab.value === 'ges') q.etapa = ['nuevo', 'en_gestion', 'seguimiento']
  else if (tab.value === 'cita') q.etapa = ['cita_programada']
  else q.abiertos = tab.value !== 'arch'
  return q
})
const { data: mis, pending, refresh: refreshMis } = await useAsyncData('leads-mis', () => leads.list(query.value), {
  default: () => [] as LeadSummary[],
  watch: [query],
})
const { data: responsables } = await useAsyncData('lead-responsables', () =>
  manager.value ? leads.responsables() : Promise.resolve([]),
)

// Recordatorios de hoy: next follow-up of my open leads due today (or overdue).
const { data: mios } = await useAsyncData(
  'leads-mios-abiertos',
  () => leads.list({ assigned: manager.value ? undefined : 'me', abiertos: true }),
  { default: () => [] as LeadSummary[] },
)
const recordatorios = computed(() =>
  mios.value
    .filter((l) => l.proximo_seguimiento && (isToday(l.proximo_seguimiento.due_at) || minutesUntil(l.proximo_seguimiento.due_at) < 0))
    .filter((l) => manager.value || l.assigned_to?.id === me.value.id)
    .sort((a, b) => a.proximo_seguimiento!.due_at.localeCompare(b.proximo_seguimiento!.due_at)),
)

async function refreshAll() {
  await Promise.all([refreshStats(), refreshNuevos(), refreshCitas(), refreshMis()])
}

// ---- actions --------------------------------------------------------------------
const error = ref<string | null>(null)
const flash = ref<string | null>(null)
const nuevoOpen = ref(false)
const perdido = ref<LeadSummary | null>(null)

async function seguir(lead: LeadSummary) {
  error.value = null
  try {
    await leads.follow(lead.id)
    await navigateTo(`/leads/${lead.id}?tomado=1`)
  } catch (e) {
    error.value = `${lead.code}: ${apiErrorMessage(e)}`
    await refreshNuevos()
  }
}

async function onCreated(lead: { id: string; code: string }) {
  nuevoOpen.value = false
  await navigateTo(`/leads/${lead.id}`)
}

async function onPerdido() {
  flash.value = `${perdido.value?.code} · ${perdido.value?.full_name} quedó archivado como perdido.`
  perdido.value = null
  await refreshAll()
}

function citaAccionChip(c: Cita) {
  if (c.estado === 'rechazada') return { t: 'Rechazada', cls: 'warn' }
  if (!c.asesor) return { t: 'Sin asesor', cls: 'bad' }
  const m = minutesUntil(c.scheduled_at)
  return { t: m < 0 ? 'Ya pasó la hora' : `Faltan ${m} min`, cls: 'bad' }
}
</script>

<template>
  <PageBar
    title="Atención y Preventa"
    :subtitle="`${me.full_name} · un solo flujo: desde que llega el lead hasta que pasa a la siguiente etapa`"
  >
    <label class="row per">
      {{ manager ? 'Cifras de:' : 'Ver mis cifras de:' }}
      <select v-model="periodo" class="sel" aria-label="Período de las cifras">
        <option v-for="(t, k) in PERIODOS" :key="k" :value="k">{{ t }}</option>
      </select>
    </label>
    <NuxtLink class="btn bs" to="/citas">Control de citas</NuxtLink>
    <NuxtLink class="btn bs" to="/pedidos">Pedidos</NuxtLink>
    <NuxtLink v-if="perfilRendimiento(auth.user.value) === 'atencion'" class="btn bs" to="/resultados">Mis resultados</NuxtLink>
    <button type="button" class="btn bp" @click="nuevoOpen = !nuevoOpen">+ Registrar lead</button>
  </PageBar>

  <div class="cnt">
    <LeadNewCard v-if="nuevoOpen" @cancel="nuevoOpen = false" @created="onCreated" />
    <div v-if="flash" class="note ok" role="status"><b>✓ {{ flash }}</b></div>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>

    <div class="g6">
      <div v-for="k in kpis" :key="k.t" class="card kpi">
        <div class="lbl">{{ k.t }}</div>
        <div class="kn num">{{ k.v }}</div>
        <div class="mut tiny">{{ k.d }}</div>
      </div>
    </div>

    <div class="split">
      <div class="col">
        <div class="card">
          <div class="sb head">
            <span class="lbl">Leads nuevos · llegan solos al sistema</span>
            <span class="chip" :class="nuevos.length ? 'warn' : 'ok'">{{ nuevos.length }} sin responsable</span>
          </div>
          <div class="mut small intro">
            No hay que cargarlos ni asignarlos. Al pulsar «Seguir lead» quedas como responsable y nadie más del equipo
            puede tomarlo, salvo que Coordinación o Gerencia lo reasigne.
          </div>
          <div v-if="!nuevos.length" class="note">No hay leads nuevos sin responsable. 🎉</div>
          <div v-for="l in nuevos" :key="l.id" class="sb lead-row">
            <div class="lead-info">
              <b>{{ l.code }} · {{ l.full_name }}</b>
              <span class="mut small">
                {{ l.negocio ? `Busca ${NEGOCIO_LABELS[l.negocio].toLowerCase()}` : 'Busca' }}{{ l.busca ? ` · ${l.busca}` : '' }}
                · llegó {{ fmtCuando(l.created_at) }}
              </span>
              <span class="chip info self-start">Llegó desde: {{ FUENTE_LABELS[l.fuente] }}</span>
            </div>
            <span class="row">
              <NuxtLink v-if="manager" class="btn bs" :to="`/leads/${l.id}`">Ver</NuxtLink>
              <button type="button" class="btn bp" @click="seguir(l)">Seguir lead</button>
            </span>
          </div>
        </div>
      </div>

      <div class="col">
        <div class="card" :class="{ 'warn-card': citasAccion?.items.length }">
          <div class="lbl head-sm">Citas que requieren acción</div>
          <p v-if="!citasAccion?.items.length" class="mut small none">Ninguna cita requiere acción ahora.</p>
          <NuxtLink v-for="c in citasAccion?.items ?? []" :key="c.id" class="it" to="/citas">
            <div class="sb">
              <b>{{ c.code }} · {{ c.estado === 'rechazada' ? 'rechazada' : c.asesor ? 'sin aceptar' : 'sin responsable' }}</b>
              <span class="chip" :class="citaAccionChip(c).cls">{{ citaAccionChip(c).t }}</span>
            </div>
            <span class="mut small">{{ CITA_TIPO_CORTO[c.tipo] }} · {{ fmtCuando(c.scheduled_at) }} · {{ c.lead.full_name }} · Reasignar, reprogramar o cancelar ›</span>
          </NuxtLink>
        </div>

        <div class="card">
          <div class="lbl head-sm">{{ manager ? 'Recordatorios de hoy del equipo' : 'Mis recordatorios de hoy' }}</div>
          <p v-if="!recordatorios.length" class="mut small none">No hay seguimientos para hoy.</p>
          <NuxtLink v-for="l in recordatorios" :key="l.id" class="it" :to="`/leads/${l.id}`">
            <div class="sb">
              <b>{{ fmtHora(l.proximo_seguimiento!.due_at) }} · {{ ACCION_LABELS[l.proximo_seguimiento!.accion] }}</b>
              <span class="chip" :class="minutesUntil(l.proximo_seguimiento!.due_at) < 0 ? 'bad' : 'warn'">
                {{ minutesUntil(l.proximo_seguimiento!.due_at) < 0 ? 'Vencido' : 'Hoy' }}
              </span>
            </div>
            <span class="mut small">{{ l.code }} · {{ l.full_name }}{{ l.proximo_seguimiento!.nota ? ` · ${l.proximo_seguimiento!.nota}` : '' }}</span>
          </NuxtLink>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="sb head">
        <span class="lbl">
          {{ manager ? 'Leads del equipo' : 'Mis leads · todos los que tomaste con «Seguir lead»' }} · toca el cliente para ver el proceso
        </span>
        <div class="tabs">
          <button v-for="[k, t] in TABS" :key="k" type="button" class="tab" :class="{ on: tab === k }" @click="tab = k">{{ t }}</button>
        </div>
      </div>

      <div class="row filters">
        <input v-model="filtros.q" class="in f-q" type="search" placeholder="Buscar nombre, teléfono o LD-…" aria-label="Buscar">
        <select v-if="manager" v-model="filtros.assigned" class="sel" aria-label="Responsable">
          <option value="">Todos los responsables</option>
          <option value="none">Sin responsable</option>
          <option v-for="r in responsables ?? []" :key="r.id" :value="r.id">{{ r.full_name }}</option>
        </select>
        <select v-model="filtros.fuente" class="sel" aria-label="Fuente">
          <option value="">Todas las fuentes</option>
          <optgroup v-for="g in FUENTE_GRUPOS" :key="g.label" :label="g.label">
            <option v-for="f in g.fuentes" :key="f" :value="f">{{ FUENTE_LABELS[f] }}</option>
          </optgroup>
        </select>
        <label class="row date">Desde <input v-model="filtros.desde" class="in" type="date" aria-label="Llegó desde"></label>
        <label class="row date">Hasta <input v-model="filtros.hasta" class="in" type="date" aria-label="Llegó hasta"></label>
      </div>

      <div class="wrap">
        <table class="tbl mis">
          <thead>
            <tr>
              <th>Lead</th>
              <th>Estado</th>
              <th>Próxima acción o resultado</th>
              <th v-if="manager">Responsable</th>
              <th><span class="sr-only">Acciones</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="l in mis" :key="l.id">
              <td>
                <NuxtLink :to="`/leads/${l.id}`" class="lead-link">{{ l.code }} · {{ l.full_name }}</NuxtLink><br>
                <span class="mut small">{{ l.negocio ? NEGOCIO_LABELS[l.negocio] : 'Sin tipo' }} · {{ llamadasTxt(l.llamadas) }} · {{ FUENTE_LABELS[l.fuente] }}</span>
              </td>
              <td><span class="chip" :class="leadEstado(l).cls">{{ leadEstado(l).t }}</span></td>
              <td>{{ leadProxima(l) }}</td>
              <td v-if="manager">{{ l.assigned_to?.full_name ?? '—' }}</td>
              <td>
                <span class="row acts">
                  <NuxtLink v-if="l.can_edit && !['ganado', 'perdido'].includes(l.etapa)" class="btn bp sm" :to="`/leads/${l.id}`">Registrar acción</NuxtLink>
                  <NuxtLink v-else class="btn bs sm" :to="`/leads/${l.id}`">Ver proceso</NuxtLink>
                  <button
                    v-if="l.can_edit && !['ganado', 'perdido'].includes(l.etapa)"
                    type="button"
                    class="btn bs sm soft-bad"
                    @click="perdido = l"
                  >
                    Perdido
                  </button>
                </span>
              </td>
            </tr>
            <tr v-if="!mis.length">
              <td :colspan="manager ? 5 : 4" class="mut empty">{{ pending ? 'Cargando…' : 'No hay leads en esta vista.' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="note foot">
        <b>Ganado y perdido:</b> al marcarlo, el lead sale de tu lista y queda archivado para Gerencia. «Ganado» lo
        confirma Coordinación o Gerencia con el cierre del negocio. Un perdido descuenta en el rendimiento, salvo si el
        número estaba equivocado o si no contestó después de mínimo 3 llamadas en 3 días seguidos.
      </div>
    </div>
  </div>

  <LeadLostDialog
    v-if="perdido"
    :lead-id="perdido.id"
    :title="`${perdido.code} · ${perdido.full_name}`"
    @done="onPerdido"
    @cancel="perdido = null"
  />
</template>

<style scoped>
.per {
  gap: 6px;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--cdc-gray);
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
.head {
  margin-bottom: 6px;
  gap: 8px;
}
.head-sm {
  margin-bottom: 6px;
}
.intro {
  margin-bottom: 6px;
}
.none {
  margin: 4px 0 0;
}
.lead-row {
  padding: 12px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  flex-wrap: nowrap;
}
.lead-row:last-child {
  border-bottom: 0;
}
.lead-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.self-start {
  align-self: flex-start;
}
.warn-card {
  border: 2px solid #b7791f;
}
.filters {
  flex-wrap: wrap;
  gap: 8px;
  margin: 4px 0 10px;
}
.f-q {
  width: 260px;
  min-height: 40px;
  font-size: 13.5px;
}
.date {
  gap: 6px;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--cdc-gray);
}
.date .in {
  min-height: 40px;
  width: auto;
  font-size: 13px;
}
.mis {
  min-width: 900px;
}
.lead-link {
  font-weight: 700;
  color: var(--cdc-green);
  text-decoration: underline;
}
.acts {
  gap: 6px;
  justify-content: flex-end;
}
.empty {
  text-align: center;
  padding: 24px 10px;
}
.foot {
  margin-top: 10px;
}
@media (max-width: 760px) {
  .lead-row {
    flex-wrap: wrap;
  }
  .f-q {
    width: 100%;
  }
}
</style>
