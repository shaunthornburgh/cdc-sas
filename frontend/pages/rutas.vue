<script setup lang="ts">
import type { ImportRev, MiRuta, Ruta, RutasOpciones, RutaZona, Ubicacion } from '~/types/rutas'

/**
 * Rutas (G-083). Two views on one page:
 * - Asesores with Captación: M04 «Mi ruta de hoy» (routes to answer, today's timeline, arrivals).
 * - Coordinación: X08 «Rutas y ubicación del equipo» (assign one by one, Excel template, assigned
 *   routes). Gerencia and the Auxiliar consult the same list; Gerencia rates routes 1 to 5.
 */
definePageMeta({ cargos: ['asesor', 'coordinacion', 'gerencia', 'auxiliar_administrativa'] })
useHead({ title: 'Rutas · Casa Dolce Casa' })

const api = useRutas()
const auth = useAuth()
const route = useRoute()
const { data: oData } = await useAsyncData('rutas-op', () => api.opciones())
const O = computed(() => oData.value as RutasOpciones | null)
const equipo = computed(() => !!O.value?.puede_consultar)
const home = computed(() => (['gerencia', 'coordinacion'].includes(auth.user.value?.cargo ?? '') ? '/coordinacion' : '/'))
const DIAS: [number, string][] = [
  [1, 'Lun'],
  [2, 'Mar'],
  [3, 'Mié'],
  [4, 'Jue'],
  [5, 'Vie'],
  [6, 'Sáb'],
]
const msg = ref<{ t: string; ok: boolean } | null>(null)
const say = (t: string, ok = true) => (msg.value = { t, ok })

// =============================================================== Mi ruta (asesor)
const { data: mData, refresh: refreshMi } = await useAsyncData('mi-ruta', () => (O.value?.es_captador && !equipo.value ? api.miRuta() : Promise.resolve(null)))
const M = computed(() => mData.value as MiRuta | null)
const hoyTxt = computed(() => {
  if (!M.value) return ''
  const d = new Date(`${M.value.fecha}T12:00:00`)
  const s = new Intl.DateTimeFormat('es-CO', { weekday: 'long', day: 'numeric', month: 'short' }).format(d).replace('.', '')
  return s.charAt(0).toUpperCase() + s.slice(1)
})
const resp = reactive({ id: '', motivo: '', texto: '', err: '' })
async function aceptar(r: Ruta) {
  try {
    await api.responder(r.id, true)
    say(`Ruta del ${r.periodo_txt} aceptada. Ya está en tu agenda. Coordinación recibió tu respuesta.`)
    await refreshMi()
  } catch (e) {
    say(apiErrorMessage(e), false)
  }
}
async function rechazar(r: Ruta) {
  resp.err = ''
  if (!resp.motivo || resp.texto.trim().length < 5) return (resp.err = 'Elige el motivo y explícalo para rechazar la ruta.')
  try {
    await api.responder(r.id, false, resp.motivo, resp.texto)
    say(`Rechazaste la ruta del ${r.periodo_txt}. Coordinación recibió el motivo y puede ajustarla.`)
    Object.assign(resp, { id: '', motivo: '', texto: '' })
    await refreshMi()
  } catch (e) {
    resp.err = apiErrorMessage(e)
  }
}
const llegando = ref(false)
async function llegar() {
  const s = M.value?.siguiente
  if (!s) return
  llegando.value = true
  try {
    await api.llegada(s.id)
    say(`✓ Llegada registrada a ${s.zona}.`)
    await refreshMi()
  } catch (e) {
    say(apiErrorMessage(e), false)
  } finally {
    llegando.value = false
  }
}
const COLOR: Record<string, string> = { ruta: 'var(--cdc-green)', cita: '#6B4FA0', mia: '#5A5D60' }
// schematic map: one stop per timeline item, laid out along the streets of M04's drawing
const PUNTOS: [number, number][] = [
  [45, 170],
  [85, 55],
  [200, 55],
  [200, 140],
  [295, 140],
  [295, 55],
  [150, 140],
]
const puntos = computed(() =>
  (M.value?.timeline ?? []).slice(0, PUNTOS.length).map((t, i) => ({ x: PUNTOS[i]![0], y: PUNTOS[i]![1], hecho: t.estado_txt.startsWith('✓'), color: COLOR[t.tipo] ?? '#5A5D60' })),
)
const yo = computed(() => {
  const P = puntos.value
  const last = P.filter((p) => p.hecho).pop()
  return last ? { x: last.x, y: last.y - 18 } : { x: 45, y: 150 }
})

