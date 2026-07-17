<script setup>
/**
 * simple-parts ChatPanel — delegates infrastructure to SharedChatPanel,
 * owns all app-specific message kinds and enriched native bubbles.
 */
import SharedChatPanel from '@dashboard/shared/components/ChatPanel.vue'
import { ref, watch } from 'vue'
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
  nestingButtonPrompt: {
    type: String,
    default: 'File ready — run nesting to flatten and nest parts.',
  },
  nestingNeedsRerun: { type: Boolean, default: false },
})

const emit = defineEmits([
  'send-text',
  'attach-file',
  'attach-error',
  'confirm-choice',
  'export-associated',
  'text-position-choice',
  'sheet-size-choice',
  'modify-sheet-size',
  'material-choice',
  'modify-material',
  'clear-all',
  'start-nesting',
  'show-nesting-result',
])

const TEXT_POSITION_OPTIONS = [
  { value: 'inside', label: 'Inside — text inside the part boundary' },
  { value: 'outside', label: 'Outside — text closest to the part boundary' },
]

const textPositionSelections = ref({})
const sheetSizeDrafts = ref({})
const materialDrafts = ref({})

/** Native kinds that still need simple-parts-specific bubble content. */
function isCustomMessage(message) {
  return Boolean(
    message.meta?.legend
    || message.meta?.greenHint
    || message.meta?.missingSerialCount != null
    || message.meta?.missingMaterialCount != null
    || message.meta?.missingAnzCount != null
    || message.meta?.inspectUnsolvedCount != null
    || message.meta?.sheetSizeConfirm
    || message.meta?.materialConfirm
    || message.meta?.showExportAssociated,
  )
}

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
  materialDrafts.value = {
    ...materialDrafts.value,
    [id]: label != null ? String(label) : (materialDrafts.value[id] ?? ''),
  }
})

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

