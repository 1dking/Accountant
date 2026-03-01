import { parseCellRef, expandRange, cellId } from './types'

// ---------------------------------------------------------------------------
// Token types
// ---------------------------------------------------------------------------

type TokenType =
  | 'NUMBER'
  | 'STRING'
  | 'CELL_REF'
  | 'RANGE_REF'
  | 'FUNCTION'
  | 'LPAREN'
  | 'RPAREN'
  | 'COMMA'
  | 'COLON'
  | 'OPERATOR'
  | 'COMPARISON'
  | 'CONCAT'
  | 'EOF'

interface Token {
  type: TokenType
  value: string
}

// ---------------------------------------------------------------------------
// AST node types
// ---------------------------------------------------------------------------

type ASTNode =
  | { kind: 'number'; value: number }
  | { kind: 'string'; value: string }
  | { kind: 'cell_ref'; ref: string }
  | { kind: 'range_ref'; range: string }
  | { kind: 'binary'; op: string; left: ASTNode; right: ASTNode }
  | { kind: 'unary'; op: string; operand: ASTNode }
  | { kind: 'function_call'; name: string; args: ASTNode[] }

// ---------------------------------------------------------------------------
// Error sentinels
// ---------------------------------------------------------------------------

const ERR_REF = '#REF!'
const ERR_VALUE = '#VALUE!'
const ERR_DIV0 = '#DIV/0!'
const ERR_NAME = '#NAME?'
const ERR_CIRC = '#CIRC!'

function isError(v: unknown): v is string {
  if (typeof v !== 'string') return false
  return (
    v === ERR_REF ||
    v === ERR_VALUE ||
    v === ERR_DIV0 ||
    v === ERR_NAME ||
    v === ERR_CIRC
  )
}

// ---------------------------------------------------------------------------
// Tokenizer
// ---------------------------------------------------------------------------

