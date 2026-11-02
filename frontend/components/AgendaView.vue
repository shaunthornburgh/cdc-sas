<script setup lang="ts">
import type { AgEntrada, AgPersona, AgTipo } from '~/types/agenda'

/**
 * The agenda (G09 agenda, G-089): the same top bar in every agenda — «Agenda de [persona]» (only
 * for whoever can see others), ‹ › and «Hoy», Día / Semana, «+ Agregar». One view per person that
 * joins the system's items with the activities added by hand. Tapping an activity opens its detail
 * with the actions G-088 allows.
 */
const props = defineProps<{ inicial?: string | null }>()
const emit = defineEmits<{ changed: [] }>()
const api = useAgenda()
const { refrescar } = useAvisosConteo()

const hoy = localDate(0)
const addDays = (s: string, n: number) => new Date(new Date(`${s}T12:00:00Z`).getTime() + n * 86_400_000).toISOString().slice(0, 10)
const DIAS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb']
const MES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const dia = (s: string) => new Date(`${s}T12:00:00Z`)
const fd = (s: string) => `${dia(s).getUTCDate()} ${MES[dia(s).getUTCMonth()]}`
const fdd = (s: string) => `${s === hoy ? 'Hoy · ' : ''}${DIAS[dia(s).getUTCDay()]} ${fd(s)}`

const A = reactive({ sel: props.inicial ?? '', v: 'sem' as 'sem' | 'dia', ws: hoy, dd: hoy })
const msg = ref('')

const { data: personas } = await useAsyncData('agenda-personas', () => api.personas())
const yo = computed(() => personas.value?.find((p) => p.yo))
const sel = computed<AgPersona | undefined>(() => personas.value?.find((p) => p.id === A.sel) ?? yo.value)
const esYo = computed(() => !!sel.value?.yo)
const rango = computed(() => (A.v === 'sem' ? { desde: A.ws, hasta: addDays(A.ws, 6) } : { desde: A.dd, hasta: A.dd }))
const { data, refresh } = await useAsyncData(
  'agenda-vista',
  () => api.vista({ ...rango.value, user_id: sel.value && !sel.value.yo ? sel.value.id : undefined }),
  { watch: [rango, () => A.sel] },
)
const items = computed(() => data.value?.items ?? [])
const semana = computed(() => Array.from({ length: 7 }, (_, i) => addDays(A.ws, i)))
const delDia = (d: string) => items.value.filter((i) => i.fecha === d)
const rangoTxt = computed(() => (A.v === 'sem' ? `${fd(semana.value[0]!)} – ${fd(semana.value[6]!)}` : fdd(A.dd)))
const prev = () => (A.v === 'sem' ? (A.ws = addDays(A.ws, -7)) : (A.dd = addDays(A.dd, -1)))
const next = () => (A.v === 'sem' ? (A.ws = addDays(A.ws, 7)) : (A.dd = addDays(A.dd, 1)))
const irHoy = () => Object.assign(A, { ws: hoy, dd: hoy })
const verDia = (d: string) => Object.assign(A, { v: 'dia', dd: d })

const LEYENDA: [AgTipo, string][] = [
  ['cita', 'Cita'],
  ['seg', 'Seguimiento o pendiente'],
  ['ped', 'Vencimiento o requiere acción'],
  ['ctl', 'Control e inventario'],
  ['ruta', 'Ruta del coordinador'],
  ['mia', 'Agregada por la persona'],
  ['asg', 'Asignada por otra persona'],
]
const tachada = (i: AgEntrada) => i.estado === 'hecha' || i.estado === 'rechazada'