function isActiveTextPositionSelect(m) {
  return m.kind === 'text-position-select' && m.id === props.activeTextPositionSelectId
}
function selectedTextPositionFor(m) {
  return textPositionSelections.value[m.id] ?? m.meta?.selectedPosition ?? 'inside'
}
function onTextPositionSelectChange(m, e) {
  textPositionSelections.value = { ...textPositionSelections.value, [m.id]: e.target.value }
}
function onTextPositionContinue(m) {
  const p = selectedTextPositionFor(m)
  if (p) emit('text-position-choice', p)
}
function isActiveSheetSizeSelect(m) {
  return m.kind === 'sheet-size-select' && m.id === props.activeSheetSizeSelectId
}
function sheetSizeDraftFor(m) {
  return sheetSizeDrafts.value[m.id] ?? { sheetX: '', sheetY: '', sheetThickness: '' }
}
function updateSheetSizeDraft(m, field, value) {
  const c = sheetSizeDraftFor(m)
  sheetSizeDrafts.value = { ...sheetSizeDrafts.value, [m.id]: { ...c, [field]: value } }
}
const MAX_SHEET_SIZE_MM = 5000
function parseSheetSize(v) {
  const n = Number(v)
  return Number.isFinite(n) && n > 0 ? n : null
}
function sheetSizeOverLimit(m) {
  const d = sheetSizeDraftFor(m)
  const x = parseSheetSize(d.sheetX)
  const y = parseSheetSize(d.sheetY)
  return (x != null && x > MAX_SHEET_SIZE_MM) || (y != null && y > MAX_SHEET_SIZE_MM)
}
function canConfirmSheetSize(m) {
  const d = sheetSizeDraftFor(m)
  return parseSheetSize(d.sheetX) != null
    && parseSheetSize(d.sheetY) != null
    && parseSheetSize(d.sheetThickness) != null
    && !sheetSizeOverLimit(m)
}
function onSheetSizeConfirm(m) {
  const d = sheetSizeDraftFor(m)
  const sheetX = parseSheetSize(d.sheetX)
  const sheetY = parseSheetSize(d.sheetY)
  const sheetThickness = parseSheetSize(d.sheetThickness)
  if (sheetX == null || sheetY == null || sheetThickness == null) return
  emit('sheet-size-choice', { sheetX, sheetY, sheetThickness })
}
function onModifySheetSize(m) {
  const id = m.meta?.promptMessageId
  if (id) emit('modify-sheet-size', { promptMessageId: id })
}
function isActiveMaterialSelect(m) {
  return m.kind === 'material-select' && m.id === props.activeMaterialSelectId
}
function materialDraftFor(m) {
  return materialDrafts.value[m.id] ?? ''
}
function updateMaterialDraft(m, v) {
  materialDrafts.value = { ...materialDrafts.value, [m.id]: v }
}
function selectedMaterialFor(m) {
  const label = materialDraftFor(m)
  return PLACEHOLDER_MATERIALS.find((mat) => mat.label === label) ?? null
}
function materialThicknessMismatch(m) {
  const sel = selectedMaterialFor(m)
  if (!sel) return null
  const t = props.pendingSheetThickness ?? m.meta?.sheetThickness ?? null
  if (t == null || sel.thicknessMm === t) return null
  return { materialThickness: sel.thicknessMm, sheetThickness: t }
}
function canConfirmMaterial(m) {
  return selectedMaterialFor(m) != null
}
function onMaterialConfirm(m) {
  const sel = selectedMaterialFor(m)
  if (sel) emit('material-choice', { label: sel.label, thicknessMm: sel.thicknessMm })
}
function onModifyMaterial(m) {
  const id = m.meta?.promptMessageId
  if (id) emit('modify-material', { promptMessageId: id })
}

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
    :awaiting-confirm="awaitingConfirm"
    :has-items="hasBoxes"
    :accepted-extensions="['.dxf', '.3dm', '.dwg']"
    :is-custom-message="isCustomMessage"
    empty-hint="Upload a DXF, DWG, or 3dm file or drag and drop it here to start processing."
    composer-placeholder="…"
    @send-text="emit('send-text', $event)"
    @attach-file="emit('attach-file', $event)"
    @attach-error="emit('attach-error', $event)"
    @confirm-choice="emit('confirm-choice', $event)"
    @clear-all="emit('clear-all')"
  >
    <template #message="{ message }">
      <div class="bubble" :class="bubbleExtraClass(message)">
        <template v-if="message.kind === 'nesting-result'">
          <p class="bubble-text">
            {{ nestingResultSummary(message) }}
            <template v-if="!message.meta?.leftoverComplete && message.meta?.unassignedCount > 0">
              <br>
              <span v-if="message.meta.unassignedIdsText" class="nesting-unassigned-ids">{{ message.meta.unassignedIdsText }}</span>
              <template v-if="message.meta.unassignedReasons?.length">
                <br>
                <span
                  v-for="(reason, i) in message.meta.unassignedReasons"
                  :key="`${reason}-${i}`"
                  class="nesting-unassigned-reason"
                >{{ reason }}<br></span>
              </template>
              <span class="nesting-unassigned-hint">
                Unassigned parts will now show <span class="legend-part-red">red</span> in app viewer.
              </span>
            </template>
          </p>
          <div v-if="!message.meta?.superseded" class="nesting-result-actions">
            <button type="button" class="btn-show-nesting-result" @click="emit('show-nesting-result')">
              {{ message.meta?.leftoverComplete ? 'Show full nesting result' : 'Show nesting result' }}
            </button>
          </div>
        </template>

        <template v-else-if="message.kind === 'text-position-select'">
          <p class="bubble-text">
            {{ message.content }}
            <template v-if="!isActiveTextPositionSelect(message) && selectedTextPositionFor(message)">
              <br><span class="text-position-choice-value">{{ selectedTextPositionFor(message) }}</span>
            </template>
          </p>
          <div v-if="isActiveTextPositionSelect(message)" class="text-position-select-actions">
            <select
              class="text-position-select"
              :value="selectedTextPositionFor(message)"
              @change="onTextPositionSelectChange(message, $event)"
            >
              <option v-for="opt in TEXT_POSITION_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
            <button type="button" @click="onTextPositionContinue(message)">Continue</button>
          </div>
        </template>

        <template v-else-if="message.kind === 'sheet-size-select'">
          <p class="bubble-text">{{ message.content }}</p>
          <div v-if="isActiveSheetSizeSelect(message)" class="sheet-size-select-actions">
            <div class="sheet-size-row">
              <input
                type="number"
                class="sheet-size-input"
                min="0"
                step="any"
                inputmode="decimal"
                :value="sheetSizeDraftFor(message).sheetX"
                aria-label="Sheet width mm"
                @input="updateSheetSizeDraft(message, 'sheetX', $event.target.value)"
              />
              <span class="sheet-size-label">mm (X)</span>
            </div>
            <div class="sheet-size-row">
              <input
                type="number"
                class="sheet-size-input"
                min="0"
                step="any"
                inputmode="decimal"
                :value="sheetSizeDraftFor(message).sheetY"
                aria-label="Sheet height mm"
                @input="updateSheetSizeDraft(message, 'sheetY', $event.target.value)"
              />
              <span class="sheet-size-label">mm (Y)</span>
            </div>
            <div class="sheet-size-row">
              <input
                type="number"
                class="sheet-size-input"
                min="0"
                step="any"
                inputmode="decimal"
                :value="sheetSizeDraftFor(message).sheetThickness"
                aria-label="Sheet thickness mm"
                @input="updateSheetSizeDraft(message, 'sheetThickness', $event.target.value)"
              />
              <span class="sheet-size-label">mm (thickness)</span>
            </div>
            <p v-if="sheetSizeOverLimit(message)" class="sheet-size-warning">
              You are exceeding the available maximum plate size. The maximum is 5000 mm for both X and Y.
            </p>
            <button type="button" :disabled="!canConfirmSheetSize(message)" @click="onSheetSizeConfirm(message)">
              Confirm
            </button>
          </div>
        </template>

        <template v-else-if="message.meta?.sheetSizeConfirm">
          <p class="bubble-text">{{ message.content }}</p>
          <button
            v-if="message.id === activeSheetSizeConfirmId"
            type="button"
            class="btn-sheet-size-modify"
            @click="onModifySheetSize(message)"
          >
            Modify
          </button>
        </template>

        <template v-else-if="message.kind === 'material-select'">
          <p class="bubble-text">{{ message.content }}</p>
          <div v-if="isActiveMaterialSelect(message)" class="sheet-size-select-actions">
            <select
              class="material-select"
              :value="materialDraftFor(message)"
              aria-label="Material"
              @change="updateMaterialDraft(message, $event.target.value)"
            >
              <option value="" disabled>Select material…</option>
              <option v-for="mat in PLACEHOLDER_MATERIALS" :key="mat.label" :value="mat.label">
                {{ mat.label }} ({{ mat.thicknessMm }} mm)
              </option>
            </select>
            <p v-if="materialThicknessMismatch(message)" class="sheet-size-warning">
              The thickness of the chosen material differs from the chosen sheet thickness
              ({{ materialThicknessMismatch(message).materialThickness }} vs
              {{ materialThicknessMismatch(message).sheetThickness }} mm).
              Please ensure this is correct before proceeding.
            </p>
            <button type="button" :disabled="!canConfirmMaterial(message)" @click="onMaterialConfirm(message)">
              Confirm
            </button>
          </div>
        </template>

        <template v-else-if="message.meta?.materialConfirm">
          <p class="bubble-text">{{ message.content }}</p>
          <button
            v-if="message.id === activeMaterialConfirmId"
            type="button"
            class="btn-sheet-size-modify"
            @click="onModifyMaterial(message)"
          >
            Modify
          </button>
        </template>

        <template v-else-if="message.meta?.showExportAssociated && message.id === activeExportAssociatedMessageId">
          <p class="bubble-text">{{ message.content }}</p>
          <div class="confirm-actions">
            <button type="button" :disabled="busy" @click="emit('export-associated')">
              Export associated parts
            </button>
          </div>
        </template>

        <template v-else-if="message.kind === 'result' && message.meta?.legend">
          <p class="bubble-text">
            {{ message.content }}<br><br>
            <template v-for="m in message.meta.legend.materials" :key="m.label">
              - <span :class="'legend-part-' + m.color">{{ m.label }}</span>:
              {{ m.count }} {{ m.count === 1 ? 'curve' : 'curves' }}<br>
            </template>
            <template v-if="message.meta.legend.red">
              - <span class="legend-part-red">Missing/Faulty metadata</span>
              ({{ message.meta.legend.red }})<br>
            </template>
          </p>
        </template>

        <template v-else-if="message.meta?.greenHint">
          <p class="bubble-text">
            Use Output view with <strong>Correct parts</strong> / <strong>Incorrect parts</strong>
            to see metadata status
            (<span class="legend-part-green">green</span> = complete,
            <span class="legend-part-red">red</span> = missing).
          </p>
        </template>

        <template v-else-if="message.meta?.missingSerialCount != null">
          <p class="bubble-text">
            <span class="legend-part-red">
              {{ message.meta.missingSerialCount }}
              {{ message.meta.missingSerialCount === 1 ? 'element is' : 'elements are' }}
            </span>
            missing name (Name).
          </p>
        </template>

        <template v-else-if="message.meta?.missingMaterialCount != null">
          <p class="bubble-text">
            <span class="legend-part-red">
              {{ message.meta.missingMaterialCount }}
              {{ message.meta.missingMaterialCount === 1 ? 'element is' : 'elements are' }}
            </span>
            missing material (Material).
          </p>
        </template>

        <template v-else-if="message.meta?.missingAnzCount != null">
          <p class="bubble-text">
            <span class="legend-part-red">
              {{ message.meta.missingAnzCount }}
              {{ message.meta.missingAnzCount === 1 ? 'element is' : 'elements are' }}
            </span>
            missing quantity (Amount).
          </p>
        </template>

        <template v-else-if="message.meta?.inspectUnsolvedCount != null">
          <p class="bubble-text">
            Assigned metadata to {{ message.meta.inspectSolvedCount }}
            {{ message.meta.inspectSolvedCount === 1 ? 'part' : 'parts' }}.
            <template v-if="message.meta.inspectUnsolvedCount > 0">
              <span class="legend-part-red">
                {{ message.meta.inspectUnsolvedCount }}
                {{ message.meta.inspectUnsolvedCount === 1 ? 'part still has' : 'parts still have' }}
              </span>
              missing metadata.
            </template>
          </p>
        </template>

        <template v-else>
          <p class="bubble-text">{{ message.content }}</p>
        </template>
      </div>
    </template>

    <template v-if="canStartNesting && !activeSheetSizeSelectId && !activeMaterialSelectId" #above-composer>
      <div class="bubble bubble-nesting" :class="{ 'bubble-nesting--modified': nestingNeedsRerun }">
        <p class="bubble-text">{{ nestingButtonPrompt }}</p>
        <button
          type="button"
          class="btn-nesting"
          :class="{ 'btn-nesting--modified': nestingNeedsRerun }"
          :disabled="busy"
          @click="emit('start-nesting')"
        >
          Nest
        </button>
      </div>
    </template>
  </SharedChatPanel>
