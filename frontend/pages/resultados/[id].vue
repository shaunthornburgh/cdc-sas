<script setup lang="ts">
import type { Resultado } from '~/types/rendimiento'

/**
 * One person's month for Coordinación / Gerencia / Auxiliar (K18 detail, K14-ger).
 * Whoever may rate this person does it here; weights and goals are in «Rendimiento e indicadores».
 */
definePageMeta({ cargos: ['coordinacion', 'gerencia', 'auxiliar_administrativa'] })

const route = useRoute()
const rend = useRendimiento()
const meses = ultimosMeses()
const periodo = ref((route.query.periodo as string) || meses[0]!.key)
const id = computed(() => route.params.id as string)
const { data, error, refresh } = await useAsyncData(`resultado-${id.value}`, () => rend.persona(id.value, periodo.value), { watch: [periodo] })
useHead(() => ({ title: `${data.value?.user.full_name ?? 'Resultados'} · Casa Dolce Casa` }))

function onSaved(r: Resultado) {
  data.value = r
}
</script>

<template>
  <PageBar
    :title="data?.perfil === 'coordinacion' ? 'Rendimiento del Coordinador' : (data?.user.full_name ?? 'Resultados')"
    :subtitle="data ? `${data.user.full_name} · ${data.cargo_txt} · ${data.periodo.label}` : ''"
    back="/equipo"
  >
    <select v-model="periodo" class="fsel" aria-label="Mes">
      <option v-for="m in meses" :key="m.key" :value="m.key">{{ m.t }}</option>
    </select>
    <NuxtLink v-if="data?.puede.configurar" class="btn bs" :to="`/rendimiento?persona=${id}`">Pesos y metas ›</NuxtLink>
  </PageBar>
  <div class="cnt narrow">
    <div v-if="error" class="note bad"><b>No se pudo cargar.</b> {{ apiErrorMessage(error) }}</div>
    <template v-else-if="data">
      <ResultadoView :r="data" @saved="onSaved" />
      <div v-if="data.detalle" class="g2b">
        <div class="card stack">
          <div class="lbl">{{ data.perfil === 'atencion' ? 'Leads en proceso' : 'Pedidos en proceso' }}</div>
          <div v-for="g in data.detalle.en_proceso" :key="g.code" class="sb it row-it">
            <div>
              <b class="small">{{ g.code }} · {{ g.titulo }}</b>
              <div class="mut tiny">{{ g.detalle }}</div>
            </div>
            <NuxtLink class="chip" :class="g.cls" :to="g.link">{{ g.estado }}</NuxtLink>
          </div>
          <div v-if="!data.detalle.en_proceso.length" class="note">
            {{ data.perfil === 'atencion' ? 'Sin leads abiertos.' : data.perfil === 'asesor' ? 'Sin pedidos abiertos. Los negocios en proceso se verán aquí cuando exista el módulo de negocios.' : 'No aplica.' }}
          </div>
        </div>
        <div class="card stack">
          <div class="lbl">Clientes perdidos · {{ data.periodo.label.split(' ')[0] }}</div>
          <div v-for="(x, i) in data.detalle.perdidos" :key="i" class="sb it row-it">
            <div><b class="small">{{ x.cliente }}</b><div class="mut tiny">{{ x.motivo }}</div></div>
            <span class="mut tiny">{{ x.fecha ? fmtCuando(x.fecha) : '' }}</span>
          </div>
          <div v-if="!data.detalle.perdidos.length" class="note ok">Sin clientes perdidos este mes.</div>
        </div>
      </div>
      <div class="note">
        Las cifras salen solas de lo que registra cada persona; no se editan aquí. Una meta se da por cumplida cuando el área
        llega al 100 %. <button type="button" class="linkbtn" @click="refresh()">Actualizar</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.narrow {
  max-width: 1080px;
  width: 100%;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.linkbtn {
  border: 0;
  background: none;
  padding: 0;
  color: var(--cdc-green);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}
</style>
