<script setup lang="ts">
import type { Cambio, ConfigRead, Resultado } from '~/types/rendimiento'

/**
 * K07 «Rendimiento e indicadores» (Coordinación) · «Indicadores, metas y pesos» (Gerencia).
 * Weights apply from this month; goals from next month. Every change goes to the change log.
 */
definePageMeta({ cargos: ['coordinacion', 'gerencia'] })

const auth = useAuth()
const route = useRoute()
const rend = useRendimiento()
const ger = computed(() => auth.user.value?.cargo === 'gerencia')
const titulo = computed(() => (ger.value ? 'Indicadores, metas y pesos' : 'Rendimiento e indicadores'))
useHead(() => ({ title: `${titulo.value} · Casa Dolce Casa` }))

const { data: eq } = await useAsyncData('rend-personas', () => rend.equipo())
const personas = computed(() => eq.value?.personas ?? [])
const who = ref<string | null>((route.query.persona as string) || null)
watchEffect(() => {
  if (!who.value && personas.value.length) who.value = personas.value[0]!.id
})

const cfg = ref<ConfigRead | null>(null)
const res = ref<Resultado | null>(null)
const log = ref<Cambio[]>([])
const pesos = reactive<Record<string, number>>({})
const metas = reactive<Record<string, number>>({})
const msg = ref<{ t: string; ok: boolean } | null>(null)
const busy = ref(false)

async function cargar() {
  if (!who.value) return
  msg.value = null
  const [c, r, l] = await Promise.all([rend.config(who.value), rend.persona(who.value), rend.cambios(who.value).catch(() => [])])
  cfg.value = c
  res.value = r
  log.value = l
  for (const k of Object.keys(pesos)) delete pesos[k]
  for (const k of Object.keys(metas)) delete metas[k]
  Object.assign(pesos, c.pesos)
  Object.assign(metas, c.metas_siguiente)
}
watch(who, cargar, { immediate: true })

const total = computed(() => Object.values(pesos).reduce((a, b) => a + b, 0))
const setP = (k: string, d: number) => {
  pesos[k] = Math.max(0, Math.min(100, (pesos[k] ?? 0) + d))
  msg.value = null
}
const setM = (k: string, d: number) => {
  metas[k] = Math.max(1, (metas[k] ?? 1) + d)
  msg.value = null
}
const preview = computed(() => {
  const areas = (res.value?.areas ?? []).filter((a) => a.cumplimiento != null && (pesos[a.key] ?? 0) > 0)
  const w = areas.reduce((s, a) => s + (pesos[a.key] ?? 0), 0)
  const rows = areas.map((a) => ({ t: a.titulo, r: a.cumplimiento!, p: pesos[a.key]!, ap: w ? (a.cumplimiento! * pesos[a.key]!) / w : 0 }))
  return { rows, general: rows.reduce((s, x) => s + x.ap, 0), w }
})

async function run(fn: () => Promise<ConfigRead>, ok: string) {
  busy.value = true
  try {
    cfg.value = await fn()
    msg.value = { t: ok, ok: true }
    res.value = await rend.persona(who.value!)
    log.value = await rend.cambios(who.value!).catch(() => [])
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  } finally {
    busy.value = false
  }
}
const guardarPesos = () =>
  run(() => rend.guardarPesos(who.value!, { ...pesos }), `Pesos guardados. ${firstName(cfg.value!.user.full_name)} ya ve cuánto pesa cada área en su rendimiento. El cambio queda en el registro de cambios.`)
const guardarMetas = () =>
  run(() => rend.guardarMetas(who.value!, { ...metas }), `Metas guardadas. Aplican desde ${cfg.value!.siguiente} y quedan en el registro de cambios.`)

async function onCalSaved(r: Resultado) {
  res.value = r
  log.value = await rend.cambios(r.user.id).catch(() => [])
}

const label = (k: string) => cfg.value?.areas.find((a) => a.key === k)?.titulo ?? res.value?.calificaciones.find((c) => c.key === k)?.titulo ?? k
const TIPO = { pesos: 'Pesos', metas: 'Metas', calificaciones: 'Calificaciones' } as const
</script>

