<script setup lang="ts">
import type { CierreRead, CompItem, EventoComp, PagoRead } from '~/types/compensacion'

/**
 * G05 «Comisiones, bonos y pagos» (Gerencia) · G05-aux (Auxiliar administrativa).
 * The Auxiliar gives the first visto bueno; Gerencia approves and records the payment.
 * Plus «Negocios cerrados» (enter the ganancia → commissions) and the configuration.
 */
definePageMeta({ cargos: ['gerencia', 'auxiliar_administrativa'] })
useHead({ title: 'Comisiones, bonos y pagos · Casa Dolce Casa' })

const comp = useCompensacion()
const { data, error, refresh } = await useAsyncData('compensacion', () => comp.tablero())
const ger = computed(() => !!data.value?.es_gerencia)
const aux = computed(() => !!data.value?.es_auxiliar)

type Tab = 'com' | 'bon' | 'pag' | 'neg' | 'cfg'
const tab = ref<Tab>('com')
const TABS: [Tab, string][] = [['com', 'Comisiones'], ['bon', 'Bonos'], ['pag', 'Pagos'], ['neg', 'Negocios cerrados'], ['cfg', 'Configuración']]
const estado = ref('todas')
const persona = ref('todas')
const msg = ref<{ t: string; ok: boolean } | null>(null)
const busy = ref(false)
watch(tab, () => {
  estado.value = 'todas'
  msg.value = null
  form.open = false
  ask.value = null
  hist.value = null
})

const FIL = computed<[string, string][]>(() => {
  if (tab.value === 'pag') return [['todas', 'Todos'], ['en_proceso', 'En proceso'], ['pagado', 'Pagados']]
  const f = tab.value === 'bon'
  return [['todas', f ? 'Todos' : 'Todas'], ['generada', f ? 'Generados' : 'Generadas'], ['visto_bueno', 'Con visto bueno'], ['pendiente_pago', 'Pendientes de pago'], ['pagada', f ? 'Pagados' : 'Pagadas'], ['anulada', f ? 'Anulados' : 'Anuladas']]
})
const items = computed<CompItem[]>(() => (tab.value === 'bon' ? data.value?.bonos : data.value?.comisiones) ?? [])
const filas = computed(() =>
  items.value.filter((r) => (estado.value === 'todas' || r.estado === estado.value) && (persona.value === 'todas' || r.beneficiario.id === persona.value)),
)
const pagos = computed<PagoRead[]>(() =>
  (data.value?.pagos ?? []).filter((r) => (estado.value === 'todas' || r.estado === estado.value) && (persona.value === 'todas' || r.beneficiario.id === persona.value)),
)
const tot = computed(() => {
  const t = data.value?.totales
  if (!t) return []
  if (tab.value === 'pag') return [{ t: 'En proceso', v: fmtCOP(t.pago.en_proceso) }, { t: 'Pagado', v: fmtCOP(t.pago.pagado) }, { t: 'Registros', v: String(data.value!.pagos.length) }]
  const x = t[tab.value === 'bon' ? 'bono' : 'comision']!
  const f = tab.value === 'bon'
  return [
    { t: f ? 'Generados' : 'Generadas', v: fmtCOP(x.generada) },
    { t: 'Con visto bueno', v: fmtCOP(x.visto_bueno) },
    { t: 'Pendientes de pago', v: fmtCOP(x.pendiente_pago) },
    { t: f ? 'Pagados' : 'Pagadas', v: fmtCOP(x.pagada) },
  ]
})

/** The next step this role can take (G05 NEXT). */
const siguiente = (r: CompItem): [string, string] | null => {
  if (r.estado === 'generada' && aux.value) return ['visto_bueno', 'Dar visto bueno']
  if (r.estado === 'visto_bueno' && ger.value) return ['aprobar', 'Aprobar']
  if (r.estado === 'pendiente_pago' && ger.value) return ['pagar', 'Registrar pago']
  return null
}
const espera = (r: CompItem) =>
  r.estado === 'generada' ? 'Esperando visto bueno de la Auxiliar' : r.estado === 'visto_bueno' || r.estado === 'pendiente_pago' ? 'Esperando a Gerencia' : ''

