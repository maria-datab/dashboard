<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import DownloadFileNamingPanel from './DownloadFileNamingPanelComponent.vue'
import DXFViewer from './DXFViewerComponent.vue'
import { formatUnassignedIdsDisplay } from '../features/shared/unassignedDisplay.js'
import { apiUrl } from '../scripts/env.js'

const props = defineProps({
  open: { type: Boolean, default: false },
  jobId: { type: String, default: null },
  partCount: { type: Number, default: 0 },
  nestedCount: { type: Number, default: 0 },
  unassignedCount: { type: Number, default: 0 },
  unassignedIds: { type: Array, default: () => [] },
  unassignedReasons: { type: Array, default: () => [] },
  hasUnassignedDxf: { type: Boolean, default: false },
  dxfText: { type: String, default: '' },
  boundaries: { type: Array, default: () => [] },
  blockInserts: { type: Array, default: () => [] },
  sheetX: { type: Number, default: null },
  sheetY: { type: Number, default: null },
  sheetThickness: { type: Number, default: null },
  defaultMaterial: { type: String, default: '' },
  leftoverJobId: { type: String, default: null },
  leftoverDxfText: { type: String, default: '' },
  leftoverBoundaries: { type: Array, default: () => [] },
  leftoverBlockInserts: { type: Array, default: () => [] },
  leftoverSheetX: { type: Number, default: null },
  leftoverSheetY: { type: Number, default: null },
  leftoverSheetThickness: { type: Number, default: null },
})

const emit = defineEmits(['close', 'nest-unassigned'])
const viewerRef = ref(null)
const activeTab = ref('assigned')

const hasLeftoverNest = computed(() => Boolean(props.leftoverJobId && props.leftoverDxfText))
const showingLeftover = computed(() => hasLeftoverNest.value && activeTab.value === 'unassigned')

const downloadZipLabel = computed(() => {
  if (!hasLeftoverNest.value) return 'Download ZIP'
  return activeTab.value === 'unassigned' ? 'Download ZIP (B)' : 'Download ZIP (A)'
})

const activeJobId = computed(() =>
  showingLeftover.value ? props.leftoverJobId : props.jobId,
)
const activeDxfText = computed(() =>
  showingLeftover.value ? props.leftoverDxfText : props.dxfText,
)
const activeBoundaries = computed(() =>
  showingLeftover.value ? props.leftoverBoundaries : props.boundaries,
)
const activeBlockInserts = computed(() =>
  showingLeftover.value ? props.leftoverBlockInserts : props.blockInserts,
)
const activeSheetX = computed(() =>
  showingLeftover.value ? props.leftoverSheetX : props.sheetX,
)
const activeSheetY = computed(() =>
  showingLeftover.value ? props.leftoverSheetY : props.sheetY,
)
const activeSheetThickness = computed(() =>
  showingLeftover.value ? props.leftoverSheetThickness : props.sheetThickness,
)

const effectiveNestedCount = computed(() => props.nestedCount || props.partCount)

const modalTitle = computed(() => {
  if (hasLeftoverNest.value) {
    const previouslyUnassigned = props.unassignedCount
    const previouslyLabel = previouslyUnassigned === 1 ? 'part' : 'parts'
    return `Nesting complete — ${effectiveNestedCount.value} nested + ${previouslyUnassigned} previously unassigned ${previouslyLabel} nested`
  }
  if (props.unassignedCount > 0) {
    return `Nesting complete — ${effectiveNestedCount.value} nested, ${props.unassignedCount} not nested`
  }
  return `Nesting complete — ${props.partCount} part${props.partCount === 1 ? '' : 's'}`
})

const unassignedIdsText = computed(() => formatUnassignedIdsDisplay(props.unassignedIds))

const DOWNLOAD_DXF_HINT =
  'Configure layer visibility in the viewer to determine the content of each DXF and the merged PDF inside the downloaded ZIP.'

const namingPanelOpen = ref(false)
const pendingDownloadKind = ref('nesting')
const pendingHiddenLayers = ref([])

function openNamingPanel(kind, hiddenLayers = []) {
  pendingDownloadKind.value = kind
  pendingHiddenLayers.value = hiddenLayers
  namingPanelOpen.value = true
}

function closeNamingPanel() {
  namingPanelOpen.value = false
  pendingHiddenLayers.value = []
}

