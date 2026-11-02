<script setup lang="ts">
import type { ConfigPagina, Marca } from '~/types/configuracion'

/**
 * Z02 «Configuración». Gerencia configures the whole tool (brand, pay dates, rates, alerts,
 * language, lead rules, pendientes para producción). Coordinación reads the pay dates and reaches
 * its team's settings through the cards.
 */
definePageMeta({ cargos: ['gerencia', 'coordinacion'] })
useHead({ title: 'Configuración · Casa Dolce Casa' })

const api = useConfiguracion()
const marcaApp = useMarca()
const { data, refresh } = await useAsyncData('configuracion', () => api.pagina())
const D = computed(() => data.value as ConfigPagina)
const ger = computed(() => !!D.value?.gerencia)

// One message per card, as in Z02
const msg = reactive<Record<string, { t: string; ok: boolean } | null>>({})
const say = (k: string, t: string, ok = true) => (msg[k] = { t, ok })
async function run(k: string, fn: () => Promise<unknown>, ok: string) {
  msg[k] = null
  try {
    await fn()
    say(k, ok)
    await refresh()
  } catch (e) {
    say(k, apiErrorMessage(e), false)
  }
}

// ---------------------------------------------------------------- Marca
const mk = reactive<Marca>({ ...(D.value?.marca ?? marcaApp.value) })
const VERDES: [keyof Marca, string, string][] = [
  ['color_principal', 'Verde principal', 'Botones, enlaces y elementos activos'],
  ['color_oscuro', 'Verde oscuro', 'Menú lateral'],
  ['color_claro', 'Verde claro', 'Detalles del logo y del menú'],
]
const fileIn = ref<HTMLInputElement | null>(null)
function subirLogo(ev: Event) {
  const f = (ev.target as HTMLInputElement).files?.[0]
  if (!f) return
  if (!['image/png', 'image/svg+xml'].includes(f.type)) return say('marca', 'El logo debe ser PNG o SVG.', false)
  if (f.size > 150_000) return say('marca', 'El logo es muy pesado: usa uno de menos de 150 KB.', false)
  const r = new FileReader()
  r.onload = () => {
    mk.logo = String(r.result)
    msg.marca = null
  }
  r.readAsDataURL(f)
}
const pvSide = computed(() => ({ background: mk.color_oscuro }))
async function guardarMarca() {
  if (!mk.nombre.trim()) return say('marca', 'Escribe el nombre de la empresa.', false)
  await run(
    'marca',
    async () => {
      marcaApp.value = await api.marca({ ...mk })
    },
    `Marca guardada: ${mk.nombre.trim()}${mk.logo ? ', logo propio' : ''} y colores ${mk.color_principal} · ${mk.color_oscuro} · ${mk.color_claro}. Se aplica en toda la herramienta y quedó en el registro de cambios.`,
  )
  Object.assign(mk, marcaApp.value)
}
async function restaurar() {
  await run(
    'marca',
    async () => {
      marcaApp.value = await api.restaurarMarca()
    },
    'Se volvió al logo, nombre y colores de Casa Dolce Casa.',
  )
  Object.assign(mk, marcaApp.value)
}

// ---------------------------------------------------------------- Pendientes
const nPend = computed(() => (D.value?.pendientes ?? []).filter((p) => !p.resuelto).length)
const marcar = (clave: string, resuelto: boolean) =>
  run('pend', () => api.pendiente(clave, resuelto), resuelto ? 'Marcado como definido. Queda en el registro de cambios.' : 'Vuelve a quedar pendiente.')
const usoReal = () => run('pend', () => api.usoReal(), 'Uso real activado. Queda en el registro de cambios.')

