<script setup lang="ts">
import type { DashboardCoordinacion } from '~/types/dashboard'

/**
 * Coordinación / Gerencia · hoy (prototype K01-DashCoord; phone layout K11-CoordCel).
 * All numbers come from /dashboard/coordinacion; refreshed every minute.
 */
definePageMeta({ cargos: ['gerencia', 'coordinacion'] })

const auth = useAuth()
const api = useApi()
const me = computed(() => auth.user.value!)
useHead(() => ({ title: `${CARGO_LABELS[me.value.cargo]} · hoy · Casa Dolce Casa` }))

const { data, refresh, error } = await useAsyncData('dash-coord', () => api<DashboardCoordinacion>('/dashboard/coordinacion'))
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => (timer = setInterval(() => refresh(), 60_000)))
onBeforeUnmount(() => clearInterval(timer))

const d = computed(() => data.value!)
const mes = new Intl.DateTimeFormat('es-CO', { month: 'long', timeZone: 'America/Bogota' }).format(new Date())
const hoyLargo = (() => {
  const t = new Intl.DateTimeFormat('es-CO', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'America/Bogota' }).format(new Date())
  return t.charAt(0).toUpperCase() + t.slice(1)
})()
const subtitle = computed(() => {
  const e = d.value.equipo
  return `${hoyLargo} · ${e.asesores_activos} ${e.asesores_activos === 1 ? 'asesor' : 'asesores'} · Atención y Preventa (${e.atencion_activos} ${e.atencion_activos === 1 ? 'persona' : 'personas'})`
})

/** Semáforo (decisions): green ≥ 80 %, yellow 60–79 %, red < 60 %. */
const semaforo = (pct: number | null) =>
  pct == null ? { cls: 'gray', t: 'Sin datos' } : pct >= 80 ? { cls: 'ok', t: `● ${pct}%` } : pct >= 60 ? { cls: 'warn', t: `▲ ${pct}%` } : { cls: 'bad', t: `▼ ${pct}%` }

const preop = computed(() => d.value.preoperacional)
const pedChip = (id: string) => {
  const r = d.value.pedidos.por_persona[id]
  if (!r || (!r.por_vencer && !r.vencidos)) return null
  if (r.vencidos) return { cls: 'bad', t: `${r.vencidos} vencido${r.vencidos > 1 ? 's' : ''}` }
  return { cls: r.hoy ? 'bad' : 'warn', t: r.hoy ? `${r.por_vencer} · ${r.hoy === 1 ? 'uno' : r.hoy} hoy` : String(r.por_vencer) }
}
const preopDet = computed(() => {
  const p = preop.value
  if (!p) return ''
  const parts = [p.sin_realizar ? `falta ${p.faltan.map(firstName).slice(0, 2).join(', ')}${p.faltan.length > 2 ? '…' : ''}` : 'todos al día']
  if (p.con_novedad) parts.push(`${p.con_novedad} ${p.con_novedad === 1 ? 'novedad' : 'novedades'}`)
  return parts.join(' · ')
})
const preopChip = (id: string) => {
  const e = preop.value?.por_persona[id]
  return e ? PREOP_ESTADO[e] ?? null : null
}
const oldestCap = computed(() => d.value.captaciones.lista_por_verificar[0])
const kpis = computed(() => {
  const { leads: l, citas: c, captaciones: k } = d.value
  return [
    { t: 'Leads sin responsable', v: l.sin_responsable, to: '/leads', tint: '', d: l.sin_responsable_alerta ? `${l.sin_responsable_alerta} con más de 15 min` : 'todos a tiempo', dcls: l.sin_responsable_alerta ? 'dt-warn' : 'mut' },
    { t: 'Citas sin aceptar', v: c.pendientes, to: '/citas', tint: c.pendientes_menos_1h ? 'tint-bad' : '', d: c.pendientes_menos_1h ? `${c.pendientes_menos_1h} a menos de 1 hora` : 'ninguna a menos de 1 hora', dcls: c.pendientes_menos_1h ? 'dt-bad' : 'mut' },
    {
      t: 'Pedidos vencidos',
      v: d.value.pedidos.vencidos_mes,
      to: '/pedidos',
      tint: d.value.pedidos.vencidos_sin_decidir ? 'tint-bad' : '',
      d: d.value.pedidos.vencidos_sin_decidir ? `${d.value.pedidos.vencidos_sin_decidir} sin decidir · este mes` : 'este mes',
      dcls: d.value.pedidos.vencidos_sin_decidir ? 'dt-bad' : 'mut',
    },
    { t: 'Captaciones por verificar', v: k.counts.por_verificar, to: '/captaciones', tint: k.counts.por_verificar ? 'tint-warn' : '', d: oldestCap.value ? `la más antigua: ${fmtCuando(oldestCap.value.enviada_at)}` : 'al día', dcls: k.counts.por_verificar ? 'dt-warn' : 'mut' },
    preop.value
      ? {
          t: 'Preoperacional',
          v: `${preop.value.realizados}/${preop.value.total}`,
          to: '/preoperacionales',
          tint: preop.value.sin_realizar ? 'tint-warn' : '',
          d: preopDet.value,
          dcls: preop.value.sin_realizar || preop.value.novedades_sin_revisar ? 'dt-warn' : 'mut',
        }
      : { t: 'Citas de hoy', v: c.hoy_total, to: '/citas', tint: '', d: `${c.hoy_aceptadas} aceptadas · ${c.hoy_realizadas} realizadas`, dcls: 'mut' },
    { t: 'En proceso', v: l.abiertos, to: '/leads', tint: '', d: `${l.abiertos_por_negocio.venta ?? 0} venta · ${l.abiertos_por_negocio.arriendo ?? 0} arriendo`, dcls: 'mut' },
  ]
})

