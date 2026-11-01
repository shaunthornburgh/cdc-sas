<script setup lang="ts">
import type { EstadoMovimiento, Movimiento, MovOpciones, MovPorEmpleado, TipoMovimiento } from '~/types/movimientos'

/**
 * K05 «Movimientos y GPS».
 * - Gerencia (K05-ger): «Indicadores y registro» and «Configuración y mapa»; reviews the Coordinador.
 * - Coordinación (K05): today's alerts, config and map; reviews asesores and Atención y Preventa.
 *   Also gets the registro and its own field work (K16).
 * - Asesores with Captación and Atención y Preventa: their alerts (M05 «Justificar») and, for
 *   Atención, field work (C09).
 */
definePageMeta({ module: 'movimientos' })
useHead({ title: 'Movimientos y GPS · Casa Dolce Casa' })

const api = useMovimientos()
const auth = useAuth()
const { data: opc, refresh: refreshOpc } = await useAsyncData('mov-opciones', () => api.opciones())
const O = computed(() => opc.value as MovOpciones)
const ger = computed(() => !!O.value?.gerencia)
const panel = computed(() => !!O.value?.panel)
const conCampo = computed(() => Object.keys(O.value?.tipos_campo ?? {}).length > 0)

type Vista = 'ind' | 'cfg' | 'mi'
const TABS = computed<[Vista, string][]>(() =>
  ger.value
    ? [['ind', 'Indicadores y registro'], ['cfg', 'Configuración y mapa']]
    : panel.value
      ? [['cfg', 'Hoy, configuración y mapa'], ['ind', 'Indicadores y registro'], ['mi', 'Mi trabajo en campo']]
      : [],
)
const vista = ref<Vista>(ger.value ? 'ind' : panel.value ? 'cfg' : 'mi')
const msg = ref<{ t: string; ok: boolean } | null>(null)
const say = (t: string, ok = true) => (msg.value = { t, ok })

// ---------------------------------------------------------------- registro (filters)
const rg = reactive({ desde: O.value?.desde ?? localDate(-29), hasta: O.value?.hasta ?? localDate(0) })
const rgErr = computed(() => !rg.desde || !rg.hasta || rg.desde > rg.hasta)
const f = reactive({ empleado_id: '', tipo: '' as TipoMovimiento | '', estado: '' as EstadoMovimiento | '' })
const rango = computed(() => (rgErr.value ? { desde: O.value?.desde, hasta: O.value?.hasta } : { desde: rg.desde, hasta: rg.hasta }))
const query = computed(() =>
  panel.value
    ? { ...rango.value, empleado_id: f.empleado_id || undefined, tipo: f.tipo || undefined, estado: f.estado || undefined }
    : {},
)
const { data, refresh, pending } = await useAsyncData('movimientos', () => api.list(query.value), { watch: [query] })
const hayFil = computed(() => !!(f.empleado_id || f.tipo || f.estado))
const rangoT = computed(() => (rango.value.desde && rango.value.hasta ? `${fmtFecha(rango.value.desde)} al ${fmtFecha(rango.value.hasta)}` : ''))

const KPIS = computed(() => {
  const k = data.value?.kpis
  if (!k) return []
  return [
    { t: 'Alertas', v: k.alertas, d: 'salidas de ruta y tiempos detenidos', warn: false },
    { t: 'Justificadas', v: k.justificadas_pct === null ? '—' : `${k.justificadas_pct}%`, d: `${k.justificadas} de ${k.alertas}`, warn: false },
    { t: 'Sin justificar', v: k.sin_justificar, d: k.vencidas ? `${k.vencidas} vencida${k.vencidas === 1 ? '' : 's'} · −1 punto` : 'pendientes', warn: k.sin_justificar > 0 },
    { t: 'Por revisar', v: k.por_revisar, d: k.por_revisar_gerencia ? `${k.por_revisar_gerencia} del Coordinador: las revisa Gerencia` : 'las del Coordinador las revisa Gerencia', warn: false },
    { t: 'Rechazadas', v: k.rechazadas, d: '−1 punto cada una', warn: false },
    { t: 'Coordinador en campo', v: fmtHorasMin(k.coord_campo_min), d: `${k.coord_campo_salidas} salida${k.coord_campo_salidas === 1 ? '' : 's'}`, warn: false },
  ]
})

