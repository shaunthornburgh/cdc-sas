<script setup lang="ts">
import type { PlOpciones, PlataformaRow } from '~/types/plataformas'

/**
 * K15 «Actualización de plataformas» (Coordinación, and the Auxiliar for the portals assigned to
 * her) and K15-ger «Plataformas tradicionales» (Gerencia: Actualizaciones, Resultados de los
 * portales, Histórico y descarga).
 */
definePageMeta({ cargos: ['gerencia', 'coordinacion', 'auxiliar_administrativa'] })
useHead({ title: 'Actualización de plataformas · Casa Dolce Casa' })

const api = usePlataformas()
const { data: opc, refresh: refreshOpc } = await useAsyncData('pl-opciones', () => api.opciones())
const O = computed(() => opc.value as PlOpciones)
const ger = computed(() => !!O.value?.gerencia)

const msg = ref<{ t: string; ok: boolean } | null>(null)
const say = (t: string, ok = true) => (msg.value = { t, ok })

// ---- filters (K15-ger)
type Vista = 'act' | 'res' | 'dl'
const vista = ref<Vista>('act')
const TABS: [Vista, string][] = [['act', 'Actualizaciones'], ['res', 'Resultados de los portales'], ['dl', 'Histórico y descarga']]
const rg = reactive({ desde: O.value?.desde ?? localDate(-60), hasta: O.value?.hasta ?? localDate(0) })
const rgErr = computed(() => !rg.desde || !rg.hasta || rg.desde > rg.hasta)
const f = reactive({ plataforma_id: '', quien_id: '' })
const rango = computed(() => (rgErr.value ? { desde: O.value?.desde, hasta: O.value?.hasta } : { desde: rg.desde, hasta: rg.hasta }))
const query = computed(() =>
  ger.value
    ? { ...rango.value, plataforma_id: f.plataforma_id || undefined, quien_id: f.quien_id || undefined }
    : {},
)
const rangoT = computed(() => (rango.value.desde && rango.value.hasta ? `${fmtFecha(rango.value.desde)} al ${fmtFecha(rango.value.hasta)}` : ''))

const { data: t, refresh } = await useAsyncData('pl-tablero', () => api.tablero(query.value), { watch: [query] })
const resQuery = computed(() => ({ ...rango.value, plataforma_id: f.plataforma_id || undefined }))
const { data: res, refresh: refreshRes } = await useAsyncData(
  'pl-resultados',
  () => (ger.value && vista.value === 'res' ? api.resultados(resQuery.value) : Promise.resolve(null)),
  { watch: [resQuery, vista] },
)
const { data: hist } = await useAsyncData(
  'pl-historico',
  () => (ger.value && vista.value === 'dl' ? api.historico(query.value) : Promise.resolve(null)),
  { watch: [query, vista] },
)

const activas = computed(() => (t.value?.plataformas ?? []).filter((p) => p.activa))
const disp = (total: number | null, usado: number | null) => (total == null || usado == null ? '—' : `${total - usado} de ${total}`)

// ---------------------------------------------------------------- K15 (Coordinación / Auxiliar)
const abierta = ref<string | null>(null)
async function guardado(p: PlataformaRow) {
  abierta.value = null
  say(`${p.nombre} actualizada hoy. Cuenta en «Actualización de plataformas» del rendimiento de quien la tiene asignada.`)
  await Promise.all([refresh(), refreshOpc()])
}
const aTiempoD = computed(() => {
  const k = t.value?.kpis
  if (!k) return ''
  return k.atrasadas.length ? `${k.atrasadas.join(', ')} ${k.atrasadas.length === 1 ? 'está atrasada' : 'están atrasadas'}` : 'todas al día'
})

async function descargar() {
  try {
    await api.descargar(ger.value ? (query.value as Record<string, string>) : { desde: O.value.desde, hasta: O.value.hasta })
    say('Histórico descargado (CSV, se abre en Excel). La descarga queda en el registro de cambios.')
  } catch (e) {
    say(apiErrorMessage(e), false)
  }
}

