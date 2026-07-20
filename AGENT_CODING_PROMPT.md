# Agent Coding Prompt — Unified Dashboard Migration

> **HISTORICAL.** The migration described below has been completed.
> Do not re-bootstrap from this file. Current layout and run steps: [`README.md`](README.md).
> Architecture notes: [`DASHBOARD_PLAN.md`](DASHBOARD_PLAN.md).

## Context

You are working inside a monorepo root at the path where this file lives.
The current folder contains exactly two subdirectories:

```
boxout-copy/
  boxout-back/      ← Flask API (Python 3.14), port 5000, Rhino.Compute for box geometry
  boxout-front/     ← Vue 3 + Vite, box dimension input via CSV/chat, Three.js 3D viewer
simple-parts-copy/
  simple-parts-back/  ← Flask API (Python 3.14), port 5001, DXF processing + CNC export
  simple-parts-front/ ← Vue 3 + Vite, DXF upload, Three.js mesh viewer, nesting
```

Both frontends: Vue 3, Vite, Three.js, rhino3dm, Anthropic-backed chat.
Both backends: Flask, Python 3.14, Anthropic, python-dotenv.

Your goal is to build a unified dashboard that hosts both tools under one URL, with shared
components extracted into a `packages/shared` library. Execute the phases below in order.
Complete each phase fully before starting the next. Do not skip verification steps.

---

## Phase 1 — Monorepo bootstrap

**Goal:** set up npm workspaces so the repo root manages all packages together.
No existing code moves yet. Verify both apps still build.

### 1.1 — Root `package.json`

Create at repo root:

```json
{
  "name": "dashboard-monorepo",
  "private": true,
  "workspaces": [
    "packages/*",
    "apps/*"
  ],
  "scripts": {
    "dev:boxout": "npm -w apps/boxout run dev",
    "dev:simple-parts": "npm -w apps/simple-parts run dev",
    "dev:dashboard": "npm -w apps/dashboard run dev",
    "build:all": "npm -w apps/boxout run build && npm -w apps/simple-parts run build && npm -w apps/dashboard run build"
  }
}
```

### 1.2 — Move frontends into `apps/`

```
mkdir apps
cp -r boxout-copy/boxout-front   apps/boxout
cp -r simple-parts-copy/simple-parts-front   apps/simple-parts
```

Move backends:

```
mkdir backends
cp -r boxout-copy/boxout-back       backends/boxout
cp -r simple-parts-copy/simple-parts-back   backends/simple-parts
```

> The original `boxout-copy/` and `simple-parts-copy/` folders are kept as a safety backup.
> Do not delete them yet.

### 1.3 — Adjust `package.json` names

In `apps/boxout/package.json` set `"name": "@dashboard/boxout"`.
In `apps/simple-parts/package.json` set `"name": "@dashboard/simple-parts"`.

### 1.4 — Verify

```bash
cd apps/boxout && npm install && npm run build
cd apps/simple-parts && npm install && npm run build
```

Both must build without errors before continuing.

---

## Phase 2 — Create `packages/shared`

**Goal:** extract the design token CSS, the merged ChatPanel component, the generic
Sidebar shell, and the `useJobPoller` composable into an importable shared package.

### 2.1 — `packages/shared/package.json`

```json
{
  "name": "@dashboard/shared",
  "version": "0.0.1",
  "private": true,
  "type": "module",
  "exports": {
    "./styles/tokens.css": "./styles/tokens.css",
    "./components/ChatPanel.vue": "./components/ChatPanel.vue",
    "./components/Sidebar.vue": "./components/Sidebar.vue",
    "./components/MobileToggle.vue": "./components/MobileToggle.vue",
    "./composables/useJobPoller.js": "./composables/useJobPoller.js",
    "./types.js": "./types.js"
  },
  "peerDependencies": {
    "vue": "^3.5.0"
  }
}
```

### 2.2 — `packages/shared/styles/tokens.css`

Merge both apps' `:root` token sets. Use the union of all variables; tokens that only
exist in simple-parts are inert in boxout.

```css
/* Shared design tokens — import this file in every app instead of a local styles.css */
*,
*::before,
*::after {
  box-sizing: border-box;
}

:root {
  /* Accent */
  --color-accent: #1d4e89;
  --color-accent-bg: #e6f2ff;
  --color-accent-bg-hover: #d4e8ff;

  /* Selection */
  --color-selection: #3498db;
  --color-selection-bg: #e3f2fb;

  /* Neutrals */
  --color-border: #cccccc;
  --color-surface: #ffffff;
  --color-surface-hover: #f5f5f5;
  --color-text-summary: #333333;
  --color-text-muted: #888888;
  --color-text-chat: #c4c4c4;
  --color-text-code: #353535;
  --color-viewer-background: #ebebeb;
  --color-viewer-foreground: #333333;

  /* Warm stone */
  --color-neutral-bg: #fafaf9;
  --color-neutral-bg-hover: #f5f5f4;
  --color-neutral-selected: #e7e5e4;
  --color-neutral-accent: #57534e;
  --color-neutral-edited: #f5f2ed;
  --color-neutral-edited-accent: #a8a29e;
  --color-result-bg: #f0efed;
  --color-result-text: #78716c;

  /* Status */
  --color-success: #137333;
  --color-success-bg: #e6f4ea;
  --color-error: #c5221f;
  --color-error-bg: #aa3333;
  --color-error-on: #ffffff;
  --color-warning: #b06000;
  --color-warning-emphasis: #8a5200;
  --color-warning-bg: #fef7e0;

  /* simple-parts: salmon CTA */
  --color-salmon: #e8a090;
  --color-salmon-hover: #d98978;
  --color-salmon-bg: #fde8e2;

  /* simple-parts: part highlight colors */
  --color-part-red: #ff0000;
  --color-part-yellow: #ffff00;
  --color-part-purple: #800080;
  --color-part-brown: #712e11;
  --color-part-green: #188500;
  --color-part-blue: #176498;
  --color-part-grey: #808080;
  --color-part-orange: #ff8c00;
  --color-part-pink: #e91e8c;
  --color-part-default: #b0b0b0;
}

/* Part legend color helpers (used in simple-parts chat bubbles) */
.legend-part-red    { color: var(--color-part-red); }
.legend-part-green  { color: var(--color-part-green); }
.legend-part-blue   { color: var(--color-part-blue); }
.legend-part-grey   { color: var(--color-part-grey); }
.legend-part-orange { color: var(--color-part-orange); }
.legend-part-pink   { color: var(--color-part-pink); }

/* Base resets */
html, body, #app {
  height: 100%;
  margin: 0;
}

body {
  font-family: system-ui, sans-serif;
}

/* Shared app shell */
.app {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  flex: 0 0 16.666667%;
  min-width: 240px;
  padding: 1rem;
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 0;
  overflow: hidden;
}

.main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  height: 100%;
  display: flex;
}

/* Mobile toggle (hidden-radio tab pattern) */
.mobile-toggle {
  display: none;
}

.mobile-toggle input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.mobile-toggle label {
  flex: 1;
  padding: 0.4rem;
  font-size: 0.8rem;
  text-align: center;
  cursor: pointer;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
}

.mobile-toggle input:checked + label {
  background: var(--color-neutral-selected);
}

.mobile-toggle input:disabled + label {
  opacity: 0.45;
  cursor: not-allowed;
}
```