const ACT_CORTO = { captacion: 'C', ventas: 'V', arriendos: 'A' } as const
const nivel = (n: 'bad' | 'warn') => (n === 'bad' ? { sym: '■', cls: 'a-bad', chip: 'bad', t: 'Urgente' } : { sym: '▲', cls: 'a-warn', chip: 'warn', t: 'Atención' })

// Phone (K11): tabs and a one-line status per person.
const tabCel = ref<'alertas' | 'equipo'>('alertas')
const equipoCel = computed(() => [
  ...d.value.equipo.asesores.map((a) => ({
    n: a.full_name,
    d: `${a.actividades.map((x) => ACTIVIDAD_LABELS[x]).join(' + ') || 'Sin actividades'} · ${a.citas_hoy} citas hoy`,
    ...(a.cita_sin_aceptar_urgente
      ? { cls: 'bad', r: `${a.cita_sin_aceptar_code} · menos de 1 h` }
      : a.citas_sin_aceptar
        ? { cls: 'warn', r: `${a.citas_sin_aceptar} sin aceptar` }
        : a.captaciones_rechazadas
          ? { cls: 'warn', r: `${a.captaciones_rechazadas} capt. por corregir` }
          : { cls: 'ok', r: 'Al día' }),
  })),
  ...d.value.equipo.atencion.map((a) => ({
    n: a.full_name,
    d: `${a.funcion ? FUNCION_LABELS[a.funcion] : 'Atención'} · ${a.leads_abiertos} leads abiertos`,
    ...(a.citas_requieren_accion
      ? { cls: 'bad', r: `${a.citas_requieren_accion} cita por resolver` }
      : a.seguimientos_vencidos
        ? { cls: 'warn', r: `${a.seguimientos_vencidos} seguimiento vencido` }
        : { cls: 'ok', r: 'Al día' }),
  })),
])
</script>

