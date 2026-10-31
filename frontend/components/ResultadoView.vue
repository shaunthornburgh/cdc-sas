<script setup lang="ts">
import type { Resultado } from '~/types/rendimiento'

/**
 * One person's month (prototypes M08 asesor · C04 Atención · K14 Coordinador).
 * Read-only for the person; Coordinación (asesores, Atención) or the Auxiliar / Gerencia
 * (Coordinador) can rate the 1–5 indicators here.
 */
const props = defineProps<{ r: Resultado; yo?: boolean }>()
const emit = defineEmits<{ saved: [r: Resultado] }>()

const tu = computed(() => (props.yo ? 'Tus' : 'Sus'))
const sem = computed(() => (props.r.semaforo ? SEM[props.r.semaforo] : null))
const formula = computed(() => {
  const r = props.r
  if (r.por_areas == null) return 'Todavía no hay áreas con datos este mes.'
  const ganados = r.ajustes.find((a) => a.titulo.startsWith('Ganados'))
  const perd = r.ajustes.find((a) => a.titulo.startsWith('Perdidos con'))
  let t = `Resultado por áreas ${dec(r.por_areas)}%`
  if (ganados) t += ` + ganados ${dec(ganados.puntos)}`
  if (perd) t += ` − perdidos ${dec(-perd.puntos)}`
  t += ` − descuentos ${dec(r.puntos_descuento)} punto${r.puntos_descuento === 1 ? '' : 's'}`
  const ex = r.total_exacto ?? 0
  t += ` = ${dec(ex)}%`
  if (r.total !== null && r.total !== ex) t += ` ≈ ${r.total}%`
  return t
})
const tendencia = (now: number, before: number | null) => {
  if (before == null) return ''
  if (now > before) return `▲ ${props.yo ? 'mejoraste' : 'mejoró'} ${now - before} puntos vs el mes anterior (${before} %)`
  if (now < before) return `▼ ${props.yo ? 'bajaste' : 'bajó'} ${before - now} puntos vs el mes anterior (${before} %)`
  return `= igual que el mes anterior (${before} %)`
}
const pctColor = (v: number | null) => (v == null ? 'var(--cdc-muted)' : SEM[semDe(v)!].color)

</script>

