import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Phone,
  PhoneCall,
  PhoneIncoming,
  PhoneOutgoing,
  Voicemail,
  Zap,
  CircleAlert,
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
  Search,
  ShoppingCart,
  UserCog,
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
  searchAvailableNumbers,
  purchaseNumber,
  assignPhoneNumber,
  syncWebhooks,
  type AvailableNumber,
  type CallLogFilters,
  type SmsFilters,
} from '@/api/communication'
import { listUsers } from '@/api/auth'
import type {
  TwilioPhoneNumber,
  CallLogEntry,
  SmsMessageEntry,
  ChatSession,
  ChatMessage,
  User as AppUser,
} from '@/types/models'
import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'

type TabKey = 'phone-numbers' | 'calls' | 'sms' | 'chat'

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'phone-numbers', label: i18n.t('ui:CommunicationPage.phoneNumbers'), icon: <Hash className="h-4 w-4" /> },
  { key: 'calls', label: i18n.t('ui:CommunicationPage.callLog'), icon: <PhoneCall className="h-4 w-4" /> },
  { key: 'sms', label: 'SMS', icon: <MessageSquare className="h-4 w-4" /> },
  { key: 'chat', label: i18n.t('ui:CommunicationPage.liveChat'), icon: <MessageCircle className="h-4 w-4" /> },
]

