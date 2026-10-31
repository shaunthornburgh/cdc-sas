<script setup lang="ts">
/** G12 «Rendimiento de la empresa» (Gerencia): result per area, goals, last month and alerts. */
definePageMeta({ cargos: ['gerencia'] })
useHead({ title: 'Rendimiento de la empresa · Casa Dolce Casa' })

const rend = useRendimiento()
const meses = ultimosMeses()
const periodo = ref(meses[0]!.key)
const { data, error } = await useAsyncData('rend-empresa', () => rend.empresa(periodo.value), { watch: [periodo] })
const sem = (v: number | null) => {
  const s = semDe(v)
  return s ? SEM[s] : null
}
const mesAnt = computed(() => meses[meses.findIndex((m) => m.key === periodo.value) + 1]?.t.split(' ')[0] ?? 'el mes anterior')
</script>

<template>
  <PageBar title="Rendimiento de la empresa" subtitle="Cómo estamos por área · el detalle de cada persona está en «Rendimiento por empleado»" back="/coordinacion">
    <select v-model="periodo" class="fsel" aria-label="Mes">
      <option v-for="m in meses" :key="m.key" :value="m.key">{{ m.t }}</option>
    </select>
    <NuxtLink class="btn bs" to="/equipo">Rendimiento por empleado ›</NuxtLink>
  </PageBar>
  <div class="cnt">
    <div v-if="error" class="note bad"><b>No se pudo cargar.</b> {{ apiErrorMessage(error) }}</div>
    <template v-else-if="data">
      <div class="card score">
        <ScoreRing :value="data.total" :size="130" />
        <div class="stack">
          <div class="row fw g8">
            <span class="lbl">Rendimiento de la empresa · {{ data.periodo.label }}{{ data.periodo.en_curso ? ' (va en curso)' : '' }}</span>
            <span v-if="sem(data.total)" class="chip" :class="sem(data.total)!.cls">{{ sem(data.total)!.sym }} {{ sem(data.total)!.t }}</span>
          </div>
          <div class="small">{{ data.texto }}</div>
          <div v-if="data.anterior != null" class="mut tiny">{{ mesAnt.charAt(0).toUpperCase() + mesAnt.slice(1) }} cerró en {{ data.anterior }} %.</div>
        </div>
      </div>

      <div class="g2b">
        <div v-for="a in data.areas" :key="a.key" class="card stack" :class="{ low: a.total != null && a.total < 60 }">
          <div class="sb">
            <div>
              <b>{{ a.titulo }}</b>
              <div class="mut tiny">{{ a.n ? `${a.n} persona${a.n === 1 ? '' : 's'} · ` : '' }}{{ a.personas }}</div>
            </div>
            <span v-if="sem(a.total)" class="chip" :class="sem(a.total)!.cls">{{ sem(a.total)!.sym }} {{ a.total }}%</span>
            <span v-else class="chip gray">Sin datos</span>
          </div>
          <div class="trk"><div class="fl" :style="{ width: `${a.total ?? 0}%`, background: sem(a.total)?.color ?? 'transparent' }" /></div>
          <div v-for="m in a.metas" :key="m.titulo" class="sb small">
            <span>{{ m.titulo }}</span>
            <span class="row g8">
              <span class="mut">{{ m.logrado }} de {{ m.meta }} (meta)</span>
              <span class="chip" :class="m.pct >= 100 ? 'ok' : sem(m.pct)!.cls">{{ m.pct >= 100 ? '✓ ' : '' }}{{ m.pct }}%</span>
            </span>
          </div>
          <div v-if="a.anterior != null" class="mut tiny">{{ mesAnt.charAt(0).toUpperCase() + mesAnt.slice(1) }} cerró en {{ a.anterior }} %</div>
        </div>
      </div>

      <div class="card stack">
        <div class="lbl">Avisos de rendimiento por área</div>
        <div v-for="v in data.avisos" :key="v.titulo" class="sb it row-it">
          <div><b class="small">{{ v.titulo }}</b><div class="mut tiny">{{ v.detalle }}</div></div>
          <span class="chip" :class="v.nivel === 'ok' ? 'ok' : 'bad'">{{ v.nivel === 'ok' ? 'Al día' : 'Tomar acciones' }}</span>
        </div>
        <div class="mut tiny">
          Gerencia recibe un aviso cuando un área queda por debajo del 60 %. Semáforo: verde 80–100 · amarillo 70–79 ·
          naranja 60–69 · rojo menos de 60.
        </div>
      </div>
      <div class="note">
        El resultado de cada área es el promedio del rendimiento de sus personas; el de la empresa, el promedio de todas. Metas de
        ejemplo; las metas reales: PENDIENTE DE CONFIGURACIÓN. Para ver cómo va cada persona o calificar, entra a «Rendimiento por
        empleado».
      </div>
    </template>
  </div>
</template>

<style scoped>
.score {
  display: flex;
  gap: 18px;
  align-items: center;
  flex-wrap: wrap;
}
.score .stack {
  flex: 1;
  min-width: 220px;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.low {
  border: 2px solid var(--sem-rojo);
}
.fw {
  flex-wrap: wrap;
}
.g8 {
  gap: 8px;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
</style>
