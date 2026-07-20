<script setup>
/**
 * Generic viewer checkbox control (label + boolean model).
 */
defineProps({
  label: { type: String, required: true },
  disabled: { type: Boolean, default: false },
  labelClass: { type: String, default: '' },
})

const model = defineModel({ type: Boolean, default: false })
</script>

<template>
  <label class="viewer-checkbox" :class="{ 'viewer-checkbox--disabled': disabled }">
    <input v-model="model" type="checkbox" :disabled="disabled" />
    <span :class="labelClass">{{ label }}</span>
  </label>
</template>

<style scoped>
.viewer-checkbox {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.5rem;
  font-size: 0.8rem;
  color: var(--color-text-summary);
  cursor: pointer;
  user-select: none;
}

.viewer-checkbox--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
