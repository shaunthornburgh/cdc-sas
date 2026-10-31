<script setup lang="ts">
/** White top bar: optional back link, Bebas title + subtitle on the left, actions slot on the right. */
defineProps<{ title: string; subtitle?: string; back?: string }>()
</script>

<template>
  <div class="bar">
    <div class="row bar-title">
      <NuxtLink v-if="back" class="back" :to="back" aria-label="Volver">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </NuxtLink>
      <div>
        <h1 class="ttl">{{ title }}</h1>
        <div v-if="subtitle" class="mut bar-sub">{{ subtitle }}</div>
      </div>
    </div>
    <div v-if="$slots.default" class="row bar-actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 28px;
  background: #fff;
  border-bottom: 1px solid var(--cdc-border);
}
.bar-title {
  gap: 12px;
  min-width: 0;
}
.bar-sub {
  font-size: 13px;
  margin-top: 2px;
}
.bar-actions {
  flex-wrap: wrap;
}
@media (max-width: 760px) {
  .bar {
    padding: 12px 14px;
  }
}
</style>
