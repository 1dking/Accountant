import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import {
  ChevronUp,
  ChevronDown,
  X,
  CaseSensitive,
  WholeWord,
  Replace,
  ReplaceAll,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CellData } from '@/lib/spreadsheet/types'
import { parseCellRef } from '@/lib/spreadsheet/types'

interface SheetFindReplaceProps {
  visible: boolean
  onClose: () => void
  cells: Record<string, CellData>
  onNavigateToCell: (row: number, col: number) => void
  onReplace: (cellKey: string, oldValue: string, newValue: string) => void
  onReplaceAll: (oldValue: string, newValue: string) => void
}

interface MatchResult {
  key: string
  row: number
  col: number
}

export default function SheetFindReplace({
  visible,
  onClose,
  cells,
  onNavigateToCell,
  onReplace,
  onReplaceAll,
}: SheetFindReplaceProps) {
  const [searchTerm, setSearchTerm] = useState('')
  const [replaceTerm, setReplaceTerm] = useState('')
  const [matchCase, setMatchCase] = useState(false)
  const [matchEntireCell, setMatchEntireCell] = useState(false)
  const [showReplace, setShowReplace] = useState(false)
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0)

  const findInputRef = useRef<HTMLInputElement>(null)

  // Compute matches from cells whenever search criteria change
  const matches: MatchResult[] = useMemo(() => {
    if (!searchTerm) return []

    const results: MatchResult[] = []
    const term = matchCase ? searchTerm : searchTerm.toLowerCase()

    for (const [key, cell] of Object.entries(cells)) {
      if (!cell.value) continue

      const cellValue = matchCase ? cell.value : cell.value.toLowerCase()
      let isMatch = false

      if (matchEntireCell) {
        isMatch = cellValue === term
      } else {
        isMatch = cellValue.includes(term)
      }

      if (isMatch) {
        const parsed = parseCellRef(key)
        if (parsed) {
          results.push({ key, row: parsed.row, col: parsed.col })
        }
      }
    }

    // Sort by row then column for consistent navigation order
    results.sort((a, b) => {
      if (a.row !== b.row) return a.row - b.row
      return a.col - b.col
    })

    return results
  }, [cells, searchTerm, matchCase, matchEntireCell])

  // Reset current match index when matches change
  useEffect(() => {
    setCurrentMatchIndex(0)
    if (matches.length > 0) {
      onNavigateToCell(matches[0].row, matches[0].col)
    }
  }, [matches]) // eslint-disable-line react-hooks/exhaustive-deps

  // Focus find input when bar becomes visible
  useEffect(() => {
    if (visible && findInputRef.current) {
      findInputRef.current.focus()
      findInputRef.current.select()
    }
  }, [visible])

  // Global Ctrl+F handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && visible) {
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [visible, onClose])

  const navigateToMatch = useCallback(
    (index: number) => {
      if (matches.length === 0) return
      const wrappedIndex = ((index % matches.length) + matches.length) % matches.length
      setCurrentMatchIndex(wrappedIndex)
      const match = matches[wrappedIndex]
      onNavigateToCell(match.row, match.col)
    },
    [matches, onNavigateToCell]
  )

  const goToNext = useCallback(() => {
    navigateToMatch(currentMatchIndex + 1)
  }, [currentMatchIndex, navigateToMatch])

  const goToPrevious = useCallback(() => {
    navigateToMatch(currentMatchIndex - 1)
  }, [currentMatchIndex, navigateToMatch])

  const handleFindKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (e.shiftKey) {
        goToPrevious()
      } else {
        goToNext()
      }
    }
  }

  const handleReplace = () => {
    if (matches.length === 0) return
    const match = matches[currentMatchIndex]
    if (!match) return
    onReplace(match.key, searchTerm, replaceTerm)
  }

  const handleReplaceAll = () => {
    if (matches.length === 0 || !searchTerm) return
    onReplaceAll(searchTerm, replaceTerm)
  }

  if (!visible) return null

  const hasMatches = matches.length > 0
  const matchCountText = searchTerm
    ? hasMatches
      ? `${currentMatchIndex + 1} of ${matches.length} match${matches.length !== 1 ? 'es' : ''}`
      : 'No matches'
    : ''

  return (
    <div className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-3 py-1.5 flex items-center gap-2 h-10">
      {/* Find input */}
      <div className="relative flex items-center">
        <input
          ref={findInputRef}
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onKeyDown={handleFindKeyDown}
          placeholder="Find"
          className="h-7 w-48 px-2 pr-16 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        />
        {/* Match count inside the input area */}
        <span className="absolute right-2 text-xs text-gray-400 dark:text-gray-500 pointer-events-none whitespace-nowrap">
          {matchCountText}
        </span>
      </div>

      {/* Toggle case sensitive */}
      <button
        onClick={() => setMatchCase(!matchCase)}
        className={cn(
          'h-7 w-7 flex items-center justify-center rounded text-sm transition-colors',
          matchCase
            ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
            : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
        )}
        title="Match case"
      >
        <CaseSensitive className="h-4 w-4" />
      </button>

      {/* Toggle match entire cell */}
      <button
        onClick={() => setMatchEntireCell(!matchEntireCell)}
        className={cn(
          'h-7 w-7 flex items-center justify-center rounded text-sm transition-colors',
          matchEntireCell
            ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
            : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
        )}
        title="Match entire cell"
      >
        <WholeWord className="h-4 w-4" />
      </button>

      {/* Previous / Next */}
      <button
        onClick={goToPrevious}
        disabled={!hasMatches}
        className={cn(
          'h-7 w-7 flex items-center justify-center rounded transition-colors',
          hasMatches
            ? 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
            : 'text-gray-300 dark:text-gray-600 cursor-not-allowed'
        )}
        title="Previous match (Shift+Enter)"
      >
        <ChevronUp className="h-4 w-4" />
      </button>
      <button
        onClick={goToNext}
        disabled={!hasMatches}
        className={cn(
          'h-7 w-7 flex items-center justify-center rounded transition-colors',
          hasMatches
            ? 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
            : 'text-gray-300 dark:text-gray-600 cursor-not-allowed'
        )}
        title="Next match (Enter)"
      >
        <ChevronDown className="h-4 w-4" />
      </button>

      {/* Separator */}
      <div className="w-px h-5 bg-gray-200 dark:bg-gray-700 mx-1" />

      {/* Toggle replace mode */}
      <button
        onClick={() => setShowReplace(!showReplace)}
        className={cn(
          'h-7 px-2 flex items-center gap-1 rounded text-xs font-medium transition-colors',
          showReplace
            ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
            : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
        )}
        title="Toggle replace"
      >
        <Replace className="h-3.5 w-3.5" />
        Replace
      </button>

      {/* Replace input and buttons */}
      {showReplace && (
        <>
          <input
            type="text"
            value={replaceTerm}
            onChange={(e) => setReplaceTerm(e.target.value)}
            placeholder="Replace with"
            className="h-7 w-40 px-2 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
          <button
            onClick={handleReplace}
            disabled={!hasMatches}
            className={cn(
              'h-7 px-2 flex items-center gap-1 rounded text-xs font-medium transition-colors',
              hasMatches
                ? 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                : 'text-gray-300 dark:text-gray-600 cursor-not-allowed'
            )}
            title="Replace current match"
          >
            <Replace className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={handleReplaceAll}
            disabled={!hasMatches}
            className={cn(
              'h-7 px-2 flex items-center gap-1 rounded text-xs font-medium transition-colors',
              hasMatches
                ? 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                : 'text-gray-300 dark:text-gray-600 cursor-not-allowed'
            )}
            title="Replace all matches"
          >
            <ReplaceAll className="h-3.5 w-3.5" />
            All
          </button>
        </>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Close button */}
      <button
        onClick={onClose}
        className="h-7 w-7 flex items-center justify-center rounded text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        title="Close (Escape)"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
