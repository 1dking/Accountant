import type { Workflow } from '@/types/models'

// ---------------------------------------------------------------------------
// The full trigger/action library, mirroring backend/app/workflows/models.py.
// WAIT_DELAY and IF_ELSE_BRANCH aren't in the action palette -- on the canvas
// they're their own node kinds (delay, condition) with dedicated UI instead
// of a generic action_config_json blob.
// ---------------------------------------------------------------------------

export const TRIGGER_LIBRARY: { value: string; label: string }[] = [
  { value: 'contact_created', label: 'Contact Created' },
  { value: 'contact_tag_added', label: 'Contact Tag Added' },
  { value: 'contact_tag_removed', label: 'Contact Tag Removed' },
  { value: 'form_submitted', label: 'Form Submitted' },
  { value: 'appointment_booked', label: 'Appointment Booked' },
  { value: 'appointment_cancelled', label: 'Appointment Cancelled' },
  { value: 'appointment_completed', label: 'Appointment Completed' },
  { value: 'invoice_created', label: 'Invoice Created' },
  { value: 'invoice_sent', label: 'Invoice Sent' },
  { value: 'invoice_paid', label: 'Invoice Paid' },
  { value: 'invoice_overdue', label: 'Invoice Overdue' },
  { value: 'proposal_sent', label: 'Proposal Sent' },
  { value: 'proposal_viewed', label: 'Proposal Viewed' },
  { value: 'proposal_signed', label: 'Proposal Signed' },
  { value: 'proposal_declined', label: 'Proposal Declined' },
  { value: 'payment_received', label: 'Payment Received' },
  { value: 'pipeline_stage_changed', label: 'Pipeline Stage Changed' },
  { value: 'call_completed', label: 'Call Completed' },
  { value: 'sms_received', label: 'SMS Received' },
  { value: 'email_opened', label: 'Email Opened' },
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'webhook_received', label: 'Webhook Received' },
  { value: 'card_viewed', label: 'Business Card Viewed' },
  { value: 'card_contact_saved', label: 'Business Card Contact Saved' },
]

export const ACTION_LIBRARY: { value: string; label: string }[] = [
  { value: 'send_email', label: 'Send Email' },
  { value: 'send_sms', label: 'Send SMS' },
  { value: 'add_tag', label: 'Add Tag' },
  { value: 'remove_tag', label: 'Remove Tag' },
  { value: 'update_contact_field', label: 'Update Contact Field' },
  { value: 'create_contact', label: 'Create Contact' },
  { value: 'move_pipeline_stage', label: 'Move Pipeline Stage' },
  { value: 'create_task', label: 'Create Task' },
  { value: 'create_note', label: 'Create Note' },
  { value: 'create_invoice', label: 'Create Invoice' },
  { value: 'send_proposal', label: 'Send Proposal' },
  { value: 'webhook_outbound', label: 'Outbound Webhook' },
  { value: 'add_to_workflow', label: 'Add to Workflow' },
  { value: 'remove_from_workflow', label: 'Remove from Workflow' },
  { value: 'assign_to_user', label: 'Assign to User' },
  { value: 'send_notification', label: 'Send Notification' },
  { value: 'ask_obrain', label: 'Ask O-Brain' },
  { value: 'log_to_brain', label: 'Log to Brain' },
]

export function triggerLabel(value: string): string {
  return TRIGGER_LIBRARY.find((t) => t.value === value)?.label ?? value
}

export function actionLabel(value: string): string {
  return ACTION_LIBRARY.find((a) => a.value === value)?.label ?? value
}

// ---------------------------------------------------------------------------
// Graph types -- mirrors backend/app/workflows/service.py::validate_definition
// and _execute_graph's expectations for definition_json.
// ---------------------------------------------------------------------------

export type NodeKind = 'trigger' | 'action' | 'condition' | 'delay'

export interface GraphNodeData {
  kind: NodeKind
  label?: string
  // trigger
  trigger_type?: string
  trigger_config?: Record<string, unknown>
  // action
  action_type?: string
  config?: Record<string, unknown>
  // condition
  condition?: { field: string; operator: 'eq' | 'neq' | 'contains' | 'exists'; value?: string }
  // delay
  wait_duration_seconds?: number
}

