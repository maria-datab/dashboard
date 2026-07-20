/**
 * Boxout app orchestration: chat, CSV/image import, table edits, solve triggers.
 */
import { computed, ref, watch } from 'vue'
import ExcelJS from 'exceljs'
import { analyzeCsv, analyzeImage, parseBoxCommand } from '@/scripts/compute.js'
import {
  appendVariations,
  coerceParamValue,
  collectOutOfRangeMessages,
  CSV_GH_INPUT_NAMES,
  CSV_PARSE_SOURCE,
  CSV_PARSE_SOURCE_LABELS,
  formatDefaultBoxName,
  mergeAnalyzeWithLocalParse,
  normalizeVariationPayload,
  parseLenientLocalCsv,
  spliceBoxRow,
  summarizeVariationRows,
  tryParseCleanCsv,
} from '@/scripts/csv.js'
import { createSolveState, resetSolveState, SOLVE_STAGE } from '@/scripts/solveState.js'

console.log('Box-Out Version 0.1.3')

export function useApp() {
  const inputLists = ref(null)
  const csvSourceLists = ref(null)
  const emptyCellKeys = ref(new Set())
  const variationNames = ref([])
  const quantities = ref([])
  const selectedVariationIndex = ref(0)
  const solveRequestId = ref(0)

  const csvError = ref(null)
  const csvAnalyzing = ref(false)
  const csvParamCount = ref(0)
  /** @type {import('vue').Ref<'local'|'llm'|null>} */
  const csvParseSource = ref(null)

  /** @type {import('vue').Ref<{ fileName: string, normalized: object, parseSource: string }|null>} */
  const pendingFileImport = ref(null)

  const chatMessages = ref([])
  const solveState = ref(createSolveState())
  const nestingPreviewOpen = ref(false)
  const sendResultsPhase = ref(null)

  const nestingGeometryPayload = computed(
    () => solveState.value.fullSetNesting?.geometryPayload ?? null,
  )

  const nestingPreviewReady = computed(
    () =>
      !solveState.value.isSolving &&
      solveState.value.fullSetNesting?.geometryPayload != null,
  )

  function onToggleNestingPreview() {
    if (!nestingPreviewReady.value) return
    nestingPreviewOpen.value = !nestingPreviewOpen.value
  }

  watch(nestingPreviewReady, (ready) => {
    if (!ready) {
      nestingPreviewOpen.value = false
      sendResultsPhase.value = null
    }
  })

  function nextChatMessageId() {
    return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  }

  function pushChatMessage(message) {
    chatMessages.value = [...chatMessages.value, message]
  }

  function existingBoxesForLlm() {
    if (!inputLists.value || csvParamCount.value === 0) return []
    return Array.from({ length: csvParamCount.value }, (_, i) => ({
      boxNumber: i + 1,
      name: variationNames.value[i]?.trim() || formatDefaultBoxName(i),
      BoxWidth: inputLists.value.BoxWidth[i],
      BoxHeight: inputLists.value.BoxHeight[i],
      BoxDepth: inputLists.value.BoxDepth[i],
    }))
  }

  function clearTableState() {
    inputLists.value = null
    csvSourceLists.value = null
    emptyCellKeys.value = new Set()
    variationNames.value = []
    quantities.value = []
    csvParamCount.value = 0
    csvParseSource.value = null
    selectedVariationIndex.value = 0
    resetSolveState(solveState)
    nestingPreviewOpen.value = false
  }

  watch(
    () => solveState.value.solveStage,
    (stage) => {
      if (stage === SOLVE_STAGE.completed && csvParamCount.value > 0) {
        selectedVariationIndex.value = Math.min(
          selectedVariationIndex.value,
          csvParamCount.value - 1,
        )
      }
    },
  )

  function onSolveStateUpdate(state) {
    solveState.value = {
      ...createSolveState(),
      ...state,
      rowErrors: state.rowErrors instanceof Map ? new Map(state.rowErrors) : new Map(),
      computeProgress: { ...state.computeProgress },
      warnings: [...(state.warnings ?? [])],
      variationStatuses: [...(state.variationStatuses ?? [])],
      sentParamNames: [...(state.sentParamNames ?? [])],
      perBoxNesting: {
        kSheetNr: state.perBoxNesting?.kSheetNr ?? null,
        fSheetNr: state.perBoxNesting?.fSheetNr ?? null,
      },
      fullSetNesting: { ...(state.fullSetNesting ?? {}) },
    }
  }

  function csvField(value) {
    if (value == null || value === '') return ''
    const s = String(value)
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }

  async function xlsxBufferToCsv(buffer) {
    const workbook = new ExcelJS.Workbook()
    await workbook.xlsx.load(buffer)
    const sheet = workbook.worksheets[0]
    if (!sheet) throw new Error('Excel file has no sheets')

    const colCount = sheet.actualColumnCount
    const lines = []
    sheet.eachRow((row) => {
      const fields = []
      for (let c = 1; c <= colCount; c++) {
        const cell = row.getCell(c)
        fields.push(csvField(cell.text || cell.value))
      }
      lines.push(fields.join(','))
    })
    return lines.join('\n')
  }

  async function fileToCsvText(file) {
    const name = file.name.toLowerCase()
    if (name.endsWith('.xlsx')) {
      return xlsxBufferToCsv(await file.arrayBuffer())
    }
    return file.text()
  }

  function applyVariationPayload(normalizedNew, parseSource, mode) {
    const previousCount = csvParamCount.value
    const isAppend = mode === 'append'

    const merged = normalizeVariationPayload(
      isAppend
        ? appendVariations(inputLists.value, variationNames.value, normalizedNew, quantities.value)
        : normalizedNew,
    )

    const newEmptyKeys = normalizedNew.emptyCellKeys ?? new Set()

    if (isAppend) {
      const offset = previousCount
      const mergedKeys = new Set(emptyCellKeys.value)
      for (const key of newEmptyKeys) {
        const [i, param] = key.split(':')
        mergedKeys.add(`${Number(i) + offset}:${param}`)
      }
      emptyCellKeys.value = mergedKeys
    } else {
      emptyCellKeys.value = new Set(newEmptyKeys)
      selectedVariationIndex.value = 0
    }

    csvSourceLists.value = {
      BoxDepth: [...merged.inputLists.BoxDepth],
      BoxHeight: [...merged.inputLists.BoxHeight],
      BoxWidth: [...merged.inputLists.BoxWidth],
    }

    csvParseSource.value = parseSource
    csvParamCount.value = merged.variationCount
    inputLists.value = merged.inputLists
    variationNames.value = merged.variationNames
    quantities.value = merged.quantities
    solveRequestId.value += 1

    const rowStartIndex = isAppend ? previousCount : 0
    return {
      addedCount: isAppend ? merged.variationCount - previousCount : merged.variationCount,
      isAppend,
      sourceLabel: CSV_PARSE_SOURCE_LABELS[parseSource] ?? 'Parsed',
      summaryText: summarizeVariationRows(merged.inputLists, merged.variationNames, rowStartIndex).join('\n') || 'No boxes parsed.',
      outOfRangeMessages: collectOutOfRangeMessages(merged.inputLists, merged.variationNames, rowStartIndex),
    }
  }

  function formatWithWarnings(summaryText, outOfRangeMessages) {
    if (!outOfRangeMessages.length) return summaryText
    return `${summaryText}\n\nOut of range:\n${outOfRangeMessages.join('\n')}`
  }

  function finishFileImport(choice) {
    const pending = pendingFileImport.value
    if (!pending) return
    pendingFileImport.value = null

    if (choice === 'cancel') {
      pushChatMessage({ id: nextChatMessageId(), role: 'assistant', kind: 'result', content: 'Import cancelled.' })
      return
    }

    const result = applyVariationPayload(
      pending.normalized,
      pending.parseSource,
      choice === 'append' ? 'append' : 'overwrite',
    )
    const label = choice === 'append' ? 'Added' : 'Replaced with'
    pushChatMessage({
      id: nextChatMessageId(),
      role: 'assistant',
      kind: result.outOfRangeMessages.length > 0 ? 'error' : 'result',
      content: formatWithWarnings(
        `${label} ${result.addedCount} box(es). ${result.sourceLabel}.\n${result.summaryText}`,
        result.outOfRangeMessages,
      ),
    })
  }

  async function fileToImageBody(file) {
    const bytes = new Uint8Array(await file.arrayBuffer())
    let binary = ''
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
    const name = file.name.toLowerCase()
    const mediaType =
      file.type ||
      (name.endsWith('.png') ? 'image/png' : 'image/jpeg')
    return { imageBase64: btoa(binary), mediaType }
  }

  async function parseImportFile(file) {
    if (/\.(jpe?g|png)$/i.test(file.name)) {
      const llmResult = await analyzeImage(await fileToImageBody(file))
      return { normalized: normalizeVariationPayload(llmResult), parseSource: CSV_PARSE_SOURCE.llm }
    }

    const text = await fileToCsvText(file)
    const assessment = tryParseCleanCsv(text)
    let parsed
    const usedLlm = assessment.needsAi

    if (!usedLlm) {
      parsed = assessment
    } else {
      const localParsed = parseLenientLocalCsv(text)
      const llmResult = await analyzeCsv(text)
      parsed = mergeAnalyzeWithLocalParse(localParsed, llmResult)
    }

    return {
      normalized: {
        ...normalizeVariationPayload(parsed),
        emptyCellKeys: parsed.emptyCellKeys ?? new Set(),
      },
      parseSource: usedLlm ? CSV_PARSE_SOURCE.llm : CSV_PARSE_SOURCE.local,
    }
  }

  async function processParsedFileImport(file, parseFile) {
    pushChatMessage({ id: nextChatMessageId(), role: 'user', kind: 'file', content: file.name })
    csvError.value = null
    csvAnalyzing.value = true

    try {
      const { normalized, parseSource } = await parseFile(file)

      if (csvParamCount.value > 0) {
        pendingFileImport.value = { fileName: file.name, normalized, parseSource }
        pushChatMessage({
          id: nextChatMessageId(),
          role: 'assistant',
          kind: 'confirm',
          content: `You have ${csvParamCount.value} box(es). Append ${normalized.variationCount} from "${file.name}" or overwrite?`,
          meta: { choices: ['append', 'overwrite', 'cancel'] },
        })
        return
      }

      const result = applyVariationPayload(normalized, parseSource, 'replace')
      pushChatMessage({
        id: nextChatMessageId(),
        role: 'assistant',
        kind: result.outOfRangeMessages.length > 0 ? 'error' : 'result',
        content: formatWithWarnings(
          `Parsed ${result.addedCount} box(es). ${result.sourceLabel}.\n${result.summaryText}`,
          result.outOfRangeMessages,
        ),
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Invalid file'
      csvError.value = message
      pushChatMessage({ id: nextChatMessageId(), role: 'assistant', kind: 'error', content: message })
    } finally {
      csvAnalyzing.value = false
    }
  }

  function processChatFile(file) {
    return processParsedFileImport(file, parseImportFile)
  }

  function onAttachError(message) {
    pushChatMessage({ id: nextChatMessageId(), role: 'assistant', kind: 'error', content: message })
  }

  async function processChatText(text) {
    pushChatMessage({ id: nextChatMessageId(), role: 'user', kind: 'text', content: text })

    const pendingChoice = text.trim().toLowerCase()
    if (pendingFileImport.value && ['append', 'overwrite', 'cancel'].includes(pendingChoice)) {
      finishFileImport(pendingChoice)
      return
    }

    csvError.value = null
    csvAnalyzing.value = true

    try {
      const command = await parseBoxCommand(text, existingBoxesForLlm())

      if (command.action === 'add') {
        const add = command.add
        if (!add?.variationCount) throw new Error('No box dimensions could be parsed.')
        const result = applyVariationPayload(
          { inputLists: add.inputLists, variationNames: add.variationNames, variationCount: add.variationCount },
          CSV_PARSE_SOURCE.llm,
          csvParamCount.value > 0 ? 'append' : 'replace',
        )
        pushChatMessage({
          id: nextChatMessageId(),
          role: 'assistant',
          kind: result.outOfRangeMessages.length > 0 ? 'error' : 'result',
          content: formatWithWarnings(
            `${result.isAppend ? 'Added' : 'Created'} ${result.addedCount} box(es). ${result.sourceLabel}.\n${result.summaryText}`,
            result.outOfRangeMessages,
          ),
        })
        return
      }

      if (command.action === 'update') {
        const lists = {
          BoxDepth: [...inputLists.value.BoxDepth],
          BoxHeight: [...inputLists.value.BoxHeight],
          BoxWidth: [...inputLists.value.BoxWidth],
        }
        for (const n of command.boxNumbers ?? []) {
          const index = n - 1
          if (index < 0 || index >= csvParamCount.value) continue
          for (const param of CSV_GH_INPUT_NAMES) {
            const delta = coerceParamValue(command.fieldDeltas?.[param])
            if (delta != null) {
              lists[param][index] = (lists[param][index] ?? 0) + delta
              continue
            }
            const coerced = coerceParamValue(command.fields?.[param])
            if (coerced != null) lists[param][index] = coerced
          }
        }
        const merged = normalizeVariationPayload({
          inputLists: lists,
          variationNames: variationNames.value,
          quantities: quantities.value,
        })
        inputLists.value = merged.inputLists
        variationNames.value = merged.variationNames
        quantities.value = merged.quantities
        csvParamCount.value = merged.variationCount
        solveRequestId.value += 1

        const summary = summarizeVariationRows(
          merged.inputLists,
          merged.variationNames,
          0,
          merged.quantities,
        ).join('\n')
        const oor = collectOutOfRangeMessages(merged.inputLists, merged.variationNames, 0)
        pushChatMessage({
          id: nextChatMessageId(),
          role: 'assistant',
          kind: oor.length > 0 ? 'error' : 'result',
          content: formatWithWarnings(`Updated ${command.boxNumbers?.length ?? 0} box(es).\n${summary}`, oor),
        })
        return
      }

      if (command.action === 'delete') {
        const index = command.boxNumber - 1
        if (index < 0 || index >= csvParamCount.value) throw new Error(`Box ${command.boxNumber} not found.`)

        const remaining = csvParamCount.value - 1
        onDeleteRow(index)

        pushChatMessage({
          id: nextChatMessageId(),
          role: 'assistant',
          kind: 'result',
          content: remaining === 0
            ? 'Deleted Box ' + command.boxNumber + '. No boxes remaining.'
            : `Deleted Box ${command.boxNumber}. ${remaining} box(es) remaining.`,
        })
        return
      }

      if (command.action === 'clear') {
        clearTableState()
        pushChatMessage({ id: nextChatMessageId(), role: 'assistant', kind: 'result', content: 'Cleared all boxes.' })
        return
      }

      throw new Error('Could not understand that command.')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not process message'
      csvError.value = message
      pushChatMessage({ id: nextChatMessageId(), role: 'assistant', kind: 'error', content: message })
    } finally {
      csvAnalyzing.value = false
    }
  }

  function onClearAll() {
    clearTableState()
    pushChatMessage({ id: nextChatMessageId(), role: 'assistant', kind: 'result', content: 'Cleared all boxes.' })
  }

  function onApplyEditedLists({ inputLists: lists, quantities: qtys }) {
    const merged = normalizeVariationPayload({
      inputLists: lists,
      variationNames: variationNames.value,
      quantities: qtys,
    })
    inputLists.value = merged.inputLists
    variationNames.value = merged.variationNames
    quantities.value = merged.quantities
    csvParamCount.value = merged.variationCount
    solveRequestId.value += 1
  }

  function onDeleteRow(index) {
    if (index < 0 || index >= csvParamCount.value) return

    const sliced = spliceBoxRow(
      inputLists.value,
      variationNames.value,
      index,
      quantities.value,
    )
    const merged = normalizeVariationPayload({
      inputLists: sliced.inputLists,
      variationNames: sliced.variationNames,
      quantities: sliced.quantities,
    })

    if (merged.variationCount === 0) {
      clearTableState()
      return
    }

    const nextEmptyKeys = new Set()
    for (const key of emptyCellKeys.value) {
      const [i, param] = key.split(':')
      const ri = Number(i)
      if (ri === index) continue
      nextEmptyKeys.add(ri > index ? `${ri - 1}:${param}` : key)
    }
    variationNames.value = merged.variationNames
    inputLists.value = merged.inputLists
    quantities.value = merged.quantities
    csvSourceLists.value = {
      BoxDepth: [...merged.inputLists.BoxDepth],
      BoxHeight: [...merged.inputLists.BoxHeight],
      BoxWidth: [...merged.inputLists.BoxWidth],
    }
    emptyCellKeys.value = nextEmptyKeys
    csvParamCount.value = merged.variationCount
    selectedVariationIndex.value = Math.min(selectedVariationIndex.value, csvParamCount.value - 1)
    solveRequestId.value += 1
  }

  return {
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
  }
}