// «Por empleado»: 5 at a time, «Por mejorar» / «Mejores»
const orden = ref<'low' | 'top'>('low')
const perOrd = computed(() => {
  const rows = (data.value?.por_empleado ?? []).filter((r) => r.alertas || r.campo_min || r.empleado.id === f.empleado_id)
  const mal = (r: MovPorEmpleado) => r.sin_justificar + r.rechazadas
  return rows.slice().sort((a, b) => (orden.value === 'low' ? mal(b) - mal(a) || b.alertas - a.alertas : mal(a) - mal(b) || a.alertas - b.alertas))
})
const pickEmp = (id: string) => (f.empleado_id = f.empleado_id === id ? '' : id)

const nVer = ref(8)
watch(query, () => (nVer.value = 8))
const items = computed(() => data.value?.items ?? [])
const visibles = computed(() => items.value.slice(0, nVer.value))
const verMas = () => (nVer.value = nVer.value < items.value.length ? nVer.value + 20 : 8)

const fFecha = (iso: string) => `${diaMes(iso)} · ${fmtHora(iso)}`

async function descargar() {
  try {
    await api.descargar({ ...query.value } as Record<string, string>)
    say(`Descargado con los filtros actuales: ${items.value.length} filas (fecha, hora, empleado, acción, detalle, duración, estado y quién revisó). La descarga queda en el historial.`)
  } catch (e) {
    say(apiErrorMessage(e), false)
  }
}

// ---------------------------------------------------------------- row actions
const abierto = ref<string | null>(null)
const justificando = ref<string | null>(null)
const nota = reactive<Record<string, string>>({})
const busy = ref(false)
async function revisar(m: Movimiento, ok: boolean) {
  busy.value = true
  try {
    await (ok ? api.aprobar(m.id, nota[m.id]) : api.rechazar(m.id, nota[m.id]))
    say(
      ok
        ? `${m.code}: justificación aprobada. Queda en el historial.`
        : `${m.code}: justificación rechazada. Descuenta 1 punto en el rendimiento de ${m.empleado.full_name}.`,
    )
    await Promise.all([refresh(), panel.value ? refreshPanel() : null])
  } catch (e) {
    say(apiErrorMessage(e), false)
  } finally {
    busy.value = false
  }
}
async function justificado(m: Movimiento) {
  justificando.value = null
  say(`Justificación enviada. Quedó registrada con fecha, hora, ubicación, motivo y datos. ${m.revisa} la revisa.`)
  await Promise.all([refresh(), panel.value ? refreshPanel() : null])
}

// ---------------------------------------------------------------- «Configuración y mapa»
const { data: pn, refresh: refreshPanel } = await useAsyncData('mov-panel', () => (panel.value ? api.panel() : Promise.resolve(null)))
const cfg = reactive({ t: pn.value?.config.minutos_alerta ?? 20, otro: '', plazo: pn.value?.config.plazo_horas?.toString() ?? '', busy: false })
const esOtro = computed(() => !(pn.value?.config.minutos_opciones ?? [15, 20, 30]).includes(cfg.t) || cfg.t === 0)
const minTxt = computed(() => (cfg.t === 0 ? 'el tiempo que definas' : `${cfg.t} minutos`))
watch(pn, (v) => {
  if (v) Object.assign(cfg, { t: v.config.minutos_alerta, plazo: v.config.plazo_horas?.toString() ?? '' })
})
async function guardarCfg() {
  const minutos = cfg.t === 0 ? Number(cfg.otro) : cfg.t
  if (!minutos) return say('Escribe los minutos.', false)
  cfg.busy = true
  try {
    await api.guardarConfig({ minutos_alerta: minutos, plazo_horas: cfg.plazo ? Number(cfg.plazo) : null })
    say('Configuración guardada. El cambio queda en el historial.')
    await Promise.all([refreshPanel(), refreshOpc()])
  } catch (e) {
    say(apiErrorMessage(e), false)
  } finally {
    cfg.busy = false
  }
}
const atencionTxt = computed(() => {
  const a = pn.value?.atencion_campo
  if (!a) return ''
  const ahora = a.abiertos.length ? `en campo ahora: ${a.abiertos.map((m) => `${m.empleado.full_name} (${m.detalle_txt})`).join(', ')}` : 'nadie en campo ahora'
  const u = a.ultimo
  return u ? `${ahora} · último: ${u.empleado.full_name}, ${fmtCuando(u.ocurrido_at)}, ${u.detalle_txt}` : ahora
})
// Map pins: points at the same place are stacked so their labels don't overlap.
const pins = computed(() => {
  const seen = new Map<string, number>()
  return (pn.value?.mapa ?? []).map((p) => {
    const k = `${p.x}-${p.y}`
    const n = seen.get(k) ?? 0
    seen.set(k, n + 1)
    return { ...p, cx: 60 + p.x * 640, cy: Math.min(232, 35 + p.y * 180 + n * 38) }
  })
})
const PIN = (e: EstadoMovimiento) => (e === 'sin_justificar' || e === 'por_revisar' || e === 'rechazada' ? '#B7791F' : '#1F6B35')