export default function CommunicationPage() {
  const { t } = useTranslation('ui')
  const [activeTab, setActiveTab] = useState<TabKey>('phone-numbers')

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Phone className="h-6 w-6 text-blue-500" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
         {t('ui:CommunicationPage.communication')}
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
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)
  const [newNumber, setNewNumber] = useState('')
  const [newFriendlyName, setNewFriendlyName] = useState('')

  // Buy a Number modal state
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchCountry, setSearchCountry] = useState('US')
  const [searchAreaCode, setSearchAreaCode] = useState('')
  const [searchContains, setSearchContains] = useState('')
  const [searchResults, setSearchResults] = useState<AvailableNumber[]>([])

  // Assign-to-User modal state
  // assignTarget non-null = modal open; assignUserId '' = "Unassigned" (sent as null to API)
  const [assignTarget, setAssignTarget] = useState<TwilioPhoneNumber | null>(null)
  const [assignUserId, setAssignUserId] = useState<string>('')

  const { data, isLoading } = useQuery({
    queryKey: ['phone-numbers'],
    queryFn: () => listPhoneNumbers(),
  })
  const numbers: TwilioPhoneNumber[] = data?.data ?? []

  // User lookup for assigned-user-name resolution
  const { data: usersData } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers(),
  })
  const usersById = new Map<string, AppUser>(
    (usersData?.data ?? []).map((u: AppUser) => [u.id, u])
  )
  function resolveAssignedName(uid: string | undefined): string {
    if (!uid) return ''
    const u = usersById.get(uid)
    return u?.full_name ?? `${uid.slice(0, 8)}...`
  }

  const addMutation = useMutation({
    mutationFn: () =>
      addPhoneNumber({
        phone_number: newNumber.trim(),
        friendly_name: newFriendlyName.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phone-numbers'] })
      toast.success(t('ui:CommunicationPage.phoneNumberAdded'))
      setAddOpen(false)
      setNewNumber('')
      setNewFriendlyName('')
    },
    onError: (err: any) => toast.error(err.message || 'Failed to add number'),
  })

  const searchMutation = useMutation({
    mutationFn: () =>
      searchAvailableNumbers({
        country: searchCountry || 'US',
        area_code: searchAreaCode.trim() || undefined,
        contains: searchContains.trim() || undefined,
        sms_enabled: true,
      }),
    onSuccess: (resp) => setSearchResults(resp.data ?? []),
    onError: (err: any) => toast.error(err.message || 'Search failed'),
  })

  const purchaseMutation = useMutation({
    mutationFn: (phone: string) => purchaseNumber(phone),
    onSuccess: (resp: any) => {
      queryClient.invalidateQueries({ queryKey: ['phone-numbers'] })
      const wh = resp?.data?.webhooks_configured_at
      const err = resp?.data?.webhook_config_error
      if (wh) {
        toast.success(t('ui:CommunicationPage.numberPurchasedAndWebhooksConfigured'))
      } else if (err) {
        toast.success(
          t('ui:CommunicationPage.numberPurchasedWebhookConfigFailed', { err }),
        )
      } else {
        toast.success(t('ui:CommunicationPage.numberPurchased'))
      }
      setSearchOpen(false)
      setSearchResults([])
      setSearchAreaCode('')
      setSearchContains('')
    },
    onError: (err: any) => toast.error(err.message || 'Purchase failed'),
  })

  const syncMutation = useMutation({
    mutationFn: (phoneId: string) => syncWebhooks(phoneId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phone-numbers'] })
      toast.success(t('ui:CommunicationPage.webhooksSynced'))
    },
    onError: (err: any) =>
      toast.error(err.message || 'Webhook sync failed'),
  })

  const assignMutation = useMutation({
    mutationFn: ({ phoneId, userId }: { phoneId: string; userId: string | null }) =>
      assignPhoneNumber(phoneId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phone-numbers'] })
      queryClient.invalidateQueries({ queryKey: ['my-number'] })
      toast.success(t('ui:CommunicationPage.assignmentUpdated'))
      setAssignTarget(null)
      setAssignUserId('')
    },
    onError: (err: any) => toast.error(err.message || 'Assignment failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deletePhoneNumber(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phone-numbers'] })
      toast.success(t('ui:CommunicationPage.phoneNumberRemoved'))
    },
    onError: (err: any) => toast.error(err.message || 'Failed to delete'),
  })

  function handleDelete(id: string) {
    if (confirm(t('ui:CommunicationPage.removeThisPhoneNumber'))) {
      deleteMutation.mutate(id)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">
         {t('ui:CommunicationPage.manageTwilioPhoneNumbersAnd')}
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            <ShoppingCart className="h-4 w-4" />
           {t('ui:CommunicationPage.buyANumber')}
          </button>
          <button
            onClick={() => setAddOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
           {t('ui:CommunicationPage.addManually')}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : numbers.length === 0 ? (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500">
          <Phone className="h-10 w-10 mx-auto mb-2 opacity-50" />
          <p className="text-sm">{t('ui:CommunicationPage.noPhoneNumbersConfigured')}</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                 {t('ui:CommunicationPage.number')}
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                 {t('ui:CommunicationPage.friendlyName')}
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                 {t('ui:CommunicationPage.assignedUser')}
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                 {t('ui:CommunicationPage.webhooks')}
                </th>
                <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                 {t('ui:CommunicationPage.actions')}
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
                        {resolveAssignedName(num.assigned_user_id)}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">{t('ui:CommunicationPage.unassigned')}</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {num.webhooks_configured_at ? (
                      <span
                        className="inline-flex items-center gap-1 text-xs text-green-700 dark:text-green-400"
                        title={t('ui:CommunicationPage.configuredV0', { v0: new Date(num.webhooks_configured_at).toLocaleString() })}
                      >
                        <Zap className="h-3 w-3" />
                       {t('ui:CommunicationPage.configured')}
                      </span>
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
                          <CircleAlert className="h-3 w-3" />
                         {t('ui:CommunicationPage.notConfigured')}
                        </span>
                        <button
                          onClick={() => syncMutation.mutate(num.id)}
                          disabled={
                            syncMutation.isPending && syncMutation.variables === num.id
                          }
                          className="px-2 py-0.5 text-xs font-medium text-blue-600 hover:text-blue-700 border border-blue-200 dark:border-blue-800 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded disabled:opacity-50"
                          title={t('ui:CommunicationPage.pushPlatformWebhookUrlsTo')}
                        >
                          {syncMutation.isPending && syncMutation.variables === num.id
                            ? t('ui:CommunicationPage.syncing')
                            : t('ui:CommunicationPage.syncWebhooks')}
                        </button>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex items-center gap-1">
                      <button
                        onClick={() => {
                          setAssignTarget(num)
                          setAssignUserId(num.assigned_user_id ?? '')
                        }}
                        className="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20"
                        title={t('ui:CommunicationPage.assign')}
                      >
                        <UserCog className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(num.id)}
                        className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
                        title={t('ui:CommunicationPage.remove')}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
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
               {t('ui:CommunicationPage.addPhoneNumber')}
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
                 {t('ui:CommunicationPage.phoneNumber')}
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
                 {t('ui:CommunicationPage.friendlyNameOptional')}
                </label>
                <input
                  type="text"
                  value={newFriendlyName}
                  onChange={(e) => setNewFriendlyName(e.target.value)}
                  placeholder={t('ui:CommunicationPage.eGMainOffice')}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 dark:border-gray-700">
              <button
                onClick={() => setAddOpen(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
               {t('ui:CommunicationPage.cancel')}
              </button>
              <button
                onClick={() => addMutation.mutate()}
                disabled={!newNumber.trim() || addMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {addMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
               {t('ui:CommunicationPage.addNumber')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Buy a Number Dialog */}
      {searchOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-2xl flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
               {t('ui:CommunicationPage.buyAPhoneNumber')}
              </h2>
              <button
                onClick={() => setSearchOpen(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="px-6 py-4 space-y-4 border-b border-gray-100 dark:border-gray-700">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                   {t('ui:CommunicationPage.country')}
                  </label>
                  <select
                    value={searchCountry}
                    onChange={(e) => setSearchCountry(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                  >
                    <option value="US">US</option>
                    <option value="CA">CA</option>
                    <option value="GB">GB</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                   {t('ui:CommunicationPage.areaCode')}
                  </label>
                  <input
                    type="text"
                    value={searchAreaCode}
                    onChange={(e) => setSearchAreaCode(e.target.value)}
                    placeholder="e.g. 415"
                    className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                   {t('ui:CommunicationPage.contains')}
                  </label>
                  <input
                    type="text"
                    value={searchContains}
                    onChange={(e) => setSearchContains(e.target.value)}
                    placeholder={t('ui:CommunicationPage.eGCat')}
                    className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                  />
                </div>
              </div>
              <button
                onClick={() => searchMutation.mutate()}
                disabled={searchMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {searchMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Search className="h-4 w-4" />
                )}
               {t('ui:CommunicationPage.search')}
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-4">
              {searchResults.length === 0 && !searchMutation.isPending && (
                <div className="text-center text-sm text-gray-400 py-8">
                 {t('ui:CommunicationPage.enterSearchCriteriaAboveAnd')}
                </div>
              )}
              {searchResults.length > 0 && (
                <div className="space-y-2">
                  {searchResults.map((r) => (
                    <div
                      key={r.phone_number}
                      className="flex items-center justify-between p-3 border border-gray-100 dark:border-gray-700 rounded-lg"
                    >
                      <div>
                        <div className="font-mono text-sm text-gray-900 dark:text-gray-100">
                          {r.phone_number}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {r.locality || '—'}
                          {r.region ? `, ${r.region}` : ''}
                        </div>
                        <div className="flex gap-1 mt-1">
                          {r.capabilities.sms && (
                            <span className="text-[10px] uppercase px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded">
                              SMS
                            </span>
                          )}
                          {r.capabilities.voice && (
                            <span className="text-[10px] uppercase px-1.5 py-0.5 bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 rounded">
                             {t('ui:CommunicationPage.voice')}
                            </span>
                          )}
                          {r.capabilities.mms && (
                            <span className="text-[10px] uppercase px-1.5 py-0.5 bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 rounded">
                              MMS
                            </span>
                          )}
                        </div>
                      </div>
                      <button
                        onClick={() => purchaseMutation.mutate(r.phone_number)}
                        disabled={purchaseMutation.isPending}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 disabled:opacity-50"
                      >
                        {purchaseMutation.isPending &&
                          purchaseMutation.variables === r.phone_number && (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          )}
                       {t('ui:CommunicationPage.buy')}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end px-6 py-4 border-t border-gray-100 dark:border-gray-700">
              <button
                onClick={() => setSearchOpen(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
               {t('ui:CommunicationPage.close')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Assign Modal */}
      {assignTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-md flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
               {t('ui:CommunicationPage.assignPhoneNumber')}
              </h2>
              <button
                onClick={() => {
                  setAssignTarget(null)
                  setAssignUserId('')
                }}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="px-6 py-4 space-y-4">
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">{t('ui:CommunicationPage.phoneNumber')}</div>
                <div className="font-mono text-sm text-gray-900 dark:text-gray-100">
                  {assignTarget.phone_number}
                  {assignTarget.friendly_name && (
                    <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                      ({assignTarget.friendly_name})
                    </span>
                  )}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                 {t('ui:CommunicationPage.assignTo')}
                </label>
                <select
                  value={assignUserId}
                  onChange={(e) => setAssignUserId(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                >
                  <option value="">{t('ui:CommunicationPage.unassigned')}</option>
                  {(usersData?.data ?? []).map((u: AppUser) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name} ({u.email})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 dark:border-gray-700">
              <button
                onClick={() => {
                  setAssignTarget(null)
                  setAssignUserId('')
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
               {t('ui:CommunicationPage.cancel')}
              </button>
              <button
                onClick={() =>
                  assignMutation.mutate({
                    phoneId: assignTarget!.id,
                    userId: assignUserId || null,
                  })
                }
                disabled={assignMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {assignMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
               {t('ui:CommunicationPage.save')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ===================== Call Log Tab ===================== */

function VoicemailTranscript({
  status,
  transcript,
}: {
  status?: 'pending' | 'completed' | 'failed' | null
  transcript?: string | null
}) {
  const { t } = useTranslation('ui')
  const [isExpanded, setIsExpanded] = useState(false)
  if (status === 'pending') {
    return (
      <span className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400 italic">
        <Loader2 className="h-3 w-3 animate-spin" />
       {t('ui:CommunicationPage.transcribing')}
      </span>
    )
  }
  if (status === 'failed') {
    return <span className="text-xs text-gray-400 italic">{t('ui:CommunicationPage.transcriptUnavailable')}</span>
  }
  if (status === 'completed' && transcript) {
    return (
      <button
        type="button"
        onClick={() => setIsExpanded((v) => !v)}
        className="text-left text-xs text-gray-600 dark:text-gray-400 italic hover:text-gray-900 dark:hover:text-gray-100 cursor-pointer max-w-xs"
        title={isExpanded ? t('ui:CommunicationPage.clickToCollapse') : t('ui:CommunicationPage.clickToExpand')}
      >
        <span className={isExpanded ? '' : 'line-clamp-2'}>"{transcript}"</span>
      </button>
    )
  }
  return null
}

function CallLogTab() {
  const { t } = useTranslation('ui')
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
      toast.success(t('ui:CommunicationPage.callLogged'))
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
              { value: '', label: t('ui:CommunicationPage.all') },
              { value: 'inbound', label: t('ui:CommunicationPage.inbound') },
              { value: 'outbound', label: t('ui:CommunicationPage.outbound') },
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
         {t('ui:CommunicationPage.logCall')}
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : calls.length === 0 ? (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500">
          <PhoneCall className="h-10 w-10 mx-auto mb-2 opacity-50" />
          <p className="text-sm">{t('ui:CommunicationPage.noCallsRecorded')}</p>
        </div>
      ) : (
        <>
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400 w-10">
                   {t('ui:CommunicationPage.dir')}
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                   {t('ui:CommunicationPage.from')}
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                   {t('ui:CommunicationPage.to')}
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                   {t('ui:CommunicationPage.duration')}
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                   {t('ui:CommunicationPage.status')}
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                   {t('ui:CommunicationPage.recording')}
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                   {t('ui:CommunicationPage.outcome')}
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                   {t('ui:CommunicationPage.date')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {calls.map((call) => {
                  const token = localStorage.getItem('access_token')
                  return (
                  <tr
                    key={call.id}
                    className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50/50 dark:hover:bg-gray-800/30"
                  >
                    <td className="px-4 py-3">
                      {call.kind === 'voicemail' ? (
                        <Voicemail className="h-4 w-4 text-purple-500" />
                      ) : call.direction === 'inbound' ? (
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
                    <td className="px-4 py-3">
                      {call.recording_url ? (
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-2">
                            <audio
                              controls
                              controlsList="nodownload"
                              preload="metadata"
                              className="h-8"
                              style={{ maxWidth: '200px' }}
                            >
                              <source
                                src={`/api/communication/calls/${call.id}/recording?token=${encodeURIComponent(token ?? '')}`}
                                type="audio/mpeg"
                              />
                            </audio>
                            {call.recording_duration_seconds != null && (
                              <span className="text-xs text-gray-500 dark:text-gray-400">
                                {formatDuration(call.recording_duration_seconds)}
                              </span>
                            )}
                          </div>
                          {call.kind === 'voicemail' && (
                            <VoicemailTranscript
                              status={call.voicemail_transcript_status}
                              transcript={call.voicemail_transcript}
                            />
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
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
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {meta && meta.total_pages > 1 && (
            <div className="flex items-center justify-between mt-4 text-sm">
              <span className="text-gray-500 dark:text-gray-400">
               {t('ui:CommunicationPage.page')} {meta.page} of {meta.total_pages} ({meta.total_count} {t('ui:CommunicationPage.total')}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) - 1 }))}
                  disabled={meta.page <= 1}
                  className="px-3 py-1 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50"
                >
                 {t('ui:CommunicationPage.previous')}
                </button>
                <button
                  onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))}
                  disabled={meta.page >= meta.total_pages}
                  className="px-3 py-1 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50"
                >
                 {t('ui:CommunicationPage.next')}
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
               {t('ui:CommunicationPage.logACall')}
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
                 {t('ui:CommunicationPage.direction')}
                </label>
                <select
                  value={callDirection}
                  onChange={(e) => setCallDirection(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                >
                  <option value="outbound">{t('ui:CommunicationPage.outbound')}</option>
                  <option value="inbound">{t('ui:CommunicationPage.inbound')}</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                   {t('ui:CommunicationPage.from')}
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
                   {t('ui:CommunicationPage.to')}
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
                 {t('ui:CommunicationPage.durationSeconds')}
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
                 {t('ui:CommunicationPage.outcome')}
                </label>
                <select
                  value={callOutcome}
                  onChange={(e) => setCallOutcome(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                >
                  <option value="">{t('ui:CommunicationPage.select')}</option>
                  <option value="connected">{t('ui:CommunicationPage.connected')}</option>
                  <option value="voicemail">{t('ui:CommunicationPage.voicemail')}</option>
                  <option value="no_answer">{t('ui:CommunicationPage.noAnswer')}</option>
                  <option value="busy">{t('ui:CommunicationPage.busy')}</option>
                  <option value="wrong_number">{t('ui:CommunicationPage.wrongNumber')}</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                 {t('ui:CommunicationPage.notes')}
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
               {t('ui:CommunicationPage.cancel')}
              </button>
              <button
                onClick={() => logMutation.mutate()}
                disabled={!callFrom.trim() || !callTo.trim() || logMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {logMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
               {t('ui:CommunicationPage.saveCall')}
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
  const { t } = useTranslation('ui')
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
      toast.success(t('ui:CommunicationPage.smsSent'))
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
         {t('ui:CommunicationPage.smsMessagesSentAndReceived')}
        </p>
        <button
          onClick={() => setComposeOpen(true)}
          className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Send className="h-4 w-4" />
         {t('ui:CommunicationPage.compose')}
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : messages.length === 0 ? (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500">
          <MessageSquare className="h-10 w-10 mx-auto mb-2 opacity-50" />
          <p className="text-sm">{t('ui:CommunicationPage.noSmsMessages')}</p>
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
                    {msg.direction === 'outbound' ? t('ui:CommunicationPage.sent') : t('ui:CommunicationPage.received')}{' '}
                    {msg.direction === 'outbound' ? t('ui:CommunicationPage.toToNumber', { to_number: msg.to_number }) : t('ui:CommunicationPage.fromFromNumber', { from_number: msg.from_number })}
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
               {t('ui:CommunicationPage.page')} {meta.page} of {meta.total_pages}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) - 1 }))}
                  disabled={(filters.page ?? 1) <= 1}
                  className="px-3 py-1 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50"
                >
                 {t('ui:CommunicationPage.previous')}
                </button>
                <button
                  onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))}
                  disabled={(filters.page ?? 1) >= (meta?.total_pages ?? 1)}
                  className="px-3 py-1 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50"
                >
                 {t('ui:CommunicationPage.next')}
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
               {t('ui:CommunicationPage.sendSms')}
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
                 {t('ui:CommunicationPage.to')}
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
                 {t('ui:CommunicationPage.message')}
                </label>
                <textarea
                  value={smsBody}
                  onChange={(e) => setSmsBody(e.target.value)}
                  rows={4}
                  placeholder={t('ui:CommunicationPage.typeYourMessage')}
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
               {t('ui:CommunicationPage.cancel')}
              </button>
              <button
                onClick={() => sendMutation.mutate()}
                disabled={!smsTo.trim() || !smsBody.trim() || sendMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {sendMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                <Send className="h-4 w-4" />
               {t('ui:CommunicationPage.send')}
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
  const { t } = useTranslation('ui')
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
      toast.success(t('ui:CommunicationPage.chatSessionClosed'))
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
              { value: '', label: t('ui:CommunicationPage.all') },
              { value: 'open', label: t('ui:CommunicationPage.open') },
              { value: 'closed', label: t('ui:CommunicationPage.closed') },
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
              <p className="text-xs">{t('ui:CommunicationPage.noChatSessions')}</p>
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
                    {session.visitor_name || session.visitor_email || t('ui:CommunicationPage.anonymous')}
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
                  {session.visitor_email || t('ui:CommunicationPage.noEmail')}
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
                  {selectedSession?.visitor_name || t('ui:CommunicationPage.anonymous')}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {selectedSession?.visitor_email || t('ui:CommunicationPage.noEmail')}
                </p>
              </div>
              {selectedSession?.status === 'open' && (
                <button
                  onClick={() => closeMutation.mutate(selectedSessionId)}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
                >
                  <XCircle className="h-3.5 w-3.5" />
                 {t('ui:CommunicationPage.closeSession')}
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
                    placeholder={t('ui:CommunicationPage.typeAMessage')}
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
              <p className="text-sm">{t('ui:CommunicationPage.selectAChatSessionTo')}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
