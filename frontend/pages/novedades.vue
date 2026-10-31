<script setup lang="ts">
import type { Novedad, NovedadOpciones, TipoNovedad } from '~/types/novedades'

/**
 * K13 «Ausencias y permisos»: incapacidades and permisos of the staff (they discount in
 * «Salarios del mes»), and the novedades reported in the preoperacional.
 * Coordinación and the Auxiliar register; Gerencia sees.
 */
definePageMeta({ cargos: ['gerencia', 'coordinacion', 'auxiliar_administrativa'] })
useHead({ title: 'Ausencias y permisos · Casa Dolce Casa' })

const auth = useAuth()
const api = useNovedades()
const me = computed(() => auth.user.value!)
const ger = computed(() => me.value.cargo === 'gerencia')
const aux = computed(() => me.value.cargo === 'auxiliar_administrativa')

const { data: opc } = await useAsyncData('nov-opciones', () => api.opciones())
const O = computed(() => opc.value as NovedadOpciones)
const TIPOS = computed(() => Object.keys(O.value?.tipos ?? {}) as TipoNovedad[])

// ---- range (K13 «Desde / Hasta», this month by default) and filters
const tab = ref<'a' | 'p'>('a')
const rg = reactive({ desde: O.value?.desde ?? localDate(0), hasta: O.value?.hasta ?? localDate(0) })
const rgErr = computed(() => !rg.desde || !rg.hasta || rg.desde > rg.hasta)
const f = reactive({ tipo: '', empleado_id: '', anuladas: false })
const rango = computed(() => (rgErr.value ? { desde: O.value?.desde, hasta: O.value?.hasta } : { desde: rg.desde, hasta: rg.hasta }))
const query = computed(() => ({
  ...rango.value,
  tipo: f.tipo || undefined,
  empleado_id: f.empleado_id || undefined,
  anuladas: f.anuladas || undefined,
}))
const { data, refresh, pending } = await useAsyncData('novedades', () => api.list(query.value), { watch: [query] })
const { data: pre, refresh: refreshPre } = await useAsyncData('nov-preop', () => api.preoperacional(rango.value), { watch: [rango] })
const rgT = computed(() => (rango.value.desde && rango.value.hasta ? `${fmtFecha(rango.value.desde)} al ${fmtFecha(rango.value.hasta)}` : ''))
const RES = computed(() =>
  TIPOS.value.map((t) => ({
    t: t === 'incapacidad' ? 'Días de incapacidad' : t === 'permiso_no_remunerado' ? 'Días de permiso no remunerado' : 'Días de permiso remunerado',
    v: data.value?.dias[t] ?? 0,
  })),
)
const empleadosFiltro = computed(() => {
  const m = new Map<string, string>()
  for (const e of O.value?.empleados ?? []) m.set(e.id, e.full_name)
  for (const n of data.value?.items ?? []) m.set(n.empleado.id, n.empleado.full_name)
  return [...m].sort((a, b) => a[1].localeCompare(b[1]))
})
const hayFiltros = computed(() => !!(f.tipo || f.empleado_id || f.anuladas))

// ---- messages
const msg = ref<{ t: string; ok: boolean; avisos?: string[] } | null>(null)

