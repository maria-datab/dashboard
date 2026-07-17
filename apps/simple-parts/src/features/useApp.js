import { computed, watch } from 'vue'
import { parseDxf } from 'dxf-vuer'
import { createAppState, DEFAULT_SHEET_SIZE, METADATA_MODIFIED_NEST_PROMPT } from './shared/createAppState.js'
import { createMessaging, safeFilename } from './shared/curveHelpers.js'
import { useChat } from './chat/useChat.js'
import { useMetadataPanel } from './metadata/useMetadataPanel.js'
import {
  buildMeshPartDescriptors,
} from './metadata/meshMetadataSelection.js'
import {
  applyMetadataByPartKeys,
  buildPartRegistry,
  effectivePartMeta,
  resolvePartByNr,
  listKnownPartNrs,
} from './metadata/partRegistry.js'
import { buildPartKeyMetadataOverrides } from './metadata/buildPartKeyMetadataOverrides.js'
import { seedPostNestMetadata, normalizeGhStringList, buildDescriptorBaseMetaFromGhLists } from './metadata/seedPostNestMetadata.js'
import { is3dDxf, dxfTextHasAcisSolid } from '../dxfDetection.js'
import { apiUrl } from '../scripts/env.js'
import {
  normalizeInputText,
  normalizeMeshes3d,
  normalizePreviewMeshes3d,
} from '../rhino3dmPreview.js'

import {
  formatUnassignedIdsDisplay,
  normalizeUnassignedReasons,
  resolveNestingCounts,
  resolveUnassignedPartIds,
  resolveUnassignedPartKeys,
} from './shared/unassignedDisplay.js'
import {
  resolveGeometryMode,
  resolveHopsGeometryModeInt,
  isPlain2dDxf,
} from './viewer/resolveGeometryMode.js'
import { useViewerRouting } from './viewer/useViewerRouting.js'

function buildNestingResultMessage(nestedCount, unassignedCount) {
  if (unassignedCount === 0) {
    return `Nesting complete — ${nestedCount} part${nestedCount === 1 ? '' : 's'}.`
  }
  return `Nesting complete — ${nestedCount} nested, ${unassignedCount} not nested.`
}

function buildLeftoverCompleteMessage(nestedCount, previouslyUnassignedCount) {
  const previouslyLabel = previouslyUnassignedCount === 1 ? 'part' : 'parts'
  return `Nesting complete — ${nestedCount} nested + ${previouslyUnassignedCount} previously unassigned ${previouslyLabel} nested`
}

function resetFileState(state) {
  state.selectedFile.value = null
  state.dxfText.value = null
  state.messages.value = []
  state.busy.value = false
  state.busyMessage.value = ''
  state.viewerBusy.value = false
  state.viewerBusyMessage.value = ''
  state.readyForNesting.value = false
  state.awaitingConfirm.value = false
  state.step.value = 'idle'
  state.metadataOverrides.value = {}
  state.modifiedHandles.value = []
  state.boundaries.value = []
  state.blockInserts.value = []
  state.schemeOutliers.value = []
  state.dxfInterpreted.value = false
  state.sourceType.value = 'dxf'
  state.geometryMode.value = null
  state.summonedPreview.value = null
  state.leftoverNestPreview.value = null
  state.showNestingModal.value = false
  state.setSummonPreviewTask(null)
  state.viewMode.value = 'input'
  state.meshPreview.value = null
  state.previewPartKeys.value = []
  state.meshPreviewPostInjectionNames.value = []
  state.meshPreviewPostInjectionAmount.value = []
  state.previewNotice.value = null
  state.annotationOverlayDxf.value = null
  state.activeSheetSizeSelectId.value = null
  state.activeSheetSizeConfirmId.value = null
  state.pendingSheetSize.value = null
  state.activeMaterialSelectId.value = null
  state.activeMaterialConfirmId.value = null
  state.pendingSheetMaterial.value = null
  state.sheetSizeModifiedSinceNest.value = false
  state.metadataModifiedSinceNest.value = false
  state.postNestMetadataEditing.value = false
  state.nestingViewerKey.value = 0
  state.inputPreviewMeshes.value = null
  state.inputPreviewPartKeys.value = null
  state.inputPreviewPostInjectionNames.value = null
  state.inputPreviewPostInjectionAmount.value = null
  state.inputPreviewAnnotationDxf.value = null
  state.lastHopsGeometryMode.value = null
  state.meshDescriptorBaseMeta.value = null
}