### 2.3 — `packages/shared/types.js`

```js
/**
 * Shared ChatMessage type used by both apps.
 *
 * @typedef {'user' | 'assistant'} ChatMessageRole
 * @typedef {'text' | 'file' | 'result' | 'error' | 'confirm'} ChatMessageKindBase
 *
 * @typedef {object} ChatMessage
 * @property {string} id
 * @property {ChatMessageRole} role
 * @property {string} kind          - ChatMessageKindBase or app-specific extension
 * @property {string} content
 * @property {Record<string, unknown>} [meta]
 */

export {}
```

### 2.4 — `packages/shared/components/ChatPanel.vue`

This is the merged chat panel. It handles all shared logic (scroll, drag/drop, file
picker, keyboard, composer) and natively renders the five common kinds:
`text`, `file`, `result`, `error`, `confirm`.

App-specific message kinds (e.g. `sheet-size-select`, `nesting-result` in simple-parts)
are delegated to the `#message` scoped slot. If no slot is provided the bubble falls
back to showing `message.content` as plain text.

```vue
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
        <!-- App-specific message kinds go through the scoped slot -->
        <slot v-if="!NATIVE_KINDS.has(message.kind)" name="message" :message="message">
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
```

### 2.5 — `packages/shared/components/Sidebar.vue`

```vue
<script setup>
/**
 * Generic sidebar shell. Render the app title + pass a ChatPanel as the default slot.
 *
 * Usage:
 *   <Sidebar title="DoorBoxOut">
 *     <ChatPanel ... />
 *   </Sidebar>
 */
defineProps({
  title: { type: String, required: true },
})
</script>

<template>
  <aside class="sidebar">
    <h1 class="sidebar-title">{{ title }}</h1>
    <slot />
  </aside>
</template>

<style scoped>
/* .sidebar layout rules live in tokens.css; only decorative rules here */
.sidebar-title {
  margin: 0 0 0.25rem;
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-text-summary);
  letter-spacing: -0.01em;
}
</style>
```

### 2.6 — `packages/shared/components/MobileToggle.vue`

```vue
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
```

### 2.7 — `packages/shared/composables/useJobPoller.js`

```js
/**
 * Generic async-job poller.
 *
 * @param {object} options
 * @param {() => Promise<{ jobId: string }>} options.startFn   - POST the job, returns { jobId }
 * @param {(jobId: string) => Promise<object>} options.pollFn  - GET one status snapshot
 * @param {(snapshot: object) => void} [options.onSnapshot]    - called after each poll
 * @param {number} [options.intervalMs]                        - default 1200
 * @param {() => boolean} [options.shouldAbort]                - return true to stop early
 * @returns {Promise<object>} final snapshot when status === 'completed'
 * @throws if status === 'failed' or shouldAbort triggered
 */
export async function runJobPoll({
  startFn,
  pollFn,
  onSnapshot,
  intervalMs = 1200,
  shouldAbort,
}) {
  const start = await startFn()
  const jobId = start.jobId

  while (true) {
    if (shouldAbort?.()) throw new Error('aborted')

    const snapshot = await pollFn(jobId)
    onSnapshot?.(snapshot)

    if (snapshot.status === 'completed') return snapshot
    if (snapshot.status === 'failed') throw new Error(snapshot.error || 'Job failed')

    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
}
```

### 2.8 — Verify shared package structure

```
packages/shared/
  package.json
  types.js
  styles/
    tokens.css
  components/
    ChatPanel.vue
    Sidebar.vue
    MobileToggle.vue
  composables/
    useJobPoller.js
```

Run `npm install` from repo root so workspaces are linked.

---

## Phase 3 — Wire `apps/boxout` to shared

**Goal:** replace boxout's local `styles.css`, `ChatPanelComponent.vue`, and `Sidebar.vue`
with the shared equivalents. The app's logic (App.vue, compute.js, etc.) is unchanged.

### 3.1 — Add shared as a dependency

In `apps/boxout/package.json` add:

```json
"dependencies": {
  "@dashboard/shared": "*"
}
```

Run `npm install` from repo root.

### 3.2 — Replace tokens import

In `apps/boxout/src/main.js`, change:

```js
import './styles/styles.css'
```

to:

```js
import '@dashboard/shared/styles/tokens.css'
```

Delete `apps/boxout/src/styles/styles.css` (it is now superseded by tokens.css).

### 3.3 — Rewrite `apps/boxout/src/components/Sidebar.vue`

Replace the entire file with:

```vue
<script setup>
import SharedSidebar from '@dashboard/shared/components/Sidebar.vue'
import ChatPanelComponent from './ChatPanelComponent.vue'

const props = defineProps({
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
```

