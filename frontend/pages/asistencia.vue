<script setup lang="ts">
import type { AsConfig, AsEquipo, AsMia, AsPendiente } from '~/types/asistencia'

/**
 * Asistencia (G-048 … G-051).
 * - «Mi asistencia» (Z04): one button to mark entrada and salida with the browser's location.
 * - «Asistencia y ausencias» (K17): Coordinación, the Auxiliar and Gerencia; reviews and today.
 * - «Sedes y horario» (X08): the Auxiliar and Gerencia edit; Coordinación changes asesores' sede.
 */
definePageMeta({ cargos: ['asesor', 'atencion_cliente', 'coordinacion', 'auxiliar_administrativa', 'gerencia'] })
useHead({ title: 'Asistencia · Casa Dolce Casa' })

const api = useAsistencia()
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const cargo = computed(() => auth.user.value?.cargo ?? '')
const veEquipo = computed(() => ['coordinacion', 'auxiliar_administrativa', 'gerencia'].includes(cargo.value))
const home = computed(() => (['gerencia', 'coordinacion'].includes(cargo.value) ? '/coordinacion' : '/'))

const { data: mData, refresh: refreshMia } = await useAsyncData('as-mia', () => api.mia())
const M = computed(() => mData.value as AsMia | null)
type Tab = 'mia' | 'equipo' | 'sedes'
const inicial = (): Tab => {
  const q = String(route.query.tab ?? '')
  if (q === 'equipo' && veEquipo.value) return 'equipo'
  if (q === 'sedes' && veEquipo.value) return 'sedes'
  return M.value?.marca ? 'mia' : 'equipo'
}
const tab = ref<Tab>(inicial())
watch(tab, (t) => router.replace({ query: t === 'mia' ? {} : { tab: t } }))
const msg = ref<{ t: string; ok: boolean } | null>(null)
const say = (t: string, ok = true) => (msg.value = { t, ok })

// =============================================================== Mi asistencia
const busy = ref(false)
const V = reactive({ on: false, que: 'entrada' as 'entrada' | 'salida', titulo: '', detalle: '', opciones: {} as Record<string, string>, motivo: '', texto: '', err: '', pos: null as { lat: number; lng: number } | null })
const toast = ref(true)
async function marcar(que: 'entrada' | 'salida', extra: object = {}) {
  busy.value = true
  msg.value = null
  try {
    const pos = V.on ? V.pos : await ubicacionActual()
    const r = await (que === 'entrada' ? api.entrada : api.salida)({ ...(pos ?? {}), ...extra })
    if (!r.ok && r.requiere_justificacion) {
      Object.assign(V, { on: true, que, titulo: r.titulo, detalle: r.detalle, opciones: r.opciones ?? {}, motivo: Object.keys(r.opciones ?? {})[0] ?? '', texto: '', err: '', pos })
      return
    }
    V.on = false
    const f = r.marcacion!
    if (que === 'entrada') {
      say(
        f.entrada_estado === 'por_aprobar'
          ? `Justificación enviada · ${f.entrada}. Marcaste fuera de tu ubicación asignada. ${M.value?.revisa} la revisa; si la acepta, vale esa hora.`
          : `✓ Entrada registrada · ${f.entrada} · ${f.entrada_txt} · ${f.asignada}. Reporte enviado.${f.minutos_tarde ? ' Los minutos se descuentan del salario.' : ''}`,
        f.entrada_estado === 'a_tiempo',
      )
    } else {
      say(`✓ Salida registrada · ${f.salida} · ${f.salida_txt}.`, f.salida_tipo === 'marcada')
    }
    await Promise.all([refreshMia(), veEquipo.value ? refreshEq() : null])
  } catch (e) {
    say(apiErrorMessage(e), false)
  } finally {
    busy.value = false
  }
}
async function enviarJustificacion() {
  V.err = ''
  if (V.texto.trim().length < 5) return (V.err = 'Justifica brevemente (al menos unas palabras).')
  await marcar(V.que, { motivo: V.motivo, texto: V.texto })
}