// =============================================================== Team (Coordinación, Gerencia, Auxiliar)
type V = 'man' | 'xls' | 'list'
const v = ref<V>(O.value?.puede_programar && route.query.tab !== 'list' ? 'man' : 'list')
const F = reactive({ desde: '', hasta: '', asesor: '', estado: '', n: 5 })
const { data: lData, refresh: refreshL } = await useAsyncData(
  'rutas-list',
  () => (equipo.value ? api.listar({ ...(F.desde ? { desde: F.desde } : {}), ...(F.hasta ? { hasta: F.hasta } : {}), ...(F.asesor ? { asesor_id: F.asesor } : {}), ...(F.estado ? { estado: F.estado } : {}) }) : Promise.resolve(null)),
  { watch: [() => F.desde, () => F.hasta, () => F.asesor, () => F.estado] },
)
const L = computed(() => lData.value?.items ?? [])
const { data: uData } = await useAsyncData('rutas-ubic', () => (equipo.value ? api.ubicaciones() : Promise.resolve(null)))
const U = computed(() => (uData.value ?? []) as Ubicacion[])
const totalRutas = computed(() => lData.value?.total ?? 0)

// ---- form
const sumar = (iso: string, n: number) => {
  const d = new Date(`${iso}T12:00:00`)
  d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}