> Note: we keep boxout's own `ChatPanelComponent.vue` in place for now — it wraps the shared
> one in Step 3.4. Do not delete it yet.

### 3.4 — Rewrite `apps/boxout/src/components/ChatPanelComponent.vue`

Replace it entirely with a thin wrapper over the shared ChatPanel:

```vue
<script setup>
/**
 * Boxout-specific ChatPanel wrapper.
 * Passes boxout's accepted file types and the confirm-choice handler.
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
```

### 3.5 — Verify boxout

```bash
cd apps/boxout && npm run dev
```

Open the app. Confirm:
- Visual appearance is identical to original (tokens applied correctly).
- Chat panel accepts .csv / .xlsx / image files and rejects others.
- Confirm-choice bubbles work.
- 3D viewer and solve still work.

---

## Phase 4 — Wire `apps/simple-parts` to shared

**Goal:** same substitution for simple-parts. This app's ChatPanel has many app-specific
message kinds (sheet-size-select, material-select, nesting-result, etc.) — those stay in
the app's own file and are passed through the `#message` scoped slot.

### 4.1 — Add shared as a dependency

In `apps/simple-parts/package.json`:

```json
"dependencies": {
  "@dashboard/shared": "*"
}
```

### 4.2 — Replace tokens import

In `apps/simple-parts/src/main.js` change the styles import to:

```js
import '@dashboard/shared/styles/tokens.css'
```

Delete `apps/simple-parts/src/styles/styles.css`.

### 4.3 — Rewrite `apps/simple-parts/src/components/SidebarComponent.vue`

```vue
<script setup>
import SharedSidebar from '@dashboard/shared/components/Sidebar.vue'
import ChatPanelComponent from './ChatPanelComponent.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
  busyMessage: { type: String, default: '' },
  hasBoxes: { type: Boolean, default: false },
  canStartNesting: { type: Boolean, default: false },
  nestingButtonPrompt: { type: String, default: 'File ready — run nesting to flatten and nest parts.' },
  nestingNeedsRerun: { type: Boolean, default: false },
  activeSheetSizeSelectId: { type: String, default: null },
  activeSheetSizeConfirmId: { type: String, default: null },
  activeMaterialSelectId: { type: String, default: null },
  activeMaterialConfirmId: { type: String, default: null },
  pendingSheetThickness: { type: Number, default: null },
})

const emit = defineEmits([
  'send-text', 'attach-file', 'attach-error', 'clear-all',
  'start-nesting', 'show-nesting-result',
  'sheet-size-choice', 'modify-sheet-size',
  'material-choice', 'modify-material',
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
```

### 4.4 — Rewrite `apps/simple-parts/src/components/ChatPanelComponent.vue`

This is the most involved file. Keep all simple-parts-specific logic (sheet-size-select,
material-select, nesting-result, text-position-select, etc.) but replace the structural
scaffolding (drag/drop, file input, composer, scroll) with the shared ChatPanel.

Replace the entire file with the version below. The key changes from the original are:
- Remove all duplicated drag/drop, file picker, scroll, and keyboard code — the shared
  ChatPanel handles those.
- Keep all app-specific state (sheetSizeDrafts, materialDrafts, textPositionSelections)
  and their handlers.
- Pass app-specific message rendering through `template #message="{ message }"`.
- Pass the nesting button through `template #above-composer`.