// ---- «Registrar novedad» (K13 form)
const form = reactive({ on: false, tipo: 'incapacidad' as TipoNovedad, empleado_id: '', desde: localDate(0), hasta: localDate(0), soportes: 0, observacion: '', err: '', busy: false })
function abrir() {
  Object.assign(form, { on: !form.on, tipo: 'incapacidad', empleado_id: '', desde: localDate(0), hasta: localDate(0), soportes: 0, observacion: '', err: '' })
  msg.value = null
}
const diasForm = computed(() => {
  if (!form.desde || !form.hasta || form.hasta < form.desde) return 0
  return diasHasta(form.hasta) - diasHasta(form.desde) + 1
})
const descuenta = computed(() => O.value?.descontables.includes(form.tipo))
async function guardar() {
  form.err = ''
  if (!form.empleado_id || !form.desde || !form.hasta) return (form.err = 'Completa el empleado y las fechas.')
  if (form.hasta < form.desde) return (form.err = 'La fecha «Hasta» no puede ser anterior a «Desde».')
  form.busy = true
  try {
    const r = await api.create({
      empleado_id: form.empleado_id,
      tipo: form.tipo,
      desde: form.desde,
      hasta: form.hasta,
      soportes: form.soportes,
      observacion: form.observacion || null,
    })
    const n = r.novedad
    form.on = false
    msg.value = {
      t: `${n.code}: ${n.tipo_txt.toLowerCase()} de ${n.empleado.full_name}, ${n.fechas_txt} (${n.dias} día${n.dias === 1 ? '' : 's'}). ${n.descuenta ? 'El salario del corte se recalculó solo.' : 'Queda contada; no se descuenta.'} Gerencia la ve en esta página.`,
      ok: true,
      avisos: r.avisos,
    }
    await refresh()
  } catch (e) {
    form.err = apiErrorMessage(e)
  } finally {
    form.busy = false
  }
}

// ---- row detail: note / attachments / annul
const open = ref<string | null>(null)
const det = reactive({ observacion: '', motivo: '', anulando: false, busy: false })
function toggle(n: Novedad) {
  open.value = open.value === n.id ? null : n.id
  Object.assign(det, { observacion: n.observacion ?? '', motivo: '', anulando: false })
}
async function run(fn: () => Promise<unknown>) {
  det.busy = true
  try {
    await fn()
    await refresh()
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  } finally {
    det.busy = false
  }
}
const guardarObs = (n: Novedad) => run(async () => {
  await api.update(n.id, { observacion: det.observacion })
  msg.value = { t: `${n.code}: observación guardada.`, ok: true }
})
const adjuntar = (n: Novedad) => run(async () => {
  await api.update(n.id, { soportes: n.soportes + 1 })
  msg.value = { t: `${n.code}: soporte adjuntado.`, ok: true }
})
const anular = (n: Novedad) => run(async () => {
  const r = await api.anular(n.id, det.motivo)
  open.value = null
  msg.value = { t: `${n.code} anulada. ${n.descuenta ? 'El salario del corte se recalculó.' : ''}`, ok: true, avisos: r.avisos }
})

// ---- «Del preoperacional»
const notaRev = reactive<Record<string, string>>({})
const sinRevisar = computed(() => (pre.value ?? []).filter((x) => !x.revisado).length)
async function revisar(id: string) {
  try {
    await api.revisar(id, notaRev[id] || null)
    msg.value = { t: 'Novedad del preoperacional marcada como revisada.', ok: true }
    await Promise.all([refreshPre(), refresh()])
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  }
}
const fmtCel = (iso: string) => fmtCuando(iso)
</script>

