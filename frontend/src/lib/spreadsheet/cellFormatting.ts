/**
 * Check if a string value represents a numeric value.
 */
export function isNumeric(value: string): boolean {
  if (value === '' || value === null || value === undefined) return false
  const trimmed = value.trim()
  if (trimmed === '') return false
  return !isNaN(Number(trimmed))
}

/**
 * Parse a string value to a number, returning null if not numeric.
 */
export function parseNumeric(value: string): number | null {
  if (!isNumeric(value)) return null
  return Number(value.trim())
}

/**
 * Format a number with commas as thousands separators and a fixed number
 * of decimal places.
 */
function formatWithCommas(num: number, decimals: number): string {
  const isNegative = num < 0
  const abs = Math.abs(num)
  const fixed = abs.toFixed(decimals)
  const [intPart, decPart] = fixed.split('.')

  // Add commas to integer part
  let formatted = ''
  const digits = intPart
  for (let i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 === 0) {
      formatted += ','
    }
    formatted += digits[i]
  }

  if (decPart !== undefined) {
    formatted += '.' + decPart
  }

  return isNegative ? '-' + formatted : formatted
}

/**
 * Try to interpret a value as a date. Supports:
 * - Numeric values interpreted as days since Unix epoch
 * - ISO date strings (YYYY-MM-DD)
 * - Common date strings (MM/DD/YYYY, M/D/YYYY)
 * Returns a Date object or null if the value cannot be parsed as a date.
 */
function parseAsDate(value: string): Date | null {
  const trimmed = value.trim()

  // Try as a number (days since Unix epoch)
  const num = Number(trimmed)
  if (!isNaN(num) && trimmed !== '') {
    const date = new Date(num * 86400000)
    // Sanity check: year should be reasonable
    const year = date.getUTCFullYear()
    if (year >= 1900 && year <= 2200) {
      return date
    }
  }

  // Try ISO format (YYYY-MM-DD)
  const isoMatch = trimmed.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/)
  if (isoMatch) {
    const date = new Date(
      Date.UTC(parseInt(isoMatch[1]), parseInt(isoMatch[2]) - 1, parseInt(isoMatch[3]))
    )
    if (!isNaN(date.getTime())) return date
  }

  // Try MM/DD/YYYY or M/D/YYYY
  const usMatch = trimmed.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/)
  if (usMatch) {
    const date = new Date(
      Date.UTC(parseInt(usMatch[3]), parseInt(usMatch[1]) - 1, parseInt(usMatch[2]))
    )
    if (!isNaN(date.getTime())) return date
  }

  // Try Date.parse as fallback
  const parsed = Date.parse(trimmed)
  if (!isNaN(parsed)) {
    return new Date(parsed)
  }

  return null
}

/**
 * Format a cell's display value based on its format type.
 *
 * @param value  The raw string value of the cell (may be a number, string, etc.)
 * @param format The format type: 'plain', 'number', 'currency', 'percent', 'date'
 * @returns The formatted string for display.
 */
export function formatCellValue(value: string, format?: string): string {
  if (value === '' || value === null || value === undefined) return ''

  // If no format or plain, return as-is
  if (!format || format === 'plain') return value

  switch (format) {
    case 'number': {
      const num = parseNumeric(value)
      if (num === null) return value
      return formatWithCommas(num, 2)
    }

    case 'currency': {
      const num = parseNumeric(value)
      if (num === null) return value
      const isNegative = num < 0
      const formatted = formatWithCommas(Math.abs(num), 2)
      return isNegative ? '-$' + formatted : '$' + formatted
    }

    case 'percent': {
      const num = parseNumeric(value)
      if (num === null) return value
      const percentValue = num * 100
      return formatWithCommas(percentValue, 2) + '%'
    }

    case 'date': {
      const date = parseAsDate(value)
      if (!date) return value
      const mm = String(date.getUTCMonth() + 1).padStart(2, '0')
      const dd = String(date.getUTCDate()).padStart(2, '0')
      const yyyy = date.getUTCFullYear()
      return `${mm}/${dd}/${yyyy}`
    }

    default:
      return value
  }
}