<template>
  <div v-if="error" class="cnt"><div class="note bad"><b>No se pudo cargar el tablero.</b> {{ apiErrorMessage(error) }}</div></div>
  <template v-else-if="data">
    <!-- =================== Desktop / tablet (K01) =================== -->
    <div class="desk">
      <PageBar :title="`${CARGO_LABELS[me.cargo]} · hoy`" :subtitle="subtitle">
        <NuxtLink class="btn bs" to="/citas">Control de citas</NuxtLink>
        <NuxtLink class="btn bs" to="/equipo">{{ auth.user.value?.cargo === 'gerencia' ? 'Rendimiento por empleado' : 'Mi equipo' }}</NuxtLink>
        <NuxtLink class="btn bs" to="/pedidos">Pedidos</NuxtLink>
        <NuxtLink class="btn bs" to="/captaciones">Verificar captaciones</NuxtLink>
        <NuxtLink class="btn bp" to="/leads">Leads</NuxtLink>
      </PageBar>

      <div class="cnt">
        <div class="g6">
          <NuxtLink v-for="k in kpis" :key="k.t" class="card kpi" :class="k.tint" :to="k.to">
            <div class="lbl">{{ k.t }}</div>
            <div class="kn num">{{ k.v }}</div>
            <div class="kd" :class="k.dcls">{{ k.d }}</div>
          </NuxtLink>
        </div>

        <div class="g2">
          <NuxtLink class="card link-row" to="/captaciones">
            <div>
              <div class="lbl">Captaciones · {{ mes }}</div>
              <div class="mut small">
                {{ d.captaciones.aprobadas_mes }} aprobadas · {{ d.captaciones.rechazadas_mes }} rechazadas · {{ d.captaciones.sin_publicar }} sin publicar
              </div>
            </div>
            <span class="chip big" :class="semaforo(d.captaciones.aprobacion_pct).cls">{{ semaforo(d.captaciones.aprobacion_pct).t }}</span>
          </NuxtLink>
          <NuxtLink class="card link-row" to="/leads">
            <div>
              <div class="lbl">Leads · {{ mes }}</div>
              <div class="mut small">
                {{ d.leads.ganados_mes }} ganados · {{ d.leads.perdidos_mes }} perdidos ({{ d.leads.perdidos_con_descuento_mes }} con descuento) · {{ d.leads.nuevos_semana }} nuevos esta semana
              </div>
            </div>
            <span class="chip info big">{{ d.leads.nuevos_hoy }} nuevos hoy</span>
          </NuxtLink>
        </div>

        <div class="split">
          <div class="col">
            <div class="card">
              <div class="sb head"><span class="lbl">Mi equipo hoy · lo que necesita tu atención</span><span class="mut small">una fila por persona · toca un asesor para ver su inicio</span></div>
              <div class="wrap">
                <table class="tbl t-hoy">
                  <thead>
                    <tr><th>Persona</th><th>Citas sin aceptar</th><th>Citas hoy</th><th>Pedidos por vencer</th><th>Seguimientos vencidos</th><th>Citas por resolver</th><th>Captaciones por corregir</th><th>Preoperacional</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="a in d.equipo.asesores" :key="a.id">
                      <td><NuxtLink :to="`/asesor?asesor=${a.id}`" class="who">{{ a.full_name }}</NuxtLink></td>
                      <td>
                        <span v-if="a.citas_sin_aceptar" class="chip" :class="a.cita_sin_aceptar_urgente ? 'bad' : 'warn'">
                          {{ a.citas_sin_aceptar }} · {{ a.cita_sin_aceptar_code }}{{ a.cita_sin_aceptar_urgente ? ' a 1 h' : '' }}
                        </span>
                        <span v-else class="num">0</span>
                      </td>
                      <td class="num">{{ a.citas_hoy }}</td>
                      <td>
                        <span v-if="pedChip(a.id)" class="chip" :class="pedChip(a.id)!.cls">{{ pedChip(a.id)!.t }}</span>
                        <span v-else class="num">0</span>
                      </td>
                      <td class="mut">—</td>
                      <td class="mut">—</td>
                      <td>
                        <span v-if="a.captaciones_rechazadas == null" class="mut">—</span>
                        <span v-else-if="a.captaciones_rechazadas" class="chip bad">{{ a.captaciones_rechazadas }}</span>
                        <span v-else class="num">0</span>
                      </td>
                      <td>
                        <NuxtLink v-if="preopChip(a.id)" to="/preoperacionales" class="chip" :class="preopChip(a.id)!.cls">{{ preopChip(a.id)!.t.replace('Sin realizar', 'Falta') }}</NuxtLink>
                        <span v-else class="mut">—</span>
                      </td>
                    </tr>
                    <tr v-for="a in d.equipo.atencion" :key="a.id">
                      <td><b>{{ a.full_name }}</b></td>
                      <td class="mut">—</td>
                      <td class="mut">—</td>
                      <td>
                        <span v-if="pedChip(a.id)" class="chip" :class="pedChip(a.id)!.cls">{{ pedChip(a.id)!.t }}</span>
                        <span v-else class="num">0</span>
                      </td>
                      <td><span v-if="a.seguimientos_vencidos" class="chip warn">{{ a.seguimientos_vencidos }}</span><span v-else class="num">0</span></td>
                      <td><span v-if="a.citas_requieren_accion" class="chip bad">{{ a.citas_requieren_accion }}</span><span v-else class="num">0</span></td>
                      <td class="mut">—</td>
                      <td>
                        <NuxtLink v-if="preopChip(a.id)" to="/preoperacionales" class="chip" :class="preopChip(a.id)!.cls">{{ preopChip(a.id)!.t.replace('Sin realizar', 'Falta') }}</NuxtLink>
                        <span v-else class="mut">—</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="mut small foot">
                Reúne lo que necesita tu atención hoy. Tareas, GPS y asistencia se suman aquí cuando existan esos módulos.
              </div>
            </div>

            <div class="card">
              <div class="sb head">
                <span class="lbl">Mi equipo · actividades activas y resultados de {{ mes }}</span>
                <NuxtLink to="/usuarios" class="lnk">Cambiar actividades ›</NuxtLink>
              </div>
              <div class="wrap">
                <table class="tbl t-act">
                  <thead>
                    <tr><th>Persona</th><th>Actividades activas</th><th>GPS</th><th>Capt. V / A</th><th>Por verificar</th><th>Citas realizadas</th><th>Citas aceptadas</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="a in d.equipo.asesores" :key="a.id">
                      <td><NuxtLink :to="`/asesor?asesor=${a.id}`" class="who">{{ a.full_name }}</NuxtLink></td>
                      <td>
                        <span class="row pills">
                          <span v-for="(c, k) in ACT_CORTO" :key="k" class="act" :class="a.actividades.includes(k) ? 'on1' : 'off1'" :title="ACTIVIDAD_LABELS[k]">{{ c }}</span>
                        </span>
                      </td>
                      <td><span class="chip" :class="a.gps_checkin_enabled ? 'ok' : 'gray'">{{ a.gps_checkin_enabled ? 'Activo' : 'Sin GPS' }}</span></td>
                      <td :class="a.captaciones_venta_mes == null ? 'mut' : 'num'">
                        {{ a.captaciones_venta_mes == null ? 'no aplica' : `${a.captaciones_venta_mes} / ${a.captaciones_arriendo_mes}` }}
                      </td>
                      <td :class="a.captaciones_por_verificar == null ? 'mut' : 'num'">{{ a.captaciones_por_verificar ?? 'no aplica' }}</td>
                      <td class="num">{{ a.citas_realizadas_mes }}</td>
                      <td class="num">{{ a.citas_aceptadas_activas }}</td>
                    </tr>
                    <tr v-if="!d.equipo.asesores.length"><td colspan="7" class="mut">No hay asesores activos.</td></tr>
                  </tbody>
                </table>
              </div>
              <div class="mut small foot">C = Captación · V = Ventas · A = Arriendos. «No aplica» = la actividad no está activa, así que no se mide. Capt. V / A = captaciones aprobadas este mes.</div>
            </div>
          </div>

          <div class="col">
            <div class="card">
              <div class="lbl head">Alertas en tiempo real</div>
              <p v-if="!d.alertas.length" class="mut small">Todo en orden: no hay alertas ahora.</p>
              <div v-for="(a, i) in d.alertas" :key="i" class="it">
                <b :class="nivel(a.nivel).cls">{{ nivel(a.nivel).sym }} {{ a.titulo }}</b>
                <span class="mut small">{{ a.detalle }} · <NuxtLink :to="a.link">{{ a.accion.toLowerCase() }} ›</NuxtLink></span>
              </div>
            </div>

            <div class="card">
              <div class="sb head"><span class="lbl">Citas de hoy</span><NuxtLink to="/citas" class="lnk">Ver todas ›</NuxtLink></div>
              <p v-if="!d.citas.lista_hoy.length" class="mut small">No hay citas hoy.</p>
              <NuxtLink v-for="c in d.citas.lista_hoy" :key="c.id" class="it" :to="`/leads/${c.lead_id}`">
                <div class="sb">
                  <b class="small">{{ fmtHora(c.scheduled_at) }} · {{ c.code }} · {{ CITA_TIPO_CORTO[c.tipo] }}</b>
                  <span class="chip" :class="c.requiere_accion ? 'bad' : citaChip(c.estado).cls">{{ c.requiere_accion && c.estado === 'pendiente' ? 'Sin aceptar' : citaChip(c.estado).t }}</span>
                </div>
                <span class="mut small">{{ c.asesor_name ?? 'Sin asesor' }} · {{ c.lead_name }}</span>
              </NuxtLink>
            </div>

            <div class="card">
              <div class="sb head"><span class="lbl">Captaciones por verificar</span><NuxtLink to="/captaciones" class="lnk">Verificar ›</NuxtLink></div>
              <p v-if="!d.captaciones.lista_por_verificar.length" class="mut small">No hay captaciones por verificar.</p>
              <NuxtLink v-for="c in d.captaciones.lista_por_verificar" :key="c.id" class="it" :to="`/captaciones/${c.id}`">
                <div class="sb">
                  <b class="small">{{ c.code }} · {{ c.codigo_inmueble }} · {{ NEGOCIO_LABELS[c.negocio] }}</b>
                  <span class="chip warn">{{ fmtCuando(c.enviada_at) }}</span>
                </div>
                <span class="mut small">{{ c.asesor_name }}{{ c.reenvios ? ' · corregida y reenviada' : '' }}</span>
              </NuxtLink>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="sb head"><span class="lbl">Atención y Preventa · una sola área · {{ mes }}</span><NuxtLink to="/leads" class="lnk">Ver leads ›</NuxtLink></div>
          <div class="wrap">
            <table class="tbl t-at">
              <thead>
                <tr><th>Persona</th><th>Leads que siguió</th><th>Primera respuesta</th><th>Llamadas</th><th>Seguimientos a tiempo</th><th>Citas programadas</th><th>Citas realizadas</th><th>Ganados</th><th>Leads abiertos</th></tr>
              </thead>
              <tbody>
                <tr v-for="a in d.equipo.atencion" :key="a.id">
                  <td><b>{{ a.full_name }}</b></td>
                  <td class="num">{{ a.leads_seguidos_mes }}</td>
                  <td class="num">{{ a.primera_respuesta_min == null ? '—' : `${a.primera_respuesta_min} min` }}</td>
                  <td class="num">{{ a.llamadas_mes }} <span class="mut">({{ a.llamadas_contestadas_mes }} contest.)</span></td>
                  <td class="num">{{ a.seguimientos_a_tiempo_mes }} de {{ a.seguimientos_mes }}</td>
                  <td class="num">{{ a.citas_programadas_mes }}</td>
                  <td class="num">{{ a.citas_realizadas_mes }}</td>
                  <td class="num">{{ a.ganados_mes }}</td>
                  <td class="num">{{ a.leads_abiertos }}</td>
                </tr>
                <tr v-if="!d.equipo.atencion.length"><td colspan="9" class="mut">No hay personas activas en Atención y Preventa.</td></tr>
              </tbody>
            </table>
          </div>
          <div class="mut small foot">Primera respuesta = minutos desde que llega el lead hasta que alguien lo toma. Un seguimiento es «a tiempo» si se marca realizado hasta 30 min después de su hora.</div>
        </div>

        <div class="g3">
          <NuxtLink class="card link-card" to="/usuarios"><b>Activar o quitar actividades</b><div class="mut small">Captación, Ventas y Arriendos por persona. El GPS sigue a Captación.</div></NuxtLink>
          <NuxtLink class="card link-card" to="/citas"><b>Control de citas</b><div class="mut small">Reasignar, reprogramar o cancelar las que requieren acción.</div></NuxtLink>
          <NuxtLink class="card link-card" to="/preoperacionales"><b>Preoperacionales</b><div class="mut small">Quién lo hizo hoy, novedades por revisar y el puntaje automático del mes.</div></NuxtLink>
          <NuxtLink class="card link-card" to="/plataformas"><b>{{ me.cargo === 'gerencia' ? 'Plataformas tradicionales' : 'Actualización de plataformas' }}</b><div class="mut small">Cupo, destacados y quién actualizó cada portal; cuenta en el rendimiento del Coordinador.</div></NuxtLink>
          <NuxtLink class="card link-card" to="/movimientos"><b>Movimientos y GPS</b><div class="mut small">Salidas de ruta y tiempos detenidos de hoy, justificaciones por revisar y el trabajo en campo.</div></NuxtLink>
          <NuxtLink class="card link-card" to="/novedades"><b>Ausencias y permisos</b><div class="mut small">Incapacidades y permisos del personal, y las novedades del preoperacional.</div></NuxtLink>
          <NuxtLink class="card link-card" to="/captaciones"><b>Verificar captaciones</b><div class="mut small">Solo las aprobadas suman en la captación del asesor.</div></NuxtLink>
        </div>
      </div>
    </div>

    <!-- =================== Phone (K11) =================== -->
    <div class="cel cnt">
      <div>
        <h1 class="ttl">Hola, {{ firstName(me.full_name) }}</h1>
        <div class="mut small">{{ CARGO_LABELS[me.cargo] }} · {{ hoyLargo.toLowerCase() }}</div>
      </div>
      <div class="g2 tiles">
        <NuxtLink class="st" to="/leads"><div class="lbl">Leads sin responsable</div><div class="kn num">{{ d.leads.sin_responsable }}</div></NuxtLink>
        <NuxtLink class="st" :class="{ 'st-bad': d.citas.pendientes_menos_1h }" to="/citas"><div class="lbl">Citas sin aceptar</div><div class="kn num">{{ d.citas.pendientes }}</div></NuxtLink>
        <NuxtLink class="st" :class="{ 'st-warn': d.captaciones.counts.por_verificar }" to="/captaciones"><div class="lbl">Captaciones por verificar</div><div class="kn num">{{ d.captaciones.counts.por_verificar }}</div></NuxtLink>
        <NuxtLink v-if="preop" class="st" :class="{ 'st-warn': preop.sin_realizar }" to="/preoperacionales"><div class="lbl">Preoperacional</div><div class="kn num">{{ preop.realizados }}/{{ preop.total }}</div></NuxtLink>
        <NuxtLink v-else class="st" to="/citas"><div class="lbl">Citas de hoy</div><div class="kn num">{{ d.citas.hoy_total }}</div></NuxtLink>
      </div>
      <NuxtLink class="card link-row" to="/captaciones">
        <div><div class="lbl">Captaciones · {{ mes }}</div><div class="mut tiny">{{ d.captaciones.aprobadas_mes }} aprobadas · {{ d.captaciones.rechazadas_mes }} rechazadas</div></div>
        <span class="chip big" :class="semaforo(d.captaciones.aprobacion_pct).cls">{{ semaforo(d.captaciones.aprobacion_pct).t }} ›</span>
      </NuxtLink>
      <div class="tabs">
        <button type="button" class="tab grow" :class="{ on: tabCel === 'alertas' }" @click="tabCel = 'alertas'">Alertas ({{ d.alertas.length }})</button>
        <button type="button" class="tab grow" :class="{ on: tabCel === 'equipo' }" @click="tabCel = 'equipo'">Mi equipo</button>
      </div>
      <div v-if="tabCel === 'alertas'" class="card list">
        <p v-if="!d.alertas.length" class="mut small pad">Todo en orden: no hay alertas ahora.</p>
        <div v-for="(a, i) in d.alertas" :key="i" class="alert-cel">
          <div class="sb"><b class="t">{{ a.titulo }}</b><span class="chip" :class="nivel(a.nivel).chip">{{ nivel(a.nivel).t }}</span></div>
          <span class="mut tiny">{{ a.detalle }}</span>
          <span class="tiny"><b>Qué hacer:</b> {{ a.que_hacer }}</span>
          <NuxtLink class="btn bs" :to="a.link">{{ a.accion }}</NuxtLink>
        </div>
      </div>
      <div v-else class="card list">
        <div v-for="p in equipoCel" :key="p.n" class="li">
          <div><b>{{ p.n }}</b><div class="mut tiny">{{ p.d }}</div></div>
          <span class="chip" :class="p.cls">{{ p.r }}</span>
        </div>
      </div>
      <div class="note">Versión de celular para revisar el día y actuar rápido. La configuración completa (usuarios, actividades) está en la versión de navegador.</div>
    </div>
  </template>
