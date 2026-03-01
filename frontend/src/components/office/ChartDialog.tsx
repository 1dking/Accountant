import { useState, useEffect } from 'react'
import { X, BarChart3, LineChart as LineChartIcon, PieChart as PieChartIcon, AreaChart as AreaChartIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ChartConfig } from '@/lib/spreadsheet/types'
import { colLabel } from '@/lib/spreadsheet/types'

interface ChartDialogProps {
  open: boolean
  onClose: () => void
  onInsertChart: (config: ChartConfig) => void
  selectionRange: { startRow: number; startCol: number; endRow: number; endCol: number } | null
  existingChart?: ChartConfig | null
}

type ChartType = ChartConfig['type']

const CHART_TYPES: { value: ChartType; label: string; Icon: typeof BarChart3 }[] = [
  { value: 'bar', label: 'Bar', Icon: BarChart3 },
  { value: 'line', label: 'Line', Icon: LineChartIcon },
  { value: 'pie', label: 'Pie', Icon: PieChartIcon },
  { value: 'area', label: 'Area', Icon: AreaChartIcon },
]

function formatRange(range: { startRow: number; startCol: number; endRow: number; endCol: number }): string {
  const start = `${colLabel(range.startCol)}${range.startRow + 1}`
  const end = `${colLabel(range.endCol)}${range.endRow + 1}`
  return `${start}:${end}`
}