// ---------------------------------------------------------------- «Mi GPS» (own view)
const mios = computed(() => (panel.value ? [] : items.value))
const pendientes = computed(() => data.value?.pendientes ?? [])
const propios = ref<Movimiento[]>([])
async function cargarPropios() {
  // Coordinación's own alerts and field records (its list is everyone's)
  if (!panel.value || !conCampo.value) return
  const me = auth.user.value
  if (!me) return
  const r = await api.list({ empleado_id: me.id, desde: localDate(-29), hasta: localDate(0) })
  propios.value = r.items
}
await cargarPropios()
const misRegistros = computed(() => (panel.value ? propios.value : mios.value))
const campoAbierto = computed(() => misRegistros.value.find((m) => m.en_curso) ?? null)
const historialCampo = computed(() => misRegistros.value.filter((m) => !m.es_alerta))
const misAlertas = computed(() => {
  const ids = new Set(pendientes.value.map((m) => m.id))
  return [...pendientes.value, ...misRegistros.value.filter((m) => m.es_alerta && !ids.has(m.id))]
})
async function campoCambio(t: string) {
  say(t)
  await Promise.all([refresh(), refreshOpc(), cargarPropios(), panel.value ? refreshPanel() : null])
}
async function justificadoPropio(m: Movimiento) {
  await justificado(m)
  await cargarPropios()
}
</script>