<template>
  <PageBar :title="titulo" subtitle="Asesores y Atención y Preventa · mismo sistema: pesos, metas, semáforo, calificaciones y descuentos" back="/coordinacion">
    <NuxtLink class="btn bs" to="/equipo">{{ ger ? 'Rendimiento por empleado' : 'Mi equipo' }} ›</NuxtLink>
  </PageBar>

  <div class="cnt">
    <div class="card stack">
      <div class="lbl">Reglas de rendimiento de todos los cargos · lo que aplica hoy</div>
      <div class="g2b">
        <div class="small rules">
          <b>Cómo se calcula</b>
          <p>• Resultado = cumplimiento de cada área × su peso − descuentos. 1 punto = 1 % del resultado del mes.</p>
          <p>• Cumplimiento = logrado ÷ meta, hasta 100 %. Las áreas sin datos todavía no cuentan: el resultado se calcula sobre el peso de las que sí tienen.</p>
          <p>• Semáforo: verde 80–100 · amarillo 70–79 · naranja 60–69 · rojo menos de 60.</p>
          <p>• Calificaciones de 1 a 5: cada nota de 2 o 1 descuenta 5 puntos. El preoperacional lo calcula el sistema; la puntualidad, cuando exista «Marcar entrada».</p>
          <p>• «Material de trabajo» solo se califica a los asesores.</p>
          <p>• Atención y Preventa: lead ganado +1 punto; perdido −0,5, sin descuento si el número estaba equivocado o tras 3 llamadas en 3 días seguidos.</p>
          <p>• Coordinador: resultado del equipo y monitoreo (salen solos), plataformas y rutas (cuando existan esos módulos), más sus calificaciones.</p>
          <p>• Nadie suma ni resta puntos a mano.</p>
        </div>
        <div class="small rules">
          <b>Cómo se evita contar dos veces</b>
          <p>• Una venta o un arriendo cuenta para el asesor de la última cita realizada cuando Coordinación o Gerencia marca el lead «Ganado»; el lead ganado cuenta para Atención y Preventa, no otra vez para el asesor.</p>
          <p>• Una captación cuenta una sola vez, cuando Coordinación la aprueba; un código ya registrado no se puede volver a enviar.</p>
          <p>• Si el cliente ya tiene un pedido abierto, se actualiza; no se crea otro.</p>
          <p>• Cada llamada, mensaje o seguimiento se registra una vez en el historial del lead.</p>
          <p class="mut">Pesos, metas y calificaciones se configuran abajo. Todo cambio queda en el registro de cambios con quién, cuándo, antes y después.</p>
        </div>
      </div>
    </div>

    <div class="row fw gap6" role="radiogroup" aria-label="Persona">
      <button v-for="p in personas" :key="p.id" type="button" class="opt" :class="{ on: who === p.id }" role="radio" :aria-checked="who === p.id" @click="who = p.id">
        {{ firstName(p.full_name) }}<span class="mut tiny"> · {{ p.perfil === 'asesor' ? 'Asesor' : p.perfil === 'atencion' ? 'Atención' : 'Coordinador' }}</span>
      </button>
    </div>

    <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.ok ? '✓ ' : '' }}{{ msg.t }}</b></div>

    <template v-if="cfg && res">
      <div class="g2b">
        <div class="card stack">
          <div class="sb">
            <span class="lbl">Peso de cada área en el resultado</span>
            <b>{{ cfg.user.full_name }}</b>
          </div>
          <div class="mut small">{{ cfg.cargo_txt }}{{ cfg.pesos_configurados ? '' : ' · pesos de ejemplo (sin configurar)' }}</div>
          <div v-for="a in cfg.areas" :key="a.key" class="sb it row-it">
            <span>{{ a.titulo }}</span>
            <span class="row gap6">
              <button v-if="cfg.puede_configurar" type="button" class="opt pm" :aria-label="`Bajar ${a.titulo}`" @click="setP(a.key, -5)">−</button>
              <b class="num w4">{{ pesos[a.key] }}%</b>
              <button v-if="cfg.puede_configurar" type="button" class="opt pm" :aria-label="`Subir ${a.titulo}`" @click="setP(a.key, 5)">+</button>
            </span>
          </div>
          <div class="sb">
            <b>Total</b>
            <span class="chip" :class="total === 100 ? 'ok' : 'bad'">{{ total }}%</span>
          </div>
          <div v-if="total !== 100" class="note bad">No se puede guardar: la suma debe ser exactamente 100%. {{ total > 100 ? 'Sobran' : 'Faltan' }} {{ Math.abs(100 - total) }} puntos.</div>
          <div v-if="!cfg.puede_configurar" class="note">
            Solo lectura. {{ cfg.perfil === 'asesor' ? 'Los pesos de los asesores los configura Coordinación.' : 'Los indicadores y pesos de Atención y Preventa y del Coordinador los configura Gerencia. Coordinación los monitorea.' }}
          </div>
          <div v-else><button type="button" class="btn bp" :disabled="busy || total !== 100" @click="guardarPesos">Guardar pesos</button></div>
        </div>

        <div class="card stack">
          <div class="sb"><span class="lbl">Metas del mes · {{ firstName(cfg.user.full_name) }}</span><span class="mut tiny">nuevas metas desde {{ cfg.siguiente }}</span></div>
          <template v-for="a in cfg.areas" :key="a.key">
            <div v-if="a.tiene_meta" class="sb it row-it">
              <div>
                <span>{{ a.titulo }} {{ a.key === 'ventas' ? '(cantidad de ventas del mes)' : a.key === 'conversion' ? '(%)' : '(cantidad)' }}</span>
                <div class="mut tiny">Este mes: {{ cfg.metas[a.key] }}</div>
              </div>
              <span class="row gap6">
                <button v-if="cfg.puede_configurar" type="button" class="opt pm" :aria-label="`Bajar meta ${a.titulo}`" @click="setM(a.key, -1)">−</button>
                <b class="num w4">{{ metas[a.key] }}</b>
                <button v-if="cfg.puede_configurar" type="button" class="opt pm" :aria-label="`Subir meta ${a.titulo}`" @click="setM(a.key, 1)">+</button>
              </span>
            </div>
          </template>
          <div v-if="!cfg.areas.some((a) => a.tiene_meta)" class="note">Sin metas configurables: sus áreas salen solas del sistema.</div>
          <div v-else-if="cfg.puede_configurar"><button type="button" class="btn bp" :disabled="busy" @click="guardarMetas">Guardar metas</button></div>
          <div class="mut tiny">Las metas aplican desde el mes siguiente: el resultado de este mes se mide con las metas con las que empezó. Metas reales: PENDIENTE DE CONFIGURACIÓN.</div>
        </div>
      </div>

      <div class="g2b">
        <SemaforoLegend compact />
        <div class="card stack">
          <div class="lbl">Vista previa del resultado de {{ firstName(cfg.user.full_name) }}</div>
          <div v-for="x in preview.rows" :key="x.t" class="sb small">
            <span>{{ x.t }}</span>
            <span>resultado {{ x.r }}% × peso {{ x.p }}%{{ preview.w !== 100 ? ` (sobre ${preview.w})` : '' }} = <b>{{ dec(Math.round(x.ap * 100) / 100) }}</b></span>
          </div>
          <div class="sb"><b>Resultado por áreas</b><b class="num">{{ dec(Math.round(preview.general * 100) / 100) }}%</b></div>
          <div class="mut tiny">
            A esto se le restan los descuentos del mes (calificaciones de 2 o 1: −5 puntos cada una; ahora {{ dec(res.puntos_descuento) }}). Un punto equivale a 1 % del resultado del mes.
          </div>
        </div>
      </div>

      <CalificacionesCard :r="res" @saved="onCalSaved" />
      <div v-if="!res.puede.calificar" class="note">
        {{ res.perfil === 'coordinacion' ? 'Las calificaciones del Coordinador las asigna la Auxiliar administrativa o Gerencia.' : 'Las calificaciones de 1 a 5 de asesores y Atención las asigna solo Coordinación; la Auxiliar administrativa y Gerencia solo las consultan.' }}
        <NuxtLink :to="`/resultados/${res.user.id}`">Ver resultados de {{ firstName(res.user.full_name) }} ›</NuxtLink>
      </div>

      <div class="card stack">
        <div class="lbl">Registro de cambios · {{ cfg.user.full_name }}</div>
        <div v-for="(c, i) in log" :key="i" class="it">
          <div class="sb">
            <b class="small">{{ TIPO[c.tipo] }} · {{ c.tipo === 'metas' ? `desde ${c.periodo.slice(0, 7)}` : c.periodo.slice(0, 7) }}</b>
            <span class="mut tiny">{{ fmtCuando(c.created_at) }} · {{ c.created_by_name ?? 'Sistema' }}</span>
          </div>
          <span class="mut small">
            {{ Object.keys(c.despues).map((k) => `${label(k)}: ${c.antes[k] ?? '—'} → ${c.despues[k]}`).join(' · ') }}
          </span>
        </div>
        <div v-if="!log.length" class="note">Sin cambios registrados.</div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rules p {
  margin: 6px 0 0;
}
.gap6 {
  gap: 6px;
}
.fw {
  flex-wrap: wrap;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.pm {
  width: 34px;
  min-height: 34px;
  padding: 0;
}
.w4 {
  min-width: 44px;
  text-align: center;
}
</style>