```vue
<script setup>
/**
 * simple-parts ChatPanel — delegates infrastructure to SharedChatPanel,
 * owns all app-specific message kinds.
 */
import SharedChatPanel from '@dashboard/shared/components/ChatPanel.vue'
import { ref, watch, computed } from 'vue'
import { PLACEHOLDER_MATERIALS } from '../features/shared/createAppState.js'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
  busyMessage: { type: String, default: '' },
  awaitingConfirm: { type: Boolean, default: false },
  activeTextPositionSelectId: { type: String, default: null },
  activeSheetSizeSelectId: { type: String, default: null },
  activeSheetSizeConfirmId: { type: String, default: null },
  activeMaterialSelectId: { type: String, default: null },
  activeMaterialConfirmId: { type: String, default: null },
  pendingSheetThickness: { type: Number, default: null },
  activeExportAssociatedMessageId: { type: String, default: null },
  hasBoxes: { type: Boolean, default: false },
  canStartNesting: { type: Boolean, default: false },
  nestingButtonPrompt: { type: String, default: 'File ready — run nesting to flatten and nest parts.' },
  nestingNeedsRerun: { type: Boolean, default: false },
})

const emit = defineEmits([
  'send-text', 'attach-file', 'attach-error', 'confirm-choice', 'export-associated',
  'text-position-choice', 'sheet-size-choice', 'modify-sheet-size',
  'material-choice', 'modify-material', 'clear-all', 'start-nesting', 'show-nesting-result',
])

// ── App-specific state (unchanged from original) ──────────────────────────────

const TEXT_POSITION_OPTIONS = [
  { value: 'inside', label: 'Inside — text inside the part boundary' },
  { value: 'outside', label: 'Outside — text closest to the part boundary' },
]

const textPositionSelections = ref({})
const sheetSizeDrafts = ref({})
const materialDrafts = ref({})

watch(() => props.messages, (msgs) => {
  const next = { ...textPositionSelections.value }
  for (const message of msgs) {
    if (message.kind !== 'text-position-select') continue
    if (next[message.id] == null && message.meta?.selectedPosition) {
      next[message.id] = message.meta.selectedPosition
    }
  }
  textPositionSelections.value = next
}, { deep: true })

watch(() => props.activeSheetSizeSelectId, (id) => {
  if (!id) return
  const message = props.messages.find((m) => m.id === id)
  if (!message || message.kind !== 'sheet-size-select') return
  const { sheetX, sheetY, sheetThickness } = message.meta ?? {}
  if (sheetX == null && sheetY == null && sheetThickness == null) return
  sheetSizeDrafts.value = {
    ...sheetSizeDrafts.value,
    [id]: {
      sheetX: sheetX != null ? String(sheetX) : '',
      sheetY: sheetY != null ? String(sheetY) : '',
      sheetThickness: sheetThickness != null ? String(sheetThickness) : '',
    },
  }
})

watch(() => props.activeMaterialSelectId, (id) => {
  if (!id) return
  const message = props.messages.find((m) => m.id === id)
  if (!message || message.kind !== 'material-select') return
  const label = message.meta?.materialLabel
  if (label == null && materialDrafts.value[id] != null) return
  materialDrafts.value = { ...materialDrafts.value, [id]: label != null ? String(label) : (materialDrafts.value[id] ?? '') }
})

// ── Helpers (unchanged from original) ────────────────────────────────────────

function nestingResultSummary(message) {
  if (message.meta?.leftoverComplete) {
    const nested = message.meta?.nestedCount
    const previously = message.meta?.previouslyUnassignedCount
    if (typeof nested === 'number' && typeof previously === 'number') {
      const previouslyLabel = previously === 1 ? 'part' : 'parts'
      return `Nesting complete — ${nested} nested + ${previously} previously unassigned ${previouslyLabel} nested`
    }
    return message.content
  }
  const nested = message.meta?.nestedCount
  const unassigned = message.meta?.unassignedCount
  if (typeof nested === 'number' && typeof unassigned === 'number') {
    if (unassigned === 0) return `Nesting complete — ${nested} part${nested === 1 ? '' : 's'}.`
    return `Nesting complete — ${nested} nested, ${unassigned} not nested.`
  }
  return message.content
}

function isActiveTextPositionSelect(m) { return m.kind === 'text-position-select' && m.id === props.activeTextPositionSelectId }
function selectedTextPositionFor(m) { return textPositionSelections.value[m.id] ?? m.meta?.selectedPosition ?? 'inside' }
function onTextPositionSelectChange(m, e) { textPositionSelections.value = { ...textPositionSelections.value, [m.id]: e.target.value } }
function onTextPositionContinue(m) { const p = selectedTextPositionFor(m); if (p) emit('text-position-choice', p) }
function isActiveSheetSizeSelect(m) { return m.kind === 'sheet-size-select' && m.id === props.activeSheetSizeSelectId }
function sheetSizeDraftFor(m) { return sheetSizeDrafts.value[m.id] ?? { sheetX: '', sheetY: '', sheetThickness: '' } }
function updateSheetSizeDraft(m, field, value) { const c = sheetSizeDraftFor(m); sheetSizeDrafts.value = { ...sheetSizeDrafts.value, [m.id]: { ...c, [field]: value } } }
const MAX_SHEET_SIZE_MM = 5000
function parseSheetSize(v) { const n = Number(v); return Number.isFinite(n) && n > 0 ? n : null }
function sheetSizeOverLimit(m) { const d = sheetSizeDraftFor(m); const x = parseSheetSize(d.sheetX); const y = parseSheetSize(d.sheetY); return (x != null && x > MAX_SHEET_SIZE_MM) || (y != null && y > MAX_SHEET_SIZE_MM) }
function canConfirmSheetSize(m) { const d = sheetSizeDraftFor(m); return parseSheetSize(d.sheetX) != null && parseSheetSize(d.sheetY) != null && parseSheetSize(d.sheetThickness) != null && !sheetSizeOverLimit(m) }
function onSheetSizeConfirm(m) { const d = sheetSizeDraftFor(m); const sheetX = parseSheetSize(d.sheetX); const sheetY = parseSheetSize(d.sheetY); const sheetThickness = parseSheetSize(d.sheetThickness); if (sheetX == null || sheetY == null || sheetThickness == null) return; emit('sheet-size-choice', { sheetX, sheetY, sheetThickness }) }
function onModifySheetSize(m) { const id = m.meta?.promptMessageId; if (id) emit('modify-sheet-size', { promptMessageId: id }) }
function isActiveMaterialSelect(m) { return m.kind === 'material-select' && m.id === props.activeMaterialSelectId }
function materialDraftFor(m) { return materialDrafts.value[m.id] ?? '' }
function updateMaterialDraft(m, v) { materialDrafts.value = { ...materialDrafts.value, [m.id]: v } }
function selectedMaterialFor(m) { const label = materialDraftFor(m); return PLACEHOLDER_MATERIALS.find((mat) => mat.label === label) ?? null }
function materialThicknessMismatch(m) { const sel = selectedMaterialFor(m); if (!sel) return null; const t = props.pendingSheetThickness ?? m.meta?.sheetThickness ?? null; if (t == null || sel.thicknessMm === t) return null; return { materialThickness: sel.thicknessMm, sheetThickness: t } }
function canConfirmMaterial(m) { return selectedMaterialFor(m) != null }
function onMaterialConfirm(m) { const sel = selectedMaterialFor(m); if (sel) emit('material-choice', { label: sel.label, thicknessMm: sel.thicknessMm }) }
function onModifyMaterial(m) { const id = m.meta?.promptMessageId; if (id) emit('modify-material', { promptMessageId: id }) }

function bubbleExtraClass(message) {
  return {
    'bubble-user': message.role === 'user',
    'bubble-assistant': message.role === 'assistant',
    'bubble-result': message.kind === 'result' || message.kind === 'nesting-result',
    'bubble-error': message.kind === 'error',
    'bubble-nesting-result--superseded': message.kind === 'nesting-result' && Boolean(message.meta?.superseded),
    'bubble-nesting': message.kind === 'nesting-result',
    'bubble-text-position-select': message.kind === 'text-position-select',
    'bubble-sheet-size-select': message.kind === 'sheet-size-select',
    'bubble-sheet-size-select--leftover': message.kind === 'sheet-size-select' && Boolean(message.meta?.leftover),
    'bubble-sheet-size-confirm': Boolean(message.meta?.sheetSizeConfirm),
    'bubble-material-select': message.kind === 'material-select',
    'bubble-material-confirm': Boolean(message.meta?.materialConfirm),
  }
}
</script>

<template>
  <SharedChatPanel
    :messages="messages"
    :busy="busy"
    :busy-message="busyMessage"
    :has-items="hasBoxes"
    :accepted-extensions="['.dxf', '.3dm', '.dwg']"
    empty-hint="Upload a DXF, DWG, or 3dm file or drag and drop it here to start processing."
    composer-placeholder="…"
    @send-text="emit('send-text', $event)"
    @attach-file="emit('attach-file', $event)"
    @attach-error="emit('attach-error', $event)"
    @confirm-choice="emit('confirm-choice', $event)"
    @clear-all="emit('clear-all')"
  >
    <!-- App-specific message kinds -->
    <template #message="{ message }">
      <div class="bubble" :class="bubbleExtraClass(message)">
        <!-- nesting-result -->
        <template v-if="message.kind === 'nesting-result'">
          <p class="bubble-text">
            {{ nestingResultSummary(message) }}
            <template v-if="!message.meta?.leftoverComplete && message.meta?.unassignedCount > 0">
              <br><span v-if="message.meta.unassignedIdsText" class="nesting-unassigned-ids">{{ message.meta.unassignedIdsText }}</span>
              <template v-if="message.meta.unassignedReasons?.length"><br><span v-for="(reason, i) in message.meta.unassignedReasons" :key="`${reason}-${i}`" class="nesting-unassigned-reason">{{ reason }}<br></span></template>
              <span class="nesting-unassigned-hint">Unassigned parts will now show <span class="legend-part-red">red</span> in app viewer.</span>
            </template>
          </p>
          <div v-if="!message.meta?.superseded" class="nesting-result-actions">
            <button type="button" class="btn-show-nesting-result" @click="emit('show-nesting-result')">
              {{ message.meta?.leftoverComplete ? 'Show full nesting result' : 'Show nesting result' }}
            </button>
          </div>
        </template>

        <!-- text-position-select -->
        <template v-else-if="message.kind === 'text-position-select'">
          <p class="bubble-text">
            {{ message.content }}
            <template v-if="!isActiveTextPositionSelect(message) && selectedTextPositionFor(message)">
              <br><span class="text-position-choice-value">{{ selectedTextPositionFor(message) }}</span>
            </template>
          </p>
          <div v-if="isActiveTextPositionSelect(message)" class="text-position-select-actions">
            <select class="text-position-select" :value="selectedTextPositionFor(message)" @change="onTextPositionSelectChange(message, $event)">
              <option v-for="opt in TEXT_POSITION_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
            <button type="button" @click="onTextPositionContinue(message)">Continue</button>
          </div>
        </template>

        <!-- sheet-size-select -->
        <template v-else-if="message.kind === 'sheet-size-select'">
          <p class="bubble-text">{{ message.content }}</p>
          <div v-if="isActiveSheetSizeSelect(message)" class="sheet-size-select-actions">
            <div class="sheet-size-row"><input type="number" class="sheet-size-input" min="0" step="any" inputmode="decimal" :value="sheetSizeDraftFor(message).sheetX" aria-label="Sheet width mm" @input="updateSheetSizeDraft(message, 'sheetX', $event.target.value)" /><span class="sheet-size-label">mm (X)</span></div>
            <div class="sheet-size-row"><input type="number" class="sheet-size-input" min="0" step="any" inputmode="decimal" :value="sheetSizeDraftFor(message).sheetY" aria-label="Sheet height mm" @input="updateSheetSizeDraft(message, 'sheetY', $event.target.value)" /><span class="sheet-size-label">mm (Y)</span></div>
            <div class="sheet-size-row"><input type="number" class="sheet-size-input" min="0" step="any" inputmode="decimal" :value="sheetSizeDraftFor(message).sheetThickness" aria-label="Sheet thickness mm" @input="updateSheetSizeDraft(message, 'sheetThickness', $event.target.value)" /><span class="sheet-size-label">mm (thickness)</span></div>
            <p v-if="sheetSizeOverLimit(message)" class="sheet-size-warning">You are exceeding the available maximum plate size. The maximum is 5000 mm for both X and Y.</p>
            <button type="button" :disabled="!canConfirmSheetSize(message)" @click="onSheetSizeConfirm(message)">Confirm</button>
          </div>
        </template>

        <!-- sheet-size-confirm -->
        <template v-else-if="message.meta?.sheetSizeConfirm">
          <p class="bubble-text">{{ message.content }}</p>
          <button v-if="message.id === activeSheetSizeConfirmId" type="button" class="btn-sheet-size-modify" @click="onModifySheetSize(message)">Modify</button>
        </template>

        <!-- material-select -->
        <template v-else-if="message.kind === 'material-select'">
          <p class="bubble-text">{{ message.content }}</p>
          <div v-if="isActiveMaterialSelect(message)" class="sheet-size-select-actions">
            <select class="material-select" :value="materialDraftFor(message)" aria-label="Material" @change="updateMaterialDraft(message, $event.target.value)">
              <option value="" disabled>Select material…</option>
              <option v-for="mat in PLACEHOLDER_MATERIALS" :key="mat.label" :value="mat.label">{{ mat.label }} ({{ mat.thicknessMm }} mm)</option>
            </select>
            <p v-if="materialThicknessMismatch(message)" class="sheet-size-warning">The thickness of the chosen material differs from the chosen sheet thickness ({{ materialThicknessMismatch(message).materialThickness }} vs {{ materialThicknessMismatch(message).sheetThickness }} mm).</p>
            <button type="button" :disabled="!canConfirmMaterial(message)" @click="onMaterialConfirm(message)">Confirm</button>
          </div>
        </template>

        <!-- material-confirm -->
        <template v-else-if="message.meta?.materialConfirm">
          <p class="bubble-text">{{ message.content }}</p>
          <button v-if="message.id === activeMaterialConfirmId" type="button" class="btn-sheet-size-modify" @click="onModifyMaterial(message)">Modify</button>
        </template>

        <!-- export-associated -->
        <template v-else-if="message.meta?.showExportAssociated && message.id === activeExportAssociatedMessageId">
          <p class="bubble-text">{{ message.content }}</p>
          <div class="confirm-actions">
            <button type="button" :disabled="busy" @click="emit('export-associated')">Export associated parts</button>
          </div>
        </template>

        <!-- result with legend -->
        <template v-else-if="message.kind === 'result' && message.meta?.legend">
          <p class="bubble-text">{{ message.content }}<br><br>
            <template v-for="m in message.meta.legend.materials" :key="m.label">- <span :class="'legend-part-' + m.color">{{ m.label }}</span>: {{ m.count }} {{ m.count === 1 ? 'curve' : 'curves' }}<br></template>
            <template v-if="message.meta.legend.red">- <span class="legend-part-red">Missing/Faulty metadata</span> ({{ message.meta.legend.red }})<br></template>
          </p>
        </template>

        <!-- result with greenHint -->
        <template v-else-if="message.meta?.greenHint">
          <p class="bubble-text">Use Output view with <strong>Correct parts</strong> / <strong>Incorrect parts</strong> to see metadata status (<span class="legend-part-green">green</span> = complete, <span class="legend-part-red">red</span> = missing).</p>
        </template>

        <!-- fallback -->
        <template v-else>
          <p class="bubble-text">{{ message.content }}</p>
        </template>
      </div>
    </template>

    <!-- Nesting button above composer -->
    <template v-if="canStartNesting && !activeSheetSizeSelectId && !activeMaterialSelectId" #above-composer>
      <div class="bubble bubble-nesting" :class="{ 'bubble-nesting--modified': nestingNeedsRerun }">
        <p class="bubble-text">{{ nestingButtonPrompt }}</p>
        <button type="button" class="btn-nesting" :class="{ 'btn-nesting--modified': nestingNeedsRerun }" :disabled="busy" @click="emit('start-nesting')">Nest</button>
      </div>
    </template>
  </SharedChatPanel>
</template>

<style scoped>
/* Only app-specific styles live here. All base bubble/panel/composer styles are in SharedChatPanel. */

.bubble-nesting {
  margin: 0 0.5rem 0.25rem;
  padding: 0.45rem 0.6rem;
  border-radius: 8px;
  font-size: 0.8rem;
  line-height: 1.35;
  background: var(--color-accent-bg);
  color: var(--color-text-summary);
  border: 1px solid var(--color-accent);
}

.bubble-nesting--modified {
  background: var(--color-warning-bg);
  border-color: var(--color-warning-emphasis);
}

.btn-nesting {
  display: block;
  width: 100%;
  margin-top: 0.5rem;
  padding: 0.55rem 0.75rem;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  color: var(--color-surface);
  background: var(--color-accent);
  border: 1px solid var(--color-accent);
  border-radius: 6px;
}

.btn-nesting:hover:not(:disabled) { background: #163d6e; }
.btn-nesting--modified { background: var(--color-warning-emphasis); border-color: var(--color-warning-emphasis); }
.btn-nesting--modified:hover:not(:disabled) { background: #e68a00; }
.btn-nesting:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-show-nesting-result {
  display: block;
  width: 100%;
  padding: 0.45rem 0.6rem;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  color: var(--color-surface);
  background: var(--color-accent);
  border: 1px solid var(--color-accent);
  border-radius: 6px;
}

.btn-show-nesting-result:hover { background: #163d6e; }

.bubble-nesting-result--superseded {
  color: var(--color-text-muted);
  text-decoration: line-through;
  opacity: 0.75;
}

.nesting-result-actions { margin-top: 0.45rem; }
.nesting-unassigned-ids { display: inline-block; margin-top: 0.35rem; }
.nesting-unassigned-reason { display: inline-block; margin-top: 0.2rem; font-size: 0.85em; color: var(--color-text-muted); }
.nesting-unassigned-hint { display: inline-block; margin-top: 0.45rem; font-size: 0.85em; color: var(--color-text-muted); font-style: italic; }

.text-position-select-actions { display: flex; flex-direction: column; gap: 0.35rem; margin-top: 0.45rem; }
.text-position-select { width: 100%; padding: 0.25rem 0.35rem; font-size: 0.75rem; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-surface); }
.text-position-select-actions button { align-self: flex-start; padding: 0.25rem 0.5rem; font-size: 0.75rem; cursor: pointer; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-surface); }
.text-position-choice-value { font-style: italic; color: var(--color-text-muted); text-transform: capitalize; }

.bubble-sheet-size-select { background: var(--color-accent-bg); color: var(--color-text-summary); }
.bubble-sheet-size-select--leftover { background: var(--color-warning-bg); border: 1px solid var(--color-warning-emphasis); }
.bubble-material-select { background: var(--color-accent-bg); color: var(--color-text-summary); }
.bubble-sheet-size-confirm, .bubble-material-confirm { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; background: var(--color-surface-hover); color: var(--color-text-summary); }
.bubble-sheet-size-confirm .bubble-text, .bubble-material-confirm .bubble-text { flex: 1; min-width: 0; }

.btn-sheet-size-modify { flex-shrink: 0; padding: 0.2rem 0.45rem; font-size: 0.72rem; cursor: pointer; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-surface); }
.btn-sheet-size-modify:hover { background: var(--color-result-bg); border-color: var(--color-neutral-edited-accent); }

.sheet-size-select-actions { display: flex; flex-direction: column; gap: 0.35rem; margin-top: 0.45rem; }
.sheet-size-row { display: flex; align-items: center; gap: 0.4rem; }
.sheet-size-input { flex: 1; min-width: 0; padding: 0.25rem 0.35rem; font-size: 0.75rem; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-surface); }
.sheet-size-label { flex-shrink: 0; font-size: 0.75rem; color: var(--color-text-muted); }
.sheet-size-warning { margin: 0; padding: 0.35rem 0.45rem; font-size: 0.72rem; line-height: 1.35; color: var(--color-warning-emphasis); background: var(--color-warning-bg); border-radius: 4px; }
.sheet-size-select-actions button { align-self: flex-start; padding: 0.25rem 0.5rem; font-size: 0.75rem; cursor: pointer; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-surface); }
.sheet-size-select-actions button:disabled { opacity: 0.5; cursor: not-allowed; }
.material-select { width: 100%; padding: 0.25rem 0.35rem; font-size: 0.75rem; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-surface); }

.bubble-text { margin: 0; white-space: pre-line; }
.confirm-actions { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.45rem; }
.confirm-actions button { padding: 0.25rem 0.5rem; font-size: 0.75rem; cursor: pointer; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-surface); text-transform: capitalize; }
</style>
```

