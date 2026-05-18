import { useState } from 'react'
import { Navigate } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Bell, Users, X, Check, AlertCircle } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import {
  listAdminTeam,
  getTeamMemberOnboarding,
  overrideTeamMember,
  sendTeamMemberReminder,
  type AdminTeamMember,
} from '@/api/auth'

export default function AdminTeamPage() {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // Permission guard — non-admins redirect home
  if (user && user.role !== 'admin') {
    return <Navigate to="/dashboard" replace />
  }

  const { data, isLoading } = useQuery({
    queryKey: ['admin-team'],
    queryFn: () => listAdminTeam(),
  })

  const remindMut = useMutation({
    mutationFn: (id: string) => sendTeamMemberReminder(id),
    onSuccess: (resp: any) => {
      if (resp?.data?.sent) {
        toast.success('Reminder sent')
      } else {
        toast.message(resp?.data?.reason || 'No reminder needed')
      }
    },
    onError: (e: any) => toast.error(`Failed: ${e.message || ''}`),
  })

  const members: AdminTeamMember[] = (data?.data ?? []) as AdminTeamMember[]
  const selected = selectedId ? members.find((m) => m.id === selectedId) : null

  return (
    <div className="flex flex-1 min-h-0">
      <div className="flex-1 overflow-y-auto p-6">
        <div className="flex items-center gap-3 mb-6">
          <Users className="h-6 w-6 text-gray-600 dark:text-gray-400" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              Team
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              Setup progress across everyone on the platform
            </p>
          </div>
        </div>

        {isLoading ? (
          <div className="text-sm text-gray-500">Loading…</div>
        ) : members.length === 0 ? (
          <div className="text-sm text-gray-500 italic py-8">
            No users yet.
          </div>
        ) : (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 text-left">
                  <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">User</th>
                  <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Role</th>
                  <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Phone</th>
                  <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Fallback</th>
                  <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Setup</th>
                  <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {members.map((m) => {
                  const pct = Math.round((m.onboarding_progress ?? 0) * 100)
                  return (
                    <tr
                      key={m.id}
                      onClick={() => setSelectedId(m.id)}
                      className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50/50 dark:hover:bg-gray-800/30 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div className="font-semibold text-gray-900 dark:text-gray-100">
                          {m.full_name}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {m.email}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-400 capitalize">
                        {m.role || '—'}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-700 dark:text-gray-300">
                        {m.assigned_phone_number || '—'}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-700 dark:text-gray-300">
                        {m.fallback_phone || '—'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-24 h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                            <div
                              className={`h-full transition-all ${
                                pct === 100
                                  ? 'bg-green-500'
                                  : pct >= 50
                                    ? 'bg-blue-500'
                                    : 'bg-amber-500'
                              }`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-600 dark:text-gray-400 w-12">
                            {m.onboarding_done_count}/{m.onboarding_total_count}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            remindMut.mutate(m.id)
                          }}
                          disabled={remindMut.isPending}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded disabled:opacity-50"
                          title="Send setup reminder notification"
                        >
                          <Bell className="h-3 w-3" />
                          Remind
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Side panel — detailed onboarding state */}
      {selectedId && selected && (
        <TeamMemberPanel
          memberId={selectedId}
          onClose={() => setSelectedId(null)}
          onChange={() => {
            queryClient.invalidateQueries({ queryKey: ['admin-team'] })
          }}
        />
      )}
    </div>
  )
}


function TeamMemberPanel({
  memberId,
  onClose,
  onChange,
}: {
  memberId: string
  onClose: () => void
  onChange: () => void
}) {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['admin-team-onboarding', memberId],
    queryFn: () => getTeamMemberOnboarding(memberId),
    enabled: !!memberId,
  })

  const [fallback, setFallback] = useState('')
  const [voicemailMode, setVoicemailMode] = useState('')

  const overrideMut = useMutation({
    mutationFn: (data: { fallback_phone?: string; voicemail_mode?: string }) =>
      overrideTeamMember(memberId, data),
    onSuccess: () => {
      toast.success('Override saved')
      queryClient.invalidateQueries({ queryKey: ['admin-team'] })
      queryClient.invalidateQueries({ queryKey: ['admin-team-onboarding', memberId] })
      onChange()
    },
    onError: (e: any) => toast.error(`Failed: ${e.message || ''}`),
  })

  const payload = data?.data
  if (isLoading || !payload) return null

  return (
    <div className="w-96 shrink-0 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 overflow-y-auto">
      <div className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-100 dark:border-gray-700 px-4 py-3 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-gray-900 dark:text-gray-100">
            {payload.full_name}
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400">{payload.email}</p>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="p-4 space-y-4">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">
            Onboarding ({Math.round((payload.overall_progress ?? 0) * 100)}%)
          </h3>
          <ul className="space-y-1.5">
            {payload.items.map((i: any) => (
              <li key={i.key} className="flex items-start gap-2 text-sm">
                {i.completed ? (
                  <Check className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                ) : i.dismissed_at ? (
                  <X className="h-4 w-4 text-gray-300 mt-0.5 shrink-0" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <div
                    className={
                      i.completed
                        ? 'text-gray-500 dark:text-gray-400'
                        : 'text-gray-900 dark:text-gray-100'
                    }
                  >
                    {i.label}
                  </div>
                  {i.dismissed_at && (
                    <div className="text-[10px] text-gray-400 italic">dismissed</div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="pt-3 border-t border-gray-100 dark:border-gray-700">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">
            Admin override
          </h3>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                Fallback phone
              </label>
              <input
                type="tel"
                placeholder="+1..."
                value={fallback}
                onChange={(e) => setFallback(e.target.value)}
                className="w-full px-2 py-1 text-sm border rounded dark:bg-gray-900 dark:border-gray-700"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                Voicemail mode
              </label>
              <select
                value={voicemailMode}
                onChange={(e) => setVoicemailMode(e.target.value)}
                className="w-full px-2 py-1 text-sm border rounded dark:bg-gray-900 dark:border-gray-700"
              >
                <option value="">— no change —</option>
                <option value="cell_then_voicemail">Cell, then voicemail</option>
                <option value="voicemail_only">Voicemail only</option>
                <option value="cell_only">Cell only</option>
              </select>
            </div>
            <button
              onClick={() => {
                const payload: any = {}
                if (fallback) payload.fallback_phone = fallback
                if (voicemailMode) payload.voicemail_mode = voicemailMode
                if (Object.keys(payload).length === 0) {
                  toast.message('Nothing to save')
                  return
                }
                overrideMut.mutate(payload)
                setFallback('')
                setVoicemailMode('')
              }}
              disabled={overrideMut.isPending}
              className="w-full px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm disabled:opacity-50"
            >
              {overrideMut.isPending ? 'Saving…' : 'Apply override'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