export interface GraphNode {
  id: string
  kind: NodeKind
  trigger_type?: string
  trigger_config?: Record<string, unknown>
  action_type?: string
  config?: Record<string, unknown>
  condition?: { field: string; operator: string; value?: string }
  wait_duration_seconds?: number
  position: { x: number; y: number }
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  source_handle?: 'true' | 'false' | null
}

export interface WorkflowDefinition {
  version: 1
  start_node_id: string
  nodes: GraphNode[]
  edges: GraphEdge[]
}

let idCounter = 0
export function newNodeId(prefix: string): string {
  idCounter += 1
  return `${prefix}-${Date.now().toString(36)}-${idCounter}`
}

/** Convert a linear workflow (trigger_type + WorkflowStep[]) into a straight-
 * chain graph. IF_ELSE_BRANCH becomes a condition node whose false edge skips
 * the following step (the linear engine's own semantics) -- lossless for the
 * common two-step if/else shape; deeper branches flatten to a chain, matching
 * what the linear engine actually executes. */
export function legacyToGraph(workflow: Workflow): WorkflowDefinition {
  const steps = [...(workflow.steps ?? [])].sort((a, b) => a.step_order - b.step_order)
  const triggerId = newNodeId('trigger')
  const triggerNode: GraphNode = {
    id: triggerId,
    kind: 'trigger',
    trigger_type: workflow.trigger_type,
    trigger_config: safeParse(workflow.trigger_config_json),
    position: { x: 250, y: 0 },
  }

  // Pass 1: one graph node per step, in order, so branch targets can be
  // resolved by array index before any edges are wired.
  const stepNodes: GraphNode[] = steps.map((step, idx) => {
    const id = newNodeId('node')
    const position = { x: 250, y: 140 * (idx + 1) }
    if (step.action_type === 'wait_delay') {
      return { id, kind: 'delay', wait_duration_seconds: step.wait_duration_seconds ?? 0, position }
    }
    if (step.action_type === 'if_else_branch') {
      const condition = safeParse(step.condition_json) as GraphNode['condition'] | undefined
      return { id, kind: 'condition', condition: condition ?? { field: '', operator: 'eq', value: '' }, position }
    }
    return { id, kind: 'action', action_type: step.action_type, config: safeParse(step.action_config_json) ?? {}, position }
  })

  const nodes: GraphNode[] = [triggerNode, ...stepNodes]
  const edges: GraphEdge[] = []
  let prevId = triggerId
  // Nodes already wired in by a condition's true/false handle shouldn't also
  // get a default chain edge from whatever step precedes them positionally.
  const alreadyWired = new Set<string>()

  stepNodes.forEach((node, idx) => {
    if (!alreadyWired.has(node.id)) {
      edges.push({ id: newNodeId('edge'), source: prevId, target: node.id, source_handle: null })
    }

    if (node.kind === 'condition') {
      // True branch: the immediate next step (the linear engine's default
      // continuation). False branch: this canvas's intended semantic --
      // skip the next step -- so false jumps to the step after that.
      const trueTarget = stepNodes[idx + 1]
      const falseTarget = stepNodes[idx + 2]
      if (trueTarget) {
        edges.push({ id: newNodeId('edge'), source: node.id, target: trueTarget.id, source_handle: 'true' })
        alreadyWired.add(trueTarget.id)
      }
      if (falseTarget) {
        edges.push({ id: newNodeId('edge'), source: node.id, target: falseTarget.id, source_handle: 'false' })
        alreadyWired.add(falseTarget.id)
      }
    }

    prevId = node.id
  })

  return { version: 1, start_node_id: triggerId, nodes, edges }
}

function safeParse(json: string | undefined): Record<string, unknown> | undefined {
  if (!json) return undefined
  try {
    return JSON.parse(json)
  } catch {
    return undefined
  }
}

/** A brand-new canvas workflow: just a trigger node, nothing downstream. */
export function emptyGraph(triggerType: string): WorkflowDefinition {
  const triggerId = newNodeId('trigger')
  return {
    version: 1,
    start_node_id: triggerId,
    nodes: [{ id: triggerId, kind: 'trigger', trigger_type: triggerType, position: { x: 250, y: 0 } }],
    edges: [],
  }
}