// ---------------------------------------------------------------- K15-ger «Actualizaciones»
const KPIS = computed(() => {
  const k = t.value?.kpis
  if (!k) return []
  return [
    { t: 'Al día hoy', v: `${k.al_dia} de ${k.total}`, d: k.atrasadas.length ? `atrasada: ${k.atrasadas.join(', ')}` : 'todas al día', bad: k.atrasadas.length > 0 },
    { t: 'Actualizaciones en el rango', v: String(k.actualizaciones), d: 'registradas', bad: false },
    { t: 'A tiempo', v: k.a_tiempo_pct === null ? '—' : `${k.a_tiempo_pct}%`, d: `${k.a_tiempo} de ${k.actualizaciones}`, bad: false },
    { t: 'Hechas por el responsable', v: k.del_responsable_pct === null ? '—' : `${k.del_responsable_pct}%`, d: 'las demás las hizo otra persona', bad: false },
  ]
})
async function asignar(p: PlataformaRow, ev: Event) {
  const v = (ev.target as HTMLSelectElement).value
  try {
    const r = await api.responsable(p.id, v || null)
    say(`${p.nombre}: responsable asignado ${r.responsable?.full_name ?? 'nadie'}. Queda en el registro de cambios.`)
    await refresh()
  } catch (e) {
    say(apiErrorMessage(e), false)
    await refresh()
  }
}
const regla = ref<string>('')
watch(t, (v) => v && !regla.value && (regla.value = String(v.dias_regla)), { immediate: true })
async function guardarRegla() {
  try {
    await api.regla(Number(regla.value))
    say(`Regla guardada: cada plataforma se debe actualizar al menos cada ${regla.value} días. Queda en el registro de cambios.`)
    await refresh()
  } catch (e) {
    say(apiErrorMessage(e), false)
  }
}
const nVer = ref(8)
watch(query, () => (nVer.value = 8))
const log = computed(() => t.value?.actualizaciones ?? [])
const verMas = () => (nVer.value = nVer.value < log.value.length ? nVer.value + 20 : 8)
const fDia = (iso: string) => `${diaMes(iso)} ${new Date(iso).getFullYear()} ${fmtHora(iso)}`

// ---------------------------------------------------------------- K15-ger «Resultados»
const KPIR = computed(() => {
  const k = res.value?.kpis
  if (!k) return []
  return [
    { t: 'Leads', v: String(k.leads), d: 'de los portales filtrados' },
    { t: 'Cierres', v: String(k.cierres), d: k.conversion === null ? '—' : `${String(k.conversion).replace('.', ',')}% de los leads` },
    { t: 'Costo del rango', v: fmtCOP(k.costo), d: 'precio de los planes' },
    { t: 'Costo por lead', v: fmtCOP(k.costo_lead), d: k.costo_cierre ? `costo por cierre ${fmtCOP(k.costo_cierre)}` : 'sin cierres' },
  ]
})
const planAbierto = ref<string | null>(null)
const planDe = (id: string) => (t.value?.plataformas ?? []).find((p) => p.id === id)
async function planGuardado(m: string) {
  planAbierto.value = null
  say(m)
  await Promise.all([refresh(), refreshRes(), refreshOpc()])
}
const inactivas = computed(() => (t.value?.plataformas ?? []).filter((p) => !p.activa))
</script>

