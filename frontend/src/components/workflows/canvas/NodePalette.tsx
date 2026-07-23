import { useState } from 'react'
import { Play, GitBranch, Clock, Search } from 'lucide-react'
import { ACTION_LIBRARY } from './graph'

export type PaletteDragPayload =
  | { kind: 'action'; action_type: string }
  | { kind: 'condition' }
  | { kind: 'delay' }

export const PALETTE_MIME = 'application/x-obrain-workflow-node'

function DraggableItem({ payload, icon, label }: { payload: PaletteDragPayload; icon: React.ReactNode; label: string }) {
  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData(PALETTE_MIME, JSON.stringify(payload))
        e.dataTransfer.effectAllowed = 'move'
      }}
      className="flex items-center gap-2 px-2.5 py-2 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-xs text-gray-700 dark:text-gray-300 cursor-grab hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50/50 dark:hover:bg-blue-900/10 transition-colors"
    >
      {icon}
      <span className="truncate">{label}</span>
    </div>
  )
}

export default function NodePalette() {
  const [search, setSearch] = useState('')
  const filtered = ACTION_LIBRARY.filter((a) =>
    a.label.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="w-64 shrink-0 border-r border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50 h-full overflow-y-auto p-3">
      <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
        Logic
      </p>
      <div className="space-y-1.5 mb-4">
        <DraggableItem
          payload={{ kind: 'condition' }}
          icon={<GitBranch className="h-3.5 w-3.5 text-purple-500 shrink-0" />}
          label="Condition"
        />
        <DraggableItem
          payload={{ kind: 'delay' }}
          icon={<Clock className="h-3.5 w-3.5 text-gray-500 shrink-0" />}
          label="Delay"
        />
      </div>

      <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
        Actions
      </p>
      <div className="relative mb-2">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search actions…"
          className="w-full pl-7 pr-2 py-1.5 text-xs border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
        />
      </div>
      <div className="space-y-1.5">
        {filtered.map((a) => (
          <DraggableItem
            key={a.value}
            payload={{ kind: 'action', action_type: a.value }}
            icon={<Play className="h-3.5 w-3.5 text-blue-500 shrink-0" />}
            label={a.label}
          />
        ))}
      </div>
    </div>
  )
}
