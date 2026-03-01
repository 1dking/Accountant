import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, Bell, X, Check } from 'lucide-react'
import {
  listReminderRules,
  createReminderRule,
  updateReminderRule,
  deleteReminderRule,
} from '@/api/reminders'
import type { ReminderRule, ReminderChannel } from '@/types/models'

interface RuleFormData {
  name: string
  days_offset: number
  channel: ReminderChannel
  email_subject: string
  email_body: string
  sms_body: string
  is_active: boolean
}

const emptyForm: RuleFormData = {
  name: '',
  days_offset: -3,
  channel: 'email',
  email_subject: '',
  email_body: '',
  sms_body: '',
  is_active: true,
}

function formatOffset(days: number): string {
  if (days < 0) return `${Math.abs(days)} day${Math.abs(days) !== 1 ? 's' : ''} before due`
  if (days === 0) return 'On due date'
  return `${days} day${days !== 1 ? 's' : ''} after due`
}

const channelLabels: Record<ReminderChannel, string> = {
  email: 'Email',
  sms: 'SMS',
  both: 'Email + SMS',
}

const channelColors: Record<ReminderChannel, string> = {
  email: 'bg-blue-100 dark:bg-blue-900/50 text-blue-700',
  sms: 'bg-purple-100 text-purple-700',
  both: 'bg-indigo-100 text-indigo-700',
}