// =============================================================== Equipo
const hoy = localDate(0)
const R = reactive({ desde: hoy, hasta: hoy })
const rErr = computed(() => !R.desde || !R.hasta || R.desde > R.hasta)
const rq = computed(() => (rErr.value ? { desde: hoy, hasta: hoy } : { ...R }))
const { data: eData, refresh: refreshEq } = await useAsyncData('as-equipo', () => (veEquipo.value ? api.equipo(rq.value) : Promise.resolve(null)), { watch: [rq] })
const E = computed(() => eData.value as AsEquipo | null)
const QUIEN: Record<string, string> = { coordinacion: 'Coordinación aprueba', auxiliar_administrativa: 'Auxiliar administrativa aprueba salidas y horas extra', gerencia: 'Gerencia consulta, descarga y aprueba lo del Coordinador y la Auxiliar' }
const quien = computed(() => QUIEN[cargo.value] ?? '')
const hechos = reactive<Record<string, { t: string; ok: boolean }>>({})
async function revisar(p: AsPendiente, acepta: boolean) {
  const k = `${p.id}:${p.que}`
  try {
    await api.revisar(p.id, p.que, acepta)
    const nom = p.nombre.split(' · ')[0]
    hechos[k] = {
      ok: acepta,
      t:
        p.que === 'entrada'
          ? acepta
            ? `✓ Aceptada: vale la hora marcada de ${nom}.`
            : `Rechazada. Se le envió a ${nom}: «Marca entrada cuando estés en la sede o ubicación asignada». Hasta que la registre es impuntualidad.`
          : p.que === 'salida'
            ? acepta
              ? '✓ Salida anticipada aceptada: no se descuenta.'
              : 'Rechazada: el tiempo no trabajado se descuenta del salario. Se le avisó a la persona.'
            : acepta
              ? '✓ Respondiste: aceptas las horas extra. Cuando acepten Coordinación y la Auxiliar pasan a Salarios.'
              : 'No aceptaste las horas extra: no pasan a Salarios.',
    }
    await refreshEq()
  } catch (e) {
    hechos[k] = { ok: false, t: apiErrorMessage(e) }
  }
}
const resueltos = computed(() => Object.entries(hechos).filter(([k]) => !E.value?.por_aprobar.some((p) => `${p.id}:${p.que}` === k)))

// =============================================================== Sedes y horario
const { data: cData, refresh: refreshCfg } = await useAsyncData('as-config', () => (veEquipo.value ? api.config() : Promise.resolve(null)))
const CF = computed(() => cData.value as AsConfig | null)
const H = reactive<Record<string, unknown>>({})
watch(
  CF,
  (c) => {
    if (c) Object.assign(H, JSON.parse(JSON.stringify(c.config)))
  },
  { immediate: true },
)
async function guardarHorario() {
  try {
    await api.guardarConfig({ ...H })
    say('✓ Horario y reglas guardados. Aplican desde la próxima marcación y quedan en el registro de cambios.')
    await Promise.all([refreshCfg(), refreshMia()])
  } catch (e) {
    say(apiErrorMessage(e), false)
  }
}
const S = reactive({ on: false, nombre: '', direccion: '', lat: '', lng: '', radio: 100, err: '', tomando: false })
async function tomarUbicacion() {
  S.tomando = true
  const p = await ubicacionActual()
  S.tomando = false
  if (!p) return (S.err = 'El navegador no dio la ubicación: escribe las coordenadas.')
  S.lat = p.lat.toFixed(6)
  S.lng = p.lng.toFixed(6)
}
async function guardarSede() {
  S.err = ''
  try {
    await api.crearSede({ nombre: S.nombre, direccion: S.direccion, lat: Number(S.lat), lng: Number(S.lng), radio_m: S.radio })
    say(`✓ Sede «${S.nombre}» guardada.`)
    Object.assign(S, { on: false, nombre: '', direccion: '', lat: '', lng: '', radio: 100 })
    await refreshCfg()
  } catch (e) {
    S.err = apiErrorMessage(e)
  }
}
async function sedeAccion(id: string, body: object, t: string) {
  try {
    await api.editarSede(id, body)
    say(t)
    await refreshCfg()
  } catch (e) {
    say(apiErrorMessage(e), false)
  }
}
async function asignar(userId: string, sedeId: string, nombre: string) {
  try {
    await api.asignar(userId, sedeId)
    say(`✓ Ubicación de ${nombre} actualizada. Desde ahora solo puede marcar entrada allí.`)
    await refreshCfg()
  } catch (e) {
    say(apiErrorMessage(e), false)
  }
}
const sedesActivas = computed(() => CF.value?.sedes.filter((s) => s.activa) ?? [])
</script>

