<script setup lang="ts">
import type { Cita, CitaBucket } from '~/types/leads'

/** Control de citas (prototype C03): no cita stays without someone responsible. */
definePageMeta({ module: 'leads' })
useHead({ title: 'Control de citas · Casa Dolce Casa' })

const leads = useLeads()
const TABS: [CitaBucket, string][] = [
  ['accion', 'Requieren acción'],
  ['pendientes', 'Pendientes de aceptación'],
  ['aceptadas', 'Aceptadas'],
  ['realizadas', 'Realizadas'],
  ['canceladas', 'Canceladas'],
]
const tab = ref<CitaBucket>('accion')
const { data, refresh, pending } = await useAsyncData('citas', () => leads.citas({ bucket: tab.value }), {
  watch: [tab],
})

const EMPTY: Record<CitaBucket, string> = {
  accion: 'Ninguna cita requiere acción: todas tienen un asesor que las aceptó o que aún está a tiempo.',
  pendientes: 'No hay citas pendientes de aceptación.',
  aceptadas: 'No hay citas aceptadas próximas.',
  realizadas: 'Aún no hay citas realizadas.',
  canceladas: 'No hay citas canceladas.',
}

// After an action, keep the card visible until the list is refreshed so the success note shows.
const lastChanged = ref<Cita | null>(null)
async function onChanged(c: Cita) {
  lastChanged.value = c
  await refresh()
}
</script>

<template>
  <PageBar
    title="Control de citas"
    subtitle="Ninguna cita queda sin responsable: aceptadas, rechazadas y sin aceptar a 1 hora"
    back="/leads"
  >
    <div class="tabs">
      <button v-for="[k, t] in TABS" :key="k" type="button" class="tab" :class="{ on: tab === k }" @click="tab = k">
        {{ t }} ({{ data?.counts[k] ?? 0 }})
      </button>
    </div>
  </PageBar>

  <div class="cnt">
    <div v-if="lastChanged && lastChanged.bucket !== tab" class="note ok" role="status">
      <b>✓ {{ lastChanged.code }} actualizada: ahora está en «{{ TABS.find(([k]) => k === lastChanged!.bucket)?.[1] }}».</b>
    </div>
    <p v-if="pending && !data" class="mut">Cargando…</p>
    <div v-else-if="!data?.items.length" class="note">{{ EMPTY[tab] }}</div>
    <CitaCard v-for="c in data?.items ?? []" :key="c.id + c.estado + c.scheduled_at" :cita="c" @changed="onChanged" />
    <div class="note">
      La cita llega al asesor «Pendiente de aceptación». Si la rechaza, o si falta 1 hora y nadie la aceptó, aparece en
      «Requieren acción» para asignar otro asesor, reprogramarla o cancelarla. Solo Atención al Cliente, Pre-ventas,
      Coordinación y Gerencia reprograman.
    </div>
  </div>
</template>