### 4.5 — Verify simple-parts

```bash
cd apps/simple-parts && npm run dev
```

Confirm:
- Visual appearance identical to original.
- DXF drag/drop works, only `.dxf/.3dm/.dwg` accepted.
- Sheet-size-select, material-select, nesting-result messages render correctly.
- Nesting button appears and triggers correctly.
- 3D viewer functional.

---

## Phase 5 — Dashboard shell app

**Goal:** build a new minimal app that hosts both tools under one URL via Vue Router.

### 5.1 — Scaffold `apps/dashboard/`

```
apps/dashboard/
  package.json
  index.html
  vite.config.js
  src/
    main.js
    App.vue
    router.js
    views/
      HomeView.vue
```

### 5.2 — `apps/dashboard/package.json`

```json
{
  "name": "@dashboard/app",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@dashboard/shared": "*",
    "vue": "^3.5.0",
    "vue-router": "^4.4.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^6.0.0"
  }
}
```

### 5.3 — `apps/dashboard/index.html`

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Dashboard</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

### 5.4 — `apps/dashboard/vite.config.js`

```js
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      // Route each app's API calls to its respective backend
      '/api/boxout': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/boxout/, ''),
      },
      '/api/simple-parts': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/simple-parts/, ''),
      },
    },
  },
})
```

