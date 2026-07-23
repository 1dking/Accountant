import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { Zap, Play, GitBranch, Clock } from 'lucide-react'
import { actionLabel, triggerLabel, type GraphNode } from './graph'

type FlowNodeType = Node<{ node: GraphNode }, string>
type FlowNode = NodeProps<FlowNodeType>

const baseCard =
  'min-w-[200px] rounded-lg border shadow-sm px-3 py-2.5 text-sm bg-white dark:bg-gray-900'

export function TriggerNode({ data, selected }: FlowNode) {
  const node = data.node
  return (
    <div
      className={`${baseCard} border-amber-300 dark:border-amber-700 ${selected ? 'ring-2 ring-amber-400' : ''}`}
    >
      <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400 font-medium">
        <Zap className="h-4 w-4" />
        Trigger
      </div>
      <p className="mt-1 text-gray-700 dark:text-gray-300 text-xs">
        {node.trigger_type ? triggerLabel(node.trigger_type) : 'Select a trigger…'}
      </p>
      <Handle type="source" position={Position.Bottom} className="!bg-amber-500" />
    </div>
  )
}

export function ActionNode({ data, selected }: FlowNode) {
  const node = data.node
  return (
    <div
      className={`${baseCard} border-blue-300 dark:border-blue-700 ${selected ? 'ring-2 ring-blue-400' : ''}`}
    >
      <Handle type="target" position={Position.Top} className="!bg-blue-500" />
      <div className="flex items-center gap-2 text-blue-700 dark:text-blue-400 font-medium">
        <Play className="h-4 w-4" />
        Action
      </div>
      <p className="mt-1 text-gray-700 dark:text-gray-300 text-xs">
        {node.action_type ? actionLabel(node.action_type) : 'Select an action…'}
      </p>
      <Handle type="source" position={Position.Bottom} className="!bg-blue-500" />
    </div>
  )
}

export function ConditionNode({ data, selected }: FlowNode) {
  const node = data.node
  const condition = node.condition
  return (
    <div
      className={`${baseCard} border-purple-300 dark:border-purple-700 ${selected ? 'ring-2 ring-purple-400' : ''}`}
    >
      <Handle type="target" position={Position.Top} className="!bg-purple-500" />
      <div className="flex items-center gap-2 text-purple-700 dark:text-purple-400 font-medium">
        <GitBranch className="h-4 w-4" />
        Condition
      </div>
      <p className="mt-1 text-gray-700 dark:text-gray-300 text-xs">
        {condition?.field ? `${condition.field} ${condition.operator} ${condition.value ?? ''}` : 'Configure condition…'}
      </p>
      <div className="flex justify-between mt-2 text-[10px] font-medium">
        <span className="text-red-500">false</span>
        <span className="text-green-600">true</span>
      </div>
      <Handle
        id="false"
        type="source"
        position={Position.Bottom}
        style={{ left: '25%' }}
        className="!bg-red-500"
      />
      <Handle
        id="true"
        type="source"
        position={Position.Bottom}
        style={{ left: '75%' }}
        className="!bg-green-500"
      />
    </div>
  )
}

export function DelayNode({ data, selected }: FlowNode) {
  const node = data.node
  const seconds = node.wait_duration_seconds ?? 0
  return (
    <div
      className={`${baseCard} border-gray-300 dark:border-gray-700 ${selected ? 'ring-2 ring-gray-400' : ''}`}
    >
      <Handle type="target" position={Position.Top} className="!bg-gray-500" />
      <div className="flex items-center gap-2 text-gray-700 dark:text-gray-300 font-medium">
        <Clock className="h-4 w-4" />
        Delay
      </div>
      <p className="mt-1 text-gray-700 dark:text-gray-300 text-xs">
        Wait {formatDuration(seconds)}
      </p>
      <Handle type="source" position={Position.Bottom} className="!bg-gray-500" />
    </div>
  )
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`
  return `${Math.round(seconds / 86400)}d`
}
