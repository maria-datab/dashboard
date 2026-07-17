import { computed, ref } from 'vue'
import { parseDxf } from 'dxf-vuer'

export const FIELD_LABELS = { nr: 'Name', mat: 'Material', anz: 'Amount' }

export const DEFAULT_SHEET_SIZE = { sheetX: 2500, sheetY: 1250, sheetThickness: 21 }

export const PLACEHOLDER_MATERIALS = [
  { label: 'placeholder 1', thicknessMm: 21 },
  { label: 'placeholder 2', thicknessMm: 30 },
  { label: 'Placeholder 3', thicknessMm: 35 },
]

export const METADATA_MODIFIED_NEST_PROMPT =
  'Part data has been modified. Please run Nesting process again once all necessary modifications have been made.'

export function createAppState() {
  const selectedFile = ref(null)
  const dxfText = ref(null)
  const messages = ref([])
  const busy = ref(false)
  const busyMessage = ref('')
  const viewerBusy = ref(false)
  const viewerBusyMessage = ref('')
  const readyForNesting = ref(false)
  const awaitingConfirm = ref(false)
  const step = ref('idle')
  const materialText = ref('')
  const metadataOverrides = ref({})
  const boundaries = ref([])
  const blockInserts = ref([])
  const schemeOutliers = ref([])
  const showMetadataColors = ref(false)
  const showModifiedPartsGreen = ref(false)
  const showPartLabels = ref(false)
  const clickForProperties = ref(false)
  const viewMode = ref('input')
  const showOutlierLines = ref(false)
  const showSchemeOutliers = ref(false)
  const showCorrectParts = ref(false)
  const showIncorrectParts = ref(false)
  const showDimensions = ref(true)
  const modifiedHandles = ref([])
  const hasShownGreenHint = ref(false)
  const dxfInterpreted = ref(false)
  const sourceType = ref('dxf')
  /** @type {import('vue').Ref<'2d' | '3d' | null>} */
  const geometryMode = ref(null)
  const scanPageImages = ref([])
  const scanParts = ref([])
  const scanPartsByPage = ref([])
  const drillDiameterMm = ref(null)
  const meshViewerRef = ref(null)
  const summonedPreview = ref(null)
  /** Successful leftover nest (unassigned DXF re-nested); null until all leftovers fit. */
  const leftoverNestPreview = ref(null)
  const showNestingModal = ref(false)
  const meshPreview = ref(null)
  /** GH InitialPartKeys — canonical part keys for both 2D and 3D preview. */
  const previewPartKeys = ref([])
  const meshPreviewPostInjectionNames = ref([])
  const meshPreviewPostInjectionAmount = ref([])
  const previewNotice = ref(null)
  const annotationOverlayDxf = ref(null)
  const inspectTextPosition = ref('inside')
  const activeTextPositionSelectId = ref(null)
  const activeSheetSizeSelectId = ref(null)
  const activeSheetSizeConfirmId = ref(null)
  const pendingSheetSize = ref(null)
  const activeMaterialSelectId = ref(null)
  const activeMaterialConfirmId = ref(null)
  /** @type {import('vue').Ref<{ label: string, thicknessMm: number } | null>} */
  const pendingSheetMaterial = ref(null)
  const sheetSizeModifiedSinceNest = ref(false)
  const metadataModifiedSinceNest = ref(false)
  const postNestMetadataEditing = ref(false)
  const nestingViewerKey = ref(0)
  const inputPreviewMeshes = ref(null)
  const inputPreviewPartKeys = ref(null)
  const inputPreviewPostInjectionNames = ref(null)
  const inputPreviewPostInjectionAmount = ref(null)
  const inputPreviewAnnotationDxf = ref(null)
  /** @type {import('vue').Ref<Array<{ nr?: string, mat?: string, anz?: string }> | null>} */
  const meshDescriptorBaseMeta = ref(null)
  /** Last Hops geometryMode int sent (0 = flat pipeline, 1 = solid pipeline). */
  const lastHopsGeometryMode = ref(null)
  const activeExportAssociatedMessageId = ref(null)
  const embeddedMetaState = ref('none')

  let summonPreviewTask = null

  const parsedDxf = computed(() => {
    if (!dxfText.value) return null
    try {
      return parseDxf(dxfText.value)
    } catch {
      return null
    }
  })

  const requiresHopsProcessing = computed(
    () =>
      sourceType.value === 'dwg'
      || sourceType.value === '3dm'
      || sourceType.value === 'dxf',
  )

  const hasBoxes = computed(() => !!selectedFile.value)

  return {
    selectedFile,
    dxfText,
    messages,
    busy,
    busyMessage,
    viewerBusy,
    viewerBusyMessage,
    readyForNesting,
    awaitingConfirm,
    step,
    materialText,
    metadataOverrides,
    boundaries,
    blockInserts,
    schemeOutliers,
    showMetadataColors,
    showModifiedPartsGreen,
    showPartLabels,
    clickForProperties,
    viewMode,
    showOutlierLines,
    showSchemeOutliers,
    showCorrectParts,
    showIncorrectParts,
    showDimensions,
    modifiedHandles,
    hasShownGreenHint,
    dxfInterpreted,
    sourceType,
    geometryMode,
    scanPageImages,
    scanParts,
    scanPartsByPage,
    drillDiameterMm,
    meshViewerRef,
    summonedPreview,
    leftoverNestPreview,
    showNestingModal,
    meshPreview,
    previewPartKeys,
    meshPreviewPostInjectionNames,
    meshPreviewPostInjectionAmount,
    previewNotice,
    annotationOverlayDxf,
    inspectTextPosition,
    activeTextPositionSelectId,
    activeSheetSizeSelectId,
    activeSheetSizeConfirmId,
    pendingSheetSize,
    activeMaterialSelectId,
    activeMaterialConfirmId,
    pendingSheetMaterial,
    sheetSizeModifiedSinceNest,
    metadataModifiedSinceNest,
    postNestMetadataEditing,
    nestingViewerKey,
    inputPreviewMeshes,
    inputPreviewPartKeys,
    inputPreviewPostInjectionNames,
    inputPreviewPostInjectionAmount,
    inputPreviewAnnotationDxf,
    meshDescriptorBaseMeta,
    lastHopsGeometryMode,
    activeExportAssociatedMessageId,
    embeddedMetaState,
    parsedDxf,
    requiresHopsProcessing,
    hasBoxes,
    getSummonPreviewTask: () => summonPreviewTask,
    setSummonPreviewTask: (task) => {
      summonPreviewTask = task
    },
  }
}