<template>
  <PageBar title="Ausencias y permisos" subtitle="Incapacidades y permisos · y lo que el personal reportó en el preoperacional" :back="aux ? '/' : '/coordinacion'">
    <NuxtLink v-if="ger || aux" class="btn bs" to="/salarios">‹ Salarios del mes</NuxtLink>
    <NuxtLink v-else class="btn bs" to="/preoperacionales">‹ Preoperacionales</NuxtLink>
    <button v-if="O?.puede_registrar && tab === 'a'" type="button" class="btn bp" @click="abrir">{{ form.on ? 'Cancelar' : '+ Registrar ausencia o permiso' }}</button>
  </PageBar>

  <div class="cnt">
    <div v-if="rgErr" class="note bad"><b>La fecha «Desde» no puede ser posterior a «Hasta». Se muestra el mes actual mientras lo corriges.</b></div>

    <div class="tabs self-start">
      <button type="button" class="tab" :class="{ on: tab === 'a' }" @click="tab = 'a'">Incapacidades y permisos</button>
      <button type="button" class="tab" :class="{ on: tab === 'p' }" @click="tab = 'p'; form.on = false">Del preoperacional ({{ data?.preop_sin_revisar ?? sinRevisar }} por revisar)</button>
    </div>

    <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status">
      <b>{{ msg.t }}</b>
      <div v-for="a in msg.avisos ?? []" :key="a" class="aviso">⚠ {{ a }}</div>
    </div>

    <!-- =================== Incapacidades y permisos =================== -->
    <template v-if="tab === 'a'">
      <div v-if="form.on" class="card focus stack">
        <b class="t17">Registrar novedad</b>
        <div class="fld">
          <span class="fld-label">Tipo <span class="req">*</span></span>
          <div class="row fw">
            <button v-for="t in TIPOS" :key="t" type="button" class="opt" :class="{ on: form.tipo === t }" @click="form.tipo = t">{{ O.tipos[t] }}</button>
          </div>
        </div>
        <div class="g4">
          <div class="fld">
            <label for="n1">Empleado <span class="req">*</span></label>
            <select id="n1" v-model="form.empleado_id" class="in">
              <option value="" disabled>Elige el empleado</option>
              <option v-for="e in O.empleados" :key="e.id" :value="e.id">{{ e.full_name }} · {{ CARGO_LABELS[e.cargo] }}</option>
            </select>
          </div>
          <div class="fld"><label for="n2">Desde <span class="req">*</span></label><input id="n2" v-model="form.desde" class="in" type="date"></div>
          <div class="fld"><label for="n3">Hasta <span class="req">*</span></label><input id="n3" v-model="form.hasta" class="in" type="date" :min="form.desde"></div>
          <div class="fld">
            <span class="fld-label">Soporte</span>
            <button type="button" class="btn bs" @click="form.soportes++">{{ form.soportes ? `✓ ${form.soportes} archivo${form.soportes === 1 ? '' : 's'}` : 'Adjuntar soporte' }}</button>
          </div>
        </div>
        <div class="fld"><label for="n4">Observación</label><input id="n4" v-model="form.observacion" class="in" placeholder="Motivo o detalle"></div>
        <div class="note">
          {{ O.ayudas[form.tipo] }} El sistema cuenta los días solo{{ diasForm ? ` (${diasForm} día${diasForm === 1 ? '' : 's'})` : '' }}{{ descuenta ? ', los descuenta en «Salarios del mes»' : '' }} y Gerencia la ve en esta página.
        </div>
        <div v-if="form.err" class="note bad"><b>{{ form.err }}</b></div>
        <div class="row">
          <button type="button" class="btn bp" :disabled="form.busy" @click="guardar">Registrar novedad</button>
          <button type="button" class="btn bs" @click="form.on = false">Cancelar</button>
        </div>
      </div>

      <div class="g3">
        <div v-for="r in RES" :key="r.t" class="card"><div class="lbl">{{ r.t }}</div><div class="kn num">{{ r.v }}</div></div>
      </div>

      <div class="card">
        <div class="sb mb6">
          <span class="lbl">{{ rgT }}</span>
          <div class="row fw gap8">
            <label class="row gap6 flt">Desde<input v-model="rg.desde" class="in dt" type="date" aria-label="Fecha desde"></label>
            <label class="row gap6 flt">Hasta<input v-model="rg.hasta" class="in dt" type="date" aria-label="Fecha hasta"></label>
          </div>
        </div>
        <div class="row fw gap6 mb6">
          <button type="button" class="fch" :class="{ on: !f.tipo }" @click="f.tipo = ''">Todos</button>
          <button v-for="t in TIPOS" :key="t" type="button" class="fch" :class="{ on: f.tipo === t }" @click="f.tipo = t">{{ O.tipos[t] }}</button>
          <select v-model="f.empleado_id" class="fsel" aria-label="Empleado">
            <option value="">Todos los empleados</option>
            <option v-for="[id, n] in empleadosFiltro" :key="id" :value="id">{{ n }}</option>
          </select>
          <button type="button" class="fch" :class="{ on: f.anuladas }" @click="f.anuladas = !f.anuladas">Ver anuladas</button>
          <button v-if="hayFiltros" type="button" class="fch" @click="Object.assign(f, { tipo: '', empleado_id: '', anuladas: false })">✕ Quitar filtros</button>
        </div>

        <div class="wrap">
          <div class="tbl-min">
            <div class="grid hd"><span>Empleado</span><span>Tipo</span><span>Fechas</span><span>Días</span><span>Observación</span><span>Registro</span></div>
            <template v-for="n in data?.items ?? []" :key="n.id">
              <button type="button" class="grid rw" :class="{ anul: n.estado === 'anulada', sel: open === n.id }" :aria-expanded="open === n.id" @click="toggle(n)">
                <b>{{ n.empleado.full_name }}</b>
                <span><span class="chip" :class="n.estado === 'anulada' ? 'gray' : NOV_CLS[n.tipo]">{{ n.tipo_txt }}</span></span>
                <span>{{ n.fechas_txt }}</span>
                <b class="num">{{ n.dias }}</b>
                <span class="mut ell">{{ n.observacion ?? '—' }}</span>
                <span class="mut tiny">{{ n.estado === 'anulada' ? `Anulada · ${n.motivo_anulacion}` : `${n.registrada_por_name ?? '—'} · ${fmtCel(n.created_at)}` }}</span>
              </button>
              <div v-if="open === n.id" class="panel det">
                <div class="datos">
                  <div><span class="mut tiny">Código</span><br><b class="small">{{ n.code }}</b></div>
                  <div><span class="mut tiny">Descuenta del salario</span><br><b class="small">{{ n.descuenta ? 'Sí' : 'No, solo se cuenta' }}</b></div>
                  <div><span class="mut tiny">Soportes</span><br><b class="small">{{ n.soportes }} archivo{{ n.soportes === 1 ? '' : 's' }}</b></div>
                  <div><span class="mut tiny">Estado</span><br><b class="small">{{ n.estado_txt }}{{ n.anulada_por_name ? ` por ${n.anulada_por_name}` : '' }}</b></div>
                </div>
                <template v-if="n.puede_editar">
                  <div class="row fw gap8 end">
                    <div class="fld grow"><label :for="`ob-${n.id}`">Observación</label><input :id="`ob-${n.id}`" v-model="det.observacion" class="in"></div>
                    <button type="button" class="btn bs sm" :disabled="det.busy" @click="guardarObs(n)">Guardar</button>
                    <button type="button" class="btn bs sm" :disabled="det.busy" @click="adjuntar(n)">Adjuntar soporte</button>
                    <button v-if="!det.anulando" type="button" class="btn br sm" @click="det.anulando = true">Anular</button>
                  </div>
                  <div v-if="det.anulando" class="row fw gap8 end">
                    <div class="fld grow"><label :for="`an-${n.id}`">Por qué se anula <span class="req">*</span></label><input :id="`an-${n.id}`" v-model="det.motivo" class="in" placeholder="Ej.: fechas equivocadas"></div>
                    <button type="button" class="btn br sm" :disabled="det.busy || det.motivo.trim().length < 3" @click="anular(n)">Anular novedad</button>
                    <button type="button" class="btn bs sm" @click="det.anulando = false">Cancelar</button>
                  </div>
                  <div class="mut tiny">¿Fechas o tipo equivocados? Anúlala y regístrala de nuevo: el salario se recalcula.</div>
                </template>
              </div>
            </template>
            <div v-if="!data?.items.length" class="mut empty">{{ pending ? 'Cargando…' : 'No hay novedades en este periodo.' }}</div>
          </div>
        </div>
        <div class="note mt10">
          Incapacidad y permiso no remunerado descuentan del pago del mes (salario mensual ÷ 30 por día); el permiso remunerado solo se cuenta.
          Las registran Coordinación y la Auxiliar; Gerencia las ve aquí. Un salario ya confirmado o pagado no se cambia solo: el sistema avisa para ajustarlo a mano.
        </div>
      </div>
    </template>

    <!-- =================== Del preoperacional =================== -->
    <div v-else class="card">
      <div class="sb mb6">
        <span class="lbl">Novedades reportadas en el preoperacional · {{ rgT }}</span>
        <div class="row fw gap8">
          <label class="row gap6 flt">Desde<input v-model="rg.desde" class="in dt" type="date" aria-label="Fecha desde"></label>
          <label class="row gap6 flt">Hasta<input v-model="rg.hasta" class="in dt" type="date" aria-label="Fecha hasta"></label>
          <NuxtLink v-if="!aux" class="btn bs" to="/preoperacionales">Ver preoperacionales completos</NuxtLink>
        </div>
      </div>
      <div v-for="n in pre ?? []" :key="n.id" class="pre">
        <div class="sb">
          <span><b>{{ n.empleado.full_name }}</b> · {{ fmtCel(n.realizado_at) }} · {{ n.medio }}</span>
          <span class="chip" :class="n.revisado ? 'ok' : 'warn'">{{ n.revisado ? '✓ Revisada' : 'Por revisar' }}</span>
        </div>
        <div class="small">{{ n.texto }}</div>
        <div v-if="n.revisado" class="mut tiny">Revisada por {{ n.revisado_por_name }}{{ n.revisado_at ? ` · ${fmtCel(n.revisado_at)}` : '' }}{{ n.revision_nota ? ` · «${n.revision_nota}»` : '' }}</div>
        <div v-if="n.puede_revisar" class="row fw gap8">
          <input v-model="notaRev[n.id]" class="in nota" placeholder="Nota (opcional)" :aria-label="`Nota de la revisión de ${n.empleado.full_name}`">
          <button type="button" class="btn bs sm" @click="revisar(n.id)">Marcar como revisada</button>
        </div>
      </div>
      <div v-if="!(pre ?? []).length" class="mut empty">No hay novedades del preoperacional en este periodo.</div>
      <div class="note mt10">
        Estas novedades las reporta el empleado en su preoperacional (respuestas «NO» u observaciones). No afectan el pago; sí la seguridad y el
        puntaje del preoperacional. Las revisan Coordinación (las de su equipo) y Gerencia{{ aux ? '; la Auxiliar las ve' : '' }}.
      </div>
    </div>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.self-start {
  align-self: flex-start;
}
.t17 {
  font-size: 17px;
}
.fw {
  flex-wrap: wrap;
}
.gap6 {
  gap: 6px;
}
.gap8 {
  gap: 8px;
}
.mb6 {
  margin-bottom: 6px;
}
.mt10 {
  margin-top: 10px;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.flt {
  font-size: 13px;
  font-weight: 700;
}
.dt {
  min-height: 38px;
  width: auto;
}
.aviso {
  margin-top: 4px;
  color: var(--cdc-warn);
}
.wrap {
  overflow-x: auto;
}
.tbl-min {
  min-width: 860px;
}
.grid {
  display: grid;
  grid-template-columns: 150px 180px 130px 70px minmax(0, 1fr) 190px;
  gap: 10px;
  padding: 10px 6px;
  align-items: center;
  font-size: 13px;
  border-bottom: 1px solid var(--cdc-border-soft);
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
.rw {
  width: 100%;
  background: none;
  border: 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  text-align: left;
  font: inherit;
  color: inherit;
  cursor: pointer;
}
.rw:hover,
.rw.sel {
  background: var(--cdc-bg);
}
.anul {
  opacity: 0.6;
}
.ell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.det {
  padding: 10px 6px 14px;
}
.datos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
}
.end {
  align-items: flex-end;
}
.grow {
  flex: 1 1 260px;
}
.empty {
  padding: 14px 6px;
  font-size: 13px;
}
.pre {
  padding: 12px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.nota {
  min-height: 34px;
  flex: 1 1 220px;
  max-width: 360px;
  font-size: 12.5px;
}
</style>