<template>
  <PageBar
    :title="tab === 'mia' ? 'Mi asistencia' : tab === 'equipo' ? 'Asistencia y ausencias' : 'Sedes, ubicaciones y horarios'"
    :subtitle="
      tab === 'mia'
        ? `${M?.quien} · marcar entrada y salida con la ubicación del navegador o el GPS del celular`
        : tab === 'equipo'
          ? `Entradas y salidas, justificaciones por aprobar, impuntualidad y horas extra · ${quien}`
          : 'Sedes, horario de la empresa, reglas de puntualidad y dónde marca cada persona'
    "
    :back="home"
  >
    <div class="row fw gp8 center">
      <div v-if="veEquipo" class="tabs">
        <button v-if="M?.marca" type="button" class="tab" :class="{ on: tab === 'mia' }" @click="tab = 'mia'; msg = null">Mi asistencia</button>
        <button type="button" class="tab" :class="{ on: tab === 'equipo' }" @click="tab = 'equipo'; msg = null">Asistencia y ausencias</button>
        <button type="button" class="tab" :class="{ on: tab === 'sedes' }" @click="tab = 'sedes'; msg = null">Sedes y horario</button>
      </div>
      <template v-if="tab === 'equipo'">
        <NuxtLink class="btn bs" to="/novedades">Ausencias y permisos ›</NuxtLink>
        <label class="row gp6 flt">Desde<input v-model="R.desde" class="in dt" type="date" aria-label="Fecha desde"></label>
        <label class="row gp6 flt">Hasta<input v-model="R.hasta" class="in dt" type="date" aria-label="Fecha hasta"></label>
        <button v-if="E?.puede_descargar" type="button" class="btn bp" @click="api.descargar(rq)">Descargar Excel</button>
      </template>
    </div>
  </PageBar>

  <div class="cnt">
    <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'warn'" role="status"><b>{{ msg.t }}</b></div>

    <!-- ====================== Z04 · Mi asistencia ====================== -->
    <template v-if="tab === 'mia' && M">
      <div v-if="!M.marca" class="note">Tu cargo no marca entrada y salida. La Auxiliar administrativa o Gerencia lo activan en «Sedes y horario».</div>
      <template v-else>
        <div v-if="M.recordar_salida && toast" class="card toast">
          <span class="grow"><b class="t15">Recuerda marcar salida</b><br><span class="mut t125">Tu turno termina a las {{ M.fin }}. Este aviso aparece unos minutos antes.</span></span>
          <button type="button" class="btn bp" @click="toast = false">OK</button>
          <button type="button" class="btn bs w44" aria-label="Cerrar" @click="toast = false">✕</button>
        </div>
        <div class="g3">
          <div class="card"><div class="lbl">Mi horario de hoy</div><div class="t18 b8">{{ M.horario_hoy }}</div><div class="mut t12">{{ M.horario_txt }}</div></div>
          <div class="card"><div class="lbl">Mi ubicación asignada</div><div class="t16 b8">{{ M.ubicacion }}</div><div class="mut t12">{{ M.ubicacion_det }}</div></div>
          <div class="card">
            <div class="lbl">Puntualidad de {{ M.mes }}</div><div class="t18 b8">{{ M.puntualidad.txt }}</div>
            <div class="mut t12">calculada por el sistema{{ M.puntualidad.puntaje ? ` · ${M.puntualidad.puntaje} de 5` : '' }} · pasa a «Mis resultados»</div>
          </div>
        </div>

        <div v-if="M.preop_pendiente" class="note warn row fw gp8 center">
          <b>Primero haz tu preoperacional de hoy: después marcas la entrada.</b>
          <NuxtLink to="/preoperacional" class="btn bp h36">Hacer preoperacional</NuxtLink>
        </div>

        <div class="split2">
          <div class="card col12">
            <div class="sb"><span class="lbl">Entrada</span><span class="chip" :class="M.entrada_cls">{{ M.entrada_txt }}</span></div>
            <template v-if="M.puede_entrada">
              <button type="button" class="btn bp big" :disabled="busy || M.preop_pendiente" @click="marcar('entrada')">{{ busy ? 'Ubicándote…' : M.hoy?.entrada_estado === 'rechazada' ? 'Marcar entrada de nuevo' : 'Marcar entrada' }}</button>
              <span class="mut t12 tc">La fecha, la hora y tu ubicación se registran solas al tocar el botón. Puedes marcar hasta las {{ M.limite }}.</span>
            </template>
            <div v-else-if="M.hoy?.entrada" class="note" :class="M.hoy.entrada_estado === 'a_tiempo' ? 'ok' : M.hoy.entrada_estado === 'rechazada' ? 'bad' : 'warn'">
              <b class="t15">{{ M.hoy.entrada_estado === 'por_aprobar' ? `Justificación enviada · ${M.hoy.entrada}` : `✓ Entrada registrada · ${M.hoy.entrada}` }}</b><br>
              {{ M.hoy.entrada_estado === 'por_aprobar' ? `Marcaste fuera de tu ubicación asignada (${M.hoy.entrada_lugar}). ${M.revisa} la revisa; si la acepta, vale esa hora.` : `${M.hoy.entrada_txt} · ${M.hoy.entrada_lugar}. Reporte enviado.${M.hoy.minutos_descuento ? ' Los minutos se descuentan del salario.' : ''}` }}
            </div>
            <div v-else-if="M.pasado_limite" class="note bad"><b>Ya pasó el límite para marcar entrada ({{ M.limite }}).</b> Habla con Coordinación: el día queda sin entrada.</div>
            <div v-else class="mut t13">{{ M.horario_hoy }}</div>
            <div v-if="M.hoy?.entrada_estado === 'rechazada'" class="note bad">
              <b>«Marca entrada cuando estés en la sede o ubicación asignada».</b><br>Hasta que la registres se considera impuntualidad y se descuenta del salario.
            </div>
          </div>
          <div class="card col12">
            <div class="sb"><span class="lbl">Salida</span><span class="chip" :class="M.salida_cls">{{ M.salida_txt }}</span></div>
            <template v-if="M.puede_salida">
              <button type="button" class="btn bp big" :disabled="busy" @click="marcar('salida')">{{ busy ? 'Ubicándote…' : 'Marcar salida' }}</button>
              <span class="mut t12 tc">Tu turno termina a las {{ M.fin }}.</span>
            </template>
            <span v-else-if="!M.hoy?.salida" class="mut t13">Disponible después de marcar la entrada.</span>
            <div v-if="M.hoy?.salida" class="note" :class="M.hoy.salida_tipo === 'marcada' ? 'ok' : 'warn'">
              <b class="t15">✓ Salida registrada · {{ M.hoy.salida }}</b><br>
              {{
                M.hoy.salida_tipo === 'anticipada'
                  ? `Salida antes de hora con motivo enviado (${M.hoy.salida_txt}). ${M.revisa === 'Gerencia' ? 'Gerencia' : 'Coordinación o la Auxiliar'} la acepta o la rechaza.`
                  : M.hoy.salida_tipo === 'extra'
                    ? `${M.hoy.salida_txt}: ${M.revisa === 'Gerencia' ? 'Gerencia decide' : 'Coordinación y la Auxiliar deciden'} si aceptan las horas extra.`
                    : 'Turno completo. Reporte enviado.'
              }}
            </div>
          </div>
        </div>

        <div v-if="veEquipo && E" class="card">
          <div class="sb mb6 fw gp8">
            <span class="lbl">Entrada y salida de mi equipo · hoy</span>
            <button type="button" class="btn bs h36" @click="tab = 'equipo'">Aprobar o rechazar y ver el mes ›</button>
          </div>
          <div class="wrap">
            <div class="tb t5">
              <div class="th"><span>Persona</span><span>Ubicación asignada</span><span>Dónde marcó</span><span>Entrada</span><span>Estado</span></div>
              <div v-for="r in E.filas_hoy" :key="r.user_id" class="tr"><b>{{ r.nombre }}</b><span class="mut">{{ r.asignada }}</span><span>{{ r.donde }}</span><b class="num">{{ r.entrada }}</b><span><span class="chip" :class="r.cls">{{ r.estado }}</span></span></div>
            </div>
          </div>
          <div class="mut t12 mt6">Las salidas se ven al final de la jornada.</div>
        </div>

        <div class="card">
          <div class="lbl mb8">Mi registro · últimos 30 días</div>
          <div class="wrap">
            <div class="tb t6">
              <div class="th"><span>Día</span><span>Entrada</span><span>Estado</span><span>Salida</span><span>Estado de salida</span><span>Observación</span></div>
              <div v-for="r in M.registro" :key="r.id" class="tr">
                <span>{{ fmtFecha(r.fecha) }}</span><b class="num">{{ r.entrada ?? '—' }}</b><span><span class="chip" :class="r.entrada_cls">{{ r.entrada_txt }}</span></span>
                <span class="num">{{ r.salida ?? '—' }}</span><span><span class="chip" :class="r.salida_cls">{{ r.salida_txt }}</span></span><span class="mut t125">{{ r.observacion }}</span>
              </div>
            </div>
          </div>
          <div v-if="!M.registro.length" class="mut t13">Todavía no tienes marcaciones anteriores.</div>
        </div>
        <div class="note">
          Un solo botón: al tocarlo se registran solas la fecha, la hora y la ubicación, y se envía el reporte (a tiempo o impuntual). La entrada solo se puede marcar dentro de la ubicación
          asignada; se puede marcar hasta {{ CF?.config.limite_min ?? 30 }} minutos después de la hora de entrada. Leve y grave son impuntualidad y los minutos se descuentan del salario.
        </div>
      </template>
    </template>

    <!-- ====================== K17 · Asistencia y ausencias ====================== -->
    <template v-if="tab === 'equipo' && E">
      <div v-if="rErr" class="note bad"><b>La fecha «Desde» no puede ser posterior a «Hasta». Se muestra hoy mientras lo corriges.</b></div>
      <div class="g4">
        <div class="card"><div class="lbl">Marcaron entrada hoy</div><div class="kn num">{{ E.kpis.marcaron }} / {{ E.kpis.total }}</div><div class="mut t12">{{ E.kpis.faltan.length ? `falta${E.kpis.faltan.length > 1 ? 'n' : ''} ${E.kpis.faltan.join(', ')}` : 'todos marcaron' }}</div></div>
        <div class="card amar"><div class="lbl">Por aprobar</div><div class="kn num">{{ E.kpis.por_aprobar }}</div><div class="mut t12">tuyas · {{ E.kpis.pendientes }} en total</div></div>
        <div class="card rosa"><div class="lbl">Impuntualidad en el rango</div><div class="kn num">{{ E.kpis.leves }} {{ E.kpis.leves === 1 ? 'leve' : 'leves' }} · {{ E.kpis.graves }} {{ E.kpis.graves === 1 ? 'grave' : 'graves' }}</div><div class="mut t12">{{ E.kpis.minutos }} minutos se descuentan del salario</div></div>
        <div class="card"><div class="lbl">Horas extra aceptadas</div><div class="kn num">{{ (E.kpis.extra / 60).toFixed(1).replace('.', ',').replace(',0', '') }} h</div><div class="mut t12">en el rango · pasan a Salarios</div></div>
      </div>

      <div class="card col8">
        <div class="lbl">Por aprobar</div>
        <div v-for="p in E.por_aprobar" :key="`${p.id}:${p.que}`" class="pend col8">
          <div class="sb fw gp10">
            <span><span class="chip" :class="p.tcls">{{ p.tipo }}</span> <b>{{ p.nombre }}</b><br><span class="mut t125">{{ p.detalle }}</span><br><span class="t13">{{ p.justificacion }}</span></span>
            <span class="chip warn">{{ p.estado }}</span>
          </div>
          <div v-if="p.puede" class="row fw gp8">
            <button type="button" class="btn bp" @click="revisar(p, true)">{{ p.que === 'extra' ? 'Aceptar horas extra' : 'Aceptar' }}</button>
            <button type="button" class="btn bs" @click="revisar(p, false)">{{ p.que === 'extra' ? 'No aceptar' : 'Rechazar' }}</button>
          </div>
          <span v-else class="mut t12">{{ p.quien }}</span>
          <div v-if="hechos[`${p.id}:${p.que}`]" class="note" :class="hechos[`${p.id}:${p.que}`]!.ok ? 'ok' : 'bad'"><b>{{ hechos[`${p.id}:${p.que}`]!.t }}</b></div>
        </div>
        <div v-for="[k, h] in resueltos" :key="k" class="note" :class="h.ok ? 'ok' : 'bad'"><b>{{ h.t }}</b></div>
        <div v-if="!E.por_aprobar.length && !resueltos.length" class="note ok"><b>✓ No hay nada por aprobar.</b></div>
      </div>

      <div class="card">
        <div class="lbl mb8">Hoy · {{ fmtFecha(E.hoy) }}{{ E.entrada_hoy ? ` · entrada ${E.entrada_hoy}` : ' · sin jornada' }}</div>
        <div class="wrap">
          <div class="tb t6h">
            <div class="th"><span>Persona</span><span>Ubicación asignada</span><span>Dónde marcó</span><span>Entrada</span><span>Estado</span><span>Salida</span></div>
            <div v-for="r in E.filas_hoy" :key="r.user_id" class="tr">
              <b>{{ r.nombre }}</b><span class="mut">{{ r.asignada }}</span><span>{{ r.donde }}</span><b class="num">{{ r.entrada }}</b><span><span class="chip" :class="r.cls">{{ r.estado }}</span></span><span class="mut">{{ r.salida }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="E.registro.length && (E.desde !== E.hasta || E.desde !== E.hoy)" class="card">
        <div class="lbl mb8">Registro del {{ fmtFecha(E.desde) }} al {{ fmtFecha(E.hasta) }} ({{ E.registro.length }})</div>
        <div class="wrap">
          <div class="tb t7r">
            <div class="th"><span>Persona</span><span>Día</span><span>Entrada</span><span>Estado</span><span>Salida</span><span>Estado de salida</span><span>Observación</span></div>
            <div v-for="r in E.registro" :key="r.id" class="tr">
              <b>{{ r.nombre }}</b><span>{{ fmtFecha(r.fecha) }}</span><b class="num">{{ r.entrada ?? '—' }}</b><span><span class="chip" :class="r.entrada_cls">{{ r.entrada_txt }}</span></span>
              <span class="num">{{ r.salida ?? '—' }}</span><span><span class="chip" :class="r.salida_cls">{{ r.salida_txt }}</span></span><span class="mut t12">{{ r.observacion }}</span>
            </div>
          </div>
        </div>
      </div>
      <div class="note">
        Entrada fuera de la ubicación asignada: la aprueba Coordinación (las del Coordinador y la Auxiliar, Gerencia). Si la rechaza, a la persona le llega «Marca entrada cuando estés en la
        sede o ubicación asignada»; hasta que la registre se considera impuntualidad y esos minutos se descuentan del salario. Salida anticipada: la aprueba Coordinación o la Auxiliar
        administrativa. Horas extra: las aceptan Coordinación y la Auxiliar administrativa. Las ausencias con permiso o incapacidad se registran en «Ausencias y permisos».
      </div>
    </template>

    <!-- ====================== X08 · Sedes y horario ====================== -->
    <template v-if="tab === 'sedes' && CF">
      <div class="card col10">
        <div class="sb"><span class="lbl">Sedes de la empresa</span><button v-if="CF.puede_editar" type="button" class="btn bp" @click="S.on = !S.on">{{ S.on ? 'Cancelar' : '+ Agregar sede' }}</button></div>
        <div v-for="s in CF.sedes" :key="s.id" class="sb srow fw gp10">
          <span><b>{{ s.nombre }}</b> <span v-if="s.principal" class="chip ok">Principal</span><span v-if="!s.activa" class="chip gray">Inactiva</span><br><span class="mut t125">{{ s.direccion }} · {{ s.lat.toFixed(4) }}, {{ s.lng.toFixed(4) }}</span></span>
          <span class="row fw gp6">
            <span class="chip gray">Radio {{ s.radio_m }} m</span><span class="chip info">{{ s.personas }} persona{{ s.personas === 1 ? '' : 's' }}</span>
            <template v-if="CF.puede_editar && s.activa && !s.principal">
              <button type="button" class="fch" @click="sedeAccion(s.id, { principal: true }, `${s.nombre} es ahora la sede principal.`)">Hacer principal</button>
              <button type="button" class="fch" @click="sedeAccion(s.id, { activa: false }, `${s.nombre} desactivada.`)">Desactivar</button>
            </template>
          </span>
        </div>
        <div v-if="S.on" class="form">
          <div class="fld"><label for="s-n">Nombre de la sede <span class="req">*</span></label><input id="s-n" v-model="S.nombre" class="in" placeholder="Ej.: Punto de atención Envigado"></div>
          <div class="fld"><label for="s-d">Dirección <span class="req">*</span></label><input id="s-d" v-model="S.direccion" class="in" placeholder="Dirección completa"></div>
          <div class="fld"><label for="s-r">Radio permitido para marcar</label><select id="s-r" v-model.number="S.radio" class="in"><option :value="50">50 m</option><option :value="100">100 m</option><option :value="200">200 m</option></select></div>
          <div class="fld"><label for="s-lat">Latitud <span class="req">*</span></label><input id="s-lat" v-model="S.lat" class="in" inputmode="decimal"></div>
          <div class="fld"><label for="s-lng">Longitud <span class="req">*</span></label><input id="s-lng" v-model="S.lng" class="in" inputmode="decimal"></div>
          <button type="button" class="btn bs" :disabled="S.tomando" @click="tomarUbicacion">{{ S.tomando ? 'Ubicando…' : 'Tomar mi ubicación' }}</button>
          <button type="button" class="btn bp" @click="guardarSede">Guardar sede</button>
          <div v-if="S.err" class="note bad full"><b>{{ S.err }}</b></div>
        </div>
        <div class="mut t12">Sin mapas conectados todavía, la ubicación de la sede se toma estando allí («Tomar mi ubicación») o se escriben sus coordenadas. Las personas solo pueden marcar entrada dentro del radio de su ubicación asignada.</div>
      </div>

      <div class="card col10">
        <div class="lbl">Horario de actividad de la empresa · el sistema usa este horario para marcar entrada y salida</div>
        <fieldset :disabled="!CF.puede_editar" class="col10 plain">
          <div class="g4b">
            <div class="fld"><label for="h1">Lun a vie · entrada</label><input id="h1" v-model="H.entrada_lv" class="in" type="time" step="900"></div>
            <div class="fld"><label for="h2">Lun a vie · salida</label><input id="h2" v-model="H.salida_lv" class="in" type="time" step="900"></div>
            <div class="fld"><label for="h3">Sábado · entrada</label><input id="h3" v-model="H.entrada_sab" class="in" type="time" step="900"></div>
            <div class="fld"><label for="h4">Sábado · salida</label><input id="h4" v-model="H.salida_sab" class="in" type="time" step="900"></div>
          </div>
          <div class="g4b">
            <div class="fld"><label for="h5">Se puede marcar entrada hasta</label><select id="h5" v-model.number="H.limite_min" class="in"><option v-for="n in [15, 30, 45, 60]" :key="n" :value="n">{{ n }} minutos después</option></select></div>
            <div class="fld"><label for="h6">Impuntualidad leve</label><select id="h6" v-model.number="H.leve_max" class="in"><option v-for="n in [5, 10, 15]" :key="n" :value="n">1 a {{ n }} minutos</option></select></div>
            <div class="fld"><span class="fld-label">Impuntualidad grave</span><div class="in fake">Desde el minuto siguiente a «leve» hasta el límite para marcar</div></div>
            <div class="fld"><label for="h7">Recordatorio de salida</label><select id="h7" v-model.number="H.recordatorio_min" class="in"><option v-for="n in [5, 10, 15]" :key="n" :value="n">{{ n }} minutos antes</option></select></div>
            <div class="fld"><label for="h8">Horas extra desde</label><select id="h8" v-model.number="H.extra_min" class="in"><option v-for="n in [15, 30, 60]" :key="n" :value="n">{{ n }} minutos después de la salida</option></select></div>
            <div class="fld"><label for="h9">Radio de las zonas de ruta</label><select id="h9" v-model.number="H.radio_zona_m" class="in"><option v-for="n in [1000, 2000, 3000]" :key="n" :value="n">{{ n / 1000 }} km desde el centro</option></select></div>
          </div>
          <label class="row gp8 t13"><input v-model="H.exigir_preoperacional" type="checkbox"> Pedir el preoperacional antes de marcar entrada (a quien lo hace)</label>
          <div class="lbl">Quién marca entrada y salida · por cargo</div>
          <div class="cargos">
            <div v-for="(t, k) in CF.cargos" :key="k" class="cg">
              <b class="t13">{{ t }}</b>
              <button type="button" class="btn self-start" :class="(H.marcan as Record<string, boolean>)?.[k] ? 'bp' : 'bs'" @click="(H.marcan as Record<string, boolean>)[k] = !(H.marcan as Record<string, boolean>)[k]">{{ (H.marcan as Record<string, boolean>)?.[k] ? '✓ Activo' : 'Desactivado' }}</button>
            </div>
          </div>
        </fieldset>
        <div class="row fw gp10 center">
          <button v-if="CF.puede_editar" type="button" class="btn bp" @click="guardarHorario">Guardar horario y reglas</button>
          <span class="mut t12">Lo configuran la Auxiliar administrativa y Gerencia. Valores de ejemplo. Leve y grave son impuntualidad; los minutos se descuentan del salario. Quedan en el registro de cambios.</span>
        </div>
      </div>

      <div class="card col8">
        <div class="sb fw gp8"><span class="lbl">Dónde marca cada persona</span><span class="mut t12">{{ cargo === 'coordinacion' ? 'Tú cambias la sede de asesores y Atención; las rutas se ponen en «Rutas»' : 'Las rutas las pone Coordinación en «Rutas»' }}</span></div>
        <div class="wrap">
          <div class="tb t5p">
            <div class="th"><span>Persona</span><span>Cargo</span><span>Dónde marca ahora</span><span>Sede asignada</span><span>Último cambio</span></div>
            <div v-for="u in CF.personas" :key="u.id" class="tr">
              <b>{{ u.nombre }}</b><span class="mut">{{ CF.cargos[u.cargo] }}</span><span><span class="chip" :class="u.ubicacion.startsWith('En ruta') ? 'warn' : 'ok'">{{ u.ubicacion }}</span></span>
              <span>
                <select v-if="u.puede_cambiar" class="sel w100" :value="u.sede_id ?? sedesActivas.find((s) => s.principal)?.id" :aria-label="`Sede de ${u.nombre}`" @change="asignar(u.id, ($event.target as HTMLSelectElement).value, u.nombre)">
                  <option v-for="s in sedesActivas" :key="s.id" :value="s.id">{{ s.nombre }}</option>
                </select>
                <span v-else class="mut t12">{{ cargo === 'coordinacion' && u.cargo === 'coordinacion' ? 'Tu ubicación: sede principal' : 'La cambia la Auxiliar' }}</span>
              </span>
              <span class="mut t12">{{ u.cambio ?? 'Por defecto' }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>

  <!-- Justification window (G-049) -->
  <div v-if="V.on" class="velo" role="dialog" aria-modal="true" :aria-label="V.titulo">
    <div class="card vent col12">
      <b class="t18 rojo">{{ V.titulo }}</b>
      <span class="t135">{{ V.detalle }}</span>
      <div class="row fw gp6"><button v-for="(t, k) in V.opciones" :key="k" type="button" class="opt" :class="{ on: V.motivo === k }" @click="V.motivo = String(k)">{{ t }}</button></div>
      <textarea v-model="V.texto" class="in ta" placeholder="Justifica brevemente" aria-label="Justificación" />
      <div v-if="V.err" class="note bad"><b>{{ V.err }}</b></div>
      <div class="row gp8"><button type="button" class="btn bp grow h48" :disabled="busy" @click="enviarJustificacion">Enviar</button><button type="button" class="btn bs h48" @click="V.on = false">Cancelar</button></div>
    </div>
  </div>
</template>

<style scoped>
.fw {
  flex-wrap: wrap;
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
.center {
  align-items: center;
}
.grow {
  flex: 1;
  min-width: 200px;
}
.self-start {
  align-self: flex-start;
}
.full {
  grid-column: 1 / -1;
}
.flt {
  font-size: 13px;
  font-weight: 700;
}
.dt {
  min-height: 38px;
  width: auto;
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
.t135 {
  font-size: 13.5px;
}
.t15 {
  font-size: 15px;
}
.t16 {
  font-size: 16px;
}
.t18 {
  font-size: 18px;
}
.b8 {
  font-weight: 800;
}
.tc {
  text-align: center;
}
.mb6 {
  margin-bottom: 6px;
}
.mb8 {
  margin-bottom: 8px;
}
.mt6 {
  margin-top: 6px;
}
.h36 {
  min-height: 36px;
}
.h48 {
  min-height: 48px;
}
.w44 {
  min-width: 44px;
}
.col8,
.col10,
.col12 {
  display: flex;
  flex-direction: column;
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
.split2 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
  align-items: start;
}
.big {
  min-height: 64px;
  font-size: 20px;
}
.toast {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  border: 2px solid var(--cdc-warn);
  background: var(--cdc-warn-bg);
}
.amar {
  background: var(--cdc-warn-bg);
  border-color: var(--cdc-warn);
}
.rosa {
  background: var(--cdc-bad-bg);
  border-color: var(--cdc-bad);
}
.pend {
  border: 1px solid var(--cdc-border);
  border-radius: 12px;
  padding: 12px;
}
.tb {
  display: grid;
}
.th,
.tr {
  display: grid;
  gap: 10px;
  padding: 9px 6px;
  font-size: 13px;
  align-items: center;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.th {
  font-size: 10.5px;
  font-weight: 700;
  color: var(--cdc-gray);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom-color: var(--cdc-border);
}
.t5 {
  min-width: 680px;
}
.t5 .th,
.t5 .tr {
  grid-template-columns: 1.2fr 1.3fr 1.1fr 90px 1.2fr;
}
.t6 {
  min-width: 860px;
}
.t6 .th,
.t6 .tr {
  grid-template-columns: 110px 100px 200px 100px 220px minmax(0, 1fr);
}
.t6h {
  min-width: 900px;
}
.t6h .th,
.t6h .tr {
  grid-template-columns: 160px 170px 170px 100px 210px minmax(0, 1fr);
}
.t7r {
  min-width: 1060px;
}
.t7r .th,
.t7r .tr {
  grid-template-columns: 150px 100px 100px 210px 100px 220px minmax(0, 1fr);
}
.t5p {
  min-width: 860px;
}
.t5p .th,
.t5p .tr {
  grid-template-columns: 170px 150px minmax(0, 1fr) 210px 200px;
}
.srow {
  padding: 10px 0;
  border-top: 1px solid var(--cdc-border-soft);
}
.form {
  border: 2px solid var(--cdc-green);
  border-radius: 12px;
  padding: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
  align-items: end;
}
.g4b {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
  align-items: end;
}
.fake {
  display: flex;
  align-items: center;
  background: var(--cdc-bg);
  font-size: 12.5px;
}
.plain {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.cargos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 8px;
}
.cg {
  border: 1px solid var(--cdc-border);
  border-radius: 12px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.w100 {
  width: 100%;
  max-width: 100%;
}
.velo {
  position: fixed;
  inset: 0;
  background: rgba(20, 22, 24, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 16px;
}
.vent {
  max-width: 460px;
  width: 100%;
  border: 2px solid var(--cdc-bad);
}
.rojo {
  color: var(--cdc-bad);
}
</style>
