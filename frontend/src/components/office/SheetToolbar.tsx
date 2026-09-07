import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Undo2,
  Redo2,
  Bold,
  Italic,
  Underline,
  Strikethrough,
  AlignLeft,
  AlignCenter,
  AlignRight,
  ArrowUpAZ,
  ArrowDownAZ,
  Filter,
  Search,
  BarChart3,
  Upload,
  Download,
  RemoveFormatting,
  ChevronDown,
  Snowflake,
  Merge,
  Grid3x3,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CellData } from '@/lib/spreadsheet/types'
import { useTranslation } from 'react-i18next'

interface SheetToolbarProps {
  selectedCellData: CellData | null
  selectionRange: { startRow: number; startCol: number; endRow: number; endCol: number } | null
  onToggleFormat: (format: 'bold' | 'italic' | 'underline' | 'strikethrough') => void
  onSetBgColor: (color: string) => void
  onSetTextColor: (color: string) => void
  onSetAlign: (align: 'left' | 'center' | 'right') => void
  onSetFormat: (format: 'plain' | 'number' | 'currency' | 'percent' | 'date') => void
  onSetFontSize: (size: number) => void
  onClearFormatting: () => void
  onMergeCells: () => void
  onUnmergeCells: () => void
  isMerged: boolean
  onUndo: () => void
  onRedo: () => void
  canUndo: boolean
  canRedo: boolean
  onSetBorders: (borders: { top?: boolean; bottom?: boolean; left?: boolean; right?: boolean }) => void
  onInsertChart: () => void
  onToggleFilter: () => void
  filterEnabled: boolean
  onSort: (direction: 'asc' | 'desc') => void
  onExportCsv: () => void
  onImportCsv: () => void
  onExportXlsx?: () => void
  onImportXlsx?: () => void
  onToggleFindReplace: () => void
  onFreezeRow: (count: number) => void
  onFreezeCol: (count: number) => void
  freezeRow: number
  freezeCol: number
}

const FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36]

interface ToolbarButtonProps {
  onClick: () => void
  isActive?: boolean
  disabled?: boolean
  title: string
  children: React.ReactNode
  className?: string
}

function ToolbarButton({ onClick, isActive, disabled, title, children, className }: ToolbarButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cn(
        'p-1.5 rounded-md transition-colors',
        isActive
          ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:bg-blue-900/50 dark:text-blue-400'
          : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:bg-gray-700 dark:hover:text-gray-200',
        disabled && 'opacity-40 cursor-not-allowed',
        className
      )}
    >
      {children}
    </button>
  )
}

function ToolbarSeparator() {
  return <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-1" />
}

function useClickOutside(ref: React.RefObject<HTMLElement | null>, onClose: () => void) {
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [ref, onClose])
}

interface DropdownProps {
  open: boolean
  onClose: () => void
  children: React.ReactNode
  className?: string
}

function Dropdown({ open, onClose, children, className }: DropdownProps) {
  const ref = useRef<HTMLDivElement>(null)
  useClickOutside(ref, onClose)

  if (!open) return null

  return (
    <div
      ref={ref}
      className={cn(
        'absolute top-full left-0 mt-1 z-50 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 shadow-lg rounded-lg py-1 min-w-[160px]',
        className
      )}
    >
      {children}
    </div>
  )
}

interface DropdownItemProps {
  onClick: () => void
  children: React.ReactNode
  active?: boolean
}

function DropdownItem({ onClick, children, active }: DropdownItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left px-3 py-1.5 text-sm transition-colors',
        active
          ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
          : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-700'
      )}
    >
      {children}
    </button>
  )
}

