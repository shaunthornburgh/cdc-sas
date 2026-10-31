<script setup lang="ts">
/** Big round score (M08 / C04 / K14 / G12): conic ring coloured by the traffic light. */
const props = withDefaults(defineProps<{ value: number | null; size?: number }>(), { size: 150 })
const sem = computed(() => semDe(props.value))
const style = computed(() => {
  const v = props.value ?? 0
  const c = sem.value ? SEM[sem.value].color : 'var(--cdc-border)'
  return { width: `${props.size}px`, height: `${props.size}px`, background: `conic-gradient(${c} 0 ${v}%, #ecedea ${v}% 100%)` }
})
</script>

<template>
  <div class="ring" :style="style" role="img" :aria-label="value == null ? 'Sin datos' : `${value} %`">
    <div class="in" :style="{ width: `${size - 26}px`, height: `${size - 26}px` }">
      <span class="big num">{{ value == null ? '—' : `${value}%` }}</span>
    </div>
  </div>
</template>

<style scoped>
.ring {
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.in {
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.big {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 46px;
  line-height: 0.9;
}
</style>