<template>
  <PageBar
    :title="ger ? 'Plataformas tradicionales' : 'Actualización de plataformas'"
    subtitle="Plataformas tradicionales: cupo, destacados, última actualización y quién la hizo · resultados de cada portal · cuenta en el rendimiento de quien la tiene asignada"
    :back="ger || O?.puede_descargar ? '/coordinacion' : '/'"
  >
    <button v-if="!ger && O?.puede_descargar" type="button" class="btn bs" @click="descargar">Descargar (Excel)</button>
  </PageBar>

  <div class="cnt">
    <!-- =================== K15-ger =================== -->
    <template v-if="ger">
      <div class="tabs self-start">
        <button v-for="[k, l] in TABS" :key="k" type="button" class="tab" :class="{ on: vista === k }" @click="vista = k; msg = null">{{ l }}</button>
      </div>
      <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.t }}</b></div>
      <div class="card filtros">
        <div class="fld"><label for="pl-d1">Desde</label><input id="pl-d1" v-model="rg.desde" class="in dt" type="date"></div>
        <div class="fld"><label for="pl-d2">Hasta</label><input id="pl-d2" v-model="rg.hasta" class="in dt" type="date"></div>
        <div class="fld">
          <label for="pl-p">Plataforma</label>
          <select id="pl-p" v-model="f.plataforma_id" class="sel"><option value="">Todas</option><option v-for="p in O.plataformas" :key="p.id" :value="p.id">{{ p.nombre }}{{ p.activa ? '' : ' (inactiva)' }}</option></select>
        </div>
        <div v-if="vista !== 'res'" class="fld">
          <label for="pl-q">Quién actualizó</label>
          <select id="pl-q" v-model="f.quien_id" class="sel"><option value="">Todos</option><option v-for="q in O.quienes" :key="q.id" :value="q.id">{{ q.full_name }}</option></select>
        </div>
        <span class="mut rng">{{ rangoT }}</span>
      </div>
      <div v-if="rgErr" class="note bad"><b>La fecha «Desde» no puede ser posterior a «Hasta». Se muestran los últimos tres meses mientras lo corriges.</b></div>

      <!-- Actualizaciones -->
      <template v-if="vista === 'act' && t">
        <div class="g4">
          <div v-for="k in KPIS" :key="k.t" class="card" :class="{ kbad: k.bad }"><div class="lbl">{{ k.t }}</div><div class="kn num">{{ k.v }}</div><div class="mut tiny">{{ k.d }}</div></div>
        </div>
        <div class="card">
          <div class="lbl mb8">Última actualización de cada plataforma</div>
          <div class="wrap">
            <div class="min760">
              <div class="gu hd"><span>Plataforma</span><span>Responsable asignado</span><span>Última actualización</span><span>Quién la hizo</span><span>Estado</span></div>
              <div v-for="p in t.plataformas" :key="p.id" class="gu rw" :class="{ off: !p.activa }">
                <b>{{ p.nombre }}</b>
                <select class="sel ssm" :value="p.responsable?.id ?? ''" :aria-label="`Responsable asignado de ${p.nombre}`" :disabled="!p.activa" @change="asignar(p, $event)">
                  <option value="">Sin asignar</option>
                  <option v-for="r in O.responsables" :key="r.id" :value="r.id">{{ r.full_name }} ({{ CARGO_LABELS[r.cargo] }})</option>
                </select>
                <span>{{ p.ultima_at ? fDia(p.ultima_at) : 'Nunca' }}</span>
                <span>{{ p.ultima_por ? firstName(p.ultima_por) : '—' }}</span>
                <span><span v-if="p.activa" class="chip" :class="p.estado_cls">{{ p.estado_txt }}</span><button v-else type="button" class="btn bs xs" @click="vista = 'res'; planAbierto = p.id">Inactiva · activar</button></span>
              </div>
            </div>
          </div>
          <div class="mut tiny mt8 regla">
            Gerencia asigna el responsable de cada plataforma. Regla: se debe actualizar al menos cada
            <input v-model="regla" class="in rin" inputmode="numeric" aria-label="Días de la regla"> días
            <button type="button" class="btn bs xs" :disabled="regla === String(t.dias_regla)" @click="guardarRegla">Guardar</button>
            <span v-if="!t.regla_confirmada" class="chip pend">valor de ejemplo · PENDIENTE DE CONFIGURACIÓN</span>.
            Si se pasa, queda «Atrasada» y cuenta en el rendimiento de quien la tiene asignada.
          </div>
        </div>
        <div class="card">
          <div class="sb mb8"><span class="lbl">Actualizaciones en el rango · {{ log.length }} {{ log.length === 1 ? 'actualización' : 'actualizaciones' }}</span><span class="mut tiny">las más recientes primero</span></div>
          <div class="wrap">
            <div class="min620">
              <div v-for="a in log.slice(0, nVer)" :key="a.id" class="gl">
                <span class="num">{{ fDia(a.realizada_at) }}</span>
                <b>{{ a.plataforma }}</b>
                <span>{{ a.actualizado_por ? firstName(a.actualizado_por) : '—' }}{{ a.responsable && !a.es_responsable ? ' (no es el responsable)' : '' }}</span>
                <span><span class="chip" :class="a.a_tiempo ? 'ok' : 'warn'">{{ a.a_tiempo ? 'A tiempo' : `Tarde (más de ${a.regla_dias} días)` }}</span></span>
              </div>
              <div v-if="!log.length" class="mut empty">No hay actualizaciones en este rango.</div>
            </div>
          </div>
          <div class="sb mt8 small">
            <span class="mut">Mostrando {{ Math.min(nVer, log.length) }} de {{ log.length }}</span>
            <button v-if="log.length > 8" type="button" class="btn bs sm" @click="verMas">{{ nVer < log.length ? 'Ver más' : 'Ver menos' }}</button>
          </div>
        </div>
      </template>

      <!-- Resultados de los portales -->
      <template v-if="vista === 'res' && res">
        <div class="g4">
          <div v-for="k in KPIR" :key="k.t" class="card"><div class="lbl">{{ k.t }}</div><div class="kn num k32">{{ k.v }}</div><div class="mut tiny">{{ k.d }}</div></div>
        </div>
        <div class="card">
          <div class="lbl mb8">Resultados por portal en el rango</div>
          <div class="wrap">
            <div class="min960">
              <div class="gres hd"><span>Portal</span><span>Leads</span><span>Citas</span><span>Cierres</span><span>Costo</span><span>Costo por lead</span><span>Costo por cierre</span><span>Conversión</span><span>Plan</span></div>
              <template v-for="r in res.filas" :key="r.plataforma_id">
                <div class="gres rw" :class="{ warnbg: r.plan_estado === 'por_vencer' }">
                  <b class="pn"><span class="sw" :style="{ background: r.color }" />{{ r.nombre }}</b>
                  <span class="num">{{ r.leads }}</span>
                  <span class="num">{{ r.citas }}</span>
                  <span class="num">{{ r.cierres }}</span>
                  <span class="num">{{ fmtCOP(r.costo) }}</span>
                  <span class="num">{{ fmtCOP(r.costo_lead) }}</span>
                  <span class="num">{{ fmtCOP(r.costo_cierre) }}</span>
                  <span class="num">{{ r.conversion === null ? '—' : `${String(r.conversion).replace('.', ',')}%` }}</span>
                  <span><button type="button" class="chip chipbtn" :class="r.plan_cls" :aria-expanded="planAbierto === r.plataforma_id" @click="planAbierto = planAbierto === r.plataforma_id ? null : r.plataforma_id">{{ r.plan_txt }} ✎</button></span>
                </div>
                <PlPlanForm v-if="planAbierto === r.plataforma_id && planDe(r.plataforma_id)" :p="planDe(r.plataforma_id)!" @saved="planGuardado" @cancel="planAbierto = null" />
              </template>
              <template v-for="p in inactivas" :key="p.id">
                <div class="gres rw off">
                  <b class="pn"><span class="sw" :style="{ background: p.color }" />{{ p.nombre }}</b>
                  <span class="mut span7">Inactiva: no se actualiza ni cuenta en los resultados.</span>
                  <span><button type="button" class="chip gray chipbtn" @click="planAbierto = planAbierto === p.id ? null : p.id">Activar o registrar plan ✎</button></span>
                </div>
                <PlPlanForm v-if="planAbierto === p.id" :p="p" @saved="planGuardado" @cancel="planAbierto = null" />
              </template>
            </div>
          </div>
          <div class="mut tiny mt8">
            Leads, citas y cierres salen solos de los leads que entraron por cada portal. El costo es el precio de cada plan repartido en sus días, contado para los
            días del rango hasta hoy. Toca el plan para registrar una renovación o corregirlo.
          </div>
        </div>
        <div class="card">
          <div class="lbl mb8">Leads por mes y portal</div>
          <PlLeadsChart :r="res" />
        </div>
      </template>

      <!-- Histórico y descarga -->
      <template v-if="vista === 'dl' && hist">
        <div class="card dlcard">
          <div class="sb fw g8">
            <div>
              <div class="lbl">Histórico completo de plataformas</div>
              <div class="mut small">Con las fechas, la plataforma y la persona elegidas arriba · {{ hist.total }} {{ hist.total === 1 ? 'actualización' : 'actualizaciones' }} · una fila por actualización</div>
            </div>
            <div class="row g8">
              <select class="sel" aria-label="Formato"><option>Excel (CSV)</option></select>
              <button type="button" class="btn bp" :disabled="!hist.total" @click="descargar">Descargar histórico</button>
            </div>
          </div>
          <div class="lbl">Vista previa (primeras 5 filas)</div>
          <div class="wrap">
            <div class="hgrid hd"><span v-for="c in hist.columnas" :key="c">{{ c }}</span></div>
            <div v-for="(r, i) in hist.filas" :key="i" class="hgrid hr"><span v-for="(x, j) in r" :key="j" class="num">{{ x }}</span></div>
            <div v-if="!hist.filas.length" class="mut empty">No hay actualizaciones en este rango.</div>
          </div>
          <div class="note">
            El archivo trae cada actualización con: fecha y hora, plataforma, responsable asignado, quién actualizó, cupo total, utilizado y disponible, destacados
            (total, usados y disponibles), precio del plan, activación, vencimiento, alarma, si estaba activa, leads, citas y cierres del mes, costo por lead, costo
            por cierre, a tiempo o tarde y observación. La descarga queda en el registro de cambios.
          </div>
        </div>
      </template>
    </template>

    <!-- =================== K15 (Coordinación / Auxiliar) =================== -->
    <template v-else-if="t">
      <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.t }}</b></div>
      <div class="g3">
        <div class="card"><div class="lbl">Actualizaciones a tiempo · {{ t.mes_txt }}</div><div class="kn num">{{ t.kpis.al_dia }} de {{ t.kpis.total }}</div><div class="mut tiny">{{ aTiempoD }}</div></div>
        <div class="card"><div class="lbl">Cupo disponible total</div><div class="kn num">{{ t.cupo_disponible }}</div><div class="mut tiny">publicaciones que aún se pueden subir</div></div>
        <div class="card"><div class="lbl">Destacados disponibles</div><div class="kn num">{{ t.destacados_disponibles }}</div><div class="mut tiny">entre todas las plataformas</div></div>
      </div>
      <div class="card">
        <div class="wrap">
          <div class="min880">
            <div class="gk hd"><span>Plataforma</span><span>Cupo disponible</span><span>Destacados</span><span>Última actualización</span><span>Estado</span><span>Acción</span></div>
            <template v-for="p in activas" :key="p.id">
              <div class="gk rw">
                <b>{{ p.nombre }}<br><span class="mut tiny nb">{{ p.responsable ? `Responsable: ${firstName(p.responsable.full_name)}` : 'Sin responsable' }}</span></b>
                <span class="num">{{ disp(p.cupo_total, p.cupo_usado) }}</span>
                <span class="num">{{ disp(p.destacados_total, p.destacados_usados) }}</span>
                <span>{{ p.ultima_txt }}{{ p.ultima_por && p.ultima_txt.startsWith('Hoy') ? ` · ${firstName(p.ultima_por)}` : '' }}</span>
                <span><span class="chip" :class="p.estado_cls">{{ p.estado_txt }}</span></span>
                <span>
                  <button v-if="p.puede_registrar" type="button" :class="abierta === p.id ? 'opt on' : 'btn bs'" class="h36" @click="abierta = abierta === p.id ? null : p.id; msg = null">Registrar actualización</button>
                  <span v-else class="mut tiny">La registra {{ p.responsable ? firstName(p.responsable.full_name) : 'Coordinación' }}</span>
                </span>
              </div>
              <PlActualizacionForm v-if="abierta === p.id" :p="p" @saved="guardado(p)" @cancel="abierta = null" />
            </template>
            <div v-if="!activas.length" class="mut empty">No hay plataformas activas. Gerencia las activa en «Plataformas tradicionales».</div>
          </div>
        </div>
        <div class="row fw g8 mt10">
          <span class="chip pend wrapchip">
            Se debe actualizar al menos cada {{ t.dias_regla }} días{{ t.regla_confirmada ? '' : ' (valor de ejemplo, PENDIENTE DE CONFIGURACIÓN)' }} · cupos y planes los registra Gerencia
          </span>
          <span class="mut tiny">El sistema guarda fecha y hora de cada actualización y quién la hizo.</span>
        </div>
      </div>
      <div class="note">«Actualización de plataformas» es una de las áreas del rendimiento del Coordinador; su peso lo define Gerencia.</div>
    </template>
  </div>