<template>
  <div class="g2b">
    <div class="card score">
      <ScoreRing :value="r.total" />
      <div class="stack">
        <div class="row fw g8">
          <span class="lbl">{{ yo ? 'Mi puntaje del mes' : 'Puntaje del mes' }}</span>
          <span v-if="sem" class="chip" :class="sem.cls">{{ sem.sym }} {{ sem.t }}</span>
        </div>
        <div class="mut small">{{ formula }}</div>
        <div v-if="r.peso_con_datos && r.peso_con_datos < 100" class="mut tiny">
          Calculado sobre el {{ r.peso_con_datos }} % del peso: las áreas sin datos todavía no cuentan.
        </div>
        <div v-if="r.anterior != null && r.total != null" class="mut tiny">{{ tendencia(r.total, r.anterior) }}</div>
      </div>
    </div>
    <SemaforoLegend class="desk-only" />
  </div>

  <!-- Puntos de mejora -->
  <div class="card stack">
    <div class="sb">
      <div>
        <div class="lbl">{{ tu }} puntos de mejora · {{ r.periodo.label.split(' ')[0] }}</div>
        <div class="mut small">
          {{
            r.mejoras.todo_verde
              ? r.mejoras.items.length
                ? `Todos ${tu.toLowerCase()} indicadores están en verde. Esto es lo que falta para llegar al 100 %:`
                : `Todos ${tu.toLowerCase()} indicadores están al 100 %.`
              : `${tu} indicadores más bajos frente a la meta, de menor a mayor, con lo que falta y qué hacer`
          }}
        </div>
      </div>
      <span class="chip" :class="r.mejoras.todo_verde ? 'ok' : 'warn'">
        {{ r.mejoras.todo_verde ? (yo ? '● Vas bien' : '● Va bien') : `${r.mejoras.items.length} indicador${r.mejoras.items.length === 1 ? '' : 'es'} por mejorar` }}
      </span>
    </div>
    <div v-for="(m, i) in r.mejoras.items" :key="m.key" class="it">
      <div class="sb"><b>{{ i + 1 }}. {{ m.titulo }}</b><b :style="{ color: pctColor(m.cumplimiento) }">{{ m.cumplimiento }} %</b></div>
      <div class="small">{{ m.falta }}</div>
      <div v-if="m.que_hacer" class="small"><b>Qué hacer:</b> {{ m.que_hacer }}</div>
      <div class="sb mut tiny">
        <span>{{ [tendencia(m.cumplimiento, m.anterior), `pesa ${m.peso} %`].filter(Boolean).join(' · ') }}</span>
        <NuxtLink v-if="yo && m.link" :to="m.link">Ir ›</NuxtLink>
      </div>
    </div>
    <template v-if="r.mejoras.calificaciones.length">
      <div class="lbl">Calificaciones por mejorar (de 1 a 5)</div>
      <div v-for="c in r.mejoras.calificaciones" :key="c.titulo" class="small">
        <b>{{ c.titulo }}</b> · {{ c.valor }} de 5 · {{ c.quien.replace('Asignado por ', '') }}
        <div v-if="c.que_hacer" class="mut">Qué hacer: {{ c.que_hacer }}</div>
      </div>
    </template>
    <div v-if="r.mejoras.bien.length" class="small ok-txt">
      <b>{{ yo ? 'Lo que haces bien:' : 'Lo que hace bien:' }}</b>
      {{ r.mejoras.bien.map((b) => `${b.titulo} (${b.cumplimiento} %)`).join(' · ') }}
    </div>
    <div class="mut tiny">Se calcula solo con lo que se registra cada día y se compara con el mes anterior.</div>
  </div>

  <!-- Áreas -->
  <div class="card stack">
    <div class="sb">
      <span class="lbl">Indicadores, metas y cumplimiento</span>
      <span class="mut tiny">Peso</span>
    </div>
    <div v-if="r.perfil === 'atencion'" class="wrap">
      <table class="tbl t-areas">
        <thead><tr><th>Indicador</th><th>Meta</th><th>Logrado</th><th>Cumplimiento</th><th>Peso</th><th>Aporta</th></tr></thead>
        <tbody>
          <tr v-for="a in r.areas" :key="a.key">
            <td><b>{{ a.titulo }}</b></td>
            <td>{{ a.meta_txt || '—' }}</td>
            <td>{{ a.logrado_txt || '—' }}</td>
            <td>
              <span v-if="a.cumplimiento != null" class="row g8">
                <span class="semd" :style="{ background: SEM[a.semaforo!].color }" />
                <b>{{ a.cumplimiento }}%</b>
              </span>
              <span v-else class="mut tiny">{{ a.sin_datos }}</span>
            </td>
            <td><span class="chip gray">{{ a.peso }}%</span></td>
            <td class="num">{{ a.cumplimiento != null ? `${dec(a.aporte)} pts` : '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <template v-else>
      <div v-for="a in r.areas" :key="a.key" class="area">
        <div class="sb">
          <b>{{ a.titulo }}</b>
          <span class="chip gray">pesa {{ a.peso }}%</span>
        </div>
        <div v-if="r.perfil === 'coordinacion'" class="mut tiny">{{ a.descripcion }}</div>
        <template v-if="a.cumplimiento != null">
          <div class="sb small">
            <span>{{ a.meta_txt ? `Meta ${a.meta_txt}` : '' }}</span>
            <span>Logrado <b>{{ a.logrado_txt }}</b></span>
          </div>
          <div class="trk"><div class="fl" :style="{ width: `${a.cumplimiento}%`, background: SEM[a.semaforo!].color }" /></div>
          <div class="sb small">
            <span>Cumplimiento <b>{{ a.cumplimiento }}%</b> · {{ a.semaforo }}</span>
            <span class="mut">aporta {{ dec(a.aporte) }} pts</span>
          </div>
        </template>
        <div v-else class="note">{{ a.sin_datos }}</div>
      </div>
    </template>
    <div class="sb">
      <b>Resultado por áreas</b>
      <b class="num">{{ r.por_areas != null ? `${dec(r.por_areas)}%` : '—' }}</b>
    </div>
    <details class="mut tiny">
      <summary>Qué cuenta en cada área</summary>
      <p v-for="a in r.areas" :key="a.key"><b>{{ a.titulo }}:</b> {{ a.descripcion }}</p>
      <p>Metas de ejemplo; las metas reales: PENDIENTE DE CONFIGURACIÓN.</p>
    </details>
  </div>

  <div class="g2b">
    <CalificacionesCard :r="r" :yo="yo" @saved="(x) => emit('saved', x)" />

    <div class="stack-cards">
      <!-- Descuentos -->
      <div class="card stack">
        <div class="lbl">Descuentos de {{ r.periodo.label.split(' ')[0] }}</div>
        <div v-for="d in r.descuentos" :key="d.titulo" class="sb">
          <div><b class="small">{{ d.titulo }}</b><div class="mut tiny">{{ d.detalle }}</div></div>
          <span class="chip bad">−{{ dec(d.puntos) }}</span>
        </div>
        <div v-for="a in r.avisos" :key="a.titulo" class="sb">
          <div><b class="small">{{ a.titulo }}</b><div class="mut tiny">{{ a.detalle }}</div></div>
          <NuxtLink v-if="yo" class="chip warn" :to="a.link">Hacer ›</NuxtLink>
        </div>
        <div v-if="!r.descuentos.length && !r.avisos.length" class="note ok">Sin descuentos este mes.</div>
        <div class="mut tiny">
          Cada calificación de 2 o 1 descuenta 5 puntos. Las justificaciones de ruta (−1 punto) se suman cuando exista el GPS.
        </div>
      </div>

      <!-- Atención: leads ganados y perdidos -->
      <div v-if="r.perfil === 'atencion'" class="card stack">
        <div class="lbl">Leads ganados y perdidos · {{ r.periodo.label.split(' ')[0] }}</div>
        <div v-for="a in r.ajustes" :key="a.titulo" class="sb">
          <div><b class="small">{{ a.titulo }}</b><div class="mut tiny">{{ a.detalle }}</div></div>
          <span class="chip" :class="a.puntos > 0 ? 'ok' : a.puntos < 0 ? 'bad' : 'gray'">{{ a.puntos > 0 ? '+' : a.puntos < 0 ? '−' : '' }}{{ dec(Math.abs(a.puntos)) }}</span>
        </div>
        <div v-if="!r.ajustes.length" class="note">Sin leads ganados ni perdidos este mes.</div>
        <div class="mut tiny">
          Ganado suma 1 punto cuando se confirma el cierre del negocio. Perdido descuenta 0,5 (valor de ejemplo; lo configura
          Gerencia). No descuenta por número equivocado ni sin contacto tras mínimo 3 llamadas en 3 días seguidos.
        </div>
      </div>
    </div>
  </div>
  <div v-if="yo" class="card stack">
    <div class="lbl">Mi información económica · tres secciones separadas</div>
    <NuxtLink class="sb eco" to="/mis-pagos?tab=comision"><span><b class="small">Mis comisiones</b><span class="mut tiny"> · generadas, pendientes y pagadas</span></span>›</NuxtLink>
    <NuxtLink class="sb eco" to="/mis-pagos?tab=bono"><span><b class="small">Mis bonos</b><span class="mut tiny"> · generados, pendientes y pagados</span></span>›</NuxtLink>
    <NuxtLink class="sb eco" to="/mis-pagos?tab=pagos"><span><b class="small">Pagos</b><span class="mut tiny"> · pagos que te ha hecho la empresa</span></span>›</NuxtLink>
  </div>
  <SemaforoLegend class="mob-only" />
</template>

<style scoped>
.mob-only {
  display: none;
}
@media (max-width: 760px) {
  .desk-only {
    display: none;
  }
  .mob-only {
    display: flex;
  }
}
.score {
  display: flex;
  gap: 18px;
  align-items: center;
  flex-wrap: wrap;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.stack-cards {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.score .stack {
  flex: 1;
  min-width: 200px;
  gap: 6px;
}
.g8 {
  gap: 8px;
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
.ok-txt {
  color: var(--sem-verde);
}
.area {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--cdc-border);
}
.t-areas {
  min-width: 640px;
}
details p {
  margin: 6px 0 0;
}
.eco {
  color: inherit;
  text-decoration: none;
  padding: 8px 0;
  border-bottom: 1px solid var(--cdc-border);
}
</style>
