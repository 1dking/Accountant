export interface CellData {
  value: string
  bold?: boolean
  italic?: boolean
  underline?: boolean
  strikethrough?: boolean
  bgColor?: string
  textColor?: string
  align?: 'left' | 'center' | 'right'
  format?: 'plain' | 'number' | 'currency' | 'percent' | 'date'
  fontSize?: number
  borders?: { top?: boolean; bottom?: boolean; left?: boolean; right?: boolean }
}

export interface MergedRange {
  startRow: number
  startCol: number
  endRow: number
  endCol: number
}

export interface ConditionalRule {
  id: string
  range: { startRow: number; startCol: number; endRow: number; endCol: number }
  type:
    | 'greater_than'
    | 'less_than'
    | 'equal_to'
    | 'between'
    | 'text_contains'
    | 'text_starts_with'
    | 'is_empty'
    | 'is_not_empty'
  value?: string
  value2?: string // for 'between'
  style: { bgColor?: string; textColor?: string; bold?: boolean }
}

export interface ValidationRule {
  type: 'number' | 'list' | 'text_length' | 'date' | 'custom'
  min?: number
  max?: number
  listValues?: string[]
  customFormula?: string
  showWarning?: boolean
  warningMessage?: string
}

export interface ChartConfig {
  id: string
  type: 'bar' | 'line' | 'pie' | 'area'
  title: string
  dataRange: { startRow: number; startCol: number; endRow: number; endCol: number }
  position: { x: number; y: number; width: number; height: number }
  headerRow?: boolean
}

export interface SheetData {
  name: string
  cells: Record<string, CellData>
  colWidths?: Record<number, number>
  rowHeights?: Record<number, number>
  numRows?: number
  numCols?: number
  freezeRow?: number
  freezeCol?: number
  hiddenRows?: number[]
  hiddenCols?: number[]
  mergedCells?: MergedRange[]
  conditionalFormats?: ConditionalRule[]
  charts?: ChartConfig[]
  filterEnabled?: boolean
  filterValues?: Record<number, string[]>
}

// Helper to get column label (0=A, 1=B, ... 25=Z, 26=AA, etc.)
export function colLabel(index: number): string {
  let label = ''
  let n = index
  while (n >= 0) {
    label = String.fromCharCode(65 + (n % 26)) + label
    n = Math.floor(n / 26) - 1
  }
  return label
}

// Helper to get cell ID (e.g., "A1", "B2")
export function cellId(row: number, col: number): string {
  return `${colLabel(col)}${row + 1}`
}

// Parse cell reference (e.g., "A1" -> {row: 0, col: 0})
export function parseCellRef(ref: string): { row: number; col: number } | null {
  const match = ref.match(/^([A-Z]+)(\d+)$/)
  if (!match) return null
  const colStr = match[1]
  const rowNum = parseInt(match[2], 10) - 1
  let col = 0
  for (let i = 0; i < colStr.length; i++) {
    col = col * 26 + (colStr.charCodeAt(i) - 64)
  }
  col -= 1
  return { row: rowNum, col }
}

// Expand range reference "A1:C3" to array of cell refs
export function expandRange(rangeStr: string): string[] {
  const parts = rangeStr.split(':')
  if (parts.length !== 2) return [rangeStr]
  const start = parseCellRef(parts[0])
  const end = parseCellRef(parts[1])
  if (!start || !end) return [rangeStr]
  const cells: string[] = []
  const minRow = Math.min(start.row, end.row)
  const maxRow = Math.max(start.row, end.row)
  const minCol = Math.min(start.col, end.col)
  const maxCol = Math.max(start.col, end.col)
  for (let r = minRow; r <= maxRow; r++) {
    for (let c = minCol; c <= maxCol; c++) {
      cells.push(cellId(r, c))
    }
  }
  return cells
}
