import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { useParams } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getOfficeDoc, updateOfficeDoc, starOfficeDoc } from '@/api/office'
import { useAuthStore } from '@/stores/authStore'
import EditorTopBar from '@/components/office/EditorTopBar'
import SheetToolbar from '@/components/office/SheetToolbar'
import SheetContextMenu from '@/components/office/SheetContextMenu'
import SheetFindReplace from '@/components/office/SheetFindReplace'
import { Plus, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CellData, SheetData, MergedRange } from '@/lib/spreadsheet/types'
import { colLabel, cellId, parseCellRef } from '@/lib/spreadsheet/types'
import { evaluateFormula } from '@/lib/spreadsheet/formulaEngine'
import { formatCellValue, isNumeric, parseNumeric } from '@/lib/spreadsheet/cellFormatting'

// ---------------------------------------------------------------------------
// Selection range type
// ---------------------------------------------------------------------------
interface SelectionRange {
  startRow: number
  startCol: number
  endRow: number
  endCol: number
}

// Normalize selection so start <= end
function normalizeRange(r: SelectionRange): SelectionRange {
  return {
    startRow: Math.min(r.startRow, r.endRow),
    startCol: Math.min(r.startCol, r.endCol),
    endRow: Math.max(r.startRow, r.endRow),
    endCol: Math.max(r.startCol, r.endCol),
  }
}

function inRange(row: number, col: number, r: SelectionRange | null): boolean {
  if (!r) return false
  const n = normalizeRange(r)
  return row >= n.startRow && row <= n.endRow && col >= n.startCol && col <= n.endCol
}

// ---------------------------------------------------------------------------
// Context menu state
// ---------------------------------------------------------------------------
interface ContextMenuState {
  visible: boolean
  x: number
  y: number
  row: number
  col: number
}

// ---------------------------------------------------------------------------
// Filter dropdown state
// ---------------------------------------------------------------------------
interface FilterDropdown {
  col: number
  x: number
  y: number
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const DEFAULT_COL_WIDTH = 100
const DEFAULT_ROW_HEIGHT = 28
const ROW_NUM_WIDTH = 44
const MIN_COL_WIDTH = 30
const MIN_ROW_HEIGHT = 20
const MAX_HISTORY = 50
const SAVE_DELAY_MS = 2000

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function SheetEditorPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const { user: _user } = useAuthStore()

  // ---------------------------------------------------------------------------
  // Connection state (collaboration placeholders)
  // ---------------------------------------------------------------------------
  const [connectionStatus] = useState<'connected' | 'connecting' | 'disconnected'>('connected')
  const [connectedUsers] = useState<{ name: string; color: string }[]>([])

