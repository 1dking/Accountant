import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Phone,
  PhoneCall,
  PhoneIncoming,
  PhoneOutgoing,
  MessageSquare,
  MessageCircle,
  Plus,
  Trash2,
  Send,
  User,
  Loader2,
  X,
  XCircle,
  Hash,
} from 'lucide-react'
import {
  listPhoneNumbers,
  addPhoneNumber,
  deletePhoneNumber,
  logCall,
  listCalls,
  sendSms,
  listSms,
  listChatSessions,
  sendChatMessage,
  getChatMessages,
  closeChatSession,
  type CallLogFilters,
  type SmsFilters,
} from '@/api/communication'
import type {
  TwilioPhoneNumber,
  CallLogEntry,
  SmsMessageEntry,
  ChatSession,
  ChatMessage,
} from '@/types/models'

type TabKey = 'phone-numbers' | 'calls' | 'sms' | 'chat'

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'phone-numbers', label: 'Phone Numbers', icon: <Hash className="h-4 w-4" /> },
  { key: 'calls', label: 'Call Log', icon: <PhoneCall className="h-4 w-4" /> },
  { key: 'sms', label: 'SMS', icon: <MessageSquare className="h-4 w-4" /> },
  { key: 'chat', label: 'Live Chat', icon: <MessageCircle className="h-4 w-4" /> },
]

export default function CommunicationPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('phone-numbers')

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Phone className="h-6 w-6 text-blue-500" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Communication
        </h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1 mb-6 w-fit">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              activeTab === tab.key
                ? 'bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'phone-numbers' && <PhoneNumbersTab />}
      {activeTab === 'calls' && <CallLogTab />}
      {activeTab === 'sms' && <SmsTab />}
      {activeTab === 'chat' && <LiveChatTab />}
    </div>
  )
}

/* ===================== Phone Numbers Tab ===================== */

