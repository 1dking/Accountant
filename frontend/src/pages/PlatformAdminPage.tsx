import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { platformAdminApi } from '@/api/platformAdmin'
import { useAuthStore } from '@/stores/authStore'
import {
  LayoutDashboard,
  Users,
  ToggleLeft,
  DollarSign,
  Key,
  HeartPulse,
  Shield,
  AlertTriangle,
  Search,
  CheckCircle,
  XCircle,
  LogIn,
  RefreshCw,
  Activity,
  Clock,
  FileText,
  Globe,
  Save,
  Building2,
  Plus,
  Trash2,
  ChevronLeft,
  Palette,
  UserPlus,
  UserMinus,
  Edit3,
  Eye,
  EyeOff,
  Zap,
  Loader2,
  Power,
  Copy,
  Mail,
  X,
  Phone,
  Blocks,
} from 'lucide-react'
import BlocksAdminTab from '@/components/pages/BlocksAdminTab'
import { FEATURE_CATEGORIES, ROLE_DEFAULTS, FEATURE_LABELS } from '@/lib/features'
import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'

// ── Tab definitions ──────────────────────────────────────────────────────

const TABS = [
  { key: 'overview', label: i18n.t('ui:PlatformAdminPage.overview'), icon: LayoutDashboard },
  { key: 'organizations', label: i18n.t('ui:PlatformAdminPage.organizations'), icon: Building2 },
  { key: 'users', label: i18n.t('ui:PlatformAdminPage.users'), icon: Users },
  { key: 'features', label: i18n.t('ui:PlatformAdminPage.featureToggles'), icon: ToggleLeft },
  { key: 'pricing', label: i18n.t('ui:PlatformAdminPage.pricingLimits'), icon: DollarSign },
  { key: 'apikeys', label: i18n.t('ui:PlatformAdminPage.apiKeys'), icon: Key },
  { key: 'telephony', label: i18n.t('ui:PlatformAdminPage.telephony'), icon: Phone },
  { key: 'blocks', label: i18n.t('ui:PlatformAdminPage.blocks'), icon: Blocks },
  { key: 'health', label: i18n.t('ui:PlatformAdminPage.health'), icon: HeartPulse },
  { key: 'security', label: i18n.t('ui:PlatformAdminPage.security'), icon: Shield },
  { key: 'errors', label: i18n.t('ui:PlatformAdminPage.errors'), icon: AlertTriangle },
] as const

type TabKey = (typeof TABS)[number]['key']

// ── Main page ────────────────────────────────────────────────────────────

export default function PlatformAdminPage() {
  const { t } = useTranslation('ui')
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const user = useAuthStore((s) => s.user)

  if (user?.role !== 'admin') {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.youDoNotHaveAccess')}</p>
      </div>
    )
  }

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-56 shrink-0 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 overflow-y-auto">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.platformAdmin')}</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{t('ui:PlatformAdminPage.systemManagement')}</p>
        </div>
        <nav className="p-2">
          {TABS.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
                  activeTab === tab.key
                    ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 font-medium'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'organizations' && <OrganizationsTab />}
        {activeTab === 'users' && <UsersTab />}
        {activeTab === 'features' && <FeatureTogglesTab />}
        {activeTab === 'pricing' && <PricingTab />}
        {activeTab === 'apikeys' && <ApiKeysTab />}
        {activeTab === 'telephony' && <TelephonyTab />}
        {activeTab === 'blocks' && <BlocksAdminTab />}
        {activeTab === 'health' && <HealthTab />}
        {activeTab === 'security' && <SecurityTab />}
        {activeTab === 'errors' && <ErrorsTab />}
      </div>
    </div>
  )
}

// ── Telephony tab — least-privilege capability grants ─────────────────────

const TELEPHONY_CAPS = [
  { apiKey: 'number_purchase', field: 'allow_number_purchase', label: i18n.t('ui:PlatformAdminPage.buyNumbers') },
  { apiKey: 'sms', field: 'allow_sms', label: i18n.t('ui:PlatformAdminPage.sendSms') },
  { apiKey: 'mms', field: 'allow_mms', label: i18n.t('ui:PlatformAdminPage.sendMms') },
  { apiKey: 'voice_outbound', field: 'allow_voice_outbound', label: i18n.t('ui:PlatformAdminPage.outboundCalls') },
  { apiKey: 'voice_inbound', field: 'allow_voice_inbound', label: i18n.t('ui:PlatformAdminPage.inboundCalls') },
] as const

function CapToggle({
  on, disabled, onClick,
}: { on: boolean; disabled?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      role="switch"
      aria-checked={on}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:opacity-40 ${
        on ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600'
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
          on ? 'translate-x-4' : 'translate-x-0.5'
        }`}
      />
    </button>
  )
}

function TelephonyTab() {
  const { t } = useTranslation('ui')
  const qc = useQueryClient()
  const [provisionId, setProvisionId] = useState('')
  const [view, setView] = useState<'capabilities' | 'pricing'>('capabilities')

  const { data, isLoading } = useQuery({
    queryKey: ['platform-admin', 'telephony-accounts'],
    queryFn: () => platformAdminApi.listTelephonyAccounts(),
  })
  const accounts = ((data as any)?.data ?? []) as any[]
  const enforcing = Boolean((data as any)?.meta?.enforcing)

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ['platform-admin', 'telephony-accounts'] })

  const setCap = useMutation({
    mutationFn: ({ tenantKey, field, value }: { tenantKey: string; field: string; value: boolean }) =>
      platformAdminApi.setTelephonyCapability(tenantKey, field, value),
    onSuccess: () => { toast.success(t('ui:PlatformAdminPage.capabilityUpdated')); invalidate() },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Failed to update capability'),
  })
  const provision = useMutation({
    mutationFn: (userId: string) => platformAdminApi.provisionTelephony(userId),
    onSuccess: () => { toast.success(t('ui:PlatformAdminPage.subaccountProvisioned')); setProvisionId(''); invalidate() },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Provision failed'),
  })
  const suspend = useMutation({
    mutationFn: (id: string) => platformAdminApi.suspendTelephony(id),
    onSuccess: () => { toast.success(t('ui:PlatformAdminPage.suspended')); invalidate() },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Failed'),
  })
  const reactivate = useMutation({
    mutationFn: (id: string) => platformAdminApi.reactivateTelephony(id),
    onSuccess: () => { toast.success(t('ui:PlatformAdminPage.reactivated')); invalidate() },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Failed'),
  })

  return (
    <div className="space-y-4">
      <div className="flex gap-2 border-b border-gray-200 pb-2 dark:border-gray-700">
        {(['capabilities', 'pricing'] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${
              view === v
                ? 'bg-blue-600 text-white'
                : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
            }`}
          >
            {v === 'capabilities' ? t('ui:PlatformAdminPage.capabilities') : t('ui:PlatformAdminPage.pricingMargin')}
          </button>
        ))}
      </div>

      {view === 'pricing' && <TelephonyPricingPanel />}
      {view === 'capabilities' && (
      <>
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
         {t('ui:PlatformAdminPage.telephonyCapabilities')}
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
         {t('ui:PlatformAdminPage.leastPrivilegeEverySubaccountStarts')}
        </p>
      </div>

      {/* Enforcement banner */}
      <div
        className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${
          enforcing
            ? 'border-green-300 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-900/30 dark:text-green-300'
            : 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-300'
        }`}
      >
        <Shield className="h-4 w-4 shrink-0" />
        {enforcing ? (
          <span><strong>{t('ui:PlatformAdminPage.enforcing')}</strong> {t('ui:PlatformAdminPage.ungrantedActionsAreBlocked403')}</span>
        ) : (
          <span><strong>{t('ui:PlatformAdminPage.stagingNotEnforced')}</strong> {t('ui:PlatformAdminPage.grantsAreRecordedButDo')} <code>telephony_enforce_capabilities</code> {t('ui:PlatformAdminPage.onToEnforce')}</span>
        )}
      </div>

      {/* Provision */}
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('ui:PlatformAdminPage.provisionASubaccount')}</span>
        <input
          value={provisionId}
          onChange={(e) => setProvisionId(e.target.value)}
          placeholder={t('ui:PlatformAdminPage.tenantOwnerUserIdUuid')}
          className="flex-1 min-w-[220px] rounded-md border border-gray-300 px-2 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-900"
        />
        <button
          onClick={() => provisionId && provision.mutate(provisionId)}
          disabled={!provisionId || provision.isPending}
          className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          <Plus className="h-4 w-4" /> {t('ui:PlatformAdminPage.provision')}
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 p-6 text-gray-500"><Loader2 className="h-4 w-4 animate-spin" /> {t('ui:PlatformAdminPage.loading')}</div>
      ) : accounts.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-8 text-center text-sm text-gray-500 dark:border-gray-700">
         {t('ui:PlatformAdminPage.noTelephonySubaccountsYetProvision')}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border border-gray-200 dark:border-gray-700">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800/50">
              <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                <th className="px-3 py-2">{t('ui:PlatformAdminPage.tenant')}</th>
                <th className="px-3 py-2">{t('ui:PlatformAdminPage.status')}</th>
                {TELEPHONY_CAPS.map((c) => (
                  <th key={c.apiKey} className="px-3 py-2 text-center">{c.label}</th>
                ))}
                <th className="px-3 py-2">{t('ui:PlatformAdminPage.numbers')}</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {accounts.map((a) => {
                const suspended = a.status === 'suspended'
                return (
                  <tr key={a.id} className="text-gray-800 dark:text-gray-200">
                    <td className="px-3 py-2">
                      <div className="font-medium">{a.tenant_key}</div>
                      <div className="font-mono text-[11px] text-gray-400">{a.subaccount_sid}</div>
                    </td>
                    <td className="px-3 py-2">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        suspended
                          ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
                          : 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                      }`}>{a.status}</span>
                    </td>
                    {TELEPHONY_CAPS.map((c) => (
                      <td key={c.apiKey} className="px-3 py-2 text-center">
                        <CapToggle
                          on={Boolean(a.capabilities?.[c.apiKey])}
                          disabled={setCap.isPending || suspended}
                          onClick={() => setCap.mutate({
                            tenantKey: a.tenant_key,
                            field: c.field,
                            value: !a.capabilities?.[c.apiKey],
                          })}
                        />
                      </td>
                    ))}
                    <td className="px-3 py-2 tabular-nums">{a.numbers_held}/{a.max_numbers}</td>
                    <td className="px-3 py-2 text-right">
                      {suspended ? (
                        <button onClick={() => reactivate.mutate(a.id)} className="text-xs font-medium text-green-600 hover:underline">{t('ui:PlatformAdminPage.reactivate')}</button>
                      ) : (
                        <button onClick={() => suspend.mutate(a.id)} className="text-xs font-medium text-red-600 hover:underline">{t('ui:PlatformAdminPage.suspend')}</button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      </>
      )}
    </div>
  )
}

