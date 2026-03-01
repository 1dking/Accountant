import { useState, useEffect } from 'react'
import { X, Plus, Pencil, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ConditionalRule } from '@/lib/spreadsheet/types'
import { colLabel } from '@/lib/spreadsheet/types'

interface ConditionalFormatDialogProps {
  open: boolean
  onClose: () => void
  rules: ConditionalRule[]
  onSaveRules: (rules: ConditionalRule[]) => void
  selectionRange: { startRow: number; startCol: number; endRow: number; endCol: number } | null
}

const RULE_TYPES: { value: ConditionalRule['type']; label: string }[] = [
  { value: 'greater_than', label: 'Greater than' },
  { value: 'less_than', label: 'Less than' },
  { value: 'equal_to', label: 'Equal to' },
  { value: 'between', label: 'Between' },
  { value: 'text_contains', label: 'Text contains' },
  { value: 'text_starts_with', label: 'Text starts with' },
  { value: 'is_empty', label: 'Is empty' },
  { value: 'is_not_empty', label: 'Is not empty' },
]

function getRuleTypeLabel(type: ConditionalRule['type']): string {
  return RULE_TYPES.find((t) => t.value === type)?.label ?? type
}

function formatRange(range: ConditionalRule['range']): string {
  const start = `${colLabel(range.startCol)}${range.startRow + 1}`
  const end = `${colLabel(range.endCol)}${range.endRow + 1}`
  return `${start}:${end}`
}

function parseRangeString(rangeStr: string): ConditionalRule['range'] | null {
  const match = rangeStr.match(/^([A-Z]+)(\d+):([A-Z]+)(\d+)$/)
  if (!match) return null

  const startColStr = match[1]
  const startRow = parseInt(match[2], 10) - 1
  const endColStr = match[3]
  const endRow = parseInt(match[4], 10) - 1

  let startCol = 0
  for (let i = 0; i < startColStr.length; i++) {
    startCol = startCol * 26 + (startColStr.charCodeAt(i) - 64)
  }
  startCol -= 1

  let endCol = 0
  for (let i = 0; i < endColStr.length; i++) {
    endCol = endCol * 26 + (endColStr.charCodeAt(i) - 64)
  }
  endCol -= 1

  if (startRow < 0 || endRow < 0 || startCol < 0 || endCol < 0) return null

  return { startRow, startCol, endRow, endCol }
}

function describeRule(rule: ConditionalRule): string {
  const range = formatRange(rule.range)
  const typeLabel = getRuleTypeLabel(rule.type)

  let description = `${range} — ${typeLabel}`

  if (rule.type === 'between') {
    description += ` ${rule.value ?? ''} and ${rule.value2 ?? ''}`
  } else if (rule.type !== 'is_empty' && rule.type !== 'is_not_empty') {
    description += ` ${rule.value ?? ''}`
  }

  const styleParts: string[] = []
  if (rule.style.bgColor) styleParts.push(`bg: ${rule.style.bgColor}`)
  if (rule.style.textColor) styleParts.push(`text: ${rule.style.textColor}`)
  if (rule.style.bold) styleParts.push('bold')

  if (styleParts.length > 0) {
    description += ` → ${styleParts.join(', ')}`
  }

  return description
}

interface RuleEditorState {
  rangeStr: string
  type: ConditionalRule['type']
  value: string
  value2: string
  bgColor: string
  textColor: string
  bold: boolean
}

function defaultEditorState(
  selectionRange: ConditionalFormatDialogProps['selectionRange']
): RuleEditorState {
  const rangeStr = selectionRange
    ? formatRange({
        startRow: selectionRange.startRow,
        startCol: selectionRange.startCol,
        endRow: selectionRange.endRow,
        endCol: selectionRange.endCol,
      })
    : 'A1:A1'

  return {
    rangeStr,
    type: 'greater_than',
    value: '',
    value2: '',
    bgColor: '#fecaca',
    textColor: '#000000',
    bold: false,
  }
}

function ruleToEditorState(rule: ConditionalRule): RuleEditorState {
  return {
    rangeStr: formatRange(rule.range),
    type: rule.type,
    value: rule.value ?? '',
    value2: rule.value2 ?? '',
    bgColor: rule.style.bgColor ?? '#fecaca',
    textColor: rule.style.textColor ?? '#000000',
    bold: rule.style.bold ?? false,
  }
}

const needsValue = (type: ConditionalRule['type']): boolean =>
  type !== 'is_empty' && type !== 'is_not_empty'

