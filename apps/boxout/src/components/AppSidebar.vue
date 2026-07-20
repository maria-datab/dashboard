<script setup>
/**
 * Left sidebar: shared shell + boxout chat panel.
 */

import SharedSidebar from '@dashboard/shared/components/Sidebar.vue'
import ChatPanelComponent from './ChatPanelComponent.vue'

defineProps({
  messages: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
  awaitingConfirm: { type: Boolean, default: false },
  hasBoxes: { type: Boolean, default: false },
})

const emit = defineEmits(['send-text', 'attach-file', 'attach-error', 'confirm-choice', 'clear-all'])
</script>

<template>
  <SharedSidebar title="DoorBoxOut">
    <ChatPanelComponent
      class="chat-slot"
      :messages="messages"
      :busy="busy"
      :awaiting-confirm="awaitingConfirm"
      :has-boxes="hasBoxes"
      @send-text="emit('send-text', $event)"
      @attach-file="emit('attach-file', $event)"
      @attach-error="emit('attach-error', $event)"
      @confirm-choice="emit('confirm-choice', $event)"
      @clear-all="emit('clear-all')"
    />
  </SharedSidebar>
</template>

<style scoped>
.chat-slot {
  flex: 1;
  min-height: 0;
}
</style>
