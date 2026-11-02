<script setup lang="ts">
import type { Aviso, AvisoOpciones, Comunicado, VistaAvisos } from '~/types/avisos'

/**
 * G09 «Avisos y agenda» (Gerencia) · C05 / M10 «Notificaciones» (everyone else).
 * «Por atender» is the bell: only what asks for an action with a deadline. Informative notices go
 * to «Resumen del día». «Mi agenda» is each person's own scheduled actions.
 * Gerencia and Coordinación also send avisos (comunicados) and see who read them.
 */
useHead({ title: 'Avisos · Casa Dolce Casa' })

const api = useAvisos()
const { conteo, refrescar } = useAvisosConteo()
const { data: opc } = await useAsyncData('avisos-opciones', () => api.opciones())
const O = computed(() => opc.value as AvisoOpciones)

type Tab = VistaAvisos | 'agenda' | 'enviados'
const route = useRoute()
const tab = ref<Tab>((route.query.tab as Tab) || 'por_atender')
const msg = ref<{ t: string; ok: boolean } | null>(null)
const say = (t: string, ok = true) => (msg.value = { t, ok })

// ---------------------------------------------------------------- avisos
const vistaAv = computed<VistaAvisos>(() => (['por_atender', 'atendidos', 'resumen'].includes(tab.value) ? (tab.value as VistaAvisos) : 'por_atender'))
const { data, refresh, pending } = await useAsyncData('avisos', () => api.list(vistaAv.value), { watch: [vistaAv] })
watch(data, (d) => d && (conteo.value = d.conteo), { immediate: true })
const items = computed<Aviso[]>(() => data.value?.items ?? [])

// «Resumen del día»: shown = read (the sender sees it in the read receipts)
watch(
  [items, tab],
  async () => {
    if (tab.value !== 'resumen') return
    const ids = items.value.filter((a) => !a.leido_at).map((a) => a.id)
    if (ids.length) conteo.value = await api.leidos(ids)
  },
  { immediate: true },
)

async function changed(t: string) {
  say(t)
  await Promise.all([refresh(), refrescar()])
}

// ---------------------------------------------------------------- enviados (comunicados)
const { data: com, refresh: refreshCom } = await useAsyncData(
  'comunicados',
  () => (O.value?.puede_comunicar && tab.value === 'enviados' ? api.comunicados() : Promise.resolve([] as Comunicado[])),
  { watch: [tab] },
)
const cf = reactive({ titulo: '', cuerpo: '', audiencia: [] as string[], prioridad: 'normal', expira_el: '', err: '', busy: false })
const toggleAud = (k: string) => (cf.audiencia = cf.audiencia.includes(k) ? cf.audiencia.filter((x) => x !== k) : [...cf.audiencia, k])
async function enviar() {
  cf.err = ''
  cf.busy = true
  try {
    const c = await api.enviar({ titulo: cf.titulo, cuerpo: cf.cuerpo, audiencia: cf.audiencia, prioridad: cf.prioridad, expira_el: cf.expira_el || null })
    say(`Aviso enviado a ${c.total} persona${c.total === 1 ? '' : 's'} (${c.audiencia_txt}). ${c.prioridad === 'alta' ? 'Les llega a la campana.' : 'Lo ven en su «Resumen del día».'}`)
    Object.assign(cf, { titulo: '', cuerpo: '', audiencia: [], prioridad: 'normal', expira_el: '' })
    await refreshCom()
  } catch (e) {
    cf.err = apiErrorMessage(e)
  } finally {
    cf.busy = false
  }
}
const verLect = ref<string | null>(null)

const TABS = computed<[Tab, string][]>(() => {
  const c = conteo.value
  const t: [Tab, string][] = [
    ['por_atender', `Por atender (${c?.por_atender ?? 0})`],
    ['atendidos', 'Atendidos'],
    ['resumen', `Resumen del día${c?.resumen_sin_leer ? ` (${c.resumen_sin_leer})` : ''}`],
    ['agenda', `Mi agenda${c?.agenda_hoy ? ` (${c.agenda_hoy})` : ''}`],
  ]
  if (O.value?.puede_comunicar) t.push(['enviados', 'Avisos enviados'])
  return t
})
function goTab(t: Tab) {
  tab.value = t
  msg.value = null
}
</script>