function parseRangeString(
  rangeStr: string
): { startRow: number; startCol: number; endRow: number; endCol: number } | null {
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

interface EditorState {
  chartType: ChartType
  title: string
  rangeStr: string
  headerRow: boolean
}

function getDefaultEditorState(
  selectionRange: ChartDialogProps['selectionRange'],
  existingChart?: ChartConfig | null
): EditorState {
  if (existingChart) {
    return {
      chartType: existingChart.type,
      title: existingChart.title,
      rangeStr: formatRange(existingChart.dataRange),
      headerRow: existingChart.headerRow ?? true,
    }
  }

  const rangeStr = selectionRange
    ? formatRange({
        startRow: selectionRange.startRow,
        startCol: selectionRange.startCol,
        endRow: selectionRange.endRow,
        endCol: selectionRange.endCol,
      })
    : 'A1:D10'

  return {
    chartType: 'bar',
    title: '',
    rangeStr,
    headerRow: true,
  }
}

export default function ChartDialog({
  open,
  onClose,
  onInsertChart,
  selectionRange,
  existingChart,
}: ChartDialogProps) {
  const [editor, setEditor] = useState<EditorState>(
    getDefaultEditorState(selectionRange, existingChart)
  )
  const [rangeError, setRangeError] = useState('')

  const isEditing = !!existingChart

  // Reset when dialog opens
  useEffect(() => {
    if (open) {
      setEditor(getDefaultEditorState(selectionRange, existingChart))
      setRangeError('')
    }
  }, [open, selectionRange, existingChart])

  if (!open) return null

  function handleInsert() {
    const normalizedRange = editor.rangeStr.toUpperCase().replace(/\s/g, '')
    const parsed = parseRangeString(normalizedRange)
    if (!parsed) {
      setRangeError('Invalid range. Use format like A1:D10')
      return
    }

    const config: ChartConfig = {
      id: existingChart?.id ?? (crypto.randomUUID?.() ?? Date.now().toString()),
      type: editor.chartType,
      title: editor.title || `${CHART_TYPES.find((t) => t.value === editor.chartType)?.label ?? 'Chart'} Chart`,
      dataRange: parsed,
      position: existingChart?.position ?? { x: 50, y: 50, width: 500, height: 350 },
      headerRow: editor.headerRow,
    }

    onInsertChart(config)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-full max-w-md mx-4 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {isEditing ? 'Edit Chart' : 'Insert Chart'}
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-gray-400 dark:text-gray-500 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 dark:hover:text-gray-300 dark:hover:bg-gray-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="px-5 py-4 space-y-4">
          {/* Chart type selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Chart type
            </label>
            <div className="grid grid-cols-4 gap-2">
              {CHART_TYPES.map(({ value, label, Icon }) => (
                <button
                  key={value}
                  onClick={() => setEditor((prev) => ({ ...prev, chartType: value }))}
                  className={cn(
                    'flex flex-col items-center gap-1.5 p-3 rounded-lg border-2 transition-colors',
                    editor.chartType === value
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-400'
                      : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800'
                  )}
                >
                  <Icon className="h-6 w-6" />
                  <span className="text-xs font-medium">{label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Chart title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Chart title
            </label>
            <input
              type="text"
              value={editor.title}
              onChange={(e) => setEditor((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="My Chart"
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* Data range */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Data range
            </label>
            <input
              type="text"
              value={editor.rangeStr}
              onChange={(e) => {
                setEditor((prev) => ({ ...prev, rangeStr: e.target.value }))
                setRangeError('')
              }}
              placeholder="A1:D10"
              className={cn(
                'w-full px-3 py-2 text-sm border rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500',
                rangeError
                  ? 'border-red-400 dark:border-red-600'
                  : 'border-gray-300 dark:border-gray-600'
              )}
            />
            {rangeError && (
              <p className="text-xs text-red-500 dark:text-red-400 mt-1">{rangeError}</p>
            )}
          </div>

          {/* Header row checkbox */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={editor.headerRow}
              onChange={(e) =>
                setEditor((prev) => ({ ...prev, headerRow: e.target.checked }))
              }
              className="rounded border-gray-300 dark:border-gray-600 text-blue-600 dark:text-blue-400 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              First row is header
            </span>
          </label>

          {/* Preview area */}
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-950">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Preview</p>
            <div className="flex items-center justify-center h-24">
              {/* Minimal visual chart preview */}
              {editor.chartType === 'bar' && (
                <div className="flex items-end gap-1.5 h-16">
                  {[40, 65, 35, 80, 55].map((h, i) => (
                    <div
                      key={i}
                      className="w-6 rounded-t transition-all"
                      style={{
                        height: `${h}%`,
                        backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'][i],
                      }}
                    />
                  ))}
                </div>
              )}
              {editor.chartType === 'line' && (
                <svg viewBox="0 0 100 50" className="h-16 w-32">
                  <polyline
                    points="5,40 25,15 45,30 65,10 95,25"
                    fill="none"
                    stroke="#3b82f6"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  {[
                    { x: 5, y: 40 },
                    { x: 25, y: 15 },
                    { x: 45, y: 30 },
                    { x: 65, y: 10 },
                    { x: 95, y: 25 },
                  ].map((p, i) => (
                    <circle key={i} cx={p.x} cy={p.y} r="3" fill="#3b82f6" />
                  ))}
                </svg>
              )}
              {editor.chartType === 'pie' && (
                <svg viewBox="0 0 50 50" className="h-16 w-16">
                  <circle cx="25" cy="25" r="20" fill="#3b82f6" />
                  <path d="M25,25 L25,5 A20,20 0 0,1 43.66,15 Z" fill="#10b981" />
                  <path d="M25,25 L43.66,15 A20,20 0 0,1 43.66,35 Z" fill="#f59e0b" />
                  <path d="M25,25 L43.66,35 A20,20 0 0,1 25,45 Z" fill="#ef4444" />
                </svg>
              )}
              {editor.chartType === 'area' && (
                <svg viewBox="0 0 100 50" className="h-16 w-32">
                  <path
                    d="M5,45 L5,40 L25,15 L45,30 L65,10 L95,25 L95,45 Z"
                    fill="#3b82f6"
                    opacity="0.3"
                  />
                  <polyline
                    points="5,40 25,15 45,30 65,10 95,25"
                    fill="none"
                    stroke="#3b82f6"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </div>
            <p className="text-xs text-gray-400 dark:text-gray-500 text-center mt-1">
              {editor.title || 'Untitled'} &mdash;{' '}
              {CHART_TYPES.find((t) => t.value === editor.chartType)?.label} chart from{' '}
              {editor.rangeStr || '...'}
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
          >
            Cancel
          </button>
          <button
            onClick={handleInsert}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
          >
            {isEditing ? 'Update' : 'Insert'}
          </button>
        </div>
      </div>
    </div>
  )
}
