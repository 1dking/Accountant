import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getOfficeDoc, updateOfficeDoc, starOfficeDoc } from '@/api/office'
import { useAuthStore } from '@/stores/authStore'
import EditorTopBar from '@/components/office/EditorTopBar'
import { Bold, Italic, Plus, Type } from 'lucide-react'
import { cn } from '@/lib/utils'

import * as Y from 'yjs'
import { WebsocketProvider } from 'y-websocket'

const NUM_ROWS = 50
const NUM_COLS = 26

function colLabel(index: number): string {
  let label = ''
  let n = index
  while (n >= 0) {
    label = String.fromCharCode(65 + (n % 26)) + label
    n = Math.floor(n / 26) - 1
  }
  return label
}

function cellId(row: number, col: number): string {
  return `${colLabel(col)}${row + 1}`
}

function generateColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  const hue = Math.abs(hash) % 360
  return `hsl(${hue}, 70%, 50%)`
}

interface SheetData {
  name: string
  cells: Record<string, CellData>
}

interface CellData {
  value: string
  bold?: boolean
  italic?: boolean
  bgColor?: string
  textColor?: string
}

export default function SheetEditorPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'connecting' | 'disconnected'>('connecting')
  const [connectedUsers, setConnectedUsers] = useState<{ name: string; color: string }[]>([])

  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number } | null>(null)
  const [editingCell, setEditingCell] = useState<{ row: number; col: number } | null>(null)
  const [formulaBarValue, setFormulaBarValue] = useState('')
  const [sheets, setSheets] = useState<SheetData[]>([{ name: 'Sheet1', cells: {} }])
  const [activeSheetIndex, setActiveSheetIndex] = useState(0)
  const gridRef = useRef<HTMLDivElement>(null)
  const cellRefs = useRef<Record<string, HTMLInputElement | null>>({})

  const { data: docData } = useQuery({
    queryKey: ['office-doc', id],
    queryFn: () => getOfficeDoc(id!),
    enabled: !!id,
  })

  const doc = docData?.data

  const updateMutation = useMutation({
    mutationFn: (data: { title?: string }) => updateOfficeDoc(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-doc', id] })
    },
  })

  const starMutation = useMutation({
    mutationFn: () => starOfficeDoc(id!, !doc?.is_starred),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-doc', id] })
    },
  })

  // Yjs setup for syncing cell data
  const ydoc = useMemo(() => new Y.Doc(), [])

  const wsProvider = useMemo(() => {
    if (!id) return null
    return new WebsocketProvider(
      import.meta.env.VITE_COLLAB_URL || 'ws://localhost:1234',
      id,
      ydoc,
      { params: { token: localStorage.getItem('access_token') || '' } }
    )
  }, [id, ydoc])

  // Sync Yjs map to local state
  useEffect(() => {
    const ySheets = ydoc.getArray<Y.Map<unknown>>('sheets')

    const syncFromYjs = () => {
      const newSheets: SheetData[] = []
      ySheets.forEach((ySheet: Y.Map<unknown>) => {
        const name = (ySheet.get('name') as string) || 'Sheet1'
        const yCells = ySheet.get('cells') as Y.Map<Y.Map<unknown>> | undefined
        const cells: Record<string, CellData> = {}
        if (yCells) {
          yCells.forEach((yCell: Y.Map<unknown>, key: string) => {
            cells[key] = {
              value: (yCell.get('value') as string) || '',
              bold: yCell.get('bold') as boolean | undefined,
              italic: yCell.get('italic') as boolean | undefined,
              bgColor: yCell.get('bgColor') as string | undefined,
              textColor: yCell.get('textColor') as string | undefined,
            }
          })
        }
        newSheets.push({ name, cells })
      })
      if (newSheets.length > 0) {
        setSheets(newSheets)
      }
    }

    // Initialize if empty
    if (ySheets.length === 0) {
      ydoc.transact(() => {
        const ySheet = new Y.Map<unknown>()
        ySheet.set('name', 'Sheet1')
        ySheet.set('cells', new Y.Map<Y.Map<unknown>>())
        ySheets.push([ySheet])
      })
    }

    ySheets.observeDeep(syncFromYjs)
    syncFromYjs()

    return () => {
      ySheets.unobserveDeep(syncFromYjs)
    }
  }, [ydoc])

  // Connection and awareness
  useEffect(() => {
    if (!wsProvider) return

    const onStatus = (event: { status: string }) => {
      if (event.status === 'connected') setConnectionStatus('connected')
      else if (event.status === 'connecting') setConnectionStatus('connecting')
      else setConnectionStatus('disconnected')
    }
    wsProvider.on('status', onStatus)

    const awareness = wsProvider.awareness
    const userName = user?.full_name || 'Anonymous'
    awareness.setLocalStateField('user', { name: userName, color: generateColor(userName) })

    const onAwarenessChange = () => {
      const states = awareness.getStates()
      const users: { name: string; color: string }[] = []
      states.forEach((state, clientId) => {
        if (clientId !== awareness.clientID && state.user) {
          users.push(state.user)
        }
      })
      setConnectedUsers(users)
    }
    awareness.on('change', onAwarenessChange)
    onAwarenessChange()

    return () => {
      wsProvider.off('status', onStatus)
      awareness.off('change', onAwarenessChange)
    }
  }, [wsProvider, user])

  useEffect(() => {
    return () => {
      wsProvider?.destroy()
      ydoc.destroy()
    }
  }, [wsProvider, ydoc])

  const activeSheet = sheets[activeSheetIndex] || sheets[0]

  const getCellValue = useCallback(
    (row: number, col: number) => {
      const key = cellId(row, col)
      return activeSheet?.cells[key]?.value || ''
    },
    [activeSheet]
  )

  const getCellData = useCallback(
    (row: number, col: number): CellData => {
      const key = cellId(row, col)
      return activeSheet?.cells[key] || { value: '' }
    },
    [activeSheet]
  )

  const setCellValue = useCallback(
    (row: number, col: number, value: string) => {
      const key = cellId(row, col)
      const ySheets = ydoc.getArray<Y.Map<unknown>>('sheets')
      const ySheet = ySheets.get(activeSheetIndex)
      if (!ySheet) return
      const yCells = ySheet.get('cells') as Y.Map<Y.Map<unknown>>
      if (!yCells) return

      ydoc.transact(() => {
        let yCell = yCells.get(key)
        if (!yCell) {
          yCell = new Y.Map<unknown>()
          yCells.set(key, yCell)
        }
        yCell.set('value', value)
      })
    },
    [ydoc, activeSheetIndex]
  )

  const toggleCellFormat = useCallback(
    (format: 'bold' | 'italic') => {
      if (!selectedCell) return
      const key = cellId(selectedCell.row, selectedCell.col)
      const ySheets = ydoc.getArray<Y.Map<unknown>>('sheets')
      const ySheet = ySheets.get(activeSheetIndex)
      if (!ySheet) return
      const yCells = ySheet.get('cells') as Y.Map<Y.Map<unknown>>
      if (!yCells) return

      ydoc.transact(() => {
        let yCell = yCells.get(key)
        if (!yCell) {
          yCell = new Y.Map<unknown>()
          yCells.set(key, yCell)
        }
        const current = yCell.get(format) as boolean | undefined
        yCell.set(format, !current)
      })
    },
    [ydoc, activeSheetIndex, selectedCell]
  )

  const addSheet = useCallback(() => {
    const ySheets = ydoc.getArray<Y.Map<unknown>>('sheets')
    ydoc.transact(() => {
      const ySheet = new Y.Map<unknown>()
      ySheet.set('name', `Sheet${ySheets.length + 1}`)
      ySheet.set('cells', new Y.Map<Y.Map<unknown>>())
      ySheets.push([ySheet])
    })
    setActiveSheetIndex(sheets.length)
  }, [ydoc, sheets.length])

  const handleCellClick = (row: number, col: number) => {
    setSelectedCell({ row, col })
    setFormulaBarValue(getCellValue(row, col))
  }

  const handleCellDoubleClick = (row: number, col: number) => {
    setEditingCell({ row, col })
    setSelectedCell({ row, col })
    setFormulaBarValue(getCellValue(row, col))
    setTimeout(() => {
      const key = cellId(row, col)
      cellRefs.current[key]?.focus()
    }, 0)
  }

  const handleCellInputChange = (row: number, col: number, value: string) => {
    setCellValue(row, col, value)
    setFormulaBarValue(value)
  }

  const handleCellBlur = () => {
    setEditingCell(null)
  }

  const handleKeyDown = (e: React.KeyboardEvent, row: number, col: number) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      setEditingCell(null)
      const nextRow = Math.min(row + 1, NUM_ROWS - 1)
      setSelectedCell({ row: nextRow, col })
      setFormulaBarValue(getCellValue(nextRow, col))
    } else if (e.key === 'Tab') {
      e.preventDefault()
      setEditingCell(null)
      const nextCol = Math.min(col + 1, NUM_COLS - 1)
      setSelectedCell({ row, col: nextCol })
      setFormulaBarValue(getCellValue(row, nextCol))
    } else if (e.key === 'Escape') {
      setEditingCell(null)
    }
  }

  const handleGridKeyDown = (e: React.KeyboardEvent) => {
    if (editingCell) return
    if (!selectedCell) return

    const { row, col } = selectedCell

    if (e.key === 'ArrowUp') {
      e.preventDefault()
      const newRow = Math.max(0, row - 1)
      setSelectedCell({ row: newRow, col })
      setFormulaBarValue(getCellValue(newRow, col))
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      const newRow = Math.min(NUM_ROWS - 1, row + 1)
      setSelectedCell({ row: newRow, col })
      setFormulaBarValue(getCellValue(newRow, col))
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      const newCol = Math.max(0, col - 1)
      setSelectedCell({ row, col: newCol })
      setFormulaBarValue(getCellValue(row, newCol))
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      const newCol = Math.min(NUM_COLS - 1, col + 1)
      setSelectedCell({ row, col: newCol })
      setFormulaBarValue(getCellValue(row, newCol))
    } else if (e.key === 'Enter' || e.key === 'F2') {
      e.preventDefault()
      handleCellDoubleClick(row, col)
    } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) {
      // Start editing with typed character
      setCellValue(row, col, e.key)
      setFormulaBarValue(e.key)
      setEditingCell({ row, col })
      setTimeout(() => {
        const key = cellId(row, col)
        const input = cellRefs.current[key]
        if (input) {
          input.focus()
          input.setSelectionRange(1, 1)
        }
      }, 0)
    } else if (e.key === 'Delete' || e.key === 'Backspace') {
      setCellValue(row, col, '')
      setFormulaBarValue('')
    }
  }

  const handleFormulaBarChange = (value: string) => {
    setFormulaBarValue(value)
    if (selectedCell) {
      setCellValue(selectedCell.row, selectedCell.col, value)
    }
  }

  const handleTitleChange = useCallback(
    (title: string) => {
      updateMutation.mutate({ title })
    },
    [updateMutation]
  )

  const selectedCellData = selectedCell ? getCellData(selectedCell.row, selectedCell.col) : null

  if (!id) return null

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] bg-white">
      <EditorTopBar
        docType="spreadsheet"
        docId={id}
        title={doc?.title || 'Untitled spreadsheet'}
        isStarred={doc?.is_starred ?? false}
        onTitleChange={handleTitleChange}
        onStar={() => starMutation.mutate()}
        connectedUsers={connectedUsers}
        connectionStatus={connectionStatus}
      />

      {/* Toolbar */}
      <div className="bg-white border-b px-3 py-1.5 flex items-center gap-1">
        <button
          onClick={() => toggleCellFormat('bold')}
          className={cn(
            'p-1.5 rounded-md transition-colors',
            selectedCellData?.bold
              ? 'bg-blue-100 text-blue-700'
              : 'text-gray-600 hover:bg-gray-100'
          )}
          title="Bold"
        >
          <Bold className="h-4 w-4" />
        </button>
        <button
          onClick={() => toggleCellFormat('italic')}
          className={cn(
            'p-1.5 rounded-md transition-colors',
            selectedCellData?.italic
              ? 'bg-blue-100 text-blue-700'
              : 'text-gray-600 hover:bg-gray-100'
          )}
          title="Italic"
        >
          <Italic className="h-4 w-4" />
        </button>
        <div className="w-px h-6 bg-gray-200 mx-1" />
        <div className="flex items-center gap-1 text-xs text-gray-500">
          <Type className="h-3.5 w-3.5" />
          <span>Format</span>
        </div>
      </div>

      {/* Formula bar */}
      <div className="bg-white border-b px-3 py-1 flex items-center gap-2">
        <div className="w-16 text-center text-sm font-medium text-gray-700 bg-gray-100 rounded px-2 py-1 border">
          {selectedCell ? cellId(selectedCell.row, selectedCell.col) : ''}
        </div>
        <div className="text-gray-300">|</div>
        <input
          type="text"
          value={formulaBarValue}
          onChange={(e) => handleFormulaBarChange(e.target.value)}
          placeholder="Enter value or formula..."
          className="flex-1 text-sm px-2 py-1 border rounded focus:outline-none focus:ring-1 focus:ring-green-500"
        />
      </div>

      {/* Spreadsheet grid */}
      <div
        ref={gridRef}
        className="flex-1 overflow-auto relative"
        tabIndex={0}
        onKeyDown={handleGridKeyDown}
      >
        <table className="border-collapse table-fixed" style={{ minWidth: NUM_COLS * 100 + 40 }}>
          <thead className="sticky top-0 z-10">
            <tr>
              {/* Row number header */}
              <th className="w-10 h-7 bg-gray-100 border border-gray-300 text-xs text-gray-500 sticky left-0 z-20" />
              {/* Column headers */}
              {Array.from({ length: NUM_COLS }, (_, col) => (
                <th
                  key={col}
                  className={cn(
                    'w-[100px] h-7 bg-gray-100 border border-gray-300 text-xs font-medium text-gray-600 select-none',
                    selectedCell?.col === col && 'bg-blue-100 text-blue-700'
                  )}
                >
                  {colLabel(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: NUM_ROWS }, (_, row) => (
              <tr key={row}>
                {/* Row number */}
                <td
                  className={cn(
                    'w-10 h-7 bg-gray-100 border border-gray-300 text-xs text-center text-gray-600 select-none sticky left-0 z-10',
                    selectedCell?.row === row && 'bg-blue-100 text-blue-700'
                  )}
                >
                  {row + 1}
                </td>
                {/* Cells */}
                {Array.from({ length: NUM_COLS }, (_, col) => {
                  const isSelected =
                    selectedCell?.row === row && selectedCell?.col === col
                  const isEditing =
                    editingCell?.row === row && editingCell?.col === col
                  const data = getCellData(row, col)
                  const key = cellId(row, col)

                  return (
                    <td
                      key={col}
                      className={cn(
                        'w-[100px] h-7 border border-gray-200 p-0 relative',
                        isSelected && 'outline outline-2 outline-blue-500 outline-offset-[-1px] z-[5]'
                      )}
                      style={{
                        backgroundColor: data.bgColor || undefined,
                      }}
                      onClick={() => handleCellClick(row, col)}
                      onDoubleClick={() => handleCellDoubleClick(row, col)}
                    >
                      {isEditing ? (
                        <input
                          ref={(el) => { cellRefs.current[key] = el }}
                          type="text"
                          value={data.value}
                          onChange={(e) => handleCellInputChange(row, col, e.target.value)}
                          onBlur={handleCellBlur}
                          onKeyDown={(e) => handleKeyDown(e, row, col)}
                          className="w-full h-full px-1 text-sm outline-none border-none bg-white"
                          style={{
                            fontWeight: data.bold ? 'bold' : undefined,
                            fontStyle: data.italic ? 'italic' : undefined,
                            color: data.textColor || undefined,
                          }}
                        />
                      ) : (
                        <div
                          className="w-full h-full px-1 text-sm leading-7 truncate"
                          style={{
                            fontWeight: data.bold ? 'bold' : undefined,
                            fontStyle: data.italic ? 'italic' : undefined,
                            color: data.textColor || undefined,
                          }}
                        >
                          {data.value}
                        </div>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Sheet tabs */}
      <div className="bg-gray-100 border-t px-2 py-1 flex items-center gap-1">
        {sheets.map((sheet, index) => (
          <button
            key={index}
            onClick={() => setActiveSheetIndex(index)}
            className={cn(
              'px-3 py-1 text-sm rounded-t border border-b-0 transition-colors',
              activeSheetIndex === index
                ? 'bg-white text-gray-900 font-medium border-gray-300'
                : 'bg-gray-200 text-gray-600 hover:bg-gray-50 border-transparent'
            )}
          >
            {sheet.name}
          </button>
        ))}
        <button
          onClick={addSheet}
          className="p-1 rounded text-gray-500 hover:bg-gray-200 hover:text-gray-700"
          title="Add sheet"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
