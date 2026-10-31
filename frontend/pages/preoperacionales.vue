<script setup lang="ts">
import type { Cargo } from '~/types/auth'
import type { EquipoPreop } from '~/types/preoperacional'

/** Preoperacionales del equipo (prototype K09) — Coordinación and Gerencia. */
definePageMeta({ cargos: ['gerencia', 'coordinacion'] })
useHead({ title: 'Preoperacionales · Casa Dolce Casa' })

const auth = useAuth()
const preop = usePreoperacional()
const me = computed(() => auth.user.value!)
const esGerencia = computed(() => me.value.cargo === 'gerencia')

const fecha = ref(localDate())
const { data, refresh, error } = await useAsyncData('preop-equipo', () => preop.equipo(fecha.value), { watch: [fecha] })
const d = computed(() => data.value as EquipoPreop)

const sel = ref(0)
watch(data, () => {
  // Default to the first person who needs attention.
  const i = d.value?.filas.findIndex((f) => f.estado === 'novedad' || f.estado === 'sin_realizar') ?? 0
  sel.value = Math.max(0, i)
}, { immediate: true })
const fila = computed(() => d.value?.filas[sel.value] ?? null)

const fechaTxt = computed(() => {
  const t = new Intl.DateTimeFormat('es-CO', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' }).format(new Date(`${fecha.value}T12:00:00Z`))
  return fecha.value === localDate() ? `Hoy · ${t}` : t.charAt(0).toUpperCase() + t.slice(1)
})
const mesTxt = computed(() => new Intl.DateTimeFormat('es-CO', { month: 'long', timeZone: 'UTC' }).format(new Date(`${d.value.mes}-15T12:00:00Z`)))

const CARGOS_CFG: [Cargo, string][] = [
  ['asesor', 'Asesor comercial'],
  ['atencion_cliente', 'Atención y Preventa'],
  ['coordinacion', 'Coordinador comercial · le llega a Gerencia'],
  ['auxiliar_administrativa', 'Auxiliar administrativa'],
  ['gerencia', 'Gerencia · registro'],
]
const flash = ref<string | null>(null)
const errMsg = ref<string | null>(null)
async function toggle(cargo: Cargo) {
  errMsg.value = null
  try {
    await preop.setConfig(cargo, !d.value.config[cargo])
    await refresh()
  } catch (e) {
    errMsg.value = apiErrorMessage(e)
  }
}

const nota = ref('')
async function revisar() {
  const r = fila.value?.registro
  if (!r) return
  errMsg.value = null
  try {
    await preop.revisar(r.id, nota.value || null)
    nota.value = ''
    flash.value = `Novedad de ${fila.value!.user.full_name} marcada como revisada. Queda en el historial.`
    await refresh()
  } catch (e) {
    errMsg.value = apiErrorMessage(e)
  }
}

async function descargar(userId?: string) {
  errMsg.value = null
  try {
    await preop.descargar(d.value.mes, userId)
  } catch (e) {
    errMsg.value = apiErrorMessage(e)
  }
}

const detalleFila = (f: EquipoPreop['filas'][number]) => {
  if (f.estado === 'desactivado') return 'Preoperacional desactivado para el cargo'
  if (!f.registro) return f.estado === 'fin_de_semana' ? 'Fin de semana' : 'Aún no lo ha realizado'
  return preopDetalle(f.registro, MEDIO_LABELS_PREOP)
}
const nombre = (u: { full_name: string; cargo: Cargo }) =>
  u.cargo === 'coordinacion' || u.cargo === 'gerencia' || u.cargo === 'auxiliar_administrativa' ? `${u.full_name} · ${CARGO_LABELS[u.cargo]}` : u.full_name
</script>

<template>
  <PageBar
    title="Preoperacionales"
    subtitle="Lo hacen todos los cargos, incluida Gerencia · los reportes llegan a Coordinación (el del Coordinador, a Gerencia) · Gerencia lo activa o desactiva por cargo"
    back="/coordinacion"
  >
    <label class="row f">Día <input v-model="fecha" class="in d" type="date" :max="localDate()" aria-label="Día"></label>
    <button type="button" class="btn bs" @click="descargar()">Descargar el mes (Excel)</button>
    <NuxtLink class="btn bp" to="/preoperacional">Hacer mi preoperacional ›</NuxtLink>
  </PageBar>

  <div class="cnt">
    <div v-if="error" class="note bad"><b>{{ apiErrorMessage(error) }}</b></div>
    <template v-else-if="data">
      <div class="card stack">
        <div class="sb"><span class="lbl">Preoperacional activo por cargo</span><span class="mut tiny">{{ esGerencia ? 'Toca para activar o desactivar · solo Gerencia' : 'Lo define Gerencia · solo lectura' }}</span></div>
        <div class="cfg">
          <div v-for="[c, t] in CARGOS_CFG" :key="c" class="cfg-item">
            <b class="small">{{ CARGO_LABELS[c] }}</b>
            <span class="mut tiny">{{ t }}</span>
            <button v-if="esGerencia" type="button" class="btn sm self-start" :class="d.config[c] ? 'bp' : 'bs'" @click="toggle(c)">{{ d.config[c] ? '✓ Activo' : 'Desactivado' }}</button>
            <span v-else class="chip self-start" :class="d.config[c] ? 'ok' : 'gray'">{{ d.config[c] ? '✓ Activo' : 'Desactivado' }}</span>
          </div>
        </div>
        <div class="note">Desactivado: no aparece el aviso diario, no cuenta como cumplido y no descuenta puntos; el historial se conserva.</div>
      </div>

      <div class="g4">
        <div class="card"><div class="lbl">Realizados {{ fecha === localDate() ? 'hoy' : 'ese día' }}</div><div class="kn num">{{ d.kpis.realizados }} / {{ d.kpis.total }}</div></div>
        <div class="card" :class="{ 'tint-warn': d.kpis.con_novedad }"><div class="lbl">Con novedad</div><div class="kn num">{{ d.kpis.con_novedad }}</div><div class="mut tiny">{{ d.kpis.novedades_sin_revisar }} sin revisar</div></div>
        <div class="card" :class="{ 'tint-bad': d.kpis.sin_realizar }"><div class="lbl">Sin realizar</div><div class="kn num">{{ d.kpis.sin_realizar }}</div><div v-if="d.kpis.sin_realizar" class="dt-bad tiny">baja la nota del mes</div></div>
        <div class="card"><div class="lbl">Cumplimiento del mes anterior</div><div class="kn num">{{ d.kpis.cumplimiento_mes_anterior == null ? '—' : `${d.kpis.cumplimiento_mes_anterior}%` }}</div></div>
      </div>

      <div v-if="flash" class="note ok" role="status"><b>✓ {{ flash }}</b></div>
      <div v-if="errMsg" class="note bad" role="alert"><b>{{ errMsg }}</b></div>

      <div class="g2b">
        <div class="card">
          <div class="lbl head">{{ fechaTxt }} · toca una persona</div>
          <button v-for="(f, i) in d.filas" :key="f.user.id" type="button" class="pick person" :class="{ on: i === sel }" @click="sel = i">
            <span><b>{{ nombre(f.user) }}</b><br><span class="mut tiny">{{ detalleFila(f) }}</span></span>
            <span class="chip" :class="PREOP_ESTADO[f.estado]?.cls">{{ PREOP_ESTADO[f.estado]?.t }}</span>
          </button>
          <p v-if="!d.filas.length" class="mut small">No hay personas para revisar.</p>
        </div>

        <div class="col">
          <div v-if="fila" class="card focus stack">
            <div class="lbl">Reporte de {{ fila.user.full_name }}</div>
            <div class="small">{{ preopReporte(fila.estado, fila.registro) }}</div>
            <template v-if="fila.registro?.tiene_novedad">
              <div class="note warn">
                <b>Novedad:</b>
                <template v-if="fila.registro.respuestas_no.length">
                  NO en {{ fila.registro.respuestas_no.map((n) => `«${fila!.registro!.respuestas[n - 1]?.pregunta}»`).join(', ') }}.
                </template>
                <template v-if="fila.registro.observaciones"> Observación: «{{ fila.registro.observaciones }}».</template>
              </div>
              <template v-if="!fila.registro.revisado_at">
                <input v-model="nota" class="in" placeholder="Nota de la revisión (opcional)" aria-label="Nota">
                <button type="button" class="btn bs self-start" @click="revisar">Marcar novedad como revisada</button>
              </template>
              <span v-else class="chip ok self-start wrap-chip">
                ✓ Revisada por {{ fila.registro.revisado_por_name }} · {{ fmtCuando(fila.registro.revisado_at) }}{{ fila.registro.revision_nota ? ` · «${fila.registro.revision_nota}»` : '' }}
              </span>
            </template>
            <button v-if="fila.registro" type="button" class="btn bs sm self-start" @click="descargar(fila.user.id)">Descargar su mes</button>
          </div>

          <div class="card">
            <div class="lbl head">Puntaje automático de {{ mesTxt }} (1 a 5)</div>
            <div class="wrap">
              <table class="tbl t-mes">
                <thead><tr><th>Persona</th><th>Días cumplidos</th><th>Puntaje</th><th>Descuento por nota</th></tr></thead>
                <tbody>
                  <tr v-for="m in d.mes_rows" :key="m.user.id">
                    <td>{{ nombre(m.user) }}</td>
                    <td class="num">{{ m.resumen.pct == null ? '—' : `${m.resumen.cumplidos} de ${m.resumen.dias_habiles}` }}</td>
                    <td><b>{{ m.user.cargo === 'gerencia' ? 'Registro' : m.resumen.puntaje ?? '—' }}</b></td>
                    <td class="num">{{ m.user.cargo === 'gerencia' ? '—' : m.resumen.descuento ? `−${m.resumen.descuento}` : 0 }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="note foot"><b>Regla aprobada:</b> 100% de días = 5 · 90–99% = 4 · 80–89% = 3 · 70–79% = 2 · menos de 70% = 1. Días hábiles de lunes a viernes. Nota de 2 o 1: −5 puntos.</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.f {
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
}
.d {
  width: auto;
  min-height: 40px;
  font-size: 13px;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.cfg {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 8px;
}
.cfg-item {
  border: 1px solid var(--cdc-border);
  border-radius: 12px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.self-start {
  align-self: flex-start;
}
.head {
  margin-bottom: 6px;
}
.person {
  margin-bottom: 6px;
}
.dt-bad {
  color: var(--cdc-bad);
  font-weight: 700;
}
.wrap-chip {
  white-space: normal;
}
.t-mes {
  min-width: 420px;
}
.foot {
  margin-top: 8px;
}
</style>
