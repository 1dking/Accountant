import type { CellData, SheetData } from './types'
import { cellId, parseCellRef } from './types'

/**
 * Detect the most likely delimiter in a CSV string by checking the first line.
 * Supports comma, tab, and semicolon.
 */
function detectDelimiter(text: string): string {
  const firstLine = text.split(/\r?\n/)[0] || ''

  // Count occurrences of each candidate delimiter outside of quoted fields
  const candidates = [',', '\t', ';']
  let bestDelimiter = ','
  let bestCount = 0

  for (const delim of candidates) {
    let count = 0
    let inQuotes = false
    for (let i = 0; i < firstLine.length; i++) {
      const ch = firstLine[i]
      if (ch === '"') {
        inQuotes = !inQuotes
      } else if (ch === delim && !inQuotes) {
        count++
      }
    }
    if (count > bestCount) {
      bestCount = count
      bestDelimiter = delim
    }
  }

  return bestDelimiter
}

/**
 * Parse a single CSV line into fields, respecting quoted fields.
 * Handles escaped quotes (double-double-quote inside quoted strings).
 */
function parseCsvLine(line: string, delimiter: string): string[] {
  const fields: string[] = []
  let current = ''
  let inQuotes = false
  let i = 0

  while (i < line.length) {
    const ch = line[i]

    if (inQuotes) {
      if (ch === '"') {
        // Check for escaped quote (two consecutive double quotes)
        if (i + 1 < line.length && line[i + 1] === '"') {
          current += '"'
          i += 2
          continue
        } else {
          // End of quoted field
          inQuotes = false
          i++
          continue
        }
      } else {
        current += ch
        i++
      }
    } else {
      if (ch === '"') {
        inQuotes = true
        i++
      } else if (ch === delimiter) {
        fields.push(current)
        current = ''
        i++
      } else {
        current += ch
        i++
      }
    }
  }

  // Push the last field
  fields.push(current)

  return fields
}

/**
 * Escape a value for CSV output.
 * Wraps in quotes if the value contains a comma, double quote, or newline.
 * Escapes internal double quotes by doubling them.
 */
function escapeCsvValue(value: string): string {
  if (value === '') return ''

  const needsQuoting = value.includes(',') || value.includes('"') || value.includes('\n') || value.includes('\r')

  if (needsQuoting) {
    return '"' + value.replace(/"/g, '""') + '"'
  }

  return value
}

/**
 * Export a SheetData to a CSV string (comma-separated).
 * Determines the used range by scanning all cells, then writes
 * rows from 0..maxRow and columns from 0..maxCol.
 */
export function exportSheetToCsv(sheet: SheetData): string {
  const cellKeys = Object.keys(sheet.cells)

  if (cellKeys.length === 0) {
    return ''
  }

  // Determine the extent of the used range
  let maxRow = 0
  let maxCol = 0

  for (const key of cellKeys) {
    const ref = parseCellRef(key)
    if (ref) {
      if (ref.row > maxRow) maxRow = ref.row
      if (ref.col > maxCol) maxCol = ref.col
    }
  }

  // Also consider explicit dimensions if set
  if (sheet.numRows && sheet.numRows - 1 > maxRow) {
    maxRow = sheet.numRows - 1
  }
  if (sheet.numCols && sheet.numCols - 1 > maxCol) {
    maxCol = sheet.numCols - 1
  }

  const lines: string[] = []

  for (let row = 0; row <= maxRow; row++) {
    const fields: string[] = []
    for (let col = 0; col <= maxCol; col++) {
      const id = cellId(row, col)
      const cell = sheet.cells[id]
      const value = cell?.value ?? ''
      fields.push(escapeCsvValue(value))
    }

    // Trim trailing empty fields on each row to keep output clean,
    // but keep at least one field per row.
    while (fields.length > 1 && fields[fields.length - 1] === '') {
      fields.pop()
    }

    lines.push(fields.join(','))
  }

  // Remove trailing empty lines
  while (lines.length > 0 && lines[lines.length - 1].trim() === '') {
    lines.pop()
  }

  return lines.join('\n')
}

/**
 * Trigger a CSV file download in the browser.
 */
export function downloadCsv(csv: string, filename: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename.endsWith('.csv') ? filename : `${filename}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * Parse a CSV string into a cells record.
 * Auto-detects delimiter (comma, tab, or semicolon).
 * Returns cells record, numRows, and numCols.
 */
export function parseCsv(csvText: string): {
  cells: Record<string, CellData>
  numRows: number
  numCols: number
} {
  const cells: Record<string, CellData> = {}

  if (!csvText || csvText.trim() === '') {
    return { cells, numRows: 0, numCols: 0 }
  }

  const delimiter = detectDelimiter(csvText)

  // Split into lines, handling both \r\n and \n
  // But we need to handle quoted fields that contain newlines
  const lines: string[] = []
  let currentLine = ''
  let inQuotes = false

  for (let i = 0; i < csvText.length; i++) {
    const ch = csvText[i]

    if (ch === '"') {
      inQuotes = !inQuotes
      currentLine += ch
    } else if ((ch === '\n' || ch === '\r') && !inQuotes) {
      // End of line
      lines.push(currentLine)
      currentLine = ''
      // Handle \r\n
      if (ch === '\r' && i + 1 < csvText.length && csvText[i + 1] === '\n') {
        i++
      }
    } else {
      currentLine += ch
    }
  }

  // Push the final line if non-empty
  if (currentLine.length > 0) {
    lines.push(currentLine)
  }

  let maxCols = 0

  for (let row = 0; row < lines.length; row++) {
    const line = lines[row]
    if (line.trim() === '' && row === lines.length - 1) {
      // Skip trailing empty line
      continue
    }

    const fields = parseCsvLine(line, delimiter)

    if (fields.length > maxCols) {
      maxCols = fields.length
    }

    for (let col = 0; col < fields.length; col++) {
      const value = fields[col].trim()
      if (value !== '') {
        const id = cellId(row, col)
        cells[id] = { value }
      }
    }
  }

  const numRows = lines.length
  const numCols = maxCols

  return { cells, numRows, numCols }
}

/**
 * Read a File object as text. Returns a promise that resolves with the file content.
 */
export function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(new Error(`Failed to read file: ${file.name}`))
    reader.readAsText(file)
  })
}
