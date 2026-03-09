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
} from 'lucide-react'

// ── Tab definitions ──────────────────────────────────────────────────────

const TABS = [
  { key: 'overview', label: 'Overview', icon: LayoutDashboard },
  { key: 'organizations', label: 'Organizations', icon: Building2 },
  { key: 'users', label: 'Users', icon: Users },
  { key: 'features', label: 'Feature Toggles', icon: ToggleLeft },
  { key: 'pricing', label: 'Pricing & Limits', icon: DollarSign },
  { key: 'apikeys', label: 'API Keys', icon: Key },
  { key: 'health', label: 'Health', icon: HeartPulse },
  { key: 'security', label: 'Security', icon: Shield },
  { key: 'errors', label: 'Errors', icon: AlertTriangle },
] as const

type TabKey = (typeof TABS)[number]['key']

// ── Main page ────────────────────────────────────────────────────────────

export default function PlatformAdminPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const user = useAuthStore((s) => s.user)

  if (user?.role !== 'admin') {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500 dark:text-gray-400">You do not have access to this page.</p>
      </div>
    )
  }

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-56 shrink-0 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 overflow-y-auto">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Platform Admin</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">System management</p>
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
        {activeTab === 'health' && <HealthTab />}
        {activeTab === 'security' && <SecurityTab />}
        {activeTab === 'errors' && <ErrorsTab />}
      </div>
    </div>
  )
}

// ── Overview tab ─────────────────────────────────────────────────────────

function OverviewTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['platform-admin', 'dashboard'],
    queryFn: () => platformAdminApi.getDashboard(),
  })

  const metrics = (data as any)?.data
  if (isLoading) return <LoadingSpinner />

  const cards = [
    { label: 'Total Users', value: metrics?.total_users ?? 0, sub: `${metrics?.active_users ?? 0} active`, icon: Users, color: 'blue' },
    { label: 'Pages', value: metrics?.total_pages ?? 0, sub: `${metrics?.published_pages ?? 0} published`, icon: Globe, color: 'purple' },
    { label: 'Documents', value: metrics?.total_documents ?? 0, sub: formatBytes(metrics?.storage_used_bytes ?? 0), icon: FileText, color: 'green' },
    { label: 'Invoices', value: metrics?.total_invoices ?? 0, sub: `$${(metrics?.total_revenue ?? 0).toLocaleString()}`, icon: DollarSign, color: 'amber' },
    { label: 'Contacts', value: metrics?.total_contacts ?? 0, icon: Users, color: 'cyan' },
    { label: 'Proposals', value: metrics?.total_proposals ?? 0, icon: FileText, color: 'indigo' },
    { label: 'Expenses', value: `$${(metrics?.total_expenses ?? 0).toLocaleString()}`, icon: DollarSign, color: 'red' },
    { label: 'Meetings', value: metrics?.total_meetings ?? 0, icon: Activity, color: 'emerald' },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Dashboard Overview</h1>

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
          <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Users by Role</h3>
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
          <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Activity (Last 30 Days)</h3>
          <div className="flex items-end gap-1 h-24">
            {(() => {
              const maxCount = Math.max(...metrics.activity_by_day.map((d: any) => d.count), 1)
              return metrics.activity_by_day.map((day: any, i: number) => (
                <div
                  key={i}
                  className="flex-1 bg-blue-500 dark:bg-blue-400 rounded-t opacity-80 hover:opacity-100 transition-opacity"
                  style={{ height: `${Math.max((day.count / maxCount) * 100, 2)}%` }}
                  title={`${day.date}: ${day.count} actions`}
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
        <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Recent Activity</h3>
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
            <p className="text-sm text-gray-400">No recent activity</p>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Organizations tab ─────────────────────────────────────────────────────

function OrganizationsTab() {
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
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Organizations</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium bg-blue-600 text-white hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" /> Create Organization
        </button>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search organizations..."
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
          <option value="">All Plans</option>
          <option value="starter">Starter</option>
          <option value="pro">Pro</option>
          <option value="business">Business</option>
          <option value="enterprise">Enterprise</option>
        </select>
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : orgs.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
          <Building2 className="w-8 h-8 mx-auto mb-2 text-gray-400" />
          <p className="text-sm text-gray-500 dark:text-gray-400">No organizations yet</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Organization</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Plan</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Members</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Owner</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Created</th>
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
                        <CheckCircle className="w-3 h-3" /> Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-red-500 text-xs">
                        <XCircle className="w-3 h-3" /> Inactive
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
      toast.success('Organization created')
      onCreated()
    },
    onError: (err: any) => toast.error(err?.message || 'Failed to create organization'),
  })

  const autoSlug = (n: string) => n.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Create Organization</h2>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name <span className="text-red-500">*</span></label>
            <input
              type="text"
              value={name}
              onChange={(e) => { setName(e.target.value); if (!slug || slug === autoSlug(name)) setSlug(autoSlug(e.target.value)) }}
              className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white"
              placeholder="Acme Corp"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Slug <span className="text-red-500">*</span></label>
            <input
              type="text"
              value={slug}
              onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
              className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white font-mono"
              placeholder="acme-corp"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Owner <span className="text-red-500">*</span></label>
            <select
              value={ownerId}
              onChange={(e) => setOwnerId(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white"
            >
              <option value="">Select owner...</option>
              {allUsers.map((u: any) => (
                <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Plan</label>
              <select
                value={plan}
                onChange={(e) => setPlan(e.target.value)}
                className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white"
              >
                <option value="starter">Starter</option>
                <option value="pro">Pro</option>
                <option value="business">Business</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Max Users</label>
              <input type="number" value={maxUsers} onChange={(e) => setMaxUsers(Number(e.target.value))} min={1}
                className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Storage (GB)</label>
              <input type="number" value={maxStorage} onChange={(e) => setMaxStorage(Number(e.target.value))} min={1}
                className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-4 py-2 rounded-md text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">Cancel</button>
          <button
            onClick={() => createMut.mutate()}
            disabled={!name || !slug || !ownerId || createMut.isPending}
            className="px-4 py-2 rounded-md text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {createMut.isPending ? 'Creating...' : 'Create'}
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
  const queryClient = useQueryClient()
  const [editMode, setEditMode] = useState(false)
  const [editData, setEditData] = useState<any>({})
  const [showAddMember, setShowAddMember] = useState(false)
  const [addUserId, setAddUserId] = useState('')

  const invalidateOrg = () => queryClient.invalidateQueries({ queryKey: ['platform-admin', 'org-detail', org.id] })

  // Update org
  const updateMut = useMutation({
    mutationFn: (data: any) => platformAdminApi.updateOrganization(org.id, data),
    onSuccess: () => { toast.success('Organization updated'); setEditMode(false); invalidateOrg() },
    onError: (err: any) => toast.error(err?.message || 'Update failed'),
  })

  // Delete org
  const deleteMut = useMutation({
    mutationFn: () => platformAdminApi.deleteOrganization(org.id),
    onSuccess: () => { toast.success('Organization deleted'); onBack() },
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
    onSuccess: () => { toast.success('Member added'); setShowAddMember(false); setAddUserId(''); invalidateOrg() },
  })

  const removeMemberMut = useMutation({
    mutationFn: (userId: string) => platformAdminApi.removeOrgMember(org.id, userId),
    onSuccess: () => { toast.success('Member removed'); invalidateOrg() },
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
            <Edit3 className="w-3.5 h-3.5" /> Edit
          </button>
          <button
            onClick={() => { if (confirm('Delete this organization? Members will be unlinked.')) deleteMut.mutate() }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm border border-red-300 dark:border-red-600 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
          >
            <Trash2 className="w-3.5 h-3.5" /> Delete
          </button>
        </div>
      </div>

      {/* Edit form */}
      {editMode && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-blue-200 dark:border-blue-800 p-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">Edit Organization</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Name</label>
              <input type="text" value={editData.name ?? ''} onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Slug</label>
              <input type="text" value={editData.slug ?? ''} onChange={(e) => setEditData({ ...editData, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white font-mono" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Plan</label>
              <select value={editData.plan ?? 'starter'} onChange={(e) => setEditData({ ...editData, plan: e.target.value })}
                className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white">
                <option value="starter">Starter</option>
                <option value="pro">Pro</option>
                <option value="business">Business</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Active</label>
              <select value={editData.is_active ? 'true' : 'false'} onChange={(e) => setEditData({ ...editData, is_active: e.target.value === 'true' })}
                className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white">
                <option value="true">Active</option>
                <option value="false">Inactive</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Max Users</label>
              <input type="number" min={1} value={editData.max_users ?? 5} onChange={(e) => setEditData({ ...editData, max_users: Number(e.target.value) })}
                className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Max Storage (GB)</label>
              <input type="number" min={1} value={editData.max_storage_gb ?? 5} onChange={(e) => setEditData({ ...editData, max_storage_gb: Number(e.target.value) })}
                className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" />
            </div>
          </div>

          {/* White-label */}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-3 mt-3">
            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2 flex items-center gap-1"><Palette className="w-3.5 h-3.5" /> White-label</h4>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Logo URL</label>
                <input type="text" value={editData.logo_url ?? ''} onChange={(e) => setEditData({ ...editData, logo_url: e.target.value })}
                  className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" placeholder="https://..." />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Custom Domain</label>
                <input type="text" value={editData.custom_domain ?? ''} onChange={(e) => setEditData({ ...editData, custom_domain: e.target.value })}
                  className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" placeholder="app.example.com" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Primary Color</label>
                <div className="flex items-center gap-2">
                  <input type="color" value={editData.primary_color || '#3b82f6'} onChange={(e) => setEditData({ ...editData, primary_color: e.target.value })}
                    className="w-8 h-8 rounded border border-gray-300 dark:border-gray-600 cursor-pointer" />
                  <input type="text" value={editData.primary_color ?? ''} onChange={(e) => setEditData({ ...editData, primary_color: e.target.value })}
                    className="flex-1 px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white font-mono" placeholder="#3b82f6" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Secondary Color</label>
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
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Notes</label>
            <textarea value={editData.notes ?? ''} onChange={(e) => setEditData({ ...editData, notes: e.target.value })} rows={2}
              className="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white" />
          </div>

          <div className="flex justify-end gap-2">
            <button onClick={() => setEditMode(false)} className="px-3 py-1.5 rounded text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">Cancel</button>
            <button onClick={() => updateMut.mutate(editData)} disabled={updateMut.isPending}
              className="flex items-center gap-1 px-3 py-1.5 rounded text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
              <Save className="w-3.5 h-3.5" /> Save
            </button>
          </div>
        </div>
      )}

      {/* Info cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">Plan</p>
          <p className="text-lg font-bold text-gray-900 dark:text-white capitalize">{org.plan}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">Members</p>
          <p className="text-lg font-bold text-gray-900 dark:text-white">{org.member_count} / {org.max_users}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">Storage Limit</p>
          <p className="text-lg font-bold text-gray-900 dark:text-white">{org.max_storage_gb} GB</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">Status</p>
          <p className={`text-lg font-bold ${org.is_active ? 'text-green-600' : 'text-red-500'}`}>{org.is_active ? 'Active' : 'Inactive'}</p>
        </div>
      </div>

      {/* Members */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">Members ({org.members?.length ?? 0})</h3>
          <button onClick={() => setShowAddMember(!showAddMember)}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-blue-600 text-white hover:bg-blue-700">
            <UserPlus className="w-3 h-3" /> Add
          </button>
        </div>
        {showAddMember && (
          <div className="px-4 py-2 bg-blue-50 dark:bg-blue-900/20 border-b border-blue-200 dark:border-blue-800 flex items-center gap-2">
            <select value={addUserId} onChange={(e) => setAddUserId(e.target.value)}
              className="flex-1 px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white">
              <option value="">Select user...</option>
              {nonMembers.map((u: any) => <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>)}
            </select>
            <button onClick={() => addUserId && addMemberMut.mutate(addUserId)} disabled={!addUserId || addMemberMut.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">Add</button>
            <button onClick={() => { setShowAddMember(false); setAddUserId('') }}
              className="px-2 py-1.5 rounded text-xs text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700">Cancel</button>
          </div>
        )}
        <div className="divide-y divide-gray-200 dark:divide-gray-700">
          {(org.members ?? []).map((m: any) => (
            <div key={m.id} className="flex items-center justify-between px-4 py-2.5">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">{m.full_name}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">{m.email} &middot; <span className="capitalize">{m.role?.replace('_', ' ')}</span></p>
              </div>
              <button onClick={() => { if (confirm(`Remove ${m.full_name}?`)) removeMemberMut.mutate(m.id) }}
                className="p-1 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20" title="Remove member">
                <UserMinus className="w-4 h-4" />
              </button>
            </div>
          ))}
          {(!org.members || org.members.length === 0) && (
            <p className="px-4 py-3 text-sm text-gray-400">No members</p>
          )}
        </div>
      </div>

      {/* Feature Overrides */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">Feature Overrides</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400">Override global feature flags for this org. Unset = uses global default.</p>
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
                      <p className="text-[10px] text-gray-400 font-mono">{flag.key} {hasOverride ? '(overridden)' : '(global)'}</p>
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
                          className="p-0.5 rounded text-gray-400 hover:text-red-500" title="Reset to global">
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
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">Setting Overrides</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400">Override global pricing/limits for this org.</p>
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
                      <p className="text-[10px] text-gray-400 font-mono">{setting.key} {hasOverride ? '(overridden)' : '(global)'}</p>
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
                          className="p-0.5 rounded text-gray-400 hover:text-red-500" title="Reset to global">
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
          <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3 flex items-center gap-1.5"><Palette className="w-4 h-4" /> White-label Settings</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {org.logo_url && (
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Logo</p>
                <img src={org.logo_url} alt="Org logo" className="h-10 object-contain" />
              </div>
            )}
            {org.primary_color && (
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Primary Color</p>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded" style={{ backgroundColor: org.primary_color }} />
                  <span className="font-mono text-gray-700 dark:text-gray-300">{org.primary_color}</span>
                </div>
              </div>
            )}
            {org.secondary_color && (
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Secondary Color</p>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded" style={{ backgroundColor: org.secondary_color }} />
                  <span className="font-mono text-gray-700 dark:text-gray-300">{org.secondary_color}</span>
                </div>
              </div>
            )}
            {org.custom_domain && (
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Custom Domain</p>
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
            <p className="text-xs text-gray-500 dark:text-gray-400">Owner</p>
            <p className="text-gray-900 dark:text-white font-medium">{org.owner_name}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">{org.owner_email}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">Created</p>
            <p className="text-gray-900 dark:text-white">{org.created_at ? new Date(org.created_at).toLocaleDateString() : '-'}</p>
          </div>
          {org.notes && (
            <div className="col-span-2">
              <p className="text-xs text-gray-500 dark:text-gray-400">Notes</p>
              <p className="text-gray-700 dark:text-gray-300">{org.notes}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Users tab ────────────────────────────────────────────────────────────

function UsersTab() {
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
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
      toast.success('Impersonation active. Refresh to apply.')
      window.location.reload()
    },
  })

  const revokeSessionsMut = useMutation({
    mutationFn: (userId: string) => platformAdminApi.revokeUserSessions(userId),
    onSuccess: () => {
      toast.success('All sessions revoked')
      queryClient.invalidateQueries({ queryKey: ['platform-admin'] })
    },
  })

  const users = (data as any)?.data ?? []
  const detail = (userDetail as any)?.data

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Users Management</h1>

      <div className="flex gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search users..."
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
          <option value="">All Roles</option>
          <option value="admin">Admin</option>
          <option value="team_member">Team Member</option>
          <option value="accountant">Accountant</option>
          <option value="client">Client</option>
          <option value="viewer">Viewer</option>
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
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">User</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Role</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Last Login</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {users.map((u: any) => (
                  <tr
                    key={u.id}
                    className={`hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer ${selectedUserId === u.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''}`}
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
                          <CheckCircle className="w-3 h-3" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-red-500 text-xs">
                          <XCircle className="w-3 h-3" /> Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                      {u.last_login ? timeAgo(u.last_login) : 'Never'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={(e) => { e.stopPropagation(); impersonateMut.mutate(u.id) }}
                          title="Impersonate"
                          className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500 hover:text-blue-600"
                        >
                          <LogIn className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); revokeSessionsMut.mutate(u.id) }}
                          title="Revoke sessions"
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
            <h3 className="font-medium text-gray-900 dark:text-white">{detail.full_name}</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">{detail.email}</p>
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Role</span>
                <span className="text-gray-900 dark:text-white capitalize">{detail.role?.replace('_', ' ')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Auth</span>
                <span className="text-gray-900 dark:text-white">{detail.auth_provider}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Pages</span>
                <span className="text-gray-900 dark:text-white">{detail.page_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Documents</span>
                <span className="text-gray-900 dark:text-white">{detail.document_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Invoices</span>
                <span className="text-gray-900 dark:text-white">{detail.invoice_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Activities</span>
                <span className="text-gray-900 dark:text-white">{detail.activity_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Joined</span>
                <span className="text-gray-900 dark:text-white">{detail.created_at ? new Date(detail.created_at).toLocaleDateString() : '-'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Last Login</span>
                <span className="text-gray-900 dark:text-white">{detail.last_login ? timeAgo(detail.last_login) : 'Never'}</span>
              </div>
            </div>

            {detail.recent_activity?.length > 0 && (
              <div className="mt-4 border-t border-gray-200 dark:border-gray-700 pt-3">
                <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2">Recent Activity</h4>
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
    </div>
  )
}

// ── Feature toggles tab ─────────────────────────────────────────────────

function FeatureTogglesTab() {
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
      <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Feature Toggles</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400">Enable or disable features across the platform.</p>

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
      toast.success('Setting updated')
    },
  })

  const settings = (data as any)?.data ?? []
  const categories = [...new Set(settings.map((s: any) => s.category))] as string[]

  if (isLoading) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Pricing & Limits</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400">Manage plan pricing, usage limits, and add-on configuration.</p>

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

function ApiKeysTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['platform-admin', 'api-keys'],
    queryFn: () => platformAdminApi.listApiKeys(),
  })

  const keys = (data as any)?.data ?? []
  if (isLoading) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900 dark:text-white">API Keys & Integrations</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400">View the status of all configured API keys and integrations. Keys are managed via environment variables or the Integration Settings page.</p>

      <div className="grid gap-4 md:grid-cols-2">
        {keys.map((k: any) => (
          <div key={k.integration} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-900 dark:text-white capitalize">{k.integration.replace('_', ' ')}</h3>
              {k.configured ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                  <CheckCircle className="w-3 h-3" /> Configured
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400">
                  <AlertTriangle className="w-3 h-3" /> Not configured
                </span>
              )}
            </div>
            {k.masked_key && (
              <p className="text-xs font-mono text-gray-500 dark:text-gray-400 mb-2">{k.masked_key}</p>
            )}
            <div className="space-y-1">
              {(k.fields || []).map((f: any) => (
                <div key={f.name} className="flex items-center gap-2 text-xs">
                  {f.configured ? (
                    <CheckCircle className="w-3 h-3 text-green-500" />
                  ) : (
                    <XCircle className="w-3 h-3 text-gray-300 dark:text-gray-600" />
                  )}
                  <span className="font-mono text-gray-600 dark:text-gray-400">{f.name}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Health tab ───────────────────────────────────────────────────────────

function HealthTab() {
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
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">System Health</h1>
        <button onClick={() => refetch()} className="flex items-center gap-1 px-3 py-1.5 rounded-md text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Overall status */}
      <div className={`rounded-lg border p-6 text-center ${statusBg(health?.status)}`}>
        <HeartPulse className={`w-8 h-8 mx-auto mb-2 ${statusColor(health?.status)}`} />
        <p className={`text-lg font-semibold capitalize ${statusColor(health?.status)}`}>{health?.status}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Uptime: {formatUptime(health?.uptime_seconds ?? 0)}</p>
      </div>

      {/* Core services */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">Database</p>
          <p className={`text-sm font-medium capitalize ${statusColor(health?.database)}`}>{health?.database}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">Errors (24h)</p>
          <p className={`text-sm font-medium ${(health?.error_count_24h ?? 0) > 0 ? 'text-red-600' : 'text-green-600'}`}>{health?.error_count_24h ?? 0}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">Warnings (24h)</p>
          <p className={`text-sm font-medium ${(health?.warning_count_24h ?? 0) > 0 ? 'text-yellow-600' : 'text-green-600'}`}>{health?.warning_count_24h ?? 0}</p>
        </div>
      </div>

      {/* Integrations */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">Integration Status</h3>
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
      toast.success('Session revoked')
      queryClient.invalidateQueries({ queryKey: ['platform-admin', 'sessions'] })
    },
  })

  const sessions = (sessionsData as any)?.data ?? []
  const activities = (activityData as any)?.data ?? []
  const activityMeta = (activityData as any)?.meta

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Security</h1>

      {/* Active sessions */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">Active Sessions ({sessions.length})</h3>
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
                    <p className="text-xs text-gray-500 dark:text-gray-400">Created: {timeAgo(s.created_at)}</p>
                    <p className="text-xs text-gray-400">Expires: {s.expires_at ? new Date(s.expires_at).toLocaleDateString() : '-'}</p>
                  </div>
                  <button
                    onClick={() => revokeMut.mutate(s.id)}
                    className="p-1 rounded text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                    title="Revoke session"
                  >
                    <XCircle className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
            {sessions.length === 0 && (
              <p className="px-4 py-3 text-sm text-gray-400">No active sessions</p>
            )}
          </div>
        )}
      </div>

      {/* Audit log */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">
            Audit Log {activityMeta?.total ? `(${activityMeta.total})` : ''}
          </h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActivityPage((p) => Math.max(1, p - 1))}
              disabled={activityPage <= 1}
              className="px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 disabled:opacity-50"
            >
              Prev
            </button>
            <span className="text-xs text-gray-500">Page {activityPage}</span>
            <button
              onClick={() => setActivityPage((p) => p + 1)}
              disabled={activities.length < 30}
              className="px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 disabled:opacity-50"
            >
              Next
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
              <p className="px-4 py-3 text-sm text-gray-400">No activity records</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Errors tab ──────────────────────────────────────────────────────────

function ErrorsTab() {
  const queryClient = useQueryClient()
  const [showResolved, setShowResolved] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['platform-admin', 'errors', showResolved],
    queryFn: () => platformAdminApi.listErrors({ resolved: showResolved ? undefined : false }),
  })

  const resolveMut = useMutation({
    mutationFn: (errorId: string) => platformAdminApi.resolveError(errorId),
    onSuccess: () => {
      toast.success('Error resolved')
      queryClient.invalidateQueries({ queryKey: ['platform-admin', 'errors'] })
    },
  })

  const errors = (data as any)?.data ?? []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Error Log</h1>
        <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
          <input
            type="checkbox"
            checked={showResolved}
            onChange={(e) => setShowResolved(e.target.checked)}
            className="rounded"
          />
          Show resolved
        </label>
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : errors.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
          <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-500" />
          <p className="text-sm text-gray-500 dark:text-gray-400">No errors found</p>
        </div>
      ) : (
        <div className="space-y-2">
          {errors.map((err: any) => (
            <div key={err.id} className={`bg-white dark:bg-gray-800 rounded-lg border p-4 ${
              err.resolved
                ? 'border-gray-200 dark:border-gray-700 opacity-60'
                : err.level === 'error'
                  ? 'border-red-200 dark:border-red-900/50'
                  : 'border-yellow-200 dark:border-yellow-900/50'
            }`}>
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium uppercase ${
                      err.level === 'error'
                        ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                        : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                    }`}>
                      {err.level}
                    </span>
                    <span className="text-xs font-mono text-gray-500 dark:text-gray-400">{err.source}</span>
                    {err.request_method && (
                      <span className="text-xs text-gray-400">{err.request_method} {err.request_path}</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-900 dark:text-white break-words">{err.message}</p>
                  {err.traceback && (
                    <details className="mt-2">
                      <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">Traceback</summary>
                      <pre className="mt-1 text-xs text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 p-2 rounded overflow-x-auto max-h-40">{err.traceback}</pre>
                    </details>
                  )}
                  <p className="text-xs text-gray-400 mt-1">{timeAgo(err.created_at)}</p>
                </div>
                {!err.resolved && (
                  <button
                    onClick={() => resolveMut.mutate(err.id)}
                    className="ml-3 p-1.5 rounded text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 shrink-0"
                    title="Mark resolved"
                  >
                    <CheckCircle className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
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