### 5.5 — `apps/dashboard/src/main.js`

```js
import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import '@dashboard/shared/styles/tokens.css'
import App from './App.vue'
import router from './router.js'

createApp(App).use(router).mount('#app')
```

### 5.6 — `apps/dashboard/src/router.js`

```js
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('./views/HomeView.vue'),
  },
  {
    // All /boxout/* paths go to the boxout app root
    path: '/boxout',
    component: () => import('../../boxout/src/App.vue'),
  },
  {
    path: '/simple-parts',
    component: () => import('../../simple-parts/src/App.vue'),
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
```

> IMPORTANT: after adding routes, each app's `main.js` (in `apps/boxout` and
> `apps/simple-parts`) must NOT call `createApp().mount()` when loaded as a component
> inside the dashboard. The safe approach: conditionally mount only when run standalone.
>
> In each app's `main.js`, wrap the mount call:
>
> ```js
> // Only mount directly when running as a standalone app (not imported by dashboard)
> if (document.getElementById('app')) {
>   createApp(App).mount('#app')
> }
> ```

### 5.7 — `apps/dashboard/src/App.vue`

```vue
<script setup>
import { useRouter, useRoute } from 'vue-router'
const router = useRouter()
const route = useRoute()
</script>

<template>
  <div class="dashboard-root">
    <nav class="top-nav" v-if="route.path !== '/' || true">
      <span class="top-nav-logo">Dashboard</span>
      <router-link to="/" class="nav-link">Home</router-link>
      <router-link to="/boxout" class="nav-link">DoorBoxOut</router-link>
      <router-link to="/simple-parts" class="nav-link">Simple Parts</router-link>
    </nav>
    <router-view class="dashboard-view" />
  </div>
</template>

<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; }

.dashboard-root {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.top-nav {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0 1rem;
  height: 36px;
  background: var(--color-accent);
  color: #fff;
  font-size: 0.82rem;
  z-index: 100;
}

.top-nav-logo {
  font-weight: 700;
  letter-spacing: -0.01em;
  margin-right: auto;
}

.nav-link {
  color: rgba(255, 255, 255, 0.85);
  text-decoration: none;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  transition: background 0.12s;
}

.nav-link:hover,
.nav-link.router-link-active {
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
}

.dashboard-view {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>
```