<template>
  <PageBar title="Movimientos y GPS" :subtitle="`Solo asesores con Captación activa · solo en jornada ${O?.jornada ?? '8:00 a. m.–6:00 p. m.'}`" :back="panel ? '/coordinacion' : '/'">
    <button v-if="panel && vista === 'cfg'" type="button" class="btn bs" @click="descargar">Descargar salidas y tiempos detenidos (Excel)</button>
  </PageBar>

  <div class="cnt">
    <div v-if="TABS.length" class="tabs self-start">
      <button v-for="[k, t] in TABS" :key="k" type="button" class="tab" :class="{ on: vista === k }" @click="vista = k; msg = null">{{ t }}</button>
    </div>
    <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.t }}</b></div>

    <!-- =================== Indicadores y registro (K05-ger) =================== -->
    <template v-if="vista === 'ind'">
      <div class="card filtros">
        <div class="fld"><label for="m-d1">Desde</label><input id="m-d1" v-model="rg.desde" class="in dt" type="date"></div>
        <div class="fld"><label for="m-d2">Hasta</label><input id="m-d2" v-model="rg.hasta" class="in dt" type="date"></div>
        <div class="fld">
          <label for="m-q">Empleado</label>
          <select id="m-q" v-model="f.empleado_id" class="sel"><option value="">Todos</option><option v-for="e in O.empleados" :key="e.id" :value="e.id">{{ e.full_name }}</option></select>
        </div>
        <div class="fld">
          <label for="m-a">Acción</label>
          <select id="m-a" v-model="f.tipo" class="sel"><option value="">Todas</option><option v-for="(t, k) in O.tipos" :key="k" :value="k">{{ t }}</option></select>
        </div>
        <div class="fld">
          <label for="m-e">Estado</label>
          <select id="m-e" v-model="f.estado" class="sel"><option value="">Todos</option><option v-for="(t, k) in O.estados" :key="k" :value="k">{{ t }}</option></select>
        </div>
        <button v-if="hayFil" type="button" class="fch" @click="Object.assign(f, { empleado_id: '', tipo: '', estado: '' })">✕ Quitar filtros</button>
        <button type="button" class="btn bs ml-auto" @click="descargar">Descargar (Excel)</button>
      </div>
      <div v-if="rgErr" class="note bad"><b>La fecha «Desde» no puede ser posterior a «Hasta». Se muestran los últimos 30 días mientras lo corriges.</b></div>

      <div class="kpis">
        <div v-for="k in KPIS" :key="k.t" class="card" :class="{ kwarn: k.warn }">
          <div class="lbl">{{ k.t }}</div>
          <div class="kn num k32">{{ k.v }}</div>
          <div class="mut tiny">{{ k.d }}</div>
        </div>
      </div>

      <div class="card">
        <div class="sb mb6 fw gap8">
          <span class="lbl">Por empleado · {{ rangoT }}</span>
          <div class="tabs">
            <button type="button" class="tab" :class="{ on: orden === 'low' }" @click="orden = 'low'">Por mejorar</button>
            <button type="button" class="tab" :class="{ on: orden === 'top' }" @click="orden = 'top'">Mejores</button>
          </div>
        </div>
        <div class="wrap">
          <div class="min760">
            <div class="gp hd"><span>Empleado</span><span>Alertas</span><span>Justificadas</span><span>Sin justificar</span><span>Rechazadas</span><span>Horas en campo</span></div>
            <button v-for="r in perOrd.slice(0, 5)" :key="r.empleado.id" type="button" class="gp rw" :class="{ sel: f.empleado_id === r.empleado.id }" @click="pickEmp(r.empleado.id)">
              <span><b>{{ r.empleado.full_name }}</b><br><span class="mut tiny">{{ r.empleado.perfil_txt }}</span></span>
              <span class="num">{{ r.alertas }}</span>
              <span class="num">{{ r.justificadas }}</span>
              <span><span :class="r.sin_justificar ? 'chip warn' : 'mut'">{{ r.sin_justificar }}</span></span>
              <span class="num">{{ r.rechazadas }}</span>
              <span class="num">{{ r.campo_min ? fmtHorasMin(r.campo_min) : '—' }}</span>
            </button>
            <div v-if="!perOrd.length" class="mut empty">Sin movimientos en este periodo.</div>
          </div>
        </div>
        <div class="mut tiny mt6">Mostrando {{ Math.min(5, perOrd.length) }} de {{ perOrd.length }} · toca una fila para filtrar por esa persona</div>
      </div>

      <div class="card">
        <div class="sb mb6"><span class="lbl">Registro · {{ items.length }} {{ items.length === 1 ? 'movimiento' : 'movimientos' }}</span><span class="mut tiny">los más recientes primero</span></div>
        <div class="wrap">
          <div class="min880">
            <div class="gr hd"><span>Fecha</span><span>Empleado</span><span>Acción</span><span>Detalle</span><span>Estado</span></div>
            <template v-for="m in visibles" :key="m.id">
              <div class="gr rw" :class="{ sel: abierto === m.id }" role="button" tabindex="0" :aria-expanded="abierto === m.id" @click="abierto = abierto === m.id ? null : m.id" @keydown.enter="abierto = abierto === m.id ? null : m.id">
                <span class="num">{{ fFecha(m.ocurrido_at) }}</span>
                <b>{{ firstName(m.empleado.full_name) }}</b>
                <span>{{ m.tipo_txt }}</span>
                <span class="mut">{{ m.detalle_txt }}</span>
                <span class="est">
                  <span :class="movCls(m)">{{ movEstado(m) }}</span>
                  <span v-if="m.puede_revisar" class="row gap6" @click.stop>
                    <button type="button" class="btn bp xs" :disabled="busy" @click="revisar(m, true)">Aprobar</button>
                    <button type="button" class="btn br xs" :disabled="busy" @click="revisar(m, false)">Rechazar</button>
                  </span>
                </span>
              </div>
              <template v-if="abierto === m.id">
                <div v-if="m.puede_revisar" class="row fw gap8 nota-rev">
                  <input v-model="nota[m.id]" class="in nota" placeholder="Nota de la revisión (opcional)" :aria-label="`Nota de la revisión de ${m.code}`">
                </div>
                <MovDetalle :m="m" @error="(t) => say(t, false)" />
              </template>
            </template>
            <div v-if="!items.length" class="mut empty">{{ pending ? 'Cargando…' : 'No hay movimientos con estos filtros.' }}</div>
          </div>
        </div>
        <div class="sb mt8 small">
          <span class="mut">Mostrando {{ visibles.length }} de {{ items.length }}</span>
          <button v-if="items.length > 8" type="button" class="btn bs sm" @click="verMas">{{ nVer < items.length ? 'Ver más' : 'Ver menos' }}</button>
        </div>
      </div>
      <div class="note">
        Aquí está todo lo de campo: salidas de ruta y tiempos detenidos de los asesores con Captación, el trabajo en campo del Coordinador (con sus alertas, que revisa
        Gerencia) y Atención y Preventa cuando sale a apoyar una cita. Una alerta rechazada o sin justificar en el plazo descuenta 1 punto. El tiempo que genera alerta y
        el mapa están en «Configuración y mapa».
      </div>
    </template>

    <!-- =================== Configuración y mapa / hoy (K05) =================== -->
    <template v-if="vista === 'cfg' && pn">
      <div class="sb strip">
        <span><b>Atención y Preventa en campo:</b> {{ atencionTxt }}</span>
        <span class="chip" :class="pn.atencion_campo.abiertos.length ? 'ok' : 'gray'">{{ pn.atencion_campo.abiertos.length ? 'GPS activo' : 'GPS apagado' }}</span>
      </div>
      <div v-if="pn.coordinador_campo.abiertos.length" class="sb strip">
        <span><b>Coordinador en campo:</b> {{ pn.coordinador_campo.abiertos.map((m) => `${m.empleado.full_name} · ${m.detalle_txt}`).join(' · ') }}</span>
        <span class="chip ok">GPS activo</span>
      </div>

      <div class="g2b">
        <div class="card col">
          <div class="lbl">Tiempo detenido que genera alerta</div>
          <div class="row fw">
            <button v-for="t in pn.config.minutos_opciones" :key="t" type="button" class="opt" :class="{ on: cfg.t === t }" @click="cfg.t = t">{{ t }} minutos</button>
            <button type="button" class="opt" :class="{ on: esOtro }" @click="cfg.t = 0">Otro tiempo</button>
          </div>
          <div v-if="esOtro" class="fld"><label for="m-ot">Minutos</label><input id="m-ot" v-model="cfg.otro" class="in w160" inputmode="numeric" :placeholder="cfg.t ? String(cfg.t) : 'Ej: 45'"></div>
          <div class="fld">
            <label for="m-pl">Plazo para justificar (horas)</label>
            <input id="m-pl" v-model="cfg.plazo" class="in w160" inputmode="numeric" placeholder="Pendiente de configuración">
          </div>
          <div class="note">
            Si un asesor permanece más de <b>{{ minTxt }}</b> en la misma posición, a él le aparece: «Llevas más de {{ minTxt }} en esta misma posición. Por favor, justifica
            este tiempo detenido.» y a ti te llega la alerta. {{ pn.config.plazo_horas ? `Tiene ${pn.config.plazo_horas} h para justificar.` : 'Plazo: PENDIENTE DE CONFIGURACIÓN (mientras tanto, no vence).' }} El cambio queda en el historial.
          </div>
          <button type="button" class="btn bp self-start" :disabled="cfg.busy" @click="guardarCfg">Guardar</button>
          <div v-if="pn.cambios_config.length" class="mut tiny">
            Último cambio: {{ pn.cambios_config[0].detalle }} · {{ pn.cambios_config[0].actor_name }} · {{ fmtCuando(pn.cambios_config[0].created_at) }}
          </div>
        </div>
        <div class="card col">
          <div class="lbl">¿Quién tiene GPS?</div>
          <div class="sb"><span><b>{{ pn.con_gps.map(firstName).join(', ') || 'Nadie' }}</b> · tienen Captación</span><span class="chip ok">GPS activo</span></div>
          <div class="sb"><span><b>{{ pn.sin_gps.map(firstName).join(', ') || 'Nadie' }}</b> · no tienen Captación</span><span class="chip gray">Sin GPS</span></div>
          <div class="sb"><span><b>Coordinador y Atención y Preventa</b> · solo mientras están en campo</span><span class="chip info">En campo</span></div>
          <div class="note">
            Cada vez que abres la ubicación de una persona queda registrado quién la consultó y cuándo. Nada de seguimiento oculto: el asesor siempre ve que su GPS está
            activo.
          </div>
        </div>
      </div>

      <div class="card mapa">
        <svg viewBox="0 0 1000 260" role="img" aria-label="Mapa esquemático con las posiciones registradas hoy">
          <rect width="1000" height="260" fill="#E9EBE6" />
          <path d="M0 70 H1000 M0 190 H1000 M150 0 V260 M420 0 V260 M700 0 V260 M880 0 V260" stroke="#fff" stroke-width="14" />
          <g v-for="p in pins" :key="p.id">
            <circle :cx="p.cx" :cy="p.cy" r="16" :fill="PIN(p.estado)" />
            <text :x="p.cx" :y="p.cy + 5" text-anchor="middle" font-size="13" font-weight="800" fill="#fff">{{ p.empleado[0] }}</text>
            <text :x="p.cx + 22" :y="p.cy + 5" font-size="13" font-weight="700" :fill="PIN(p.estado) === '#1F6B35' ? '#1F6B35' : '#5C3B00'">
              {{ firstName(p.empleado) }} · {{ p.tipo_txt.split(' (')[0].toLowerCase() }} {{ fmtHora(p.hora) }}
            </text>
          </g>
          <text v-if="!pn.mapa.length" x="500" y="135" text-anchor="middle" font-size="15" font-weight="700" fill="#5A5D60">Sin posiciones registradas hoy</text>
        </svg>
        <div class="mut tiny pad">Posiciones de hoy, una por alerta o salida a campo, ubicadas entre sí (esquema, no a escala).</div>
      </div>

      <div class="card">
        <div class="sb mb6"><span class="lbl">Salidas de ruta y tiempos detenidos de hoy</span></div>
        <div class="wrap">
          <div class="min960">
            <div class="gh hd"><span>Hora</span><span>Asesor</span><span>Tipo</span><span>Justificación</span><span>Datos</span><span>Estado</span><span>Acción</span></div>
            <template v-for="m in pn.hoy" :key="m.id">
              <div class="gh rw" role="button" tabindex="0" @click="abierto = abierto === m.id ? null : m.id" @keydown.enter="abierto = abierto === m.id ? null : m.id">
                <span class="num">{{ fmtHora(m.ocurrido_at) }}</span>
                <b>{{ m.empleado.full_name }}</b>
                <span>{{ m.tipo_txt }}{{ m.minutos_umbral ? ` (+${m.minutos_umbral} min)` : '' }}</span>
                <span>{{ m.motivo_txt ?? 'Pendiente de justificar' }}</span>
                <span class="mut">{{ m.motivo ? [m.inmueble_codigo, m.cliente, m.motivo_texto, m.autorizo_txt && `autorizó ${m.autorizo_txt.toLowerCase()}`, m.observacion].filter(Boolean).join(' · ') : (m.lugar ?? '—') }}</span>
                <span><span :class="movCls(m)">{{ movEstado(m, true) }}</span></span>
                <span @click.stop>
                  <span v-if="m.puede_revisar" class="row gap6">
                    <button type="button" class="btn bp" :disabled="busy" @click="revisar(m, true)">Aprobar</button>
                    <button type="button" class="btn br" :disabled="busy" @click="revisar(m, false)">Rechazar</button>
                  </span>
                  <span v-else-if="m.estado === 'por_revisar'" class="mut tiny">La revisa {{ m.revisa }}</span>
                </span>
              </div>
              <MovDetalle v-if="abierto === m.id" :m="m" @error="(t) => say(t, false)" />
            </template>
            <div v-if="!pn.hoy.length" class="mut empty">Hoy no hay salidas de ruta ni tiempos detenidos.</div>
          </div>
        </div>
      </div>
    </template>

    <!-- =================== Mi GPS (M05 / K16 / C09) =================== -->
    <template v-if="vista === 'mi'">
      <div class="sb strip">
        <span><b>Mi GPS:</b> {{ O.perfil === 'asesor' ? 'activo en la jornada porque tienes Captación' : 'solo se activa mientras estás en campo' }}</span>
        <span class="chip" :class="O.gps_activo ? 'ok' : 'gray'">{{ O.gps_activo ? '● GPS activo' : 'GPS apagado' }}</span>
      </div>

      <MovCampo v-if="conCampo" :o="O" :abierto="campoAbierto" @changed="campoCambio" />

      <div class="card">
        <div class="lbl mb6">Alertas y justificaciones{{ O.perfil !== 'asesor' ? ' · igual que los asesores' : '' }}</div>
        <div v-for="m in misAlertas" :key="m.id" class="al">
          <div class="sb fw gap8">
            <span><b>{{ m.tipo_txt }} · {{ fmtCuando(m.ocurrido_at) }}</b><br><span class="mut small">{{ m.detalle_txt }}</span></span>
            <span class="row gap8">
              <span :class="movCls(m)">{{ m.estado === 'aprobada' && m.revisado_por_name ? `✓ Aprobada por ${firstName(m.revisado_por_name)}` : movEstado(m) }}</span>
              <button v-if="m.puede_justificar && justificando !== m.id" type="button" class="btn bp sm" @click="justificando = m.id">Justificar</button>
            </span>
          </div>
          <div v-if="m.nota_revision" class="mut tiny">Nota de {{ m.revisado_por_name }}: «{{ m.nota_revision }}»</div>
          <MovJustificar v-if="justificando === m.id" :m="m" :o="O" @done="panel ? justificadoPropio($event) : justificado($event)" @cancel="justificando = null" />
        </div>
        <div v-if="!misAlertas.length" class="mut empty">No tienes alertas en los últimos 30 días.</div>
        <div class="note mt10">
          Una justificación rechazada o una alerta sin justificar en el plazo descuenta 1 punto de rendimiento, igual que a todos.
          {{ O.perfil === 'coordinacion' ? 'Las del Coordinador las revisa Gerencia.' : 'Las revisa Coordinación.' }}
          Plazo para justificar: {{ O.config.plazo_horas ? `${O.config.plazo_horas} horas` : 'PENDIENTE DE CONFIGURACIÓN' }}.
        </div>
      </div>

      <div v-if="conCampo" class="card">
        <div class="lbl mb6">Historial en campo · últimos 30 días</div>
        <div v-for="m in historialCampo" :key="m.id" class="sb hc">
          <span><b>{{ diaMes(m.ocurrido_at) }} · {{ m.tipo_campo_txt }}</b><br><span class="mut small">{{ m.detalle_txt.replace(`${m.tipo_campo_txt} · `, '').replace(` · ${m.duracion_txt}`, '').replace(' · en curso', '') }}</span></span>
          <span class="num small">{{ m.en_curso ? `${fmtHora(m.ocurrido_at)} →` : m.duracion_txt }}</span>
        </div>
        <div v-if="!historialCampo.length" class="mut empty">Sin salidas a campo en los últimos 30 días.</div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.self-start {
  align-self: flex-start;
}
.ml-auto {
  margin-left: auto;
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
.mt6 {
  margin-top: 6px;
}
.mt8 {
  margin-top: 8px;
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
.col {
  display: flex;
  flex-direction: column;
  gap: 10px;
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
.kpis {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}
.kwarn {
  background: #fffbf1;
  border-color: #ebcb8b;
}
.k32 {
  font-size: 32px;
}
.wrap {
  overflow-x: auto;
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
.gp,
.gr,
.gh {
  display: grid;
  gap: 8px;
  padding: 9px 4px;
  font-size: 13px;
  align-items: center;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.gp {
  grid-template-columns: minmax(160px, 1.4fr) repeat(5, minmax(90px, 1fr));
}
.gr {
  grid-template-columns: 120px 140px 170px minmax(0, 1fr) 190px;
}
.gh {
  grid-template-columns: 70px 130px 170px 170px minmax(0, 1fr) 190px 190px;
  gap: 10px;
  padding: 11px 10px;
}
.hd {
  font-size: 10.5px;
  color: var(--cdc-muted);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding-top: 6px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--cdc-border);
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
  background: #f0f8ee;
}
.est {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}
.xs {
  min-height: 30px;
  padding: 0 10px;
  font-size: 12px;
}
.nota-rev {
  padding: 8px 4px 0;
}
.nota {
  min-height: 34px;
  flex: 1 1 260px;
  max-width: 420px;
  font-size: 12.5px;
}
.empty {
  padding: 14px 6px;
  font-size: 13px;
}
.strip {
  padding: 10px 14px;
  border: 1px solid var(--cdc-border);
  border-radius: 12px;
  background: #fff;
  font-size: 13px;
  gap: 10px;
  flex-wrap: wrap;
}
.w160 {
  max-width: 240px;
}
.mapa {
  padding: 0;
  overflow: hidden;
}
.mapa svg {
  width: 100%;
  height: auto;
  display: block;
  font-family: var(--font-body, sans-serif);
}
.pad {
  padding: 8px 14px;
}
.hc {
  padding: 10px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  gap: 12px;
}
.al {
  padding: 12px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
</style>