function tokenize(formula: string): Token[] {
  const tokens: Token[] = []
  let i = 0
  const src = formula

  while (i < src.length) {
    const ch = src[i]

    // Whitespace -- skip
    if (ch === ' ' || ch === '\t') {
      i++
      continue
    }

    // String literal in double quotes
    if (ch === '"') {
      i++ // skip opening quote
      let str = ''
      while (i < src.length && src[i] !== '"') {
        if (src[i] === '\\' && i + 1 < src.length) {
          // escaped character
          i++
          str += src[i]
        } else {
          str += src[i]
        }
        i++
      }
      if (i < src.length) i++ // skip closing quote
      tokens.push({ type: 'STRING', value: str })
      continue
    }

    // Number literal (including decimals)
    if (
      (ch >= '0' && ch <= '9') ||
      (ch === '.' && i + 1 < src.length && src[i + 1] >= '0' && src[i + 1] <= '9')
    ) {
      let num = ''
      while (i < src.length && ((src[i] >= '0' && src[i] <= '9') || src[i] === '.')) {
        num += src[i]
        i++
      }
      tokens.push({ type: 'NUMBER', value: num })
      continue
    }

    // Comparison operators (>=, <=, <>, =) and single < >
    if (ch === '>' || ch === '<') {
      if (i + 1 < src.length && src[i + 1] === '=') {
        tokens.push({ type: 'COMPARISON', value: src[i] + '=' })
        i += 2
        continue
      }
      if (ch === '<' && i + 1 < src.length && src[i + 1] === '>') {
        tokens.push({ type: 'COMPARISON', value: '<>' })
        i += 2
        continue
      }
      tokens.push({ type: 'COMPARISON', value: ch })
      i++
      continue
    }

    // Equality comparison -- only when not at start and previous token makes it contextual
    // We treat standalone = as comparison
    if (ch === '=') {
      tokens.push({ type: 'COMPARISON', value: '=' })
      i++
      continue
    }

    // Ampersand (string concatenation)
    if (ch === '&') {
      tokens.push({ type: 'CONCAT', value: '&' })
      i++
      continue
    }

    // Arithmetic operators
    if (ch === '+' || ch === '-' || ch === '*' || ch === '/' || ch === '^') {
      tokens.push({ type: 'OPERATOR', value: ch })
      i++
      continue
    }

    // Parentheses
    if (ch === '(') {
      tokens.push({ type: 'LPAREN', value: '(' })
      i++
      continue
    }
    if (ch === ')') {
      tokens.push({ type: 'RPAREN', value: ')' })
      i++
      continue
    }

    // Comma
    if (ch === ',') {
      tokens.push({ type: 'COMMA', value: ',' })
      i++
      continue
    }

    // Colon (for ranges -- handled during identifier parsing below)
    if (ch === ':') {
      tokens.push({ type: 'COLON', value: ':' })
      i++
      continue
    }

    // Identifiers: cell references (A1, AB12) or function names (SUM, IF, ...)
    if ((ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') || ch === '_') {
      let ident = ''
      while (
        i < src.length &&
        ((src[i] >= 'A' && src[i] <= 'Z') ||
          (src[i] >= 'a' && src[i] <= 'z') ||
          (src[i] >= '0' && src[i] <= '9') ||
          src[i] === '_')
      ) {
        ident += src[i]
        i++
      }

      const upper = ident.toUpperCase()

      // Check if it's a cell reference pattern: one or more letters followed by digits
      const cellMatch = upper.match(/^([A-Z]+)(\d+)$/)

      // Look ahead for colon to detect range (e.g. A1:B5)
      if (cellMatch && i < src.length && src[i] === ':') {
        // Peek ahead for second cell ref
        let j = i + 1
        let secondRef = ''
        while (
          j < src.length &&
          ((src[j] >= 'A' && src[j] <= 'Z') ||
            (src[j] >= 'a' && src[j] <= 'z') ||
            (src[j] >= '0' && src[j] <= '9'))
        ) {
          secondRef += src[j]
          j++
        }
        const secondUpper = secondRef.toUpperCase()
        if (/^[A-Z]+\d+$/.test(secondUpper)) {
          tokens.push({ type: 'RANGE_REF', value: upper + ':' + secondUpper })
          i = j
          continue
        }
      }

      if (cellMatch) {
        tokens.push({ type: 'CELL_REF', value: upper })
        continue
      }

      // Otherwise, it's a function name (or boolean literal TRUE/FALSE)
      if (upper === 'TRUE' || upper === 'FALSE') {
        // Treat booleans as numbers: TRUE=1, FALSE=0
        tokens.push({ type: 'NUMBER', value: upper === 'TRUE' ? '1' : '0' })
        continue
      }

      tokens.push({ type: 'FUNCTION', value: upper })
      continue
    }

    // Unknown character -- skip
    i++
  }

  tokens.push({ type: 'EOF', value: '' })
  return tokens
}

// ---------------------------------------------------------------------------
// Parser -- recursive descent
// ---------------------------------------------------------------------------

class Parser {
  private tokens: Token[]
  private pos: number

  constructor(tokens: Token[]) {
    this.tokens = tokens
    this.pos = 0
  }

  private peek(): Token {
    return this.tokens[this.pos] ?? { type: 'EOF', value: '' }
  }

  private advance(): Token {
    const t = this.tokens[this.pos]
    this.pos++
    return t ?? { type: 'EOF', value: '' }
  }

  private expect(type: TokenType): Token {
    const t = this.advance()
    if (t.type !== type) {
      throw new Error(`Expected ${type} but got ${t.type} (${t.value})`)
    }
    return t
  }

  parse(): ASTNode {
    const node = this.parseComparison()
    return node
  }

  // Comparison: lowest precedence among binary ops
  private parseComparison(): ASTNode {
    let left = this.parseConcatenation()
    while (this.peek().type === 'COMPARISON') {
      const op = this.advance().value
      const right = this.parseConcatenation()
      left = { kind: 'binary', op, left, right }
    }
    return left
  }

  // String concatenation with &
  private parseConcatenation(): ASTNode {
    let left = this.parseAddSub()
    while (this.peek().type === 'CONCAT') {
      this.advance()
      const right = this.parseAddSub()
      left = { kind: 'binary', op: '&', left, right }
    }
    return left
  }

  // Addition / Subtraction
  private parseAddSub(): ASTNode {
    let left = this.parseMulDiv()
    while (
      this.peek().type === 'OPERATOR' &&
      (this.peek().value === '+' || this.peek().value === '-')
    ) {
      const op = this.advance().value
      const right = this.parseMulDiv()
      left = { kind: 'binary', op, left, right }
    }
    return left
  }

  // Multiplication / Division
  private parseMulDiv(): ASTNode {
    let left = this.parsePower()
    while (
      this.peek().type === 'OPERATOR' &&
      (this.peek().value === '*' || this.peek().value === '/')
    ) {
      const op = this.advance().value
      const right = this.parsePower()
      left = { kind: 'binary', op, left, right }
    }
    return left
  }

  // Exponentiation (right-associative)
  private parsePower(): ASTNode {
    const base = this.parseUnary()
    if (this.peek().type === 'OPERATOR' && this.peek().value === '^') {
      this.advance()
      const exp = this.parsePower() // right-associative via recursion
      return { kind: 'binary', op: '^', left: base, right: exp }
    }
    return base
  }

  // Unary + / -
  private parseUnary(): ASTNode {
    if (
      this.peek().type === 'OPERATOR' &&
      (this.peek().value === '+' || this.peek().value === '-')
    ) {
      const op = this.advance().value
      const operand = this.parseUnary()
      if (op === '+') return operand
      return { kind: 'unary', op: '-', operand }
    }
    return this.parsePrimary()
  }

  // Primary: number, string, cell ref, range ref, function call, parenthesized expr
  private parsePrimary(): ASTNode {
    const tok = this.peek()

    // Number
    if (tok.type === 'NUMBER') {
      this.advance()
      return { kind: 'number', value: parseFloat(tok.value) }
    }

    // String literal
    if (tok.type === 'STRING') {
      this.advance()
      return { kind: 'string', value: tok.value }
    }

    // Range reference (A1:B5)
    if (tok.type === 'RANGE_REF') {
      this.advance()
      return { kind: 'range_ref', range: tok.value }
    }

    // Cell reference -- could also be start of a function call if followed by (
    if (tok.type === 'CELL_REF') {
      this.advance()
      return { kind: 'cell_ref', ref: tok.value }
    }

    // Function call
    if (tok.type === 'FUNCTION') {
      const name = this.advance().value
      this.expect('LPAREN')
      const args: ASTNode[] = []
      if (this.peek().type !== 'RPAREN') {
        args.push(this.parseComparison())
        while (this.peek().type === 'COMMA') {
          this.advance()
          args.push(this.parseComparison())
        }
      }
      this.expect('RPAREN')
      return { kind: 'function_call', name, args }
    }

    // Parenthesized expression
    if (tok.type === 'LPAREN') {
      this.advance()
      const inner = this.parseComparison()
      this.expect('RPAREN')
      return inner
    }

    throw new Error(`Unexpected token: ${tok.type} (${tok.value})`)
  }
}

// ---------------------------------------------------------------------------
// Evaluator
// ---------------------------------------------------------------------------

type CellGetter = (ref: string) => string

function toNumber(v: string | number): number {
  if (typeof v === 'number') return v
  if (v === '' || v === undefined || v === null) return 0
  const n = Number(v)
  if (isNaN(n)) throw new Error(ERR_VALUE)
  return n
}

function toString(v: string | number): string {
  if (typeof v === 'number') return String(v)
  return v ?? ''
}

/**
 * Resolve a cell value, recursively evaluating formulas.
 * Tracks visited cells for circular reference detection.
 */
function resolveCell(
  ref: string,
  getCellRawValue: CellGetter,
  visiting: Set<string>
): string | number {
  if (visiting.has(ref)) {
    return ERR_CIRC
  }
  const raw = getCellRawValue(ref)
  if (raw === undefined || raw === null || raw === '') return ''
  if (typeof raw === 'string' && raw.startsWith('=')) {
    visiting.add(ref)
    const result = evalFormula(raw.slice(1), getCellRawValue, visiting)
    visiting.delete(ref)
    return result
  }
  // Try to return as number if it looks numeric
  const num = Number(raw)
  if (!isNaN(num) && raw.trim() !== '') return num
  return raw
}

/**
 * Collect numeric values from a list of resolved values (skipping blanks and strings).
 */
function collectNumbers(values: (string | number)[]): number[] {
  const nums: number[] = []
  for (const v of values) {
    if (typeof v === 'number') {
      nums.push(v)
    } else if (typeof v === 'string' && v !== '' && !isError(v)) {
      const n = Number(v)
      if (!isNaN(n)) nums.push(n)
    }
  }
  return nums
}

/**
 * Resolve a range reference to an array of values.
 */
function resolveRange(
  rangeStr: string,
  getCellRawValue: CellGetter,
  visiting: Set<string>
): (string | number)[] {
  const refs = expandRange(rangeStr)
  return refs.map((ref) => resolveCell(ref, getCellRawValue, visiting))
}

/**
 * Flatten args: if an arg is a range_ref, expand it; otherwise evaluate normally.
 */
function flattenArgs(
  args: ASTNode[],
  getCellRawValue: CellGetter,
  visiting: Set<string>,
  evalNode: (node: ASTNode) => string | number
): (string | number)[] {
  const result: (string | number)[] = []
  for (const arg of args) {
    if (arg.kind === 'range_ref') {
      result.push(...resolveRange(arg.range, getCellRawValue, visiting))
    } else {
      result.push(evalNode(arg))
    }
  }
  return result
}

/**
 * Evaluate built-in functions.
 */
function evalFunction(
  name: string,
  args: ASTNode[],
  getCellRawValue: CellGetter,
  visiting: Set<string>,
  evalNode: (node: ASTNode) => string | number
): string | number {
  // Helper to flatten and collect
  const flat = () => flattenArgs(args, getCellRawValue, visiting, evalNode)

  switch (name) {
    // ------- Math -------
    case 'SUM': {
      const values = flat()
      // Propagate errors
      for (const v of values) if (isError(v)) return v as string
      const nums = collectNumbers(values)
      return nums.reduce((a, b) => a + b, 0)
    }

    case 'AVERAGE': {
      const values = flat()
      for (const v of values) if (isError(v)) return v as string
      const nums = collectNumbers(values)
      if (nums.length === 0) return ERR_DIV0
      return nums.reduce((a, b) => a + b, 0) / nums.length
    }

    case 'COUNT': {
      const values = flat()
      return collectNumbers(values).length
    }

    case 'COUNTA': {
      const values = flat()
      return values.filter((v) => v !== '' && v !== undefined && v !== null).length
    }

    case 'MIN': {
      const values = flat()
      for (const v of values) if (isError(v)) return v as string
      const nums = collectNumbers(values)
      if (nums.length === 0) return 0
      return Math.min(...nums)
    }

    case 'MAX': {
      const values = flat()
      for (const v of values) if (isError(v)) return v as string
      const nums = collectNumbers(values)
      if (nums.length === 0) return 0
      return Math.max(...nums)
    }

    case 'ABS': {
      if (args.length !== 1) return ERR_VALUE
      const v = evalNode(args[0])
      if (isError(v)) return v
      return Math.abs(toNumber(v))
    }

    case 'ROUND': {
      if (args.length < 1 || args.length > 2) return ERR_VALUE
      const v = evalNode(args[0])
      if (isError(v)) return v
      const num = toNumber(v)
      const digits = args.length === 2 ? toNumber(evalNode(args[1])) : 0
      const factor = Math.pow(10, digits)
      return Math.round(num * factor) / factor
    }

    case 'FLOOR': {
      if (args.length < 1 || args.length > 2) return ERR_VALUE
      const v = evalNode(args[0])
      if (isError(v)) return v
      const num = toNumber(v)
      if (args.length === 2) {
        const significance = toNumber(evalNode(args[1]))
        if (significance === 0) return ERR_DIV0
        return Math.floor(num / significance) * significance
      }
      return Math.floor(num)
    }

    case 'CEILING': {
      if (args.length < 1 || args.length > 2) return ERR_VALUE
      const v = evalNode(args[0])
      if (isError(v)) return v
      const num = toNumber(v)
      if (args.length === 2) {
        const significance = toNumber(evalNode(args[1]))
        if (significance === 0) return ERR_DIV0
        return Math.ceil(num / significance) * significance
      }
      return Math.ceil(num)
    }

    case 'MOD': {
      if (args.length !== 2) return ERR_VALUE
      const a = toNumber(evalNode(args[0]))
      const b = toNumber(evalNode(args[1]))
      if (b === 0) return ERR_DIV0
      // Match Excel behavior: result sign matches divisor
      return ((a % b) + b) % b
    }

    case 'POWER': {
      if (args.length !== 2) return ERR_VALUE
      const base = toNumber(evalNode(args[0]))
      const exp = toNumber(evalNode(args[1]))
      return Math.pow(base, exp)
    }

    case 'SQRT': {
      if (args.length !== 1) return ERR_VALUE
      const v = toNumber(evalNode(args[0]))
      if (v < 0) return ERR_VALUE
      return Math.sqrt(v)
    }

    // ------- Text -------
    case 'CONCATENATE': {
      const values = flat()
      for (const v of values) if (isError(v)) return v as string
      return values.map((v) => toString(v)).join('')
    }

    case 'UPPER': {
      if (args.length !== 1) return ERR_VALUE
      const v = evalNode(args[0])
      if (isError(v)) return v
      return toString(v).toUpperCase()
    }

    case 'LOWER': {
      if (args.length !== 1) return ERR_VALUE
      const v = evalNode(args[0])
      if (isError(v)) return v
      return toString(v).toLowerCase()
    }

    case 'LEN': {
      if (args.length !== 1) return ERR_VALUE
      const v = evalNode(args[0])
      if (isError(v)) return v
      return toString(v).length
    }

    case 'LEFT': {
      if (args.length < 1 || args.length > 2) return ERR_VALUE
      const s = toString(evalNode(args[0]))
      const n = args.length === 2 ? toNumber(evalNode(args[1])) : 1
      return s.substring(0, Math.max(0, n))
    }

    case 'RIGHT': {
      if (args.length < 1 || args.length > 2) return ERR_VALUE
      const s = toString(evalNode(args[0]))
      const n = args.length === 2 ? toNumber(evalNode(args[1])) : 1
      return s.substring(Math.max(0, s.length - n))
    }

    case 'MID': {
      if (args.length !== 3) return ERR_VALUE
      const s = toString(evalNode(args[0]))
      const startPos = toNumber(evalNode(args[1]))
      const length = toNumber(evalNode(args[2]))
      if (startPos < 1 || length < 0) return ERR_VALUE
      return s.substring(startPos - 1, startPos - 1 + length)
    }

    case 'TRIM': {
      if (args.length !== 1) return ERR_VALUE
      const v = evalNode(args[0])
      if (isError(v)) return v
      return toString(v).trim().replace(/\s+/g, ' ')
    }

    case 'SUBSTITUTE': {
      if (args.length < 3 || args.length > 4) return ERR_VALUE
      const text = toString(evalNode(args[0]))
      const oldText = toString(evalNode(args[1]))
      const newText = toString(evalNode(args[2]))
      if (args.length === 4) {
        // Replace nth occurrence
        const n = toNumber(evalNode(args[3]))
        if (n < 1) return ERR_VALUE
        let count = 0
        let idx = -1
        let searchFrom = 0
        while (count < n) {
          idx = text.indexOf(oldText, searchFrom)
          if (idx === -1) return text // occurrence not found, return original
          count++
          searchFrom = idx + 1
        }
        return text.substring(0, idx) + newText + text.substring(idx + oldText.length)
      }
      // Replace all occurrences
      return text.split(oldText).join(newText)
    }

    case 'TEXT': {
      if (args.length !== 2) return ERR_VALUE
      const v = evalNode(args[0])
      if (isError(v)) return v
      const format = toString(evalNode(args[1])).toLowerCase()
      const num = toNumber(v)

      // Basic format patterns
      if (format === '0' || format === '#') {
        return Math.round(num).toString()
      }
      if (format === '0.00' || format === '#.##') {
        return num.toFixed(2)
      }
      if (format === '0.0' || format === '#.#') {
        return num.toFixed(1)
      }
      if (format === '#,##0' || format === '#,##0.00') {
        const decimals = format.includes('.00') ? 2 : 0
        return num.toLocaleString('en-US', {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })
      }
      if (format === '0%' || format === '0.00%') {
        const decimals = format.includes('.00') ? 2 : 0
        return (num * 100).toFixed(decimals) + '%'
      }
      if (format === 'mm/dd/yyyy' || format === 'm/d/yyyy') {
        const date = new Date(num * 86400000) // days since epoch
        const mm = String(date.getUTCMonth() + 1).padStart(2, '0')
        const dd = String(date.getUTCDate()).padStart(2, '0')
        const yyyy = date.getUTCFullYear()
        return `${mm}/${dd}/${yyyy}`
      }
      // Fallback: just return the number as string
      return toString(num)
    }

    // ------- Logic -------
    case 'IF': {
      if (args.length < 2 || args.length > 3) return ERR_VALUE
      const condition = evalNode(args[0])
      if (isError(condition)) return condition
      const isTruthy =
        typeof condition === 'number' ? condition !== 0 : condition !== '' && condition !== '0'
      if (isTruthy) {
        return evalNode(args[1])
      }
      return args.length === 3 ? evalNode(args[2]) : ''
    }

    case 'AND': {
      if (args.length === 0) return ERR_VALUE
      const values = flat()
      for (const v of values) {
        if (isError(v)) return v as string
        const n = typeof v === 'number' ? v : Number(v)
        if (isNaN(n) || n === 0) return 0
      }
      return 1
    }

    case 'OR': {
      if (args.length === 0) return ERR_VALUE
      const values = flat()
      for (const v of values) {
        if (isError(v)) return v as string
        const n = typeof v === 'number' ? v : Number(v)
        if (!isNaN(n) && n !== 0) return 1
      }
      return 0
    }

    case 'NOT': {
      if (args.length !== 1) return ERR_VALUE
      const v = evalNode(args[0])
      if (isError(v)) return v
      const n = toNumber(v)
      return n === 0 ? 1 : 0
    }

    case 'IFERROR': {
      if (args.length !== 2) return ERR_VALUE
      try {
        const v = evalNode(args[0])
        if (isError(v)) return evalNode(args[1])
        return v
      } catch {
        return evalNode(args[1])
      }
    }

    // ------- Date -------
    case 'TODAY': {
      // Return days since Unix epoch (Excel-like serial number approach)
      const now = new Date()
      const epoch = new Date(Date.UTC(1970, 0, 1))
      const diffMs = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) - epoch.getTime()
      return Math.floor(diffMs / 86400000)
    }

    case 'NOW': {
      // Return days since Unix epoch including fractional day for time
      const now = new Date()
      const epoch = new Date(Date.UTC(1970, 0, 1))
      const diffMs = now.getTime() - epoch.getTime()
      return diffMs / 86400000
    }

    case 'YEAR': {
      if (args.length !== 1) return ERR_VALUE
      const v = evalNode(args[0])
      if (isError(v)) return v
      const days = toNumber(v)
      const date = new Date(days * 86400000)
      return date.getUTCFullYear()
    }

    case 'MONTH': {
      if (args.length !== 1) return ERR_VALUE
      const v = evalNode(args[0])
      if (isError(v)) return v
      const days = toNumber(v)
      const date = new Date(days * 86400000)
      return date.getUTCMonth() + 1
    }

    case 'DAY': {
      if (args.length !== 1) return ERR_VALUE
      const v = evalNode(args[0])
      if (isError(v)) return v
      const days = toNumber(v)
      const date = new Date(days * 86400000)
      return date.getUTCDate()
    }

    // ------- Lookup -------
    case 'INDEX': {
      // Simple INDEX(range, row_num, [col_num])
      if (args.length < 2 || args.length > 3) return ERR_VALUE
      if (args[0].kind !== 'range_ref') return ERR_VALUE

      const rangeStr = args[0].range
      const parts = rangeStr.split(':')
      if (parts.length !== 2) return ERR_REF

      const startRef = parseCellRef(parts[0])
      const endRef = parseCellRef(parts[1])
      if (!startRef || !endRef) return ERR_REF

      const rowIdx = toNumber(evalNode(args[1]))
      const colIdx = args.length === 3 ? toNumber(evalNode(args[2])) : 1

      if (rowIdx < 1 || colIdx < 1) return ERR_VALUE

      const targetRow = startRef.row + rowIdx - 1
      const targetCol = startRef.col + colIdx - 1

      if (targetRow > endRef.row || targetCol > endRef.col) return ERR_REF

      const targetRef = cellId(targetRow, targetCol)
      return resolveCell(targetRef, getCellRawValue, visiting)
    }

    default:
      return ERR_NAME
  }
}

