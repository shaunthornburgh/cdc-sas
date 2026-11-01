<script setup lang="ts">
/** The company logo: the one Gerencia uploaded in Configuración, or the built-in house. */
const props = withDefaults(defineProps<{ size?: number; preview?: { logo: string | null; color_principal: string; color_claro: string } }>(), { size: 38 })
const marca = useMarca()
const m = computed(() => props.preview ?? marca.value)
</script>

<template>
  <img v-if="m.logo" :src="m.logo" :width="size" :height="size" alt="" class="logo-img">
  <svg v-else :width="size" :height="size" viewBox="0 0 40 40" aria-hidden="true">
    <rect width="40" height="40" rx="10" :fill="m.color_principal" />
    <path
      d="M9 21 L20 11 L31 21"
      fill="none"
      stroke="#fff"
      stroke-width="3"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
    <path d="M13.5 19v10.5h13V19" fill="none" :stroke="m.color_claro" stroke-width="3" stroke-linejoin="round" />
  </svg>
</template>

<style scoped>
.logo-img {
  object-fit: contain;
  border-radius: 10px;
  flex: none;
}
</style>
