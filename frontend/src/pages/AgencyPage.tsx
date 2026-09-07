import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Plus, Building2, Loader2, X, Check, Lock, Unlock, ChevronDown, ChevronRight, UserPlus, Users } from 'lucide-react'
import {
  listTemplates, listSubAccounts, createSubAccount, setSubAccountFeature, unlockBooks, lockBooks, listMembers, inviteMember,
  type SubAccount, type SubAccountCreate, type TemplateInfo, type OnboardingTemplate,
} from '@/api/agency'
import { FEATURE_LABELS } from '@/lib/features'

const FEATURE_GROUPS: Record<string, string[]> = {
  CRM: ['contacts', 'pipeline', 'tasks', 'cards'],
  Sales: ['invoices', 'estimates', 'proposals'],
  Accounting: ['cashbook', 'expenses', 'smart_import', 'email_scanner', 'reports', 'tax', 'recurring'],
  Communication: ['inbox', 'phone', 'sms'],
  Automation: ['workflows', 'forms'],
  Content: ['pages', 'docs', 'sheets', 'slides'],
  Storage: ['drive'],
  Meetings: ['calendar', 'meeting_rooms'],
  AI: ['obrain_chat', 'obrain_coach'],
}

export default function AgencyPage() {
  const { t } = useTranslation('agency')
  const [creating, setCreating] = useState(false)
  const { data, isLoading } = useQuery({ queryKey: ['agency-subaccounts'], queryFn: listSubAccounts })
  const rows: SubAccount[] = data?.data ?? []

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <Building2 className="w-6 h-6 text-gray-700 dark:text-gray-300" />
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">{t('title')}</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-2xl">{t('subtitle')}</p>
        </div>
        <button onClick={() => setCreating(true)} className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          <Plus className="w-4 h-4" /> {t('new')}
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : rows.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-gray-200 dark:border-gray-700 rounded-xl">
          <Building2 className="w-10 h-10 mx-auto text-gray-300 dark:text-gray-600" />
          <p className="mt-3 text-gray-600 dark:text-gray-300 font-medium">{t('empty')}</p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-md mx-auto">{t('emptyHint')}</p>
        </div>
      ) : (
        <div className="space-y-2">{rows.map((s) => <SubAccountRow key={s.id} s={s} />)}</div>
      )}

      {creating && <CreateModal onClose={() => setCreating(false)} />}
    </div>
  )
}