// ---------------------------------------------------------------- detail
const det = ref<AgEntrada | null>(null)
const ac = ref<'' | 'r' | 'j' | 'x'>('')
const motivo = ref('')
const busy = ref(false)
function abrir(i: AgEntrada) {
  det.value = i
  ac.value = ''
  motivo.value = ''
}
const cerrar = () => (det.value = null)
const quien = computed(() => {
  const i = det.value
  if (!i) return ''
  if (i.k === 'sys') return 'Lo pone el sistema (citas, seguimientos y vencimientos)'
  const cuando = i.created_at ? ` · ${fmtCuando(i.created_at)}` : ''
  return `${i.sub ?? ''}${cuando}`.replace(' · prioridad alta', '')
})
const respuesta = computed(() => {
  const i = det.value
  if (!i || i.k !== 'man') return ''
  if (i.estado === 'rechazada' || i.estado === 'justificada')
    return `${i.estado === 'rechazada' ? 'Rechazada' : 'Justificada'} por ${esYo.value ? 'ti' : sel.value?.full_name} · ${i.respondida_at ? fmtCuando(i.respondida_at) : ''} · motivo: ${i.motivo}`
  if (i.estado === 'hecha') return `Hecha · ${i.respondida_at ? fmtCuando(i.respondida_at) : ''}`
  return ''
})
const info = computed(() => {
  const i = det.value
  if (!i || i.k !== 'man') return ''
  if (i.acciones.rechazar) return `La asignó ${i.por_name}: no se puede borrar; si no la vas a hacer, recházala o justifícala con el motivo.`
  if (!i.por_yo && !i.acciones.hecha) return `Solo lectura: la puso ${i.por_name}.`
  return ''
})
async function hacer(fn: () => Promise<unknown>, texto: string) {
  busy.value = true
  try {
    await fn()
    msg.value = texto
    det.value = null
    await Promise.all([refresh(), refrescar()])
    emit('changed')
  } catch (e) {
    msg.value = apiErrorMessage(e)
  } finally {
    busy.value = false
  }
}
function confirmar() {
  const i = det.value!
  if (ac.value === 'x') return hacer(() => api.eliminar(i.id), `«${i.titulo}» eliminada · queda en «Actividades eliminadas».`)
  if (motivo.value.trim().length < 3) return (msg.value = 'Escribe el motivo.')
  const r = ac.value === 'r'
  return hacer(
    () => (r ? api.rechazar(i.id, motivo.value) : api.justificar(i.id, motivo.value)),
    `«${i.titulo}» ${r ? 'rechazada' : 'justificada'}. ${i.por_name} recibió el aviso con tu motivo.`,
  )
}
const marcarHecha = (i: AgEntrada) =>
  hacer(() => api.hecha(i.id), `«${i.titulo}» marcada como hecha.${i.por_yo ? '' : ` ${i.por_name} recibió el aviso.`}`)

// ---------------------------------------------------------------- add
const paraOp = computed(() => (personas.value ?? []).filter((p) => p.puede_agregar))
const F = reactive({ on: false, para: '', titulo: '', fecha: hoy, hora: '', prioridad: 'normal', nota: '', err: '' })
function nuevo() {
  const para = sel.value?.puede_agregar ? sel.value.id : (yo.value?.id ?? '')
  Object.assign(F, { on: true, para, titulo: '', fecha: A.v === 'dia' && A.dd >= hoy ? A.dd : hoy, hora: '', prioridad: 'normal', nota: '', err: '' })
  det.value = null
  msg.value = ''
}
const paraPersona = computed(() => personas.value?.find((p) => p.id === F.para))
const fAviso = computed(() =>
  paraPersona.value?.yo
    ? 'Queda en tu agenda. Puedes eliminarla cuando quieras.'
    : `Queda como «asignada por ${yo.value?.full_name}». ${paraPersona.value?.full_name} recibe el aviso y no la puede borrar: solo hacerla, rechazarla o justificarla.`,
)
async function guardar() {
  F.err = ''
  if (!F.titulo.trim() || !F.fecha) return (F.err = 'Escribe la actividad y la fecha.')
  try {
    await api.agregar({ para_id: F.para, titulo: F.titulo, fecha: F.fecha, hora: F.hora || null, prioridad: F.prioridad, nota: F.nota || null })
    const p = paraPersona.value
    msg.value = p?.yo ? 'Actividad agregada a tu agenda.' : `Actividad asignada a ${p?.full_name}. Le llegó el aviso y queda registrado que la pusiste tú.`
    F.on = false
    A.sel = p?.yo ? '' : F.para
    if (A.v === 'sem' && (F.fecha < A.ws || F.fecha > addDays(A.ws, 6))) A.ws = F.fecha
    A.dd = F.fecha
    await Promise.all([refresh(), refrescar()])
    emit('changed')
  } catch (e) {
    F.err = apiErrorMessage(e)
  }
}

