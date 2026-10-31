<script setup lang="ts">
/** «Mis resultados» (M08 asesor · C04 Atención y Preventa · K14 Coordinador). */
definePageMeta({ module: 'resultados' })
useHead({ title: 'Mis resultados · Casa Dolce Casa' })

const auth = useAuth()
const rend = useRendimiento()
const meses = ultimosMeses()
const periodo = ref(meses[0]!.key)
const { data, error, pending } = await useAsyncData('mis-resultados', () => rend.mio(periodo.value), { watch: [periodo] })
const perfil = computed(() => perfilRendimiento(auth.user.value))
const home = computed(() => (perfil.value === 'asesor' ? '/asesor' : perfil.value === 'atencion' ? '/leads' : '/coordinacion'))
</script>

<template>
  <PageBar
    title="Mis resultados"
    :subtitle="`${auth.user.value?.full_name} · ${data?.periodo.label ?? ''}${perfil === 'asesor' ? '' : ' · mismo sistema de indicadores que los asesores'}`"
    :back="home"
  >
    <select v-model="periodo" class="fsel" aria-label="Mes">
      <option v-for="m in meses" :key="m.key" :value="m.key">{{ m.t }}{{ m.key === meses[0]!.key ? ' (en curso)' : '' }}</option>
    </select>
  </PageBar>
  <div class="cnt narrow">
    <div v-if="error" class="note bad"><b>No se pudieron cargar tus resultados.</b> {{ apiErrorMessage(error) }}</div>
    <div v-else-if="pending && !data" class="note">Cargando…</div>
    <ResultadoView v-else-if="data" :r="data" yo />
    <div v-if="data && perfil === 'coordinacion'" class="note">
      Pesos definidos por Gerencia. «Resultados del equipo» sale solo del promedio de tu equipo: ver
      <NuxtLink to="/equipo">Mi equipo ›</NuxtLink>
    </div>
  </div>
</template>

<style scoped>
.narrow {
  max-width: 1080px;
  width: 100%;
}
</style>
