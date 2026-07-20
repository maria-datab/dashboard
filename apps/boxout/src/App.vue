<script setup>
/**
 * Root layout: sidebar chat + variation table + 3D solve viewer.
 */
import MobileToggle from '@dashboard/shared/components/MobileToggle.vue'
import AppSidebar from './components/AppSidebar.vue'
import ThreeDViewer from './components/3DViewer.vue'
import CsvPreviewComponent from './components/CsvPreviewComponent.vue'
import ParallelCoordinatesComponent from './components/ParallelCoordinatesComponent.vue'
import NestingPanelCountComponent from './components/NestingPanelCountComponent.vue'
import NestingCurvePreviewComponent from './components/NestingCurvePreviewComponent.vue'
import SendResultsComponent from './components/SendResultsComponent.vue'
import { useApp } from './features/useApp.js'
import './styles/app.css'

const {
  inputLists,
  csvSourceLists,
  emptyCellKeys,
  variationNames,
  quantities,
  selectedVariationIndex,
  solveRequestId,
  csvAnalyzing,
  csvParamCount,
  pendingFileImport,
  chatMessages,
  solveState,
  nestingPreviewOpen,
  sendResultsPhase,
  nestingGeometryPayload,
  nestingPreviewReady,
  onToggleNestingPreview,
  onSolveStateUpdate,
  finishFileImport,
  processChatFile,
  onAttachError,
  processChatText,
  onClearAll,
  onApplyEditedLists,
  onDeleteRow,
} = useApp()
</script>

<template>
  <div class="app">
    <AppSidebar
      :messages="chatMessages"
      :busy="csvAnalyzing"
      :awaiting-confirm="!!pendingFileImport"
      :has-boxes="csvParamCount > 0"
      @send-text="processChatText"
      @attach-file="processChatFile"
      @attach-error="onAttachError"
      @confirm-choice="finishFileImport"
      @clear-all="onClearAll"
    />
    <div class="main">
      <div
        class="center-panel"
        :class="{ 'center-panel--nesting-preview': nestingPreviewOpen }"
      >
        <section class="mobile-table">
          <CsvPreviewComponent
            v-model:active-variation-index="selectedVariationIndex"
            :input-lists="inputLists"
            :csv-source-lists="csvSourceLists"
            :empty-cell-keys="emptyCellKeys"
            :variation-names="variationNames"
            :quantities="quantities"
            :solve="solveState"
            @apply-lists="onApplyEditedLists"
            @delete-row="onDeleteRow"
          />
        </section>
        <MobileToggle
          group="mobile-pane"
          :tabs="[
            { id: 'mobile-chat', label: 'Agent' },
            { id: 'mobile-3d', label: '3D', default: true },
            { id: 'mobile-plot', label: 'Plot' },
            { id: 'mobile-nesting', label: 'Nesting', disabled: !nestingPreviewReady },
          ]"
        />
        <section class="mobile-viewer">
          <div class="parallel-slot">
            <ParallelCoordinatesComponent
              v-model:selected-index="selectedVariationIndex"
              :input-lists="inputLists"
              :variation-names="variationNames"
            />
          </div>
          <NestingCurvePreviewComponent
            v-if="nestingPreviewReady"
            :geometry-payload="nestingGeometryPayload"
          />
          <NestingPanelCountComponent
            :per-box-nesting="solveState.perBoxNesting"
            :full-set-nesting="solveState.fullSetNesting"
            :solving="solveState.isSolving"
            :preview-disabled="!nestingPreviewReady"
            @toggle="onToggleNestingPreview"
            @send-results="sendResultsPhase = 'confirm'"
          />
          <div v-if="nestingPreviewReady" class="mobile-send-results">
            <SendResultsComponent
              :disabled="!nestingPreviewReady"
              @click="sendResultsPhase = 'confirm'"
            />
          </div>
        </section>
      </div>
      <ThreeDViewer
        :input-lists="inputLists"
        :variation-names="variationNames"
        :quantities="quantities"
        :selected-variation-index="selectedVariationIndex"
        :solve-request-id="solveRequestId"
        @update:solve-state="onSolveStateUpdate"
      />
    </div>
    <div
      v-if="sendResultsPhase"
      class="send-results-overlay"
      @click.self="sendResultsPhase === 'sent' && (sendResultsPhase = null)"
    >
      <div class="send-results-dialog" @click.stop>
        <template v-if="sendResultsPhase === 'confirm'">
          <p class="send-results-dialog__text">Send data to production?</p>
          <div class="send-results-dialog__actions">
            <button type="button" @click="sendResultsPhase = 'sent'">Yes</button>
            <button type="button" @click="sendResultsPhase = null">Go back to editing</button>
          </div>
        </template>
        <p v-else class="send-results-dialog__text">Data sent</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app {
  display: flex;
  height: 100vh;
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: row;
}

.center-panel {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
  color: #222;
}

.mobile-table,
.mobile-viewer {
  display: contents;
}

.parallel-slot {
  flex: 0 0 25%;
  min-height: 0;
  overflow: hidden;
  border-bottom: 1px solid #ddd;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  order: -1;
}

.center-panel--nesting-preview :deep(.csv-preview) {
  flex: 0 0 50%;
  min-height: 0;
}

:deep(.nesting-panel-bar) {
  flex-shrink: 0;
  border-top: 1px solid #ddd;
  background: #f5f5f5;
  padding: 1.25rem 0.65rem 1.6rem;
  order: 1;
}

.center-panel--nesting-preview .nesting-curve-preview {
  order: 0;
  flex: 1;
  min-height: 0;
}

.send-results-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(51, 51, 51, 0.75);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

.send-results-dialog {
  background: var(--color-surface);
  border-radius: 6px;
  padding: 1rem 1.25rem;
  max-width: 18rem;
  text-align: center;
}

.send-results-dialog__text {
  margin: 0;
  font-size: 0.85rem;
  color: var(--color-text-summary);
}

.send-results-dialog__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.send-results-dialog__actions button {
  padding: 0.35rem 0.65rem;
  font-size: 0.8rem;
  cursor: pointer;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
}
</style>