const onKey = (e: KeyboardEvent) => {
  if (e.key === 'Escape') {
    det.value = null
    F.on = false
  }
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="ag">
    <div class="topbar">
      <div class="row fw g10">
        <label v-if="(personas?.length ?? 0) > 1" class="row g8 lblsel">
          Agenda de
          <select v-model="A.sel" class="sel selp" aria-label="Ver la agenda de">
            <option v-for="p in personas" :key="p.id" :value="p.yo ? '' : p.id">{{ p.yo ? 'Mi agenda' : `${p.full_name} · ${p.rol_txt}` }}</option>
          </select>
        </label>
        <div class="row gp4">
          <button type="button" class="fch" aria-label="Anterior" @click="prev">‹</button>
          <b class="rango">{{ rangoTxt }}</b>
          <button type="button" class="fch" aria-label="Siguiente" @click="next">›</button>
          <button type="button" class="fch" @click="irHoy">Hoy</button>
        </div>
        <div class="tabs tp">
          <button type="button" class="tab" :class="{ on: A.v === 'dia' }" @click="A.v = 'dia'">Día</button>
          <button type="button" class="tab" :class="{ on: A.v === 'sem' }" @click="A.v = 'sem'">Semana</button>
        </div>
      </div>
      <button v-if="paraOp.length" type="button" class="btn bp" @click="nuevo">+ Agregar</button>
    </div>

    <div v-if="msg" class="note ok" role="status"><b>{{ msg }}</b></div>
    <div class="row fw g10 ley">
      <span v-for="[k, t] in LEYENDA" :key="k" class="row gp6"><span class="sw" :style="{ background: AG_COLOR[k] }" />{{ t }}</span>
    </div>

    <!-- Semana -->
    <div v-if="A.v === 'sem'" class="semana">
      <div v-for="d in semana" :key="d" class="dia" :class="{ hoy: d === hoy }">
        <button type="button" class="dh" @click="verDia(d)"><b>{{ fdd(d) }}</b><span class="mut">{{ delDia(d).length || '' }}</span></button>
        <button v-for="i in delDia(d)" :key="i.id" type="button" class="it" :style="{ borderLeftColor: AG_COLOR[i.tipo] }" @click="abrir(i)">
          <span class="hc">{{ i.hora_txt }}</span>
          <span class="ti" :class="{ tach: tachada(i) }">{{ i.titulo }}</span>
          <span class="mut sub">{{ i.estado === 'atrasada' ? 'Atrasada · ' : '' }}{{ i.sub }}</span>
        </button>
      </div>
    </div>

    <!-- Día -->
    <div v-else class="card diac">
      <button v-for="i in items" :key="i.id" type="button" class="fila" @click="abrir(i)">
        <span class="barra" :style="{ background: AG_COLOR[i.tipo] }" />
        <b class="num hcol">{{ i.hora_txt }}</b>
        <span class="grow"><b class="t135" :class="{ tach: tachada(i) }">{{ i.titulo }}</b><br><span class="mut small">{{ i.sub }}</span></span>
        <span class="chip" :class="i.estado_cls">{{ i.estado_txt }}</span>
      </button>
      <div v-if="!items.length" class="note vacio">Nada agendado este día.</div>
    </div>

    <details class="reglas">
      <summary class="mut">Quién puede ver y agregar en las agendas · actividades eliminadas ({{ data?.eliminadas.length ?? 0 }}) ›</summary>
      <div class="note">
        Cada persona agrega y elimina solo lo que ella misma puso. Lo que pone otra persona no se borra: se hace, se rechaza o se justifica con motivo, y quien lo puso
        recibe el aviso. Coordinación ve y asigna en las agendas de asesores y de Atención y Preventa; Gerencia ve y asigna en todas; la Auxiliar administrativa ve
        todas y asigna en todas menos en la de Gerencia; entre asesores nadie ve ni toca la agenda de otro. Todo queda con fecha, hora y quién lo hizo.
      </div>
      <div v-for="(x, k) in data?.eliminadas ?? []" :key="k" class="mut tiny elim">
        «{{ x.titulo }}» · la eliminó {{ x.eliminada_por }} el {{ fmtCuando(x.eliminado_at) }} · la había puesto {{ x.por_name }} el {{ fmtCuando(x.created_at) }}
      </div>
    </details>

    <!-- Detail -->
    <div v-if="det" class="overlay top" @click.self="cerrar">
      <div class="card dlg" role="dialog" aria-modal="true" aria-label="Detalle de la actividad">
        <div class="sb start g8">
          <div>
            <span class="lbl" :style="{ color: AG_COLOR[det.tipo] }">{{ data?.tipos[det.tipo] ?? det.tipo }}</span>
            <div class="dt">{{ det.titulo }}</div>
          </div>
          <span class="chip" :class="det.estado_cls">{{ det.estado_txt }}</span>
        </div>
        <div class="small"><b>{{ fdd(det.fecha) }} · {{ det.hora_txt }}</b> · agenda de {{ esYo ? 'ti' : sel?.full_name }}</div>
        <div class="mut small">{{ quien }}{{ det.prioridad === 'alta' ? ' · prioridad alta' : '' }}</div>
        <div v-if="det.nota" class="small">{{ det.nota }}</div>
        <div v-if="det.aviso_titulo" class="mut tiny">Desde el aviso: {{ det.aviso_titulo }}</div>
        <div v-if="respuesta" class="note warn"><b>{{ respuesta }}</b></div>
        <div v-if="ac === 'r' || ac === 'j'" class="fld">
          <label for="ag-mot">{{ ac === 'r' ? 'Motivo del rechazo' : 'Justificación' }} <span class="req">*</span></label>
          <input id="ag-mot" v-model="motivo" class="in" placeholder="Explica el motivo">
        </div>
        <div v-if="ac === 'x'" class="note bad"><b>¿Eliminar esta actividad? Queda registrado quién la eliminó y cuándo.</b></div>
        <div v-if="info && !ac" class="mut tiny">{{ info }}</div>
        <div class="row fw g8">
          <template v-if="ac">
            <button type="button" class="btn" :class="ac === 'x' ? 'br' : 'bp'" :disabled="busy" @click="confirmar">
              {{ ac === 'r' ? 'Confirmar rechazo' : ac === 'j' ? 'Confirmar justificación' : 'Sí, eliminar' }}
            </button>
          </template>
          <template v-else-if="det.k === 'man'">
            <button v-if="det.acciones.hecha" type="button" class="btn bp" :disabled="busy" @click="marcarHecha(det)">Marcar hecha</button>
            <button v-if="det.acciones.rechazar" type="button" class="btn bs" @click="ac = 'r'">Rechazar</button>
            <button v-if="det.acciones.justificar" type="button" class="btn bs" @click="ac = 'j'">Justificar</button>
            <button v-if="det.acciones.eliminar" type="button" class="btn br" @click="ac = 'x'">Eliminar</button>
          </template>
          <NuxtLink v-if="det.link" :to="det.link" class="btn bs">Abrir ›</NuxtLink>
          <button type="button" class="btn bs" @click="ac ? (ac = '') : cerrar()">{{ ac ? 'Volver' : 'Cerrar' }}</button>
        </div>
      </div>
    </div>

    <!-- Add -->
    <div v-if="F.on" class="overlay top" @click.self="F.on = false">
      <div class="card dlg" role="dialog" aria-modal="true" aria-label="Agregar actividad">
        <b class="t17">Agregar actividad</b>
        <div class="fld">
          <label for="ag-para">¿En la agenda de quién?</label>
          <select id="ag-para" v-model="F.para" class="in">
            <option v-for="p in paraOp" :key="p.id" :value="p.id">{{ p.yo ? 'Mi agenda' : `${p.full_name} · ${p.rol_txt}` }}</option>
          </select>
        </div>
        <div class="fld"><label for="ag-t">Actividad <span class="req">*</span></label><input id="ag-t" v-model="F.titulo" class="in" placeholder="Ej.: Llamar al propietario de INM-0350"></div>
        <div class="g3x">
          <div class="fld"><label for="ag-f">Fecha <span class="req">*</span></label><input id="ag-f" v-model="F.fecha" class="in" type="date" :min="hoy"></div>
          <div class="fld"><label for="ag-h">Hora</label><input id="ag-h" v-model="F.hora" class="in" type="time" step="900"></div>
          <div class="fld">
            <label for="ag-p">Prioridad</label>
            <select id="ag-p" v-model="F.prioridad" class="in"><option value="normal">Normal</option><option value="alta">Alta</option></select>
          </div>
        </div>
        <div class="fld"><label for="ag-n">Nota (opcional)</label><input id="ag-n" v-model="F.nota" class="in" placeholder="Detalle o instrucciones"></div>
        <div class="mut tiny">{{ fAviso }}</div>
        <div v-if="F.err" class="note bad"><b>{{ F.err }}</b></div>
        <div class="row g8">
          <button type="button" class="btn bp" @click="guardar">Guardar</button>
          <button type="button" class="btn bs" @click="F.on = false">Cancelar</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ag {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.topbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border: 1px solid var(--cdc-border);
  border-radius: 14px;
  padding: 10px 12px;
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
.lblsel {
  font-weight: 700;
  font-size: 13px;
}
.selp {
  min-width: 210px;
}
.rango {
  font-size: 13.5px;
  min-width: 120px;
  text-align: center;
}
.tp {
  padding: 3px;
}
.tp .tab {
  min-height: 32px;
}
.ley {
  font-size: 11.5px;
}
.sw {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  display: inline-block;
}
.semana {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(7, minmax(0, 1fr));
}
.dia {
  background: #fff;
  border: 1px solid var(--cdc-border);
  border-radius: 12px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 260px;
}
.dia.hoy {
  border: 2px solid var(--cdc-green);
}
.dh {
  all: unset;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 4px;
  font-size: 12.5px;
}
.dh .mut {
  font-size: 11px;
}
.it {
  all: unset;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 1px;
  border-radius: 8px;
  padding: 6px 7px;
  background: var(--cdc-bg);
  border-left: 4px solid;
}
.it:focus-visible,
.dh:focus-visible,
.fila:focus-visible {
  outline: 2px solid var(--cdc-green);
}
.hc {
  font-size: 11px;
  font-weight: 800;
}
.ti {
  font-size: 12px;
  font-weight: 700;
  line-height: 1.25;
}
.sub {
  font-size: 10.5px;
}
.tach {
  text-decoration: line-through;
  color: var(--cdc-disabled);
}
.diac {
  padding: 6px 14px;
}
.fila {
  all: unset;
  cursor: pointer;
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  width: 100%;
}
.barra {
  width: 5px;
  align-self: stretch;
  border-radius: 4px;
  flex: none;
}
.hcol {
  width: 74px;
  flex: none;
  font-size: 13px;
}
.grow {
  flex: 1;
  min-width: 0;
}
.t135 {
  font-size: 13.5px;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.t17 {
  font-size: 17px;
}
.vacio {
  margin: 10px 0;
}
.reglas summary {
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}
.reglas .note {
  margin-top: 6px;
}
.elim {
  padding: 5px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.overlay.top {
  align-items: flex-start;
  padding-top: 70px;
}
.dlg {
  width: min(470px, 100%);
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 85vh;
  overflow: auto;
}
.start {
  align-items: flex-start;
}
.dt {
  font-size: 17px;
  font-weight: 800;
  line-height: 1.25;
}
.g3x {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
}
@media (max-width: 760px) {
  .semana {
    grid-template-columns: minmax(0, 1fr);
  }
  .dia {
    min-height: 0;
  }
}
</style>
