import { useEffect, useRef, useCallback } from 'react'
import {
  Scissors,
  Copy,
  ClipboardPaste,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Trash2,
  EyeOff,
  Eye,
  ArrowUpAZ,
  ArrowDownAZ,
  Eraser,
} from 'lucide-react'

interface SheetContextMenuProps {
  x: number
  y: number
  visible: boolean
  onClose: () => void
  onInsertRowAbove: () => void
  onInsertRowBelow: () => void
  onInsertColLeft: () => void
  onInsertColRight: () => void
  onDeleteRow: () => void
  onDeleteCol: () => void
  onHideRow: () => void
  onHideCol: () => void
  onUnhideRows: () => void
  onUnhideCols: () => void
  onSortAsc: () => void
  onSortDesc: () => void
  onCut: () => void
  onCopy: () => void
  onPaste: () => void
  onClearContents: () => void
  hasHiddenRows: boolean
  hasHiddenCols: boolean
}

interface MenuItemProps {
  icon: React.ReactNode
  label: string
  onClick: () => void
}

function MenuItem({ icon, label, onClick }: MenuItemProps) {
  return (
    <button
      onClick={onClick}
      className="w-full px-3 py-1.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer flex items-center gap-2 text-gray-700 dark:text-gray-300"
    >
      {icon}
      {label}
    </button>
  )
}

function Divider() {
  return <div className="border-t border-gray-200 dark:border-gray-700 my-1" />
}

export default function SheetContextMenu({
  x,
  y,
  visible,
  onClose,
  onInsertRowAbove,
  onInsertRowBelow,
  onInsertColLeft,
  onInsertColRight,
  onDeleteRow,
  onDeleteCol,
  onHideRow,
  onHideCol,
  onUnhideRows,
  onUnhideCols,
  onSortAsc,
  onSortDesc,
  onCut,
  onCopy,
  onPaste,
  onClearContents,
  hasHiddenRows,
  hasHiddenCols,
}: SheetContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)

  const handleAction = useCallback(
    (action: () => void) => {
      action()
      onClose()
    },
    [onClose]
  )

  // Close on click outside
  useEffect(() => {
    if (!visible) return

    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    // Delay attaching listener so the same right-click event doesn't immediately close it
    const timeoutId = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleEscape)
    }, 0)

    return () => {
      clearTimeout(timeoutId)
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [visible, onClose])

  // Adjust position to stay on-screen
  useEffect(() => {
    if (!visible || !menuRef.current) return

    const menu = menuRef.current
    const rect = menu.getBoundingClientRect()
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    let adjustedX = x
    let adjustedY = y

    if (x + rect.width > viewportWidth) {
      adjustedX = viewportWidth - rect.width - 8
    }
    if (y + rect.height > viewportHeight) {
      adjustedY = viewportHeight - rect.height - 8
    }
    if (adjustedX < 0) adjustedX = 8
    if (adjustedY < 0) adjustedY = 8

    menu.style.left = `${adjustedX}px`
    menu.style.top = `${adjustedY}px`
  }, [visible, x, y])

  if (!visible) return null

  const iconSize = 'h-4 w-4'

  return (
    <div
      ref={menuRef}
      className="fixed z-50 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-1 min-w-[200px]"
      style={{ left: x, top: y }}
    >
      {/* Cut / Copy / Paste */}
      <MenuItem
        icon={<Scissors className={iconSize} />}
        label="Cut"
        onClick={() => handleAction(onCut)}
      />
      <MenuItem
        icon={<Copy className={iconSize} />}
        label="Copy"
        onClick={() => handleAction(onCopy)}
      />
      <MenuItem
        icon={<ClipboardPaste className={iconSize} />}
        label="Paste"
        onClick={() => handleAction(onPaste)}
      />

      <Divider />

      {/* Insert rows */}
      <MenuItem
        icon={<ArrowUp className={iconSize} />}
        label="Insert row above"
        onClick={() => handleAction(onInsertRowAbove)}
      />
      <MenuItem
        icon={<ArrowDown className={iconSize} />}
        label="Insert row below"
        onClick={() => handleAction(onInsertRowBelow)}
      />

      {/* Insert columns */}
      <MenuItem
        icon={<ArrowLeft className={iconSize} />}
        label="Insert column left"
        onClick={() => handleAction(onInsertColLeft)}
      />
      <MenuItem
        icon={<ArrowRight className={iconSize} />}
        label="Insert column right"
        onClick={() => handleAction(onInsertColRight)}
      />

      <Divider />

      {/* Delete */}
      <MenuItem
        icon={<Trash2 className={iconSize} />}
        label="Delete row"
        onClick={() => handleAction(onDeleteRow)}
      />
      <MenuItem
        icon={<Trash2 className={iconSize} />}
        label="Delete column"
        onClick={() => handleAction(onDeleteCol)}
      />

      <Divider />

      {/* Hide */}
      <MenuItem
        icon={<EyeOff className={iconSize} />}
        label="Hide row"
        onClick={() => handleAction(onHideRow)}
      />
      <MenuItem
        icon={<EyeOff className={iconSize} />}
        label="Hide column"
        onClick={() => handleAction(onHideCol)}
      />

      {/* Unhide (conditional) */}
      {hasHiddenRows && (
        <MenuItem
          icon={<Eye className={iconSize} />}
          label="Show hidden rows"
          onClick={() => handleAction(onUnhideRows)}
        />
      )}
      {hasHiddenCols && (
        <MenuItem
          icon={<Eye className={iconSize} />}
          label="Show hidden columns"
          onClick={() => handleAction(onUnhideCols)}
        />
      )}

      <Divider />

      {/* Sort */}
      <MenuItem
        icon={<ArrowUpAZ className={iconSize} />}
        label="Sort A \u2192 Z"
        onClick={() => handleAction(onSortAsc)}
      />
      <MenuItem
        icon={<ArrowDownAZ className={iconSize} />}
        label="Sort Z \u2192 A"
        onClick={() => handleAction(onSortDesc)}
      />

      <Divider />

      {/* Clear */}
      <MenuItem
        icon={<Eraser className={iconSize} />}
        label="Clear contents"
        onClick={() => handleAction(onClearContents)}
      />
    </div>
  )
}
