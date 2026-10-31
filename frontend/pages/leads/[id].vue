<script setup lang="ts">
import type { EtapaLead, LeadDetail, LeadFields } from '~/types/leads'

/** Gestionar lead (prototype C02): actions, history, client data, next actions, cita. */
definePageMeta({ module: 'leads' })

const route = useRoute()
const auth = useAuth()
const leads = useLeads()
const manager = computed(() => isManager(auth.user.value))

const id = computed(() => String(route.params.id))
const { data: lead, error: loadError } = await useAsyncData(`lead-${id.value}`, () => leads.get(id.value))
if (loadError.value) {
  throw createError({ statusCode: 404, message: 'Lead no encontrado.' })
}
const l = computed(() => lead.value!)
useHead(() => ({ title: `${l.value.code} · ${l.value.full_name} · Casa Dolce Casa` }))

const closed = computed(() => l.value.etapa === 'ganado' || l.value.etapa === 'perdido')
const editable = computed(() => l.value.can_edit && !closed.value)
const estado = computed(() => leadEstado(l.value))
const set = (d: LeadDetail) => (lead.value = d)
function onActionDone(d: LeadDetail) {
  set(d)
  flash.value = null // the actions card shows its own confirmation
  error.value = null
}

const flash = ref<string | null>(route.query.tomado ? 'Ahora sigues este lead. ¿Qué acción vas a realizar?' : null)
const error = ref<string | null>(null)

// ---- header actions ----------------------------------------------------------
const lostOpen = ref(false)
async function run(fn: () => Promise<LeadDetail>, ok: string) {
  error.value = null
  try {
    set(await fn())
    flash.value = ok
  } catch (e) {
    error.value = apiErrorMessage(e)
  }
}
const seguir = () => run(() => leads.follow(l.value.id), 'Ahora sigues este lead y quedó registrado.')
const ganado = () => run(() => leads.stage(l.value.id, 'ganado'), 'Lead marcado como ganado y archivado.')
const reabrir = () => run(() => leads.stage(l.value.id, 'en_gestion' as EtapaLead), 'Lead reabierto: vuelve a «En gestión».')
function onLost(d: LeadDetail) {
  set(d)
  lostOpen.value = false
  flash.value = 'Lead marcado como perdido. Quedó archivado para Gerencia con motivo, fecha y responsable.'
}

// ---- subtitle & chain --------------------------------------------------------
const subtitle = computed(() => {
  const a = l.value.assigned_to
  const who = a ? `Lo sigue ${a.full_name}${l.value.assigned_at ? ` desde ${fmtCuando(l.value.assigned_at)}` : ''}` : 'Sin responsable'
  return l.value.negocio ? `${who} · busca ${NEGOCIO_LABELS[l.value.negocio].toLowerCase()}` : who
})
const cadena = computed(() => {
  const c = l.value.cita_activa
  return [
    { t: `Lead ${l.value.code}`, cls: 'info' },
    { t: l.value.full_name, cls: 'info' },
    l.value.assigned_to ? { t: l.value.assigned_to.full_name, cls: 'info' } : { t: 'Sin responsable', cls: 'gray' },
    c?.asesor_name ? { t: `Asesor: ${c.asesor_name}`, cls: 'ok' } : { t: 'Asesor: sin asignar', cls: 'gray' },
    c ? { t: `Cita ${c.code}`, cls: citaChip(c.estado).cls } : { t: 'Cita: sin programar', cls: 'gray' },
  ]
})

// ---- history -----------------------------------------------------------------
const filtro = ref('todo')
const historial = computed(() =>
  l.value.eventos.filter((e) => filtro.value === 'todo' || EVENTO_TIPO[e.tipo].grupo === filtro.value),
)

