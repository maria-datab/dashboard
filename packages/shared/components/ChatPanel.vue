<script setup>
/**
 * Shared chat panel.
 *
 * Props:
 *   messages          ChatMessage[]   - full history
 *   busy              Boolean         - disables input, shows typing indicator
 *   busyMessage       String          - overrides default "Working…" indicator text
 *   awaitingConfirm   Boolean         - disables input (boxout-style pending confirm)
 *   hasItems          Boolean         - enables the "Clear all" button
 *   acceptedExtensions String[]       - file extensions shown to user and enforced on drop
 *   emptyHint         String          - placeholder shown when messages is empty
 *   composerPlaceholder String        - textarea placeholder
 *
 * Slots:
 *   #above-composer                   - e.g. nesting button row (simple-parts)
 *   #message="{ message }"            - custom renderer for app-specific kinds
 *
 * Emits:
 *   send-text(text: string)
 *   attach-file(file: File)
 *   attach-error(message: string)
 *   confirm-choice(choice: string)    - for kind === 'confirm' bubbles
 *   clear-all
 */

import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
  busyMessage: { type: String, default: '' },
  awaitingConfirm: { type: Boolean, default: false },
  hasItems: { type: Boolean, default: false },
  acceptedExtensions: { type: Array, default: () => [] },
  emptyHint: { type: String, default: 'Type a message or attach a file.' },
  composerPlaceholder: { type: String, default: '…' },
  /** Optional: return true to render a native kind via the #message slot (e.g. result+legend). */
  isCustomMessage: { type: Function, default: null },
})

const emit = defineEmits(['send-text', 'attach-file', 'attach-error', 'confirm-choice', 'clear-all'])

const fileInputRef = ref(null)
const messageListRef = ref(null)
const draftText = ref('')
const isDragging = ref(false)

const inputDisabled = computed(() => props.busy || props.awaitingConfirm)
const canSend = computed(() => draftText.value.trim().length > 0 && !inputDisabled.value)
const isEmpty = computed(() => props.messages.length === 0)

const acceptAttr = computed(() => props.acceptedExtensions.join(','))

async function scrollToBottom() {
  await nextTick()
  const el = messageListRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

watch(() => props.messages.length, scrollToBottom)

function isImportFile(file) {
  if (!props.acceptedExtensions.length) return true
  const name = file.name.toLowerCase()
  return props.acceptedExtensions.some((ext) => name.endsWith(ext))
}

function forwardFile(file) {
  if (!isImportFile(file)) {
    emit('attach-error', `Unsupported file type. Accepted: ${props.acceptedExtensions.join(', ')}`)
    return
  }
  emit('attach-file', file)
}

function openFilePicker() {
  if (inputDisabled.value) return
  fileInputRef.value?.click()
}

function onFileInputChange(event) {
  const file = event.target.files?.[0]
  if (file) forwardFile(file)
  event.target.value = ''
}

function onSendText() {
  const text = draftText.value.trim()
  if (!text || inputDisabled.value) return
  emit('send-text', text)
  draftText.value = ''
}

function onComposerKeydown(event) {
  if (event.key !== 'Enter' || event.shiftKey) return
  event.preventDefault()
  onSendText()
}

function onDragOver(event) {
  event.preventDefault()
  if (inputDisabled.value) return
  isDragging.value = true
}

function onDragLeave() {
  isDragging.value = false
}

function onDrop(event) {
  event.preventDefault()
  isDragging.value = false
  if (inputDisabled.value) return
  const files = event.dataTransfer?.files
  if (!files?.length) return
  if (files.length > 1) {
    emit('attach-error', 'Please drag and drop only one file at a time.')
    return
  }
  forwardFile(files[0])
}

function bubbleClass(message) {
  return {
    'bubble-user': message.role === 'user',
    'bubble-assistant': message.role === 'assistant',
    'bubble-error': message.kind === 'error',
    'bubble-result': message.kind === 'result',
    'bubble-confirm': message.kind === 'confirm',
  }
}

// The five common kinds this component renders natively.
const NATIVE_KINDS = new Set(['text', 'file', 'result', 'error', 'confirm'])

function useMessageSlot(message) {
  if (!NATIVE_KINDS.has(message.kind)) return true
  return Boolean(props.isCustomMessage?.(message))
}
</script>

<template>
  <section
    class="chat-panel"
    :class="{ 'chat-panel--dragging': isDragging, 'chat-panel--busy': busy }"
    :aria-busy="busy"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <div ref="messageListRef" class="message-list" role="log" aria-live="polite">
      <p v-if="isEmpty" class="empty-hint">{{ emptyHint }}</p>

      <article
        v-for="message in messages"
        :key="message.id"
        class="message"
        :class="message.role === 'user' ? 'message-user' : 'message-assistant'"
      >
        <!-- App-specific (or opted-in native) kinds go through the scoped slot -->
        <slot v-if="useMessageSlot(message)" name="message" :message="message">
          <!-- fallback: render as plain text bubble -->
          <div class="bubble" :class="bubbleClass(message)">
            <p class="bubble-text">{{ message.content }}</p>
          </div>
        </slot>

        <!-- Native kinds -->
        <div v-else class="bubble" :class="bubbleClass(message)">
          <p class="bubble-text">{{ message.content }}</p>
          <div v-if="message.kind === 'confirm' && message.meta?.choices" class="confirm-actions">
            <button
              v-for="choice in message.meta.choices"
              :key="choice"
              type="button"
              @click="emit('confirm-choice', choice)"
            >
              {{ choice }}
            </button>
          </div>
        </div>
      </article>

      <p v-if="busy" class="typing-indicator">{{ busyMessage || 'Working…' }}</p>
    </div>

    <div v-if="isDragging" class="drop-overlay" aria-hidden="true">
      Drop file
    </div>

    <!-- Slot for things above the composer (e.g. nesting button in simple-parts) -->
    <slot name="above-composer" />

    <form class="composer" @submit.prevent="onSendText">
      <input
        ref="fileInputRef"
        type="file"
        class="file-input"
        :accept="acceptAttr"
        tabindex="-1"
        @change="onFileInputChange"
      />

      <textarea
        v-model="draftText"
        class="composer-input"
        rows="2"
        :placeholder="composerPlaceholder"
        :disabled="inputDisabled"
        aria-label="Message"
        @keydown="onComposerKeydown"
      />

      <div class="composer-actions">
        <button type="button" class="btn-clear" :disabled="!hasItems || inputDisabled" @click="emit('clear-all')">
          Clear
        </button>
        <button type="button" class="btn-attach" :disabled="inputDisabled" @click="openFilePicker">
          Attach file
        </button>
        <button type="submit" class="btn-send" :disabled="!canSend">Send</button>
      </div>
    </form>
  </section>
</template>

<style scoped>
.chat-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  min-height: 12rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-surface);
  overflow: hidden;
}

