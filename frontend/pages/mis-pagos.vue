<script setup lang="ts">
/**
 * «Mis pagos y bonos» (Z05) · on mobile «Mis comisiones / Mis bonos / Pagos» (M12–M14).
 * Read-only: the Auxiliar gives the visto bueno and Gerencia approves and pays.
 */
useHead({ title: 'Mis pagos y bonos · Casa Dolce Casa' })

const auth = useAuth()
const route = useRoute()
const comp = useCompensacion()
const rend = useRendimiento()
const { data, error } = await useAsyncData('mis-pagos', () => comp.mio())
const perfil = computed(() => perfilRendimiento(auth.user.value))
const { data: puntaje } = useLazyAsyncData('mis-pagos-puntaje', () => (perfil.value ? rend.mio().catch(() => null) : Promise.resolve(null)), { server: false })

type Tab = 'todo' | 'salario' | 'comision' | 'bono' | 'pagos'
const TABS: [Tab, string][] = [
  ['todo', 'Todo'],
  ['salario', 'Salario'],
  ['comision', 'Comisiones'],
  ['bono', 'Bonos'],
  ['pagos', 'Pagos recibidos'],
]
const tab = ref<Tab>((['todo', 'salario', 'comision', 'bono', 'pagos'] as Tab[]).includes(route.query.tab as Tab) ? (route.query.tab as Tab) : 'todo')
const estado = ref('todas')
const mes = ref('todo')
const meses = ultimosMeses(4)

const FILTROS = computed<[string, string][]>(() =>
  tab.value === 'pagos'
    ? [['todas', 'Todos'], ['pagado', 'Pagados'], ['en_proceso', 'En proceso']]
    : [['todas', tab.value === 'bono' ? 'Todos' : 'Todas'], ['generada', tab.value === 'bono' ? 'Generados' : 'Generadas'], ['pend', 'Pendientes'], ['pagada', tab.value === 'bono' ? 'Pagados' : 'Pagadas']],
)
watch(tab, () => (estado.value = 'todas'))
const enMes = (iso: string) => mes.value === 'todo' || iso.slice(0, 7) === mes.value

const filas = computed(() => {
  if (!data.value) return []
  if (tab.value === 'pagos')
    return data.value.pagos
      .filter((p) => enMes(p.fecha) && (estado.value === 'todas' || p.estado === estado.value))
      .map((p) => ({ id: p.id, concepto: p.concepto, detalle: p.detalle, fecha: diaMes(p.fecha), valor: p.valor, se_paga: diaMes(p.fecha), estado: p.estado, estado_txt: p.estado_txt }))
  return data.value.items
    .filter((r) => (tab.value === 'todo' || r.clase === tab.value) && enMes(r.fecha))
    .filter((r) =>
      estado.value === 'todas'
        ? true
        : estado.value === 'pend'
          ? !['generada', 'pagada', 'pagado', 'anulada'].includes(r.estado)
          : estado.value === 'pagada'
            ? ['pagada', 'pagado'].includes(r.estado)
            : r.estado === estado.value,
    )
    .map((r) => ({ ...r, fecha: diaMes(r.fecha) }))
})
const sumBy = (pred: (e: string) => boolean) =>
  fmtCOP(
    tab.value === 'pagos'
      ? (data.value?.pagos ?? []).filter((p) => pred(p.estado)).reduce((s, p) => s + p.valor, 0)
      : (data.value?.items ?? []).filter((r) => (tab.value === 'todo' || r.clase === tab.value) && pred(r.estado)).reduce((s, r) => s + r.valor, 0),
  )
const tot = computed(() =>
  tab.value === 'pagos'
    ? [
        { t: 'Pagado', v: sumBy((e) => e === 'pagado') },
        { t: 'En proceso', v: sumBy((e) => e === 'en_proceso') },
        { t: 'Número de pagos', v: String(data.value?.pagos.length ?? 0) },
      ]
    : [
        { t: tab.value === 'bono' ? 'Generados' : 'Generadas', v: sumBy((e) => e === 'generada' || e === 'por_confirmar') },
        { t: 'Pendientes', v: sumBy((e) => ['visto_bueno', 'pendiente_pago', 'confirmado'].includes(e)) },
        { t: tab.value === 'bono' ? 'Pagados' : 'Pagadas', v: sumBy((e) => e === 'pagada' || e === 'pagado') },
      ],
)
const sub = computed(() => {
  const n = auth.user.value?.full_name ?? ''
  if (perfil.value === 'coordinacion') return `${n} · Coordinador · salario de tu cargo, comisión por meta grupal y bono por rendimiento`
  if (perfil.value === 'atencion') return `${n} · Atención y Preventa · salario de tu cargo, comisiones por citas que terminan en negocio y bono por rendimiento`
  if (perfil.value === 'asesor') return `${n} · salario, comisiones por negocios y bono por rendimiento`
  return `${n} · salario de tu cargo`
})
const COMO = computed(() =>
  tab.value === 'comision'
    ? 'Una comisión se genera cuando se cierra un negocio en el que participaste. Cuenta lo cerrado hasta el último día del mes y se paga el 5 del mes siguiente, aparte del salario.'
    : tab.value === 'bono'
      ? 'Un bono se genera cuando cumples la condición que define Gerencia. Pasa a «pendiente de pago» cuando se aprueba, y a «pagado» cuando se registra el pago.'
      : 'Comisiones y bonos se pagan el 5 de cada mes. El salario se paga aparte, en dos cortes: el 15 y el 30. Un pago «en proceso» ya fue aprobado y está por transferirse.',
)
const home = computed(() => (perfil.value === 'asesor' ? '/asesor' : perfil.value === 'atencion' ? '/leads' : perfil.value === 'coordinacion' ? '/coordinacion' : '/'))
</script>