// ---------------------------------------------------------------- Fechas de pago
const fp = reactive({ ...(D.value?.pagos ?? { dia_corte_1: 15, dia_corte_2: 30, dia_pago: 5 }) })
const dias = (max: number) => Array.from({ length: max }, (_, i) => i + 1)
const fpRes = computed(() => `Salarios: los días ${fp.dia_corte_1} y ${fp.dia_corte_2} de cada mes. Comisiones y bonos: el día ${fp.dia_pago} del mes siguiente.`)
const guardarPagos = () => run('fp', () => api.pagos({ ...fp }), '✓ Fechas guardadas. «Salarios del mes», «Comisiones, bonos y pagos» y «Mis pagos» ya las usan.')

// ---------------------------------------------------------------- Tarifas
const tf = reactive<Record<string, string>>(
  Object.fromEntries(Object.entries(D.value?.tarifas ?? {}).map(([k, v]) => [k, v === null ? '' : String(v)])),
)
const P = (v: string) => (v === '' ? 'PENDIENTE DE CONFIGURACIÓN' : `${v.replace('.', ',')} %`)
const tfRes = computed(
  () =>
    `Arriendo: el arrendatario paga una sola vez el ${P(tf.arriendo_pct ?? '')} del canon + IVA (${P(tf.iva_pct ?? '')}) y la papelería de ${fmtCOP(Number(tf.papeleria || 0))} con IVA incluido. ` +
    `Venta: ${P(tf.venta_pct ?? '')} del valor + IVA por defecto. Referidos: ${P(tf.referidos_pct ?? '')} del canon. Retención en la fuente: ${P(tf.retencion_pct ?? '')} ` +
    '(la aplica el arrendatario persona jurídica al propietario; no cambia la ganancia de la empresa). Cada cambio queda en el registro de cambios.',
)
const guardarTarifas = () =>
  run(
    'tf',
    () => api.seccion('tarifas', { ...tf, retencion_pct: tf.retencion_pct === '' ? null : tf.retencion_pct }),
    '✓ Tarifas guardadas.',
  )

// ---------------------------------------------------------------- Automatizaciones, idioma, leads
const au = reactive({ ...(D.value?.automatizaciones ?? { lead_sin_responsable_min: 15, resumen_diario: '07:30', escalar_urgentes: true }) })
const guardarAuto = () => run('au', () => api.seccion('automatizaciones', { ...au }), '✓ Guardado. El inicio de Coordinación ya usa los minutos nuevos.')
const AUTOS = computed(() => [
  ['Lead sin atender', `Alerta en el inicio de Coordinación pasados ${au.lead_sin_responsable_min} minutos sin responsable`, 'ok'],
  ['Puntos de leads ganados y perdidos', 'Suma o descuenta en el rendimiento de Atención y Preventa con las reglas de abajo', 'ok'],
  ['Resumen diario de avisos', `Cada día a las ${au.resumen_diario}`, 'pend'],
  ['Escalar avisos urgentes', au.escalar_urgentes ? 'Al jefe directo, una sola vez' : 'No se escala', 'pend'],
  ['Entrada de leads desde portales', 'Crear el lead con su fuente; si ya existe, sumarlo al cliente', 'pend'],
])
const lang = ref(D.value?.idioma?.idioma ?? 'es')
const PREV: Record<string, string[]> = {
  es: ['Inicio', 'Notificaciones', 'Mis resultados', 'Configuración', 'Mi perfil'],
  en: ['Home', 'Notifications', 'My results', 'Settings', 'My profile'],
  it: ['Home', 'Notifiche', 'I miei risultati', 'Impostazioni', 'Il mio profilo'],
}
const aplicarIdioma = () => run('lang', () => api.seccion('idioma', { idioma: lang.value }), 'Idioma aplicado a toda la herramienta.')
const gl = reactive({ ...(D.value?.leads ?? { puntos_ganado: 1, puntos_perdido: 0.5, llamadas_minimas: 3, dias_seguidos: 3 }) })
const pts = (n: number) => `${String(n).replace('.', ',')} punto${n === 1 ? '' : 's'}`
const guardarLeads = () => run('gl', () => api.seccion('leads', { ...gl }), '✓ Reglas guardadas. Aplican al rendimiento del mes y a los próximos leads perdidos.')