  // ---------------------------------------------------------------------------
  // Core spreadsheet state
  // ---------------------------------------------------------------------------
  const [sheets, setSheets] = useState<SheetData[]>([{ name: 'Sheet1', cells: {} }])
  const [activeSheetIndex, setActiveSheetIndex] = useState(0)
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number } | null>(null)
  const [editingCell, setEditingCell] = useState<{ row: number; col: number } | null>(null)
  const [formulaBarValue, setFormulaBarValue] = useState('')
  const [selectionRange, setSelectionRange] = useState<SelectionRange | null>(null)

  // ---------------------------------------------------------------------------
  // UI toggles
  // ---------------------------------------------------------------------------
  const [showFindReplace, setShowFindReplace] = useState(false)
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false,
    x: 0,
    y: 0,
    row: 0,
    col: 0,
  })
  const [filterDropdown, setFilterDropdown] = useState<FilterDropdown | null>(null)

  // ---------------------------------------------------------------------------
  // Resize tracking
  // ---------------------------------------------------------------------------
  const [resizingCol, setResizingCol] = useState<{
    col: number
    startX: number
    startWidth: number
  } | null>(null)
  const [resizingRow, setResizingRow] = useState<{
    row: number
    startY: number
    startHeight: number
  } | null>(null)

  // ---------------------------------------------------------------------------
  // Mouse drag selection tracking
  // ---------------------------------------------------------------------------
  const isDraggingSelection = useRef(false)

  // ---------------------------------------------------------------------------
  // Auto-fill drag tracking
  // ---------------------------------------------------------------------------
  const [autoFillTarget, setAutoFillTarget] = useState<{ row: number; col: number } | null>(null)
  const isDraggingFill = useRef(false)

  // ---------------------------------------------------------------------------
  // Refs
  // ---------------------------------------------------------------------------
  const gridRef = useRef<HTMLDivElement>(null)
  const cellRefs = useRef<Record<string, HTMLInputElement | null>>({})
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const initialLoadRef = useRef(false)

  // ---------------------------------------------------------------------------
  // Undo/Redo history
  // ---------------------------------------------------------------------------
  const historyStack = useRef<SheetData[][]>([])
  const historyIndex = useRef(-1)

  const pushHistory = useCallback((snapshot: SheetData[]) => {
    // Trim any future states
    historyStack.current = historyStack.current.slice(0, historyIndex.current + 1)
    // Deep-clone the snapshot
    historyStack.current.push(JSON.parse(JSON.stringify(snapshot)))
    if (historyStack.current.length > MAX_HISTORY) {
      historyStack.current.shift()
    }
    historyIndex.current = historyStack.current.length - 1
  }, [])

  const canUndo = historyIndex.current > 0
  const canRedo = historyIndex.current < historyStack.current.length - 1

  const undo = useCallback(() => {
    if (historyIndex.current <= 0) return
    historyIndex.current -= 1
    const snapshot = JSON.parse(JSON.stringify(historyStack.current[historyIndex.current]))
    setSheets(snapshot)
    debouncedSave(snapshot)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const redo = useCallback(() => {
    if (historyIndex.current >= historyStack.current.length - 1) return
    historyIndex.current += 1
    const snapshot = JSON.parse(JSON.stringify(historyStack.current[historyIndex.current]))
    setSheets(snapshot)
    debouncedSave(snapshot)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // Data fetching
  // ---------------------------------------------------------------------------
  const { data: docData } = useQuery({
    queryKey: ['office-doc', id],
    queryFn: () => getOfficeDoc(id!),
    enabled: !!id,
  })

  const doc = docData?.data

  const updateMutation = useMutation({
    mutationFn: (data: { title?: string; content_json?: Record<string, unknown> }) =>
      updateOfficeDoc(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-doc', id] })
    },
  })

  const starMutation = useMutation({
    mutationFn: () => starOfficeDoc(id!, !doc?.is_starred),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-doc', id] })
    },
  })

  // ---------------------------------------------------------------------------
  // Load from backend
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!doc || initialLoadRef.current) return
    initialLoadRef.current = true

    if (doc.content_json && typeof doc.content_json === 'object') {
      const saved = doc.content_json as { sheets?: SheetData[] }
      if (saved.sheets && Array.isArray(saved.sheets) && saved.sheets.length > 0) {
        setSheets(saved.sheets)
        // Seed history
        historyStack.current = [JSON.parse(JSON.stringify(saved.sheets))]
        historyIndex.current = 0
      } else {
        historyStack.current = [JSON.parse(JSON.stringify([{ name: 'Sheet1', cells: {} }]))]
        historyIndex.current = 0
      }
    } else {
      historyStack.current = [JSON.parse(JSON.stringify([{ name: 'Sheet1', cells: {} }]))]
      historyIndex.current = 0
    }
  }, [doc])

  // Cleanup save timer
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Debounced save
  // ---------------------------------------------------------------------------
  const debouncedSave = useCallback(
    (updatedSheets: SheetData[]) => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      saveTimerRef.current = setTimeout(() => {
        updateMutation.mutate({
          content_json: { sheets: updatedSheets } as Record<string, unknown>,
        })
      }, SAVE_DELAY_MS)
    },
    [updateMutation]
  )

  // ---------------------------------------------------------------------------
  // Active sheet helpers
  // ---------------------------------------------------------------------------
  const activeSheet = sheets[activeSheetIndex] || sheets[0]
  const numRows = activeSheet.numRows || 50
  const numCols = activeSheet.numCols || 26
  const freezeRow = activeSheet.freezeRow || 0
  const freezeCol = activeSheet.freezeCol || 0
  const hiddenRows = useMemo(() => new Set(activeSheet.hiddenRows || []), [activeSheet.hiddenRows])
  const hiddenCols = useMemo(() => new Set(activeSheet.hiddenCols || []), [activeSheet.hiddenCols])
  const mergedCells = activeSheet.mergedCells || []
  const filterEnabled = activeSheet.filterEnabled || false
  const filterValues = activeSheet.filterValues || {}

  // Compute visible rows taking filters into account
  const filteredHiddenRows = useMemo(() => {
    const hidden = new Set(hiddenRows)
    if (filterEnabled && Object.keys(filterValues).length > 0) {
      for (let r = 0; r < numRows; r++) {
        if (hidden.has(r)) continue
        for (const [colStr, allowed] of Object.entries(filterValues)) {
          const col = Number(colStr)
          if (allowed.length === 0) continue
          const key = cellId(r, col)
          const val = activeSheet.cells[key]?.value || ''
          if (!allowed.includes(val)) {
            hidden.add(r)
            break
          }
        }
      }
    }
    return hidden
  }, [hiddenRows, filterEnabled, filterValues, numRows, activeSheet.cells])

  const getColWidth = useCallback(
    (col: number): number => activeSheet.colWidths?.[col] ?? DEFAULT_COL_WIDTH,
    [activeSheet.colWidths]
  )

  const getRowHeight = useCallback(
    (row: number): number => activeSheet.rowHeights?.[row] ?? DEFAULT_ROW_HEIGHT,
    [activeSheet.rowHeights]
  )

  // ---------------------------------------------------------------------------
  // Cell value helpers
  // ---------------------------------------------------------------------------
  const getCellRawValue = useCallback(
    (ref: string): string => {
      return activeSheet.cells[ref]?.value || ''
    },
    [activeSheet.cells]
  )

  const getCellDisplayValue = useCallback(
    (row: number, col: number): string => {
      const key = cellId(row, col)
      const data = activeSheet.cells[key]
      if (!data || !data.value) return ''
      const raw = data.value
      if (raw.startsWith('=')) {
        const result = evaluateFormula(raw, getCellRawValue)
        const strResult = typeof result === 'number' ? String(result) : result
        return formatCellValue(strResult, data.format)
      }
      return formatCellValue(raw, data.format)
    },
    [activeSheet.cells, getCellRawValue]
  )

  const getCellData = useCallback(
    (row: number, col: number): CellData => {
      const key = cellId(row, col)
      return activeSheet.cells[key] || { value: '' }
    },
    [activeSheet.cells]
  )

  // ---------------------------------------------------------------------------
  // Mutation helpers: all go through setSheets with history push
  // ---------------------------------------------------------------------------
  const mutateSheets = useCallback(
    (updater: (sheets: SheetData[]) => SheetData[]) => {
      setSheets((prev) => {
        pushHistory(prev)
        const next = updater(prev)
        debouncedSave(next)
        return next
      })
    },
    [pushHistory, debouncedSave]
  )

  const mutateActiveSheet = useCallback(
    (updater: (sheet: SheetData) => SheetData) => {
      mutateSheets((prev) => {
        const updated = [...prev]
        updated[activeSheetIndex] = updater({ ...prev[activeSheetIndex] })
        return updated
      })
    },
    [mutateSheets, activeSheetIndex]
  )

  // Light mutation that does NOT push history (used for resize, etc.)
  const mutateActiveSheetSilent = useCallback(
    (updater: (sheet: SheetData) => SheetData) => {
      setSheets((prev) => {
        const updated = [...prev]
        updated[activeSheetIndex] = updater({ ...prev[activeSheetIndex] })
        debouncedSave(updated)
        return updated
      })
    },
    [activeSheetIndex, debouncedSave]
  )

  const setCellValue = useCallback(
    (row: number, col: number, value: string) => {
      const key = cellId(row, col)
      mutateActiveSheet((sheet) => {
        const cells = { ...sheet.cells }
        const existing = cells[key] || { value: '' }
        cells[key] = { ...existing, value }
        return { ...sheet, cells }
      })
    },
    [mutateActiveSheet]
  )

  // Set cell value without history push (for typing in edit mode)
  const setCellValueSilent = useCallback(
    (row: number, col: number, value: string) => {
      const key = cellId(row, col)
      setSheets((prev) => {
        const updated = [...prev]
        const sheet = { ...updated[activeSheetIndex], cells: { ...updated[activeSheetIndex].cells } }
        const existing = sheet.cells[key] || { value: '' }
        sheet.cells[key] = { ...existing, value }
        updated[activeSheetIndex] = sheet
        debouncedSave(updated)
        return updated
      })
    },
    [activeSheetIndex, debouncedSave]
  )

  // ---------------------------------------------------------------------------
  // Merge helpers
  // ---------------------------------------------------------------------------
  const getMergeForCell = useCallback(
    (row: number, col: number): MergedRange | null => {
      for (const m of mergedCells) {
        if (row >= m.startRow && row <= m.endRow && col >= m.startCol && col <= m.endCol) {
          return m
        }
      }
      return null
    },
    [mergedCells]
  )

  const isMergeOrigin = useCallback(
    (row: number, col: number): boolean => {
      const m = getMergeForCell(row, col)
      return m !== null && m.startRow === row && m.startCol === col
    },
    [getMergeForCell]
  )

  const isMergeCovered = useCallback(
    (row: number, col: number): boolean => {
      const m = getMergeForCell(row, col)
      return m !== null && (m.startRow !== row || m.startCol !== col)
    },
    [getMergeForCell]
  )

  const isAnyCellMerged = useMemo(() => {
    if (!selectedCell) return false
    return getMergeForCell(selectedCell.row, selectedCell.col) !== null
  }, [selectedCell, getMergeForCell])

  // ---------------------------------------------------------------------------
  // Formatting handlers
  // ---------------------------------------------------------------------------
  const applyToSelection = useCallback(
    (updater: (cell: CellData) => CellData) => {
      const range = selectionRange ? normalizeRange(selectionRange) : selectedCell ? { startRow: selectedCell.row, startCol: selectedCell.col, endRow: selectedCell.row, endCol: selectedCell.col } : null
      if (!range) return

      mutateActiveSheet((sheet) => {
        const cells = { ...sheet.cells }
        for (let r = range.startRow; r <= range.endRow; r++) {
          for (let c = range.startCol; c <= range.endCol; c++) {
            const key = cellId(r, c)
            const existing = cells[key] || { value: '' }
            cells[key] = updater(existing)
          }
        }
        return { ...sheet, cells }
      })
    },
    [selectionRange, selectedCell, mutateActiveSheet]
  )

  const handleToggleFormat = useCallback(
    (format: 'bold' | 'italic' | 'underline' | 'strikethrough') => {
      applyToSelection((cell) => ({ ...cell, [format]: !cell[format] }))
    },
    [applyToSelection]
  )

  const handleSetBgColor = useCallback(
    (color: string) => {
      applyToSelection((cell) => ({ ...cell, bgColor: color }))
    },
    [applyToSelection]
  )

  const handleSetTextColor = useCallback(
    (color: string) => {
      applyToSelection((cell) => ({ ...cell, textColor: color }))
    },
    [applyToSelection]
  )

  const handleSetAlign = useCallback(
    (align: 'left' | 'center' | 'right') => {
      applyToSelection((cell) => ({ ...cell, align }))
    },
    [applyToSelection]
  )

  const handleSetFormat = useCallback(
    (format: 'plain' | 'number' | 'currency' | 'percent' | 'date') => {
      applyToSelection((cell) => ({ ...cell, format }))
    },
    [applyToSelection]
  )

  const handleSetFontSize = useCallback(
    (size: number) => {
      applyToSelection((cell) => ({ ...cell, fontSize: size }))
    },
    [applyToSelection]
  )

  const handleSetBorders = useCallback(
    (borders: { top?: boolean; bottom?: boolean; left?: boolean; right?: boolean }) => {
      applyToSelection((cell) => ({ ...cell, borders: { ...cell.borders, ...borders } }))
    },
    [applyToSelection]
  )

  const handleClearFormatting = useCallback(() => {
    applyToSelection((cell) => ({
      value: cell.value,
    }))
  }, [applyToSelection])

  // ---------------------------------------------------------------------------
  // Merge cells
  // ---------------------------------------------------------------------------
  const handleMergeCells = useCallback(() => {
    const range = selectionRange ? normalizeRange(selectionRange) : null
    if (!range) return
    if (range.startRow === range.endRow && range.startCol === range.endCol) return

    mutateActiveSheet((sheet) => {
      const cells = { ...sheet.cells }
      const merged = [...(sheet.mergedCells || [])]

      // Remove any existing merges that overlap
      const filtered = merged.filter(
        (m) =>
          m.endRow < range.startRow ||
          m.startRow > range.endRow ||
          m.endCol < range.startCol ||
          m.startCol > range.endCol
      )

      // Keep top-left value, clear all others
      const originKey = cellId(range.startRow, range.startCol)
      for (let r = range.startRow; r <= range.endRow; r++) {
        for (let c = range.startCol; c <= range.endCol; c++) {
          const key = cellId(r, c)
          if (key !== originKey && cells[key]) {
            cells[key] = { ...cells[key], value: '' }
          }
        }
      }

      filtered.push(range)
      return { ...sheet, cells, mergedCells: filtered }
    })
  }, [selectionRange, mutateActiveSheet])

  const handleUnmergeCells = useCallback(() => {
    if (!selectedCell) return
    const merge = getMergeForCell(selectedCell.row, selectedCell.col)
    if (!merge) return

    mutateActiveSheet((sheet) => {
      const merged = (sheet.mergedCells || []).filter(
        (m) =>
          m.startRow !== merge.startRow ||
          m.startCol !== merge.startCol ||
          m.endRow !== merge.endRow ||
          m.endCol !== merge.endCol
      )
      return { ...sheet, mergedCells: merged }
    })
  }, [selectedCell, getMergeForCell, mutateActiveSheet])

  // ---------------------------------------------------------------------------
  // Freeze panes
  // ---------------------------------------------------------------------------
  const handleFreezeRow = useCallback(
    (count: number) => {
      mutateActiveSheetSilent((sheet) => ({ ...sheet, freezeRow: count }))
    },
    [mutateActiveSheetSilent]
  )

  const handleFreezeCol = useCallback(
    (count: number) => {
      mutateActiveSheetSilent((sheet) => ({ ...sheet, freezeCol: count }))
    },
    [mutateActiveSheetSilent]
  )

  // ---------------------------------------------------------------------------
  // Sort
  // ---------------------------------------------------------------------------
  const handleSort = useCallback(
    (direction: 'asc' | 'desc') => {
      const col = selectedCell?.col ?? 0
      mutateActiveSheet((sheet) => {
        const cells = { ...sheet.cells }
        // Gather all row data
        const nr = sheet.numRows || 50
        const nc = sheet.numCols || 26
        const rows: { rowIdx: number; rowData: Record<number, CellData> }[] = []
        for (let r = 0; r < nr; r++) {
          const rowData: Record<number, CellData> = {}
          for (let c = 0; c < nc; c++) {
            const key = cellId(r, c)
            if (cells[key]) rowData[c] = cells[key]
          }
          rows.push({ rowIdx: r, rowData })
        }

        rows.sort((a, b) => {
          const aVal = a.rowData[col]?.value || ''
          const bVal = b.rowData[col]?.value || ''
          const aNum = parseNumeric(aVal)
          const bNum = parseNumeric(bVal)
          let cmp: number
          if (aNum !== null && bNum !== null) {
            cmp = aNum - bNum
          } else {
            cmp = aVal.localeCompare(bVal, undefined, { sensitivity: 'base' })
          }
          return direction === 'asc' ? cmp : -cmp
        })

        // Re-assign cells based on sorted order
        const newCells: Record<string, CellData> = {}
        rows.forEach((row, newRow) => {
          for (let c = 0; c < nc; c++) {
            if (row.rowData[c]) {
              newCells[cellId(newRow, c)] = row.rowData[c]
            }
          }
        })

        return { ...sheet, cells: newCells }
      })
    },
    [selectedCell?.col, mutateActiveSheet]
  )

  // ---------------------------------------------------------------------------
  // Filter
  // ---------------------------------------------------------------------------
  const handleToggleFilter = useCallback(() => {
    mutateActiveSheetSilent((sheet) => ({
      ...sheet,
      filterEnabled: !sheet.filterEnabled,
      filterValues: sheet.filterEnabled ? {} : sheet.filterValues || {},
    }))
  }, [mutateActiveSheetSilent])

  const getUniqueColumnValues = useCallback(
    (col: number): string[] => {
      const values = new Set<string>()
      for (let r = 0; r < numRows; r++) {
        const key = cellId(r, col)
        const val = activeSheet.cells[key]?.value
        if (val !== undefined && val !== '') values.add(val)
      }
      return Array.from(values).sort()
    },
    [numRows, activeSheet.cells]
  )

  const handleFilterToggleValue = useCallback(
    (col: number, value: string) => {
      mutateActiveSheetSilent((sheet) => {
        const fv = { ...(sheet.filterValues || {}) }
        const existing = fv[col] || []
        if (existing.includes(value)) {
          fv[col] = existing.filter((v) => v !== value)
        } else {
          fv[col] = [...existing, value]
        }
        return { ...sheet, filterValues: fv }
      })
    },
    [mutateActiveSheetSilent]
  )

  // ---------------------------------------------------------------------------
  // Insert / Delete row/col
  // ---------------------------------------------------------------------------
  const reKeyCells = useCallback(
    (
      cells: Record<string, CellData>,
      nr: number,
      nc: number,
      mapRow: (r: number) => number | null,
      mapCol: (c: number) => number | null
    ): Record<string, CellData> => {
      const newCells: Record<string, CellData> = {}
      for (let r = 0; r < nr; r++) {
        for (let c = 0; c < nc; c++) {
          const key = cellId(r, c)
          const data = cells[key]
          if (!data) continue
          const nr2 = mapRow(r)
          const nc2 = mapCol(c)
          if (nr2 !== null && nc2 !== null) {
            newCells[cellId(nr2, nc2)] = data
          }
        }
      }
      return newCells
    },
    []
  )

  const handleInsertRowAbove = useCallback(() => {
    const row = contextMenu.row
    mutateActiveSheet((sheet) => {
      const nr = sheet.numRows || 50
      const nc = sheet.numCols || 26
      const newCells = reKeyCells(
        sheet.cells,
        nr,
        nc,
        (r) => (r >= row ? r + 1 : r),
        (c) => c
      )
      return { ...sheet, cells: newCells, numRows: nr + 1 }
    })
  }, [contextMenu.row, mutateActiveSheet, reKeyCells])

  const handleInsertRowBelow = useCallback(() => {
    const row = contextMenu.row
    mutateActiveSheet((sheet) => {
      const nr = sheet.numRows || 50
      const nc = sheet.numCols || 26
      const newCells = reKeyCells(
        sheet.cells,
        nr,
        nc,
        (r) => (r > row ? r + 1 : r),
        (c) => c
      )
      return { ...sheet, cells: newCells, numRows: nr + 1 }
    })
  }, [contextMenu.row, mutateActiveSheet, reKeyCells])

  const handleInsertColLeft = useCallback(() => {
    const col = contextMenu.col
    mutateActiveSheet((sheet) => {
      const nr = sheet.numRows || 50
      const nc = sheet.numCols || 26
      const newCells = reKeyCells(
        sheet.cells,
        nr,
        nc,
        (r) => r,
        (c) => (c >= col ? c + 1 : c)
      )
      return { ...sheet, cells: newCells, numCols: nc + 1 }
    })
  }, [contextMenu.col, mutateActiveSheet, reKeyCells])

  const handleInsertColRight = useCallback(() => {
    const col = contextMenu.col
    mutateActiveSheet((sheet) => {
      const nr = sheet.numRows || 50
      const nc = sheet.numCols || 26
      const newCells = reKeyCells(
        sheet.cells,
        nr,
        nc,
        (r) => r,
        (c) => (c > col ? c + 1 : c)
      )
      return { ...sheet, cells: newCells, numCols: nc + 1 }
    })
  }, [contextMenu.col, mutateActiveSheet, reKeyCells])

  const handleDeleteRow = useCallback(() => {
    const row = contextMenu.row
    mutateActiveSheet((sheet) => {
      const nr = sheet.numRows || 50
      const nc = sheet.numCols || 26
      const newCells = reKeyCells(
        sheet.cells,
        nr,
        nc,
        (r) => {
          if (r === row) return null
          return r > row ? r - 1 : r
        },
        (c) => c
      )
      return { ...sheet, cells: newCells, numRows: Math.max(1, nr - 1) }
    })
  }, [contextMenu.row, mutateActiveSheet, reKeyCells])

  const handleDeleteCol = useCallback(() => {
    const col = contextMenu.col
    mutateActiveSheet((sheet) => {
      const nr = sheet.numRows || 50
      const nc = sheet.numCols || 26
      const newCells = reKeyCells(
        sheet.cells,
        nr,
        nc,
        (r) => r,
        (c) => {
          if (c === col) return null
          return c > col ? c - 1 : c
        }
      )
      return { ...sheet, cells: newCells, numCols: Math.max(1, nc - 1) }
    })
  }, [contextMenu.col, mutateActiveSheet, reKeyCells])

  // ---------------------------------------------------------------------------
  // Hide/Unhide row/col
  // ---------------------------------------------------------------------------
  const handleHideRow = useCallback(() => {
    const row = contextMenu.row
    mutateActiveSheetSilent((sheet) => ({
      ...sheet,
      hiddenRows: [...(sheet.hiddenRows || []), row],
    }))
  }, [contextMenu.row, mutateActiveSheetSilent])

  const handleHideCol = useCallback(() => {
    const col = contextMenu.col
    mutateActiveSheetSilent((sheet) => ({
      ...sheet,
      hiddenCols: [...(sheet.hiddenCols || []), col],
    }))
  }, [contextMenu.col, mutateActiveSheetSilent])

  const handleUnhideRows = useCallback(() => {
    mutateActiveSheetSilent((sheet) => ({ ...sheet, hiddenRows: [] }))
  }, [mutateActiveSheetSilent])

  const handleUnhideCols = useCallback(() => {
    mutateActiveSheetSilent((sheet) => ({ ...sheet, hiddenCols: [] }))
  }, [mutateActiveSheetSilent])

  // ---------------------------------------------------------------------------
  // Clipboard: copy / cut / paste / clear
  // ---------------------------------------------------------------------------
  const getSelectionBounds = useCallback((): SelectionRange | null => {
    if (selectionRange) return normalizeRange(selectionRange)
    if (selectedCell) return { startRow: selectedCell.row, startCol: selectedCell.col, endRow: selectedCell.row, endCol: selectedCell.col }
    return null
  }, [selectionRange, selectedCell])

  const copyToClipboard = useCallback(async () => {
    const bounds = getSelectionBounds()
    if (!bounds) return
    const lines: string[] = []
    for (let r = bounds.startRow; r <= bounds.endRow; r++) {
      const cols: string[] = []
      for (let c = bounds.startCol; c <= bounds.endCol; c++) {
        cols.push(getCellDisplayValue(r, c))
      }
      lines.push(cols.join('\t'))
    }
    try {
      await navigator.clipboard.writeText(lines.join('\n'))
    } catch {
      // Clipboard API may not be available
    }
  }, [getSelectionBounds, getCellDisplayValue])

  const cutToClipboard = useCallback(async () => {
    await copyToClipboard()
    const bounds = getSelectionBounds()
    if (!bounds) return
    mutateActiveSheet((sheet) => {
      const cells = { ...sheet.cells }
      for (let r = bounds.startRow; r <= bounds.endRow; r++) {
        for (let c = bounds.startCol; c <= bounds.endCol; c++) {
          const key = cellId(r, c)
          if (cells[key]) {
            cells[key] = { ...cells[key], value: '' }
          }
        }
      }
      return { ...sheet, cells }
    })
  }, [copyToClipboard, getSelectionBounds, mutateActiveSheet])

  const pasteFromClipboard = useCallback(async () => {
    if (!selectedCell) return
    try {
      const text = await navigator.clipboard.readText()
      const lines = text.split('\n')
      mutateActiveSheet((sheet) => {
        const cells = { ...sheet.cells }
        lines.forEach((line, rowOffset) => {
          const cols = line.split('\t')
          cols.forEach((val, colOffset) => {
            const r = selectedCell.row + rowOffset
            const c = selectedCell.col + colOffset
            const key = cellId(r, c)
            const existing = cells[key] || { value: '' }
            cells[key] = { ...existing, value: val }
          })
        })
        return { ...sheet, cells }
      })
    } catch {
      // Clipboard API may not be available
    }
  }, [selectedCell, mutateActiveSheet])

  const clearSelection = useCallback(() => {
    const bounds = getSelectionBounds()
    if (!bounds) return
    mutateActiveSheet((sheet) => {
      const cells = { ...sheet.cells }
      for (let r = bounds.startRow; r <= bounds.endRow; r++) {
        for (let c = bounds.startCol; c <= bounds.endCol; c++) {
          const key = cellId(r, c)
          if (cells[key]) {
            cells[key] = { ...cells[key], value: '' }
          }
        }
      }
      return { ...sheet, cells }
    })
  }, [getSelectionBounds, mutateActiveSheet])

  // ---------------------------------------------------------------------------
  // Find & Replace handlers
  // ---------------------------------------------------------------------------
  const handleNavigateToCell = useCallback(
    (row: number, col: number) => {
      setSelectedCell({ row, col })
      setSelectionRange(null)
      setFormulaBarValue(activeSheet.cells[cellId(row, col)]?.value || '')
    },
    [activeSheet.cells]
  )

  const handleFindReplace = useCallback(
    (cellKey: string, oldValue: string, newValue: string) => {
      mutateActiveSheet((sheet) => {
        const cells = { ...sheet.cells }
        const data = cells[cellKey]
        if (!data) return sheet
        const updated = data.value.replace(oldValue, newValue)
        cells[cellKey] = { ...data, value: updated }
        return { ...sheet, cells }
      })
    },
    [mutateActiveSheet]
  )

  const handleFindReplaceAll = useCallback(
    (oldValue: string, newValue: string) => {
      mutateActiveSheet((sheet) => {
        const cells = { ...sheet.cells }
        for (const [key, data] of Object.entries(cells)) {
          if (data.value.includes(oldValue)) {
            cells[key] = { ...data, value: data.value.split(oldValue).join(newValue) }
          }
        }
        return { ...sheet, cells }
      })
    },
    [mutateActiveSheet]
  )

  // ---------------------------------------------------------------------------
  // CSV export / import
  // ---------------------------------------------------------------------------
  const handleExportCsv = useCallback(() => {
    const lines: string[] = []
    for (let r = 0; r < numRows; r++) {
      const cols: string[] = []
      for (let c = 0; c < numCols; c++) {
        const val = getCellDisplayValue(r, c)
        // Escape commas and quotes
        if (val.includes(',') || val.includes('"') || val.includes('\n')) {
          cols.push(`"${val.replace(/"/g, '""')}"`)
        } else {
          cols.push(val)
        }
      }
      lines.push(cols.join(','))
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${doc?.title || 'spreadsheet'}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }, [numRows, numCols, getCellDisplayValue, doc?.title])

  const handleImportCsv = useCallback(() => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.csv'
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (!file) return
      const reader = new FileReader()
      reader.onload = (ev) => {
        const text = ev.target?.result as string
        if (!text) return
        const lines = text.split('\n')
        mutateActiveSheet((sheet) => {
          const cells = { ...sheet.cells }
          lines.forEach((line, r) => {
            // Simple CSV parse (handles quoted fields)
            const cols: string[] = []
            let current = ''
            let inQuotes = false
            for (let i = 0; i < line.length; i++) {
              const ch = line[i]
              if (inQuotes) {
                if (ch === '"' && i + 1 < line.length && line[i + 1] === '"') {
                  current += '"'
                  i++
                } else if (ch === '"') {
                  inQuotes = false
                } else {
                  current += ch
                }
              } else {
                if (ch === '"') {
                  inQuotes = true
                } else if (ch === ',') {
                  cols.push(current)
                  current = ''
                } else {
                  current += ch
                }
              }
            }
            cols.push(current)

            cols.forEach((val, c) => {
              const key = cellId(r, c)
              const existing = cells[key] || { value: '' }
              cells[key] = { ...existing, value: val.trim() }
            })
          })
          return {
            ...sheet,
            cells,
            numRows: Math.max(sheet.numRows || 50, lines.length),
            numCols: Math.max(sheet.numCols || 26, Math.max(...lines.map((l) => l.split(',').length))),
          }
        })
      }
      reader.readAsText(file)
    }
    input.click()
  }, [mutateActiveSheet])

  // ---------------------------------------------------------------------------
  // Insert chart (placeholder)
  // ---------------------------------------------------------------------------
  const handleInsertChart = useCallback(() => {
    // Chart functionality placeholder
  }, [])

  // ---------------------------------------------------------------------------
  // Sheet tabs
  // ---------------------------------------------------------------------------
  const addSheet = useCallback(() => {
    setSheets((prev) => {
      pushHistory(prev)
      const updated = [...prev, { name: `Sheet${prev.length + 1}`, cells: {} }]
      debouncedSave(updated)
      return updated
    })
    setActiveSheetIndex(sheets.length)
  }, [sheets.length, pushHistory, debouncedSave])

  const handleRenameSheet = useCallback(
    (index: number, name: string) => {
      mutateSheets((prev) => {
        const updated = [...prev]
        updated[index] = { ...updated[index], name }
        return updated
      })
    },
    [mutateSheets]
  )

  // ---------------------------------------------------------------------------
  // Cell click / double-click / edit
  // ---------------------------------------------------------------------------
  const handleCellClick = useCallback(
    (row: number, col: number, e: React.MouseEvent) => {
      if (e.shiftKey && selectedCell) {
        // Extend selection
        setSelectionRange({
          startRow: selectedCell.row,
          startCol: selectedCell.col,
          endRow: row,
          endCol: col,
        })
      } else {
        setSelectedCell({ row, col })
        setSelectionRange(null)
      }
      setFormulaBarValue(activeSheet.cells[cellId(row, col)]?.value || '')
      setEditingCell(null)
    },
    [selectedCell, activeSheet.cells]
  )

  const handleCellDoubleClick = useCallback(
    (row: number, col: number) => {
      setEditingCell({ row, col })
      setSelectedCell({ row, col })
      setSelectionRange(null)
      setFormulaBarValue(activeSheet.cells[cellId(row, col)]?.value || '')
      setTimeout(() => {
        const key = cellId(row, col)
        cellRefs.current[key]?.focus()
      }, 0)
    },
    [activeSheet.cells]
  )

  const handleCellInputChange = useCallback(
    (row: number, col: number, value: string) => {
      setCellValueSilent(row, col, value)
      setFormulaBarValue(value)
    },
    [setCellValueSilent]
  )

  const handleCellBlur = useCallback(() => {
    if (editingCell) {
      // Push history on blur (commit the edit)
      pushHistory(sheets)
    }
    setEditingCell(null)
  }, [editingCell, pushHistory, sheets])

  const handleCellKeyDown = useCallback(
    (e: React.KeyboardEvent, row: number, col: number) => {
      if (e.key === 'Enter') {
        e.preventDefault()
        pushHistory(sheets)
        setEditingCell(null)
        const nextRow = Math.min(row + 1, numRows - 1)
        setSelectedCell({ row: nextRow, col })
        setFormulaBarValue(activeSheet.cells[cellId(nextRow, col)]?.value || '')
      } else if (e.key === 'Tab') {
        e.preventDefault()
        pushHistory(sheets)
        setEditingCell(null)
        const nextCol = e.shiftKey ? Math.max(col - 1, 0) : Math.min(col + 1, numCols - 1)
        setSelectedCell({ row, col: nextCol })
        setFormulaBarValue(activeSheet.cells[cellId(row, nextCol)]?.value || '')
      } else if (e.key === 'Escape') {
        setEditingCell(null)
      }
    },
    [numRows, numCols, activeSheet.cells, pushHistory, sheets]
  )

  const handleFormulaBarChange = useCallback(
    (value: string) => {
      setFormulaBarValue(value)
      if (selectedCell) {
        setCellValueSilent(selectedCell.row, selectedCell.col, value)
      }
    },
    [selectedCell, setCellValueSilent]
  )

  const handleFormulaBarKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault()
        pushHistory(sheets)
        if (selectedCell) {
          const nextRow = Math.min(selectedCell.row + 1, numRows - 1)
          setSelectedCell({ row: nextRow, col: selectedCell.col })
          setFormulaBarValue(activeSheet.cells[cellId(nextRow, selectedCell.col)]?.value || '')
        }
      } else if (e.key === 'Escape') {
        gridRef.current?.focus()
      }
    },
    [selectedCell, numRows, activeSheet.cells, pushHistory, sheets]
  )

  // ---------------------------------------------------------------------------
  // Grid keyboard navigation
  // ---------------------------------------------------------------------------
  const handleGridKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (editingCell) return
      if (!selectedCell) return

      const { row, col } = selectedCell
      const ctrlOrMeta = e.ctrlKey || e.metaKey

      // Ctrl shortcuts
      if (ctrlOrMeta) {
        switch (e.key.toLowerCase()) {
          case 'z':
            e.preventDefault()
            if (e.shiftKey) {
              redo()
            } else {
              undo()
            }
            return
          case 'y':
            e.preventDefault()
            redo()
            return
          case 'c':
            e.preventDefault()
            copyToClipboard()
            return
          case 'x':
            e.preventDefault()
            cutToClipboard()
            return
          case 'v':
            e.preventDefault()
            pasteFromClipboard()
            return
          case 'a':
            e.preventDefault()
            setSelectionRange({ startRow: 0, startCol: 0, endRow: numRows - 1, endCol: numCols - 1 })
            return
          case 'b':
            e.preventDefault()
            handleToggleFormat('bold')
            return
          case 'i':
            e.preventDefault()
            handleToggleFormat('italic')
            return
          case 'u':
            e.preventDefault()
            handleToggleFormat('underline')
            return
          case 'f':
            e.preventDefault()
            setShowFindReplace(true)
            return
          case 'h':
            e.preventDefault()
            setShowFindReplace(true)
            return
        }
      }

      // Arrow keys
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        let newRow = Math.max(0, row - 1)
        while (newRow > 0 && filteredHiddenRows.has(newRow)) newRow--
        if (e.shiftKey) {
          setSelectionRange((prev) => ({
            startRow: prev?.startRow ?? row,
            startCol: prev?.startCol ?? col,
            endRow: newRow,
            endCol: prev?.endCol ?? col,
          }))
        } else {
          setSelectedCell({ row: newRow, col })
          setSelectionRange(null)
        }
        setFormulaBarValue(activeSheet.cells[cellId(newRow, col)]?.value || '')
      } else if (e.key === 'ArrowDown') {
        e.preventDefault()
        let newRow = Math.min(numRows - 1, row + 1)
        while (newRow < numRows - 1 && filteredHiddenRows.has(newRow)) newRow++
        if (e.shiftKey) {
          setSelectionRange((prev) => ({
            startRow: prev?.startRow ?? row,
            startCol: prev?.startCol ?? col,
            endRow: newRow,
            endCol: prev?.endCol ?? col,
          }))
        } else {
          setSelectedCell({ row: newRow, col })
          setSelectionRange(null)
        }
        setFormulaBarValue(activeSheet.cells[cellId(newRow, col)]?.value || '')
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        let newCol = Math.max(0, col - 1)
        while (newCol > 0 && hiddenCols.has(newCol)) newCol--
        if (e.shiftKey) {
          setSelectionRange((prev) => ({
            startRow: prev?.startRow ?? row,
            startCol: prev?.startCol ?? col,
            endRow: prev?.endRow ?? row,
            endCol: newCol,
          }))
        } else {
          setSelectedCell({ row, col: newCol })
          setSelectionRange(null)
        }
        setFormulaBarValue(activeSheet.cells[cellId(row, newCol)]?.value || '')
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        let newCol = Math.min(numCols - 1, col + 1)
        while (newCol < numCols - 1 && hiddenCols.has(newCol)) newCol++
        if (e.shiftKey) {
          setSelectionRange((prev) => ({
            startRow: prev?.startRow ?? row,
            startCol: prev?.startCol ?? col,
            endRow: prev?.endRow ?? row,
            endCol: newCol,
          }))
        } else {
          setSelectedCell({ row, col: newCol })
          setSelectionRange(null)
        }
        setFormulaBarValue(activeSheet.cells[cellId(row, newCol)]?.value || '')
      } else if (e.key === 'Enter' || e.key === 'F2') {
        e.preventDefault()
        handleCellDoubleClick(row, col)
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault()
        clearSelection()
        setFormulaBarValue('')
      } else if (e.key.length === 1 && !ctrlOrMeta) {
        // Start typing in cell
        setCellValue(row, col, e.key)
        setFormulaBarValue(e.key)
        setEditingCell({ row, col })
        setTimeout(() => {
          const key = cellId(row, col)
          const input = cellRefs.current[key]
          if (input) {
            input.focus()
            input.setSelectionRange(1, 1)
          }
        }, 0)
      }
    },
    [
      editingCell,
      selectedCell,
      numRows,
      numCols,
      activeSheet.cells,
      filteredHiddenRows,
      hiddenCols,
      undo,
      redo,
      copyToClipboard,
      cutToClipboard,
      pasteFromClipboard,
      handleToggleFormat,
      handleCellDoubleClick,
      clearSelection,
      setCellValue,
    ]
  )

  // ---------------------------------------------------------------------------
  // Mouse drag selection
  // ---------------------------------------------------------------------------
  const handleCellMouseDown = useCallback(
    (row: number, col: number, e: React.MouseEvent) => {
      if (e.button !== 0) return // Only left click
      isDraggingSelection.current = true
      if (!e.shiftKey) {
        setSelectionRange({ startRow: row, startCol: col, endRow: row, endCol: col })
      }
    },
    []
  )

  const handleCellMouseEnter = useCallback(
    (row: number, col: number) => {
      if (isDraggingSelection.current) {
        setSelectionRange((prev) =>
          prev ? { ...prev, endRow: row, endCol: col } : null
        )
      }
      if (isDraggingFill.current) {
        setAutoFillTarget({ row, col })
      }
    },
    []
  )

  // Global mouse up to stop drag
  useEffect(() => {
    const handleMouseUp = () => {
      if (isDraggingSelection.current) {
        isDraggingSelection.current = false
      }
      if (isDraggingFill.current) {
        isDraggingFill.current = false
        // Execute autofill
        if (selectedCell && autoFillTarget) {
          performAutoFill(selectedCell, autoFillTarget)
        }
        setAutoFillTarget(null)
      }
    }
    window.addEventListener('mouseup', handleMouseUp)
    return () => window.removeEventListener('mouseup', handleMouseUp)
  }, [selectedCell, autoFillTarget]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // Auto-fill logic
  // ---------------------------------------------------------------------------
  const performAutoFill = useCallback(
    (origin: { row: number; col: number }, target: { row: number; col: number }) => {
      const originKey = cellId(origin.row, origin.col)
      const originData = activeSheet.cells[originKey]
      if (!originData) return
      const originVal = originData.value

      mutateActiveSheet((sheet) => {
        const cells = { ...sheet.cells }

        // Determine direction and range
        const isVertical = target.col === origin.col
        const isHorizontal = target.row === origin.row

        if (isVertical) {
          const start = Math.min(origin.row, target.row)
          const end = Math.max(origin.row, target.row)
          const direction = target.row > origin.row ? 1 : -1
          for (let r = start; r <= end; r++) {
            if (r === origin.row) continue
            const key = cellId(r, origin.col)
            const offset = (r - origin.row) * direction
            let fillVal = originVal
            // Number increment
            if (isNumeric(originVal)) {
              fillVal = String(parseNumeric(originVal)! + offset)
            } else if (originVal.startsWith('=')) {
              // Adjust row references in formula
              fillVal = adjustFormulaRefs(originVal, r - origin.row, 0)
            }
            cells[key] = { ...originData, value: fillVal }
          }
        } else if (isHorizontal) {
          const start = Math.min(origin.col, target.col)
          const end = Math.max(origin.col, target.col)
          const direction = target.col > origin.col ? 1 : -1
          for (let c = start; c <= end; c++) {
            if (c === origin.col) continue
            const key = cellId(origin.row, c)
            const offset = (c - origin.col) * direction
            let fillVal = originVal
            if (isNumeric(originVal)) {
              fillVal = String(parseNumeric(originVal)! + offset)
            } else if (originVal.startsWith('=')) {
              fillVal = adjustFormulaRefs(originVal, 0, c - origin.col)
            }
            cells[key] = { ...originData, value: fillVal }
          }
        } else {
          // Diagonal / general: just copy
          const startR = Math.min(origin.row, target.row)
          const endR = Math.max(origin.row, target.row)
          const startC = Math.min(origin.col, target.col)
          const endC = Math.max(origin.col, target.col)
          for (let r = startR; r <= endR; r++) {
            for (let c = startC; c <= endC; c++) {
              if (r === origin.row && c === origin.col) continue
              const key = cellId(r, c)
              cells[key] = { ...originData }
            }
          }
        }

        return { ...sheet, cells }
      })
    },
    [activeSheet.cells, mutateActiveSheet]
  )

  // Adjust cell references in a formula by row/col offset
  function adjustFormulaRefs(formula: string, rowDelta: number, colDelta: number): string {
    return formula.replace(/([A-Z]+)(\d+)/g, (_match, colStr: string, rowStr: string) => {
      const ref = parseCellRef(colStr + rowStr)
      if (!ref) return colStr + rowStr
      const newRow = ref.row + rowDelta
      const newCol = ref.col + colDelta
      if (newRow < 0 || newCol < 0) return colStr + rowStr
      return cellId(newRow, newCol)
    })
  }

  // ---------------------------------------------------------------------------
  // Column / Row resize
  // ---------------------------------------------------------------------------
  const handleColResizeStart = useCallback(
    (col: number, e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setResizingCol({ col, startX: e.clientX, startWidth: getColWidth(col) })
    },
    [getColWidth]
  )

  const handleRowResizeStart = useCallback(
    (row: number, e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setResizingRow({ row, startY: e.clientY, startHeight: getRowHeight(row) })
    },
    [getRowHeight]
  )

  const handleColResizeDoubleClick = useCallback(
    (col: number, e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      // Auto-fit: estimate width from longest content
      let maxLen = 3
      for (let r = 0; r < numRows; r++) {
        const key = cellId(r, col)
        const val = activeSheet.cells[key]?.value || ''
        maxLen = Math.max(maxLen, val.length)
      }
      const estimatedWidth = Math.max(MIN_COL_WIDTH, Math.min(maxLen * 9 + 16, 400))
      mutateActiveSheetSilent((sheet) => ({
        ...sheet,
        colWidths: { ...sheet.colWidths, [col]: estimatedWidth },
      }))
    },
    [numRows, activeSheet.cells, mutateActiveSheetSilent]
  )

  const handleRowResizeDoubleClick = useCallback(
    (row: number, e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      mutateActiveSheetSilent((sheet) => ({
        ...sheet,
        rowHeights: { ...sheet.rowHeights, [row]: DEFAULT_ROW_HEIGHT },
      }))
    },
    [mutateActiveSheetSilent]
  )

  // Global mouse move/up for resize
  useEffect(() => {
    if (!resizingCol && !resizingRow) return

    const handleMouseMove = (e: MouseEvent) => {
      if (resizingCol) {
        const delta = e.clientX - resizingCol.startX
        const newWidth = Math.max(MIN_COL_WIDTH, resizingCol.startWidth + delta)
        mutateActiveSheetSilent((sheet) => ({
          ...sheet,
          colWidths: { ...sheet.colWidths, [resizingCol.col]: newWidth },
        }))
      }
      if (resizingRow) {
        const delta = e.clientY - resizingRow.startY
        const newHeight = Math.max(MIN_ROW_HEIGHT, resizingRow.startHeight + delta)
        mutateActiveSheetSilent((sheet) => ({
          ...sheet,
          rowHeights: { ...sheet.rowHeights, [resizingRow.row]: newHeight },
        }))
      }
    }

    const handleMouseUp = () => {
      setResizingCol(null)
      setResizingRow(null)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [resizingCol, resizingRow, mutateActiveSheetSilent])

  // ---------------------------------------------------------------------------
  // Context menu
  // ---------------------------------------------------------------------------
  const handleContextMenu = useCallback((e: React.MouseEvent, row: number, col: number) => {
    e.preventDefault()
    setContextMenu({ visible: true, x: e.clientX, y: e.clientY, row, col })
    setSelectedCell({ row, col })
  }, [])

  const closeContextMenu = useCallback(() => {
    setContextMenu((prev) => ({ ...prev, visible: false }))
  }, [])

  // ---------------------------------------------------------------------------
  // Title change
  // ---------------------------------------------------------------------------
  const handleTitleChange = useCallback(
    (title: string) => {
      updateMutation.mutate({ title })
    },
    [updateMutation]
  )

  // ---------------------------------------------------------------------------
  // Computed values for toolbar
  // ---------------------------------------------------------------------------
  const selectedCellData = useMemo(() => {
    if (!selectedCell) return null
    return getCellData(selectedCell.row, selectedCell.col)
  }, [selectedCell, getCellData])

  // ---------------------------------------------------------------------------
  // Compute frozen offsets for sticky positioning
  // ---------------------------------------------------------------------------
  // ---------------------------------------------------------------------------
  // Build cell style
  // ---------------------------------------------------------------------------
  const buildCellStyle = useCallback(
    (data: CellData, colWidth: number, rowHeight: number): React.CSSProperties => {
      const style: React.CSSProperties = {
        width: colWidth,
        minWidth: colWidth,
        maxWidth: colWidth,
        height: rowHeight,
      }
      if (data.bgColor) style.backgroundColor = data.bgColor
      if (data.textColor) style.color = data.textColor
      if (data.bold) style.fontWeight = 'bold'
      if (data.italic) style.fontStyle = 'italic'
      if (data.underline) style.textDecoration = (style.textDecoration || '') + ' underline'
      if (data.strikethrough) style.textDecoration = (style.textDecoration || '') + ' line-through'
      if (data.align) style.textAlign = data.align
      if (data.fontSize) style.fontSize = `${data.fontSize}px`
      return style
    },
    []
  )

  const buildCellBorderClasses = useCallback(
    (data: CellData): string => {
      const parts: string[] = []
      if (data.borders?.top) parts.push('border-t-2 border-t-gray-800 dark:border-t-gray-300')
      if (data.borders?.bottom) parts.push('border-b-2 border-b-gray-800 dark:border-b-gray-300')
      if (data.borders?.left) parts.push('border-l-2 border-l-gray-800 dark:border-l-gray-300')
      if (data.borders?.right) parts.push('border-r-2 border-r-gray-800 dark:border-r-gray-300')
      return parts.join(' ')
    },
    []
  )

  // ---------------------------------------------------------------------------
  // Auto-fill handle coordinates
  // ---------------------------------------------------------------------------
  const autoFillHighlight = useMemo(() => {
    if (!selectedCell || !autoFillTarget) return null
    return normalizeRange({
      startRow: Math.min(selectedCell.row, autoFillTarget.row),
      startCol: Math.min(selectedCell.col, autoFillTarget.col),
      endRow: Math.max(selectedCell.row, autoFillTarget.row),
      endCol: Math.max(selectedCell.col, autoFillTarget.col),
    })
  }, [selectedCell, autoFillTarget])

  // ---------------------------------------------------------------------------
  // Filter dropdown
  // ---------------------------------------------------------------------------
  const filterDropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!filterDropdown) return
    const handleClick = (e: MouseEvent) => {
      if (filterDropdownRef.current && !filterDropdownRef.current.contains(e.target as Node)) {
        setFilterDropdown(null)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [filterDropdown])

  // ---------------------------------------------------------------------------
  // Sheet tab rename
  // ---------------------------------------------------------------------------
  const [renamingSheet, setRenamingSheet] = useState<number | null>(null)
  const [renameValue, setRenameValue] = useState('')

  // ---------------------------------------------------------------------------
  // Render guard
  // ---------------------------------------------------------------------------
  if (!id) return null

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="flex flex-col h-[calc(100vh-49px)] bg-white dark:bg-gray-900">
      {/* 1. Editor top bar */}
      <EditorTopBar
        docType="spreadsheet"
        docId={id}
        title={doc?.title || 'Untitled spreadsheet'}
        isStarred={doc?.is_starred ?? false}
        onTitleChange={handleTitleChange}
        onStar={() => starMutation.mutate()}
        connectedUsers={connectedUsers}
        connectionStatus={connectionStatus}
      />

      {/* 2. Sheet toolbar */}
      <SheetToolbar
        selectedCellData={selectedCellData}
        selectionRange={selectionRange}
        onToggleFormat={handleToggleFormat}
        onSetBgColor={handleSetBgColor}
        onSetTextColor={handleSetTextColor}
        onSetAlign={handleSetAlign}
        onSetFormat={handleSetFormat}
        onSetFontSize={handleSetFontSize}
        onClearFormatting={handleClearFormatting}
        onMergeCells={handleMergeCells}
        onUnmergeCells={handleUnmergeCells}
        isMerged={isAnyCellMerged}
        onUndo={undo}
        onRedo={redo}
        canUndo={canUndo}
        canRedo={canRedo}
        onSetBorders={handleSetBorders}
        onInsertChart={handleInsertChart}
        onToggleFilter={handleToggleFilter}
        filterEnabled={filterEnabled}
        onSort={handleSort}
        onExportCsv={handleExportCsv}
        onImportCsv={handleImportCsv}
        onToggleFindReplace={() => setShowFindReplace((p) => !p)}
        onFreezeRow={handleFreezeRow}
        onFreezeCol={handleFreezeCol}
        freezeRow={freezeRow}
        freezeCol={freezeCol}
      />

      {/* 3. Formula bar */}
      <div className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-3 py-1 flex items-center gap-2">
        <div className="w-16 text-center text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded px-2 py-1 border border-gray-300 dark:border-gray-600">
          {selectedCell ? cellId(selectedCell.row, selectedCell.col) : ''}
        </div>
        <div className="text-gray-300 dark:text-gray-600 select-none">|</div>
        <input
          type="text"
          value={formulaBarValue}
          onChange={(e) => handleFormulaBarChange(e.target.value)}
          onKeyDown={handleFormulaBarKeyDown}
          onBlur={() => {
            if (editingCell) {
              pushHistory(sheets)
            }
          }}
          placeholder="Enter value or formula..."
          className="flex-1 text-sm px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-green-500 dark:focus:ring-green-600"
        />
      </div>

      {/* 4. Find & Replace bar */}
      <SheetFindReplace
        visible={showFindReplace}
        onClose={() => setShowFindReplace(false)}
        cells={activeSheet.cells}
        onNavigateToCell={handleNavigateToCell}
        onReplace={handleFindReplace}
        onReplaceAll={handleFindReplaceAll}
      />

      {/* 5. Grid */}
      <div
        ref={gridRef}
        className="flex-1 overflow-auto relative focus:outline-none"
        tabIndex={0}
        onKeyDown={handleGridKeyDown}
      >
        <table
          className="border-collapse table-fixed"
          style={{
            minWidth:
              ROW_NUM_WIDTH +
              Array.from({ length: numCols }, (_, c) =>
                hiddenCols.has(c) ? 0 : getColWidth(c)
              ).reduce((a, b) => a + b, 0),
          }}
        >
          {/* Column headers */}
          <thead className="sticky top-0 z-20">
            <tr>
              {/* Top-left corner cell */}
              <th
                className="bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-xs text-gray-500 dark:text-gray-400 sticky left-0 z-30 select-none"
                style={{
                  width: ROW_NUM_WIDTH,
                  minWidth: ROW_NUM_WIDTH,
                  height: DEFAULT_ROW_HEIGHT,
                }}
              />
              {Array.from({ length: numCols }, (_, col) => {
                if (hiddenCols.has(col)) return null
                const w = getColWidth(col)
                const isFrozen = col < freezeCol
                const isFreezeEdge = col === freezeCol - 1

                return (
                  <th
                    key={col}
                    className={cn(
                      'bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-xs font-medium text-gray-600 dark:text-gray-400 select-none relative group',
                      selectedCell?.col === col && 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400',
                      isFrozen && 'sticky z-30',
                      isFreezeEdge && 'border-r-2 border-r-blue-500 dark:border-r-blue-400'
                    )}
                    style={{
                      width: w,
                      minWidth: w,
                      height: DEFAULT_ROW_HEIGHT,
                      ...(isFrozen
                        ? {
                            left:
                              ROW_NUM_WIDTH +
                              Array.from({ length: col }, (_, c) =>
                                hiddenCols.has(c) ? 0 : getColWidth(c)
                              ).reduce((a, b) => a + b, 0),
                          }
                        : {}),
                    }}
                  >
                    <span className="flex items-center justify-center h-full">
                      {colLabel(col)}
                      {/* Filter dropdown trigger */}
                      {filterEnabled && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            const rect = (e.target as HTMLElement).closest('th')?.getBoundingClientRect()
                            setFilterDropdown(
                              filterDropdown?.col === col
                                ? null
                                : { col, x: rect?.left ?? 0, y: (rect?.bottom ?? 0) }
                            )
                          }}
                          className="ml-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <ChevronDown className="h-3 w-3" />
                        </button>
                      )}
                    </span>
                    {/* Resize handle */}
                    <div
                      className="absolute right-0 top-0 w-1 h-full cursor-col-resize hover:bg-blue-500 dark:hover:bg-blue-400 z-10"
                      onMouseDown={(e) => handleColResizeStart(col, e)}
                      onDoubleClick={(e) => handleColResizeDoubleClick(col, e)}
                    />
                  </th>
                )
              })}
            </tr>
          </thead>

          <tbody>
            {Array.from({ length: numRows }, (_, row) => {
              if (filteredHiddenRows.has(row)) return null

              const rh = getRowHeight(row)
              const isFrozenRow = row < freezeRow
              const isFreezeRowEdge = row === freezeRow - 1

              // Compute sticky top for frozen rows
              let frozenTop: number | undefined
              if (isFrozenRow) {
                frozenTop =
                  DEFAULT_ROW_HEIGHT + // header row height
                  Array.from({ length: row }, (_, r) =>
                    filteredHiddenRows.has(r) ? 0 : getRowHeight(r)
                  ).reduce((a, b) => a + b, 0)
              }

              return (
                <tr
                  key={row}
                  className={cn(
                    isFrozenRow && 'sticky z-10',
                    isFreezeRowEdge && 'border-b-2 border-b-blue-500 dark:border-b-blue-400'
                  )}
                  style={isFrozenRow ? { top: frozenTop } : undefined}
                >
                  {/* Row number */}
                  <td
                    className={cn(
                      'bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-xs text-center text-gray-600 dark:text-gray-400 select-none sticky left-0 relative group',
                      isFrozenRow ? 'z-20' : 'z-10',
                      selectedCell?.row === row && 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400'
                    )}
                    style={{
                      width: ROW_NUM_WIDTH,
                      minWidth: ROW_NUM_WIDTH,
                      height: rh,
                    }}
                  >
                    {row + 1}
                    {/* Row resize handle */}
                    <div
                      className="absolute bottom-0 left-0 w-full h-1 cursor-row-resize hover:bg-blue-500 dark:hover:bg-blue-400 z-10"
                      onMouseDown={(e) => handleRowResizeStart(row, e)}
                      onDoubleClick={(e) => handleRowResizeDoubleClick(row, e)}
                    />
                  </td>

                  {/* Data cells */}
                  {Array.from({ length: numCols }, (_, col) => {
                    if (hiddenCols.has(col)) return null

                    // Merged cell handling
                    if (isMergeCovered(row, col)) return null

                    const merge = getMergeForCell(row, col)
                    let colSpan = 1
                    let rowSpan = 1
                    if (merge && isMergeOrigin(row, col)) {
                      colSpan = merge.endCol - merge.startCol + 1
                      rowSpan = merge.endRow - merge.startRow + 1
                    }

                    const isSelected = selectedCell?.row === row && selectedCell?.col === col
                    const isEditing = editingCell?.row === row && editingCell?.col === col
                    const isInSelection = inRange(row, col, selectionRange)
                    const isInAutoFill = autoFillHighlight ? inRange(row, col, autoFillHighlight) : false
                    const data = getCellData(row, col)
                    const key = cellId(row, col)
                    const w = getColWidth(col)

                    const isFrozenCol = col < freezeCol
                    const isFreezeColEdge = col === freezeCol - 1

                    // Sticky position for frozen columns
                    let stickyLeft: number | undefined
                    if (isFrozenCol) {
                      stickyLeft =
                        ROW_NUM_WIDTH +
                        Array.from({ length: col }, (_, c) =>
                          hiddenCols.has(c) ? 0 : getColWidth(c)
                        ).reduce((a, b) => a + b, 0)
                    }

                    const cellStyle = buildCellStyle(data, w, rh)
                    if (isFrozenCol) {
                      cellStyle.position = 'sticky'
                      cellStyle.left = stickyLeft
                    }

                    const displayValue = isEditing ? data.value : getCellDisplayValue(row, col)

                    return (
                      <td
                        key={col}
                        colSpan={colSpan > 1 ? colSpan : undefined}
                        rowSpan={rowSpan > 1 ? rowSpan : undefined}
                        className={cn(
                          'border border-gray-200 dark:border-gray-700 p-0 relative overflow-hidden',
                          isSelected && 'outline outline-2 outline-blue-500 dark:outline-blue-400 outline-offset-[-1px] z-[5]',
                          isInSelection && !isSelected && 'bg-blue-50 dark:bg-blue-900/20',
                          isInAutoFill && !isSelected && 'bg-blue-100/50 dark:bg-blue-800/30',
                          isFrozenCol && (isFrozenRow ? 'z-20' : 'z-10'),
                          isFreezeColEdge && 'border-r-2 border-r-blue-500 dark:border-r-blue-400',
                          buildCellBorderClasses(data)
                        )}
                        style={cellStyle}
                        onClick={(e) => handleCellClick(row, col, e)}
                        onDoubleClick={() => handleCellDoubleClick(row, col)}
                        onMouseDown={(e) => handleCellMouseDown(row, col, e)}
                        onMouseEnter={() => handleCellMouseEnter(row, col)}
                        onContextMenu={(e) => handleContextMenu(e, row, col)}
                      >
                        {isEditing ? (
                          <input
                            ref={(el) => {
                              cellRefs.current[key] = el
                            }}
                            type="text"
                            value={data.value}
                            onChange={(e) => handleCellInputChange(row, col, e.target.value)}
                            onBlur={handleCellBlur}
                            onKeyDown={(e) => handleCellKeyDown(e, row, col)}
                            className="w-full h-full px-1 text-sm outline-none border-none bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
                            style={{
                              fontWeight: data.bold ? 'bold' : undefined,
                              fontStyle: data.italic ? 'italic' : undefined,
                              fontSize: data.fontSize ? `${data.fontSize}px` : undefined,
                              textAlign: data.align || undefined,
                              color: data.textColor || undefined,
                            }}
                          />
                        ) : (
                          <div
                            className="w-full h-full px-1 text-sm truncate flex items-center"
                            style={{
                              justifyContent:
                                data.align === 'center'
                                  ? 'center'
                                  : data.align === 'right'
                                    ? 'flex-end'
                                    : 'flex-start',
                            }}
                          >
                            {displayValue}
                          </div>
                        )}

                        {/* Auto-fill handle */}
                        {isSelected && !isEditing && (
                          <div
                            className="absolute bottom-0 right-0 w-2 h-2 bg-blue-500 dark:bg-blue-400 cursor-crosshair z-10 border border-white dark:border-gray-900"
                            style={{ transform: 'translate(50%, 50%)' }}
                            onMouseDown={(e) => {
                              e.preventDefault()
                              e.stopPropagation()
                              isDraggingFill.current = true
                            }}
                          />
                        )}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* 6. Sheet tabs */}
      <div className="bg-gray-100 dark:bg-gray-800 border-t border-gray-300 dark:border-gray-700 px-2 py-1 flex items-center gap-1">
        {sheets.map((sheet, index) => (
          <button
            key={index}
            onClick={() => {
              setActiveSheetIndex(index)
              setSelectedCell(null)
              setEditingCell(null)
              setSelectionRange(null)
              setFormulaBarValue('')
            }}
            onDoubleClick={() => {
              setRenamingSheet(index)
              setRenameValue(sheet.name)
            }}
            className={cn(
              'px-3 py-1 text-sm rounded-t border border-b-0 transition-colors min-w-[60px]',
              activeSheetIndex === index
                ? 'bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 font-medium border-gray-300 dark:border-gray-600'
                : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-600 border-transparent'
            )}
          >
            {renamingSheet === index ? (
              <input
                type="text"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onBlur={() => {
                  if (renameValue.trim()) handleRenameSheet(index, renameValue.trim())
                  setRenamingSheet(null)
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    if (renameValue.trim()) handleRenameSheet(index, renameValue.trim())
                    setRenamingSheet(null)
                  } else if (e.key === 'Escape') {
                    setRenamingSheet(null)
                  }
                }}
                className="w-16 px-1 text-sm bg-white dark:bg-gray-900 border border-blue-400 rounded outline-none text-gray-900 dark:text-gray-100"
                autoFocus
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              sheet.name
            )}
          </button>
        ))}
        <button
          onClick={addSheet}
          className="p-1 rounded text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-200"
          title="Add sheet"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* 7. Context menu */}
      <SheetContextMenu
        x={contextMenu.x}
        y={contextMenu.y}
        visible={contextMenu.visible}
        onClose={closeContextMenu}
        onInsertRowAbove={handleInsertRowAbove}
        onInsertRowBelow={handleInsertRowBelow}
        onInsertColLeft={handleInsertColLeft}
        onInsertColRight={handleInsertColRight}
        onDeleteRow={handleDeleteRow}
        onDeleteCol={handleDeleteCol}
        onHideRow={handleHideRow}
        onHideCol={handleHideCol}
        onUnhideRows={handleUnhideRows}
        onUnhideCols={handleUnhideCols}
        onSortAsc={() => handleSort('asc')}
        onSortDesc={() => handleSort('desc')}
        onCut={cutToClipboard}
        onCopy={copyToClipboard}
        onPaste={pasteFromClipboard}
        onClearContents={clearSelection}
        hasHiddenRows={(activeSheet.hiddenRows?.length ?? 0) > 0}
        hasHiddenCols={(activeSheet.hiddenCols?.length ?? 0) > 0}
      />

      {/* Filter dropdown overlay */}
      {filterDropdown && (
        <div
          ref={filterDropdownRef}
          className="fixed z-50 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-2 px-2 min-w-[180px] max-h-64 overflow-auto"
          style={{ left: filterDropdown.x, top: filterDropdown.y }}
        >
          <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1 px-1">
            Filter column {colLabel(filterDropdown.col)}
          </div>
          <button
            onClick={() => {
              mutateActiveSheetSilent((sheet) => {
                const fv = { ...(sheet.filterValues || {}) }
                delete fv[filterDropdown.col]
                return { ...sheet, filterValues: fv }
              })
              setFilterDropdown(null)
            }}
            className="w-full text-left text-xs px-2 py-1 text-blue-600 dark:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded mb-1"
          >
            Clear filter
          </button>
          <div className="border-t border-gray-200 dark:border-gray-700 my-1" />
          {getUniqueColumnValues(filterDropdown.col).map((val) => {
            const isChecked = filterValues[filterDropdown.col]?.includes(val) ?? false
            return (
              <label
                key={val}
                className="flex items-center gap-2 px-2 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => handleFilterToggleValue(filterDropdown.col, val)}
                  className="rounded"
                />
                <span className="truncate">{val || '(empty)'}</span>
              </label>
            )
          })}
        </div>
      )}
    </div>
  )
}
