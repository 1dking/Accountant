import { X, Trash2 } from 'lucide-react'
import StepConfigForm from '@/components/workflows/StepConfigForm'
import { ACTION_LIBRARY, TRIGGER_LIBRARY, type GraphNode } from './graph'

interface NodeConfigDrawerProps {
  node: GraphNode
  onChange: (node: GraphNode) => void
  onDelete: () => void
  onClose: () => void
}

export default function NodeConfigDrawer({ node, onChange, onDelete, onClose }: NodeConfigDrawerProps) {
  return (
    <div className="w-80 shrink-0 border-l border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 h-full overflow-y-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 capitalize">
          {node.kind} settings
        </h3>
        <button onClick={onClose} className="p-1 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
          <X className="h-4 w-4" />
        </button>
      </div>

      {node.kind === 'trigger' && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Trigger Type</label>
            <select
              value={node.trigger_type ?? ''}
              onChange={(e) => onChange({ ...node, trigger_type: e.target.value })}
              className="w-full px-2 py-1.5 text-xs border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
            >
              <option value="" disabled>Select a trigger…</option>
              {TRIGGER_LIBRARY.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <StepConfigForm
            label="Trigger Config (JSON)"
            value={node.trigger_config ? JSON.stringify(node.trigger_config, null, 2) : ''}
            onChange={(value) => {
              try {
                onChange({ ...node, trigger_config: value.trim() ? JSON.parse(value) : undefined })
              } catch {
                // leave trigger_config unchanged until the JSON is valid again
              }
            }}
          />
        </div>
      )}

      {node.kind === 'action' && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Action Type</label>
            <select
              value={node.action_type ?? ''}
              onChange={(e) => onChange({ ...node, action_type: e.target.value })}
              className="w-full px-2 py-1.5 text-xs border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
            >
              <option value="" disabled>Select an action…</option>
              {ACTION_LIBRARY.map((a) => (
                <option key={a.value} value={a.value}>{a.label}</option>
              ))}
            </select>
          </div>
          <StepConfigForm
            value={node.config ? JSON.stringify(node.config, null, 2) : '{}'}
            onChange={(value) => {
              try {
                onChange({ ...node, config: JSON.parse(value) })
              } catch {
                // leave config unchanged until the JSON is valid again
              }
            }}
            rows={6}
          />
        </div>
      )}

      {node.kind === 'condition' && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Field</label>
            <input
              type="text"
              value={node.condition?.field ?? ''}
              onChange={(e) =>
                onChange({ ...node, condition: { ...(node.condition ?? { operator: 'eq' }), field: e.target.value } })
              }
              placeholder="e.g. amount"
              className="w-full px-2 py-1.5 text-xs border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Operator</label>
            <select
              value={node.condition?.operator ?? 'eq'}
              onChange={(e) =>
                onChange({
                  ...node,
                  condition: {
                    ...(node.condition ?? { field: '' }),
                    operator: e.target.value as 'eq' | 'neq' | 'contains' | 'exists',
                  },
                })
              }
              className="w-full px-2 py-1.5 text-xs border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
            >
              <option value="eq">equals</option>
              <option value="neq">not equals</option>
              <option value="contains">contains</option>
              <option value="exists">exists</option>
            </select>
          </div>
          {node.condition?.operator !== 'exists' && (
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Value</label>
              <input
                type="text"
                value={node.condition?.value ?? ''}
                onChange={(e) =>
                  onChange({ ...node, condition: { ...(node.condition ?? { field: '', operator: 'eq' }), value: e.target.value } })
                }
                className="w-full px-2 py-1.5 text-xs border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
              />
            </div>
          )}
          <p className="text-[11px] text-gray-400 dark:text-gray-500">
            Green (true) and red (false) handles on the node connect to whatever runs next for each outcome.
          </p>
        </div>
      )}

      {node.kind === 'delay' && (
        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Wait (seconds)</label>
          <input
            type="number"
            min={0}
            value={node.wait_duration_seconds ?? 0}
            onChange={(e) => onChange({ ...node, wait_duration_seconds: parseInt(e.target.value, 10) || 0 })}
            className="w-full px-2 py-1.5 text-xs border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
          />
        </div>
      )}

      {node.kind !== 'trigger' && (
        <button
          onClick={onDelete}
          className="mt-6 flex items-center gap-1.5 text-xs text-red-500 hover:text-red-600"
        >
          <Trash2 className="h-3.5 w-3.5" />
          Delete node
        </button>
      )}
    </div>
  )
}
