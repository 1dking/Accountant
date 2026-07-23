import { useCallback, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type Node,
  type Edge,
  type Connection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { ArrowLeft, Loader2, Save, ShieldCheck } from 'lucide-react'
import { getWorkflow, validateWorkflowDefinition, saveWorkflowDefinition } from '@/api/workflows'
import type { Workflow } from '@/types/models'
import { nodeTypes } from '@/components/workflows/canvas/nodeTypes'
import NodePalette, { PALETTE_MIME, type PaletteDragPayload } from '@/components/workflows/canvas/NodePalette'
import NodeConfigDrawer from '@/components/workflows/canvas/NodeConfigDrawer'
import {
  legacyToGraph,
  newNodeId,
  type GraphNode,
  type WorkflowDefinition,
} from '@/components/workflows/canvas/graph'

type FlowNodeType = Node<{ node: GraphNode }, string>

function definitionToFlow(definition: WorkflowDefinition): { nodes: FlowNodeType[]; edges: Edge[] } {
  const nodes: FlowNodeType[] = definition.nodes.map((n) => ({
    id: n.id,
    type: n.kind,
    position: n.position,
    data: { node: n },
  }))
  const edges: Edge[] = definition.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.source_handle ?? undefined,
    animated: e.source_handle === 'true',
    style: e.source_handle === 'false' ? { stroke: '#ef4444' } : e.source_handle === 'true' ? { stroke: '#16a34a' } : undefined,
  }))
  return { nodes, edges }
}

function flowToDefinition(nodes: Node[], edges: Edge[]): WorkflowDefinition {
  const graphNodes: GraphNode[] = nodes.map((n) => {
    const gn = (n.data as { node: GraphNode }).node
    return { ...gn, id: n.id, position: n.position }
  })
  const trigger = graphNodes.find((n) => n.kind === 'trigger')
  return {
    version: 1,
    start_node_id: trigger?.id ?? graphNodes[0]?.id ?? '',
    nodes: graphNodes,
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      source_handle: (e.sourceHandle as 'true' | 'false' | null) ?? null,
    })),
  }
}

function CanvasInner({ workflow }: { workflow: Workflow }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { screenToFlowPosition } = useReactFlow()

  const initialDefinition = useMemo<WorkflowDefinition>(() => {
    if (workflow.definition_json) {
      try {
        return JSON.parse(workflow.definition_json)
      } catch {
        // fall through to legacy conversion
      }
    }
    return legacyToGraph(workflow)
  }, [workflow])

  const initialFlow = useMemo(() => definitionToFlow(initialDefinition), [initialDefinition])
  const [nodes, setNodes, onNodesChange] = useNodesState(initialFlow.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialFlow.edges)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [validating, setValidating] = useState(false)

  const selectedNode = nodes.find((n) => n.id === selectedId)

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            animated: connection.sourceHandle === 'true',
            style:
              connection.sourceHandle === 'false'
                ? { stroke: '#ef4444' }
                : connection.sourceHandle === 'true'
                  ? { stroke: '#16a34a' }
                  : undefined,
          },
          eds
        )
      )
    },
    [setEdges]
  )

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const raw = event.dataTransfer.getData(PALETTE_MIME)
      if (!raw) return
      const payload: PaletteDragPayload = JSON.parse(raw)
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY })
      const id = newNodeId(payload.kind)

      let node: GraphNode
      if (payload.kind === 'action') {
        node = { id, kind: 'action', action_type: payload.action_type, config: {}, position }
      } else if (payload.kind === 'condition') {
        node = { id, kind: 'condition', condition: { field: '', operator: 'eq', value: '' }, position }
      } else {
        node = { id, kind: 'delay', wait_duration_seconds: 3600, position }
      }

      setNodes((nds) => [...nds, { id, type: node.kind, position, data: { node } }])
    },
    [screenToFlowPosition, setNodes]
  )

  function updateSelectedNode(updated: GraphNode) {
    setNodes((nds) =>
      nds.map((n) => (n.id === updated.id ? { ...n, data: { node: updated } } : n))
    )
  }

  function deleteSelectedNode() {
    if (!selectedId) return
    setNodes((nds) => nds.filter((n) => n.id !== selectedId))
    setEdges((eds) => eds.filter((e) => e.source !== selectedId && e.target !== selectedId))
    setSelectedId(null)
  }

  async function handleValidate(): Promise<boolean> {
    setValidating(true)
    try {
      const definition = flowToDefinition(nodes, edges)
      const res = await validateWorkflowDefinition(workflow.id, JSON.stringify(definition))
      const result = res.data
      if (!result.valid) {
        toast.error(result.errors[0] ?? 'Workflow graph is invalid', {
          description: result.errors.slice(1).join('; ') || undefined,
        })
        return false
      }
      toast.success('Workflow graph is valid')
      return true
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Validation failed')
      return false
    } finally {
      setValidating(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      const definition = flowToDefinition(nodes, edges)
      const definitionJson = JSON.stringify(definition)
      const validation = await validateWorkflowDefinition(workflow.id, definitionJson)
      if (!validation.data.valid) {
        toast.error(validation.data.errors[0] ?? 'Workflow graph is invalid')
        return
      }
      await saveWorkflowDefinition(workflow.id, definitionJson, 'canvas')
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      queryClient.invalidateQueries({ queryKey: ['workflow', workflow.id] })
      toast.success('Canvas saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col h-full min-h-[600px]">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => navigate('/workflows')}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <h1 className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
            {workflow.name} <span className="text-gray-400 font-normal">— Canvas</span>
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleValidate}
            disabled={validating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50"
          >
            {validating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />}
            Validate
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            Save
          </button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        <NodePalette />
        <div className="flex-1 min-w-0" onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            onNodeClick={(_, node) => setSelectedId(node.id)}
            onPaneClick={() => setSelectedId(null)}
            fitView
          >
            <Background />
            <Controls />
            <MiniMap pannable zoomable className="!bg-white dark:!bg-gray-900" />
          </ReactFlow>
        </div>
        {selectedNode && (
          <NodeConfigDrawer
            node={(selectedNode.data as { node: GraphNode }).node}
            onChange={updateSelectedNode}
            onDelete={deleteSelectedNode}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>
    </div>
  )
}

export default function WorkflowCanvasPage() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading } = useQuery({
    queryKey: ['workflow', id],
    queryFn: () => getWorkflow(id!),
    enabled: !!id,
  })
  const workflow: Workflow | undefined = data?.data

  if (isLoading || !workflow) {
    return (
      <div className="flex items-center justify-center h-screen text-gray-400">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  return (
    <ReactFlowProvider>
      <CanvasInner workflow={workflow} />
    </ReactFlowProvider>
  )
}
