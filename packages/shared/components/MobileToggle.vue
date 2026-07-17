<script setup>
/**
 * Hidden-radio tab bar. Identical pattern used in both apps.
 *
 * Usage:
 *   <MobileToggle
 *     group="my-pane"
 *     :tabs="[
 *       { id: 'chat',  label: 'Agent',  default: false },
 *       { id: 'view',  label: '3D',     default: true  },
 *     ]"
 *   />
 *
 * Consumers control visibility via CSS selectors:
 *   .main:has(#view:checked) .some-panel { display: block; }
 */
defineProps({
  group: { type: String, required: true },
  tabs: {
    type: Array,  // { id: string, label: string, default?: boolean, disabled?: boolean }
    required: true,
  },
})
</script>

<template>
  <div class="mobile-toggle">
    <template v-for="tab in tabs" :key="tab.id">
      <input
        type="radio"
        :name="group"
        :id="tab.id"
        :checked="tab.default"
        :disabled="tab.disabled"
      />
      <label :for="tab.id">{{ tab.label }}</label>
    </template>
  </div>
</template>
<!-- styles live in tokens.css .mobile-toggle rules -->
