<script setup lang="ts">
/** «Semáforo» card (K07 / M08). */
defineProps<{ compact?: boolean }>()
const ROWS = [
  ['verde', 'Verde', 'de 80% a 100%'],
  ['amarillo', 'Amarillo', 'de 70% a 79%'],
  ['naranja', 'Naranja', 'de 60% a 69%'],
  ['rojo', 'Rojo', 'menos de 60%'],
] as const
</script>

<template>
  <div class="card stack">
    <div class="lbl">Semáforo</div>
    <div v-for="[k, t, d] in ROWS" :key="k" class="row g8">
      <span class="semd" :style="{ background: SEM[k].color }" />
      <span class="small"><b>{{ t }}</b>: {{ d }}</span>
    </div>
    <div v-if="!compact" class="mut tiny">Un punto equivale a 1 % del resultado del mes.</div>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
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