// ---- confirm / adjust / cancel (G05 confirm card)
const ask = ref<{ r: CompItem; accion: string; label: string } | null>(null)
const ajuste = reactive({ valor: '', motivo: '' })
function preguntar(r: CompItem, accion: string, label: string) {
  ask.value = { r, accion, label }
  ajuste.valor = String(r.valor)
  ajuste.motivo = ''
  msg.value = null
}
async function confirmar() {
  if (!ask.value) return
  const { r, accion, label } = ask.value
  busy.value = true
  try {
    const clase = r.clase === 'bono' ? 'bonos' : 'comisiones'
    const extra = accion === 'ajustar' ? { valor: parsePesos(ajuste.valor), motivo: ajuste.motivo } : accion === 'anular' ? { motivo: ajuste.motivo } : {}
    const out = await comp.accion(clase, r.id, accion, extra)
    msg.value = { t: `Listo: ${r.concepto} · ${label.toLowerCase()} → «${out.estado_txt}». Queda en el historial.`, ok: true }
    ask.value = null
    await refresh()
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  } finally {
    busy.value = false
  }
}
async function pagarPago(p: PagoRead) {
  busy.value = true
  try {
    await comp.pagar(p.id)
    msg.value = { t: `Pago registrado: ${p.concepto} · ${fmtCOP(p.valor)}. ${p.beneficiario.full_name} lo ve en «Pagos».`, ok: true }
    await refresh()
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  } finally {
    busy.value = false
  }
}

// ---- history
const hist = ref<{ id: string; t: string; ev: EventoComp[] } | null>(null)
async function verHistorial(r: CompItem) {
  if (hist.value?.id === r.id) return (hist.value = null)
  hist.value = { id: r.id, t: r.concepto, ev: await comp.historial(r.clase, r.id) }
}

// ---- manual record
const form = reactive({ open: false, persona: '', concepto: '', fecha: localDate(), valor: '', cierre: '' })
async function guardarManual() {
  busy.value = true
  try {
    await comp.crear(tab.value === 'bon' ? 'bonos' : 'comisiones', {
      beneficiario_id: form.persona,
      concepto: form.concepto,
      valor: parsePesos(form.valor),
      fecha: toIso(form.fecha, '12:00'),
      cierre_id: form.cierre || null,
    })
    msg.value = { t: `Registro guardado. ${data.value?.personas.find((x) => x.id === form.persona)?.full_name} ya lo ve en su sección. Quedó en el historial.`, ok: true }
    Object.assign(form, { open: false, persona: '', concepto: '', valor: '', cierre: '' })
    await refresh()
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  } finally {
    busy.value = false
  }
}

// ---- closed deals
const gan = reactive<Record<string, { g: string; cap: string }>>({})
watchEffect(() => {
  for (const c of data.value?.cierres ?? []) if (!gan[c.id]) gan[c.id] = { g: c.ganancia ? c.ganancia.toLocaleString('es-CO') : '', cap: c.captador?.id ?? '' }
})
async function guardarGanancia(c: CierreRead) {
  busy.value = true
  try {
    await comp.ganancia(c.id, parsePesos(gan[c.id]!.g), gan[c.id]!.cap || null)
    msg.value = { t: `${c.code}: ganancia registrada. Las comisiones quedaron «Generadas» para el visto bueno.`, ok: true }
    await refresh()
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  } finally {
    busy.value = false
  }
}
const sinGanancia = computed(() => (data.value?.cierres ?? []).filter((c) => c.estado === 'cerrado' && !c.ganancia).length)

