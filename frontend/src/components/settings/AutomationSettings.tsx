import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Plus, Trash2, Pencil, GripVertical, Zap, Power, Bot } from 'lucide-react'
import {
  listAutomationFlows,
  createAutomationFlow,
  updateAutomationFlow,
  deleteAutomationFlow,
  toggleAutomationFlow,
  type AutomationFlow,
  type AutomationStep,
  type AutomationTriggerType,
  type AutomationFlowInput,
} from '@/api/automation'
import { updateProfile, previewConversationReply } from '@/api/auth'
import { useAuthStore } from '@/stores/authStore'

const TRIGGER_LABELS: Record<AutomationTriggerType, string> = {
  missed_call: 'Missed call (no voicemail)',
  voicemail: 'Voicemail captured',
  inbound_sms_unknown: 'Inbound SMS from unknown',
}

const MAX_STEP_BODY = 320

function emptyFlow(): AutomationFlowInput {
  return {
    name: '',
    trigger_type: 'voicemail',
    is_active: true,
    steps: [
      { step_order: 1, message_body: '', delay_minutes: 0, include_booking_link: false },
    ],
  }
}

function FlowEditor({
  flow,
  onSave,
  onCancel,
  hasBookingLink,
  saving,
}: {
  flow: AutomationFlowInput
  onSave: (input: AutomationFlowInput) => void
  onCancel: () => void
  hasBookingLink: boolean
  saving: boolean
}) {
  const [draft, setDraft] = useState<AutomationFlowInput>(flow)

  const updateStep = (idx: number, patch: Partial<AutomationStep>) => {
    setDraft({
      ...draft,
      steps: draft.steps.map((s, i) => (i === idx ? { ...s, ...patch } : s)),
    })
  }

  const addStep = () => {
    setDraft({
      ...draft,
      steps: [
        ...draft.steps,
        {
          step_order: draft.steps.length + 1,
          message_body: '',
          delay_minutes: 0,
          include_booking_link: false,
        },
      ],
    })
  }

  const removeStep = (idx: number) => {
    const next = draft.steps.filter((_, i) => i !== idx)
    // Renumber
    next.forEach((s, i) => (s.step_order = i + 1))
    setDraft({ ...draft, steps: next })
  }

  const handleSave = () => {
    if (!draft.name.trim()) {
      toast.error('Name is required')
      return
    }
    if (draft.steps.length === 0) {
      toast.error('At least one step required')
      return
    }
    for (const s of draft.steps) {
      if (!s.message_body.trim()) {
        toast.error(`Step ${s.step_order}: message is empty`)
        return
      }
      if (s.message_body.length > MAX_STEP_BODY) {
        toast.error(`Step ${s.step_order}: exceeds ${MAX_STEP_BODY} chars`)
        return
      }
    }
    onSave(draft)
  }

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Flow name</label>
          <input
            type="text"
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value.slice(0, 100) })}
            placeholder="e.g., Missed call follow-up"
            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-900 dark:border-gray-600"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Trigger</label>
          <select
            value={draft.trigger_type}
            onChange={(e) =>
              setDraft({ ...draft, trigger_type: e.target.value as AutomationTriggerType })
            }
            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-900 dark:border-gray-600"
          >
            {Object.entries(TRIGGER_LABELS).map(([val, label]) => (
              <option key={val} value={val}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={!!draft.is_active}
            onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })}
          />
          Active
        </label>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">Steps</h3>
          <button
            type="button"
            onClick={addStep}
            className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
          >
            <Plus className="h-3 w-3" /> Add step
          </button>
        </div>

        {draft.steps.map((step, idx) => (
          <div
            key={idx}
            className="border border-gray-200 dark:border-gray-700 rounded-md p-3 bg-gray-50 dark:bg-gray-800/30"
          >
            <div className="flex items-start gap-2">
              <div className="flex flex-col items-center text-gray-400 mt-1">
                <GripVertical className="h-4 w-4" />
                <span className="text-xs font-mono mt-1">{step.step_order}</span>
              </div>
              <div className="flex-1 space-y-2">
                <textarea
                  value={step.message_body}
                  onChange={(e) =>
                    updateStep(idx, { message_body: e.target.value.slice(0, MAX_STEP_BODY) })
                  }
                  placeholder="The SMS message we'll send for this step…"
                  rows={2}
                  className="w-full px-3 py-2 border rounded-md text-sm resize-none dark:bg-gray-900 dark:border-gray-600"
                />
                <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
                  <label className="flex items-center gap-1">
                    Delay:
                    <input
                      type="number"
                      min={0}
                      max={10080}
                      value={step.delay_minutes}
                      onChange={(e) =>
                        updateStep(idx, {
                          delay_minutes: Math.max(
                            0,
                            Math.min(10080, parseInt(e.target.value || '0', 10)),
                          ),
                        })
                      }
                      className="w-16 px-2 py-1 border rounded dark:bg-gray-900 dark:border-gray-600"
                    />
                    min
                  </label>
                  <label
                    className={`flex items-center gap-1 ${
                      !hasBookingLink ? 'opacity-50 cursor-not-allowed' : ''
                    }`}
                    title={!hasBookingLink ? 'Set a booking link in Profile first' : ''}
                  >
                    <input
                      type="checkbox"
                      disabled={!hasBookingLink}
                      checked={step.include_booking_link}
                      onChange={(e) =>
                        updateStep(idx, { include_booking_link: e.target.checked })
                      }
                    />
                    Append booking link
                  </label>
                  <span className="ml-auto">{step.message_body.length}/{MAX_STEP_BODY}</span>
                  <button
                    type="button"
                    onClick={() => removeStep(idx)}
                    className="text-red-600 hover:text-red-700"
                    disabled={draft.steps.length === 1}
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="flex gap-2 pt-2 border-t border-gray-200 dark:border-gray-700">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save flow'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

export default function AutomationSettings() {
  const { user, fetchMe } = useAuthStore()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<
    { id?: string; input: AutomationFlowInput } | null
  >(null)
  const [bookingLink, setBookingLink] = useState(user?.booking_link || '')

  const { data: flows, isLoading } = useQuery({
    queryKey: ['automation-flows'],
    queryFn: () => listAutomationFlows(),
  })

  const createMut = useMutation({
    mutationFn: createAutomationFlow,
    onSuccess: () => {
      toast.success('Flow created')
      setEditing(null)
      queryClient.invalidateQueries({ queryKey: ['automation-flows'] })
    },
    onError: (e: any) => toast.error(`Create failed: ${e.message}`),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: AutomationFlowInput }) =>
      updateAutomationFlow(id, data),
    onSuccess: () => {
      toast.success('Flow updated')
      setEditing(null)
      queryClient.invalidateQueries({ queryKey: ['automation-flows'] })
    },
    onError: (e: any) => toast.error(`Update failed: ${e.message}`),
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      toggleAutomationFlow(id, isActive),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automation-flows'] })
    },
  })

  const deleteMut = useMutation({
    mutationFn: deleteAutomationFlow,
    onSuccess: () => {
      toast.success('Flow deleted')
      queryClient.invalidateQueries({ queryKey: ['automation-flows'] })
    },
  })

  const bookingMut = useMutation({
    mutationFn: (link: string) =>
      updateProfile({ booking_link: link } as any),
    onSuccess: () => {
      toast.success('Booking link saved')
      fetchMe()
    },
    onError: (e: any) => toast.error(`Save failed: ${e.message}`),
  })

  const handleSave = (input: AutomationFlowInput) => {
    if (editing?.id) {
      updateMut.mutate({ id: editing.id, data: input })
    } else {
      createMut.mutate(input)
    }
  }

  const hasBookingLink = !!(user?.booking_link || bookingLink).trim()

  return (
    <div className="space-y-6">
      <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">
              Booking link
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-md">
              Optional public URL. Steps that opt in will append this to the
              outbound SMS so callers can self-schedule.
            </p>
          </div>
        </div>
        <div className="flex gap-2 max-w-xl">
          <input
            type="url"
            value={bookingLink}
            onChange={(e) => setBookingLink(e.target.value)}
            placeholder="https://cal.com/yourname/30min"
            className="flex-1 px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-900 dark:border-gray-600"
          />
          <button
            type="button"
            onClick={() => bookingMut.mutate(bookingLink)}
            disabled={bookingMut.isPending || bookingLink === (user?.booking_link || '')}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm disabled:opacity-50"
          >
            Save
          </button>
        </div>
      </section>

      <ConversationEnginePanel />

      <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <Zap className="h-5 w-5 text-yellow-500" />
              SMS Automation Flows
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-lg">
              Define multi-step SMS sequences that fire when calls go missed
              or voicemails arrive. Messages are sent verbatim — you control
              every word.
            </p>
          </div>
          {!editing && (
            <button
              type="button"
              onClick={() => setEditing({ input: emptyFlow() })}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm flex items-center gap-1"
            >
              <Plus className="h-4 w-4" /> New flow
            </button>
          )}
        </div>

        {editing && (
          <div className="mb-6">
            <FlowEditor
              flow={editing.input}
              onSave={handleSave}
              onCancel={() => setEditing(null)}
              hasBookingLink={hasBookingLink}
              saving={createMut.isPending || updateMut.isPending}
            />
          </div>
        )}

        {isLoading ? (
          <div className="text-sm text-gray-500">Loading…</div>
        ) : !flows?.data?.length ? (
          <div className="text-sm text-gray-500 italic py-4">
            No flows yet. Click "New flow" to create your first sequence.
          </div>
        ) : (
          <div className="space-y-2">
            {flows.data.map((flow: AutomationFlow) => (
              <div
                key={flow.id}
                className="border border-gray-200 dark:border-gray-700 rounded-md p-3 flex items-center gap-3"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-gray-900 dark:text-gray-100">
                      {flow.name}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      · {TRIGGER_LABELS[flow.trigger_type]} · {flow.steps.length}{' '}
                      step{flow.steps.length === 1 ? '' : 's'}
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    toggleMut.mutate({ id: flow.id, isActive: !flow.is_active })
                  }
                  className={`px-2 py-1 rounded text-xs flex items-center gap-1 ${
                    flow.is_active
                      ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                      : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
                  }`}
                  title={flow.is_active ? 'Click to disable' : 'Click to enable'}
                >
                  <Power className="h-3 w-3" />
                  {flow.is_active ? 'On' : 'Off'}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setEditing({
                      id: flow.id,
                      input: {
                        name: flow.name,
                        trigger_type: flow.trigger_type,
                        is_active: flow.is_active,
                        steps: flow.steps.map((s) => ({
                          step_order: s.step_order,
                          message_body: s.message_body,
                          delay_minutes: s.delay_minutes,
                          include_booking_link: s.include_booking_link,
                        })),
                      },
                    })
                  }
                  className="p-1 text-gray-500 hover:text-gray-900 dark:hover:text-gray-100"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (confirm(`Delete "${flow.name}"?`)) {
                      deleteMut.mutate(flow.id)
                    }
                  }}
                  className="p-1 text-red-600 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}


function ConversationEnginePanel() {
  const { user, fetchMe } = useAuthStore()
  const [enabled, setEnabled] = useState(!!user?.conversation_reply_enabled)
  const [template, setTemplate] = useState(user?.conversation_template ?? '')
  const [instructions, setInstructions] = useState(
    user?.conversation_ai_instructions ?? '',
  )
  const [identityCapture, setIdentityCapture] = useState(
    user?.identity_capture_enabled ?? true,
  )
  const [preview, setPreview] = useState<null | {
    generated_reply: string
    classification: string
    sample_inbound_used: string
  }>(null)
  const previewMut = useMutation({
    mutationFn: () =>
      previewConversationReply({
        template,
        ai_instructions: instructions || undefined,
      }),
    onSuccess: (resp: any) => {
      setPreview(resp?.data ?? null)
    },
    onError: (e: any) => toast.error(`Preview failed: ${e.message || ''}`),
  })

  useEffect(() => {
    setEnabled(!!user?.conversation_reply_enabled)
    setTemplate(user?.conversation_template ?? '')
    setInstructions(user?.conversation_ai_instructions ?? '')
    setIdentityCapture(user?.identity_capture_enabled ?? true)
  }, [user])

  const saveMut = useMutation({
    mutationFn: () =>
      updateProfile({
        conversation_reply_enabled: enabled,
        conversation_template: template,
        conversation_ai_instructions: instructions,
        identity_capture_enabled: identityCapture,
      } as any),
    onSuccess: () => {
      toast.success('Conversation engine settings saved')
      fetchMe()
    },
    onError: (e: any) => toast.error(`Save failed: ${e.message || ''}`),
  })

  const dirty =
    enabled !== !!user?.conversation_reply_enabled ||
    template !== (user?.conversation_template ?? '') ||
    instructions !== (user?.conversation_ai_instructions ?? '') ||
    identityCapture !== (user?.identity_capture_enabled ?? true)

  return (
    <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Bot className="h-5 w-5 text-indigo-500" />
            AI Conversation Engine
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-lg">
            When an inbound SMS arrives from a known contact, AI classifies
            the message and either replies, sends a brief sign-off, or stays
            silent. Capped at 6 auto-replies per conversation. Paused for
            24h on any manual outbound from you.
          </p>
        </div>
      </div>

      <div className="space-y-4">
        <label className="flex items-start gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            className="mt-1"
          />
          <span className="text-sm">
            <span className="font-medium">AI continues SMS conversations on my behalf</span>
            <span className="block text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Requires the template field below. Send any manual SMS yourself
              to pause AI for that contact.
            </span>
          </span>
        </label>

        <div>
          <label className="block text-sm font-medium mb-1">
            How you'd typically respond
          </label>
          <textarea
            value={template}
            onChange={(e) => setTemplate(e.target.value.slice(0, 2000))}
            placeholder="Hey — appreciate the message. I'll get back to you with details shortly."
            rows={3}
            className="w-full px-3 py-2 text-sm border rounded resize-none dark:bg-gray-900 dark:border-gray-600"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            The AI uses this as the voice/cadence to mirror. Be conversational.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">
            Tone & style instructions <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          <textarea
            value={instructions}
            onChange={(e) => setInstructions(e.target.value.slice(0, 2000))}
            placeholder="Keep it friendly and brief. Canadian English. No emojis."
            rows={2}
            className="w-full px-3 py-2 text-sm border rounded resize-none dark:bg-gray-900 dark:border-gray-600"
          />
        </div>

        {enabled && (
          <label className="flex items-start gap-2 cursor-pointer pt-2 border-t border-gray-100 dark:border-gray-800">
            <input
              type="checkbox"
              checked={identityCapture}
              onChange={(e) => setIdentityCapture(e.target.checked)}
              className="mt-1"
            />
            <span className="text-sm">
              <span className="font-medium">
                Ask unknown numbers to identify themselves
              </span>
              <span className="block text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                When an inbound SMS arrives from a phone not in your contacts,
                AI will ask for their name + email and auto-create a contact
                when they respond. Capped at 2 attempts per number per week.
              </span>
            </span>
          </label>
        )}

        <div className="flex items-center gap-3 flex-wrap">
          <button
            type="button"
            onClick={() => saveMut.mutate()}
            disabled={!dirty || saveMut.isPending}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md text-sm disabled:opacity-50"
          >
            {saveMut.isPending ? 'Saving…' : 'Save'}
          </button>
          <button
            type="button"
            onClick={() => previewMut.mutate()}
            disabled={!template.trim() || previewMut.isPending}
            className="px-4 py-2 border border-indigo-300 dark:border-indigo-700 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 rounded-md text-sm disabled:opacity-50"
            title="Generate a sample AI reply using your current template + tone, without saving"
          >
            {previewMut.isPending ? 'Generating…' : 'See sample reply'}
          </button>
          {dirty && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              Unsaved changes
            </span>
          )}
        </div>

        {preview && (
          <div className="mt-2 p-3 bg-indigo-50/60 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800 rounded">
            <div className="text-[11px] uppercase tracking-wide text-indigo-700 dark:text-indigo-300 mb-1">
              Sample reply ({preview.classification})
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mb-1.5 italic">
              They sent: "{preview.sample_inbound_used}"
            </div>
            <div className="text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-900 p-2 rounded border border-gray-200 dark:border-gray-700">
              {preview.generated_reply || (
                <span className="italic text-gray-400">(no reply — would stay silent)</span>
              )}
            </div>
            <button
              type="button"
              onClick={() => previewMut.mutate()}
              disabled={previewMut.isPending}
              className="mt-2 text-xs text-indigo-600 hover:underline disabled:opacity-50"
            >
              Try another
            </button>
          </div>
        )}

        <div className="text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded p-2">
          ⚠ The AI will reply up to 6 times per conversation. Close-out
          detection ends the loop. You can stop a conversation anytime by
          sending a manual reply (24h pause), or disable per-contact from
          their detail page.
        </div>
      </div>
    </section>
  )
}