export default function ReminderSettings() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<RuleFormData>(emptyForm)
  const [msg, setMsg] = useState('')
  const [msgType, setMsgType] = useState<'success' | 'error'>('success')

  const { data } = useQuery({
    queryKey: ['reminder-rules'],
    queryFn: listReminderRules,
  })

  const rules = data?.data ?? []

  function showMessage(text: string, type: 'success' | 'error' = 'success') {
    setMsg(text)
    setMsgType(type)
    setTimeout(() => setMsg(''), 4000)
  }

  const createMutation = useMutation({
    mutationFn: (formData: RuleFormData) =>
      createReminderRule({
        name: formData.name,
        days_offset: formData.days_offset,
        channel: formData.channel,
        email_subject: formData.email_subject || undefined,
        email_body: formData.email_body || undefined,
        sms_body: formData.sms_body || undefined,
        is_active: formData.is_active,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminder-rules'] })
      setShowForm(false)
      setForm(emptyForm)
      showMessage('Reminder rule created')
    },
    onError: () => showMessage('Failed to create rule', 'error'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, formData }: { id: string; formData: RuleFormData }) =>
      updateReminderRule(id, {
        name: formData.name,
        days_offset: formData.days_offset,
        channel: formData.channel,
        email_subject: formData.email_subject || undefined,
        email_body: formData.email_body || undefined,
        sms_body: formData.sms_body || undefined,
        is_active: formData.is_active,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminder-rules'] })
      setShowForm(false)
      setEditingId(null)
      setForm(emptyForm)
      showMessage('Reminder rule updated')
    },
    onError: () => showMessage('Failed to update rule', 'error'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteReminderRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminder-rules'] })
      showMessage('Reminder rule deleted')
    },
    onError: () => showMessage('Failed to delete rule', 'error'),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      updateReminderRule(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminder-rules'] })
    },
  })

  function startEdit(rule: ReminderRule) {
    setEditingId(rule.id)
    setForm({
      name: rule.name,
      days_offset: rule.days_offset,
      channel: rule.channel,
      email_subject: rule.email_subject || '',
      email_body: rule.email_body || '',
      sms_body: rule.sms_body || '',
      is_active: rule.is_active,
    })
    setShowForm(true)
  }

  function cancelForm() {
    setShowForm(false)
    setEditingId(null)
    setForm(emptyForm)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (editingId) {
      updateMutation.mutate({ id: editingId, formData: form })
    } else {
      createMutation.mutate(form)
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">Payment Reminders</h2>
        {!showForm && (
          <button
            onClick={() => { setForm(emptyForm); setEditingId(null); setShowForm(true) }}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Plus className="w-4 h-4" />
            Add Rule
          </button>
        )}
      </div>

      {msg && (
        <div
          className={`border rounded-lg p-3 text-sm ${
            msgType === 'success'
              ? 'bg-green-50 dark:bg-green-900/30 border-green-200 text-green-700'
              : 'bg-red-50 dark:bg-red-900/30 border-red-200 text-red-700'
          }`}
        >
          {msg}
        </div>
      )}

      {/* Rule Form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {editingId ? 'Edit Reminder Rule' : 'New Reminder Rule'}
            </h3>
            <button type="button" onClick={cancelForm} className="text-gray-400 dark:text-gray-500 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Rule Name</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. 3 Days Before Due"
                required
                className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Days Offset</label>
              <input
                type="number"
                value={form.days_offset}
                onChange={(e) => setForm({ ...form, days_offset: parseInt(e.target.value) || 0 })}
                className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{formatOffset(form.days_offset)}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Channel</label>
              <select
                value={form.channel}
                onChange={(e) => setForm({ ...form, channel: e.target.value as ReminderChannel })}
                className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="email">Email</option>
                <option value="sms">SMS</option>
                <option value="both">Email + SMS</option>
              </select>
            </div>
          </div>

          {/* Email fields */}
          {(form.channel === 'email' || form.channel === 'both') && (
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-gray-600 dark:text-gray-400">Email Template (optional - defaults will be used if empty)</h4>
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Subject</label>
                <input
                  type="text"
                  value={form.email_subject}
                  onChange={(e) => setForm({ ...form, email_subject: e.target.value })}
                  placeholder="Payment Reminder: Invoice {{invoice_number}}"
                  className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Body (HTML)</label>
                <textarea
                  value={form.email_body}
                  onChange={(e) => setForm({ ...form, email_body: e.target.value })}
                  placeholder="Dear {{contact_name}}, this is a reminder for invoice {{invoice_number}}..."
                  rows={3}
                  className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          )}

          {/* SMS fields */}
          {(form.channel === 'sms' || form.channel === 'both') && (
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-gray-600 dark:text-gray-400">SMS Template (optional - defaults will be used if empty)</h4>
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">SMS Body</label>
                <textarea
                  value={form.sms_body}
                  onChange={(e) => setForm({ ...form, sms_body: e.target.value })}
                  placeholder="Reminder: Invoice {{invoice_number}} for {{total}} is due on {{due_date}}."
                  rows={2}
                  className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          )}

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_active"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              className="rounded border-gray-300 dark:border-gray-600 text-blue-600 dark:text-blue-400 focus:ring-blue-500"
            />
            <label htmlFor="is_active" className="text-sm text-gray-700 dark:text-gray-300">Active</label>
          </div>

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={isPending || !form.name}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <Check className="w-4 h-4" />
              {isPending ? 'Saving...' : editingId ? 'Update Rule' : 'Create Rule'}
            </button>
            <button
              type="button"
              onClick={cancelForm}
              className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Template variables help */}
      <div className="bg-gray-50 dark:bg-gray-950 border rounded-lg p-4 text-sm text-gray-600 dark:text-gray-400">
        <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">Template Variables</h4>
        <p className="text-gray-500 dark:text-gray-400 mb-2">
          Use these placeholders in your email/SMS templates. They will be replaced with actual values when sending.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-1 text-xs font-mono">
          <span>{'{{invoice_number}}'}</span>
          <span>{'{{total}}'}</span>
          <span>{'{{currency}}'}</span>
          <span>{'{{due_date}}'}</span>
          <span>{'{{contact_name}}'}</span>
          <span>{'{{company_name}}'}</span>
        </div>
      </div>

      {/* Rules list */}
      {rules.length > 0 ? (
        <div className="bg-white dark:bg-gray-900 border rounded-lg overflow-hidden">
          <div className="px-5 py-3 border-b">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Configured Rules ({rules.length})
            </h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 dark:bg-gray-950">
                <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Name</th>
                <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Timing</th>
                <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Channel</th>
                <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Status</th>
                <th className="text-right px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id} className="border-b last:border-0">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Bell className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                      <span className="text-gray-900 dark:text-gray-100 font-medium">{rule.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{formatOffset(rule.days_offset)}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${channelColors[rule.channel]}`}
                    >
                      {channelLabels[rule.channel]}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() =>
                        toggleMutation.mutate({ id: rule.id, is_active: !rule.is_active })
                      }
                      className={`text-xs px-2 py-0.5 rounded-full cursor-pointer ${
                        rule.is_active
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 dark:bg-gray-800 text-gray-500'
                      }`}
                    >
                      {rule.is_active ? 'Active' : 'Inactive'}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => startEdit(rule)}
                        className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-blue-600 rounded hover:bg-blue-50"
                        title="Edit"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm('Delete this reminder rule?')) {
                            deleteMutation.mutate(rule.id)
                          }
                        }}
                        disabled={deleteMutation.isPending}
                        className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-red-600 rounded hover:bg-red-50"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-900 border rounded-lg p-8 text-center text-gray-500 dark:text-gray-400">
          <Bell className="w-8 h-8 mx-auto mb-2 text-gray-300" />
          <p className="text-sm">No reminder rules configured yet.</p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Create rules to automatically send payment reminders before or after invoice due dates.
          </p>
        </div>
      )}

      {/* Info section */}
      <div className="bg-gray-50 dark:bg-gray-950 border rounded-lg p-4 text-sm text-gray-600 dark:text-gray-400">
        <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">How Payment Reminders Work</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500 dark:text-gray-400">
          <li>Reminders are checked daily at 8:00 AM and sent automatically</li>
          <li>Set negative days offset to send before the due date (e.g. -3 = 3 days before)</li>
          <li>Set 0 to send on the due date, positive numbers for after due date</li>
          <li>Each reminder is sent only once per invoice per rule (no duplicates)</li>
          <li>Only unpaid invoices (sent, viewed, overdue, partially paid) receive reminders</li>
          <li>You can also manually send reminders from the invoice detail page</li>
        </ul>
      </div>
    </div>
  )
}
