import { useState, useRef, useCallback, useEffect } from 'react'
import { Pencil, Trash2, GripHorizontal } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ChartConfig } from '@/lib/spreadsheet/types'
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

interface SheetChartProps {
  chart: ChartConfig
  data: Array<Record<string, string | number>>
  headers: string[]
  onEdit: () => void
  onDelete: () => void
  onMove: (position: { x: number; y: number }) => void
  onResize: (size: { width: number; height: number }) => void
}

const COLOR_PALETTE = [
  '#3b82f6',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#ec4899',
  '#06b6d4',
  '#84cc16',
]

export default function SheetChart({
  chart,
  data,
  headers,
  onEdit,
  onDelete,
  onMove,
  onResize,
}: SheetChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isResizing, setIsResizing] = useState(false)
  const dragStartRef = useRef<{ x: number; y: number; startX: number; startY: number }>({
    x: 0,
    y: 0,
    startX: 0,
    startY: 0,
  })
  const resizeStartRef = useRef<{
    x: number
    y: number
    startWidth: number
    startHeight: number
  }>({ x: 0, y: 0, startWidth: 0, startHeight: 0 })

  // Data series = all headers except the first one (which is the X axis / category)
  const xKey = headers[0] || 'category'
  const seriesKeys = headers.slice(1)

  // ---- Dragging ----
  const handleDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(true)
      dragStartRef.current = {
        x: e.clientX,
        y: e.clientY,
        startX: chart.position.x,
        startY: chart.position.y,
      }
    },
    [chart.position.x, chart.position.y]
  )

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - dragStartRef.current.x
      const dy = e.clientY - dragStartRef.current.y
      const newX = Math.max(0, dragStartRef.current.startX + dx)
      const newY = Math.max(0, dragStartRef.current.startY + dy)
      onMove({ x: newX, y: newY })
    }

    const handleMouseUp = () => {
      setIsDragging(false)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, onMove])

  // ---- Resizing ----
  const handleResizeStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsResizing(true)
      resizeStartRef.current = {
        x: e.clientX,
        y: e.clientY,
        startWidth: chart.position.width,
        startHeight: chart.position.height,
      }
    },
    [chart.position.width, chart.position.height]
  )

  useEffect(() => {
    if (!isResizing) return

    const handleMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - resizeStartRef.current.x
      const dy = e.clientY - resizeStartRef.current.y
      const newWidth = Math.max(250, resizeStartRef.current.startWidth + dx)
      const newHeight = Math.max(200, resizeStartRef.current.startHeight + dy)
      onResize({ width: newWidth, height: newHeight })
    }

    const handleMouseUp = () => {
      setIsResizing(false)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isResizing, onResize])

  // Chart-specific rendering
  function renderChart() {
    const chartHeight = chart.position.height - 60 // account for title bar + padding
    const chartWidth = chart.position.width - 16 // account for padding

    if (data.length === 0) {
      return (
        <div className="flex items-center justify-center h-full text-sm text-gray-400 dark:text-gray-500">
          No data in selected range
        </div>
      )
    }

    switch (chart.type) {
      case 'bar':
        return (
          <ResponsiveContainer width="100%" height={chartHeight}>
            <BarChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="text-gray-200 dark:text-gray-300" />
              <XAxis
                dataKey={xKey}
                tick={{ fontSize: 11 }}
                stroke="currentColor"
                className="text-gray-500 dark:text-gray-400"
              />
              <YAxis
                tick={{ fontSize: 11 }}
                stroke="currentColor"
                className="text-gray-500 dark:text-gray-400"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--tooltip-bg, #fff)',
                  border: '1px solid var(--tooltip-border, #e5e7eb)',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
              />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              {seriesKeys.map((key, i) => (
                <Bar
                  key={key}
                  dataKey={key}
                  fill={COLOR_PALETTE[i % COLOR_PALETTE.length]}
                  radius={[2, 2, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        )

      case 'line':
        return (
          <ResponsiveContainer width="100%" height={chartHeight}>
            <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="text-gray-200 dark:text-gray-300" />
              <XAxis
                dataKey={xKey}
                tick={{ fontSize: 11 }}
                stroke="currentColor"
                className="text-gray-500 dark:text-gray-400"
              />
              <YAxis
                tick={{ fontSize: 11 }}
                stroke="currentColor"
                className="text-gray-500 dark:text-gray-400"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--tooltip-bg, #fff)',
                  border: '1px solid var(--tooltip-border, #e5e7eb)',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
              />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              {seriesKeys.map((key, i) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={COLOR_PALETTE[i % COLOR_PALETTE.length]}
                  strokeWidth={2}
                  dot={{ r: 3, fill: COLOR_PALETTE[i % COLOR_PALETTE.length] }}
                  activeDot={{ r: 5 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )

      case 'pie': {
        // For pie chart, use the first data series
        const pieKey = seriesKeys[0] || xKey
        const pieData = data.map((row, i) => ({
          name: String(row[xKey] ?? `Item ${i + 1}`),
          value: typeof row[pieKey] === 'number' ? row[pieKey] : parseFloat(String(row[pieKey])) || 0,
        }))

        return (
          <ResponsiveContainer width="100%" height={chartHeight}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                outerRadius={Math.min(chartHeight, chartWidth) / 3}
                dataKey="value"
                nameKey="name"
                label={({ name, percent }) =>
                  `${name}: ${(percent * 100).toFixed(0)}%`
                }
                labelLine={{ strokeWidth: 1 }}
                fontSize={11}
              >
                {pieData.map((_entry, i) => (
                  <Cell key={`cell-${i}`} fill={COLOR_PALETTE[i % COLOR_PALETTE.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--tooltip-bg, #fff)',
                  border: '1px solid var(--tooltip-border, #e5e7eb)',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
              />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
            </PieChart>
          </ResponsiveContainer>
        )
      }

      case 'area':
        return (
          <ResponsiveContainer width="100%" height={chartHeight}>
            <AreaChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="text-gray-200 dark:text-gray-300" />
              <XAxis
                dataKey={xKey}
                tick={{ fontSize: 11 }}
                stroke="currentColor"
                className="text-gray-500 dark:text-gray-400"
              />
              <YAxis
                tick={{ fontSize: 11 }}
                stroke="currentColor"
                className="text-gray-500 dark:text-gray-400"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--tooltip-bg, #fff)',
                  border: '1px solid var(--tooltip-border, #e5e7eb)',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
              />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              {seriesKeys.map((key, i) => (
                <Area
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={COLOR_PALETTE[i % COLOR_PALETTE.length]}
                  fill={COLOR_PALETTE[i % COLOR_PALETTE.length]}
                  fillOpacity={0.2}
                  strokeWidth={2}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        )

      default:
        return null
    }
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        'absolute bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg flex flex-col overflow-hidden',
        isDragging && 'opacity-90 shadow-xl',
        isResizing && 'opacity-90'
      )}
      style={{
        left: chart.position.x,
        top: chart.position.y,
        width: chart.position.width,
        height: chart.position.height,
        zIndex: 20,
        userSelect: isDragging || isResizing ? 'none' : undefined,
      }}
    >
      {/* Title bar / drag handle */}
      <div
        className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 dark:bg-gray-950 border-b border-gray-200 dark:border-gray-700 cursor-move shrink-0"
        onMouseDown={handleDragStart}
      >
        <GripHorizontal className="h-3.5 w-3.5 text-gray-400 dark:text-gray-500 shrink-0" />
        <span className="flex-1 text-xs font-medium text-gray-700 dark:text-gray-300 truncate">
          {chart.title || 'Chart'}
        </span>

        {/* Toolbar */}
        <button
          onClick={(e) => {
            e.stopPropagation()
            onEdit()
          }}
          className="p-0.5 rounded text-gray-400 dark:text-gray-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:text-blue-400 dark:hover:bg-blue-900/30 transition-colors"
          title="Edit chart"
          onMouseDown={(e) => e.stopPropagation()}
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
          className="p-0.5 rounded text-gray-400 dark:text-gray-500 hover:text-red-500 hover:bg-red-50 dark:hover:text-red-400 dark:hover:bg-red-900/30 transition-colors"
          title="Delete chart"
          onMouseDown={(e) => e.stopPropagation()}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Chart body */}
      <div className="flex-1 p-2 min-h-0">{renderChart()}</div>

      {/* Resize handle */}
      <div
        className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize"
        onMouseDown={handleResizeStart}
      >
        <svg
          viewBox="0 0 16 16"
          className="w-full h-full text-gray-400 dark:text-gray-500"
        >
          <path
            d="M14 14L14 8M14 14L8 14M10 14L14 10"
            stroke="currentColor"
            strokeWidth="1.5"
            fill="none"
            strokeLinecap="round"
          />
        </svg>
      </div>
    </div>
  )
}
