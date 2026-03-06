import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Zap,
  Plus,
  Trash2,
  Pencil,
  ChevronDown,
  ChevronRight,
  ArrowUp,
  ArrowDown,
  Copy,
  Power,
  PowerOff,
  Clock,
  AlertCircle,
  CheckCircle2,
  Loader2,
  X,
} from 'lucide-react'
import {
  listWorkflows,
  createWorkflow,
  getWorkflow,
  updateWorkflow,
  deleteWorkflow,
  toggleWorkflow,
  getTemplates,
  getExecutions,
  type WorkflowCreateData,
  type WorkflowUpdateData,
} from '@/api/workflows'
import type {
  WorkflowListItem,
  Workflow,
  WorkflowTemplate,
  WorkflowExecution,
} from '@/types/models'

const TRIGGER_TYPES = [
  { value: 'contact_created', label: 'Contact Created' },
  { value: 'contact_updated', label: 'Contact Updated' },
  { value: 'contact_tagged', label: 'Contact Tagged' },
  { value: 'invoice_sent', label: 'Invoice Sent' },
  { value: 'invoice_paid', label: 'Invoice Paid' },
  { value: 'invoice_overdue', label: 'Invoice Overdue' },
  { value: 'form_submitted', label: 'Form Submitted' },
  { value: 'proposal_signed', label: 'Proposal Signed' },
  { value: 'manual', label: 'Manual Trigger' },
  { value: 'schedule', label: 'Scheduled' },
]

const ACTION_TYPES = [
  { value: 'send_email', label: 'Send Email' },
  { value: 'send_sms', label: 'Send SMS' },
  { value: 'create_task', label: 'Create Task' },
  { value: 'update_contact', label: 'Update Contact' },
  { value: 'add_tag', label: 'Add Tag' },
  { value: 'remove_tag', label: 'Remove Tag' },
  { value: 'create_invoice', label: 'Create Invoice' },
  { value: 'webhook', label: 'Webhook' },
  { value: 'wait', label: 'Wait / Delay' },
  { value: 'condition', label: 'Condition Check' },
]

interface StepDraft {
  step_order: number
  action_type: string
  action_config_json: string
  condition_json: string
  wait_duration_seconds: number
}

function emptyStep(order: number): StepDraft {
  return {
    step_order: order,
    action_type: 'send_email',
    action_config_json: '{}',
    condition_json: '',
    wait_duration_seconds: 0,
  }
}

function triggerLabel(value: string) {
  return TRIGGER_TYPES.find((t) => t.value === value)?.label ?? value
}

function statusIcon(status: string) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="h-4 w-4 text-green-500" />
    case 'running':
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
    case 'failed':
      return <AlertCircle className="h-4 w-4 text-red-500" />
    default:
      return <Clock className="h-4 w-4 text-gray-400" />
  }
}