</template>

<style scoped>
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
.btn-nesting--modified {
  background: var(--color-warning-emphasis);
  border-color: var(--color-warning-emphasis);
}
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
.nesting-unassigned-reason {
  display: inline-block;
  margin-top: 0.2rem;
  font-size: 0.85em;
  color: var(--color-text-muted);
}
.nesting-unassigned-hint {
  display: inline-block;
  margin-top: 0.45rem;
  font-size: 0.85em;
  color: var(--color-text-muted);
  font-style: italic;
}

.text-position-select-actions {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-top: 0.45rem;
}
.text-position-select {
  width: 100%;
  padding: 0.25rem 0.35rem;
  font-size: 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
}
.text-position-select-actions button {
  align-self: flex-start;
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  cursor: pointer;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
}
.text-position-choice-value {
  font-style: italic;
  color: var(--color-text-muted);
  text-transform: capitalize;
}

.bubble-sheet-size-select { background: var(--color-accent-bg); color: var(--color-text-summary); }
.bubble-sheet-size-select--leftover {
  background: var(--color-warning-bg);
  border: 1px solid var(--color-warning-emphasis);
}
.bubble-material-select { background: var(--color-accent-bg); color: var(--color-text-summary); }
.bubble-sheet-size-confirm,
.bubble-material-confirm {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  background: var(--color-surface-hover);
  color: var(--color-text-summary);
}
.bubble-sheet-size-confirm .bubble-text,
.bubble-material-confirm .bubble-text { flex: 1; min-width: 0; }