</template>

<style scoped>
.cel {
  display: none;
}
.kpi {
  text-decoration: none;
  color: var(--cdc-text);
  padding: 14px 16px;
}
.kpi:hover {
  border-color: var(--cdc-green);
  color: var(--cdc-text);
}
.kd {
  font-size: 12px;
}
.dt-bad {
  color: var(--cdc-bad);
  font-weight: 700;
}
.dt-warn {
  color: var(--cdc-warn);
  font-weight: 700;
}
.link-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  text-decoration: none;
  color: var(--cdc-text);
}
.g3 {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}
.link-card {
  text-decoration: none;
  color: var(--cdc-text);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.link-row:hover,
.link-card:hover {
  border-color: var(--cdc-green);
  color: var(--cdc-text);
}
.chip.big {
  font-size: 14px;
  padding: 6px 12px;
}
.head {
  margin-bottom: 6px;
}
.lnk {
  font-weight: 700;
  font-size: 13px;
}
.small {
  font-size: 12.5px;
}
.tiny {
  font-size: 12px;
}
.foot {
  margin-top: 8px;
}
.t-hoy {
  min-width: 920px;
}
.t-act {
  min-width: 760px;
}
.t-at {
  min-width: 880px;
}
.pills {
  gap: 4px;
}
.who {
  font-weight: 700;
  color: var(--cdc-text);
}
.who:hover {
  color: var(--cdc-green);
}
.a-bad {
  color: var(--cdc-bad);
}
.a-warn {
  color: var(--cdc-warn);
}
.it b {
  font-size: 13.5px;
}

/* ---- Phone (K11) ---- */
@media (max-width: 760px) {
  .desk {
    display: none;
  }
  .cel {
    display: flex;
  }
  .tiles {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
  .st {
    text-decoration: none;
    color: var(--cdc-text);
  }
  .st .kn {
    font-size: 32px;
  }
  .st-bad {
    background: var(--cdc-bad-bg);
  }
  .st-warn {
    background: var(--cdc-warn-bg);
  }
  .grow {
    flex: 1;
  }
  .li .chip {
    flex: none;
    white-space: nowrap;
  }
  .list {
    padding: 4px 14px;
  }
  .pad {
    padding: 10px 0;
  }
  .alert-cel {
    padding: 11px 0;
    border-bottom: 1px solid var(--cdc-border-soft);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .alert-cel:last-child {
    border-bottom: 0;
  }
  .alert-cel .t {
    font-size: 13.5px;
  }
  .alert-cel .btn {
    min-height: 38px;
    font-size: 13px;
  }
}
</style>
