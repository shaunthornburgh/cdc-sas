<script setup lang="ts">
import type { NuxtError } from '#app'

const props = defineProps<{ error: NuxtError }>()

const title = computed(() => {
  if (props.error.statusCode === 403) return 'Sin acceso'
  if (props.error.statusCode === 404) return 'Página no encontrada'
  return 'Algo salió mal'
})
const message = computed(() =>
  props.error.statusCode === 403
    ? props.error.message
    : 'Intenta de nuevo o vuelve al inicio.',
)
</script>

<template>
  <NuxtLayout name="auth">
    <div class="hero"><BrandLogo :size="56" /></div>
    <div class="card box">
      <span class="chip" :class="error.statusCode === 403 ? 'warn' : 'bad'">Error {{ error.statusCode }}</span>
      <h1 class="ttl">{{ title }}</h1>
      <p class="mut">{{ message }}</p>
      <button type="button" class="btn bp" @click="clearError({ redirect: '/' })">Volver al inicio</button>
    </div>
  </NuxtLayout>
</template>

<style scoped>
.hero {
  display: flex;
  justify-content: center;
  padding-top: 40px;
}
.box {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
}
.box p {
  margin: 0 0 6px;
}
</style>