<template>
  <PageBar title="Mis pagos y bonos" :subtitle="sub" :back="home" />
  <div class="cnt narrow">
    <div v-if="error" class="note bad"><b>No se pudo cargar.</b> {{ apiErrorMessage(error) }}</div>
    <template v-else-if="data">
      <div class="g4 kpis">
        <div class="card"><div class="lbl">Pagado</div><div class="kn num">{{ fmtCOP(data.kpis.pagado) }}</div><div class="mut tiny">transferencias registradas</div></div>
        <div class="card"><div class="lbl">Por pagar</div><div class="kn num">{{ fmtCOP(data.kpis.por_pagar) }}</div><div class="mut tiny">aprobado o por confirmar</div></div>
        <div class="card"><div class="lbl">Comisiones y bonos</div><div class="kn num">{{ fmtCOP(data.kpis.comisiones_bonos) }}</div><div class="mut tiny">todo el historial</div></div>
        <div class="card"><div class="lbl">Próximo pago</div><div class="kn num">{{ data.kpis.proximo ?? '—' }}</div><div class="mut tiny">{{ data.kpis.proximo_txt ?? 'nada pendiente' }}</div></div>
      </div>

      <div class="card stack">
        <div class="sb">
          <span class="lbl">Cómo ganas</span>
          <NuxtLink v-if="puntaje?.total != null" to="/resultados" class="small">Ver mi rendimiento · {{ SEM[semDe(puntaje.total)!].sym }} {{ puntaje.total }}% ›</NuxtLink>
        </div>
        <div v-for="c in data.como_ganas" :key="c.titulo" class="como">
          <b class="small">{{ c.titulo }}</b>
          <span class="mut small">{{ c.detalle }}</span>
        </div>
        <span class="chip pend self-start">Porcentajes, condiciones y montos: valores de ejemplo · PENDIENTE DE CONFIGURACIÓN</span>
      </div>

      <div class="tabs scroll-x">
        <button v-for="[k, t] in TABS" :key="k" type="button" class="tab" :class="{ on: tab === k }" @click="tab = k">{{ t }}</button>
      </div>
      <div v-if="tab !== 'todo'" class="g3 tot">
        <div v-for="t in tot" :key="t.t" class="st card"><div class="lbl">{{ t.t }}</div><div class="num big">{{ t.v }}</div></div>
      </div>
      <div class="row fw gap6">
        <template v-if="tab !== 'todo' && tab !== 'salario'">
          <button v-for="[k, t] in FILTROS" :key="k" type="button" class="fch" :class="{ on: estado === k }" @click="estado = k">{{ t }}</button>
        </template>
        <select v-model="mes" class="fsel" aria-label="Mes">
          <option value="todo">Todo el año</option>
          <option v-for="m in meses" :key="m.key" :value="m.key">{{ m.t.charAt(0).toUpperCase() + m.t.slice(1) }}</option>
        </select>
      </div>

      <!-- Desktop: Z05 table -->
      <div class="card desk">
        <div class="wrap">
          <table class="tbl">
            <thead><tr><th>Concepto</th><th>Fecha</th><th>Valor</th><th>Se paga</th><th>Estado</th></tr></thead>
            <tbody>
              <tr v-for="r in filas" :key="r.id">
                <td><b>{{ r.concepto }}</b><div class="mut tiny">{{ r.detalle }}</div></td>
                <td>{{ r.fecha }}</td>
                <td class="num">{{ fmtCOP(r.valor) }}</td>
                <td>{{ r.se_paga }}</td>
                <td><span class="chip" :class="COMP_CLS[r.estado]">{{ r.estado_txt }}</span></td>
              </tr>
              <tr v-if="!filas.length"><td colspan="5" class="mut empty">No hay registros con este filtro.</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <!-- Mobile: M12–M14 cards -->
      <div class="mob stack-cards">
        <div v-for="r in filas" :key="r.id" class="card stack">
          <div class="sb"><b class="small">{{ r.concepto }}</b><span class="chip" :class="COMP_CLS[r.estado]">{{ r.estado_txt }}</span></div>
          <div class="sb small"><span class="mut">{{ r.fecha }} · se paga {{ r.se_paga }}</span><b class="num">{{ fmtCOP(r.valor) }}</b></div>
          <span class="mut tiny">{{ r.detalle }}</span>
        </div>
        <div v-if="!filas.length" class="note">No hay registros con este filtro.</div>
      </div>

      <div class="card stack">
        <div class="lbl">Cómo funciona</div>
        <div class="small">{{ COMO }}</div>
        <div class="mut small">
          Solo puedes consultar esta información. Crear, aprobar o registrar pagos lo hacen la Auxiliar administrativa (visto bueno) y
          Gerencia (aprobación y pago), y cada cambio queda registrado.
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.narrow {
  max-width: 1080px;
  width: 100%;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stack-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.como {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.self-start {
  align-self: flex-start;
}
.fw {
  flex-wrap: wrap;
}
.gap6 {
  gap: 6px;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.big {
  font-size: 22px;
}
.scroll-x {
  overflow-x: auto;
}
.empty {
  text-align: center;
  padding: 24px 10px;
}
.mob {
  display: none;
}
@media (max-width: 760px) {
  .desk {
    display: none;
  }
  .mob {
    display: flex;
  }
  .kpis {
    grid-template-columns: 1fr 1fr;
  }
  .kpis .kn {
    font-size: 24px;
  }
  .big {
    font-size: 15px;
  }
  .tot {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px;
  }
  .tot .card {
    padding: 10px;
  }
}
</style>