function PhoneNumbersTab() {
  const queryClient = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)
  const [newNumber, setNewNumber] = useState('')
  const [newFriendlyName, setNewFriendlyName] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['phone-numbers'],
    queryFn: () => listPhoneNumbers(),
  })
  const numbers: TwilioPhoneNumber[] = data?.data ?? []

  const addMutation = useMutation({
    mutationFn: () =>
      addPhoneNumber({
        phone_number: newNumber.trim(),
        friendly_name: newFriendlyName.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phone-numbers'] })
      toast.success('Phone number added')
      setAddOpen(false)
      setNewNumber('')
      setNewFriendlyName('')
    },
    onError: (err: any) => toast.error(err.message || 'Failed to add number'),
  })



  const deleteMutation = useMutation({
    mutationFn: (id: string) => deletePhoneNumber(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phone-numbers'] })
      toast.success('Phone number removed')
    },
    onError: (err: any) => toast.error(err.message || 'Failed to delete'),
  })

  function handleDelete(id: string) {
    if (confirm('Remove this phone number?')) {
      deleteMutation.mutate(id)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Manage Twilio phone numbers and user assignments.
        </p>
        <button
          onClick={() => setAddOpen(true)}
          className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add Number
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : numbers.length === 0 ? (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500">
          <Phone className="h-10 w-10 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No phone numbers configured.</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Number
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Friendly Name
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Assigned User
                </th>
                <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {numbers.map((num) => (
                <tr
                  key={num.id}
                  className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50/50 dark:hover:bg-gray-800/30"
                >
                  <td className="px-4 py-3 font-mono text-gray-900 dark:text-gray-100">
                    {num.phone_number}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {num.friendly_name || '--'}
                  </td>
                  <td className="px-4 py-3">
                    {num.assigned_user_id ? (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 dark:text-blue-400">
                        <User className="h-3 w-3" />
                        {num.assigned_user_id.slice(0, 8)}...
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">Unassigned</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleDelete(num.id)}
                      className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
                      title="Remove"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Number Dialog */}
      {addOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Add Phone Number
              </h2>
              <button
                onClick={() => setAddOpen(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Phone Number
                </label>
                <input
                  type="text"
                  value={newNumber}
                  onChange={(e) => setNewNumber(e.target.value)}
                  placeholder="+1234567890"
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Friendly Name (optional)
                </label>
                <input
                  type="text"
                  value={newFriendlyName}
                  onChange={(e) => setNewFriendlyName(e.target.value)}
                  placeholder="e.g. Main Office"
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 dark:border-gray-700">
              <button
                onClick={() => setAddOpen(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => addMutation.mutate()}
                disabled={!newNumber.trim() || addMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {addMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Add Number
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ===================== Call Log Tab ===================== */

function CallLogTab() {
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<CallLogFilters>({ page: 1, page_size: 25 })
  const [directionFilter, setDirectionFilter] = useState('')
  const [logOpen, setLogOpen] = useState(false)

  // Log call form
  const [callDirection, setCallDirection] = useState('outbound')
  const [callFrom, setCallFrom] = useState('')
  const [callTo, setCallTo] = useState('')
  const [callDuration, setCallDuration] = useState(0)
  const [callNotes, setCallNotes] = useState('')
  const [callOutcome, setCallOutcome] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['calls', { ...filters, direction: directionFilter || undefined }],
    queryFn: () => listCalls({ ...filters, direction: directionFilter || undefined }),
  })
  const calls: CallLogEntry[] = data?.data ?? []
  const meta = data?.meta

  const logMutation = useMutation({
    mutationFn: () =>
      logCall({
        direction: callDirection,
        from_number: callFrom,
        to_number: callTo,
        duration_seconds: callDuration,
        notes: callNotes || undefined,
        outcome: callOutcome || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calls'] })
      toast.success('Call logged')
      setLogOpen(false)
      setCallFrom('')
      setCallTo('')
      setCallDuration(0)
      setCallNotes('')
      setCallOutcome('')
    },
    onError: (err: any) => toast.error(err.message || 'Failed to log call'),
  })

  function formatDuration(seconds: number) {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${String(s).padStart(2, '0')}`
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
            {[
              { value: '', label: 'All' },
              { value: 'inbound', label: 'Inbound' },
              { value: 'outbound', label: 'Outbound' },
            ].map((opt) => (
              <button
                key={opt.value}
                onClick={() => {
                  setDirectionFilter(opt.value)
                  setFilters((f) => ({ ...f, page: 1 }))
                }}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  directionFilter === opt.value
                    ? 'bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 shadow-sm'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={() => setLogOpen(true)}
          className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Log Call
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : calls.length === 0 ? (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500">
          <PhoneCall className="h-10 w-10 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No calls recorded.</p>
        </div>
      ) : (
        <>
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400 w-10">
                    Dir
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    From
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    To
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Duration
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Status
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Outcome
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody>
                {calls.map((call) => (
                  <tr
                    key={call.id}
                    className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50/50 dark:hover:bg-gray-800/30"
                  >
                    <td className="px-4 py-3">
                      {call.direction === 'inbound' ? (
                        <PhoneIncoming className="h-4 w-4 text-green-500" />
                      ) : (
                        <PhoneOutgoing className="h-4 w-4 text-blue-500" />
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono text-gray-900 dark:text-gray-100 text-xs">
                      {call.from_number}
                    </td>
                    <td className="px-4 py-3 font-mono text-gray-900 dark:text-gray-100 text-xs">
                      {call.to_number}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                      {formatDuration(call.duration_seconds)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${
                          call.status === 'completed'
                            ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                            : call.status === 'failed'
                              ? 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                              : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                        }`}
                      >
                        {call.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs">
                      {call.outcome || '--'}
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs">
                      {new Date(call.created_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {meta && meta.total_pages > 1 && (
            <div className="flex items-center justify-between mt-4 text-sm">
              <span className="text-gray-500 dark:text-gray-400">
                Page {meta.page} of {meta.total_pages} ({meta.total_count} total)
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) - 1 }))}
                  disabled={meta.page <= 1}
                  className="px-3 py-1 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))}
                  disabled={meta.page >= meta.total_pages}
                  className="px-3 py-1 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Log Call Dialog */}
      {logOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Log a Call
              </h2>
              <button
                onClick={() => setLogOpen(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Direction
                </label>
                <select
                  value={callDirection}
                  onChange={(e) => setCallDirection(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                >
                  <option value="outbound">Outbound</option>
                  <option value="inbound">Inbound</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    From
                  </label>
                  <input
                    type="text"
                    value={callFrom}
                    onChange={(e) => setCallFrom(e.target.value)}
                    placeholder="+1..."
                    className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    To
                  </label>
                  <input
                    type="text"
                    value={callTo}
                    onChange={(e) => setCallTo(e.target.value)}
                    placeholder="+1..."
                    className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Duration (seconds)
                </label>
                <input
                  type="number"
                  value={callDuration}
                  onChange={(e) => setCallDuration(parseInt(e.target.value) || 0)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Outcome
                </label>
                <select
                  value={callOutcome}
                  onChange={(e) => setCallOutcome(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                >
                  <option value="">Select...</option>
                  <option value="connected">Connected</option>
                  <option value="voicemail">Voicemail</option>
                  <option value="no_answer">No Answer</option>
                  <option value="busy">Busy</option>
                  <option value="wrong_number">Wrong Number</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Notes
                </label>
                <textarea
                  value={callNotes}
                  onChange={(e) => setCallNotes(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100 resize-none"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 dark:border-gray-700">
              <button
                onClick={() => setLogOpen(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => logMutation.mutate()}
                disabled={!callFrom.trim() || !callTo.trim() || logMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {logMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Save Call
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ===================== SMS Tab ===================== */

function SmsTab() {
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<SmsFilters>({ page: 1, page_size: 25 })
  const [composeOpen, setComposeOpen] = useState(false)
  const [smsTo, setSmsTo] = useState('')
  const [smsBody, setSmsBody] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['sms', filters],
    queryFn: () => listSms(filters),
  })
  const messages: SmsMessageEntry[] = data?.data ?? []
  const meta = data?.meta

  const sendMutation = useMutation({
    mutationFn: () => sendSms({ to_number: smsTo.trim(), body: smsBody.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sms'] })
      toast.success('SMS sent')
      setComposeOpen(false)
      setSmsTo('')
      setSmsBody('')
    },
    onError: (err: any) => toast.error(err.message || 'Failed to send SMS'),
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          SMS messages sent and received.
        </p>
        <button
          onClick={() => setComposeOpen(true)}
          className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Send className="h-4 w-4" />
          Compose
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : messages.length === 0 ? (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500">
          <MessageSquare className="h-10 w-10 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No SMS messages.</p>
        </div>
      ) : (
        <>
          <div className="space-y-2">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`p-3 rounded-lg border ${
                  msg.direction === 'outbound'
                    ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-100 dark:border-blue-800 ml-8'
                    : 'bg-white dark:bg-gray-900 border-gray-100 dark:border-gray-700 mr-8'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                    {msg.direction === 'outbound' ? 'Sent' : 'Received'}{' '}
                    {msg.direction === 'outbound' ? `to ${msg.to_number}` : `from ${msg.from_number}`}
                  </span>
                  <span className="text-xs text-gray-400 dark:text-gray-500">
                    {new Date(msg.created_at).toLocaleString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
                <p className="text-sm text-gray-800 dark:text-gray-200">{msg.body}</p>
                <div className="flex items-center justify-between mt-1.5">
                  <span
                    className={`text-xs ${
                      msg.status === 'delivered'
                        ? 'text-green-500'
                        : msg.status === 'failed'
                          ? 'text-red-500'
                          : 'text-gray-400'
                    }`}
                  >
                    {msg.status}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {meta && meta.total_pages > 1 && (
            <div className="flex items-center justify-between mt-4 text-sm">
              <span className="text-gray-500 dark:text-gray-400">
                Page {meta.page} of {meta.total_pages}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) - 1 }))}
                  disabled={(filters.page ?? 1) <= 1}
                  className="px-3 py-1 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))}
                  disabled={(filters.page ?? 1) >= (meta?.total_pages ?? 1)}
                  className="px-3 py-1 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Compose SMS Dialog */}
      {composeOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Send SMS
              </h2>
              <button
                onClick={() => setComposeOpen(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  To
                </label>
                <input
                  type="text"
                  value={smsTo}
                  onChange={(e) => setSmsTo(e.target.value)}
                  placeholder="+1234567890"
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Message
                </label>
                <textarea
                  value={smsBody}
                  onChange={(e) => setSmsBody(e.target.value)}
                  rows={4}
                  placeholder="Type your message..."
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100 resize-none"
                />
                <p className="text-xs text-gray-400 mt-1">
                  {smsBody.length} / 160 characters
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 dark:border-gray-700">
              <button
                onClick={() => setComposeOpen(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => sendMutation.mutate()}
                disabled={!smsTo.trim() || !smsBody.trim() || sendMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {sendMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                <Send className="h-4 w-4" />
                Send
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ===================== Live Chat Tab ===================== */

function LiveChatTab() {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [newMessage, setNewMessage] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { data: sessionsData, isLoading: sessionsLoading } = useQuery({
    queryKey: ['chat-sessions', statusFilter],
    queryFn: () => listChatSessions(statusFilter || undefined),
  })
  const sessions: ChatSession[] = sessionsData?.data ?? []

  const { data: messagesData } = useQuery({
    queryKey: ['chat-messages', selectedSessionId],
    queryFn: () => getChatMessages(selectedSessionId!),
    enabled: !!selectedSessionId,
    refetchInterval: selectedSessionId ? 5000 : false,
  })
  const chatMessages: ChatMessage[] = messagesData?.data ?? []

  const sendMessageMutation = useMutation({
    mutationFn: () => sendChatMessage(selectedSessionId!, newMessage.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['chat-messages', selectedSessionId],
      })
      setNewMessage('')
    },
    onError: (err: any) => toast.error(err.message || 'Failed to send'),
  })

  const closeMutation = useMutation({
    mutationFn: (id: string) => closeChatSession(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      toast.success('Chat session closed')
      setSelectedSessionId(null)
    },
    onError: (err: any) => toast.error(err.message || 'Failed to close session'),
  })

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  const selectedSession = sessions.find((s) => s.id === selectedSessionId)

  return (
    <div className="flex gap-4" style={{ height: 'calc(100vh - 260px)' }}>
      {/* Sessions list */}
      <div className="w-80 flex-shrink-0 flex flex-col bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
          <div className="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5">
            {[
              { value: '', label: 'All' },
              { value: 'open', label: 'Open' },
              { value: 'closed', label: 'Closed' },
            ].map((opt) => (
              <button
                key={opt.value}
                onClick={() => setStatusFilter(opt.value)}
                className={`flex-1 px-2 py-1 text-xs font-medium rounded-md transition-colors ${
                  statusFilter === opt.value
                    ? 'bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 shadow-sm'
                    : 'text-gray-500 dark:text-gray-400'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {sessionsLoading ? (
            <div className="flex items-center justify-center py-10 text-gray-400">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-10 text-gray-400 dark:text-gray-500">
              <MessageCircle className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-xs">No chat sessions.</p>
            </div>
          ) : (
            sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => setSelectedSessionId(session.id)}
                className={`w-full text-left px-4 py-3 border-b border-gray-50 dark:border-gray-800 transition-colors ${
                  selectedSessionId === session.id
                    ? 'bg-blue-50 dark:bg-blue-900/20'
                    : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'
                }`}
              >
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                    {session.visitor_name || session.visitor_email || 'Anonymous'}
                  </span>
                  <span
                    className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                      session.status === 'open'
                        ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
                    }`}
                  >
                    {session.status}
                  </span>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {session.visitor_email || 'No email'}
                </p>
                <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
                  {new Date(session.created_at).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </p>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Chat panel */}
      <div className="flex-1 flex flex-col bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
        {selectedSessionId ? (
          <>
            {/* Chat header */}
            <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {selectedSession?.visitor_name || 'Anonymous'}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {selectedSession?.visitor_email || 'No email'}
                </p>
              </div>
              {selectedSession?.status === 'open' && (
                <button
                  onClick={() => closeMutation.mutate(selectedSessionId)}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
                >
                  <XCircle className="h-3.5 w-3.5" />
                  Close Session
                </button>
              )}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {chatMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${
                    msg.direction === 'outbound' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  <div
                    className={`max-w-[70%] px-3 py-2 rounded-lg text-sm ${
                      msg.direction === 'outbound'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100'
                    }`}
                  >
                    <p>{msg.message}</p>
                    <p
                      className={`text-[10px] mt-1 ${
                        msg.direction === 'outbound'
                          ? 'text-blue-200'
                          : 'text-gray-400 dark:text-gray-500'
                      }`}
                    >
                      {new Date(msg.created_at).toLocaleTimeString(undefined, {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Message input */}
            {selectedSession?.status === 'open' && (
              <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-700">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey && newMessage.trim()) {
                        e.preventDefault()
                        sendMessageMutation.mutate()
                      }
                    }}
                    placeholder="Type a message..."
                    className="flex-1 px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                  />
                  <button
                    onClick={() => {
                      if (newMessage.trim()) sendMessageMutation.mutate()
                    }}
                    disabled={!newMessage.trim() || sendMessageMutation.isPending}
                    className="p-2 rounded-lg text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    {sendMessageMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400 dark:text-gray-500">
            <div className="text-center">
              <MessageCircle className="h-10 w-10 mx-auto mb-2 opacity-50" />
              <p className="text-sm">Select a chat session to view messages.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
