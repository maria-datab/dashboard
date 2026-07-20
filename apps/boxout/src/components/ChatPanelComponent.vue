<script setup>
/**
 * Boxout ChatPanel — wraps SharedChatPanel with app file types and copy.
 */
import SharedChatPanel from '@dashboard/shared/components/ChatPanel.vue'

defineProps({
  messages: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
  awaitingConfirm: { type: Boolean, default: false },
  hasBoxes: { type: Boolean, default: false },
})

defineEmits(['send-text', 'attach-file', 'attach-error', 'confirm-choice', 'clear-all'])
</script>

<template>
  <SharedChatPanel
    :messages="messages"
    :busy="busy"
    :awaiting-confirm="awaitingConfirm"
    :has-items="hasBoxes"
    :accepted-extensions="['.csv', '.xlsx', '.jpg', '.jpeg', '.png']"
    empty-hint="Describe a box as D × H × W (e.g. 300 × 2100 × 900 mm) or drag/drop a CSV, Excel, or image."
    composer-placeholder="e.g. 300 × 2100 × 900 (D × H × W)…"
    @send-text="$emit('send-text', $event)"
    @attach-file="$emit('attach-file', $event)"
    @attach-error="$emit('attach-error', $event)"
    @confirm-choice="$emit('confirm-choice', $event)"
    @clear-all="$emit('clear-all')"
  />
</template>