### 5.8 — `apps/dashboard/src/views/HomeView.vue`

```vue
<template>
  <div class="home">
    <h1 class="home-title">Dashboard</h1>
    <p class="home-subtitle">Select a tool to get started.</p>
    <div class="tool-grid">
      <router-link to="/boxout" class="tool-card">
        <strong>DoorBoxOut</strong>
        <p>Parametric box design via CSV or chat. 3D viewer + nesting.</p>
      </router-link>
      <router-link to="/simple-parts" class="tool-card">
        <strong>Simple Parts</strong>
        <p>DXF part processing, metadata correction, nesting, and CNC export.</p>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 1.5rem;
  padding: 2rem;
  background: var(--color-neutral-bg);
}

.home-title {
  margin: 0;
  font-size: 1.5rem;
  color: var(--color-text-summary);
}

.home-subtitle {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.tool-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  width: 100%;
  max-width: 600px;
}

.tool-card {
  display: block;
  padding: 1.25rem 1.5rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  text-decoration: none;
  color: var(--color-text-summary);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.tool-card:hover {
  border-color: var(--color-accent);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.tool-card strong {
  display: block;
  font-size: 1rem;
  margin-bottom: 0.4rem;
  color: var(--color-accent);
}

.tool-card p {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.4;
  color: var(--color-text-muted);
}
</style>
```

### 5.9 — Update each app's API base URL for dashboard context

Each app currently calls its backend via a relative path configured in Vite's proxy.
When running inside the dashboard, the proxy prefixes change.

In `apps/boxout/src/scripts/env.js` (or wherever `VITE_API_BASE` is read), the env var
`VITE_API_BASE` needs to equal `/api/boxout` when served from the dashboard.

