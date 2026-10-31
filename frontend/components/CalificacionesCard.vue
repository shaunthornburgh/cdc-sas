<script setup lang="ts">
import type { Resultado } from '~/types/rendimiento'

/** «Calificaciones (1 a 5)»: read-only dots, or 1–5 buttons for whoever may rate this person. */
const props = defineProps<{ r: Resultado; yo?: boolean }>()
const emit = defineEmits<{ saved: [r: Resultado] }>()
const rend = useRendimiento()

// ---- ratings (only when allowed)
const notas = reactive<Record<string, number | null>>({})
watchEffect(() => {
  for (const c of props.r.calificaciones) if (!c.automatico) notas[c.key] = c.valor
})
const guardando = ref(false)
const msg = ref<string | null>(null)
const err = ref<string | null>(null)
async function guardar() {
  const valores = Object.fromEntries(
    Object.entries(notas).filter(([k, v]) => v != null && props.r.calificaciones.find((c) => c.key === k)?.valor !== v),
  ) as Record<string, number>
  if (!Object.keys(valores).length) return (msg.value = 'No hay cambios.')
  guardando.value = true
  err.value = null
  try {
    const r = await rend.calificar(props.r.user.id, valores)
    const bajos = r.descuentos.length
    msg.value = `Guardadas · ${firstName(r.user.full_name)} las ve en «Mis resultados» pero no puede modificarlas · ${bajos ? `${bajos * 5} puntos de descuento` : 'sin descuentos'}.`
    emit('saved', r)
  } catch (e) {
    err.value = apiErrorMessage(e)
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <div class="card stack">
    <div class="sb">
      <span class="lbl">Calificaciones (1 a 5)</span>
      <span class="mut tiny">{{ r.puede.calificar ? 'Calificas tú' : 'solo lectura' }}</span>
    </div>
    <div v-for="c in r.calificaciones" :key="c.key" class="sb cal">
      <div>
        <b class="small">{{ c.titulo }}</b>
        <div class="mut tiny">{{ c.quien }}</div>
      </div>
      <div v-if="r.puede.calificar && !c.automatico" class="row opts" role="radiogroup" :aria-label="c.titulo">
        <button
          v-for="n in 5"
          :key="n"
          type="button"
          class="opt"
          :class="{ on: notas[c.key] === n, low: notas[c.key] === n && n <= 2 }"
          role="radio"
          :aria-checked="notas[c.key] === n"
          @click="notas[c.key] = n"
        >{{ n }}</button>
      </div>
      <div v-else class="row dots" :aria-label="c.valor == null ? 'Sin dato' : `${c.valor} de 5`">
        <span v-for="n in 5" :key="n" class="dot" :class="{ on: c.valor != null && n <= c.valor, low: c.valor != null && c.valor <= 2 && n <= c.valor }" />
        <b class="small num">{{ c.valor == null ? '—' : `${c.valor}/5` }}</b>
      </div>
    </div>
    <div v-if="r.puede.calificar" class="row fw g8">
      <button type="button" class="btn bp" :disabled="guardando" @click="guardar">Guardar calificaciones</button>
      <span class="chip bad">2 o 1 · se descuentan 5 puntos</span>
    </div>
    <div v-if="msg" class="note ok" role="status"><b>✓ {{ msg }}</b></div>
    <div v-if="err" class="note bad" role="alert"><b>{{ err }}</b></div>
    <div class="mut tiny">
      No tienen peso en el resultado: una calificación de 2 o 1 descuenta 5 puntos. El preoperacional lo calcula el
      sistema. {{ r.perfil === 'coordinacion' ? 'Las demás las asigna la Auxiliar administrativa o Gerencia.' : 'Las demás las asigna solo Coordinación.' }}
      {{ yo ? 'Tú puedes verlas, no modificarlas.' : '' }}
    </div>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.g8 {
  gap: 8px;
}
.fw {
  flex-wrap: wrap;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.cal {
  gap: 10px;
  align-items: center;
}
.opts {
  gap: 4px;
  flex: none;
}
.opts .opt {
  width: 34px;
  min-height: 34px;
  padding: 0;
}
.opts .opt.low {
  background: var(--cdc-bad-bg);
  border-color: var(--sem-rojo);
  color: var(--sem-rojo);
}
.dots {
  gap: 4px;
  flex: none;
}
.dot {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  background: #ecedea;
}
.dot.on {
  background: var(--cdc-green);
}
.dot.low {
  background: var(--sem-rojo);
}
</style>