function triggerDownload(filename) {
  const hidden = pendingHiddenLayers.value
  const filenameParam = `filename=${encodeURIComponent(filename)}`
  const link = document.createElement('a')
  if (pendingDownloadKind.value === 'unassigned') {
    link.href = apiUrl(`jobs/${props.jobId}/download/unassigned?${filenameParam}`)
  } else if (hidden.length) {
    link.href = apiUrl(`jobs/${activeJobId.value}/download?excludeLayers=${hidden.map(encodeURIComponent).join(',')}&${filenameParam}`)
  } else {
    link.href = apiUrl(`jobs/${activeJobId.value}/download?${filenameParam}`)
  }
  link.click()
}

function onNamingPanelConfirm({ filename }) {
  triggerDownload(filename)
  closeNamingPanel()
}

function onUnassignedDownloadClick() {
  openNamingPanel('unassigned')
}

function onNestUnassignedClick() {
  emit('nest-unassigned')
}

function onDownloadClick() {
  const hidden = viewerRef.value?.getHiddenLayers?.() ?? []
  const all = viewerRef.value?.getLayerNames?.() ?? []
  if (all.length && all.every((name) => hidden.includes(name))) {
    window.alert('No layers are visible. Show at least one layer to download.')
    return
  }
  openNamingPanel('nesting', hidden)
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) activeTab.value = 'assigned'
  },
)

watch(
  () => [props.open, activeDxfText.value, activeTab.value],
  async ([isOpen]) => {
    if (!isOpen || !activeDxfText.value) return
    await nextTick()
    requestAnimationFrame(() => {
      viewerRef.value?.resize?.()
    })
  },
)
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="nesting-modal" role="dialog" aria-modal="true" aria-labelledby="nesting-modal-title">
      <div class="nesting-modal__backdrop" @click="emit('close')" />
      <div class="nesting-modal__panel">
        <header class="nesting-modal__header">
          <h2 id="nesting-modal-title" class="nesting-modal__title">
            {{ modalTitle }}
          </h2>
          <button type="button" class="nesting-modal__close" aria-label="Close" @click="emit('close')">
            ×
          </button>
        </header>

        <div v-if="hasLeftoverNest" class="nesting-modal__tabs" role="tablist">
          <button
            type="button"
            role="tab"
            class="nesting-modal__tab"
            :class="{ 'nesting-modal__tab--active': activeTab === 'assigned' }"
            :aria-selected="activeTab === 'assigned'"
            @click="activeTab = 'assigned'"
          >
            Assigned parts nesting (A)
          </button>
          <button
            type="button"
            role="tab"
            class="nesting-modal__tab"
            :class="{ 'nesting-modal__tab--active': activeTab === 'unassigned' }"
            :aria-selected="activeTab === 'unassigned'"
            @click="activeTab = 'unassigned'"
          >
            Unassigned parts nesting (B)
          </button>
        </div>

        <div class="nesting-modal__viewer">
          <div
            v-if="unassignedCount > 0 && !hasLeftoverNest"
            class="nesting-modal__unassigned-panel"
            role="status"
            aria-live="polite"
          >
            <p class="nesting-modal__unassigned-summary">
              {{ effectiveNestedCount }} nested, {{ unassignedCount }} not nested
            </p>
            <p v-if="unassignedIdsText" class="nesting-modal__unassigned-ids">
              {{ unassignedIdsText }}
            </p>
            <p
              v-for="(reason, index) in unassignedReasons"
              :key="`${reason}-${index}`"
              class="nesting-modal__unassigned-reason"
            >
              {{ reason }}
            </p>
            <p class="nesting-modal__unassigned-hint">
              Unassigned parts will now show <span class="legend-part-red">red</span> in app viewer.
            </p>
          </div>
          <DXFViewer
            v-if="activeDxfText"
            ref="viewerRef"
            :key="activeDxfText"
            :dxf-text="activeDxfText"
            :boundaries="activeBoundaries"
            :block-inserts="activeBlockInserts"
            view-mode="output"
            :click-for-properties="false"
            :show-properties-panel="false"
            :selection-enabled="false"
            :show-metadata-colors="false"
          />
          <p v-else class="nesting-modal__viewer-empty">Preview unavailable.</p>
        </div>

        <footer v-if="activeJobId || jobId" class="nesting-modal__footer">
          <button
            v-if="activeJobId"
            type="button"
            class="nesting-modal__download"
            :title="DOWNLOAD_DXF_HINT"
            @click="onDownloadClick"
          >
            {{ downloadZipLabel }}
          </button>
          <button
            v-if="unassignedCount > 0 && hasUnassignedDxf"
            type="button"
            class="nesting-modal__download nesting-modal__download--unassigned-3d"
            @click="onUnassignedDownloadClick"
          >
            Download unassigned parts (3d)
          </button>
          <button
            v-if="unassignedCount > 0 && hasUnassignedDxf && !hasLeftoverNest"
            type="button"
            class="nesting-modal__download"
            title="Reprocess unassigned parts with a different sheet size."
            @click="onNestUnassignedClick"
          >
            Nest unassigned parts
          </button>
        </footer>
      </div>
    </div>

    <DownloadFileNamingPanel
      :open="namingPanelOpen"
      :download-kind="pendingDownloadKind"
      :sheet-x="pendingDownloadKind === 'unassigned' ? sheetX : activeSheetX"
      :sheet-y="pendingDownloadKind === 'unassigned' ? sheetY : activeSheetY"
      :sheet-thickness="pendingDownloadKind === 'unassigned' ? sheetThickness : activeSheetThickness"
      :default-material="defaultMaterial"
      @close="closeNamingPanel"
      @confirm="onNamingPanelConfirm"
    />
  </Teleport>
