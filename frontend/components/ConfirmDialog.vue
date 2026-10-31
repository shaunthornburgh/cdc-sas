<script setup lang="ts">
/** Modal confirmation in the prototype style. Escape or Cancelar closes it. */
withDefaults(
  defineProps<{ title: string; confirmLabel: string; danger?: boolean; busy?: boolean }>(),
  { danger: false, busy: false },
)
const emit = defineEmits<{ confirm: []; cancel: [] }>()

const cancelBtn = ref<HTMLButtonElement | null>(null)
const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape') emit('cancel')
}
onMounted(() => {
  cancelBtn.value?.focus()
  window.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="overlay" @click.self="emit('cancel')">
    <div class="card" role="dialog" aria-modal="true" :aria-label="title">
      <b class="dlg-title">{{ title }}</b>
      <div class="mut"><slot /></div>
      <div class="row">
        <button type="button" class="btn" :class="danger ? 'br' : 'bp'" :disabled="busy" @click="emit('confirm')">
          {{ confirmLabel }}
        </button>
        <button ref="cancelBtn" type="button" class="btn bs" @click="emit('cancel')">Cancelar</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dlg-title {
  font-size: 18px;
}
</style>