export default function SheetToolbar({
  selectedCellData,
  selectionRange: _selectionRange,
  onToggleFormat,
  onSetBgColor,
  onSetTextColor,
  onSetAlign,
  onSetFormat,
  onSetFontSize,
  onClearFormatting,
  onMergeCells,
  onUnmergeCells,
  isMerged,
  onUndo,
  onRedo,
  canUndo,
  canRedo,
  onSetBorders,
  onInsertChart,
  onToggleFilter,
  filterEnabled,
  onSort,
  onExportCsv,
  onImportCsv,
  onExportXlsx,
  onImportXlsx,
  onToggleFindReplace,
  onFreezeRow,
  onFreezeCol,
  freezeRow,
  freezeCol,
}: SheetToolbarProps) {
  const { t } = useTranslation('ui')
  const [bordersOpen, setBordersOpen] = useState(false)
  const [freezeOpen, setFreezeOpen] = useState(false)

  const bgColorRef = useRef<HTMLInputElement>(null)
  const textColorRef = useRef<HTMLInputElement>(null)

  const currentBgColor = selectedCellData?.bgColor || '#ffffff'
  const currentTextColor = selectedCellData?.textColor || '#000000'
  const currentFontSize = selectedCellData?.fontSize || 12
  const currentFormat = selectedCellData?.format || 'plain'
  const currentAlign = selectedCellData?.align || 'left'

  const closeBorders = useCallback(() => setBordersOpen(false), [])
  const closeFreeze = useCallback(() => setFreezeOpen(false), [])

  return (
    <div className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-3 py-1 flex items-center gap-0.5 flex-wrap h-10">
      {/* Group 1: Undo/Redo */}
      <ToolbarButton onClick={onUndo} disabled={!canUndo} title={t('ui:SheetToolbar.undoCtrlZ')}>
        <Undo2 className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton onClick={onRedo} disabled={!canRedo} title={t('ui:SheetToolbar.redoCtrlY')}>
        <Redo2 className="h-4 w-4" />
      </ToolbarButton>

      <ToolbarSeparator />

      {/* Group 2: Text Formatting */}
      <select
        value={currentFontSize}
        onChange={(e) => onSetFontSize(Number(e.target.value))}
        title={t('ui:SheetToolbar.fontSize')}
        className="h-7 px-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
      >
        {FONT_SIZES.map((size) => (
          <option key={size} value={size}>
            {size}
          </option>
        ))}
      </select>

      <ToolbarButton
        onClick={() => onToggleFormat('bold')}
        isActive={selectedCellData?.bold}
        title={t('ui:SheetToolbar.boldCtrlB')}
      >
        <Bold className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => onToggleFormat('italic')}
        isActive={selectedCellData?.italic}
        title={t('ui:SheetToolbar.italicCtrlI')}
      >
        <Italic className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => onToggleFormat('underline')}
        isActive={selectedCellData?.underline}
        title={t('ui:SheetToolbar.underlineCtrlU')}
      >
        <Underline className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => onToggleFormat('strikethrough')}
        isActive={selectedCellData?.strikethrough}
        title={t('ui:SheetToolbar.strikethrough')}
      >
        <Strikethrough className="h-4 w-4" />
      </ToolbarButton>

      <ToolbarSeparator />

      {/* Group 3: Colors */}
      <button
        onClick={() => bgColorRef.current?.click()}
        title={t('ui:SheetToolbar.backgroundColor')}
        className="p-1.5 rounded-md transition-colors text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-400 dark:hover:bg-gray-700"
      >
        <div
          className="h-4 w-4 rounded border border-gray-300 dark:border-gray-600"
          style={{ backgroundColor: currentBgColor }}
        />
        <input
          ref={bgColorRef}
          type="color"
          value={currentBgColor}
          onChange={(e) => onSetBgColor(e.target.value)}
          className="sr-only"
          tabIndex={-1}
        />
      </button>

      <button
        onClick={() => textColorRef.current?.click()}
        title={t('ui:SheetToolbar.textColor')}
        className="p-1.5 rounded-md transition-colors text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-400 dark:hover:bg-gray-700"
      >
        <div className="h-4 w-4 flex flex-col items-center justify-center">
          <span className="text-xs font-bold leading-none" style={{ color: currentTextColor }}>
            A
          </span>
          <div
            className="w-full h-0.5 rounded-full mt-px"
            style={{ backgroundColor: currentTextColor }}
          />
        </div>
        <input
          ref={textColorRef}
          type="color"
          value={currentTextColor}
          onChange={(e) => onSetTextColor(e.target.value)}
          className="sr-only"
          tabIndex={-1}
        />
      </button>

      <ToolbarSeparator />

      {/* Group 4: Alignment */}
      <ToolbarButton
        onClick={() => onSetAlign('left')}
        isActive={currentAlign === 'left'}
        title={t('ui:SheetToolbar.alignLeft')}
      >
        <AlignLeft className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => onSetAlign('center')}
        isActive={currentAlign === 'center'}
        title={t('ui:SheetToolbar.alignCenter')}
      >
        <AlignCenter className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => onSetAlign('right')}
        isActive={currentAlign === 'right'}
        title={t('ui:SheetToolbar.alignRight')}
      >
        <AlignRight className="h-4 w-4" />
      </ToolbarButton>

      <ToolbarSeparator />

      {/* Group 5: Number Format */}
      <select
        value={currentFormat}
        onChange={(e) => onSetFormat(e.target.value as 'plain' | 'number' | 'currency' | 'percent' | 'date')}
        title={t('ui:SheetToolbar.numberFormat')}
        className="h-7 px-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
      >
        <option value="plain">{t('ui:SheetToolbar.plainText')}</option>
        <option value="number">{t('ui:SheetToolbar.number123450')}</option>
        <option value="currency">{t('ui:SheetToolbar.currency123450')}</option>
        <option value="percent">{t('ui:SheetToolbar.percent1250')}</option>
        <option value="date">{t('ui:SheetToolbar.date')}</option>
      </select>

      <ToolbarSeparator />

      {/* Group 6: Cell Operations */}
      <ToolbarButton
        onClick={isMerged ? onUnmergeCells : onMergeCells}
        isActive={isMerged}
        title={isMerged ? t('ui:SheetToolbar.unmergeCells') : t('ui:SheetToolbar.mergeCells')}
      >
        <Merge className="h-4 w-4" />
      </ToolbarButton>

      <div className="relative">
        <ToolbarButton
          onClick={() => {
            setBordersOpen((prev) => !prev)
            setFreezeOpen(false)
          }}
          title={t('ui:SheetToolbar.borders')}
        >
          <span className="flex items-center gap-0.5">
            <Grid3x3 className="h-4 w-4" />
            <ChevronDown className="h-3 w-3" />
          </span>
        </ToolbarButton>
        <Dropdown open={bordersOpen} onClose={closeBorders}>
          <DropdownItem
            onClick={() => {
              onSetBorders({ top: true, bottom: true, left: true, right: true })
              setBordersOpen(false)
            }}
          >
           {t('ui:SheetToolbar.allBorders')}
          </DropdownItem>
          <DropdownItem
            onClick={() => {
              onSetBorders({ top: false, bottom: false, left: false, right: false })
              setBordersOpen(false)
            }}
          >
           {t('ui:SheetToolbar.noBorders')}
          </DropdownItem>
          <div className="h-px bg-gray-200 dark:bg-gray-700 my-1" />
          <DropdownItem
            onClick={() => {
              onSetBorders({ top: true })
              setBordersOpen(false)
            }}
          >
           {t('ui:SheetToolbar.top')}
          </DropdownItem>
          <DropdownItem
            onClick={() => {
              onSetBorders({ bottom: true })
              setBordersOpen(false)
            }}
          >
           {t('ui:SheetToolbar.bottom')}
          </DropdownItem>
          <DropdownItem
            onClick={() => {
              onSetBorders({ left: true })
              setBordersOpen(false)
            }}
          >
           {t('ui:SheetToolbar.left')}
          </DropdownItem>
          <DropdownItem
            onClick={() => {
              onSetBorders({ right: true })
              setBordersOpen(false)
            }}
          >
           {t('ui:SheetToolbar.right')}
          </DropdownItem>
          <div className="h-px bg-gray-200 dark:bg-gray-700 my-1" />
          <DropdownItem
            onClick={() => {
              onSetBorders({ top: true, bottom: true, left: true, right: true })
              setBordersOpen(false)
            }}
          >
           {t('ui:SheetToolbar.outerBorders')}
          </DropdownItem>
        </Dropdown>
      </div>

      <ToolbarSeparator />

      {/* Group 7: Data */}
      <ToolbarButton onClick={() => onSort('asc')} title={t('ui:SheetToolbar.sortAscending')}>
        <ArrowUpAZ className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton onClick={() => onSort('desc')} title={t('ui:SheetToolbar.sortDescending')}>
        <ArrowDownAZ className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton onClick={onToggleFilter} isActive={filterEnabled} title={t('ui:SheetToolbar.toggleFilter')}>
        <Filter className="h-4 w-4" />
      </ToolbarButton>

      <ToolbarSeparator />

      {/* Group 8: Tools */}
      <ToolbarButton onClick={onToggleFindReplace} title={t('ui:SheetToolbar.findReplaceCtrlH')}>
        <Search className="h-4 w-4" />
      </ToolbarButton>

      <div className="relative">
        <ToolbarButton
          onClick={() => {
            setFreezeOpen((prev) => !prev)
            setBordersOpen(false)
          }}
          isActive={freezeRow > 0 || freezeCol > 0}
          title={t('ui:SheetToolbar.freezeRowsColumns')}
        >
          <span className="flex items-center gap-0.5">
            <Snowflake className="h-4 w-4" />
            <ChevronDown className="h-3 w-3" />
          </span>
        </ToolbarButton>
        <Dropdown open={freezeOpen} onClose={closeFreeze} className="min-w-[180px]">
          <div className="px-3 py-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
           {t('ui:SheetToolbar.freezeRows')}
          </div>
          <DropdownItem active={freezeRow === 0} onClick={() => { onFreezeRow(0); setFreezeOpen(false) }}>
           {t('ui:SheetToolbar.noFrozenRows')}
          </DropdownItem>
          <DropdownItem active={freezeRow === 1} onClick={() => { onFreezeRow(1); setFreezeOpen(false) }}>
           {t('ui:SheetToolbar.n1Row')}
          </DropdownItem>
          <DropdownItem active={freezeRow === 2} onClick={() => { onFreezeRow(2); setFreezeOpen(false) }}>
           {t('ui:SheetToolbar.n2Rows')}
          </DropdownItem>
          <DropdownItem active={freezeRow === 3} onClick={() => { onFreezeRow(3); setFreezeOpen(false) }}>
           {t('ui:SheetToolbar.n3Rows')}
          </DropdownItem>
          <div className="h-px bg-gray-200 dark:bg-gray-700 my-1" />
          <div className="px-3 py-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
           {t('ui:SheetToolbar.freezeColumns')}
          </div>
          <DropdownItem active={freezeCol === 0} onClick={() => { onFreezeCol(0); setFreezeOpen(false) }}>
           {t('ui:SheetToolbar.noFrozenColumns')}
          </DropdownItem>
          <DropdownItem active={freezeCol === 1} onClick={() => { onFreezeCol(1); setFreezeOpen(false) }}>
           {t('ui:SheetToolbar.n1Column')}
          </DropdownItem>
          <DropdownItem active={freezeCol === 2} onClick={() => { onFreezeCol(2); setFreezeOpen(false) }}>
           {t('ui:SheetToolbar.n2Columns')}
          </DropdownItem>
          <DropdownItem active={freezeCol === 3} onClick={() => { onFreezeCol(3); setFreezeOpen(false) }}>
           {t('ui:SheetToolbar.n3Columns')}
          </DropdownItem>
        </Dropdown>
      </div>

      <ToolbarButton onClick={onInsertChart} title={t('ui:SheetToolbar.insertChart')}>
        <BarChart3 className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton onClick={onImportCsv} title={t('ui:SheetToolbar.importCsv')}>
        <Upload className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton onClick={onExportCsv} title={t('ui:SheetToolbar.exportCsv')}>
        <Download className="h-4 w-4" />
      </ToolbarButton>
      {onExportXlsx && (
        <ToolbarButton onClick={onExportXlsx} title={t('ui:SheetToolbar.downloadAsXlsx')}>
          <span className="text-[9px] font-bold leading-none">XLS</span>
        </ToolbarButton>
      )}
      {onImportXlsx && (
        <ToolbarButton onClick={onImportXlsx} title={t('ui:SheetToolbar.importXlsx')}>
          <span className="text-[9px] font-bold leading-none">{t('ui:SheetToolbar.xls')}</span>
        </ToolbarButton>
      )}

      <ToolbarSeparator />

      {/* Group 9: Clear */}
      <ToolbarButton onClick={onClearFormatting} title={t('ui:SheetToolbar.clearFormatting')}>
        <RemoveFormatting className="h-4 w-4" />
      </ToolbarButton>
    </div>
  )
}
