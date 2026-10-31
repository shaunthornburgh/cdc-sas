<script setup lang="ts">
import type { Liquidacion } from '~/types/compensacion'

/**
 * X04 «Salarios del mes»: two pay periods (15 and 30). The Auxiliar confirms the salary to pay,
 * Gerencia approves and pays. Gerencia sets each person's monthly salary.
 */
definePageMeta({ cargos: ['gerencia', 'auxiliar_administrativa'] })
useHead({ title: 'Salarios del mes · Casa Dolce Casa' })

const comp = useCompensacion()
const meses = ultimosMeses(3)
const periodo = ref(meses[0]!.key)
const corte = ref(new Date().getDate() > 15 ? 2 : 1)
const { data, error, refresh } = await useAsyncData('salarios', () => comp.salarios(periodo.value, corte.value), { watch: [periodo, corte] })
const ger = computed(() => !!data.value?.es_gerencia)
const msg = ref<{ t: string; ok: boolean } | null>(null)
const busy = ref(false)

const sig = (l: Liquidacion): ['confirmar' | 'pagar', string] | null =>
  ger.value ? (l.estado === 'confirmado' ? ['pagar', 'Aprobar y pagar'] : null) : l.estado === 'por_confirmar' ? ['confirmar', 'Confirmar a pagar'] : null
const espera = (l: Liquidacion) => (l.estado === 'por_confirmar' ? 'Esperando a la Auxiliar' : l.estado === 'confirmado' ? 'Esperando a Gerencia' : '')
const pendientes = computed(() => (data.value?.filas ?? []).filter((l) => sig(l)))
const total = computed(() => (data.value?.filas ?? []).reduce((s, l) => s + l.a_pagar, 0))
const desc = computed(() => (data.value?.filas ?? []).reduce((s, l) => s + l.descuento, 0))
const nConf = computed(() => (data.value?.filas ?? []).filter((l) => l.estado !== 'por_confirmar').length)
const nPag = computed(() => (data.value?.filas ?? []).filter((l) => l.estado === 'pagado').length)
const mesTxt = computed(() => meses.find((m) => m.key === periodo.value)?.t.split(' ')[0] ?? '')
const CORTES = computed(() => [
  [1, `1.er corte · 1 al 15 ${mesTxt.value.slice(0, 3)} · se paga el 15`],
  [2, `2.º corte · 16 al 30 ${mesTxt.value.slice(0, 3)} · se paga el 30`],
] as [number, string][])

async function run(accion: 'confirmar' | 'pagar', filas: Liquidacion[]) {
  busy.value = true
  try {
    await comp.accionSalarios(accion, filas.map((f) => f.id))
    const quien = filas.length === 1 ? filas[0]!.user.full_name : `${filas.length} personas`
    msg.value = {
      t: accion === 'confirmar' ? `${quien}: salario confirmado. Gerencia recibió el aviso para aprobar y pagar.` : `${quien}: pago de salario registrado. Cada persona lo ve en «Mis pagos y bonos».`,
      ok: true,
    }
    await refresh()
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  } finally {
    busy.value = false
  }
}

const editando = ref<string | null>(null)
const nuevo = ref('')
async function guardarSalario(userId: string, nombre: string) {
  busy.value = true
  try {
    await comp.setSalario(userId, parsePesos(nuevo.value))
    msg.value = { t: `Salario de ${nombre} guardado. Los cortes por confirmar toman el nuevo valor. Queda en el historial.`, ok: true }
    editando.value = null
    await refresh()
  } catch (e) {
    msg.value = { t: apiErrorMessage(e), ok: false }
  } finally {
    busy.value = false
  }
}
function editar(id: string, actual: number | null) {
  editando.value = editando.value === id ? null : id
  nuevo.value = actual ? String(actual) : ''
}
</script>