// ── Telephony pricing (rate card) — our cost vs your sell price ────────────

const RATE_ORDER = [
  'number_monthly', 'sms_outbound', 'sms_inbound', 'mms_outbound',
  'voice_outbound_min', 'voice_inbound_min', 'a2p_brand', 'a2p_campaign',
  'a2p_campaign_monthly', 'recording_storage_min', 'transcription_min',
]

function TelephonyPricingPanel() {
  const { t } = useTranslation('ui')
  const qc = useQueryClient()
  const [draft, setDraft] = useState<Record<string, string>>({})

  const { data, isLoading } = useQuery({
    queryKey: ['platform-admin', 'telephony-rate-card'],
    queryFn: () => platformAdminApi.getRateCard('global'),
  })
  const payload = (data as any)?.data ?? {}
  const rows = (((payload.units ?? []) as any[]).slice()).sort(
    (a, b) => RATE_ORDER.indexOf(a.unit) - RATE_ORDER.indexOf(b.unit),
  )
  const globalMarkup = payload.global_markup as number | undefined

  const save = useMutation({
    mutationFn: ({ unit, sell }: { unit: string; sell: number }) =>
      platformAdminApi.updateRate({ unit, scope: 'global', sell_price_usd: sell }),
    onSuccess: () => {
      toast.success(t('ui:PlatformAdminPage.sellPriceUpdated'))
      qc.invalidateQueries({ queryKey: ['platform-admin', 'telephony-rate-card'] })
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Failed to update price'),
  })

  const commit = (unit: string) => {
    const raw = draft[unit]
    if (raw === undefined) return
    const val = Number(raw)
    if (Number.isNaN(val) || val < 0) { toast.error(t('ui:PlatformAdminPage.enterAValidPrice')); return }
    save.mutate({ unit, sell: val })
    setDraft((d) => { const n = { ...d }; delete n[unit]; return n })
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('ui:PlatformAdminPage.pricingMargin')}</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          <strong>{t('ui:PlatformAdminPage.ourCost')}</strong> {t('ui:PlatformAdminPage.isWhatTwilioBillsUs')} <strong>{t('ui:PlatformAdminPage.yourSellPrice')}</strong> {t('ui:PlatformAdminPage.isWhatTheTenantPays')}
          {globalMarkup !== undefined && (
            <> {t('ui:PlatformAdminPage.unitsWithoutAPinnedPrice')} <strong>{globalMarkup}×</strong> {t('ui:PlatformAdminPage.markup')}</>
          )}
        </p>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 p-6 text-gray-500"><Loader2 className="h-4 w-4 animate-spin" /> {t('ui:PlatformAdminPage.loading')}</div>
      ) : (
        <div className="overflow-x-auto rounded-md border border-gray-200 dark:border-gray-700">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800/50">
              <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                <th className="px-3 py-2">{t('ui:PlatformAdminPage.unit')}</th>
                <th className="px-3 py-2 text-right">{t('ui:PlatformAdminPage.ourCost')}</th>
                <th className="px-3 py-2 text-right">{t('ui:PlatformAdminPage.yourSellPrice')}</th>
                <th className="px-3 py-2 text-right">{t('ui:PlatformAdminPage.margin')}</th>
                <th className="px-3 py-2 text-right">{t('ui:PlatformAdminPage.margin_2')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {rows.map((r) => {
                const highlight = r.unit === 'number_monthly'
                return (
                  <tr key={r.unit} className={highlight ? 'bg-blue-50/60 dark:bg-blue-900/20' : ''}>
                    <td className="px-3 py-2">
                      <div className="font-medium text-gray-800 dark:text-gray-200">{r.label}</div>
                      <div className="font-mono text-[11px] text-gray-400">{r.unit} {t('ui:PlatformAdminPage.via')} {r.source}</div>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-gray-600 dark:text-gray-400">${r.our_cost_usd.toFixed(4)}</td>
                    <td className="px-3 py-2 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <span className="text-gray-400">$</span>
                        <input
                          value={draft[r.unit] ?? r.sell_price_usd.toFixed(4)}
                          onChange={(e) => setDraft((d) => ({ ...d, [r.unit]: e.target.value }))}
                          onKeyDown={(e) => { if (e.key === 'Enter') commit(r.unit) }}
                          onBlur={() => draft[r.unit] !== undefined && commit(r.unit)}
                          className="w-24 rounded-md border border-gray-300 px-2 py-1 text-right text-sm tabular-nums dark:border-gray-600 dark:bg-gray-900"
                        />
                      </div>
                    </td>
                    <td className={`px-3 py-2 text-right tabular-nums font-medium ${r.margin_usd >= 0 ? 'text-green-600' : 'text-red-600'}`}>${r.margin_usd.toFixed(4)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-gray-600 dark:text-gray-400">{r.margin_pct}%</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-gray-400">
       {t('ui:PlatformAdminPage.globalPricesShownPerPlan')}
      </p>
    </div>
  )
}

// ── Overview tab ─────────────────────────────────────────────────────────

function OverviewTab() {
  const { t } = useTranslation('ui')
  const { data, isLoading } = useQuery({
    queryKey: ['platform-admin', 'dashboard'],
    queryFn: () => platformAdminApi.getDashboard(),
  })

  const metrics = (data as any)?.data
  if (isLoading) return <LoadingSpinner />

  const cards = [
    { label: t('ui:PlatformAdminPage.totalUsers'), value: metrics?.total_users ?? 0, sub: `${metrics?.active_users ?? 0} active`, icon: Users, color: 'blue' },
    { label: t('ui:PlatformAdminPage.pages'), value: metrics?.total_pages ?? 0, sub: `${metrics?.published_pages ?? 0} published`, icon: Globe, color: 'purple' },
    { label: t('ui:PlatformAdminPage.documents'), value: metrics?.total_documents ?? 0, sub: formatBytes(metrics?.storage_used_bytes ?? 0), icon: FileText, color: 'green' },
    { label: t('ui:PlatformAdminPage.invoices'), value: metrics?.total_invoices ?? 0, sub: `$${(metrics?.total_revenue ?? 0).toLocaleString()}`, icon: DollarSign, color: 'amber' },
    { label: t('ui:PlatformAdminPage.contacts'), value: metrics?.total_contacts ?? 0, icon: Users, color: 'cyan' },
    { label: t('ui:PlatformAdminPage.proposals'), value: metrics?.total_proposals ?? 0, icon: FileText, color: 'indigo' },
    { label: t('ui:PlatformAdminPage.expenses'), value: `$${(metrics?.total_expenses ?? 0).toLocaleString()}`, icon: DollarSign, color: 'red' },
    { label: t('ui:PlatformAdminPage.meetings'), value: metrics?.total_meetings ?? 0, icon: Activity, color: 'emerald' },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.dashboardOverview')}</h1>

      {/* Metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {cards.map((c) => {
          const Icon = c.icon
          return (
            <div key={c.label} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{c.label}</span>
                <Icon className="w-4 h-4 text-gray-400" />
              </div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{c.value}</p>
              {c.sub && <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{c.sub}</p>}
            </div>
          )
        })}
      </div>

      {/* Users by role */}
      {metrics?.users_by_role && Object.keys(metrics.users_by_role).length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3">{t('ui:PlatformAdminPage.usersByRole')}</h3>
          <div className="flex gap-4 flex-wrap">
            {Object.entries(metrics.users_by_role).map(([role, count]) => (
              <div key={role} className="flex items-center gap-2">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400 capitalize">
                  {role.replace('_', ' ')}
                </span>
                <span className="text-sm font-medium text-gray-900 dark:text-white">{count as number}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Activity chart (simple bar representation) */}
      {metrics?.activity_by_day?.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3">{t('ui:PlatformAdminPage.activityLast30Days')}</h3>
          <div className="flex items-end gap-1 h-24">
            {(() => {
              const maxCount = Math.max(...metrics.activity_by_day.map((d: any) => d.count), 1)
              return metrics.activity_by_day.map((day: any, i: number) => (
                <div
                  key={i}
                  className="flex-1 bg-blue-500 dark:bg-blue-400 rounded-t opacity-80 hover:opacity-100 transition-opacity"
                  style={{ height: `${Math.max((day.count / maxCount) * 100, 2)}%` }}
                  title={t('ui:PlatformAdminPage.dateCountActions', { date: day.date, count: day.count })}
                />
              ))
            })()}
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-[10px] text-gray-400">{metrics.activity_by_day[0]?.date}</span>
            <span className="text-[10px] text-gray-400">{metrics.activity_by_day[metrics.activity_by_day.length - 1]?.date}</span>
          </div>
        </div>
      )}

      {/* Recent activity */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3">{t('ui:PlatformAdminPage.recentActivity')}</h3>
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {(metrics?.recent_activity ?? []).map((a: any) => (
            <div key={a.id} className="flex items-center gap-3 text-sm py-1.5 border-b border-gray-100 dark:border-gray-700 last:border-0">
              <Activity className="w-3.5 h-3.5 text-gray-400 shrink-0" />
              <span className="font-medium text-gray-700 dark:text-gray-300 truncate">{a.user_name}</span>
              <span className="text-gray-500 dark:text-gray-400">{a.action}</span>
              <span className="text-gray-400 dark:text-gray-500">{a.resource_type}</span>
              <span className="ml-auto text-xs text-gray-400 shrink-0">{timeAgo(a.created_at)}</span>
            </div>
          ))}
          {(!metrics?.recent_activity || metrics.recent_activity.length === 0) && (
            <p className="text-sm text-gray-400">{t('ui:PlatformAdminPage.noRecentActivity')}</p>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Organizations tab ─────────────────────────────────────────────────────

function OrganizationsTab() {
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [planFilter, setPlanFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null)

  // List
  const { data, isLoading } = useQuery({
    queryKey: ['platform-admin', 'organizations', search, planFilter],
    queryFn: () => platformAdminApi.listOrganizations({ search: search || undefined, plan: planFilter || undefined }),
  })

  // Detail
  const { data: orgDetailData } = useQuery({
    queryKey: ['platform-admin', 'org-detail', selectedOrgId],
    queryFn: () => platformAdminApi.getOrganization(selectedOrgId!),
    enabled: !!selectedOrgId,
  })

  // Feature flags (for override UI)
  const { data: flagsData } = useQuery({
    queryKey: ['platform-admin', 'feature-flags'],
    queryFn: () => platformAdminApi.listFeatureFlags(),
    enabled: !!selectedOrgId,
  })

  // Settings (for override UI)
  const { data: settingsData } = useQuery({
    queryKey: ['platform-admin', 'settings'],
    queryFn: () => platformAdminApi.listSettings(),
    enabled: !!selectedOrgId,
  })

  // Users list (for owner picker and member add)
  const { data: usersData } = useQuery({
    queryKey: ['platform-admin', 'users-all'],
    queryFn: () => platformAdminApi.listUsers({ page_size: 100 }),
    enabled: showCreate || !!selectedOrgId,
  })

  const orgs = (data as any)?.data ?? []
  const orgDetail = (orgDetailData as any)?.data
  const allFlags = (flagsData as any)?.data ?? []
  const allSettings = (settingsData as any)?.data ?? []
  const allUsers = (usersData as any)?.data ?? []

  if (selectedOrgId && orgDetail) {
    return (
      <OrgDetailView
        org={orgDetail}
        allFlags={allFlags}
        allSettings={allSettings}
        allUsers={allUsers}
        onBack={() => { setSelectedOrgId(null); queryClient.invalidateQueries({ queryKey: ['platform-admin', 'organizations'] }) }}
      />
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.organizations')}</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium bg-blue-600 text-white hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" /> {t('ui:PlatformAdminPage.createOrganization')}
        </button>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder={t('ui:PlatformAdminPage.searchOrganizations')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white"
          />
        </div>
        <select
          value={planFilter}
          onChange={(e) => setPlanFilter(e.target.value)}
          className="px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white"
        >
          <option value="">{t('ui:PlatformAdminPage.allPlans')}</option>
          <option value="starter">{t('ui:PlatformAdminPage.starter')}</option>
          <option value="pro">{t('ui:PlatformAdminPage.pro')}</option>
          <option value="business">{t('ui:PlatformAdminPage.business')}</option>
          <option value="enterprise">{t('ui:PlatformAdminPage.enterprise')}</option>
        </select>
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : orgs.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
          <Building2 className="w-8 h-8 mx-auto mb-2 text-gray-400" />
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.noOrganizationsYet')}</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.organization')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.plan')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.members')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.owner')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.status')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.created')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {orgs.map((org: any) => (
                <tr
                  key={org.id}
                  className="hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
                  onClick={() => setSelectedOrgId(org.id)}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900 dark:text-white">{org.name}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 font-mono">{org.slug}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize ${
                      org.plan === 'enterprise' ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400' :
                      org.plan === 'business' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400' :
                      org.plan === 'pro' ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' :
                      'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                    }`}>
                      {org.plan}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{org.member_count}</td>
                  <td className="px-4 py-3">
                    <div className="text-sm text-gray-900 dark:text-white">{org.owner_name}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{org.owner_email}</div>
                  </td>
                  <td className="px-4 py-3">
                    {org.is_active ? (
                      <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400 text-xs">
                        <CheckCircle className="w-3 h-3" /> {t('ui:PlatformAdminPage.active')}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-red-500 text-xs">
                        <XCircle className="w-3 h-3" /> {t('ui:PlatformAdminPage.inactive')}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                    {org.created_at ? timeAgo(org.created_at) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <CreateOrgModal
          allUsers={allUsers}
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false)
            queryClient.invalidateQueries({ queryKey: ['platform-admin', 'organizations'] })
          }}
        />
      )}
    </div>
  )
}

// ── Create Org Modal ──────────────────────────────────────────────────────

function CreateOrgModal({ allUsers, onClose, onCreated }: { allUsers: any[]; onClose: () => void; onCreated: () => void }) {
  const { t } = useTranslation('ui')
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [ownerId, setOwnerId] = useState('')
  const [plan, setPlan] = useState('starter')
  const [maxUsers, setMaxUsers] = useState(5)
  const [maxStorage, setMaxStorage] = useState(5)
  const [notes, setNotes] = useState('')

  const createMut = useMutation({
    mutationFn: () => platformAdminApi.createOrganization({
      name,
      slug,
      owner_id: ownerId,
      plan,
      max_users: maxUsers,
      max_storage_gb: maxStorage,
      notes: notes || undefined,
    }),
    onSuccess: () => {
      toast.success(t('ui:PlatformAdminPage.organizationCreated'))
      onCreated()
    },
    onError: (err: any) => toast.error(err?.message || 'Failed to create organization'),
  })

  const autoSlug = (n: string) => n.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">{t('ui:PlatformAdminPage.createOrganization')}</h2>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:PlatformAdminPage.name')} <span className="text-red-500">*</span></label>
            <input
              type="text"
              value={name}
              onChange={(e) => { setName(e.target.value); if (!slug || slug === autoSlug(name)) setSlug(autoSlug(e.target.value)) }}
              className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white"
              placeholder={t('ui:PlatformAdminPage.acmeCorp')}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:PlatformAdminPage.slug')} <span className="text-red-500">*</span></label>
            <input
              type="text"
              value={slug}
              onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
              className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white font-mono"
              placeholder="acme-corp"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:PlatformAdminPage.owner')} <span className="text-red-500">*</span></label>
            <select
              value={ownerId}
              onChange={(e) => setOwnerId(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white"
            >
              <option value="">{t('ui:PlatformAdminPage.selectOwner')}</option>
              {allUsers.map((u: any) => (
                <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:PlatformAdminPage.plan')}</label>
              <select
                value={plan}
                onChange={(e) => setPlan(e.target.value)}
                className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white"
              >
                <option value="starter">{t('ui:PlatformAdminPage.starter')}</option>
                <option value="pro">{t('ui:PlatformAdminPage.pro')}</option>
                <option value="business">{t('ui:PlatformAdminPage.business')}</option>
                <option value="enterprise">{t('ui:PlatformAdminPage.enterprise')}</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:PlatformAdminPage.maxUsers')}</label>
              <input type="number" value={maxUsers} onChange={(e) => setMaxUsers(Number(e.target.value))} min={1}
                className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:PlatformAdminPage.storageGb')}</label>
              <input type="number" value={maxStorage} onChange={(e) => setMaxStorage(Number(e.target.value))} min={1}
                className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:PlatformAdminPage.notes')}</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-4 py-2 rounded-md text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">{t('ui:PlatformAdminPage.cancel')}</button>
          <button
            onClick={() => createMut.mutate()}
            disabled={!name || !slug || !ownerId || createMut.isPending}
            className="px-4 py-2 rounded-md text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {createMut.isPending ? t('ui:PlatformAdminPage.creating') : t('ui:PlatformAdminPage.create')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Org Detail View ──────────────────────────────────────────────────────

function OrgDetailView({ org, allFlags, allSettings, allUsers, onBack }: {
  org: any; allFlags: any[]; allSettings: any[]; allUsers: any[]; onBack: () => void
}) {
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [editMode, setEditMode] = useState(false)
  const [editData, setEditData] = useState<any>({})
  const [showAddMember, setShowAddMember] = useState(false)
  const [addUserId, setAddUserId] = useState('')

  const invalidateOrg = () => queryClient.invalidateQueries({ queryKey: ['platform-admin', 'org-detail', org.id] })

  // Update org
  const updateMut = useMutation({
    mutationFn: (data: any) => platformAdminApi.updateOrganization(org.id, data),
    onSuccess: () => { toast.success(t('ui:PlatformAdminPage.organizationUpdated')); setEditMode(false); invalidateOrg() },
    onError: (err: any) => toast.error(err?.message || 'Update failed'),
  })

  // Delete org
  const deleteMut = useMutation({
    mutationFn: () => platformAdminApi.deleteOrganization(org.id),
    onSuccess: () => { toast.success(t('ui:PlatformAdminPage.organizationDeleted')); onBack() },
  })

  // Feature override
  const featureOverrideMut = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      platformAdminApi.setOrgFeatureOverride(org.id, key, enabled),
    onSuccess: () => invalidateOrg(),
  })

  const deleteFeatureOverrideMut = useMutation({
    mutationFn: (key: string) => platformAdminApi.deleteOrgFeatureOverride(org.id, key),
    onSuccess: () => invalidateOrg(),
  })

  // Setting override
  const settingOverrideMut = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      platformAdminApi.setOrgSettingOverride(org.id, key, value),
    onSuccess: () => invalidateOrg(),
  })

  const deleteSettingOverrideMut = useMutation({
    mutationFn: (key: string) => platformAdminApi.deleteOrgSettingOverride(org.id, key),
    onSuccess: () => invalidateOrg(),
  })

  // Members
  const addMemberMut = useMutation({
    mutationFn: (userId: string) => platformAdminApi.addOrgMember(org.id, userId),
    onSuccess: () => { toast.success(t('ui:PlatformAdminPage.memberAdded')); setShowAddMember(false); setAddUserId(''); invalidateOrg() },
  })

  const removeMemberMut = useMutation({
    mutationFn: (userId: string) => platformAdminApi.removeOrgMember(org.id, userId),
    onSuccess: () => { toast.success(t('ui:PlatformAdminPage.memberRemoved')); invalidateOrg() },
  })

  // Build override lookup maps
  const featureOverrideMap = new Map<string, boolean>()
  ;(org.feature_overrides ?? []).forEach((o: any) => featureOverrideMap.set(o.feature_key, o.enabled))
  const settingOverrideMap = new Map<string, string>()
  ;(org.setting_overrides ?? []).forEach((o: any) => settingOverrideMap.set(o.setting_key, o.value))

  const categories = [...new Set(allFlags.map((f: any) => f.category))] as string[]
  const settingCategories = [...new Set(allSettings.map((s: any) => s.category))] as string[]
  const memberIds = new Set((org.members ?? []).map((m: any) => m.id))
  const nonMembers = allUsers.filter((u: any) => !memberIds.has(u.id))

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500">
          <ChevronLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{org.name}</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 font-mono">{org.slug}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setEditMode(!editMode); setEditData({ name: org.name, slug: org.slug, plan: org.plan, max_users: org.max_users, max_storage_gb: org.max_storage_gb, is_active: org.is_active, logo_url: org.logo_url || '', primary_color: org.primary_color || '', secondary_color: org.secondary_color || '', custom_domain: org.custom_domain || '', notes: org.notes || '' }) }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <Edit3 className="w-3.5 h-3.5" /> {t('ui:PlatformAdminPage.edit')}
          </button>
          <button
            onClick={() => { if (confirm(t('ui:PlatformAdminPage.deleteThisOrganizationMembersWill'))) deleteMut.mutate() }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm border border-red-300 dark:border-red-600 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
          >
            <Trash2 className="w-3.5 h-3.5" /> {t('ui:PlatformAdminPage.delete')}
          </button>
        </div>
      </div>

      {/* Edit form */}
      {editMode && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-blue-200 dark:border-blue-800 p-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.editOrganization')}</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.name')}</label>
              <input type="text" value={editData.name ?? ''} onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.slug')}</label>
              <input type="text" value={editData.slug ?? ''} onChange={(e) => setEditData({ ...editData, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white font-mono" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.plan')}</label>
              <select value={editData.plan ?? 'starter'} onChange={(e) => setEditData({ ...editData, plan: e.target.value })}
                className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white">
                <option value="starter">{t('ui:PlatformAdminPage.starter')}</option>
                <option value="pro">{t('ui:PlatformAdminPage.pro')}</option>
                <option value="business">{t('ui:PlatformAdminPage.business')}</option>
                <option value="enterprise">{t('ui:PlatformAdminPage.enterprise')}</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.active')}</label>
              <select value={editData.is_active ? 'true' : 'false'} onChange={(e) => setEditData({ ...editData, is_active: e.target.value === 'true' })}
                className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white">
                <option value="true">{t('ui:PlatformAdminPage.active')}</option>
                <option value="false">{t('ui:PlatformAdminPage.inactive')}</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.maxUsers')}</label>
              <input type="number" min={1} value={editData.max_users ?? 5} onChange={(e) => setEditData({ ...editData, max_users: Number(e.target.value) })}
                className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.maxStorageGb')}</label>
              <input type="number" min={1} value={editData.max_storage_gb ?? 5} onChange={(e) => setEditData({ ...editData, max_storage_gb: Number(e.target.value) })}
                className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" />
            </div>
          </div>

          {/* White-label */}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-3 mt-3">
            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2 flex items-center gap-1"><Palette className="w-3.5 h-3.5" /> {t('ui:PlatformAdminPage.whiteLabel')}</h4>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.logoUrl')}</label>
                <input type="text" value={editData.logo_url ?? ''} onChange={(e) => setEditData({ ...editData, logo_url: e.target.value })}
                  className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" placeholder="https://..." />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.customDomain')}</label>
                <input type="text" value={editData.custom_domain ?? ''} onChange={(e) => setEditData({ ...editData, custom_domain: e.target.value })}
                  className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" placeholder={t('ui:PlatformAdminPage.appExampleCom')} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.primaryColor')}</label>
                <div className="flex items-center gap-2">
                  <input type="color" value={editData.primary_color || '#3b82f6'} onChange={(e) => setEditData({ ...editData, primary_color: e.target.value })}
                    className="w-8 h-8 rounded border border-gray-300 dark:border-gray-600 cursor-pointer" />
                  <input type="text" value={editData.primary_color ?? ''} onChange={(e) => setEditData({ ...editData, primary_color: e.target.value })}
                    className="flex-1 px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white font-mono" placeholder="#3b82f6" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.secondaryColor')}</label>
                <div className="flex items-center gap-2">
                  <input type="color" value={editData.secondary_color || '#6b7280'} onChange={(e) => setEditData({ ...editData, secondary_color: e.target.value })}
                    className="w-8 h-8 rounded border border-gray-300 dark:border-gray-600 cursor-pointer" />
                  <input type="text" value={editData.secondary_color ?? ''} onChange={(e) => setEditData({ ...editData, secondary_color: e.target.value })}
                    className="flex-1 px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white font-mono" placeholder="#6b7280" />
                </div>
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.notes')}</label>
            <textarea value={editData.notes ?? ''} onChange={(e) => setEditData({ ...editData, notes: e.target.value })} rows={2}
              className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" />
          </div>

          <div className="flex justify-end gap-2">
            <button onClick={() => setEditMode(false)} className="px-3 py-1.5 rounded text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">{t('ui:PlatformAdminPage.cancel')}</button>
            <button onClick={() => updateMut.mutate(editData)} disabled={updateMut.isPending}
              className="flex items-center gap-1 px-3 py-1.5 rounded text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
              <Save className="w-3.5 h-3.5" /> {t('ui:PlatformAdminPage.save')}
            </button>
          </div>
        </div>
      )}

      {/* Info cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.plan')}</p>
          <p className="text-lg font-bold text-gray-900 dark:text-white capitalize">{org.plan}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.members')}</p>
          <p className="text-lg font-bold text-gray-900 dark:text-white">{org.member_count} / {org.max_users}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.storageLimit')}</p>
          <p className="text-lg font-bold text-gray-900 dark:text-white">{org.max_storage_gb} GB</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.status')}</p>
          <p className={`text-lg font-bold ${org.is_active ? 'text-green-600' : 'text-red-500'}`}>{org.is_active ? t('ui:PlatformAdminPage.active') : t('ui:PlatformAdminPage.inactive')}</p>
        </div>
      </div>

      {/* Members */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.members_2')}{org.members?.length ?? 0})</h3>
          <button onClick={() => setShowAddMember(!showAddMember)}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-blue-600 text-white hover:bg-blue-700">
            <UserPlus className="w-3 h-3" /> {t('ui:PlatformAdminPage.add')}
          </button>
        </div>
        {showAddMember && (
          <div className="px-4 py-2 bg-blue-50 dark:bg-blue-900/20 border-b border-blue-200 dark:border-blue-800 flex items-center gap-2">
            <select value={addUserId} onChange={(e) => setAddUserId(e.target.value)}
              className="flex-1 px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white">
              <option value="">{t('ui:PlatformAdminPage.selectUser')}</option>
              {nonMembers.map((u: any) => <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>)}
            </select>
            <button onClick={() => addUserId && addMemberMut.mutate(addUserId)} disabled={!addUserId || addMemberMut.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">{t('ui:PlatformAdminPage.add')}</button>
            <button onClick={() => { setShowAddMember(false); setAddUserId('') }}
              className="px-2 py-1.5 rounded text-xs text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700">{t('ui:PlatformAdminPage.cancel')}</button>
          </div>
        )}
        <div className="divide-y divide-gray-200 dark:divide-gray-700">
          {(org.members ?? []).map((m: any) => (
            <div key={m.id} className="flex items-center justify-between px-4 py-2.5">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">{m.full_name}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">{m.email} &middot; <span className="capitalize">{m.role?.replace('_', ' ')}</span></p>
              </div>
              <button onClick={() => { if (confirm(t('ui:PlatformAdminPage.removeFullName', { full_name: m.full_name }))) removeMemberMut.mutate(m.id) }}
                className="p-1 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20" title={t('ui:PlatformAdminPage.removeMember')}>
                <UserMinus className="w-4 h-4" />
              </button>
            </div>
          ))}
          {(!org.members || org.members.length === 0) && (
            <p className="px-4 py-3 text-sm text-gray-400">{t('ui:PlatformAdminPage.noMembers')}</p>
          )}
        </div>
      </div>

      {/* Feature Overrides */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.featureOverrides')}</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.overrideGlobalFeatureFlagsFor')}</p>
        </div>
        {categories.map((cat) => (
          <div key={cat}>
            <div className="px-4 py-2 bg-gray-50/50 dark:bg-gray-900/50 border-b border-gray-100 dark:border-gray-800">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{cat}</span>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {allFlags.filter((f: any) => f.category === cat).map((flag: any) => {
                const hasOverride = featureOverrideMap.has(flag.key)
                const overrideValue = featureOverrideMap.get(flag.key)
                const effectiveValue = hasOverride ? overrideValue : flag.enabled
                return (
                  <div key={flag.key} className="flex items-center justify-between px-4 py-2.5">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-900 dark:text-white">{flag.name}</p>
                      <p className="text-[10px] text-gray-400 font-mono">{flag.key} {hasOverride ? t('ui:PlatformAdminPage.overridden') : t('ui:PlatformAdminPage.global')}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => featureOverrideMut.mutate({ key: flag.key, enabled: !effectiveValue })}
                        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                          effectiveValue ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
                        } ${hasOverride ? 'ring-2 ring-blue-300 dark:ring-blue-700' : ''}`}
                      >
                        <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                          effectiveValue ? 'translate-x-4' : 'translate-x-0.5'
                        }`} />
                      </button>
                      {hasOverride && (
                        <button onClick={() => deleteFeatureOverrideMut.mutate(flag.key)}
                          className="p-0.5 rounded text-gray-400 hover:text-red-500" title={t('ui:PlatformAdminPage.resetToGlobal')}>
                          <XCircle className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Setting Overrides */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.settingOverrides')}</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.overrideGlobalPricingLimitsFor')}</p>
        </div>
        {settingCategories.map((cat) => (
          <div key={cat}>
            <div className="px-4 py-2 bg-gray-50/50 dark:bg-gray-900/50 border-b border-gray-100 dark:border-gray-800">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{cat}</span>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {allSettings.filter((s: any) => s.category === cat).map((setting: any) => {
                const hasOverride = settingOverrideMap.has(setting.key)
                const overrideValue = settingOverrideMap.get(setting.key)
                const effectiveValue = hasOverride ? overrideValue : setting.value
                return (
                  <div key={setting.key} className="flex items-center justify-between px-4 py-2.5">
                    <div className="flex-1 min-w-0 mr-4">
                      <p className="text-sm text-gray-900 dark:text-white">{setting.description || setting.key}</p>
                      <p className="text-[10px] text-gray-400 font-mono">{setting.key} {hasOverride ? t('ui:PlatformAdminPage.overridden') : t('ui:PlatformAdminPage.global')}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type={setting.value_type === 'number' ? 'number' : 'text'}
                        value={effectiveValue ?? ''}
                        onChange={(e) => settingOverrideMut.mutate({ key: setting.key, value: e.target.value })}
                        className={`w-24 px-2 py-1 rounded border text-sm text-right font-mono text-gray-900 dark:text-white bg-white dark:bg-gray-700 ${
                          hasOverride
                            ? 'border-blue-300 dark:border-blue-700 ring-1 ring-blue-200 dark:ring-blue-800'
                            : 'border-gray-300 dark:border-gray-600'
                        }`}
                      />
                      {hasOverride && (
                        <button onClick={() => deleteSettingOverrideMut.mutate(setting.key)}
                          className="p-0.5 rounded text-gray-400 hover:text-red-500" title={t('ui:PlatformAdminPage.resetToGlobal')}>
                          <XCircle className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      {/* White-label preview */}
      {(org.logo_url || org.primary_color || org.custom_domain) && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3 flex items-center gap-1.5"><Palette className="w-4 h-4" /> {t('ui:PlatformAdminPage.whiteLabelSettings')}</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {org.logo_url && (
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.logo')}</p>
                <img src={org.logo_url} alt={t('ui:PlatformAdminPage.orgLogo')} className="h-10 object-contain" />
              </div>
            )}
            {org.primary_color && (
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.primaryColor')}</p>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded" style={{ backgroundColor: org.primary_color }} />
                  <span className="font-mono text-gray-700 dark:text-gray-300">{org.primary_color}</span>
                </div>
              </div>
            )}
            {org.secondary_color && (
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.secondaryColor')}</p>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded" style={{ backgroundColor: org.secondary_color }} />
                  <span className="font-mono text-gray-700 dark:text-gray-300">{org.secondary_color}</span>
                </div>
              </div>
            )}
            {org.custom_domain && (
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.customDomain')}</p>
                <span className="font-mono text-gray-700 dark:text-gray-300">{org.custom_domain}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Owner + meta */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-sm">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.owner')}</p>
            <p className="text-gray-900 dark:text-white font-medium">{org.owner_name}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">{org.owner_email}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.created')}</p>
            <p className="text-gray-900 dark:text-white">{org.created_at ? new Date(org.created_at).toLocaleDateString() : '-'}</p>
          </div>
          {org.notes && (
            <div className="col-span-2">
              <p className="text-xs text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.notes')}</p>
              <p className="text-gray-700 dark:text-gray-300">{org.notes}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Users tab ────────────────────────────────────────────────────────────

const ROLES = [
  { value: 'admin', label: i18n.t('ui:PlatformAdminPage.admin') },
  { value: 'manager', label: i18n.t('ui:PlatformAdminPage.manager') },
  { value: 'team_member', label: i18n.t('ui:PlatformAdminPage.teamMember') },
  { value: 'accountant', label: i18n.t('ui:PlatformAdminPage.accountant') },
  { value: 'client', label: i18n.t('ui:PlatformAdminPage.client') },
  { value: 'viewer', label: i18n.t('ui:PlatformAdminPage.viewer') },
]

function FeatureAccessEditor({ features, onChange, role }: {
  features: Record<string, boolean>
  onChange: (f: Record<string, boolean>) => void
  role: string
}) {
  const { t } = useTranslation('ui')
  const defaults = ROLE_DEFAULTS[role] ?? {}
  const applyDefaults = () => onChange({ ...defaults })

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.featureAccess')}</h4>
        <button onClick={applyDefaults} className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400">
         {t('ui:PlatformAdminPage.resetToRoleDefaults')}
        </button>
      </div>
      {Object.entries(FEATURE_CATEGORIES).map(([category, keys]) => (
        <div key={category}>
          <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{category}</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            {keys.map(key => (
              <label key={key} className="flex items-center gap-2 text-xs cursor-pointer">
                <input
                  type="checkbox"
                  checked={features[key] ?? false}
                  onChange={e => onChange({ ...features, [key]: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 h-3.5 w-3.5"
                />
                <span className="text-gray-700 dark:text-gray-300">{FEATURE_LABELS[key] || key}</span>
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function UserModal({ user, onClose, onSaved }: {
  user?: any  // null = create, object = edit
  onClose: () => void
  onSaved: () => void
}) {
  const { t } = useTranslation('ui')
  const isEdit = !!user
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [email, setEmail] = useState(user?.email || '')
  const [role, setRole] = useState(user?.role || 'viewer')
  const [password, setPassword] = useState('')
  const [sendInvite, setSendInvite] = useState(!isEdit)
  const [features, setFeatures] = useState<Record<string, boolean>>(
    user?.feature_access ?? { ...(ROLE_DEFAULTS[user?.role || 'viewer'] || {}) }
  )
  const [isActive, setIsActive] = useState(user?.is_active ?? true)
  const [managerId, setManagerId] = useState<string>(user?.manager_id || '')
  const [inviteLink, setInviteLink] = useState<string | null>(null)

  // For the manager picker: everyone who could be someone's boss (not the user
  // being edited, not clients).
  const { data: allUsers } = useQuery({
    queryKey: ['platform-admin', 'users', 'all-for-manager'],
    queryFn: () => platformAdminApi.listUsers({ page: 1, page_size: 100 }),
  })
  const managerOptions = ((allUsers as any)?.data ?? []).filter(
    (u: any) => u.id !== user?.id && u.role !== 'client',
  )

  // Auto-apply role defaults when role changes (only on create)
  const handleRoleChange = (newRole: string) => {
    setRole(newRole)
    if (!isEdit) {
      setFeatures({ ...(ROLE_DEFAULTS[newRole] || {}) })
    }
  }

  const createMut = useMutation({
    mutationFn: () => platformAdminApi.createUser({
      email,
      full_name: fullName,
      role,
      password: sendInvite ? undefined : password,
      send_invite: sendInvite,
      feature_access: features,
    }),
    onSuccess: (res: any) => {
      const link = res?.data?.invite_link
      if (link) {
        setInviteLink(link)
      } else {
        toast.success(t('ui:PlatformAdminPage.userCreated'))
        onSaved()
        onClose()
      }
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Failed to create user'),
  })

  const updateMut = useMutation({
    mutationFn: () => platformAdminApi.updateUser(user.id, {
      email: email !== user.email ? email : undefined,
      full_name: fullName !== user.full_name ? fullName : undefined,
      role: role !== user.role ? role : undefined,
      password: password || undefined,
      feature_access: features,
      is_active: isActive,
      manager_id: managerId || null,
    }),
    onSuccess: () => {
      toast.success(t('ui:PlatformAdminPage.userUpdated'))
      onSaved()
      onClose()
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Failed to update user'),
  })

  // Show invite link after create
  if (inviteLink) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
        <div className="bg-white dark:bg-gray-800 rounded-lg w-full max-w-md p-6 shadow-xl" onClick={e => e.stopPropagation()}>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">{t('ui:PlatformAdminPage.userCreatedInviteLink')}</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
            {sendInvite ? t('ui:PlatformAdminPage.anInviteEmailWasSent') : t('ui:PlatformAdminPage.shareThisSetupLinkWith')}
          </p>
          <div className="flex items-center gap-2">
            <input
              readOnly
              value={inviteLink}
              className="flex-1 px-3 py-2 text-xs font-mono rounded-md border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white"
            />
            <button
              onClick={() => { navigator.clipboard.writeText(inviteLink); toast.success(t('ui:PlatformAdminPage.copied')) }}
              className="px-3 py-2 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-700"
            >
              <Copy className="w-4 h-4" />
            </button>
          </div>
          <button onClick={() => { onSaved(); onClose() }} className="mt-4 w-full py-2 rounded-md bg-gray-100 dark:bg-gray-700 text-sm font-medium text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-600">
           {t('ui:PlatformAdminPage.done')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white dark:bg-gray-800 rounded-lg w-full max-w-lg max-h-[90vh] overflow-y-auto p-6 shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            {isEdit ? t('ui:PlatformAdminPage.editUser') : t('ui:PlatformAdminPage.addUser')}
          </h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Basic fields */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.fullName')}</label>
              <input value={fullName} onChange={e => setFullName(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.email')}</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white" />
            </div>
          </div>

          {/* Role */}
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{t('ui:PlatformAdminPage.role')}</label>
            <select value={role} onChange={e => handleRoleChange(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white">
              {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>

          {/* Reports-to — a manager sees the records of everyone who reports to
              them. Only relevant for staff; a client can't have a manager. */}
          {role !== 'client' && (
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
               {t('ui:PlatformAdminPage.reportsTo')}
              </label>
              <select value={managerId} onChange={e => setManagerId(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white">
                <option value="">{t('ui:PlatformAdminPage.noManager')}</option>
                {managerOptions.map((u: any) => (
                  <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>
                ))}
              </select>
              <p className="mt-1 text-xs text-gray-400">
               {t('ui:PlatformAdminPage.aManagerSeesTheRecords')}
              </p>
            </div>
          )}

          {/* Invite toggle (create only) */}
          {!isEdit && (
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={sendInvite} onChange={e => setSendInvite(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
              <span className="text-sm text-gray-700 dark:text-gray-300">
                <Mail className="w-3.5 h-3.5 inline mr-1" />
               {t('ui:PlatformAdminPage.sendInviteEmailUserSets')}
              </span>
            </label>
          )}

          {/* Password */}
          {(isEdit || !sendInvite) && (
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                {isEdit ? t('ui:PlatformAdminPage.newPasswordLeaveBlankTo') : t('ui:PlatformAdminPage.password')}
              </label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder={isEdit ? t('ui:PlatformAdminPage.leaveBlankToKeepCurrent') : t('ui:PlatformAdminPage.min8Chars1Upper')}
                className="w-full px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white" />
            </div>
          )}

          {/* Active toggle (edit only) */}
          {isEdit && (
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={isActive} onChange={e => setIsActive(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
              <span className="text-sm text-gray-700 dark:text-gray-300">{t('ui:PlatformAdminPage.accountActive')}</span>
            </label>
          )}

          {/* Feature access */}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
            <FeatureAccessEditor features={features} onChange={setFeatures} role={role} />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={() => isEdit ? updateMut.mutate() : createMut.mutate()}
            disabled={createMut.isPending || updateMut.isPending || !fullName || !email}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {(createMut.isPending || updateMut.isPending) ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {isEdit ? t('ui:PlatformAdminPage.saveChanges') : (sendInvite ? t('ui:PlatformAdminPage.createSendInvite') : t('ui:PlatformAdminPage.createUser'))}
          </button>
          <button onClick={onClose}
            className="px-4 py-2 text-sm font-medium rounded-md bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600">
           {t('ui:PlatformAdminPage.cancel')}
          </button>
        </div>
      </div>
    </div>
  )
}

function UsersTab() {
  const { t } = useTranslation('ui')
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
  const [showModal, setShowModal] = useState<'create' | 'edit' | null>(null)
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['platform-admin', 'users', search, roleFilter],
    queryFn: () => platformAdminApi.listUsers({ search: search || undefined, role: roleFilter || undefined }),
  })

  const { data: userDetail } = useQuery({
    queryKey: ['platform-admin', 'user-detail', selectedUserId],
    queryFn: () => platformAdminApi.getUserDetail(selectedUserId!),
    enabled: !!selectedUserId,
  })

  const impersonateMut = useMutation({
    mutationFn: (userId: string) => platformAdminApi.impersonateUser(userId),
    onSuccess: (res: any) => {
      const token = res.data.access_token
      localStorage.setItem('access_token', token)
      toast.success(t('ui:PlatformAdminPage.impersonationActiveRefreshToApply'))
      window.location.reload()
    },
  })

  const revokeSessionsMut = useMutation({
    mutationFn: (userId: string) => platformAdminApi.revokeUserSessions(userId),
    onSuccess: () => {
      toast.success(t('ui:PlatformAdminPage.allSessionsRevoked'))
      queryClient.invalidateQueries({ queryKey: ['platform-admin'] })
    },
  })

  const deactivateMut = useMutation({
    mutationFn: (userId: string) => platformAdminApi.deactivateUser(userId),
    onSuccess: () => {
      toast.success(t('ui:PlatformAdminPage.userDeactivated'))
      queryClient.invalidateQueries({ queryKey: ['platform-admin'] })
    },
  })

  const reactivateMut = useMutation({
    mutationFn: (userId: string) => platformAdminApi.reactivateUser(userId),
    onSuccess: () => {
      toast.success(t('ui:PlatformAdminPage.userReactivated'))
      queryClient.invalidateQueries({ queryKey: ['platform-admin'] })
    },
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['platform-admin'] })
  const users = (data as any)?.data ?? []
  const detail = (userDetail as any)?.data

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.usersManagement')}</h1>
        <button
          onClick={() => setShowModal('create')}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700"
        >
          <UserPlus className="w-4 h-4" /> {t('ui:PlatformAdminPage.addUser')}
        </button>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder={t('ui:PlatformAdminPage.searchUsers')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white"
        >
          <option value="">{t('ui:PlatformAdminPage.allRoles')}</option>
          <option value="admin">{t('ui:PlatformAdminPage.admin')}</option>
          <option value="team_member">{t('ui:PlatformAdminPage.teamMember')}</option>
          <option value="accountant">{t('ui:PlatformAdminPage.accountant')}</option>
          <option value="client">{t('ui:PlatformAdminPage.client')}</option>
          <option value="viewer">{t('ui:PlatformAdminPage.viewer')}</option>
        </select>
      </div>

      <div className="flex gap-4">
        {/* User list */}
        <div className="flex-1 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          {isLoading ? (
            <LoadingSpinner />
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.user')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.role')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.status')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.lastLogin')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{t('ui:PlatformAdminPage.actions')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {users.map((u: any) => (
                  <tr
                    key={u.id}
                    className={`hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer ${!u.is_active ? 'opacity-50' : ''} ${selectedUserId === u.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''}`}
                    onClick={() => setSelectedUserId(u.id)}
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900 dark:text-white">{u.full_name}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">{u.email}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300 capitalize">
                        {u.role?.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {u.is_active ? (
                        <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400 text-xs">
                          <CheckCircle className="w-3 h-3" /> {t('ui:PlatformAdminPage.active')}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-red-500 text-xs">
                          <XCircle className="w-3 h-3" /> {t('ui:PlatformAdminPage.inactive')}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                      {u.last_login ? timeAgo(u.last_login) : t('ui:PlatformAdminPage.never')}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={(e) => { e.stopPropagation(); setSelectedUserId(u.id); setShowModal('edit') }}
                          title={t('ui:PlatformAdminPage.editUser_2')}
                          className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500 hover:text-blue-600"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); impersonateMut.mutate(u.id) }}
                          title={t('ui:PlatformAdminPage.impersonate')}
                          className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500 hover:text-blue-600"
                        >
                          <LogIn className="w-3.5 h-3.5" />
                        </button>
                        {u.is_active ? (
                          <button
                            onClick={(e) => { e.stopPropagation(); if (confirm(t('ui:PlatformAdminPage.deactivateFullName', { full_name: u.full_name }))) deactivateMut.mutate(u.id) }}
                            title={t('ui:PlatformAdminPage.deactivate')}
                            className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500 hover:text-red-600"
                          >
                            <Power className="w-3.5 h-3.5" />
                          </button>
                        ) : (
                          <button
                            onClick={(e) => { e.stopPropagation(); reactivateMut.mutate(u.id) }}
                            title={t('ui:PlatformAdminPage.reactivate')}
                            className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500 hover:text-green-600"
                          >
                            <Power className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); revokeSessionsMut.mutate(u.id) }}
                          title={t('ui:PlatformAdminPage.revokeSessions')}
                          className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500 hover:text-red-600"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* User detail panel */}
        {selectedUserId && detail && (
          <div className="w-80 shrink-0 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 overflow-y-auto max-h-[calc(100vh-200px)]">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium text-gray-900 dark:text-white">{detail.full_name}</h3>
              <button onClick={() => { setShowModal('edit') }} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500">
                <Edit3 className="w-4 h-4" />
              </button>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400">{detail.email}</p>
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.role')}</span>
                <span className="text-gray-900 dark:text-white capitalize">{detail.role?.replace('_', ' ')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.auth')}</span>
                <span className="text-gray-900 dark:text-white">{detail.auth_provider}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.pages')}</span>
                <span className="text-gray-900 dark:text-white">{detail.page_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.documents')}</span>
                <span className="text-gray-900 dark:text-white">{detail.document_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.invoices')}</span>
                <span className="text-gray-900 dark:text-white">{detail.invoice_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.activities')}</span>
                <span className="text-gray-900 dark:text-white">{detail.activity_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.joined')}</span>
                <span className="text-gray-900 dark:text-white">{detail.created_at ? new Date(detail.created_at).toLocaleDateString() : '-'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.lastLogin')}</span>
                <span className="text-gray-900 dark:text-white">{detail.last_login ? timeAgo(detail.last_login) : t('ui:PlatformAdminPage.never')}</span>
              </div>
            </div>

            {detail.recent_activity?.length > 0 && (
              <div className="mt-4 border-t border-gray-200 dark:border-gray-700 pt-3">
                <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2">{t('ui:PlatformAdminPage.recentActivity')}</h4>
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {detail.recent_activity.map((a: any) => (
                    <div key={a.id} className="text-xs text-gray-600 dark:text-gray-400">
                      <span className="font-medium">{a.action}</span> {a.resource_type}
                      <span className="block text-gray-400 text-[10px]">{timeAgo(a.created_at)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modals */}
      {showModal === 'create' && (
        <UserModal onClose={() => setShowModal(null)} onSaved={invalidate} />
      )}
      {showModal === 'edit' && detail && (
        <UserModal user={detail} onClose={() => setShowModal(null)} onSaved={invalidate} />
      )}
    </div>
  )
}

// ── Feature toggles tab ─────────────────────────────────────────────────

function FeatureTogglesTab() {
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['platform-admin', 'feature-flags'],
    queryFn: () => platformAdminApi.listFeatureFlags(),
  })

  const toggleMut = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      platformAdminApi.updateFeatureFlag(key, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['platform-admin', 'feature-flags'] })
    },
  })

  const flags = (data as any)?.data ?? []
  const categories = [...new Set(flags.map((f: any) => f.category))] as string[]

  if (isLoading) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.featureToggles')}</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.enableOrDisableFeaturesAcross')}</p>

      {categories.map((cat) => (
        <div key={cat} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
            <h3 className="text-sm font-medium text-gray-900 dark:text-white capitalize">{cat}</h3>
          </div>
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {flags.filter((f: any) => f.category === cat).map((flag: any) => (
              <div key={flag.key} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">{flag.name}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{flag.description}</p>
                  <p className="text-[10px] text-gray-400 font-mono mt-0.5">{flag.key}</p>
                </div>
                <button
                  onClick={() => toggleMut.mutate({ key: flag.key, enabled: !flag.enabled })}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    flag.enabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      flag.enabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Pricing & Limits tab ────────────────────────────────────────────────

function PricingTab() {
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['platform-admin', 'settings'],
    queryFn: () => platformAdminApi.listSettings(),
  })

  const updateMut = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      platformAdminApi.updateSetting(key, { value }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['platform-admin', 'settings'] })
      setEditingKey(null)
      toast.success(t('ui:PlatformAdminPage.settingUpdated'))
    },
  })

  const settings = (data as any)?.data ?? []
  const categories = [...new Set(settings.map((s: any) => s.category))] as string[]

  if (isLoading) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.pricingLimits')}</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.managePlanPricingUsageLimits')}</p>

      {categories.map((cat) => (
        <div key={cat} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
            <h3 className="text-sm font-medium text-gray-900 dark:text-white capitalize">{cat}</h3>
          </div>
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {settings.filter((s: any) => s.category === cat).map((setting: any) => (
              <div key={setting.key} className="flex items-center justify-between px-4 py-3">
                <div className="flex-1 mr-4">
                  <p className="text-sm font-medium text-gray-900 dark:text-white">{setting.description || setting.key}</p>
                  <p className="text-[10px] text-gray-400 font-mono">{setting.key}</p>
                </div>
                {editingKey === setting.key ? (
                  <div className="flex items-center gap-2">
                    <input
                      type={setting.value_type === 'number' ? 'number' : 'text'}
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className="w-24 px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white"
                      autoFocus
                    />
                    <button
                      onClick={() => updateMut.mutate({ key: setting.key, value: editValue })}
                      className="p-1 rounded text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20"
                    >
                      <Save className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setEditingKey(null)}
                      className="p-1 rounded text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                      <XCircle className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => { setEditingKey(setting.key); setEditValue(setting.value || '') }}
                    className="flex items-center gap-2 px-3 py-1 rounded bg-gray-100 dark:bg-gray-700 text-sm font-mono text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-600"
                  >
                    {setting.value_type === 'number' && setting.category === 'pricing' && '$'}{setting.value ?? '-'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── API Keys tab ────────────────────────────────────────────────────────

const INTEGRATION_LABELS: Record<string, string> = {
  anthropic: 'Anthropic (Claude)',
  gemini: 'Google Gemini',
  openai: 'OpenAI',
  stripe: 'Stripe',
  twilio: 'Twilio',
  plaid: 'Plaid',
  google: 'Google OAuth',
  livekit: 'LiveKit',
  smtp: 'SMTP Email',
  cloudflare_r2: 'Cloudflare R2',
  assemblyai: 'AssemblyAI',
  porkbun: 'Porkbun (Domain Reseller)',
  migadu: 'Migadu (Email Hosting)',
}

const SECRET_FIELD_KEYWORDS = ['key', 'secret', 'token', 'password', 'sid']

function isSecretField(name: string) {
  return SECRET_FIELD_KEYWORDS.some(kw => name.toLowerCase().includes(kw))
}

function ApiKeyCard({ integration, fields, configured, onSaved }: {
  integration: string
  fields: { name: string; configured: boolean; masked_value: string }[]
  configured: boolean
  onSaved: () => void
}) {
  const { t } = useTranslation('ui')
  const [editing, setEditing] = useState(false)
  const [values, setValues] = useState<Record<string, string>>({})
  const [showValues, setShowValues] = useState<Record<string, boolean>>({})
  const [testResult, setTestResult] = useState<{ status: string; message: string; latency_ms?: number } | null>(null)
  const [testing, setTesting] = useState(false)

  const saveMut = useMutation({
    mutationFn: () => platformAdminApi.saveApiKeys(integration, values),
    onSuccess: () => {
      toast.success(t('ui:PlatformAdminPage.v0KeysSaved', { v0: INTEGRATION_LABELS[integration] || integration }))
      setEditing(false)
      setValues({})
      onSaved()
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Failed to save'),
  })

  const removeMut = useMutation({
    mutationFn: () => platformAdminApi.deleteApiKeys(integration),
    onSuccess: () => {
      toast.success(t('ui:PlatformAdminPage.v0KeysRemoved', { v0: INTEGRATION_LABELS[integration] || integration }))
      setTestResult(null)
      onSaved()
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Failed to remove'),
  })

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await platformAdminApi.testApiConnection(integration)
      setTestResult((res as any).data)
    } catch (err: any) {
      setTestResult({ status: 'error', message: err?.response?.data?.detail || 'Test failed' })
    } finally {
      setTesting(false)
    }
  }

  const startEditing = () => {
    const init: Record<string, string> = {}
    fields.forEach(f => { init[f.name] = f.configured ? f.masked_value : '' })
    setValues(init)
    setEditing(true)
    setTestResult(null)
  }

  const hasChanges = Object.entries(values).some(([key, val]) => {
    const field = fields.find(f => f.name === key)
    return field ? val !== field.masked_value : !!val
  })

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
          {INTEGRATION_LABELS[integration] || integration}
        </h3>
        <div className="flex items-center gap-2">
          {configured ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
              <CheckCircle className="w-3 h-3" /> {t('ui:PlatformAdminPage.configured')}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400">
              <AlertTriangle className="w-3 h-3" /> {t('ui:PlatformAdminPage.notConfigured')}
            </span>
          )}
        </div>
      </div>

      {/* View mode: field status list */}
      {!editing && (
        <>
          <div className="space-y-1.5 mb-3">
            {fields.map(f => (
              <div key={f.name} className="flex items-center gap-2 text-xs">
                {f.configured ? (
                  <CheckCircle className="w-3 h-3 text-green-500 shrink-0" />
                ) : (
                  <XCircle className="w-3 h-3 text-gray-300 dark:text-gray-600 shrink-0" />
                )}
                <span className="font-mono text-gray-600 dark:text-gray-400">{f.name}</span>
                {f.configured && f.masked_value && (
                  <span className="font-mono text-gray-400 dark:text-gray-500 ml-auto">{f.masked_value}</span>
                )}
              </div>
            ))}
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 pt-2 border-t border-gray-100 dark:border-gray-700">
            <button
              onClick={startEditing}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md bg-blue-50 text-blue-700 hover:bg-blue-100 dark:bg-blue-900/20 dark:text-blue-400 dark:hover:bg-blue-900/30"
            >
              <Edit3 className="w-3 h-3" />
              {configured ? t('ui:PlatformAdminPage.update') : t('ui:PlatformAdminPage.configure')}
            </button>
            {configured && (
              <>
                <button
                  onClick={handleTest}
                  disabled={testing}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md bg-purple-50 text-purple-700 hover:bg-purple-100 dark:bg-purple-900/20 dark:text-purple-400 dark:hover:bg-purple-900/30 disabled:opacity-50"
                >
                  {testing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                 {t('ui:PlatformAdminPage.test')}
                </button>
                <button
                  onClick={() => { if (confirm(t('ui:PlatformAdminPage.removeAllV0Keys', { v0: INTEGRATION_LABELS[integration] || integration }))) removeMut.mutate() }}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md bg-red-50 text-red-700 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-400 dark:hover:bg-red-900/30 ml-auto"
                >
                  <Trash2 className="w-3 h-3" />
                 {t('ui:PlatformAdminPage.remove')}
                </button>
              </>
            )}
          </div>

          {/* Test result */}
          {testResult && (
            <div className={`mt-2 p-2 rounded text-xs ${
              testResult.status === 'healthy' || testResult.status === 'configured'
                ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                : testResult.status === 'error'
                ? 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
                : 'bg-yellow-50 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400'
            }`}>
              <span className="font-medium">{testResult.status === 'healthy' || testResult.status === 'configured' ? t('ui:PlatformAdminPage.connected') : testResult.status === 'error' ? t('ui:PlatformAdminPage.error') : t('ui:PlatformAdminPage.warning')}:</span>{' '}
              {testResult.message}
              {testResult.latency_ms !== undefined && (
                <span className="ml-2 opacity-75">({testResult.latency_ms}{t('ui:PlatformAdminPage.ms')}</span>
              )}
            </div>
          )}
        </>
      )}

      {/* Edit mode: input fields */}
      {editing && (
        <>
          <div className="space-y-3 mb-3">
            {fields.map(f => {
              const isSecret = isSecretField(f.name)
              const showing = showValues[f.name] ?? false
              return (
                <div key={f.name}>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1 font-mono">
                    {f.name}
                  </label>
                  <div className="relative">
                    <input
                      type={isSecret && !showing ? 'password' : 'text'}
                      value={values[f.name] || ''}
                      onChange={e => setValues(prev => ({ ...prev, [f.name]: e.target.value }))}
                      placeholder={f.configured ? t('ui:PlatformAdminPage.leaveUnchangedOrPasteNew') : t('ui:PlatformAdminPage.pasteValueHere')}
                      className="w-full px-3 py-1.5 text-xs font-mono rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 pr-8"
                    />
                    {isSecret && (
                      <button
                        type="button"
                        onClick={() => setShowValues(prev => ({ ...prev, [f.name]: !showing }))}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        {showing ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          <div className="flex items-center gap-2 pt-2 border-t border-gray-100 dark:border-gray-700">
            <button
              onClick={() => saveMut.mutate()}
              disabled={saveMut.isPending || !hasChanges}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saveMut.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
             {t('ui:PlatformAdminPage.save')}
            </button>
            <button
              onClick={() => { setEditing(false); setValues({}) }}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
            >
             {t('ui:PlatformAdminPage.cancel')}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function ApiKeysTab() {
  const { t } = useTranslation('ui')
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['platform-admin', 'api-keys'],
    queryFn: () => platformAdminApi.listApiKeys(),
  })

  const keys = (data as any)?.data ?? []
  if (isLoading) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.apiKeysIntegrations')}</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
         {t('ui:PlatformAdminPage.manageApiKeysForAll')}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {keys.map((k: any) => (
          <ApiKeyCard
            key={k.integration}
            integration={k.integration}
            fields={k.fields}
            configured={k.configured}
            onSaved={() => qc.invalidateQueries({ queryKey: ['platform-admin', 'api-keys'] })}
          />
        ))}
      </div>
    </div>
  )
}

// ── Health tab ───────────────────────────────────────────────────────────

function HealthTab() {
  const { t } = useTranslation('ui')
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['platform-admin', 'health'],
    queryFn: () => platformAdminApi.getHealth(),
    refetchInterval: 30000,
  })

  const health = (data as any)?.data
  if (isLoading) return <LoadingSpinner />

  const statusColor = (s: string) => {
    if (s === 'healthy') return 'text-green-600 dark:text-green-400'
    if (s === 'degraded') return 'text-yellow-600 dark:text-yellow-400'
    return 'text-red-600 dark:text-red-400'
  }

  const statusBg = (s: string) => {
    if (s === 'healthy') return 'bg-green-100 dark:bg-green-900/30'
    if (s === 'degraded') return 'bg-yellow-100 dark:bg-yellow-900/30'
    return 'bg-red-100 dark:bg-red-900/30'
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.systemHealth')}</h1>
        <button onClick={() => refetch()} className="flex items-center gap-1 px-3 py-1.5 rounded-md text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600">
          <RefreshCw className="w-3.5 h-3.5" /> {t('ui:PlatformAdminPage.refresh')}
        </button>
      </div>

      {/* Overall status */}
      <div className={`rounded-lg border p-6 text-center ${statusBg(health?.status)}`}>
        <HeartPulse className={`w-8 h-8 mx-auto mb-2 ${statusColor(health?.status)}`} />
        <p className={`text-lg font-semibold capitalize ${statusColor(health?.status)}`}>{health?.status}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{t('ui:PlatformAdminPage.uptime')} {formatUptime(health?.uptime_seconds ?? 0)}</p>
      </div>

      {/* Core services */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">{t('ui:PlatformAdminPage.database')}</p>
          <p className={`text-sm font-medium capitalize ${statusColor(health?.database)}`}>{health?.database}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">{t('ui:PlatformAdminPage.errors24h')}</p>
          <p className={`text-sm font-medium ${(health?.error_count_24h ?? 0) > 0 ? 'text-red-600' : 'text-green-600'}`}>{health?.error_count_24h ?? 0}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">{t('ui:PlatformAdminPage.warnings24h')}</p>
          <p className={`text-sm font-medium ${(health?.warning_count_24h ?? 0) > 0 ? 'text-yellow-600' : 'text-green-600'}`}>{health?.warning_count_24h ?? 0}</p>
        </div>
      </div>

      {/* Integrations */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.integrationStatus')}</h3>
        </div>
        <div className="divide-y divide-gray-200 dark:divide-gray-700">
          {(health?.integrations ?? []).map((intg: any) => (
            <div key={intg.name} className="flex items-center justify-between px-4 py-3">
              <span className="text-sm text-gray-900 dark:text-white">{intg.name}</span>
              <span className={`inline-flex items-center gap-1 text-xs font-medium capitalize ${statusColor(intg.status)}`}>
                {intg.status === 'healthy' ? <CheckCircle className="w-3 h-3" /> : intg.status === 'unconfigured' ? <XCircle className="w-3 h-3 text-gray-400" /> : <AlertTriangle className="w-3 h-3" />}
                {intg.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Security tab ────────────────────────────────────────────────────────

function SecurityTab() {
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [activityPage, setActivityPage] = useState(1)

  const { data: sessionsData, isLoading: sessionsLoading } = useQuery({
    queryKey: ['platform-admin', 'sessions'],
    queryFn: () => platformAdminApi.listSessions(),
  })

  const { data: activityData, isLoading: activityLoading } = useQuery({
    queryKey: ['platform-admin', 'activity', activityPage],
    queryFn: () => platformAdminApi.getActivityLog({ page: activityPage, page_size: 30 }),
  })

  const revokeMut = useMutation({
    mutationFn: (sessionId: string) => platformAdminApi.revokeSession(sessionId),
    onSuccess: () => {
      toast.success(t('ui:PlatformAdminPage.sessionRevoked'))
      queryClient.invalidateQueries({ queryKey: ['platform-admin', 'sessions'] })
    },
  })

  const sessions = (sessionsData as any)?.data ?? []
  const activities = (activityData as any)?.data ?? []
  const activityMeta = (activityData as any)?.meta

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.security')}</h1>

      {/* Active sessions */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.activeSessions')}{sessions.length})</h3>
        </div>
        {sessionsLoading ? (
          <LoadingSpinner />
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-64 overflow-y-auto">
            {sessions.map((s: any) => (
              <div key={s.id} className="flex items-center justify-between px-4 py-2.5">
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">{s.user_name}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{s.user_email}</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="text-xs text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.created_2')} {timeAgo(s.created_at)}</p>
                    <p className="text-xs text-gray-400">{t('ui:PlatformAdminPage.expires')} {s.expires_at ? new Date(s.expires_at).toLocaleDateString() : '-'}</p>
                  </div>
                  <button
                    onClick={() => revokeMut.mutate(s.id)}
                    className="p-1 rounded text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                    title={t('ui:PlatformAdminPage.revokeSession')}
                  >
                    <XCircle className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
            {sessions.length === 0 && (
              <p className="px-4 py-3 text-sm text-gray-400">{t('ui:PlatformAdminPage.noActiveSessions')}</p>
            )}
          </div>
        )}
      </div>

      {/* Audit log */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">
           {t('ui:PlatformAdminPage.auditLog')} {activityMeta?.total ? `(${activityMeta.total})` : ''}
          </h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActivityPage((p) => Math.max(1, p - 1))}
              disabled={activityPage <= 1}
              className="px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 disabled:opacity-50"
            >
             {t('ui:PlatformAdminPage.prev')}
            </button>
            <span className="text-xs text-gray-500">{t('ui:PlatformAdminPage.page')} {activityPage}</span>
            <button
              onClick={() => setActivityPage((p) => p + 1)}
              disabled={activities.length < 30}
              className="px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 disabled:opacity-50"
            >
             {t('ui:PlatformAdminPage.next')}
            </button>
          </div>
        </div>
        {activityLoading ? (
          <LoadingSpinner />
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-96 overflow-y-auto">
            {activities.map((a: any) => (
              <div key={a.id} className="flex items-center gap-3 px-4 py-2 text-sm">
                <Clock className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                <span className="font-medium text-gray-700 dark:text-gray-300 truncate w-32">{a.user_name}</span>
                <span className="text-gray-500 dark:text-gray-400 font-mono text-xs">{a.action}</span>
                <span className="text-gray-400 text-xs">{a.resource_type}</span>
                <span className="ml-auto text-xs text-gray-400 shrink-0">{timeAgo(a.created_at)}</span>
              </div>
            ))}
            {activities.length === 0 && (
              <p className="px-4 py-3 text-sm text-gray-400">{t('ui:PlatformAdminPage.noActivityRecords')}</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Errors tab ──────────────────────────────────────────────────────────

function ErrorsTab() {
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [resolvedFilter, setResolvedFilter] = useState<'unresolved' | 'resolved' | 'all'>('unresolved')
  const [endpointFilter, setEndpointFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(1)

  const filterParams = {
    resolved: resolvedFilter === 'all' ? undefined : resolvedFilter === 'resolved',
    endpoint: endpointFilter || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    page,
    page_size: 50,
  }

  const { data, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['platform-admin', 'errors', filterParams],
    queryFn: () => platformAdminApi.listErrors(filterParams),
    refetchInterval: 30_000,
  })

  const resolveMut = useMutation({
    mutationFn: (errorId: string) => platformAdminApi.resolveError(errorId),
    onSuccess: () => {
      toast.success(t('ui:PlatformAdminPage.errorResolved'))
      queryClient.invalidateQueries({ queryKey: ['platform-admin', 'errors'] })
    },
  })

  const errors = (data as any)?.data ?? []
  const meta = (data as any)?.meta
  const totalPages = meta ? Math.ceil(meta.total / meta.page_size) : 1

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{t('ui:PlatformAdminPage.errorLog')}</h1>
          {meta && (
            <span className="text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full">
              {meta.total} total
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <RefreshCw className="w-3 h-3" />
         {t('ui:PlatformAdminPage.autoRefresh30s')}
          {dataUpdatedAt > 0 && (
            <span>{t('ui:PlatformAdminPage.last')} {timeAgo(new Date(dataUpdatedAt).toISOString())}</span>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-4">
        <div className="flex gap-1">
          {(['unresolved', 'resolved', 'all'] as const).map(v => (
            <button
              key={v}
              onClick={() => { setResolvedFilter(v); setPage(1) }}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg capitalize ${
                resolvedFilter === v
                  ? v === 'unresolved' ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                    : v === 'resolved' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100'
                  : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              {v}
            </button>
          ))}
        </div>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
          <input
            type="text"
            value={endpointFilter}
            onChange={(e) => { setEndpointFilter(e.target.value); setPage(1) }}
            placeholder={t('ui:PlatformAdminPage.filterByEndpoint')}
            className="pl-8 pr-3 py-1.5 text-xs border dark:border-gray-600 rounded-lg dark:bg-gray-900 dark:text-gray-100 w-48"
          />
        </div>
        <div className="flex items-center gap-1.5">
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1) }}
            className="px-2 py-1.5 text-xs border dark:border-gray-600 rounded-lg dark:bg-gray-900 dark:text-gray-100"
          />
          <span className="text-xs text-gray-400">to</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1) }}
            className="px-2 py-1.5 text-xs border dark:border-gray-600 rounded-lg dark:bg-gray-900 dark:text-gray-100"
          />
        </div>
        {(endpointFilter || dateFrom || dateTo || resolvedFilter !== 'unresolved') && (
          <button
            onClick={() => { setEndpointFilter(''); setDateFrom(''); setDateTo(''); setResolvedFilter('unresolved'); setPage(1) }}
            className="px-2.5 py-1.5 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
          >
           {t('ui:PlatformAdminPage.clearFilters')}
          </button>
        )}
      </div>

      {/* Error list */}
      {isLoading ? (
        <LoadingSpinner />
      ) : errors.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
          <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-500" />
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('ui:PlatformAdminPage.noErrorsFound')}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {errors.map((err: any) => (
            <div key={err.id} className={`bg-white dark:bg-gray-800 rounded-lg border p-4 ${
              err.resolved
                ? 'border-gray-200 dark:border-gray-700 opacity-60'
                : err.level === 'error'
                  ? 'border-red-200 dark:border-red-900/50'
                  : err.level === 'warning'
                    ? 'border-yellow-200 dark:border-yellow-900/50'
                    : 'border-blue-200 dark:border-blue-900/50'
            }`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                      err.level === 'error'
                        ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                        : err.level === 'warning'
                          ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                          : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                    }`}>
                      {err.level}
                    </span>
                    <span className="text-xs font-mono text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20 px-1.5 py-0.5 rounded">
                      {err.source}
                    </span>
                    {err.request_method && (
                      <span className="text-xs font-mono text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded">
                        {err.request_method} {err.request_path}
                      </span>
                    )}
                    {err.user_id && (
                      <span className="text-[10px] text-gray-400" title={err.user_id}>
                       {t('ui:PlatformAdminPage.user_2')} {err.user_id.slice(0, 8)}...
                      </span>
                    )}
                    {err.resolved && (
                      <span className="text-[10px] font-medium text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 px-1.5 py-0.5 rounded">
                       {t('ui:PlatformAdminPage.resolved')}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-900 dark:text-white break-words font-medium">{err.message}</p>
                  {err.traceback && (
                    <details className="mt-2">
                      <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300 select-none">
                       {t('ui:PlatformAdminPage.traceback')}{err.traceback.split('\n').length} {t('ui:PlatformAdminPage.lines')}
                      </summary>
                      <pre className="mt-1 text-[11px] leading-relaxed text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 p-3 rounded overflow-x-auto max-h-60 whitespace-pre-wrap break-words">
                        {err.traceback}
                      </pre>
                    </details>
                  )}
                  <p className="text-xs text-gray-400 mt-1.5">
                    <Clock className="inline w-3 h-3 mr-0.5 -mt-0.5" />
                    {timeAgo(err.created_at)}
                    {' · '}
                    {new Date(err.created_at).toLocaleString()}
                  </p>
                </div>
                {!err.resolved && (
                  <button
                    onClick={() => resolveMut.mutate(err.id)}
                    disabled={resolveMut.isPending}
                    className="px-3 py-1.5 text-xs font-medium text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg hover:bg-green-100 dark:hover:bg-green-900/40 shrink-0"
                    title={t('ui:PlatformAdminPage.markAsResolved')}
                  >
                   {t('ui:PlatformAdminPage.resolve')}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1 text-xs border dark:border-gray-600 rounded-lg disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
          >
           {t('ui:PlatformAdminPage.prev')}
          </button>
          <span className="text-xs text-gray-500 dark:text-gray-400">
           {t('ui:PlatformAdminPage.page')} {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="px-3 py-1 text-xs border dark:border-gray-600 rounded-lg disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
          >
           {t('ui:PlatformAdminPage.next')}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <RefreshCw className="w-5 h-5 text-gray-400 animate-spin" />
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diff = Math.floor((now.getTime() - d.getTime()) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`
  return d.toLocaleDateString()
}