const needsTwoValues = (type: ConditionalRule['type']): boolean =>
  type === 'between'

export default function ConditionalFormatDialog({
  open,
  onClose,
  rules,
  onSaveRules,
  selectionRange,
}: ConditionalFormatDialogProps) {
  const [localRules, setLocalRules] = useState<ConditionalRule[]>(rules)
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null)
  const [isAddingNew, setIsAddingNew] = useState(false)
  const [editor, setEditor] = useState<RuleEditorState>(defaultEditorState(selectionRange))
  const [rangeError, setRangeError] = useState('')

  // Sync local rules when dialog opens or rules prop changes
  useEffect(() => {
    if (open) {
      setLocalRules(rules)
      setEditingRuleId(null)
      setIsAddingNew(false)
      setEditor(defaultEditorState(selectionRange))
      setRangeError('')
    }
  }, [open, rules, selectionRange])

  if (!open) return null

  const isEditing = editingRuleId !== null || isAddingNew

  function handleAddNew() {
    setIsAddingNew(true)
    setEditingRuleId(null)
    setEditor(defaultEditorState(selectionRange))
    setRangeError('')
  }

  function handleEditRule(rule: ConditionalRule) {
    setEditingRuleId(rule.id)
    setIsAddingNew(false)
    setEditor(ruleToEditorState(rule))
    setRangeError('')
  }

  function handleDeleteRule(ruleId: string) {
    setLocalRules((prev) => prev.filter((r) => r.id !== ruleId))
    if (editingRuleId === ruleId) {
      setEditingRuleId(null)
    }
  }

  function handleSaveEditor() {
    const parsed = parseRangeString(editor.rangeStr.toUpperCase().replace(/\s/g, ''))
    if (!parsed) {
      setRangeError('Invalid range. Use format like A1:C10')
      return
    }

    const newRule: ConditionalRule = {
      id: editingRuleId ?? crypto.randomUUID?.() ?? Date.now().toString(),
      range: parsed,
      type: editor.type,
      value: needsValue(editor.type) ? editor.value : undefined,
      value2: needsTwoValues(editor.type) ? editor.value2 : undefined,
      style: {
        bgColor: editor.bgColor,
        textColor: editor.textColor,
        bold: editor.bold || undefined,
      },
    }

    if (editingRuleId) {
      setLocalRules((prev) => prev.map((r) => (r.id === editingRuleId ? newRule : r)))
    } else {
      setLocalRules((prev) => [...prev, newRule])
    }

    setEditingRuleId(null)
    setIsAddingNew(false)
    setRangeError('')
  }

  function handleCancelEditor() {
    setEditingRuleId(null)
    setIsAddingNew(false)
    setRangeError('')
  }

  function handleSaveAll() {
    onSaveRules(localRules)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-700 shrink-0">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Conditional Formatting
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-gray-400 dark:text-gray-500 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 dark:hover:text-gray-300 dark:hover:bg-gray-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {/* Rules list */}
          {localRules.length === 0 && !isEditing && (
            <p className="text-sm text-gray-500 dark:text-gray-400 py-2">
              No conditional formatting rules. Click "Add Rule" to create one.
            </p>
          )}

          {localRules.length > 0 && (
            <div className="space-y-2">
              {localRules.map((rule) => (
                <div
                  key={rule.id}
                  className={cn(
                    'flex items-center gap-2 p-3 rounded-lg border transition-colors',
                    editingRuleId === rule.id
                      ? 'border-blue-300 dark:border-blue-600 bg-blue-50 dark:bg-blue-900/30'
                      : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-950'
                  )}
                >
                  {/* Style preview swatch */}
                  <div
                    className="w-6 h-6 rounded border border-gray-300 dark:border-gray-600 shrink-0 flex items-center justify-center text-xs"
                    style={{
                      backgroundColor: rule.style.bgColor ?? 'transparent',
                      color: rule.style.textColor ?? '#000',
                      fontWeight: rule.style.bold ? 700 : 400,
                    }}
                  >
                    A
                  </div>

                  {/* Description */}
                  <span className="flex-1 text-sm text-gray-700 dark:text-gray-300 truncate">
                    {describeRule(rule)}
                  </span>

                  {/* Actions */}
                  <button
                    onClick={() => handleEditRule(rule)}
                    className="p-1 text-gray-400 dark:text-gray-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:text-blue-400 dark:hover:bg-blue-900/30 rounded"
                    title="Edit rule"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => handleDeleteRule(rule.id)}
                    className="p-1 text-gray-400 dark:text-gray-500 hover:text-red-500 hover:bg-red-50 dark:hover:text-red-400 dark:hover:bg-red-900/30 rounded"
                    title="Delete rule"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Rule editor form */}
          {isEditing && (
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3 bg-gray-50 dark:bg-gray-950">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {editingRuleId ? 'Edit Rule' : 'New Rule'}
              </h3>

              {/* Range */}
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                  Range
                </label>
                <input
                  type="text"
                  value={editor.rangeStr}
                  onChange={(e) => {
                    setEditor((prev) => ({ ...prev, rangeStr: e.target.value }))
                    setRangeError('')
                  }}
                  placeholder="A1:C10"
                  className={cn(
                    'w-full px-3 py-1.5 text-sm border rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500',
                    rangeError
                      ? 'border-red-400 dark:border-red-600'
                      : 'border-gray-300 dark:border-gray-600'
                  )}
                />
                {rangeError && (
                  <p className="text-xs text-red-500 dark:text-red-400 mt-1">{rangeError}</p>
                )}
              </div>

              {/* Rule type */}
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                  Condition
                </label>
                <select
                  value={editor.type}
                  onChange={(e) =>
                    setEditor((prev) => ({
                      ...prev,
                      type: e.target.value as ConditionalRule['type'],
                    }))
                  }
                  className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  {RULE_TYPES.map((rt) => (
                    <option key={rt.value} value={rt.value}>
                      {rt.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Value input(s) */}
              {needsValue(editor.type) && (
                <div className="flex gap-2">
                  <div className="flex-1">
                    <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                      {needsTwoValues(editor.type) ? 'Min value' : 'Value'}
                    </label>
                    <input
                      type="text"
                      value={editor.value}
                      onChange={(e) => setEditor((prev) => ({ ...prev, value: e.target.value }))}
                      placeholder="Enter value..."
                      className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>

                  {needsTwoValues(editor.type) && (
                    <div className="flex-1">
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                        Max value
                      </label>
                      <input
                        type="text"
                        value={editor.value2}
                        onChange={(e) =>
                          setEditor((prev) => ({ ...prev, value2: e.target.value }))
                        }
                        placeholder="Enter value..."
                        className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Style options */}
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                  Formatting style
                </label>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-gray-600 dark:text-gray-400">Background:</label>
                    <input
                      type="color"
                      value={editor.bgColor}
                      onChange={(e) => setEditor((prev) => ({ ...prev, bgColor: e.target.value }))}
                      className="w-7 h-7 rounded border border-gray-300 dark:border-gray-600 cursor-pointer bg-transparent"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-gray-600 dark:text-gray-400">Text:</label>
                    <input
                      type="color"
                      value={editor.textColor}
                      onChange={(e) =>
                        setEditor((prev) => ({ ...prev, textColor: e.target.value }))
                      }
                      className="w-7 h-7 rounded border border-gray-300 dark:border-gray-600 cursor-pointer bg-transparent"
                    />
                  </div>
                  <label className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editor.bold}
                      onChange={(e) => setEditor((prev) => ({ ...prev, bold: e.target.checked }))}
                      className="rounded border-gray-300 dark:border-gray-600 text-blue-600 dark:text-blue-400 focus:ring-blue-500"
                    />
                    Bold
                  </label>
                </div>

                {/* Style preview */}
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-xs text-gray-500 dark:text-gray-400">Preview:</span>
                  <span
                    className="px-3 py-1 rounded text-sm border border-gray-200 dark:border-gray-700"
                    style={{
                      backgroundColor: editor.bgColor,
                      color: editor.textColor,
                      fontWeight: editor.bold ? 700 : 400,
                    }}
                  >
                    Sample Text
                  </span>
                </div>
              </div>

              {/* Editor actions */}
              <div className="flex items-center gap-2 pt-2">
                <button
                  onClick={handleSaveEditor}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
                >
                  {editingRuleId ? 'Update Rule' : 'Add Rule'}
                </button>
                <button
                  onClick={handleCancelEditor}
                  className="px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-1"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Add rule button */}
          {!isEditing && (
            <button
              onClick={handleAddNew}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-md transition-colors"
            >
              <Plus className="h-4 w-4" />
              Add Rule
            </button>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-2 shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
          >
            Cancel
          </button>
          <button
            onClick={handleSaveAll}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  )
}
