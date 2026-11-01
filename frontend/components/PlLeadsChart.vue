<script setup lang="ts">
import type { PlResultados } from '~/types/plataformas'

/**
 * K15-ger «Leads por mes y portal»: stacked bars, one per month. Colors follow the portal (never
 * its rank), 2px gaps between segments, a total above each bar, a legend and a hover tooltip.
 * The per-portal table above it is the table view.
 */
const props = defineProps<{ r: PlResultados }>()
const H = 150
const series = computed(() => props.r.filas.map((f) => ({ id: f.plataforma_id, nombre: f.nombre, color: f.color })))
const bars = computed(() => {
  const max = Math.max(1, ...props.r.barras.map((b) => b.valores.reduce((s, v) => s + v.leads, 0)))
  return props.r.barras.map((b) => {
    const by = new Map(b.valores.map((v) => [v.plataforma_id, v.leads]))
    const segs = series.value.map((s) => ({ ...s, v: by.get(s.id) ?? 0, h: ((by.get(s.id) ?? 0) / max) * (H - 24) }))
    return { ...b, total: segs.reduce((s, x) => s + x.v, 0), segs: segs.filter((x) => x.v > 0) }
  })
})
const hover = ref<string | null>(null)
</script>

<template>
  <div>
    <div class="bars" :style="{ height: `${H}px` }">
      <div v-for="b in bars" :key="b.mes" class="col" tabindex="0" :aria-label="`${b.label}: ${b.total} leads`" @mouseenter="hover = b.mes" @mouseleave="hover = null" @focus="hover = b.mes" @blur="hover = null">
        <b class="tot num">{{ b.total }}</b>
        <div class="stack">
          <div v-for="(s, i) in [...b.segs].reverse()" :key="s.id" class="seg" :class="{ top: i === 0 }" :style="{ height: `${Math.max(2, s.h)}px`, background: s.color }" />
        </div>
        <div v-if="hover === b.mes" class="tip" role="tooltip">
          <b>{{ b.label }} · {{ b.total }} leads</b>
          <div v-for="s in b.segs" :key="s.id" class="tr"><span class="sw" :style="{ background: s.color }" />{{ s.nombre }}<b class="num ml">{{ s.v }}</b></div>
        </div>
      </div>
    </div>
    <div class="labels"><span v-for="b in bars" :key="b.mes">{{ b.label }}</span></div>
    <div class="legend">
      <span v-for="s in series" :key="s.id" class="row"><span class="sw" :style="{ background: s.color }" />{{ s.nombre }}</span>
    </div>
  </div>
</template>

<style scoped>
.bars {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  border-bottom: 1px solid var(--cdc-border);
}
.col {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  position: relative;
  outline: none;
  cursor: default;
}
.col:focus-visible .stack {
  outline: 2px solid var(--cdc-green);
  outline-offset: 2px;
}
.tot {
  font-size: 12px;
}
.stack {
  width: 100%;
  max-width: 56px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.seg.top {
  border-radius: 4px 4px 0 0;
}
.tip {
  position: absolute;
  bottom: calc(100% + 4px);
  left: 50%;
  transform: translateX(-50%);
  z-index: 5;
  min-width: 170px;
  background: #fff;
  border: 1px solid var(--cdc-border);
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 12px;
  box-shadow: 0 6px 18px rgb(0 0 0 / 0.12);
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.tr {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ml {
  margin-left: auto;
}
.labels {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}
.labels span {
  flex: 1;
  text-align: center;
  font-size: 11px;
  color: var(--cdc-muted);
  font-weight: 700;
}
.legend {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  flex-wrap: wrap;
  font-size: 12px;
}
.legend .row {
  gap: 6px;
}
.sw {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 3px;
  flex: none;
}
</style>
