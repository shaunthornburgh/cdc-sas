<script setup lang="ts">
/** M01: «ATENCIÓN: debes realizar el preoperacional» until it's done; then a green chip. */
defineProps<{ activo: boolean; realizadoAt: string | null; novedad?: boolean }>()
</script>

<template>
  <template v-if="activo">
    <NuxtLink v-if="!realizadoAt" to="/preoperacional" class="banner">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /><path d="M12 9v4" /><path d="M12 17h.01" /></svg>
      <div class="grow"><b>ATENCIÓN: debes realizar el preoperacional.</b><div class="tiny">Este aviso no desaparece hasta que lo completes.</div></div>
      <span class="go">›</span>
    </NuxtLink>
    <NuxtLink v-else to="/preoperacional?tab=historial" class="chip ok done">
      ✓ Preoperacional realizado {{ fmtHora(realizadoAt) }}{{ novedad ? ' · con novedad' : '' }}
    </NuxtLink>
  </template>
</template>

<style scoped>
.banner {
  display: flex;
  gap: 10px;
  align-items: center;
  background: var(--cdc-bad-bg);
  border: 1.5px solid var(--cdc-bad);
  border-radius: 14px;
  padding: 14px;
  text-decoration: none;
  color: #7a1d14;
}
.banner:hover {
  color: #7a1d14;
}
.grow {
  flex: 1;
}
.tiny {
  font-size: 12px;
}
.go {
  font-weight: 800;
}
.done {
  align-self: flex-start;
  text-decoration: none;
}
</style>