const finMes = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`)
  return new Date(d.getFullYear(), d.getMonth() + 1, 0, 12).toISOString().slice(0, 10)
}
const nuevaZona = (z: string, h1: string, h2: string, dias: number[]): RutaZona => ({ zona: z, hora_inicio: h1, hora_fin: h2, dias: [...dias] })
function vacio() {
  const l = O.value?.proximo_lunes ?? localDate(0)
  return { asesor: O.value?.asesores[0]?.id ?? '', per: 'sem', desde: l, hasta: sumar(l, 4), dias: [1, 2, 3, 4, 5], zonas: [nuevaZona('Laureles', '08:00', '12:00', [1, 2, 3, 4, 5])], obs: '', reemplaza: '', err: '' }
}
const R = reactive(vacio())
function periodo(k: string) {
  const l = O.value?.proximo_lunes ?? localDate(0)
  R.per = k
  if (k === 'dia') Object.assign(R, { desde: l, hasta: l })
  if (k === 'sem') Object.assign(R, { desde: l, hasta: sumar(l, 4) })
  if (k === 'mes') {
    const m1 = `${finMes(l).slice(0, 7)}-01`
    const sig = sumar(finMes(l), 1)
    const base = l.slice(8) === '01' ? m1 : sig
    Object.assign(R, { desde: base, hasta: finMes(base) })
  }
}
const tog = (arr: number[], x: number) => (arr.includes(x) ? arr.filter((y) => y !== x) : [...arr, x].sort())
function togDia(d: number) {
  R.dias = tog(R.dias, d)
  R.zonas.forEach((z) => (z.dias = z.dias.filter((x) => R.dias.includes(x))))
}
function addZona() {
  const usadas = R.zonas.map((z) => z.zona)
  R.zonas.push(nuevaZona(O.value?.zonas.find((z) => !usadas.includes(z)) ?? 'Otra zona', '14:00', '17:00', R.dias))
}
const DC: Record<number, string> = { 1: 'L', 2: 'M', 3: 'X', 4: 'J', 5: 'V', 6: 'S' }
const diasTxt = (a: number[]) => {
  const s = [...a].sort().join()
  return s === '1,2,3,4,5,6' ? 'L a S' : s === '1,2,3,4,5' ? 'L a V' : [...a].sort().map((d) => DC[d]).join('-')
}
const resumen = computed(() => {
  const n = O.value?.asesores.find((a) => a.id === R.asesor)?.nombre ?? '—'
  const per = R.desde === R.hasta ? fmtFecha(R.desde) : `${fmtFecha(R.desde)} al ${fmtFecha(R.hasta)}`
  return `${n} · ${per} · ${diasTxt(R.dias)} · ${R.zonas.map((z) => `${z.zona} (${diasTxt(z.dias)} ${z.hora_inicio}–${z.hora_fin})`).join(' · ')}`
})
async function asignar() {
  R.err = ''
  try {
    const r = await api.crear({ asesor_id: R.asesor, desde: R.desde, hasta: R.hasta, dias: R.dias, zonas: R.zonas, observacion: R.obs || null, reemplaza_id: R.reemplaza || null })
    say(`Ruta asignada a ${r.asesor} (${r.periodo_txt} · ${r.zonas.length} ${r.zonas.length === 1 ? 'zona' : 'zonas'}). Le llegó la notificación para aceptarla o rechazarla con motivo. Queda «Por aceptar» hasta que responda.`)
    Object.assign(R, vacio())
    v.value = 'list'
    await refreshL()
  } catch (e) {
    R.err = apiErrorMessage(e)
  }
}
function reenviar(r: Ruta) {
  Object.assign(R, { asesor: r.asesor_id, per: 'ran', desde: r.desde, hasta: r.hasta, dias: [...r.dias], zonas: r.zonas.map((z) => nuevaZona(z.zona, z.hora_inicio, z.hora_fin, z.dias)), obs: r.observacion ?? '', reemplaza: r.id, err: '' })
  v.value = 'man'
  say(`Ajusta la ruta de ${r.asesor} según su motivo y vuelve a enviarla.`)
}
const cancelando = ref<Ruta | null>(null)
async function cancelar() {
  const r = cancelando.value!
  cancelando.value = null
  try {
    await api.cancelar(r.id)
    say(`Ruta de ${r.asesor} cancelada. Le llegó el aviso.`)
    await refreshL()
  } catch (e) {
    say(apiErrorMessage(e), false)
  }
}
async function calificar(r: Ruta, n: number) {
  try {
    await api.calificar(r.id, n)
    say(`Ruta de ${r.asesor} calificada con ${n} de 5. Cuenta en «Rutas del equipo» del Coordinador.`)
    await refreshL()
  } catch (e) {
    say(apiErrorMessage(e), false)
  }
}

// ---- Excel (CSV)
const X = reactive({ texto: '', nombre: '', rev: null as ImportRev | null, err: '' })
const fileIn = ref<HTMLInputElement | null>(null)
async function subir(ev: Event) {
  const f = (ev.target as HTMLInputElement).files?.[0]
  ;(ev.target as HTMLInputElement).value = ''
  if (!f) return
  X.err = ''
  if (f.size > 400_000) return (X.err = 'El archivo es muy pesado.')
  X.texto = await f.text()
  X.nombre = f.name
  try {
    X.rev = await api.importar(X.texto, false)
  } catch (e) {
    X.rev = null
    X.err = apiErrorMessage(e)
  }
}
async function asignarXls() {
  try {
    const r = await api.importar(X.texto, true)
    say(`${r.asignadas} ${r.asignadas === 1 ? 'ruta asignada' : 'rutas asignadas'} desde el archivo. A cada asesor le llegó su notificación.${r.total - r.correctas ? ` Las ${r.total - r.correctas} filas con error no se asignaron: corrígelas y vuelve a subir el archivo.` : ''}`)
    Object.assign(X, { texto: '', nombre: '', rev: null })
    v.value = 'list'
    await refreshL()
  } catch (e) {
    X.err = apiErrorMessage(e)
  }
}
</script>

<template>
  <!-- ====================== M04 · Mi ruta ====================== -->
  <template v-if="!equipo">
    <PageBar title="Mi ruta de hoy" subtitle="Tu ruta del coordinador, tus citas y lo que vence hoy" :back="home" />
    <div class="cnt mob">
      <div v-if="!O?.es_captador" class="note">
        «Mi ruta» es para asesores con Captación: marcas en una sede. Si debes salir a captar, pide que te activen Captación.
      </div>
      <template v-else-if="M">
        <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.t }}</b></div>
        <div class="sb"><span class="mut t13">{{ hoyTxt }} · {{ auth.user.value?.full_name }}</span><span class="chip info">{{ M.hechos }} de {{ M.total }} hechos</span></div>

        <div v-for="r in M.por_aceptar" :key="r.id" class="pend col8">
          <div class="sb fw gp8"><b class="t13">Nueva ruta de tu coordinador · {{ r.periodo_txt }} · {{ r.dias_txt }}</b><span class="chip warn">Por aceptar</span></div>
          <div class="t125">{{ r.zonas_txt }}</div>
          <div v-if="r.observacion" class="mut t12">«{{ r.observacion }}»</div>
          <div class="row fw gp8">
            <button type="button" class="btn bp h36" @click="aceptar(r)">Aceptar ruta</button>
            <button type="button" class="btn bs h36" @click="resp.id = resp.id === r.id ? '' : r.id; resp.err = ''">{{ resp.id === r.id ? 'Cancelar' : 'Rechazar' }}</button>
          </div>
          <div v-if="resp.id === r.id" class="col8">
            <div class="fld">
              <label :for="`m-${r.id}`">Motivo <span class="req">*</span></label>
              <select :id="`m-${r.id}`" v-model="resp.motivo" class="in"><option value="">Elige</option><option v-for="(t, k) in M.motivos" :key="k" :value="k">{{ t }}</option></select>
            </div>
            <div class="fld"><label :for="`t-${r.id}`">Explica el motivo <span class="req">*</span></label><textarea :id="`t-${r.id}`" v-model="resp.texto" class="ta" rows="2" /></div>
            <div v-if="resp.err" class="note bad"><b>{{ resp.err }}</b></div>
            <button type="button" class="btn br" @click="rechazar(r)">Rechazar ruta</button>
          </div>
        </div>

        <div v-if="M.aceptadas.length" class="card col6 pad">
          <b class="t13">Mis rutas aceptadas</b>
          <div v-for="r in M.aceptadas" :key="r.id" class="t125 sep"><b>{{ r.periodo_txt }} · {{ r.dias_txt }}</b> · {{ r.zonas_txt }}</div>
        </div>

        <div class="gps">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s7-6 7-11a7 7 0 0 0-14 0c0 5 7 11 7 11z" /><circle cx="12" cy="10" r="2.5" /></svg>
          <div class="t125"><b>GPS activo</b> · funciona solo en tu jornada. Lo ven tú y tu coordinador.</div>
        </div>

        <div class="card mapa">
          <svg viewBox="0 0 358 200" role="img" aria-label="Mapa esquemático de la ruta del día">
            <rect width="358" height="200" fill="#E9EBE6" />
            <path d="M0 55 H358 M0 140 H358 M85 0 V200 M200 0 V200 M295 0 V200" stroke="#fff" stroke-width="10" />
            <polyline v-if="puntos.length > 1" :points="puntos.map((p) => `${p.x},${p.y}`).join(' ')" fill="none" stroke="#00843D" stroke-width="4" stroke-dasharray="8 6" />
            <circle v-for="(p, i) in puntos" :key="i" :cx="p.x" :cy="p.y" r="12" :fill="p.hecho ? p.color : '#fff'" :stroke="p.color" stroke-width="3" />
            <circle :cx="yo.x" :cy="yo.y" r="7" fill="#2B2D2F" stroke="#fff" stroke-width="3" />
          </svg>
          <div class="row fw ley">
            <span class="row gp4"><span class="dot" style="background: #00843d" />Ruta del coordinador</span>
            <span class="row gp4"><span class="dot" style="background: #6b4fa0" />Cita</span>
            <span class="row gp4"><span class="dot" style="background: #5a5d60" />Mi actividad</span>
            <span class="row gp4"><span class="dot" style="background: #2b2d2f" />Tú, ahora</span>
          </div>
        </div>

        <div class="card tlc">
          <component :is="t.link ? 'NuxtLink' : 'div'" v-for="t in M.timeline" :key="t.id" :to="t.link ?? undefined" class="tl">
            <span class="bar3" :style="{ background: COLOR[t.tipo] }" />
            <span class="tm">{{ t.hora }}</span>
            <div class="grow">
              <div class="sb gp8"><b>{{ t.titulo }}</b><span class="chip" :class="t.estado_cls">{{ t.estado_txt }}</span></div>
              <div class="mut t12">{{ t.sub }}</div>
            </div>
          </component>
          <div v-if="!M.timeline.length" class="mut t13 vacio">Hoy no tienes zonas de ruta, citas ni vencimientos.</div>
        </div>

        <button type="button" class="btn bp" :disabled="!M.siguiente || llegando" @click="llegar">
          {{ M.siguiente ? `Marcar llegada al siguiente punto · ${M.siguiente.zona} (${M.siguiente.hora})` : M.timeline.some((t) => t.tipo === 'ruta') ? '✓ Llegaste a todas las zonas de hoy' : 'Hoy no tienes zonas de ruta' }}
        </button>
        <NuxtLink class="btn bs" to="/agenda">Ver mi agenda de la semana</NuxtLink>
        <div class="note">Si sales de tu ruta o permaneces mucho tiempo en un mismo lugar, te llegará un aviso para justificarlo. El aviso llega a la campana solo cuando ocurre.</div>
      </template>
    </div>
  </template>

  <!-- ====================== X08 · Rutas y ubicación del equipo ====================== -->
  <template v-else-if="O">
    <PageBar
      :title="O.puede_programar ? 'Rutas y ubicación del equipo' : 'Rutas del equipo'"
      :subtitle="O.puede_programar ? 'Pones las rutas y ves dónde marca entrada cada persona del equipo' : 'Las asigna Coordinación · aquí consultas qué ruta tiene cada asesor y si la aceptó'"
      :back="home"
    />
    <div class="cnt">
      <div class="card col12" :class="{ verde: O.puede_programar }">
        <div class="sb fw gp8">
          <div>
            <div class="lbl">Programación de rutas</div>
            <div class="mut t125">
              {{ O.puede_programar ? 'Asigna rutas por día, semana, mes o rango, con 1 a 3 zonas por asesor, una por una o con plantilla de Excel' : 'Las asigna Coordinación · aquí consultas qué ruta tiene cada asesor y si la aceptó' }}
            </div>
          </div>
          <div class="tabs">
            <template v-if="O.puede_programar">
              <button type="button" class="tab" :class="{ on: v === 'man' }" @click="v = 'man'; msg = null">Asignar una por una</button>
              <button type="button" class="tab" :class="{ on: v === 'xls' }" @click="v = 'xls'; msg = null">Subir plantilla de Excel</button>
            </template>
            <button type="button" class="tab" :class="{ on: v === 'list' }" @click="v = 'list'; msg = null">Rutas asignadas ({{ totalRutas }})</button>
          </div>
        </div>
        <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.t }}</b></div>

        <!-- Asignar una por una -->
        <div v-if="v === 'man' && O.puede_programar" class="col12">
          <div v-if="R.reemplaza" class="note warn">Estás ajustando una ruta rechazada: al enviarla, la anterior queda cancelada.</div>
          <div class="g3">
            <div class="fld">
              <label for="r-as">Asesor <span class="req">*</span></label>
              <select id="r-as" v-model="R.asesor" class="in" :disabled="!!R.reemplaza"><option v-for="a in O.asesores" :key="a.id" :value="a.id">{{ a.nombre }}</option></select>
              <span class="mut t115">Solo asesores con Captación activa</span>
            </div>
            <div class="fld">
              <span class="fld-label">Período</span>
              <div class="row fw gp6">
                <button v-for="[k, t] in [['dia', 'Un día'], ['sem', 'Semana'], ['mes', 'Mes'], ['ran', 'Rango']]" :key="k" type="button" class="fch" :class="{ on: R.per === k }" @click="periodo(k!)">{{ t }}</button>
              </div>
            </div>
            <div class="row gp8 end">
              <div class="fld"><label for="r-d1">Desde <span class="req">*</span></label><input id="r-d1" v-model="R.desde" class="in" type="date" @input="R.per = 'ran'"></div>
              <div class="fld"><label for="r-d2">Hasta <span class="req">*</span></label><input id="r-d2" v-model="R.hasta" class="in" type="date" @input="R.per = 'ran'"></div>
            </div>
          </div>
          <div class="fld">
            <span class="fld-label">Días de la semana en que aplica <span class="req">*</span></span>
            <div class="row fw gp6"><button v-for="[d, t] in DIAS" :key="d" type="button" class="fch" :class="{ on: R.dias.includes(d) }" @click="togDia(d)">{{ t }}</button></div>
          </div>
          <div class="lbl">Zonas de la ruta (hasta 3)</div>
          <div v-for="(z, i) in R.zonas" :key="i" class="zona col8">
            <div class="sb"><b class="t13">Zona {{ i + 1 }}</b><button v-if="R.zonas.length > 1" type="button" class="fch" @click="R.zonas.splice(i, 1)">Quitar zona</button></div>
            <div class="row fw gp10 end">
              <div class="fld w180">
                <label :for="`z-${i}`">Zona <span class="req">*</span></label>
                <select :id="`z-${i}`" v-model="z.zona" class="in"><option v-for="x in O.zonas" :key="x" :value="x">{{ x }}</option></select>
              </div>
              <div class="fld"><label :for="`h1-${i}`">Desde la hora</label><input :id="`h1-${i}`" v-model="z.hora_inicio" class="in" type="time" step="900"></div>
              <div class="fld"><label :for="`h2-${i}`">Hasta la hora</label><input :id="`h2-${i}`" v-model="z.hora_fin" class="in" type="time" step="900"></div>
              <div class="fld">
                <span class="fld-label">Días en esta zona</span>
                <div class="row fw gp4"><button v-for="[d, t] in DIAS.filter(([d]) => R.dias.includes(d))" :key="d" type="button" class="fch" :class="{ on: z.dias.includes(d) }" @click="z.dias = tog(z.dias, d)">{{ t }}</button></div>
              </div>
            </div>
          </div>
          <button v-if="R.zonas.length < 3" type="button" class="btn bs self-start" @click="addZona">+ Agregar otra zona</button>
          <div class="fld"><label for="r-obs">Observación para el asesor</label><input id="r-obs" v-model="R.obs" class="in" placeholder="Ej.: captación de apartamentos en oferta"></div>
          <div class="note"><b>Resumen:</b> {{ resumen }}</div>
          <div v-if="R.err" class="note bad"><b>{{ R.err }}</b></div>
          <div class="row gp8">
            <button type="button" class="btn bp" @click="asignar">{{ R.reemplaza ? 'Volver a enviar la ruta ajustada' : 'Asignar ruta y notificar al asesor' }}</button>
            <button type="button" class="btn bs" @click="Object.assign(R, vacio())">Limpiar</button>
          </div>
        </div>

        <!-- Excel -->
        <div v-if="v === 'xls' && O.puede_programar" class="col10">
          <div class="row fw gp8">
            <button type="button" class="btn bs" @click="api.plantilla()">1. Descargar plantilla de Excel</button>
            <button type="button" class="btn bp" @click="fileIn?.click()">2. Subir archivo con las rutas</button>
            <input ref="fileIn" type="file" accept=".csv,text/csv" class="sr-only" aria-label="Archivo con las rutas" @change="subir">
          </div>
          <div class="wrap">
            <div class="minw900">
              <div class="xth"><span>Asesor (correo)</span><span>Desde</span><span>Hasta</span><span>Días</span><span>Zona 1 y horario</span><span>Zona 2 y horario</span><span>Zona 3 y horario</span><span>Días por zona</span><span>Observación</span></div>
              <div class="mut t12 pad4">Columnas de la plantilla · una fila por asesor y período · las zonas 2 y 3 son opcionales · días: L, M, X, J, V, S (ej.: L-X-V o L a V)</div>
            </div>
          </div>
          <div v-if="X.err" class="note bad"><b>{{ X.err }}</b></div>
          <div v-if="X.rev" class="rev">
            <div class="sb mb6"><b class="t13">Revisión del archivo · {{ X.nombre }}</b><span class="mut t12">{{ X.rev.correctas }} de {{ X.rev.total }} filas correctas · las que tienen error no se asignan</span></div>
            <div v-for="f in X.rev.filas" :key="f.fila" class="xrow">
              <b>{{ f.asesor }}</b><span>{{ f.periodo }}</span><span class="mut">{{ f.zonas }}</span>
              <span><span class="chip" :class="f.error ? 'bad' : 'ok'">{{ f.error ? `✕ ${f.error}` : '✓ Lista para asignar' }}</span></span>
            </div>
            <div class="row gp8 mt10">
              <button type="button" class="btn bp" :disabled="!X.rev.correctas" @click="asignarXls">Asignar las {{ X.rev.correctas }} rutas correctas y notificar</button>
              <button type="button" class="btn bs" @click="X.rev = null">Descartar archivo</button>
            </div>
          </div>
        </div>

        <!-- Rutas asignadas -->
        <div v-if="v === 'list'" class="col8">
          <div class="row fw gp10 end filt">
            <div class="fld"><label for="f-d1">Desde</label><input id="f-d1" v-model="F.desde" class="in h38" type="date"></div>
            <div class="fld"><label for="f-d2">Hasta</label><input id="f-d2" v-model="F.hasta" class="in h38" type="date"></div>
            <div class="fld">
              <label for="f-as">Asesor</label>
              <select id="f-as" v-model="F.asesor" class="sel"><option value="">Todos</option><option v-for="a in O.asesores" :key="a.id" :value="a.id">{{ a.nombre }}</option></select>
            </div>
            <div class="fld">
              <label for="f-e">Estado</label>
              <select id="f-e" v-model="F.estado" class="sel"><option value="">Todos</option><option v-for="(t, k) in O.estados" :key="k" :value="k">{{ t }}</option></select>
            </div>
          </div>
          <div v-for="r in L.slice(0, F.n)" :key="r.id" class="rcard" :class="r.estado">
            <div class="sb fw gp6"><span><b>{{ r.asesor }}</b> · {{ r.periodo_txt }} · {{ r.dias_txt }}</span><span class="chip" :class="r.estado_cls">{{ r.estado_txt }}</span></div>
            <div class="t13">{{ r.zonas_txt }}</div>
            <div class="mut t12">{{ r.asignada }}{{ r.observacion ? ` · «${r.observacion}»` : '' }}</div>
            <div v-if="r.motivo_txt" class="note bad">Motivo del rechazo: {{ r.motivo_txt }}</div>
            <div v-if="r.puede_calificar || r.calificacion" class="row fw gp6 estrellas">
              <span class="mut t12">Calificación de Gerencia:</span>
              <template v-if="r.puede_calificar">
                <button v-for="n in 5" :key="n" type="button" class="star" :class="{ on: (r.calificacion ?? 0) >= n }" :aria-label="`Calificar con ${n} de 5`" @click="calificar(r, n)">★</button>
              </template>
              <b v-else class="t13">{{ r.calificacion }} de 5</b>
            </div>
            <div v-if="r.puede_reenviar || r.puede_cancelar" class="row gp6">
              <button v-if="r.puede_reenviar" type="button" class="btn bp h34" @click="reenviar(r)">Ajustar y volver a enviar</button>
              <button v-if="r.puede_cancelar" type="button" class="btn br h34" @click="cancelando = r">Cancelar la ruta</button>
            </div>
          </div>
          <div v-if="!L.length" class="note">No hay rutas con estos filtros.</div>
          <div class="sb t125">
            <span class="mut">Mostrando {{ Math.min(F.n, L.length) }} de {{ L.length }}</span>
            <button v-if="L.length > 5" type="button" class="btn bs h34" @click="F.n = F.n < L.length ? F.n + 10 : 5">{{ F.n < L.length ? 'Ver más' : 'Ver menos' }}</button>
          </div>
        </div>
        <div class="mut t12">
          Al asignar, al asesor le llega la notificación y debe aceptar o rechazar con motivo. Mientras no responda, la ruta queda «Por aceptar». Cada asignación, respuesta y cambio queda
          en el registro de cambios. Zonas: la misma lista de pedidos; la lista real de zonas y los motivos de rechazo: PENDIENTE DE CONFIGURACIÓN.
        </div>
      </div>

      <div class="card col8">
        <div class="sb fw gp8">
          <span class="lbl">Ubicación y ruta de cada persona · hoy</span>
          <span class="row gp8 center">
            <span class="mut t12">{{ O.puede_programar ? 'Sale de las rutas aceptadas' : 'Lo pone Coordinación · tú consultas y descargas' }}</span>
            <button v-if="!O.puede_programar" type="button" class="btn bs h36" @click="api.bajarUbicaciones(U)">Descargar Excel</button>
          </span>
        </div>
        <div class="wrap">
          <div class="minw760">
            <div class="uth"><span>Persona</span><span>Cargo</span><span>Dónde marca hoy</span><span /></div>
            <div v-for="u in U" :key="u.id" class="utr">
              <b>{{ u.nombre }}</b><span class="mut">{{ CARGO_LABELS[u.cargo as keyof typeof CARGO_LABELS] ?? u.cargo }}</span>
              <span><span class="chip" :class="u.cls">{{ u.donde }}</span></span>
              <span class="mut t12">{{ u.nota }}</span>
            </div>
          </div>
        </div>
      </div>
      <div class="note">
        Coordinación pone las rutas (solo a asesores con Captación); la Auxiliar y Gerencia las consultan y Gerencia las califica de 1 a 5 («Rutas del equipo» del Coordinador). Quien no
        tiene ruta marca en la sede principal. Las sedes, el horario y el radio para marcar: PENDIENTE (módulo de asistencia).
      </div>
    </div>

    <ConfirmDialog v-if="cancelando" :title="`¿Cancelar la ruta de ${cancelando.asesor}?`" confirm-label="Sí, cancelar" danger @confirm="cancelar" @cancel="cancelando = null">
      {{ cancelando.periodo_txt }} · {{ cancelando.zonas_txt }}. Al asesor le llega el aviso.
    </ConfirmDialog>
  </template>
</template>

<style scoped>
.fw {
  flex-wrap: wrap;
}
.gp4 {
  gap: 4px;
}
.gp6 {
  gap: 6px;
}
.gp8 {
  gap: 8px;
}
.gp10 {
  gap: 10px;
}
.end {
  align-items: flex-end;
}
.center {
  align-items: center;
}
.grow {
  flex: 1;
  min-width: 0;
}
.self-start {
  align-self: flex-start;
}
.t115 {
  font-size: 11.5px;
}
.t12 {
  font-size: 12px;
}
.t125 {
  font-size: 12.5px;
}
.t13 {
  font-size: 13px;
}
.h34 {
  min-height: 34px;
}
.h36 {
  min-height: 36px;
}
.h38 {
  min-height: 38px;
}
.w180 {
  min-width: 180px;
}
.mb6 {
  margin-bottom: 6px;
}
.mt10 {
  margin-top: 10px;
}
.pad4 {
  padding: 6px 4px;
}
.col6,
.col8,
.col10,
.col12 {
  display: flex;
  flex-direction: column;
}
.col6 {
  gap: 6px;
}
.col8 {
  gap: 8px;
}
.col10 {
  gap: 10px;
}
.col12 {
  gap: 12px;
}
.verde {
  border: 2px solid var(--cdc-green);
}
/* M04 */
.mob {
  max-width: 560px;
}
.pend {
  background: var(--cdc-warn-bg);
  border: 1.5px solid var(--cdc-warn);
  border-radius: 14px;
  padding: 12px;
}
.pad {
  padding: 12px 14px;
}
.sep {
  border-top: 1px solid var(--cdc-border-soft);
  padding-top: 6px;
}
.gps {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  background: var(--cdc-ok-bg);
  border-radius: 14px;
  padding: 12px;
  color: var(--cdc-green-dark);
}
.gps svg {
  flex: none;
}
.mapa {
  padding: 0;
  overflow: hidden;
}
.mapa svg {
  display: block;
  width: 100%;
  height: auto;
}
.ley {
  gap: 10px;
  padding: 10px 12px;
  font-size: 11px;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
.tlc {
  padding: 4px 14px;
}
.tl {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 10px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  text-decoration: none;
  color: var(--cdc-text);
  font-size: 13.5px;
}
.tl:last-child {
  border-bottom: 0;
}
.bar3 {
  width: 4px;
  align-self: stretch;
  border-radius: 4px;
  flex: none;
}
.tm {
  width: 44px;
  flex: none;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.vacio {
  padding: 12px 0;
}
/* X08 */
.zona {
  border: 1px solid var(--cdc-border);
  border-radius: 12px;
  padding: 10px 12px;
  background: var(--cdc-bg);
}
.filt {
  background: var(--cdc-bg);
  border-radius: 12px;
  padding: 10px 12px;
}
.rcard {
  border: 1px solid var(--cdc-border);
  border-radius: 12px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.rcard.rechazada {
  border-color: var(--cdc-bad);
  background: var(--cdc-bad-bg);
}
.rcard.por_aceptar {
  border-color: var(--cdc-warn);
}
.star {
  border: 0;
  background: none;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  color: var(--cdc-border);
  padding: 0 1px;
}
.star.on {
  color: #b7791f;
}
.minw900 {
  min-width: 900px;
}
.minw760 {
  min-width: 760px;
}
.xth {
  display: grid;
  grid-template-columns: repeat(9, minmax(80px, 1fr));
  gap: 6px;
  font-size: 10.5px;
  color: var(--cdc-gray);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  padding: 6px 4px;
  border-bottom: 1px solid var(--cdc-border);
}
.rev {
  border: 1px solid var(--cdc-border);
  border-radius: 12px;
  padding: 10px;
}
.xrow {
  display: grid;
  grid-template-columns: 160px 200px minmax(0, 1fr) 280px;
  gap: 8px;
  font-size: 12.5px;
  padding: 7px 4px;
  border-bottom: 1px solid var(--cdc-border-soft);
  align-items: center;
}
.xrow .chip {
  white-space: normal;
}
.uth,
.utr {
  display: grid;
  grid-template-columns: 190px 190px minmax(0, 1fr) 240px;
  gap: 10px;
  padding: 9px 6px;
  border-bottom: 1px solid var(--cdc-border-soft);
  font-size: 13px;
  align-items: center;
}
.uth {
  font-size: 10.5px;
  color: var(--cdc-gray);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom-color: var(--cdc-border);
}
</style>
