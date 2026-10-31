<script setup lang="ts">
/** On/off switch in the prototype style (.sw). */
const model = defineModel<boolean>({ required: true })
defineProps<{ label: string; disabled?: boolean }>()
</script>

<template>
  <button
    type="button"
    class="sw"
    role="switch"
    :aria-checked="model"
    :aria-label="label"
    :disabled="disabled"
    @click="model = !model"
  >
    <span />
  </button>
</template>