// ---------------------------------------------------------------- history and cards
const valor = (v: unknown) => (v === null || v === undefined ? '—' : typeof v === 'boolean' ? (v ? 'sí' : 'no') : String(v))
const cambioTxt = (e: ConfigPagina['cambios'][number]) =>
  e.detalle ??
  Object.keys(e.despues)
    .map((k) => `${k.replace(/_/g, ' ')}: ${valor(e.antes[k])} → ${valor(e.despues[k])}`)
    .join(' · ')

type Card = { t: string; d: string; to: string; pend?: string }
const GRUPOS = computed<{ t: string; items: Card[] }[]>(() =>
  ger.value
    ? [
        {
          t: 'Personas y accesos',
          items: [
            { t: 'Usuarios, cargos y actividades', d: 'Crear, editar o desactivar usuarios; Captación, Ventas y Arriendos por persona.', to: '/usuarios' },
            { t: 'Ausencias y permisos', d: 'Incapacidades y permisos; descuentan en «Salarios del mes».', to: '/novedades' },
          ],
        },
        {
          t: 'Rendimiento y dinero',
          items: [
            { t: 'Indicadores, metas y pesos', d: 'Todas las áreas, incluida Atención y Preventa.', to: '/rendimiento', pend: 'Metas reales: pendiente' },
            { t: 'Comisiones, bonos y pagos', d: 'Porcentajes, reparto, bono por rendimiento y el día de pago.', to: '/compensacion', pend: 'Porcentajes de cada parte en ventas: pendiente' },
            { t: 'Salarios', d: 'Dos cortes. La Auxiliar confirma y Gerencia aprueba y paga.', to: '/salarios', pend: 'Deducciones de ley e incapacidades: pendiente' },
          ],
        },
        {
          t: 'Operación',
          items: [
            { t: 'Rutas, GPS y tiempo detenido', d: 'Tiempo detenido (15, 20, 30 minutos u otro) y plazo para justificar.', to: '/movimientos', pend: 'Validación legal del GPS: pendiente' },
            { t: 'Plataformas tradicionales', d: 'Responsable, planes y cada cuántos días se actualizan.', to: '/plataformas' },
            { t: 'Integraciones', d: 'Resultados de cada plataforma y los datos para conectarla.', to: '/integraciones', pend: 'Conectores reales: pendientes' },
            { t: 'Pólizas y aseguradoras', d: 'Aseguradoras, tipos de póliza y días para activar cada póliza.', to: '/polizas?tab=ase', pend: 'Aseguradoras y precios reales: pendientes' },
            { t: 'Registro de cambios', d: 'Quién hizo qué, cuándo, y cómo estaba antes y después, en todos los módulos.', to: '/trazabilidad' },
          ],
        },
      ]
    : [
        {
          t: 'Equipo',
          items: [
            { t: 'Usuarios y actividades', d: 'Agregar, editar o desactivar personas; activar o quitar Captación, Ventas y Arriendos. El GPS sigue a Captación.', to: '/usuarios' },
            { t: 'Ausencias y permisos', d: 'Registrar incapacidades y permisos; revisar novedades del preoperacional.', to: '/novedades' },
          ],
        },
        {
          t: 'Rendimiento y operación',
          items: [
            { t: 'Pesos y calificaciones', d: 'Peso de cada área de los asesores (suma 100 %), calificaciones de 1 a 5.', to: '/rendimiento', pend: 'Metas reales: pendiente' },
            { t: 'Rutas, GPS y tiempo detenido', d: 'Tiempo detenido (15, 20, 30 minutos u otro).', to: '/movimientos', pend: 'Retención de la ubicación: pendiente' },
            { t: 'Actualización de plataformas', d: 'Cupo, destacados y actualizaciones de cada portal.', to: '/plataformas' },
            { t: 'Registro de cambios', d: 'Los cambios de la operación de tu equipo, con antes y después.', to: '/trazabilidad' },
          ],
        },
      ],
)
</script>