.btn-sheet-size-modify {
  flex-shrink: 0;
  padding: 0.2rem 0.45rem;
  font-size: 0.72rem;
  cursor: pointer;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
}
.btn-sheet-size-modify:hover {
  background: var(--color-result-bg);
  border-color: var(--color-neutral-edited-accent);
}

.sheet-size-select-actions {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-top: 0.45rem;
}
.sheet-size-row { display: flex; align-items: center; gap: 0.4rem; }
.sheet-size-input {
  flex: 1;
  min-width: 0;
  padding: 0.25rem 0.35rem;
  font-size: 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
}
.sheet-size-label { flex-shrink: 0; font-size: 0.75rem; color: var(--color-text-muted); }
.sheet-size-warning {
  margin: 0;
  padding: 0.35rem 0.45rem;
  font-size: 0.72rem;
  line-height: 1.35;
  color: var(--color-warning-emphasis);
  background: var(--color-warning-bg);
  border-radius: 4px;
}
.sheet-size-select-actions button {
  align-self: flex-start;
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  cursor: pointer;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
}
.sheet-size-select-actions button:disabled { opacity: 0.5; cursor: not-allowed; }
.material-select {
  width: 100%;
  padding: 0.25rem 0.35rem;
  font-size: 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
}

.bubble-text { margin: 0; white-space: pre-line; }
.bubble-text-position-select { background: var(--color-accent-bg); color: var(--color-text-summary); }
.confirm-actions { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.45rem; }
.confirm-actions button {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  cursor: pointer;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
  text-transform: capitalize;
}
</style>