// ---- client data (inline edit) -----------------------------------------------
const editing = ref(false)
const form = reactive<Record<keyof LeadFields, string>>({
  full_name: '', phone: '', email: '', fuente: '', fuente_detalle: '', negocio: '',
  busca: '', presupuesto: '', zona: '', para_cuando: '', notas: '',
})
function startEdit() {
  for (const k of Object.keys(form) as (keyof LeadFields)[]) form[k] = (l.value[k] as string | null) ?? ''
  editing.value = true
}
async function saveEdit() {
  const body: Record<string, string | null> = {}
  for (const k of Object.keys(form) as (keyof LeadFields)[]) {
    const v = form[k].trim() || null
    if (v !== ((l.value[k] as string | null) ?? null)) body[k] = v
  }
  if (!Object.keys(body).length) return (editing.value = false)
  try {
    set(await leads.update(l.value.id, body as Partial<LeadFields>))
    editing.value = false
    flash.value = 'Datos del cliente actualizados.'
  } catch (e) {
    error.value = apiErrorMessage(e)
  }
}
const datos = computed(() => [
  ['Nombre', l.value.full_name],
  ['Teléfono', l.value.phone],
  ['Correo', l.value.email ?? '—'],
  ['Busca', [l.value.negocio ? NEGOCIO_LABELS[l.value.negocio] : null, l.value.busca].filter(Boolean).join(' · ') || '—'],
  ['Presupuesto', l.value.presupuesto ?? '—'],
  ['Zona', l.value.zona ?? '—'],
  ['¿Para cuándo?', l.value.para_cuando ?? '—'],
  ['Llegó desde', [FUENTE_LABELS[l.value.fuente], l.value.fuente_detalle].filter(Boolean).join(' · ')],
  ['Llamadas', `${llamadasTxt(l.value.llamadas)}${l.value.llamadas_dias_seguidos > 1 ? ` · ${l.value.llamadas_dias_seguidos} días seguidos` : ''}`],
])

// ---- reassign (managers) -----------------------------------------------------
const { data: responsables } = await useAsyncData('lead-responsables', () =>
  manager.value ? leads.responsables() : Promise.resolve([]),
)
const assignTo = ref(l.value.assigned_to?.id ?? '')
watch(() => l.value.assigned_to?.id, (v) => (assignTo.value = v ?? ''))
async function reasignar() {
  await run(() => leads.update(l.value.id, { assigned_to_id: assignTo.value || null }), 'Responsable actualizado. Quedó en el historial.')
}