Create `apps/boxout/.env.dashboard`:
```
VITE_API_BASE=/api/boxout
VITE_BACKEND_URL=http://127.0.0.1:5000
```

Create `apps/simple-parts/.env.dashboard`:
```
VITE_API_BASE=/api/simple-parts
```

When running standalone, the existing `.env` / `.env.local` still works unchanged.

### 5.10 — Verify dashboard

```bash
# Terminal 1: boxout backend
cd backends/boxout && pipenv run dev

# Terminal 2: simple-parts backend
cd backends/simple-parts && pipenv run serve

# Terminal 3: dashboard dev server
cd apps/dashboard && npm run dev
```

Open `http://localhost:5173`. Confirm:
- Home page shows both tool cards.
- Navigating to `/boxout` loads the full boxout app (chat, 3D viewer, all features).
- Navigating to `/simple-parts` loads the full simple-parts app.
- Back button and nav links work correctly.
- API calls from both apps reach their respective backends via the proxy.

---

## Phase 6 — Backend shared modules

**Goal:** eliminate duplicated env-reading helpers and LLM plumbing across both backends.

### 6.1 — Create `backends/shared/config_helpers.py`

```python
"""
Shared environment-reading helpers. Both backends import from here.
Usage: from shared.config_helpers import env_bool, env_int, env_str, env_float
"""
import os


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def env_int(name: str, default: int = 0) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def env_float(name: str, default: float = 0.0) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def env_str(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()
```

### 6.2 — Create `backends/shared/llm_base.py`

```python
"""
Base class for Anthropic LLM callers. Both backends inherit from BaseLLMParser.

Usage:
    from shared.llm_base import BaseLLMParser

    class MyParser(BaseLLMParser):
        def parse(self, user_input: str) -> dict:
            response = self.call(
                system_prompt="You are ...",
                user_message=user_input,
            )
            return json.loads(response)
"""
import json
import anthropic


class BaseLLMParser:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5",
        max_tokens: int = 1024,
    ):
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def call(self, system_prompt: str, user_message: str) -> str:
        """
        Send one turn to the Anthropic API and return the text response.
        Raises anthropic.APIError on failure.
        """
        message = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text

    def call_json(self, system_prompt: str, user_message: str) -> dict:
        """
        Like call(), but parses the response as JSON.
        Raises json.JSONDecodeError if the model returns invalid JSON.
        """
        raw = self.call(system_prompt, user_message)
        # Strip markdown fences if the model wraps its output
        stripped = raw.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        return json.loads(stripped)
```

### 6.3 — Update `backends/boxout/config.py`

Replace the four `_env_*` private functions with imports from shared:

```python
from pathlib import Path
from dotenv import load_dotenv
from shared.config_helpers import env_bool, env_int, env_float, env_str

_BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(_BACKEND_DIR / ".env")

def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else _BACKEND_DIR / path

PORT = env_int("PORT", 5000)
FLASK_DEBUG = env_bool("FLASK_DEBUG", True)
FLASK_HOST = env_str("FLASK_HOST", "127.0.0.1")
# … rest of config.py unchanged …
```

### 6.4 — Update `backends/simple-parts/config.py`

Same substitution: replace `os.getenv` wrappers with imports from `shared.config_helpers`.

### 6.5 — Update `backends/boxout/llm.py` and `backends/simple-parts/llm.py`

In each file, replace the raw `anthropic.Anthropic()` client construction with a call to
`BaseLLMParser`:

```python
from shared.llm_base import BaseLLMParser
import config

class CSVAnalyzer(BaseLLMParser):
    def __init__(self):
        super().__init__(api_key=config.ANTHROPIC_API_KEY)
    # existing methods unchanged — call self.call() or self.call_json() instead of raw client
```

Each backend's `llm.py` callers already use a structured call pattern; only the
instantiation and the raw API call line change.

### 6.6 — Make `backends/shared` importable

Add a `backends/shared/__init__.py` (empty file) so Python treats it as a package.

In each backend's `Pipfile`, ensure the backend root is in `PYTHONPATH` when running:

```
[scripts]
dev = "PYTHONPATH=.. python app.py"   # boxout
serve = "PYTHONPATH=.. python app.py" # simple-parts
```

This allows `from shared.config_helpers import …` to resolve.

### 6.7 — Verify backends

```bash
cd backends/boxout && pipenv run dev
cd backends/simple-parts && pipenv run serve
```

Both must start without import errors. Run `GET /health` on each to confirm.

---

## Completion checklist

Before considering the migration done, confirm all of the following:

- [ ] `apps/boxout` builds and runs standalone (`npm run dev` from `apps/boxout`).
- [ ] `apps/simple-parts` builds and runs standalone.
- [ ] `apps/dashboard` builds and both tools are accessible and fully functional via the nav.
- [ ] Chat panel: file drag/drop works in both tools with correct extension filtering.
- [ ] simple-parts: sheet-size-select, material-select, and nesting-result messages render.
- [ ] boxout: confirm-choice messages render.
- [ ] API proxy: boxout calls go to port 5000; simple-parts calls go to 5001.
- [ ] Both backends start from their new locations without import errors.
- [ ] `packages/shared` has no runtime dependency on either app (no imports from `apps/`).
- [ ] The original `boxout-copy/` and `simple-parts-copy/` folders are untouched (safety backup).

---

## What NOT to change

Do not touch any of the following — they are intentionally left app-specific:

- `apps/boxout/src/components/3DViewer.vue` — Three.js rendering, solve logic
- `apps/boxout/src/scripts/compute.js` — rhino3dm decode, GH API client
- `apps/boxout/src/components/CsvPreviewComponent.vue`
- `apps/boxout/src/components/ParallelCoordinatesComponent.vue`
- `apps/simple-parts/src/components/ThreeMeshViewer.vue`
- `apps/simple-parts/src/components/NestingResultModalComponent.vue`
- `apps/simple-parts/src/components/PartMetadataPanel.vue`
- `apps/simple-parts/src/features/` (all feature composables)
- Either backend's route logic, job system, or GH compute calls