export function useApp() {
  const state = createAppState()
  const { pushMessage, FIELD_LABELS } = createMessaging(state)
  const { viewerClickForProperties, markModified: markModifiedBase, markModifiedPart } = useMetadataPanel(state)
  const {
    activeViewer,
    showNestingMeshView,
    showMeshPreview,
    showPreviewNotice,
  } = useViewerRouting(state)

  function syncGeometryMode(overrides = {}) {
    state.geometryMode.value = resolveGeometryMode({
      hopsGeometryMode: overrides.hopsGeometryMode ?? state.lastHopsGeometryMode.value,
      sourceType: state.sourceType.value,
      parsedDxf: state.parsedDxf.value,
      dxfText: state.dxfText.value,
    })
  }

  function hopsGeometryModeForUpload(override) {
    if (override === 0 || override === 1) return override
    return resolveHopsGeometryModeInt({
      sourceType: state.sourceType.value,
      geometryMode: state.geometryMode.value,
      parsedDxf: state.parsedDxf.value,
      dxfText: state.dxfText.value,
    })
  }

  const outputViewEnabled = computed(
    () => state.dxfInterpreted.value && (state.summonedPreview.value?.boundaries?.length ?? 0) > 0,
  )

  const meshPartDescriptors = computed(() =>
    buildMeshPartDescriptors(
      state.meshPreview.value?.length ?? 0,
      state.previewPartKeys.value,
      state.meshDescriptorBaseMeta.value ?? [],
    ),
  )

  const unassignedPartIdsForViewer = computed(() => {
    const preview = state.summonedPreview.value
    if (!preview) return []
    if (preview.unassignedPartKeys?.length) return preview.unassignedPartKeys
    if (!preview.unassignedIds?.length) return []
    return resolveUnassignedPartIds(preview.unassignedIds, meshPartDescriptors.value)
  })

  const nestingMeshPartDescriptors = computed(() => {
    const preview = state.summonedPreview.value
    const meshCount = Math.max(
      preview?.assignedMeshes3d?.length ?? 0,
      preview?.unassignedMeshes3d?.length ?? 0,
    )
    if (!meshCount) return []
    const partKeys = normalizeGhStringList(
      preview.initialPartKeys?.length ? preview.initialPartKeys : state.previewPartKeys.value,
    )
    const baseMeta = buildDescriptorBaseMetaFromGhLists({
      partKeys,
      postInjectionNames: preview.postInjectionNames ?? [],
      postInjectionAmount: preview.postInjectionAmount ?? [],
      meshCount,
    })
    return buildMeshPartDescriptors(meshCount, partKeys, baseMeta)
  })

  const registryMeshDescriptors = computed(() =>
    showNestingMeshView.value
      ? nestingMeshPartDescriptors.value
      : meshPartDescriptors.value,
  )

  const partRegistry = computed(() =>
    buildPartRegistry({
      meshPartDescriptors: registryMeshDescriptors.value,
      boundaries:
        state.viewMode.value === 'output' && state.summonedPreview.value
          ? state.summonedPreview.value.boundaries
          : [],
    }),
  )

  watch(outputViewEnabled, (enabled) => {
    if (!enabled && state.viewMode.value === 'output') state.viewMode.value = 'input'
  })

  function hasSheetSizePrompt() {
    return state.messages.value.some((m) => m.kind === 'sheet-size-select')
  }

  function hasMaterialPrompt() {
    return state.messages.value.some((m) => m.kind === 'material-select')
  }

  const hasMissingMat = computed(() =>
    partRegistry.value.some(
      (entry) => !effectivePartMeta(entry, state.metadataOverrides.value).mat,
    ),
  )

  function partKeysMissingMat() {
    return partRegistry.value
      .filter((entry) => !effectivePartMeta(entry, state.metadataOverrides.value).mat)
      .map((entry) => entry.partKey)
  }

  function partKeysForMaterialApply(previousLabel) {
    return partRegistry.value
      .filter((entry) => {
        const mat = effectivePartMeta(entry, state.metadataOverrides.value).mat
        if (!mat) return true
        if (previousLabel && mat === previousLabel) return true
        return false
      })
      .map((entry) => entry.partKey)
  }

  function countMissingMat() {
    return partKeysMissingMat().length
  }

  function promptMaterial() {
    if (state.summonedPreview.value?.dxfText) return
    if (!state.pendingSheetSize.value) return
    if (!hasMissingMat.value) return
    if (state.activeMaterialSelectId.value || hasMaterialPrompt()) return

    const missingCount = countMissingMat()
    const messageId = pushMessage(
      'assistant',
      'material-select',
      `${missingCount} ${missingCount === 1 ? 'part is' : 'parts are'} missing material. Choose a material for nesting:`,
      {
        missingCount,
        sheetThickness: state.pendingSheetSize.value.sheetThickness,
      },
    )
    state.activeMaterialSelectId.value = messageId
  }

  function promptSheetSize() {
    if (state.summonedPreview.value?.dxfText) return
    if (state.activeSheetSizeSelectId.value || hasSheetSizePrompt()) return

    const messageId = pushMessage(
      'assistant',
      'sheet-size-select',
      'What sheet size should be used for nesting?',
      { ...DEFAULT_SHEET_SIZE },
    )
    state.activeSheetSizeSelectId.value = messageId
  }

  watch(
    () => state.readyForNesting.value && !state.viewerBusy.value,
    (ready) => {
      if (ready) promptSheetSize()
    },
  )

  function setPreviewPartKeysFromHops(data) {
    state.previewPartKeys.value = normalizeGhStringList(data?.initialPartKeys)
  }

  function storeGhPostInjectionLists(data) {
    state.meshPreviewPostInjectionNames.value = normalizeGhStringList(data?.postInjectionNames)
    state.meshPreviewPostInjectionAmount.value = normalizeGhStringList(data?.postInjectionAmount)
  }

  function applyGhPostInjectionMetadata(data) {
    storeGhPostInjectionLists(data)
    setPreviewPartKeysFromHops(data)
    const meshCount = state.meshPreview.value?.length ?? 0
    const { metadataOverrides, meshDescriptorBaseMeta } = seedPostNestMetadata({
      partKeys: state.previewPartKeys.value,
      postInjectionNames: state.meshPreviewPostInjectionNames.value,
      postInjectionAmount: state.meshPreviewPostInjectionAmount.value,
      metadataOverrides: state.metadataOverrides.value,
      meshCount,
    })
    state.metadataOverrides.value = metadataOverrides
    state.meshDescriptorBaseMeta.value = meshDescriptorBaseMeta.length ? meshDescriptorBaseMeta : null
  }

  function updateCachedPostInjectionFromNest(data) {
    const names = normalizeGhStringList(data?.postInjectionNames)
    const amounts = normalizeGhStringList(data?.postInjectionAmount)
    if (names.length) state.inputPreviewPostInjectionNames.value = names
    if (amounts.length) state.inputPreviewPostInjectionAmount.value = amounts
    if (Array.isArray(data?.initialPartKeys) && data.initialPartKeys.length) {
      state.inputPreviewPartKeys.value = normalizeGhStringList(data.initialPartKeys)
    }
  }

  function previewProcessedLabel() {
    if (state.sourceType.value === '3dm') return '.3dm processed for visualization'
    if (state.geometryMode.value === '3d') return '3D DXF processed for visualization'
    return 'Processed for visualization'
  }

  async function applyMeshPreviewResult(data) {
    const rawMeshes3d = Array.isArray(data.meshes3d) ? data.meshes3d : null
    if (!rawMeshes3d?.length) return false

    const previewMeshes = await normalizePreviewMeshes3d(rawMeshes3d, data.initialPartKeys)
    const meshes3d = previewMeshes?.meshes?.length ? previewMeshes.meshes : null
    if (!meshes3d?.length) return false

    state.meshPreview.value = meshes3d
    setPreviewPartKeysFromHops(data)
    state.annotationOverlayDxf.value = normalizeInputText(data.inputText, data.inputTextPt)
    applyGhPostInjectionMetadata(data)
    cacheInputPreviewState()
    syncGeometryMode({ hopsGeometryMode: state.lastHopsGeometryMode.value })
    state.readyForNesting.value = true
    return true
  }

  async function applyHopsResult(data, { openModal = true } = {}) {
    if (!data.dxfText) {
      if (await applyMeshPreviewResult(data)) {
        pushMessage('assistant', 'text', previewProcessedLabel())
      }
      return
    }

    cacheInputPreviewState()
    updateCachedPostInjectionFromNest(data)

    const is2dNest = state.geometryMode.value === '2d'
    if (!is2dNest) {
      state.blockInserts.value = data.blockInserts ?? []
      state.schemeOutliers.value = data.schemeOutliers ?? []
      state.boundaries.value = data.boundaries ?? []
    }
    state.dxfInterpreted.value = true

    const unassignedReasons = normalizeUnassignedReasons(data.unassignedReasons)
    const nestAmounts = normalizeGhStringList(
      data.postInjectionAmount?.length
        ? data.postInjectionAmount
        : state.inputPreviewPostInjectionAmount.value ?? [],
    )
    const { nestedCount, unassignedCount, unassignedIds } = resolveNestingCounts(
      {
        ...data,
        postInjectionAmount: nestAmounts,
      },
      {
        normalizePartKeys: normalizeGhStringList,
        normalizeNames: normalizeGhStringList,
        normalizeAmounts: normalizeGhStringList,
        metadataOverrides: state.metadataOverrides.value,
      },
    )

    const nestPartKeys = state.inputPreviewPartKeys.value?.length
      ? state.inputPreviewPartKeys.value
      : normalizeGhStringList(data.initialPartKeys)
    const nestNames = state.inputPreviewPostInjectionNames.value?.length
      ? state.inputPreviewPostInjectionNames.value
      : normalizeGhStringList(data.postInjectionNames)
    const unassignedPartKeys = resolveUnassignedPartKeys(unassignedIds, nestPartKeys, {
      names: nestNames,
    })

    let assignedMeshes3d = null
    if (Array.isArray(data.assignedMeshes3d) && data.assignedMeshes3d.length) {
      const normalized = await normalizeMeshes3d(data.assignedMeshes3d)
      assignedMeshes3d = normalized.length ? normalized : null
    }

    let unassignedMeshes3d = null
    if (Array.isArray(data.unassignedMeshes3d) && data.unassignedMeshes3d.length) {
      const normalized = await normalizeMeshes3d(data.unassignedMeshes3d)
      unassignedMeshes3d = normalized.length ? normalized : null
    }

    const inputTextDxf = normalizeInputText(data.inputText, data.inputTextPt)

    state.meshPreview.value = null
    if (!is2dNest) {
      state.previewPartKeys.value = []
      state.annotationOverlayDxf.value = null
    }
    state.sheetSizeModifiedSinceNest.value = false
    state.metadataModifiedSinceNest.value = false
    state.postNestMetadataEditing.value = false
    state.meshDescriptorBaseMeta.value = null
    state.viewMode.value = 'input'
    state.nestingViewerKey.value += 1

    state.leftoverNestPreview.value = null
    state.summonedPreview.value = {
      dxfText: data.dxfText,
      boundaries: data.boundaries ?? [],
      blockInserts: data.blockInserts ?? [],
      schemeOutliers: data.schemeOutliers ?? [],
      jobId: data.jobId ?? null,
      initialPartKeys: normalizeGhStringList(data.initialPartKeys),
      postInjectionNames: normalizeGhStringList(data.postInjectionNames),
      postInjectionAmount: normalizeGhStringList(data.postInjectionAmount),
      partCount: nestedCount,
      nestedCount,
      unassignedCount,
      unassignedIds,
      unassignedPartKeys,
      unassignedReasons,
      assignedMeshes3d,
      unassignedMeshes3d,
      inputTextDxf,
      hasUnassignedDxf: Boolean(data.hasUnassignedDxf),
      sheetX: state.pendingSheetSize.value?.sheetX ?? null,
      sheetY: state.pendingSheetSize.value?.sheetY ?? null,
      sheetThickness: state.pendingSheetSize.value?.sheetThickness ?? null,
    }
    if (openModal) {
      trimNestingResultMessages()
      pushMessage(
        'assistant',
        'nesting-result',
        buildNestingResultMessage(nestedCount, unassignedCount),
        {
          jobId: data.jobId ?? null,
          nestedCount,
          unassignedCount,
          ...(unassignedCount > 0
            ? {
                unassignedIds,
                unassignedReasons,
                unassignedIdsText: formatUnassignedIdsDisplay(unassignedIds),
              }
            : {}),
        },
      )
      state.showNestingModal.value = true
    }
  }

  function cacheInputPreviewState() {
    if (state.annotationOverlayDxf.value) {
      state.inputPreviewAnnotationDxf.value = state.annotationOverlayDxf.value
    }
    if (state.previewPartKeys.value?.length) {
      state.inputPreviewPartKeys.value = [...state.previewPartKeys.value]
    }
    if (state.meshPreview.value?.length) {
      state.inputPreviewMeshes.value = state.meshPreview.value
      state.inputPreviewPostInjectionNames.value = [...state.meshPreviewPostInjectionNames.value]
      state.inputPreviewPostInjectionAmount.value = [...state.meshPreviewPostInjectionAmount.value]
    }
  }

  function restoreInputAnnotationOverlay(fallbackDxf = null) {
    if (state.inputPreviewAnnotationDxf.value) {
      state.annotationOverlayDxf.value = state.inputPreviewAnnotationDxf.value
      return true
    }
    if (fallbackDxf) {
      state.annotationOverlayDxf.value = fallbackDxf
      return true
    }
    return false
  }

  function restoreInputMeshPreview() {
    if (!state.inputPreviewMeshes.value?.length) return false
    state.meshPreview.value = state.inputPreviewMeshes.value
    if (state.inputPreviewPartKeys.value?.length) {
      state.previewPartKeys.value = [...state.inputPreviewPartKeys.value]
    }
    state.meshPreviewPostInjectionNames.value = state.inputPreviewPostInjectionNames.value ?? []
    state.meshPreviewPostInjectionAmount.value = state.inputPreviewPostInjectionAmount.value ?? []
    state.meshDescriptorBaseMeta.value = buildDescriptorBaseMetaFromGhLists({
      partKeys: state.previewPartKeys.value,
      postInjectionNames: state.meshPreviewPostInjectionNames.value,
      postInjectionAmount: state.meshPreviewPostInjectionAmount.value,
      meshCount: state.meshPreview.value?.length ?? 0,
    })
    return true
  }

  function restoreInputPreviewForMetadataEditing({ annotationFallback = null } = {}) {
    let restored = restoreInputMeshPreview()

    if (state.inputPreviewPartKeys.value?.length) {
      state.previewPartKeys.value = [...state.inputPreviewPartKeys.value]
      restored = true
    }

    if (restoreInputAnnotationOverlay(annotationFallback)) {
      restored = true
    }

    if (restored) {
      state.dxfInterpreted.value = Boolean(state.meshPreview.value?.length)
    }

    return restored
  }

  function applyPostNestMetadataSeed() {
    const partKeys =
      state.inputPreviewPartKeys.value?.length
        ? state.inputPreviewPartKeys.value
        : state.previewPartKeys.value
    const postInjectionNames =
      state.summonedPreview.value?.postInjectionNames?.length
        ? state.summonedPreview.value.postInjectionNames
        : state.inputPreviewPostInjectionNames.value
          ?? state.meshPreviewPostInjectionNames.value
    const postInjectionAmount =
      state.summonedPreview.value?.postInjectionAmount?.length
        ? state.summonedPreview.value.postInjectionAmount
        : state.inputPreviewPostInjectionAmount.value
          ?? state.meshPreviewPostInjectionAmount.value

    const { metadataOverrides, meshDescriptorBaseMeta } = seedPostNestMetadata({
      partKeys,
      postInjectionNames,
      postInjectionAmount,
      metadataOverrides: state.metadataOverrides.value,
      meshCount: state.meshPreview.value?.length ?? 0,
    })
    state.metadataOverrides.value = metadataOverrides
    state.meshDescriptorBaseMeta.value = meshDescriptorBaseMeta.length
      ? meshDescriptorBaseMeta
      : null
  }

  function trimNestingResultMessages() {
    state.messages.value = state.messages.value.filter((m) => m.kind !== 'nesting-result')
  }

  function invalidateNestResult({ reason }) {
    const hadNested = Boolean(state.summonedPreview.value?.dxfText)
    if (!hadNested) return

    if (reason === 'metadata') {
      state.metadataModifiedSinceNest.value = true
    } else if (reason === 'sheet-size') {
      state.sheetSizeModifiedSinceNest.value = true
    }

    resetNestingViewerState()
    trimNestingResultMessages()
  }

  function markModified(handle) {
    markModifiedBase(handle)
    if (state.summonedPreview.value?.dxfText) {
      invalidateNestResult({ reason: 'metadata' })
    }
  }

  function resetNestingViewerState() {
    state.summonedPreview.value = null
    state.leftoverNestPreview.value = null
    state.showNestingModal.value = false
    state.postNestMetadataEditing.value = false
    state.blockInserts.value = []
    state.schemeOutliers.value = []
    state.boundaries.value = []
    state.dxfInterpreted.value = false
    state.viewMode.value = 'input'
    restoreInputPreviewForMetadataEditing()
    state.nestingViewerKey.value += 1
  }

  function promptLeftoverSheetSize() {
    if (!state.summonedPreview.value?.hasUnassignedDxf) return
    if (state.leftoverNestPreview.value) return
    if (state.activeSheetSizeSelectId.value) return

    const size = state.summonedPreview.value
    const messageId = pushMessage(
      'assistant',
      'sheet-size-select',
      'Choose a sheet size for the unassigned parts:',
      {
        leftover: true,
        sheetX: size.sheetX ?? DEFAULT_SHEET_SIZE.sheetX,
        sheetY: size.sheetY ?? DEFAULT_SHEET_SIZE.sheetY,
        sheetThickness: size.sheetThickness ?? DEFAULT_SHEET_SIZE.sheetThickness,
      },
    )
    state.activeSheetSizeSelectId.value = messageId
  }

  async function nestUnassignedParts({ sheetX, sheetY, sheetThickness }) {
    const primaryJobId = state.summonedPreview.value?.jobId
    if (!primaryJobId) return

    state.busy.value = true
    state.busyMessage.value = 'Nesting unassigned parts…'
    try {
      const formData = new FormData()
      formData.append('sheetWidth', String(sheetX))
      formData.append('sheetHeight', String(sheetY))
      formData.append('sheetThickness', String(sheetThickness))
      const response = await fetch(apiUrl(`jobs/${primaryJobId}/nest-unassigned`), {
        method: 'POST',
        body: formData,
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        state.leftoverNestPreview.value = null
        pushMessage(
          'assistant',
          'error',
          data.error || 'Parts still could not be fit into sheet. Try a different sheet size.',
        )
        promptLeftoverSheetSize()
        return
      }
      state.leftoverNestPreview.value = {
        jobId: data.jobId ?? null,
        dxfText: data.dxfText,
        boundaries: data.boundaries ?? [],
        blockInserts: data.blockInserts ?? [],
        sheetX,
        sheetY,
        sheetThickness,
      }
      const preview = state.summonedPreview.value
      const nestedCount = preview?.nestedCount ?? preview?.partCount ?? 0
      const previouslyUnassignedCount = preview?.unassignedCount ?? 0
      for (const message of state.messages.value) {
        if (message.kind === 'nesting-result') {
          message.meta = { ...message.meta, superseded: true }
        }
      }
      pushMessage(
        'assistant',
        'nesting-result',
        buildLeftoverCompleteMessage(nestedCount, previouslyUnassignedCount),
        {
          leftoverComplete: true,
          nestedCount,
          previouslyUnassignedCount,
          jobId: data.jobId ?? null,
        },
      )
      state.showNestingModal.value = true
    } catch {
      state.leftoverNestPreview.value = null
      pushMessage('assistant', 'error', 'Parts still could not be fit into sheet. Try a different sheet size.')
      promptLeftoverSheetSize()
    } finally {
      state.busy.value = false
      state.busyMessage.value = ''
    }
  }

  function resolveNestPartKeys() {
    if (state.previewPartKeys.value?.length) return state.previewPartKeys.value
    if (state.inputPreviewPartKeys.value?.length) return state.inputPreviewPartKeys.value
    if (state.summonedPreview.value?.initialPartKeys?.length) {
      return state.summonedPreview.value.initialPartKeys
    }
    return []
  }

  function resolveNestMetadataDescriptors(partKeys) {
    const meshCount = Math.max(
      state.meshPreview.value?.length ?? 0,
      partKeys.length,
    )
    if (!meshCount) return meshPartDescriptors.value
    if (meshPartDescriptors.value.length >= meshCount) return meshPartDescriptors.value
    return buildMeshPartDescriptors(
      meshCount,
      partKeys,
      state.meshDescriptorBaseMeta.value ?? [],
    )
  }

  function buildNestMetadataPayload() {
    const partKeys = resolveNestPartKeys()
    return buildPartKeyMetadataOverrides({
      metadataOverrides: state.metadataOverrides.value,
      meshPartDescriptors: resolveNestMetadataDescriptors(partKeys),
      partKeys,
    })
  }

  async function solveUpload({
    openModal = true,
    runNesting = true,
    sheetWidth,
    sheetHeight,
    sheetThickness,
    busyMessage = 'Nesting…',
    useViewerBusy = false,
    hopsGeometryMode,
  } = {}) {
    if (!state.selectedFile.value) return
    while (state.getSummonPreviewTask()) {
      await state.getSummonPreviewTask()
    }

    const task = (async () => {
      if (useViewerBusy) {
        state.viewerBusy.value = true
        state.viewerBusyMessage.value = busyMessage
      } else {
        state.busy.value = true
        state.busyMessage.value = busyMessage
      }
      try {
        const formData = new FormData()
        formData.append('file', state.selectedFile.value)
        formData.append('run', runNesting ? 'true' : 'false')
        const resolvedHopsMode = hopsGeometryModeForUpload(hopsGeometryMode)
        state.lastHopsGeometryMode.value = resolvedHopsMode
        formData.append('geometryMode', String(resolvedHopsMode))
        if (runNesting) {
          formData.append('sheetWidth', String(Math.round(sheetWidth)))
          formData.append('sheetHeight', String(Math.round(sheetHeight)))
          formData.append('sheetThickness', String(Math.round(sheetThickness)))
          const overrides = buildNestMetadataPayload()
          formData.append('metadataOverrides', JSON.stringify(overrides))
          if (import.meta.env.DEV && Object.keys(overrides).length) {
            console.info(
              `Nest metadataOverrides: ${Object.keys(overrides).length} part(s)`,
              overrides,
            )
          }
        }
        const res = await fetch(apiUrl('hops/solve'), { method: 'POST', body: formData })
        if (!res.ok) {
          const errBody = await res.json().catch(() => ({}))
          pushMessage('assistant', 'error', errBody.error || `Hops solve failed (${res.status}).`)
          return
        }
        const data = await res.json()
        await applyHopsResult(data, { openModal })
      } catch (err) {
        console.error('Hops solve error:', err)
        const message = String(err?.message ?? err)
        const isNetwork =
          err instanceof TypeError && /failed to fetch|networkerror|load failed/i.test(message)
        pushMessage(
          'assistant',
          'error',
          isNetwork
            ? 'Could not reach the backend for Hops solve. Is Rhino Compute running?'
            : `Hops result processing failed: ${message}`,
        )
      } finally {
        if (useViewerBusy) {
          state.viewerBusy.value = false
          state.viewerBusyMessage.value = ''
        } else {
          state.busy.value = false
          state.busyMessage.value = ''
        }
      }
    })().finally(() => {
      state.setSummonPreviewTask(null)
    })

    state.setSummonPreviewTask(task)
    await task
  }

  function showPartByNr(partNr) {
    const registry = partRegistry.value
    const resolved = resolvePartByNr(registry, partNr, state.metadataOverrides.value)

    const meshSelectionActive =
      showMeshPreview.value
      || showNestingMeshView.value
      || (state.postNestMetadataEditing.value && Boolean(state.meshPreview.value?.length))

    if (resolved && meshSelectionActive && resolved.entry.selectionMeshId) {
      state.meshViewerRef.value?.selectPartByHandle(resolved.entry.selectionMeshId)
      return
    }

    if (resolved?.entry.selectionMeshId) {
      state.meshViewerRef.value?.selectPartByHandle(resolved.entry.selectionMeshId)
      return
    }

    const nrs = listKnownPartNrs(registry, state.metadataOverrides.value)
    const hint =
      meshSelectionActive && !registry.length
        ? state.postNestMetadataEditing.value
          ? `Couldn't find part ${partNr} in the mesh preview.`
          : `Couldn't find part ${partNr} in the mesh preview (metadata linking is not available until nesting).`
        : `Couldn't find part ${partNr}. Available: ${nrs.join(', ') || 'none'}.`
    pushMessage('assistant', 'text', hint)
  }

  const chat = useChat(state, {
    pushMessage,
    FIELD_LABELS,
    showPartByNr,
    onMetadataModified: () => invalidateNestResult({ reason: 'metadata' }),
    markModifiedPart,
    getPartRegistry: () => partRegistry.value,
  })

  async function run2dPreviewViaHops() {
    state.lastHopsGeometryMode.value = 0
    syncGeometryMode({ hopsGeometryMode: 0 })
    await solveUpload({
      openModal: false,
      runNesting: false,
      busyMessage: 'Computing visualization…',
      useViewerBusy: true,
      hopsGeometryMode: 0,
    })
    if (!state.meshPreview.value?.length) {
      state.previewNotice.value =
        "This file couldn't be previewed — Hops returned no geometry."
    }
  }

  async function onAttachFile(file) {
    const lower = file.name.toLowerCase()
    const is3dm = lower.endsWith('.3dm')
    const isDwg = lower.endsWith('.dwg')
    resetFileState(state)
    state.selectedFile.value = file
    state.sourceType.value = is3dm ? '3dm' : isDwg ? 'dwg' : 'dxf'
    state.dxfText.value = null

    let localDxfText = null
    let parsedLocalDxf = null
    if (!is3dm && !isDwg) {
      localDxfText = await file.text()
      parsedLocalDxf = parseDxf(localDxfText)
    }

    pushMessage('user', 'file', file.name)

    if (is3dm) {
      state.lastHopsGeometryMode.value = 1
      syncGeometryMode({ hopsGeometryMode: 1 })
      await solveUpload({
        openModal: false,
        runNesting: false,
        busyMessage: 'Computing 3D visualization…',
        useViewerBusy: true,
        hopsGeometryMode: 1,
      })
      if (!state.meshPreview.value) {
        state.previewNotice.value =
          "This .3dm couldn't be previewed — Hops returned no mesh data."
      } else {
        syncGeometryMode()
      }
      return
    }

    const plain2dDxf = isPlain2dDxf({
      sourceType: state.sourceType.value,
      parsedDxf: parsedLocalDxf,
      dxfText: localDxfText,
    })

    if (isDwg || plain2dDxf) {
      await run2dPreviewViaHops()
      return
    }

    state.dxfText.value = localDxfText

    const is3d = parsedLocalDxf != null && is3dDxf(parsedLocalDxf)
    const isAcis = dxfTextHasAcisSolid(localDxfText)

    if (is3d || isAcis) {
      state.lastHopsGeometryMode.value = 1
      syncGeometryMode({ hopsGeometryMode: 1 })
      await solveUpload({
        openModal: false,
        runNesting: false,
        busyMessage: 'Computing 3D visualization…',
        useViewerBusy: true,
        hopsGeometryMode: 1,
      })
      if (!state.meshPreview.value) {
        state.dxfText.value = null
        state.previewNotice.value =
          "This 3D file couldn't be previewed — Hops returned no mesh data."
      }
      syncGeometryMode()
    }
  }

  function onStartNesting() {
    const size = state.pendingSheetSize.value
    if (!size || state.summonedPreview.value?.dxfText) return
    solveUpload({
      runNesting: true,
      sheetWidth: size.sheetX,
      sheetHeight: size.sheetY,
      sheetThickness: size.sheetThickness,
      hopsGeometryMode: hopsGeometryModeForUpload(),
    })
  }

  function onSheetSizeChoice({ sheetX, sheetY, sheetThickness }) {
    const x = Math.round(Number(sheetX))
    const y = Math.round(Number(sheetY))
    const t = Math.round(Number(sheetThickness))
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(t) || x <= 0 || y <= 0 || t <= 0) return

    const msgId = state.activeSheetSizeSelectId.value
    const msg = state.messages.value.find((m) => m.id === msgId)
    const isLeftover = Boolean(msg?.meta?.leftover)

    if (msg) {
      msg.meta = { ...msg.meta, sheetX: x, sheetY: y, sheetThickness: t, resolved: true }
    }

    if (isLeftover) {
      const confirmId = pushMessage(
        'assistant',
        'text',
        `Sheet size for unassigned parts: ${x}mm x ${y}mm x ${t}mm`,
        { sheetSizeConfirm: true, leftover: true, promptMessageId: msgId },
      )
      state.activeSheetSizeConfirmId.value = confirmId
      state.activeSheetSizeSelectId.value = null
      nestUnassignedParts({ sheetX: x, sheetY: y, sheetThickness: t })
      return
    }

    state.pendingSheetSize.value = { sheetX: x, sheetY: y, sheetThickness: t }

    const hadNested = Boolean(state.summonedPreview.value?.dxfText)
    if (hadNested) {
      invalidateNestResult({ reason: 'sheet-size' })
    }

    const confirmId = pushMessage('assistant', 'text', `Sheet size for nesting: ${x}mm x ${y}mm x ${t}mm`, {
      sheetSizeConfirm: true,
      promptMessageId: msgId,
    })
    state.activeSheetSizeConfirmId.value = confirmId
    state.activeSheetSizeSelectId.value = null

    if (hadNested) {
      const promptIndex = state.messages.value.findIndex((m) => m.id === msgId)
      state.messages.value = state.messages.value.filter((m, i) => {
        if (m.kind === 'nesting-result') return false
        if (m.meta?.sheetSizeConfirm && m.id !== confirmId) return false
        if (promptIndex >= 0 && i < promptIndex) return m.role === 'user'
        return true
      })
    }

    promptMaterial()
  }

  function onMaterialChoice({ label, thicknessMm }) {
    const matLabel = String(label ?? '').trim()
    const thickness = Math.round(Number(thicknessMm))
    if (!matLabel || !Number.isFinite(thickness)) return

    const previousLabel = state.pendingSheetMaterial.value?.label ?? null
    const keys = partKeysForMaterialApply(previousLabel)
    if (!keys.length) return

    const hadNested = Boolean(state.summonedPreview.value?.dxfText)
    if (hadNested) {
      invalidateNestResult({ reason: 'metadata' })
    }

    state.metadataOverrides.value = applyMetadataByPartKeys({
      partKeys: keys,
      field: 'mat',
      value: matLabel,
      metadataOverrides: state.metadataOverrides.value,
    })

    for (const entry of partRegistry.value) {
      if (keys.includes(entry.partKey)) markModifiedPart(entry)
    }

    state.pendingSheetMaterial.value = { label: matLabel, thicknessMm: thickness }

    const msgId = state.activeMaterialSelectId.value
    const msg = state.messages.value.find((m) => m.id === msgId)
    if (msg) {
      msg.meta = {
        ...msg.meta,
        materialLabel: matLabel,
        thicknessMm: thickness,
        resolved: true,
      }
    }

    const confirmId = pushMessage(
      'assistant',
      'text',
      `Material for nesting: ${matLabel} (${thickness} mm)`,
      {
        materialConfirm: true,
        promptMessageId: msgId,
      },
    )
    state.activeMaterialConfirmId.value = confirmId
    state.activeMaterialSelectId.value = null
  }

  function onModifyMaterial({ promptMessageId }) {
    const prompt = state.messages.value.find((m) => m.id === promptMessageId)
    if (!prompt || prompt.kind !== 'material-select') return

    prompt.meta = {
      ...prompt.meta,
      materialLabel: state.pendingSheetMaterial.value?.label,
      thicknessMm: state.pendingSheetMaterial.value?.thicknessMm,
      sheetThickness: state.pendingSheetSize.value?.sheetThickness,
      resolved: false,
    }

    state.activeMaterialConfirmId.value = null
    state.activeMaterialSelectId.value = promptMessageId
  }

  function onModifySheetSize({ promptMessageId }) {
    const prompt = state.messages.value.find((m) => m.id === promptMessageId)
    if (!prompt || prompt.kind !== 'sheet-size-select') return

    prompt.meta = prompt.meta?.leftover
      ? { ...prompt.meta, resolved: false }
      : { ...prompt.meta, ...state.pendingSheetSize.value, resolved: false }

    state.activeSheetSizeConfirmId.value = null
    state.activeSheetSizeSelectId.value = promptMessageId
  }

  const canStartNesting = computed(() => {
    if (!state.selectedFile.value || state.busy.value || state.viewerBusy.value) return false
    if (state.requiresHopsProcessing.value || dxfTextHasAcisSolid(state.dxfText.value)) {
      return state.readyForNesting.value
    }
    return true
  })

  const showNestingButton = computed(() => {
    if (state.activeSheetSizeSelectId.value) return false
    if (state.activeMaterialSelectId.value) return false
    if (state.summonedPreview.value?.dxfText) return false
    return canStartNesting.value
      && Boolean(state.pendingSheetSize.value)
      && !hasMissingMat.value
  })

  const nestingNeedsRerun = computed(
    () =>
      state.sheetSizeModifiedSinceNest.value || state.metadataModifiedSinceNest.value,
  )

  const nestingButtonPrompt = computed(() => {
    if (state.metadataModifiedSinceNest.value) return METADATA_MODIFIED_NEST_PROMPT
    if (state.sheetSizeModifiedSinceNest.value) {
      return 'Sheet size has been modified, please run Nesting process again'
    }
    return 'File ready — run nesting to flatten and nest parts.'
  })

  function onAttachError(message) {
    pushMessage('assistant', 'error', message)
  }

  function onClearAll() {
    resetFileState(state)
  }

  function closeNestingModal() {
    state.showNestingModal.value = false
    if (!state.summonedPreview.value?.dxfText) return

    state.postNestMetadataEditing.value = true
    state.viewMode.value = 'input'
    restoreInputPreviewForMetadataEditing({
      annotationFallback: state.summonedPreview.value?.inputTextDxf ?? null,
    })
    applyPostNestMetadataSeed()
    state.nestingViewerKey.value += 1
  }

  function openNestingModal() {
    if (!state.summonedPreview.value) return
    state.showNestingModal.value = true
  }

  function onNestUnassignedParts() {
    closeNestingModal()
    promptLeftoverSheetSize()
  }

  function isShowNestingResultRequest(text) {
    return /^show\s+nesting\s+result\.?$/i.test(String(text ?? '').trim())
  }

  function onSendText(text) {
    if (isShowNestingResultRequest(text)) {
      pushMessage('user', 'text', text)
      if (state.summonedPreview.value?.dxfText) {
        openNestingModal()
      } else {
        pushMessage('assistant', 'text', 'No nesting result yet. Upload a file and run Nest first.')
      }
      return
    }
    chat.onSendText(text)
  }

  return {
    ...state,
    outputViewEnabled,
    activeViewer,
    showNestingMeshView,
    showMeshPreview,
    showPreviewNotice,
    canStartNesting,
    showNestingButton,
    nestingNeedsRerun,
    nestingButtonPrompt,
    onAttachFile,
    onAttachError,
    onClearAll,
    onStartNesting,
    onSheetSizeChoice,
    onModifySheetSize,
    onMaterialChoice,
    onModifyMaterial,
    hasMissingMat,
    closeNestingModal,
    openNestingModal,
    onNestUnassignedParts,
    onSendText,
    meshPartDescriptors,
    nestingMeshPartDescriptors,
    unassignedPartIdsForViewer,
    partRegistry,
    viewerClickForProperties,
    markModified,
  }
}