// ---- month-end and config
const mesAnterior = ultimosMeses(2)[1]!
async function calcular() {
  busy.value = true
  try {
    const r = await comp.calcular(mesAnterior.key)
    msg.value = { t: `${mesAnterior.t}: ${r.bonos} bono${r.bonos === 1 ? '' : 's'} por rendimiento y ${r.grupal} comisión grupal generados (los que ya existían no se repiten).`, ok: true }
    await refresh()
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  } finally {
    busy.value = false
  }
}
const cfg = reactive<Record<string, string>>({})
watchEffect(() => {
  for (const [k, v] of Object.entries(data.value?.config ?? {})) if (cfg[k] === undefined) cfg[k] = String(v)
})
async function guardarConfig() {
  busy.value = true
  try {
    const valores = Object.fromEntries(Object.entries(cfg).map(([k, v]) => [k, k === 'modalidad_coordinador' ? v : Number(String(v).replace(',', '.'))]))
    await comp.config(valores)
    msg.value = { t: 'Configuración guardada. Aplica a lo que se genere desde ahora y queda en el historial.', ok: true }
    await refresh()
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  } finally {
    busy.value = false
  }
}
const descargar = () => comp.descargar(tab.value === 'bon' ? 'bonos' : tab.value === 'pag' ? 'pagos' : 'comisiones')
const PEND: Record<string, string> = {
  com: 'Porcentajes de comisión y pagos parciales en las ventas: PENDIENTE DE CONFIGURACIÓN',
  bon: 'Tipos de bono, condiciones y montos: PENDIENTE DE CONFIGURACIÓN',
  pag: 'Forma de pago: PENDIENTE DE CONFIGURACIÓN',
}
</script>