<template>
  <PageBar title="Configuración" subtitle="Todo lo que puedes ajustar, en un solo lugar · cada cambio queda en el registro de cambios" back="/coordinacion" />

  <div v-if="D" class="cnt">
    <div class="note">
      {{
        ger
          ? 'Gerencia configura todo el sistema. Toca una tarjeta para ir directo al ajuste. Lo marcado en morado aún está por definir.'
          : 'Coordinación configura lo de su equipo. Lo que es de toda la empresa (permisos, costos, comisiones, integraciones) lo configura Gerencia.'
      }}
    </div>

    <!-- =================== Marca =================== -->
    <div v-if="ger" class="card col focus">
      <div class="sb"><span class="lbl">Marca de la empresa · logo, nombre y colores verdes</span><span class="chip gray">Solo Gerencia</span></div>
      <div class="g2b">
        <div class="col">
          <div class="fld">
            <span class="fld-label">Logo <span class="req">*</span></span>
            <div class="row fw g8">
              <button type="button" class="btn bs" @click="fileIn?.click()">{{ mk.logo ? '✓ Logo propio · cambiar' : 'Subir logo nuevo' }}</button>
              <button type="button" class="btn bs" :disabled="!mk.logo" @click="mk.logo = null">Usar el logo de Casa Dolce Casa</button>
              <input ref="fileIn" type="file" accept="image/png,image/svg+xml" class="sr-only" aria-label="Archivo del logo" @change="subirLogo">
            </div>
            <span class="mut tiny">PNG o SVG, fondo transparente, menos de 150 KB. Se ve en el inicio de sesión, en el menú y en el celular.</span>
          </div>
          <div class="fld"><label for="mk1">Nombre de la empresa <span class="req">*</span></label><input id="mk1" v-model="mk.nombre" class="in" maxlength="40"></div>
          <div class="fld"><label for="mk2">Frase debajo del nombre</label><input id="mk2" v-model="mk.lema" class="in" maxlength="80"></div>
          <div class="lbl mt4">Colores verdes de la aplicación</div>
          <div v-for="[k, t, d] in VERDES" :key="k" class="sb verde">
            <span class="small"><b>{{ t }}</b><br><span class="mut tiny">{{ d }}</span></span>
            <span class="row g8">
              <input v-model="mk[k]" type="color" class="cpick" :aria-label="t">
              <span class="num mut tiny hex">{{ String(mk[k]).toUpperCase() }}</span>
            </span>
          </div>
          <div class="mut tiny">
            Solo se cambian los verdes. Los colores del semáforo y de los avisos (verde, amarillo, naranja y rojo de los resultados) no cambian, para que siempre
            signifiquen lo mismo.
          </div>
          <div v-if="msg.marca" class="note" :class="msg.marca.ok ? 'ok' : 'bad'"><b>{{ msg.marca.t }}</b></div>
          <div class="row fw g8">
            <button type="button" class="btn bp" @click="guardarMarca">Guardar y aplicar a toda la herramienta</button>
            <button type="button" class="btn bs" @click="restaurar">Volver a los de Casa Dolce Casa</button>
          </div>
        </div>
        <div class="col g8">
          <div class="lbl">Así se verá</div>
          <div class="pv">
            <div class="pv-side" :style="pvSide">
              <BrandLogo :size="38" :preview="mk" />
              <div>
                <div class="pv-wm">{{ mk.nombre || 'NOMBRE' }}</div>
                <div class="pv-lema" :style="{ color: mk.color_claro }">{{ mk.lema }}</div>
              </div>
            </div>
            <div class="pv-body">
              <div class="row fw g8">
                <span class="btn" :style="{ background: mk.color_principal, color: '#fff' }">Botón principal</span>
                <span class="btn" :style="{ background: '#fff', color: mk.color_principal, border: `1.5px solid ${mk.color_principal}` }">Botón secundario</span>
              </div>
              <div class="row fw g8">
                <span class="chip ok">● Verde 84 %</span><span class="chip warn">▲ Amarillo 72 %</span><span class="chip nar">▲ Naranja 61 %</span><span class="chip bad">■ Rojo 48 %</span>
              </div>
              <span class="mut tiny">El semáforo no cambia.</span>
            </div>
          </div>
        </div>
      </div>
      <div class="mut tiny">El cambio aplica en el navegador y en el celular para todos los usuarios, y queda en el registro de cambios (quién, cuándo, antes y después).</div>
    </div>

    <!-- =================== Pendientes para salir a producción =================== -->
    <div v-if="ger" class="card col red">
      <div class="sb">
        <span class="lbl">Pendientes para salir a producción</span>
        <span class="chip" :class="nPend ? 'bad' : 'ok'">{{ nPend ? `${nPend} por definir` : '✓ Todo definido' }}</span>
      </div>
      <div class="mut small">Sin estos datos el sistema no puede calcular, descontar ni pagar. Mientras quede alguno, no se puede activar el uso real.</div>
      <div v-for="p in D.pendientes" :key="p.clave" class="pend-row">
        <span>
          <b>{{ p.titulo }}</b><br>
          <span class="mut tiny">{{ p.detalle }}</span>
          <NuxtLink v-if="p.link && !p.resuelto" :to="p.link" class="tiny"> · Ir al ajuste ›</NuxtLink>
        </span>
        <label v-if="p.manual" class="row gp6 tiny chk">
          <input type="checkbox" :checked="p.resuelto" @change="marcar(p.clave, ($event.target as HTMLInputElement).checked)">
          Definido
        </label>
        <span v-else class="mut tiny">Se marca solo</span>
        <span class="chip jend" :class="p.resuelto ? 'ok' : 'pend'">{{ p.resuelto ? '✓ Definido' : p.quien }}</span>
      </div>
      <div v-if="msg.pend" class="note" :class="msg.pend.ok ? 'ok' : 'bad'"><b>{{ msg.pend.t }}</b></div>
      <div class="row fw g10">
        <span v-if="D.produccion?.uso_real" class="chip ok">✓ Uso real activado por {{ D.produccion.uso_real_por }}</span>
        <template v-else>
          <button type="button" class="btn bp" :disabled="nPend > 0" @click="usoReal">Activar uso real</button>
          <span class="mut tiny">Se habilita cuando no quede ningún pendiente. Los que se definen en otra pantalla se marcan solos al guardarlos allí.</span>
        </template>
      </div>
    </div>

    <!-- =================== Fechas de pago =================== -->
    <div class="card col" :class="{ focus: ger }">
      <div class="sb"><span class="lbl">Fechas de pago al personal</span><span class="mut tiny">{{ ger ? 'Solo Gerencia la cambia' : 'La define Gerencia · solo lectura' }}</span></div>
      <div class="gauto">
        <div class="fld">
          <label for="fp1">Salario · primer corte (día del mes)</label>
          <select id="fp1" v-model.number="fp.dia_corte_1" class="in" :disabled="!ger"><option v-for="d in dias(28)" :key="d" :value="d">Día {{ d }}</option></select>
        </div>
        <div class="fld">
          <label for="fp2">Salario · segundo corte (día del mes)</label>
          <select id="fp2" v-model.number="fp.dia_corte_2" class="in" :disabled="!ger"><option v-for="d in dias(31)" :key="d" :value="d">Día {{ d }}{{ d >= 30 ? ' (o el último día del mes)' : '' }}</option></select>
        </div>
        <div class="fld">
          <label for="fp3">Comisiones y bonos (día del mes siguiente)</label>
          <select id="fp3" v-model.number="fp.dia_pago" class="in" :disabled="!ger"><option v-for="d in dias(28)" :key="d" :value="d">Día {{ d }}</option></select>
        </div>
      </div>
      <div class="note">
        {{ fpRes }} Si el día cae en fin de semana o festivo, se paga el día hábil anterior (regla PENDIENTE DE CONFIGURACIÓN). Estas fechas las usan «Salarios del mes»,
        «Comisiones, bonos y pagos» y «Mis pagos». Cada cambio queda en el registro de cambios.
      </div>
      <div v-if="msg.fp" class="note" :class="msg.fp.ok ? 'ok' : 'bad'"><b>{{ msg.fp.t }}</b></div>
      <div v-if="ger"><button type="button" class="btn bp" @click="guardarPagos">Guardar fechas de pago</button></div>
    </div>

    <template v-if="ger">
      <!-- =================== Tarifas =================== -->
      <div class="card col focus">
        <div class="sb"><span class="lbl">Tarifas de intermediación (lo que cobra la empresa)</span><span class="mut tiny">Solo Gerencia las cambia</span></div>
        <div class="gauto">
          <div class="fld"><label for="tf1">Arriendo · comisión (% del canon, una sola vez, + IVA)</label><input id="tf1" v-model="tf.arriendo_pct" class="in" type="number" step="0.5" min="0"></div>
          <div class="fld"><label for="tf2">Arriendo · papelería ($, IVA incluido, una sola vez)</label><input id="tf2" v-model="tf.papeleria" class="in" type="number" step="1000" min="0"></div>
          <div class="fld"><label for="tf3">IVA (%)</label><input id="tf3" v-model="tf.iva_pct" class="in" type="number" step="1" min="0"></div>
          <div class="fld"><label for="tf4">Venta · comisión por defecto (% del valor, + IVA)</label><input id="tf4" v-model="tf.venta_pct" class="in" type="number" step="0.5" min="0"></div>
          <div class="fld"><label for="tf5">Pago a referidos (% del canon)</label><input id="tf5" v-model="tf.referidos_pct" class="in" type="number" step="0.5" min="0"></div>
          <div class="fld"><label for="tf6">Retención en la fuente al propietario (%)</label><input id="tf6" v-model="tf.retencion_pct" class="in" type="number" step="0.5" min="0" placeholder="PENDIENTE DE CONFIGURACIÓN"></div>
        </div>
        <div class="note">{{ tfRes }}</div>
        <div v-if="msg.tf" class="note" :class="msg.tf.ok ? 'ok' : 'bad'"><b>{{ msg.tf.t }}</b></div>
        <div><button type="button" class="btn bp" @click="guardarTarifas">Guardar tarifas</button></div>
      </div>

      <!-- =================== Automatizaciones =================== -->
      <div class="card col">
        <div class="sb"><span class="lbl">Automatizaciones y avisos</span><span class="mut tiny">Solo Gerencia</span></div>
        <div class="gauto">
          <div class="fld">
            <label for="au1">Avisar de un lead sin responsable después de</label>
            <select id="au1" v-model.number="au.lead_sin_responsable_min" class="in"><option v-for="m in D.opciones.lead_sin_responsable_min" :key="m" :value="m">{{ m }} minutos</option></select>
          </div>
          <div class="fld">
            <label for="au2">Resumen diario de avisos informativos</label>
            <select id="au2" v-model="au.resumen_diario" class="in"><option v-for="h in D.opciones.resumen_diario" :key="h" :value="h">{{ fmtHora(`2026-01-01T${h}:00-05:00`) }} a. m.</option></select>
          </div>
          <div class="fld">
            <label for="au3">Si un aviso urgente no se atiende a tiempo</label>
            <select id="au3" v-model="au.escalar_urgentes" class="in"><option :value="true">Se escala al jefe directo una sola vez</option><option :value="false">No se escala</option></select>
          </div>
        </div>
        <div class="wrap">
          <div class="min700">
            <div class="ga hd"><span>Automatización</span><span>Qué hace</span><span>Estado</span></div>
            <div v-for="[n, d, e] in AUTOS" :key="n" class="ga">
              <b>{{ n }}</b><span class="mut tiny">{{ d }}</span>
              <span><span class="chip" :class="e === 'ok' ? 'ok' : 'pend'">{{ e === 'ok' ? 'Funcionando' : 'Pendiente: módulo de avisos' }}</span></span>
            </div>
          </div>
        </div>
        <div v-if="msg.au" class="note" :class="msg.au.ok ? 'ok' : 'bad'"><b>{{ msg.au.t }}</b></div>
        <div class="row fw g10">
          <button type="button" class="btn bp" @click="guardarAuto">Guardar</button>
          <span class="mut tiny">Ninguna automatización mueve dinero ni aprueba pagos, y cada cambio queda en el registro de cambios.</span>
        </div>
      </div>

      <!-- =================== Idioma =================== -->
      <div class="card col focus">
        <div class="sb"><span class="lbl">Idioma de la herramienta · Language · Lingua</span><span class="mut tiny">Solo Gerencia</span></div>
        <div class="row fw">
          <button
            v-for="(t, k) in D.idiomas"
            :key="k"
            type="button"
            class="opt"
            :class="{ on: lang === k }"
            :disabled="!D.idiomas_disponibles.includes(String(k))"
            @click="lang = String(k)"
          >
            {{ t }}{{ D.idiomas_disponibles.includes(String(k)) ? '' : ' · traducción pendiente' }}
          </button>
        </div>
        <div class="row fw g8"><span class="mut tiny">Vista previa del menú:</span><span v-for="v in PREV[lang]" :key="v" class="chip gray">{{ v }}</span></div>
        <div class="row fw g10">
          <button type="button" class="btn" :class="lang === D.idioma?.idioma ? 'bs' : 'bp'" :disabled="lang === D.idioma?.idioma" @click="aplicarIdioma">
            {{ lang === D.idioma?.idioma ? 'Idioma en uso' : 'Aplicar a toda la herramienta' }}
          </button>
          <span class="mut small">En uso: {{ D.idiomas[D.idioma?.idioma ?? 'es'] }}</span>
        </div>
        <div v-if="msg.lang" class="note" :class="msg.lang.ok ? 'ok' : 'bad'"><b>{{ msg.lang.t }}</b></div>
        <div class="note">
          Cambia los menús, botones, títulos, avisos y reportes de todos los usuarios. Lo que escriben las personas no se traduce. Los usuarios no pueden cambiar el
          idioma: lo define solo Gerencia. Inglés e italiano se habilitan cuando esté hecha la traducción.
        </div>
      </div>

      <!-- =================== Leads ganados y perdidos =================== -->
      <div class="card col">
        <div class="sb"><span class="lbl">Leads ganados y perdidos · puntos de rendimiento</span><span class="mut tiny">Solo Gerencia · aplica a Atención y Preventa</span></div>
        <div class="gauto end">
          <div class="fld">
            <label for="gpg">Suma por lead ganado</label>
            <select id="gpg" v-model.number="gl.puntos_ganado" class="in"><option v-for="n in D.opciones.puntos_ganado" :key="n" :value="n">+{{ pts(Number(n)) }}</option></select>
          </div>
          <div class="fld">
            <label for="gpp">Descuenta por lead perdido</label>
            <select id="gpp" v-model.number="gl.puntos_perdido" class="in"><option v-for="n in D.opciones.puntos_perdido" :key="n" :value="n">−{{ pts(Number(n)) }}</option></select>
          </div>
          <div class="fld">
            <label for="gpl">Llamadas mínimas sin contacto</label>
            <select id="gpl" v-model.number="gl.llamadas_minimas" class="in"><option v-for="n in D.opciones.llamadas_minimas" :key="n" :value="n">{{ n }}</option></select>
          </div>
          <div class="fld">
            <label for="gpd">En días seguidos</label>
            <select id="gpd" v-model.number="gl.dias_seguidos" class="in"><option v-for="n in D.opciones.dias_seguidos" :key="n" :value="n">{{ n }}</option></select>
          </div>
        </div>
        <div v-if="msg.gl" class="note" :class="msg.gl.ok ? 'ok' : 'bad'"><b>{{ msg.gl.t }}</b></div>
        <div class="row fw g10">
          <span class="chip ok">Número equivocado: nunca descuenta</span>
          <span class="chip ok">Sin contacto después de las llamadas mínimas: no descuenta</span>
          <button type="button" class="btn bp" @click="guardarLeads">Guardar reglas</button>
        </div>
        <div class="note">
          Se elige de las listas, no se escribe. El perdido siempre descuenta menos de lo que suma un ganado. Los puntos se recalculan para el mes en curso; las llamadas
          mínimas aplican a los leads que se marquen como perdidos desde ahora. Cada cambio queda en el registro de cambios.
        </div>
      </div>

      <!-- =================== Registro de cambios =================== -->
      <div class="card">
        <div class="lbl mb8">Registro de cambios de la configuración</div>
        <div v-for="e in D.cambios" :key="e.id" class="ev">
          <span class="num mut tiny">{{ fmtCuando(e.created_at) }}</span>
          <span class="small"><b>{{ e.seccion_txt }}</b> · {{ e.actor_name ?? '—' }}<br><span class="mut tiny">{{ cambioTxt(e) }}</span></span>
        </div>
        <div v-if="!D.cambios.length" class="mut small">Todavía no hay cambios: todo está con los valores de ejemplo.</div>
      </div>
    </template>

    <!-- =================== Cards =================== -->
    <div v-for="g in GRUPOS" :key="g.t" class="col">
      <div class="lbl">{{ g.t }}</div>
      <div class="g3">
        <NuxtLink v-for="i in g.items" :key="i.t" :to="i.to" class="card link">
          <div class="sb"><b class="t15">{{ i.t }}</b><span class="go">›</span></div>
          <div class="mut small">{{ i.d }}</div>
          <span v-if="i.pend" class="chip pend wrapchip">{{ i.pend }}</span>
        </NuxtLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.col {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.red {
  border: 2px solid #a3271b;
}
.fw {
  flex-wrap: wrap;
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
.mt4 {
  margin-top: 4px;
}
.mb8 {
  margin-bottom: 8px;
}
.tiny {
  font-size: 12px;
}
.small {
  font-size: 13px;
}
.t15 {
  font-size: 15px;
}
.verde {
  padding: 6px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.cpick {
  width: 52px;
  height: 36px;
  border: 1.5px solid var(--cdc-input-border);
  border-radius: 8px;
  padding: 2px;
  background: #fff;
  cursor: pointer;
}
.hex {
  width: 64px;
}
.pv {
  border: 1px solid var(--cdc-border);
  border-radius: 14px;
  overflow: hidden;
}
.pv-side {
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.pv-wm {
  font-family: var(--font-display);
  font-size: 22px;
  letter-spacing: 0.04em;
  line-height: 1;
  color: #fff;
}
.pv-lema {
  font-size: 9.5px;
  font-weight: 600;
}
.pv-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--cdc-bg);
}
.chip.nar {
  background: #fde8d4;
  color: #8a4a12;
}
.jend {
  justify-self: end;
}
.pend-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 100px 150px;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  font-size: 13px;
  align-items: center;
}
.end {
  justify-content: flex-end;
}
.chk {
  cursor: pointer;
}
.chk input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--cdc-green);
}
.gauto {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.gauto.end {
  align-items: end;
}
.wrap {
  overflow-x: auto;
}
.min700 {
  min-width: 700px;
}
.ga {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1.6fr) 220px;
  gap: 10px;
  padding: 8px 6px;
  border-bottom: 1px solid var(--cdc-border-soft);
  font-size: 13px;
  align-items: center;
}
.hd {
  font-size: 10.5px;
  color: var(--cdc-muted);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom-color: var(--cdc-border);
}
.ev {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
}
.link {
  text-decoration: none;
  color: var(--cdc-text);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.go {
  font-weight: 800;
  color: var(--cdc-green);
}
.wrapchip {
  align-self: flex-start;
  white-space: normal;
}
</style>
