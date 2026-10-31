<script setup lang="ts">
import type { AsesorCita, CitasBucket } from '~/types/asesor'

/** Mis citas (prototype M03): answer, take, and close citas. */
definePageMeta({ module: 'asesor' })
useHead({ title: 'Mis citas · Casa Dolce Casa' })

const route = useRoute()
const auth = useAuth()
const asesorApi = useAsesor()
const viewing = computed(() => (isManager(auth.user.value) && typeof route.query.asesor === 'string' ? route.query.asesor : null))
if (isManager(auth.user.value) && !viewing.value && !hasCommercialActivity(auth.user.value)) {
  await navigateTo('/coordinacion', { replace: true })
}

const { data, refresh, error } = await useAsyncData(() => `mis-citas-${viewing.value ?? 'me'}`, () => asesorApi.citas(viewing.value))
const TABS: [CitasBucket, string][] = [
  ['responder', 'Por responder'],
  ['proximas', 'Próximas'],
  ['por_cerrar', 'Por cerrar'],
  ['cerradas', 'Cerradas'],
]
const tab = ref<CitasBucket>('responder')
const EMPTY: Record<CitasBucket, string> = {
  responder: 'No tienes citas por responder.',
  proximas: 'No tienes citas aceptadas próximas.',
  por_cerrar: 'No tienes citas por cerrar.',
  cerradas: 'Aún no hay citas cerradas este mes.',
}
const flash = ref<string | null>(null)

// Open the tab that contains a cita linked from the home (#cita-<id>).
onMounted(() => {
  const id = route.hash.replace('#cita-', '')
  if (!id || !data.value) return
  const found = TABS.find(([k]) => data.value![k].some((c) => c.id === id))
  if (found) tab.value = found[0]
  nextTick(() => document.getElementById(`cita-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
})

async function onChanged(_: AsesorCita, msg: string) {
  flash.value = msg
  await refresh()
}
</script>

<template>
  <PageBar title="Mis citas" :subtitle="viewing ? 'Vista de Coordinación (solo lectura)' : 'Acepta, rechaza o toma citas, y ciérralas después de la visita'" :back="viewing ? `/asesor?asesor=${viewing}` : '/asesor'">
    <div class="tabs">
      <button v-for="[k, t] in TABS" :key="k" type="button" class="tab" :class="{ on: tab === k }" @click="tab = k">
        {{ t }} ({{ data?.counts[k] ?? 0 }})
      </button>
    </div>
  </PageBar>
  <div class="cnt narrow">
    <div v-if="error" class="note bad"><b>{{ apiErrorMessage(error) }}</b></div>
    <div class="note">Flujo de cada cita: <b>Pendiente de aceptación → Aceptada → Realizada</b>. La cierras contando qué pasó en la visita.</div>
    <div v-if="flash" class="note ok" role="status"><b>✓ {{ flash }}</b></div>
    <AsesorCitaCard v-for="c in data?.[tab] ?? []" :key="c.id + c.estado" :cita="c" :readonly="!!viewing" @changed="onChanged" />
    <div v-if="data && !data[tab].length" class="note">{{ EMPTY[tab] }}</div>
  </div>
</template>

<style scoped>
.narrow {
  max-width: 760px;
  width: 100%;
}
</style>