.chat-panel--dragging {
  border-color: var(--color-accent);
  background: var(--color-accent-bg);
}

.chat-panel--busy .composer {
  opacity: 0.85;
}

.message-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0.65rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.empty-hint {
  margin: auto 0;
  text-align: center;
  font-size: 0.78rem;
  line-height: 1.4;
  color: var(--color-text-muted);
}

.message {
  display: flex;
  max-width: 92%;
}

.message-user  { align-self: flex-end; }
.message-assistant { align-self: flex-start; }

.bubble {
  padding: 0.45rem 0.6rem;
  border-radius: 8px;
  font-size: 0.8rem;
  line-height: 1.35;
  word-break: break-word;
}

.bubble-user      { background: var(--color-accent-bg);    color: var(--color-text-summary); }
.bubble-assistant { background: var(--color-surface-hover); color: var(--color-text-summary); }
.bubble-result    { background: #ececec; color: #7a7a7a; }
.bubble-error     { background: var(--color-warning-bg);   color: var(--color-warning-emphasis); }
.bubble-confirm   { background: var(--color-accent-bg);    color: var(--color-text-summary); }

.bubble-text {
  margin: 0;
  white-space: pre-line;
}

.confirm-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.45rem;
}

.confirm-actions button {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  cursor: pointer;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
  text-transform: capitalize;
}

.typing-indicator {
  margin: 0;
  font-size: 0.75rem;
  color: var(--color-text-muted);
  font-style: italic;
}

.drop-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(230, 242, 255, 0.92);
  border: 2px dashed var(--color-accent);
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-accent);
  pointer-events: none;
  z-index: 1;
}

.composer {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  min-width: 0;
  padding: 0.5rem;
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
}

.file-input { display: none; }

.composer-input {
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  resize: none;
  min-height: 2.5rem;
  max-height: 6rem;
  padding: 0.4rem 0.5rem;
  font: inherit;
  font-size: 0.8rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
}

.composer-input:focus {
  outline: 2px solid var(--color-accent-bg-hover);
  border-color: var(--color-accent);
}

.composer-input:disabled {
  background: var(--color-surface-hover);
  cursor: not-allowed;
}

.composer-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.composer-actions button {
  padding: 0.3rem 0.65rem;
  font-size: 0.78rem;
  cursor: pointer;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
}

.composer-actions .btn-clear:hover:not(:disabled),
.composer-actions .btn-attach:hover:not(:disabled) {
  background: var(--color-result-bg);
  border-color: var(--color-neutral-edited-accent);
}

.composer-actions button:disabled { opacity: 0.5; cursor: not-allowed; }

.composer-actions .btn-send {
  border: 1px solid var(--color-neutral-edited-accent);
  background: var(--color-result-bg);
  color: var(--color-result-text);
  font-weight: 600;
}

.composer-actions .btn-send:hover:not(:disabled) {
  background: var(--color-neutral-selected);
  border-color: var(--color-result-text);
}
</style>