<template>
  <PageBar
    :title="O?.gerencia ? 'Avisos y agenda' : 'Notificaciones'"
    :subtitle="O?.gerencia ? 'Lo que requiere tu atención y lo que agendaste para actuar' : 'Qué ocurrió, qué debes hacer y hasta cuándo · con botón para hacerlo directo'"
    back="/"
  >
    <div class="tabs">
      <button v-for="[k, l] in TABS" :key="k" type="button" class="tab" :class="{ on: tab === k }" @click="goTab(k)">{{ l }}</button>
    </div>
  </PageBar>

  <div class="cnt">
    <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.t }}</b></div>

    <!-- =================== Avisos =================== -->
    <template v-if="tab === 'por_atender' || tab === 'atendidos'">
      <AvisoCard v-for="a in items" :key="a.id" :a="a" @changed="changed" />
      <div v-if="!items.length" class="card mut small">
        {{ pending ? 'Cargando…' : tab === 'por_atender' ? 'No tienes nada por atender. Lo nuevo llega aquí con qué hacer y hasta cuándo.' : 'Todavía no hay avisos atendidos.' }}
      </div>
      <div v-if="tab === 'por_atender'" class="note">
        <template v-if="O?.gerencia">
          Regla: cada semana el sistema revisa el resultado de cada área de la empresa y avisa a Gerencia solo cuando una queda por debajo del 60% (rojo). Los
          resultados de cada persona los sigue Coordinación.
        </template>
        Aquí solo llega lo que pide una acción con límite. Lo informativo va al «Resumen del día». Ningún aviso se repite, y cuando lo pendiente se resuelve en su
        módulo, el aviso se cierra solo.
      </div>
    </template>

    <!-- =================== Resumen del día =================== -->
    <template v-if="tab === 'resumen'">
      <div class="card col">
        <div class="sb"><b>Resumen</b><span class="mut tiny">últimos 7 días · llega una vez al día</span></div>
        <div v-for="a in items" :key="a.id" class="res">
          <div class="row fw g8">
            <span class="chip" :class="a.nivel">{{ a.tipo_txt }}</span>
            <span class="mut tiny">{{ fmtCuando(a.created_at) }}{{ a.enviado_por ? ` · ${a.enviado_por}` : '' }}</span>
          </div>
          <b class="small">{{ a.titulo }}</b>
          <div v-if="a.detalle" class="mut small pre">{{ a.detalle }}</div>
          <NuxtLink v-if="a.link && a.accion_txt" :to="a.link" class="small">{{ a.accion_txt }} ›</NuxtLink>
        </div>
        <div v-if="!items.length" class="mut small">{{ pending ? 'Cargando…' : 'Nada informativo en los últimos 7 días.' }}</div>
        <div class="mut tiny">Son avisos informativos: no piden una acción con límite, por eso no suenan ni ocupan la campana.</div>
      </div>
    </template>

    <!-- =================== Mi agenda (G09 · G-089) =================== -->
    <AgendaView v-if="tab === 'agenda'" @changed="refresh" />

    <!-- =================== Avisos enviados (comunicados) =================== -->
    <template v-if="tab === 'enviados' && O?.puede_comunicar">
      <div class="card col focus">
        <b class="t17">Enviar un aviso</b>
        <div class="fld"><label for="c-t">Título <span class="req">*</span></label><input id="c-t" v-model="cf.titulo" class="in" maxlength="160" placeholder="Ej.: Reunión general el viernes"></div>
        <div class="fld"><label for="c-c">Mensaje <span class="req">*</span></label><textarea id="c-c" v-model="cf.cuerpo" class="in ta" maxlength="4000" /></div>
        <div class="fld">
          <span class="fld-label">Para <span class="req">*</span></span>
          <div class="row fw g8"><button v-for="(t, k) in O.audiencias" :key="k" type="button" class="opt" :class="{ on: cf.audiencia.includes(String(k)) }" @click="toggleAud(String(k))">{{ t }}</button></div>
        </div>
        <div class="g3">
          <div class="fld">
            <label for="c-p">Prioridad</label>
            <select id="c-p" v-model="cf.prioridad" class="in"><option value="normal">Normal · al «Resumen del día»</option><option value="alta">Alta · a la campana</option></select>
          </div>
          <div class="fld"><label for="c-e">Deja de mostrarse después del</label><input id="c-e" v-model="cf.expira_el" class="in" type="date" :min="localDate(0)"></div>
        </div>
        <div v-if="cf.err" class="note bad"><b>{{ cf.err }}</b></div>
        <div class="row fw g10">
          <button type="button" class="btn bp" :disabled="cf.busy" @click="enviar">Enviar aviso</button>
          <span class="mut tiny">{{ O.gerencia ? 'Gerencia envía a cualquier cargo.' : 'Coordinación envía a asesores y a Atención y Preventa.' }} Quien lo envía ve quién lo leyó.</span>
        </div>
      </div>
      <div class="card">
        <div class="lbl mb8">Avisos enviados{{ O.gerencia ? '' : ' por ti' }}</div>
        <div v-for="c in com ?? []" :key="c.id" class="env">
          <div class="sb fw g8">
            <span>
              <b class="small">{{ c.titulo }}</b>
              <span v-if="c.prioridad === 'alta'" class="chip warn ml6">Alta</span><br>
              <span class="mut tiny">{{ fmtCuando(c.created_at) }} · {{ c.creado_por }} · para {{ c.audiencia_txt }}{{ c.expira_el ? ` · hasta el ${fmtFecha(c.expira_el)}` : '' }}</span>
            </span>
            <button type="button" class="chip chipbtn" :class="c.leidos === c.total ? 'ok' : 'gray'" @click="verLect = verLect === c.id ? null : c.id">Leído por {{ c.leidos }} de {{ c.total }} ›</button>
          </div>
          <div class="mut small pre">{{ c.cuerpo }}</div>
          <div v-if="verLect === c.id" class="lect">
            <span v-for="l in c.lecturas" :key="l.nombre" class="tiny">{{ l.leido_at ? '✓' : '·' }} {{ l.nombre }}{{ l.leido_at ? ` · ${fmtCuando(l.leido_at)}` : ' · sin leer' }}</span>
          </div>
        </div>
        <div v-if="!(com ?? []).length" class="mut small">Todavía no has enviado avisos.</div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.col {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.fw {
  flex-wrap: wrap;
}
.gp4 {
  gap: 4px;
}
.gp6 {
  gap: 6px;
}
.g8 {
  gap: 8px;
}
.g10 {
  gap: 10px;
  align-items: center;
}
.mb8 {
  margin-bottom: 8px;
}
.ml6 {
  margin-left: 6px;
}
.t17 {
  font-size: 17px;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.pre {
  white-space: pre-line;
}
.res,
.env {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.chipbtn {
  border: 0;
  cursor: pointer;
  font: inherit;
  font-size: 11.5px;
  font-weight: 700;
}
.lect {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  padding: 4px 0;
}
</style>