/**
 * Internal: evaluate a formula string (without the leading '=') and return the result.
 */
function evalFormula(
  formulaBody: string,
  getCellRawValue: CellGetter,
  visiting: Set<string>
): string | number {
  let tokens: Token[]
  try {
    tokens = tokenize(formulaBody)
  } catch {
    return ERR_VALUE
  }

  let ast: ASTNode
  try {
    const parser = new Parser(tokens)
    ast = parser.parse()
  } catch {
    return ERR_VALUE
  }

  function evalNode(node: ASTNode): string | number {
    switch (node.kind) {
      case 'number':
        return node.value

      case 'string':
        return node.value

      case 'cell_ref': {
        const parsed = parseCellRef(node.ref)
        if (!parsed) return ERR_REF
        return resolveCell(node.ref, getCellRawValue, visiting)
      }

      case 'range_ref':
        // A bare range evaluated as a value returns the first cell
        return resolveRange(node.range, getCellRawValue, visiting)[0] ?? ''

      case 'unary': {
        const operand = evalNode(node.operand)
        if (isError(operand)) return operand
        if (node.op === '-') return -toNumber(operand)
        return operand
      }

      case 'binary': {
        // String concatenation
        if (node.op === '&') {
          const left = evalNode(node.left)
          if (isError(left)) return left
          const right = evalNode(node.right)
          if (isError(right)) return right
          return toString(left) + toString(right)
        }

        const left = evalNode(node.left)
        if (isError(left)) return left
        const right = evalNode(node.right)
        if (isError(right)) return right

        // Comparison operators -- work on both strings and numbers
        if (['=', '<>', '<', '>', '<=', '>='].includes(node.op)) {
          // If both sides are numeric, compare numerically
          const lNum = typeof left === 'number' ? left : Number(left)
          const rNum = typeof right === 'number' ? right : Number(right)
          const bothNumeric =
            (typeof left === 'number' || (typeof left === 'string' && left !== '' && !isNaN(lNum))) &&
            (typeof right === 'number' || (typeof right === 'string' && right !== '' && !isNaN(rNum)))

          if (bothNumeric) {
            switch (node.op) {
              case '=':
                return lNum === rNum ? 1 : 0
              case '<>':
                return lNum !== rNum ? 1 : 0
              case '<':
                return lNum < rNum ? 1 : 0
              case '>':
                return lNum > rNum ? 1 : 0
              case '<=':
                return lNum <= rNum ? 1 : 0
              case '>=':
                return lNum >= rNum ? 1 : 0
            }
          }

          // String comparison (case-insensitive like Excel)
          const lStr = toString(left).toLowerCase()
          const rStr = toString(right).toLowerCase()
          switch (node.op) {
            case '=':
              return lStr === rStr ? 1 : 0
            case '<>':
              return lStr !== rStr ? 1 : 0
            case '<':
              return lStr < rStr ? 1 : 0
            case '>':
              return lStr > rStr ? 1 : 0
            case '<=':
              return lStr <= rStr ? 1 : 0
            case '>=':
              return lStr >= rStr ? 1 : 0
          }
        }

        // Arithmetic operators
        const lVal = toNumber(left)
        const rVal = toNumber(right)
        switch (node.op) {
          case '+':
            return lVal + rVal
          case '-':
            return lVal - rVal
          case '*':
            return lVal * rVal
          case '/':
            if (rVal === 0) return ERR_DIV0
            return lVal / rVal
          case '^':
            return Math.pow(lVal, rVal)
          default:
            return ERR_VALUE
        }
      }

      case 'function_call':
        return evalFunction(node.name, node.args, getCellRawValue, visiting, evalNode)

      default:
        return ERR_VALUE
    }
  }

  try {
    return evalNode(ast)
  } catch (e) {
    if (e instanceof Error) {
      const msg = e.message
      if (msg === ERR_VALUE || msg === ERR_REF || msg === ERR_DIV0 || msg === ERR_NAME) {
        return msg
      }
    }
    return ERR_VALUE
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Evaluate a formula string. If the string starts with '=', it is treated as a
 * formula and parsed/evaluated. Otherwise the raw value is returned.
 *
 * @param formula       The raw cell value (e.g. "=SUM(A1:A5)" or "Hello")
 * @param getCellRawValue  A function that returns the raw string value of any cell
 *                         given its reference (e.g. "A1"). Should return "" for empty cells.
 * @param evaluatingCells  (internal) Set of cell refs currently being evaluated,
 *                         used for circular reference detection.
 * @returns The evaluated result as a string or number.
 */
export function evaluateFormula(
  formula: string,
  getCellRawValue: CellGetter,
  evaluatingCells?: Set<string>
): string | number {
  if (typeof formula !== 'string') return ''
  const trimmed = formula.trim()
  if (!trimmed.startsWith('=')) {
    // Not a formula -- return as-is, but try to parse numbers
    const num = Number(trimmed)
    if (trimmed !== '' && !isNaN(num)) return num
    return trimmed
  }

  const visiting = evaluatingCells ?? new Set<string>()
  return evalFormula(trimmed.slice(1), getCellRawValue, visiting)
}