<template>
  <PageBar
    title="Comisiones, bonos y pagos"
    subtitle="La Auxiliar administrativa da el primer visto bueno y Gerencia aprueba y registra el pago · se pagan el día 5 de cada mes, aparte del salario"
    :back="ger ? '/coordinacion' : '/'"
  >
    <NuxtLink class="btn bs" to="/salarios">Salarios del mes ›</NuxtLink>
  </PageBar>

  <div class="cnt">
    <div v-if="error" class="note bad"><b>No se pudo cargar.</b> {{ apiErrorMessage(error) }}</div>
    <template v-else-if="data">
      <div class="tabs">
        <button v-for="[k, t] in TABS" :key="k" type="button" class="tab" :class="{ on: tab === k }" @click="tab = k">
          {{ t }}<span v-if="k === 'neg' && sinGanancia" class="chip warn cnt-chip">{{ sinGanancia }}</span>
        </button>
      </div>
      <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.ok ? '✓ ' : '' }}{{ msg.t }}</b></div>

      <!-- ============ Comisiones / Bonos / Pagos ============ -->
      <template v-if="tab === 'com' || tab === 'bon' || tab === 'pag'">
        <div :class="tab === 'pag' ? 'g3' : 'g4'">
          <div v-for="t in tot" :key="t.t" class="card"><div class="lbl">{{ t.t }}</div><div class="kn num">{{ t.v }}</div></div>
        </div>
        <div class="sb fw gap6">
          <div class="row fw gap6">
            <select v-model="persona" class="fsel" aria-label="Persona">
              <option value="todas">Todas las personas</option>
              <option v-for="x in data.personas" :key="x.id" :value="x.id">{{ x.full_name }}</option>
            </select>
            <button v-for="[k, t] in FIL" :key="k" type="button" class="fch" :class="{ on: estado === k }" @click="estado = k">{{ t }}</button>
          </div>
          <div class="row fw gap6">
            <button type="button" class="btn bs sm" @click="descargar">Descargar (Excel)</button>
            <button v-if="tab === 'bon'" type="button" class="btn bs sm" :disabled="busy" @click="calcular">Calcular bonos de {{ mesAnterior.t.split(' ')[0] }}</button>
            <button v-if="tab !== 'pag'" type="button" class="btn bp sm" @click="form.open = !form.open">+ Registrar {{ tab === 'bon' ? 'bono' : 'comisión' }}</button>
          </div>
        </div>

        <form v-if="form.open && tab !== 'pag'" class="card stack" @submit.prevent="guardarManual">
          <b>+ Registrar {{ tab === 'bon' ? 'bono' : 'comisión' }}</b>
          <div class="g4">
            <div class="fld">
              <label for="m-p">Persona <span class="req">*</span></label>
              <select id="m-p" v-model="form.persona" class="in" required><option value="" disabled>Elige…</option><option v-for="x in data.personas" :key="x.id" :value="x.id">{{ x.full_name }}</option></select>
            </div>
            <div class="fld"><label for="m-c">Concepto <span class="req">*</span></label><input id="m-c" v-model="form.concepto" class="in" required :placeholder="tab === 'bon' ? 'Bono por meta' : 'Comisión por venta cerrada'"></div>
            <div class="fld"><label for="m-f">Fecha <span class="req">*</span></label><input id="m-f" v-model="form.fecha" class="in" type="date" :max="localDate()" required></div>
            <div class="fld"><label for="m-v">Valor <span class="req">*</span></label><input id="m-v" v-model="form.valor" class="in" inputmode="numeric" placeholder="$0" required></div>
          </div>
          <div v-if="tab === 'com'" class="fld">
            <label for="m-n">Negocio relacionado</label>
            <select id="m-n" v-model="form.cierre" class="in"><option value="">Ninguno</option><option v-for="c in data.cierres" :key="c.id" :value="c.id">{{ c.code }} · {{ c.negocio ?? '—' }} · {{ c.cliente }}</option></select>
          </div>
          <div class="note">Queda en estado «{{ tab === 'bon' ? 'Generado' : 'Generada' }}» hasta el visto bueno y la aprobación. La persona lo ve en «Mis pagos y bonos».</div>
          <div class="row gap6"><button type="submit" class="btn bp" :disabled="busy">Guardar</button><button type="button" class="btn bs" @click="form.open = false">Cancelar</button></div>
        </form>

        <div v-if="ask" class="card stack confirm">
          <b>¿{{ ask.label }}: {{ ask.r.concepto }}?</b>
          <span class="mut small">{{ ask.r.beneficiario.full_name }} · {{ fmtCOP(ask.r.valor) }}. El cambio queda en el historial con el estado anterior y el nuevo, y la persona lo ve en su sección.</span>
          <div v-if="ask.accion === 'ajustar' || ask.accion === 'anular'" class="g2">
            <div v-if="ask.accion === 'ajustar'" class="fld"><label for="a-v">Nuevo valor <span class="req">*</span></label><input id="a-v" v-model="ajuste.valor" class="in" inputmode="numeric"></div>
            <div class="fld"><label for="a-m">Motivo <span class="req">*</span></label><input id="a-m" v-model="ajuste.motivo" class="in" placeholder="Por qué"></div>
          </div>
          <div class="row gap6">
            <button type="button" class="btn" :class="ask.accion === 'anular' ? 'br' : 'bp'" :disabled="busy" @click="confirmar">Sí, confirmar</button>
            <button type="button" class="btn bs" @click="ask = null">Cancelar</button>
          </div>
        </div>

        <div class="card">
          <div class="wrap">
            <table v-if="tab !== 'pag'" class="tbl t-comp">
              <thead><tr><th>Persona</th><th>Concepto</th><th>Fecha</th><th>Valor</th><th>Se paga</th><th>Estado</th><th>Acciones</th></tr></thead>
              <tbody>
                <template v-for="r in filas" :key="r.id">
                  <tr>
                    <td><b>{{ r.beneficiario.full_name }}</b></td>
                    <td>{{ r.concepto }}<div class="mut tiny">{{ r.detalle }}</div></td>
                    <td>{{ diaMes(r.fecha) }}</td>
                    <td class="num"><b>{{ fmtCOP(r.valor) }}</b></td>
                    <td>{{ r.se_paga }}</td>
                    <td><span class="chip" :class="COMP_CLS[r.estado]">{{ r.estado_txt }}</span></td>
                    <td>
                      <div class="row fw gap6">
                        <button v-if="siguiente(r)" type="button" class="btn bp sm" @click="preguntar(r, siguiente(r)![0], siguiente(r)![1])">{{ siguiente(r)![1] }}</button>
                        <span v-else-if="espera(r)" class="mut tiny">{{ espera(r) }}</span>
                        <button v-if="r.estado === 'generada' || r.estado === 'visto_bueno'" type="button" class="btn bs sm" @click="preguntar(r, 'ajustar', 'Ajustar valor')">Ajustar</button>
                        <button v-if="!['pagada', 'anulada'].includes(r.estado)" type="button" class="btn bs sm ghost" @click="preguntar(r, 'anular', 'Anular')">Anular</button>
                        <button type="button" class="btn bs sm ghost" @click="verHistorial(r)">Historial</button>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="hist?.id === r.id" class="hist">
                    <td colspan="7">
                      <div v-for="(e, i) in hist.ev" :key="i" class="sb small">
                        <span>{{ e.accion }}</span>
                        <span class="mut tiny">{{ fmtCuando(e.created_at) }} · {{ e.created_by_name ?? 'Sistema' }}</span>
                      </div>
                    </td>
                  </tr>
                </template>
                <tr v-if="!filas.length"><td colspan="7" class="mut empty">No hay registros con este filtro.</td></tr>
              </tbody>
            </table>
            <table v-else class="tbl t-comp">
              <thead><tr><th>Persona</th><th>Concepto</th><th>Fecha</th><th>Valor</th><th>Tipo</th><th>Estado</th><th>Acciones</th></tr></thead>
              <tbody>
                <tr v-for="p in pagos" :key="p.id">
                  <td><b>{{ p.beneficiario.full_name }}</b></td>
                  <td>{{ p.concepto }}</td>
                  <td>{{ diaMes(p.fecha_programada) }}</td>
                  <td class="num"><b>{{ fmtCOP(p.valor) }}</b></td>
                  <td>{{ p.tipo === 'salario' ? 'Salario' : p.tipo === 'bono' ? 'Bono' : 'Comisión' }}</td>
                  <td><span class="chip" :class="COMP_CLS[p.estado]">{{ p.estado_txt }}</span></td>
                  <td>
                    <button v-if="p.estado === 'en_proceso' && ger" type="button" class="btn bp sm" :disabled="busy" @click="pagarPago(p)">Marcar pagado</button>
                    <span v-else-if="p.estado === 'en_proceso'" class="mut tiny">Esperando a Gerencia</span>
                  </td>
                </tr>
                <tr v-if="!pagos.length"><td colspan="7" class="mut empty">No hay pagos con este filtro.</td></tr>
              </tbody>
            </table>
          </div>
          <div class="row fw gap6 foot">
            <span class="chip pend">{{ PEND[tab] }}</span>
            <span class="mut tiny">Cuenta lo cerrado hasta el último día del mes y se paga el 5 del mes siguiente. Valores de ejemplo. Cada creación, cambio, aprobación o pago queda en el historial.</span>
          </div>
        </div>
      </template>

      <!-- ============ Negocios cerrados ============ -->
      <div v-else-if="tab === 'neg'" class="card stack">
        <div class="note">
          Cada lead «Ganado» es un negocio (<NuxtLink to="/negocios" class="lnk">ver en «Negocios»</NuxtLink>). Cuando la Auxiliar confirma la firma y da
          «negocio cerrado», la <b>ganancia efectiva</b> (lo que recibe la inmobiliaria después de referidos, sin IVA) se calcula con el valor del
          negocio y las tarifas de Gerencia, y el sistema genera las comisiones de quien cerró, quien captó y Atención y Preventa. Aquí puedes elegir
          quién captó el inmueble o registrarla a mano si el negocio no tiene valor. Si el negocio cae, sus comisiones sin pagar se anulan.
        </div>
        <div class="wrap">
          <table class="tbl t-neg">
            <thead><tr><th>Negocio</th><th>Cliente</th><th>Cerrado</th><th>Cerró</th><th>Atención</th><th>Captó</th><th>Ganancia efectiva</th><th /></tr></thead>
            <tbody>
              <tr v-for="c in data.cierres" :key="c.id" :class="{ caido: c.estado === 'caido' }">
                <td><b>{{ c.code }}</b><div class="mut tiny">{{ c.negocio ?? '—' }} · {{ c.lead_code }}</div></td>
                <td>{{ c.cliente }}</td>
                <td>{{ diaMes(c.cerrado_at) }}</td>
                <td>{{ c.cerrador?.full_name ?? '—' }}</td>
                <td>{{ c.filtro?.full_name ?? '—' }}</td>
                <td>
                  <select v-if="c.estado === 'cerrado'" v-model="gan[c.id]!.cap" class="sel" :aria-label="`Captador de ${c.code}`">
                    <option value="">Sin captador</option>
                    <option v-for="x in data.captadores" :key="x.id" :value="x.id">{{ x.full_name }}</option>
                  </select>
                  <span v-else>{{ c.captador?.full_name ?? '—' }}</span>
                </td>
                <td>
                  <input v-if="c.estado === 'cerrado'" v-model="gan[c.id]!.g" class="in gin" inputmode="numeric" placeholder="$0" :aria-label="`Ganancia de ${c.code}`">
                  <span v-else class="chip gray">Caído</span>
                </td>
                <td>
                  <button v-if="c.estado === 'cerrado'" type="button" class="btn sm" :class="c.ganancia ? 'bs' : 'bp'" :disabled="busy" @click="guardarGanancia(c)">{{ c.ganancia ? 'Actualizar' : 'Guardar' }}</button>
                </td>
              </tr>
              <tr v-if="!data.cierres.length"><td colspan="8" class="mut empty">Aún no hay leads ganados.</td></tr>
            </tbody>
          </table>
        </div>
        <span class="chip pend self-start">Comisión parcial por cada pago recibido en ventas: PENDIENTE DE CONFIGURACIÓN.</span>
      </div>

      <!-- ============ Configuración ============ -->
      <div v-else class="card stack">
        <div class="lbl">Porcentajes, montos y fechas de pago</div>
        <div class="g2">
          <div v-for="(label, k) in data.config_labels" :key="k" class="fld">
            <label :for="`cfg-${k}`">{{ label }}</label>
            <select v-if="k === 'modalidad_coordinador'" :id="`cfg-${k}`" v-model="cfg[k]" class="in" :disabled="!ger">
              <option value="bono">Bono individual</option><option value="grupal">Comisión por meta grupal</option><option value="ambos">Ambos</option>
            </select>
            <input v-else :id="`cfg-${k}`" v-model="cfg[k]" class="in" inputmode="decimal" :disabled="!ger">
          </div>
        </div>
        <div v-if="ger"><button type="button" class="btn bp" :disabled="busy" @click="guardarConfig">Guardar configuración</button></div>
        <div v-else class="note">Solo lectura: los valores los configura Gerencia.</div>
        <div class="mut tiny">
          Ejemplo: ganancia efectiva $10.000.000 → personal 33,3 % = $3.330.000 → quien cierra 70 % = $2.331.000 y quien captó 30 % = $999.000;
          Atención y Preventa 5 % = $500.000. Todos son valores de ejemplo: PENDIENTE DE CONFIGURACIÓN.
        </div>
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
.self-start {
  align-self: flex-start;
}
.t-comp {
  min-width: 980px;
}
.t-neg {
  min-width: 1000px;
}
.gin {
  min-width: 130px;
}
.ghost {
  border-color: var(--cdc-border);
  color: var(--cdc-muted);
}
.confirm {
  border: 2px solid var(--cdc-green);
}
.hist td {
  background: #fafbf9;
}
tr.caido td {
  opacity: 0.55;
}
.cnt-chip {
  margin-left: 6px;
  padding: 0 6px;
}
.foot {
  margin-top: 10px;
}
.empty {
  text-align: center;
  padding: 24px 10px;
}
.lnk {
  color: var(--cdc-green);
  font-weight: 700;
}
</style>
