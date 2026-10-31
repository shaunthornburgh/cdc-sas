<script setup lang="ts">
import type { Pedido, PedidoOpciones } from '~/types/pedidos'

/** One pedido as a card (prototype M06 / C10). */
defineProps<{ pedido: Pedido; opciones: PedidoOpciones; startWith?: string | null }>()
const emit = defineEmits<{ changed: [p: Pedido, msg: string] }>()
</script>

<template>
  <div :id="`pedido-${pedido.code}`" class="card stack" :class="{ urg: pedido.estado_visible === 'urgente' || pedido.vencido }">
    <div class="sb">
      <b>{{ pedido.cliente_nombre }}</b>
      <span class="chip" :class="PEDIDO_ESTADO[pedido.estado_visible]?.cls">{{ PEDIDO_ESTADO[pedido.estado_visible]?.t }}</span>
    </div>
    <div class="row wrap">
      <span class="chip info">{{ NEGOCIO_LABELS[pedido.negocio] }}</span>
      <span class="chip gray">{{ TIPO_INMUEBLE_LABELS[pedido.tipo_inmueble] }}</span>
      <span class="chip gray">{{ pedido.zona }}</span>
      <span class="chip gray">{{ presupuestoTxt(pedido.presupuesto) }}</span>
    </div>
    <div v-if="pedido.observaciones" class="small">{{ pedido.observaciones }}</div>
    <div class="mut tiny">
      {{ pedido.code }} · Pedido: {{ fmtCuando(pedido.created_at) }} · Fecha límite: <b class="txt">{{ fmtCuando(pedido.fecha_limite) }}</b> · Responsable: {{ pedido.responsable.full_name }}
      <template v-if="pedido.motivo_perdida"> · Motivo: {{ opciones.motivos[pedido.motivo_perdida] }}</template>
    </div>
    <PedidoActions :pedido="pedido" :opciones="opciones" :start-with="startWith" @changed="(p, m) => emit('changed', p, m)" />
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.urg {
  border: 2px solid var(--cdc-bad);
}
.wrap {
  flex-wrap: wrap;
  gap: 6px;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.txt {
  color: var(--cdc-text);
}
</style>