function SubAccountRow({ s }: { s: SubAccount }) {
  const { t } = useTranslation('agency')
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [inviting, setInviting] = useState(false)
  const refresh = () => qc.invalidateQueries({ queryKey: ['agency-subaccounts'] })

  const books = useMutation({
    mutationFn: () => (s.books_enabled ? lockBooks(s.id) : unlockBooks(s.id)),
    onSuccess: () => { refresh(); toast.success(s.books_enabled ? t('books.locked') : t('books.unlocked')) },
    onError: (e: any) => toast.error(e?.message || 'Failed'),
  })
  const feature = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) => setSubAccountFeature(s.id, key, enabled),
    onSuccess: () => refresh(),
    onError: (e: any) => toast.error(e?.message || 'Failed'),
  })
  const { data: membersData } = useQuery({ queryKey: ['agency-members', s.id], queryFn: () => listMembers(s.id), enabled: open })
  const members = membersData?.data ?? []
  const tmplLabel: Record<OnboardingTemplate, string> = { marketing_agency: 'Agency client', accounting_practice: 'Accounting client', custom: 'Custom' }

  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3">
        <button onClick={() => setOpen((v) => !v)} className="flex items-center gap-3 flex-1 text-left min-w-0">
          {open ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
          <span className="font-medium text-gray-900 dark:text-gray-100 truncate">{s.name}</span>
          <span className="text-xs text-gray-400 font-mono hidden sm:inline">/{s.slug}</span>
          <span className="text-xs text-gray-500 hidden md:inline">{tmplLabel[s.template]}</span>
          <span className="text-xs text-gray-500 inline-flex items-center gap-1"><Users className="w-3.5 h-3.5" /> {s.member_count}</span>
          <span className={`text-[11px] px-1.5 py-0.5 rounded ${s.books_enabled ? 'bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-300' : 'bg-gray-100 dark:bg-gray-800 text-gray-500'}`}>
            {s.books_enabled ? t('books.on') : t('books.off')}
          </span>
          <span className={`text-[11px] px-1.5 py-0.5 rounded ${s.status === 'active' ? 'bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300' : 'bg-red-50 dark:bg-red-950 text-red-600'}`}>
            {t(`status.${s.status}`)}
          </span>
        </button>
        <button
          onClick={() => { if (confirm(s.books_enabled ? t('books.lockConfirm') : t('books.unlockConfirm'))) books.mutate() }}
          disabled={books.isPending}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border disabled:opacity-50 ${s.books_enabled ? 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800' : 'border-green-200 dark:border-green-900 text-green-700 dark:text-green-300 hover:bg-green-50 dark:hover:bg-green-950'}`}
        >
          {s.books_enabled ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
          {s.books_enabled ? t('books.lock') : t('books.unlock')}
        </button>
      </div>

      {open && (
        <div className="border-t border-gray-100 dark:border-gray-800 px-4 py-4 bg-gray-50/50 dark:bg-gray-900/30 grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3">
            <div className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">{t('features.title')}</div>
            <p className="text-xs text-gray-500 mb-3">{t('features.hint')}</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-3">
              {Object.entries(FEATURE_GROUPS).map(([group, keys]) => (
                <div key={group}>
                  <div className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{group}</div>
                  {keys.map((k) => (
                    <label key={k} className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer py-0.5">
                      <input type="checkbox" className="rounded" checked={s.features[k] !== false}
                        onChange={(e) => feature.mutate({ key: k, enabled: e.target.checked })} />
                      <span className={s.features[k] === false ? 'text-gray-400 line-through' : ''}>{FEATURE_LABELS[k] ?? k}</span>
                    </label>
                  ))}
                </div>
              ))}
            </div>
          </div>
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400">{t('members.title')}</div>
              <button onClick={() => setInviting(true)} className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"><UserPlus className="w-3.5 h-3.5" /> {t('members.invite')}</button>
            </div>
            {members.length === 0 ? (
              <p className="text-xs text-gray-500">{t('members.none')}</p>
            ) : (
              <ul className="divide-y divide-gray-100 dark:divide-gray-800 text-sm">
                {members.map((m) => (
                  <li key={m.id} className="py-1.5 flex items-center justify-between gap-2">
                    <div className="min-w-0"><div className="truncate text-gray-900 dark:text-gray-100">{m.full_name || m.email}</div><div className="text-xs text-gray-500 truncate">{m.email}</div></div>
                    <span className="text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300">{m.role}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
      {inviting && <InviteModal subAccount={s} onClose={() => setInviting(false)} />}
    </div>
  )
}

function CreateModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation('agency')
  const { t: tc } = useTranslation('common')
  const qc = useQueryClient()
  const { data: tData } = useQuery({ queryKey: ['agency-templates'], queryFn: listTemplates })
  const templates: TemplateInfo[] = tData?.data ?? []
  const [form, setForm] = useState<SubAccountCreate>({ name: '', template: 'marketing_agency', client_email: '', client_name: '', notes: '' })

  const create = useMutation({
    mutationFn: () => createSubAccount({ ...form, client_email: form.client_email || null, client_name: form.client_name || null, notes: form.notes || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['agency-subaccounts'] }); toast.success(t('created')); onClose() },
    onError: (e: any) => toast.error(e?.message || t('createFailed')),
  })
  const inp = 'w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500'
  const lab = 'block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1'

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-start justify-center p-4 overflow-y-auto" onClick={onClose}>
      <form onClick={(e) => e.stopPropagation()} onSubmit={(e) => { e.preventDefault(); create.mutate() }}
        className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-xl p-6 space-y-5 my-8">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('new')}</h2>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>
        <div><label className={lab}>{t('fields.name')}</label><input required autoFocus className={inp} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
        <div>
          <label className={lab}>{t('fields.template')}</label>
          <div className="space-y-2">
            {templates.map((tp) => (
              <label key={tp.key} className={`flex items-start gap-3 p-3 border rounded-lg cursor-pointer ${form.template === tp.key ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-950/30' : 'border-gray-200 dark:border-gray-700'}`}>
                <input type="radio" name="template" className="mt-1" checked={form.template === tp.key} onChange={() => setForm({ ...form, template: tp.key })} />
                <div>
                  <div className="text-sm font-medium text-gray-900 dark:text-gray-100">{tp.label}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{tp.description}</div>
                </div>
              </label>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div><label className={lab}>{t('fields.clientEmail')}</label><input type="email" className={inp} value={form.client_email ?? ''} onChange={(e) => setForm({ ...form, client_email: e.target.value })} /></div>
          <div><label className={lab}>{t('fields.clientName')}</label><input className={inp} value={form.client_name ?? ''} onChange={(e) => setForm({ ...form, client_name: e.target.value })} /></div>
        </div>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">{tc('actions.cancel')}</button>
          <button type="submit" disabled={create.isPending || !form.name} className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            <Check className="w-4 h-4" /> {create.isPending ? tc('actions.saving') : tc('actions.create')}
          </button>
        </div>
      </form>
    </div>
  )
}

function InviteModal({ subAccount, onClose }: { subAccount: SubAccount; onClose: () => void }) {
  const { t } = useTranslation('agency')
  const { t: tc } = useTranslation('common')
  const qc = useQueryClient()
  const [form, setForm] = useState({ email: '', full_name: '', role: 'admin', password: '' })
  const invite = useMutation({
    mutationFn: () => inviteMember(subAccount.id, { ...form, password: form.password || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['agency-members', subAccount.id] }); qc.invalidateQueries({ queryKey: ['agency-subaccounts'] }); toast.success(t('members.invited')); onClose() },
    onError: (e: any) => toast.error(e?.message || 'Failed'),
  })
  const inp = 'w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500'
  const lab = 'block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1'
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-start justify-center p-4 overflow-y-auto" onClick={onClose}>
      <form onClick={(e) => e.stopPropagation()} onSubmit={(e) => { e.preventDefault(); invite.mutate() }}
        className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-md p-6 space-y-4 my-8">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('members.invite')} — {subAccount.name}</h2>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>
        <div><label className={lab}>{t('members.email')}</label><input type="email" required className={inp} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
        <div><label className={lab}>{t('members.fullName')}</label><input required className={inp} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={lab}>{t('members.role')}</label>
            <select className={inp} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {['admin', 'manager', 'team_member', 'accountant', 'client', 'viewer'].map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div><label className={lab}>{t('members.password')}</label><input type="text" className={inp} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
        </div>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">{tc('actions.cancel')}</button>
          <button type="submit" disabled={invite.isPending} className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            <UserPlus className="w-4 h-4" /> {invite.isPending ? tc('actions.saving') : t('members.invite')}
          </button>
        </div>
      </form>
    </div>
  )
}
