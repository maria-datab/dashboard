<script setup>
/**
 * Left sidebar: shared shell + simple-parts chat panel.
 */

import SharedSidebar from '@dashboard/shared/components/Sidebar.vue'
import ChatPanelComponent from './ChatPanelComponent.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
  busyMessage: { type: String, default: '' },
  hasBoxes: { type: Boolean, default: false },
  canStartNesting: { type: Boolean, default: false },
  nestingButtonPrompt: {
    type: String,
    default: 'File ready — run nesting to flatten and nest parts.',
  },
  nestingNeedsRerun: { type: Boolean, default: false },
  activeSheetSizeSelectId: { type: String, default: null },
  activeSheetSizeConfirmId: { type: String, default: null },
  activeMaterialSelectId: { type: String, default: null },
  activeMaterialConfirmId: { type: String, default: null },
  pendingSheetThickness: { type: Number, default: null },
})

const emit = defineEmits([
  'send-text',
  'attach-file',
  'attach-error',
  'clear-all',
  'start-nesting',
  'show-nesting-result',
  'sheet-size-choice',
  'modify-sheet-size',
  'material-choice',
  'modify-material',
])
</script>

<template>
  <SharedSidebar title="Simple Parts">
    <ChatPanelComponent
      class="chat-slot"
      v-bind="props"
      @send-text="emit('send-text', $event)"
      @attach-file="emit('attach-file', $event)"
      @attach-error="emit('attach-error', $event)"
      @clear-all="emit('clear-all')"
      @start-nesting="emit('start-nesting')"
      @show-nesting-result="emit('show-nesting-result')"
      @sheet-size-choice="emit('sheet-size-choice', $event)"
      @modify-sheet-size="emit('modify-sheet-size', $event)"
      @material-choice="emit('material-choice', $event)"
      @modify-material="emit('modify-material', $event)"
    />
  </SharedSidebar>
</template>

<style scoped>
.chat-slot {
  flex: 1;
  min-width: 0;
  min-height: 0;
}
</style>