<template>
  <PageBar
    title="Salarios del mes"
    subtitle="El salario se paga en dos cortes, los días 15 y 30 · la Auxiliar confirma y Gerencia aprueba y paga · comisiones y bonos van aparte, el 5 de cada mes"
    :back="ger ? '/coordinacion' : '/'"
  >
    <select v-model="periodo" class="fsel" aria-label="Mes">
      <option v-for="m in meses" :key="m.key" :value="m.key">{{ m.t }}</option>
    </select>
    <NuxtLink class="btn bs" to="/compensacion">Comisiones, bonos y pagos ›</NuxtLink>
  </PageBar>

  <div class="cnt">
    <div class="tabs">
      <button v-for="[c, t] in CORTES" :key="c" type="button" class="tab" :class="{ on: corte === c }" @click="corte = c; msg = null">{{ t }}</button>
    </div>
    <div v-if="error" class="note bad"><b>No se pudo cargar.</b> {{ apiErrorMessage(error) }}</div>
    <template v-else-if="data">
      <div v-if="msg" class="note" :class="msg.ok ? 'ok' : 'bad'" role="status"><b>{{ msg.ok ? '✓ ' : '' }}{{ msg.t }}</b></div>
      <div class="g3">
        <div class="card"><div class="lbl">Total a pagar el {{ diaMes(data.fecha_pago) }}</div><div class="kn num">{{ fmtCOP(total) }}</div><div class="mut tiny">ya con descuentos por novedades</div></div>
        <div class="card"><div class="lbl">Descuentos por novedades</div><div class="kn num">{{ fmtCOP(desc) }}</div><div class="mut tiny">incapacidades y permisos no remunerados</div></div>
        <div class="card"><div class="lbl">Estado</div><div class="kn num">{{ nConf }} de {{ data.filas.length }}</div><div class="mut tiny">{{ nPag }} pagados · confirmados por la Auxiliar</div></div>
      </div>

      <div class="card">
        <div class="wrap">
          <table class="tbl t-sal">
            <thead><tr><th>Empleado</th><th>Salario del corte</th><th>Novedades del mes</th><th>Descuento</th><th>A pagar</th><th>Estado</th><th>Acción</th></tr></thead>
            <tbody>
              <template v-for="l in data.filas" :key="l.id">
                <tr>
                  <td>
                    <b>{{ l.user.full_name }}</b><div class="mut tiny">{{ l.cargo_txt }} · {{ fmtCOP(l.salario_mensual) }} al mes</div>
                    <button v-if="ger" type="button" class="linkbtn tiny" @click="editar(l.user.id, l.salario_mensual)">Editar salario</button>
                  </td>
                  <td class="num">{{ fmtCOP(l.salario_corte) }}</td>
                  <td><span class="chip gray">{{ l.novedades }}</span></td>
                  <td class="num">{{ l.descuento ? `−${fmtCOP(l.descuento)}` : '$0' }}</td>
                  <td class="num"><b>{{ fmtCOP(l.a_pagar) }}</b></td>
                  <td><span class="chip" :class="COMP_CLS[l.estado]">{{ l.estado_txt }}</span></td>
                  <td>
                    <button v-if="sig(l)" type="button" class="btn bp sm" :disabled="busy" @click="run(sig(l)![0], [l])">{{ sig(l)![1] }}</button>
                    <span v-else class="mut tiny">{{ espera(l) }}</span>
                  </td>
                </tr>
                <tr v-if="editando === l.user.id" class="edit">
                  <td colspan="7">
                    <div class="row fw gap6">
                      <label :for="`s-${l.id}`" class="small">Salario mensual de {{ l.user.full_name }}</label>
                      <input :id="`s-${l.id}`" v-model="nuevo" class="in sin" inputmode="numeric">
                      <button type="button" class="btn bp sm" :disabled="busy" @click="guardarSalario(l.user.id, l.user.full_name)">Guardar</button>
                      <button type="button" class="btn bs sm" @click="editando = null">Cancelar</button>
                    </div>
                  </td>
                </tr>
              </template>
              <tr v-if="!data.filas.length"><td colspan="7" class="mut empty">Nadie tiene salario configurado todavía.</td></tr>
            </tbody>
          </table>
        </div>
        <div class="row fw gap6 foot">
          <button v-if="pendientes.length" type="button" class="btn bp" :disabled="busy" @click="run(ger ? 'pagar' : 'confirmar', pendientes)">
            {{ ger ? `Aprobar y pagar los ${pendientes.length} pendientes` : `Confirmar los ${pendientes.length} pendientes` }}
          </button>
          <span class="mut tiny">El permiso remunerado no descuenta. Descuento = días de incapacidad y de permiso no remunerado × (salario ÷ 30). Cada corte es la mitad del salario mensual.</span>
        </div>
        <div class="row fw gap6 foot">
          <NuxtLink class="chip info" to="/novedades">Novedades: se descuentan solas desde «Ausencias y permisos» ›</NuxtLink>
          <span class="chip pend">Asistencia (horas trabajadas): se descontará cuando exista ese módulo</span>
          <span class="chip pend">Valor de la hora extra y recargos: PENDIENTE DE CONFIGURACIÓN</span>
          <span class="chip pend">Deducciones de ley (salud, pensión) y auxilio de transporte: PENDIENTE DE CONFIGURACIÓN</span>
        </div>
      </div>

      <div v-if="data.sin_salario.length" class="card stack">
        <div class="lbl">Sin salario configurado</div>
        <div v-for="x in data.sin_salario" :key="x.id" class="sb it row-it">
          <span class="small">{{ x.full_name }}</span>
          <div v-if="ger" class="row gap6">
            <template v-if="editando === x.id">
              <input v-model="nuevo" class="in sin" inputmode="numeric" :aria-label="`Salario de ${x.full_name}`" placeholder="$0">
              <button type="button" class="btn bp sm" :disabled="busy" @click="guardarSalario(x.id, x.full_name)">Guardar</button>
            </template>
            <button v-else type="button" class="btn bs sm" @click="editar(x.id, null)">Poner salario</button>
          </div>
          <span v-else class="mut tiny">Lo configura Gerencia</span>
        </div>
      </div>
      <div class="note">
        Las comisiones y los bonos se pagan aparte, en «Comisiones, bonos y pagos». Cada confirmación, aprobación y pago queda en el historial.
        Las horas trabajadas (X03) necesitan «Marcar entrada y salida», que todavía no existe.
      </div>
    </template>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
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
.t-sal {
  min-width: 960px;
}
.sin {
  max-width: 180px;
}
.edit td {
  background: #fafbf9;
}
.foot {
  margin-top: 10px;
  align-items: center;
}
.empty {
  text-align: center;
  padding: 24px 10px;
}
.linkbtn {
  border: 0;
  background: none;
  padding: 0;
  color: var(--cdc-green);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}
</style>