</template>

<style scoped>
.self-start {
  align-self: flex-start;
}
.filtros {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
  background: var(--cdc-bg);
}
.dt {
  min-height: 38px;
}
.rng {
  font-size: 12.5px;
  margin-left: auto;
}
.tiny {
  font-size: 12px;
}
.small {
  font-size: 12.5px;
}
.mb8 {
  margin-bottom: 8px;
}
.mt8 {
  margin-top: 8px;
}
.mt10 {
  margin-top: 10px;
}
.fw {
  flex-wrap: wrap;
}
.g6 {
  gap: 6px;
}
.g8 {
  gap: 8px;
}
.k32 {
  font-size: 32px;
}
.kbad {
  background: #fff5f3;
  border-color: #e8b4ac;
}
.wrap {
  overflow-x: auto;
}
.min620 {
  min-width: 620px;
}
.min760 {
  min-width: 760px;
}
.min880 {
  min-width: 880px;
}
.min960 {
  min-width: 960px;
}
.gu,
.gl,
.gk,
.gres {
  display: grid;
  gap: 10px;
  padding: 10px 6px;
  font-size: 13px;
  align-items: center;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.gu {
  grid-template-columns: minmax(140px, 1fr) 290px 170px 130px 130px;
}
.pn {
  display: flex;
  align-items: center;
  gap: 6px;
}
.gl {
  grid-template-columns: 150px minmax(120px, 1fr) 210px 170px;
  padding: 8px 6px;
}
.gk {
  grid-template-columns: minmax(150px, 1.2fr) 120px 110px 160px 110px 200px;
}
.gres {
  grid-template-columns: minmax(120px, 1fr) 56px 56px 60px 100px 104px 116px 84px 215px;
  gap: 8px;
}
.span7 {
  grid-column: span 7;
}
.hd {
  padding: 8px 6px;
  border-bottom: 1px solid var(--cdc-border);
  font-size: 10.5px;
  color: var(--cdc-muted);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.rw.off {
  opacity: 0.65;
}
.warnbg {
  background: #fffbf1;
}
.ssm {
  min-height: 34px;
  font-size: 12.5px;
}
.xs {
  min-height: 28px;
  padding: 0 10px;
  font-size: 12px;
}
.h36 {
  min-height: 36px;
}
.rin {
  display: inline-block;
  width: 56px;
  min-height: 28px;
  padding: 0 6px;
  font-size: 12px;
  text-align: center;
}
.regla {
  line-height: 2.2;
}
.chipbtn {
  border: 0;
  cursor: pointer;
  font: inherit;
  font-size: 11.5px;
  font-weight: 700;
}
.sw {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 3px;
  flex: none;
}
.nb {
  font-weight: 500;
}
.wrapchip {
  white-space: normal;
}
.empty {
  padding: 14px 6px;
  font-size: 13px;
}
.dlcard {
  display: flex;
  flex-direction: column;
  gap: 12px;
  border: 2px solid var(--cdc-green);
}
.hgrid {
  display: grid;
  grid-template-columns: 140px 110px 120px 120px repeat(6, 76px) 100px 90px 90px 96px 60px 70px 70px 70px 96px 104px 70px 170px;
  gap: 6px;
  min-width: 2300px;
}
.hgrid.hd {
  font-size: 10px;
  padding: 6px 4px;
}
.hr {
  font-size: 12px;
  padding: 7px 4px;
  border-bottom: 1px solid var(--cdc-border-soft);
  align-items: center;
}
</style>