// ---- next actions --------------------------------------------------------------
const pendientes = computed(() => l.value.seguimientos.filter((s) => !s.done_at))
const actionsPanel = ref<{ open: (f: 'seg' | 'cita') => void } | null>(null)
function onSegDone(d: LeadDetail, next: 'seg' | 'cita' | null) {
  set(d)
  flash.value = 'Seguimiento realizado y guardado en el historial.'
  if (next) {
    actionsPanel.value?.open(next)
    if (import.meta.client) window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}
const citaAnteriores = computed(() => l.value.citas.filter((c) => c.id !== l.value.cita_activa?.id).reverse())
</script>

<template>
  <PageBar :title="`${l.code} · ${l.full_name}`" :subtitle="subtitle" back="/leads">
    <span class="chip info">Llegó desde: {{ FUENTE_LABELS[l.fuente] }}{{ l.fuente_detalle ? ` (${l.fuente_detalle})` : '' }}</span>
    <span class="chip big" :class="estado.cls">{{ estado.t }}</span>
    <button v-if="!l.assigned_to && !closed" type="button" class="btn bp" @click="seguir">Seguir lead</button>
    <button v-if="manager && !closed" type="button" class="btn bs" @click="ganado">Ganado</button>
    <button v-if="editable" type="button" class="btn br" @click="lostOpen = true">Perdido</button>
    <button v-if="manager && closed" type="button" class="btn bs" @click="reabrir">Reabrir</button>
  </PageBar>

  <div class="cnt">
    <div class="row chain">
      <template v-for="(c, i) in cadena" :key="i">
        <span class="chip" :class="c.cls">{{ c.t }}</span>
        <span v-if="i < cadena.length - 1" class="mut">→</span>
      </template>
    </div>

    <div v-if="flash" class="note ok" role="status"><b>✓ {{ flash }}</b></div>
    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>

    <div v-if="closed" class="note" :class="l.etapa === 'ganado' ? 'ok' : ''">
      <b>{{ l.etapa === 'ganado' ? 'Lead ganado' : `Lead perdido · ${l.motivo_perdida ? MOTIVO_LABELS[l.motivo_perdida] : ''}` }}</b>
      <template v-if="l.etapa === 'perdido'"> · {{ l.perdida_descuenta ? 'descuenta en el rendimiento' : 'no descuenta' }}</template>
      <template v-if="l.cerrado_at"> · {{ fmtCuando(l.cerrado_at) }}</template>.
      Quedó archivado{{ manager ? '; puedes reabrirlo.' : '.' }}
    </div>

    <LeadActions v-if="editable" ref="actionsPanel" :lead="l" @updated="onActionDone" />
    <div v-else-if="!closed" class="note">
      {{ l.assigned_to ? `Este lead lo sigue ${l.assigned_to.full_name}.` : 'Toma el lead con «Seguir lead» para registrar acciones.' }}
    </div>

    <div class="split">
      <div class="card">
        <div class="sb head">
          <span class="lbl">Conversación e historial · en orden cronológico</span>
          <div class="row wrap">
            <button v-for="[k, t] in EVENTO_FILTROS" :key="k" type="button" class="fch" :class="{ on: filtro === k }" @click="filtro = k">{{ t }}</button>
          </div>
        </div>
        <p v-if="!historial.length" class="mut small">Sin registros de este tipo.</p>
        <div v-for="e in historial" :key="e.id" class="feed">
          <span class="num when">{{ fmtCuando(e.created_at) }}</span>
          <div class="ev">
            <div class="row ev-head">
              <span class="chip" :class="EVENTO_TIPO[e.tipo].cls">{{ EVENTO_TIPO[e.tipo].t }}</span>
              <b>{{ e.titulo }}</b>
            </div>
            <div v-if="e.detalle" class="bubble" :class="EVENTO_TIPO[e.tipo].bg">{{ e.detalle }}</div>
            <span class="mut tiny">{{ e.created_by_name ?? 'Sistema' }}</span>
          </div>
        </div>
        <div class="mut tiny wa-note">Conexión con WhatsApp y correo para ver los mensajes del cliente aquí: pendiente de configuración.</div>
      </div>

      <div class="col">
        <div class="card stack">
          <div class="sb">
            <span class="lbl">Datos del cliente</span>
            <button v-if="editable && !editing" type="button" class="btn bs sm" @click="startEdit">Editar</button>
          </div>
          <template v-if="!editing">
            <div v-for="[k, v] in datos" :key="k" class="sb kv">
              <span class="mut">{{ k }}</span><b>{{ v }}</b>
            </div>
          </template>
          <form v-else class="stack" @submit.prevent="saveEdit">
            <div class="fld"><label for="ed-n">Nombre</label><input id="ed-n" v-model="form.full_name" class="in" required></div>
            <div class="fld"><label for="ed-t">Teléfono</label><input id="ed-t" v-model="form.phone" class="in" required minlength="7"></div>
            <div class="fld"><label for="ed-e">Correo</label><input id="ed-e" v-model="form.email" class="in" type="email"></div>
            <div class="fld">
              <label for="ed-neg">Negocio</label>
              <select id="ed-neg" v-model="form.negocio" class="in"><option value="arriendo">Arriendo</option><option value="venta">Venta</option></select>
            </div>
            <div class="fld"><label for="ed-b">Busca</label><input id="ed-b" v-model="form.busca" class="in"></div>
            <div class="fld"><label for="ed-p">Presupuesto</label><input id="ed-p" v-model="form.presupuesto" class="in"></div>
            <div class="fld"><label for="ed-z">Zona</label><input id="ed-z" v-model="form.zona" class="in"></div>
            <div class="fld"><label for="ed-c">¿Para cuándo?</label><input id="ed-c" v-model="form.para_cuando" class="in"></div>
            <div class="g2">
              <button type="button" class="btn bs" @click="editing = false">Cancelar</button>
              <button type="submit" class="btn bp">Guardar</button>
            </div>
          </form>

          <div v-if="manager" class="reassign">
            <div class="lbl">Responsable</div>
            <div class="row">
              <select v-model="assignTo" class="in" aria-label="Responsable">
                <option value="">Sin responsable</option>
                <option v-for="r in responsables ?? []" :key="r.id" :value="r.id">{{ r.full_name }}</option>
              </select>
              <button type="button" class="btn bs" :disabled="assignTo === (l.assigned_to?.id ?? '')" @click="reasignar">Reasignar</button>
            </div>
          </div>
        </div>

        <div class="card stack">
          <div class="lbl">Próximas acciones</div>
          <SeguimientoItem
            v-for="s in pendientes"
            :key="s.id"
            :lead-id="l.id"
            :seg="s"
            :can-edit="editable"
            @done="onSegDone"
          />
          <div v-if="!pendientes.length" class="note">No hay acciones pendientes. Usa «Seguimiento del cliente».</div>
        </div>

        <div class="card stack">
          <div class="lbl">Estado de la cita</div>
          <div v-if="!l.cita_activa" class="mut small">Aún no hay cita programada.</div>
          <div v-else class="stack tight">
            <div class="sb">
              <b>{{ l.cita_activa.code }} · {{ l.cita_activa.asesor_name ?? 'sin asesor' }}</b>
              <span class="chip" :class="citaChip(l.cita_activa.estado).cls">{{ citaChip(l.cita_activa.estado).t }}</span>
            </div>
            <span class="mut small">
              {{ CITA_TIPO_LABELS[l.cita_activa.tipo] }} · {{ fmtCuando(l.cita_activa.scheduled_at) }}{{ l.cita_activa.inmueble ? ` · ${l.cita_activa.inmueble}` : '' }}.
              Si a 1 hora de la cita nadie la ha aceptado, aparece en «Citas que requieren acción».
            </span>
            <NuxtLink class="btn bs self-start" to="/citas">Ver en control de citas</NuxtLink>
          </div>
          <div v-for="c in citaAnteriores" :key="c.id" class="sb kv">
            <span class="mut">{{ c.code }} · {{ fmtCuando(c.scheduled_at) }}</span>
            <span class="chip" :class="citaChip(c.estado).cls">{{ citaChip(c.estado).t }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <LeadLostDialog v-if="lostOpen" :lead-id="l.id" :title="`${l.code} · ${l.full_name}`" @done="onLost" @cancel="lostOpen = false" />
</template>

<style scoped>
.chip.big {
  font-size: 13px;
  padding: 6px 12px;
}
.chain {
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12.5px;
}
.chain .chip {
  padding: 5px 10px;
}
.head {
  margin-bottom: 8px;
}
.wrap {
  flex-wrap: wrap;
  gap: 6px;
}
.when {
  width: 92px;
  flex: none;
  font-weight: 800;
  font-size: 12px;
}
.ev {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.ev-head {
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13.5px;
}
.bubble {
  font-size: 13px;
  padding: 8px 10px;
  border-radius: 10px;
  white-space: pre-wrap;
}
.tiny {
  font-size: 11.5px;
}
.small {
  font-size: 12.5px;
}
.wa-note {
  margin-top: 8px;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stack.tight {
  gap: 6px;
}
.kv {
  font-size: 13px;
  padding: 3px 0;
  flex-wrap: nowrap;
}
.kv b {
  text-align: right;
}
.reassign {
  border-top: 1px solid var(--cdc-border-soft);
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.self-start {
  align-self: flex-start;
}
@media (max-width: 760px) {
  .when {
    width: 64px;
  }
}
</style>