export default function WorkflowsPage() {
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [showTemplates, setShowTemplates] = useState(false)

  // Form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [triggerType, setTriggerType] = useState('contact_created')
  const [triggerConfigJson, setTriggerConfigJson] = useState('{}')
  const [steps, setSteps] = useState<StepDraft[]>([emptyStep(1)])

  // Queries
  const { data: workflowsData, isLoading } = useQuery({
    queryKey: ['workflows'],
    queryFn: () => listWorkflows(),
  })
  const workflows: WorkflowListItem[] = workflowsData?.data ?? []

  const { data: templatesData } = useQuery({
    queryKey: ['workflow-templates'],
    queryFn: () => getTemplates(),
    enabled: dialogOpen,
  })
  const templates: WorkflowTemplate[] = templatesData?.data ?? []

  const { data: executionsData } = useQuery({
    queryKey: ['workflow-executions', expandedId],
    queryFn: () => getExecutions(expandedId!),
    enabled: !!expandedId,
  })
  const executions: WorkflowExecution[] = executionsData?.data ?? []

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: WorkflowCreateData) => createWorkflow(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      toast.success('Workflow created')
      closeDialog()
    },
    onError: (err: any) => toast.error(err.message || 'Failed to create workflow'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: WorkflowUpdateData }) =>
      updateWorkflow(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      toast.success('Workflow updated')
      closeDialog()
    },
    onError: (err: any) => toast.error(err.message || 'Failed to update workflow'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteWorkflow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      toast.success('Workflow deleted')
    },
    onError: (err: any) => toast.error(err.message || 'Failed to delete workflow'),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      toggleWorkflow(id, isActive),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
    },
    onError: (err: any) => toast.error(err.message || 'Failed to toggle workflow'),
  })

  function closeDialog() {
    setDialogOpen(false)
    setEditingId(null)
    setName('')
    setDescription('')
    setTriggerType('contact_created')
    setTriggerConfigJson('{}')
    setSteps([emptyStep(1)])
    setShowTemplates(false)
  }

  async function openEdit(id: string) {
    try {
      const res = await getWorkflow(id)
      const wf: Workflow = res.data
      setEditingId(id)
      setName(wf.name)
      setDescription(wf.description ?? '')
      setTriggerType(wf.trigger_type)
      setTriggerConfigJson(wf.trigger_config_json ?? '{}')
      if (wf.steps && wf.steps.length > 0) {
        setSteps(
          wf.steps.map((s) => ({
            step_order: s.step_order,
            action_type: s.action_type,
            action_config_json: s.action_config_json ?? '{}',
            condition_json: s.condition_json ?? '',
            wait_duration_seconds: s.wait_duration_seconds ?? 0,
          }))
        )
      } else {
        setSteps([emptyStep(1)])
      }
      setDialogOpen(true)
    } catch {
      toast.error('Failed to load workflow')
    }
  }

  function applyTemplate(tpl: WorkflowTemplate) {
    setName(tpl.name)
    setDescription(tpl.description)
    setTriggerType(tpl.trigger_type)
    setTriggerConfigJson(tpl.trigger_config_json)
    setSteps(
      tpl.steps.map((s, i) => ({
        step_order: s.step_order ?? i + 1,
        action_type: s.action_type,
        action_config_json: s.action_config_json ?? '{}',
        condition_json: s.condition_json ?? '',
        wait_duration_seconds: s.wait_duration_seconds ?? 0,
      }))
    )
    setShowTemplates(false)
    toast.success(`Template "${tpl.name}" applied`)
  }

  function addStep() {
    setSteps((prev) => [...prev, emptyStep(prev.length + 1)])
  }

  function removeStep(idx: number) {
    setSteps((prev) => {
      const next = prev.filter((_, i) => i !== idx)
      return next.map((s, i) => ({ ...s, step_order: i + 1 }))
    })
  }

  function moveStep(idx: number, dir: 'up' | 'down') {
    setSteps((prev) => {
      const arr = [...prev]
      const targetIdx = dir === 'up' ? idx - 1 : idx + 1
      if (targetIdx < 0 || targetIdx >= arr.length) return prev
      ;[arr[idx], arr[targetIdx]] = [arr[targetIdx], arr[idx]]
      return arr.map((s, i) => ({ ...s, step_order: i + 1 }))
    })
  }

  function updateStep(idx: number, updates: Partial<StepDraft>) {
    setSteps((prev) => prev.map((s, i) => (i === idx ? { ...s, ...updates } : s)))
  }

  function handleSave() {
    if (!name.trim()) {
      toast.error('Name is required')
      return
    }
    const payload = {
      name: name.trim(),
      description: description.trim() || undefined,
      trigger_type: triggerType,
      trigger_config_json: triggerConfigJson || undefined,
      steps: steps.map((s) => ({
        step_order: s.step_order,
        action_type: s.action_type,
        action_config_json: s.action_config_json || undefined,
        condition_json: s.condition_json || undefined,
        wait_duration_seconds: s.wait_duration_seconds || undefined,
      })),
    }
    if (editingId) {
      updateMutation.mutate({ id: editingId, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  function handleDelete(id: string) {
    if (confirm('Delete this workflow? This cannot be undone.')) {
      deleteMutation.mutate(id)
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Zap className="h-6 w-6 text-amber-500" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Workflows</h1>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Workflow
        </button>
      </div>

      {/* Workflows list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-gray-400">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : workflows.length === 0 ? (
        <div className="text-center py-20 text-gray-400 dark:text-gray-500">
          <Zap className="h-12 w-12 mx-auto mb-3 opacity-50" />
          <p className="text-lg font-medium">No workflows yet</p>
          <p className="text-sm mt-1">Create your first automation workflow to get started.</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400 w-8" />
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Name
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Trigger
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Active
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Runs
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Last Run
                </th>
                <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {workflows.map((wf) => {
                const isExpanded = expandedId === wf.id
                return (
                  <WorkflowRow
                    key={wf.id}
                    wf={wf}
                    isExpanded={isExpanded}
                    executions={isExpanded ? executions : []}
                    onToggleExpand={() =>
                      setExpandedId(isExpanded ? null : wf.id)
                    }
                    onToggleActive={() =>
                      toggleMutation.mutate({ id: wf.id, isActive: !wf.is_active })
                    }
                    onEdit={() => openEdit(wf.id)}
                    onDelete={() => handleDelete(wf.id)}
                  />
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Dialog */}
      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-10 bg-black/40">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-2xl max-h-[85vh] overflow-y-auto">
            {/* Dialog Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {editingId ? 'Edit Workflow' : 'New Workflow'}
              </h2>
              <button
                onClick={closeDialog}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="px-6 py-4 space-y-5">
              {/* Templates */}
              {!editingId && templates.length > 0 && (
                <div>
                  <button
                    onClick={() => setShowTemplates(!showTemplates)}
                    className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    <Copy className="h-4 w-4" />
                    {showTemplates ? 'Hide templates' : 'Start from a template'}
                  </button>
                  {showTemplates && (
                    <div className="mt-2 grid gap-2">
                      {templates.map((tpl, idx) => (
                        <button
                          key={idx}
                          onClick={() => applyTemplate(tpl)}
                          className="text-left p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                        >
                          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                            {tpl.name}
                          </p>
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                            {tpl.description}
                          </p>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Welcome New Clients"
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Optional description..."
                  rows={2}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100 resize-none"
                />
              </div>

              {/* Trigger type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Trigger Type
                </label>
                <select
                  value={triggerType}
                  onChange={(e) => setTriggerType(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                >
                  {TRIGGER_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Trigger config */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Trigger Config (JSON)
                </label>
                <textarea
                  value={triggerConfigJson}
                  onChange={(e) => setTriggerConfigJson(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 text-sm font-mono border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100 resize-none"
                />
              </div>

              {/* Steps */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Steps
                  </label>
                  <button
                    onClick={addStep}
                    className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    <Plus className="h-3 w-3" />
                    Add Step
                  </button>
                </div>
                <div className="space-y-3">
                  {steps.map((step, idx) => (
                    <div
                      key={idx}
                      className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 bg-gray-50 dark:bg-gray-800/50"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                          Step {step.step_order}
                        </span>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => moveStep(idx, 'up')}
                            disabled={idx === 0}
                            className="p-1 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-30"
                          >
                            <ArrowUp className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => moveStep(idx, 'down')}
                            disabled={idx === steps.length - 1}
                            className="p-1 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-30"
                          >
                            <ArrowDown className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => removeStep(idx)}
                            disabled={steps.length <= 1}
                            className="p-1 rounded text-gray-400 hover:text-red-500 disabled:opacity-30"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-3 mb-2">
                        <div>
                          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">
                            Action Type
                          </label>
                          <select
                            value={step.action_type}
                            onChange={(e) =>
                              updateStep(idx, { action_type: e.target.value })
                            }
                            className="w-full px-2 py-1.5 text-xs border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                          >
                            {ACTION_TYPES.map((a) => (
                              <option key={a.value} value={a.value}>
                                {a.label}
                              </option>
                            ))}
                          </select>
                        </div>
                        {step.action_type === 'wait' && (
                          <div>
                            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">
                              Wait (seconds)
                            </label>
                            <input
                              type="number"
                              value={step.wait_duration_seconds}
                              onChange={(e) =>
                                updateStep(idx, {
                                  wait_duration_seconds: parseInt(e.target.value) || 0,
                                })
                              }
                              className="w-full px-2 py-1.5 text-xs border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                            />
                          </div>
                        )}
                      </div>

                      <div>
                        <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">
                          Action Config (JSON)
                        </label>
                        <textarea
                          value={step.action_config_json}
                          onChange={(e) =>
                            updateStep(idx, { action_config_json: e.target.value })
                          }
                          rows={2}
                          className="w-full px-2 py-1.5 text-xs font-mono border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100 resize-none"
                        />
                      </div>

                      {step.action_type === 'condition' && (
                        <div className="mt-2">
                          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">
                            Condition (JSON)
                          </label>
                          <textarea
                            value={step.condition_json}
                            onChange={(e) =>
                              updateStep(idx, { condition_json: e.target.value })
                            }
                            rows={2}
                            className="w-full px-2 py-1.5 text-xs font-mono border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100 resize-none"
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Dialog Footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 dark:border-gray-700">
              <button
                onClick={closeDialog}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {isSaving && <Loader2 className="h-4 w-4 animate-spin" />}
                {editingId ? 'Save Changes' : 'Create Workflow'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

interface WorkflowRowProps {
  wf: WorkflowListItem
  isExpanded: boolean
  executions: WorkflowExecution[]
  onToggleExpand: () => void
  onToggleActive: () => void
  onEdit: () => void
  onDelete: () => void
}

function WorkflowRow({
  wf,
  isExpanded,
  executions,
  onToggleExpand,
  onToggleActive,
  onEdit,
  onDelete,
}: WorkflowRowProps) {
  return (
    <>
      <tr className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50/50 dark:hover:bg-gray-800/30">
        <td className="px-4 py-3">
          <button onClick={onToggleExpand} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
        </td>
        <td className="px-4 py-3">
          <button
            onClick={onToggleExpand}
            className="text-sm font-medium text-gray-900 dark:text-gray-100 hover:text-blue-600 dark:hover:text-blue-400"
          >
            {wf.name}
          </button>
        </td>
        <td className="px-4 py-3">
          <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300">
            {triggerLabel(wf.trigger_type)}
          </span>
        </td>
        <td className="px-4 py-3 text-center">
          <button
            onClick={onToggleActive}
            className={`inline-flex items-center gap-1 text-xs font-medium ${
              wf.is_active
                ? 'text-green-600 dark:text-green-400'
                : 'text-gray-400 dark:text-gray-500'
            }`}
          >
            {wf.is_active ? (
              <>
                <Power className="h-3.5 w-3.5" /> On
              </>
            ) : (
              <>
                <PowerOff className="h-3.5 w-3.5" /> Off
              </>
            )}
          </button>
        </td>
        <td className="px-4 py-3 text-center text-sm text-gray-600 dark:text-gray-400">
          {wf.execution_count}
        </td>
        <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
          {wf.last_run_at
            ? new Date(wf.last_run_at).toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })
            : '--'}
        </td>
        <td className="px-4 py-3 text-right">
          <div className="flex items-center justify-end gap-1">
            <button
              onClick={onEdit}
              className="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20"
              title="Edit"
            >
              <Pencil className="h-4 w-4" />
            </button>
            <button
              onClick={onDelete}
              className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
              title="Delete"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </td>
      </tr>

      {/* Executions */}
      {isExpanded && (
        <tr>
          <td colSpan={7} className="px-4 py-3 bg-gray-50 dark:bg-gray-800/30">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
              Execution Log
            </p>
            {executions.length === 0 ? (
              <p className="text-xs text-gray-400 dark:text-gray-500">
                No executions recorded yet.
              </p>
            ) : (
              <div className="space-y-1.5">
                {executions.map((ex) => (
                  <div
                    key={ex.id}
                    className="flex items-center gap-3 text-xs p-2 rounded-md bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-700"
                  >
                    {statusIcon(ex.status)}
                    <span className="text-gray-700 dark:text-gray-300 capitalize">
                      {ex.status}
                    </span>
                    <span className="text-gray-400 dark:text-gray-500">
                      {new Date(ex.started_at).toLocaleString()}
                    </span>
                    {ex.completed_at && (
                      <span className="text-gray-400 dark:text-gray-500">
                        Duration:{' '}
                        {Math.round(
                          (new Date(ex.completed_at).getTime() -
                            new Date(ex.started_at).getTime()) /
                            1000
                        )}
                        s
                      </span>
                    )}
                    {ex.error_message && (
                      <span className="text-red-500 truncate max-w-xs" title={ex.error_message}>
                        {ex.error_message}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}