</template>

<style scoped>
.nesting-modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.nesting-modal__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
}

.nesting-modal__panel {
  position: relative;
  display: flex;
  flex-direction: column;
  width: min(1280px, 96vw);
  height: 92vh;
  max-height: 92vh;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.nesting-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--color-border);
}

.nesting-modal__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-summary);
}

.nesting-modal__close {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  padding: 0;
  font-size: 1.4rem;
  line-height: 1;
  cursor: pointer;
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  border-radius: 4px;
}

.nesting-modal__close:hover {
  color: var(--color-text-summary);
  background: var(--color-surface-hover);
}

.nesting-modal__tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--color-border);
}

.nesting-modal__tab {
  flex: 1;
  padding: 0.55rem 0.75rem;
  font-size: 0.8rem;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}

.nesting-modal__tab:hover {
  color: var(--color-text-summary);
  background: var(--color-surface-hover);
}

.nesting-modal__tab--active {
  color: var(--color-text-summary);
  border-bottom-color: var(--color-accent);
}

.nesting-modal__viewer {
  position: relative;
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  background: #fafafa;
}

.nesting-modal__unassigned-panel {
  position: absolute;
  top: 0.75rem;
  left: 0.75rem;
  z-index: 2;
  max-width: 280px;
  padding: 0.65rem 0.75rem;
  font-size: 0.8rem;
  line-height: 1.4;
  color: var(--color-text-summary);
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  pointer-events: none;
}

.nesting-modal__unassigned-summary {
  margin: 0;
  font-weight: 600;
}

.nesting-modal__unassigned-ids {
  margin: 0.35rem 0 0;
}

.nesting-modal__unassigned-reason {
  margin: 0.2rem 0 0;
  font-size: 0.92em;
  color: var(--color-text-muted);
}

.nesting-modal__unassigned-hint {
  margin: 0.45rem 0 0;
  font-size: 0.92em;
  font-style: italic;
  color: var(--color-text-muted);
}

.nesting-modal__viewer :deep(.viewer-shell) {
  flex: 1;
  min-height: 0;
  width: 100%;
  height: 100%;
}

.nesting-modal__viewer-empty {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.nesting-modal__footer {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--color-border);
}

.nesting-modal__download {
  display: inline-block;
  padding: 0.45rem 0.75rem;
  font-size: 0.8rem;
  font-weight: 600;
  font-family: inherit;
  text-decoration: none;
  cursor: pointer;
  color: var(--color-surface);
  background: var(--color-accent);
  border: 1px solid var(--color-accent);
  border-radius: 4px;
  transition: background 0.15s ease;
}

.nesting-modal__download:hover {
  background: #163d6e;
}

.nesting-modal__download--unassigned-3d {
  background: var(--color-salmon);
  border-color: var(--color-salmon);
}

.nesting-modal__download--unassigned-3d:hover {
  background: var(--color-salmon-hover);
  border-color: var(--color-salmon-hover);
}
</style>
