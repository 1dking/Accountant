import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Plus, ListTree, Loader2, Check, X, Pencil, Sparkles, Lock } from 'lucide-react'
import {
  listChartAccounts,
  createChartAccount,
  updateChartAccount,
  deactivateChartAccount,
  seedChartOfAccounts,
  type ChartAccount,
  type ChartAccountInput,
  type CoaAccountType,
} from '@/api/accounting'

const ACCOUNT_TYPES: { value: CoaAccountType; label: string; plural: string; normal: 'debit' | 'credit'; color: string }[] = [
  { value: 'asset', label: 'Asset', plural: 'Assets', normal: 'debit', color: 'text-blue-600 dark:text-blue-400' },
  { value: 'liability', label: 'Liability', plural: 'Liabilities', normal: 'credit', color: 'text-amber-600 dark:text-amber-400' },
  { value: 'equity', label: 'Equity', plural: 'Equity', normal: 'credit', color: 'text-purple-600 dark:text-purple-400' },
  { value: 'income', label: 'Income', plural: 'Income', normal: 'credit', color: 'text-green-600 dark:text-green-400' },
  { value: 'expense', label: 'Expense', plural: 'Expenses', normal: 'debit', color: 'text-red-600 dark:text-red-400' },
]

const TYPE_ORDER: CoaAccountType[] = ['asset', 'liability', 'equity', 'income', 'expense']

export default function ChartOfAccountsPage() {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<ChartAccount | null>(null)
  const [creating, setCreating] = useState(false)
  const [includeInactive, setIncludeInactive] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['coa-accounts', includeInactive],
    queryFn: () => listChartAccounts({ include_inactive: includeInactive }),
  })
  const accounts: ChartAccount[] = data?.data ?? []

  const seedMutation = useMutation({
    mutationFn: () => seedChartOfAccounts(true),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['coa-accounts'] })
      const d = res.data
      if (d.already_seeded && d.accounts_created === 0) {
        toast.success('Chart of Accounts is already set up')
      } else {
        toast.success(
          `Set up ${d.accounts_created} accounts` +
            (d.payment_accounts_mapped ? `, linked ${d.payment_accounts_mapped} bank accounts` : '') +
            (d.categories_mapped ? `, mapped ${d.categories_mapped} categories` : ''),
        )
      }
    },
    onError: (err: any) => toast.error(err?.message || 'Failed to set up Chart of Accounts'),
  })

  const grouped = TYPE_ORDER.map((t) => ({
    type: t,
    meta: ACCOUNT_TYPES.find((a) => a.value === t)!,
    rows: accounts.filter((a) => a.account_type === t),
  })).filter((g) => g.rows.length > 0)

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <ListTree className="w-6 h-6 text-gray-700 dark:text-gray-300" />
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Chart of Accounts</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            The numbered accounts every journal entry, bill, and report posts to. Assets and expenses
            carry a debit balance; liabilities, equity, and income carry a credit balance.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {accounts.length === 0 && (
            <button
              onClick={() => seedMutation.mutate()}
              disabled={seedMutation.isPending}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {seedMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              Set up standard chart
            </button>
          )}
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-1.5 px-4 py-2 text-sm border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <Plus className="w-4 h-4" />
            New account
          </button>
        </div>
      </div>

      <label className="inline-flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
        <input
          type="checkbox"
          checked={includeInactive}
          onChange={(e) => setIncludeInactive(e.target.checked)}
          className="rounded border-gray-300"
        />
        Show deactivated accounts
      </label>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      ) : accounts.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-gray-200 dark:border-gray-700 rounded-xl">
          <ListTree className="w-10 h-10 mx-auto text-gray-300 dark:text-gray-600" />
          <p className="mt-3 text-gray-600 dark:text-gray-300 font-medium">No accounts yet</p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Set up the standard chart to get numbered accounts and link your existing bank accounts and
            categories automatically.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {grouped.map((g) => (
            <div key={g.type}>
              <div className="flex items-center justify-between mb-2">
                <h2 className={`text-sm font-semibold uppercase tracking-wide ${g.meta.color}`}>
                  {g.meta.plural}
                </h2>
                <span className="text-xs text-gray-400">normal balance: {g.meta.normal}</span>
              </div>
              <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
                {g.rows.map((a) => (
                  <div
                    key={a.id}
                    className={`flex items-center gap-3 px-4 py-2.5 border-b last:border-b-0 border-gray-100 dark:border-gray-800 ${
                      a.is_active ? '' : 'opacity-50'
                    }`}
                  >
                    <span className="font-mono text-sm text-gray-500 dark:text-gray-400 w-16 shrink-0">{a.code}</span>
                    <span className="text-sm text-gray-900 dark:text-gray-100 flex-1 truncate">{a.name}</span>
                    {a.is_system && (
                      <span className="inline-flex items-center gap-1 text-[11px] text-gray-400" title="System account">
                        <Lock className="w-3 h-3" /> system
                      </span>
                    )}
                    {!a.is_active && <span className="text-[11px] text-gray-400">inactive</span>}
                    <button
                      onClick={() => setEditing(a)}
                      className="p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"
                      title="Edit"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {(creating || editing) && (
        <AccountModal
          account={editing}
          onClose={() => {
            setCreating(false)
            setEditing(null)
          }}
        />
      )}
    </div>
  )
}

function AccountModal({ account, onClose }: { account: ChartAccount | null; onClose: () => void }) {
  const queryClient = useQueryClient()
  const isEdit = account !== null
  const [code, setCode] = useState(account?.code ?? '')
  const [name, setName] = useState(account?.name ?? '')
  const [accountType, setAccountType] = useState<CoaAccountType>(account?.account_type ?? 'expense')
  const [description, setDescription] = useState(account?.description ?? '')
  const [isActive, setIsActive] = useState(account?.is_active ?? true)

  const mutation = useMutation({
    mutationFn: () => {
      if (isEdit) {
        const patch: Partial<ChartAccountInput> = {}
        if (code !== account!.code) patch.code = code
        if (name !== account!.name) patch.name = name
        if ((description || '') !== (account!.description || '')) patch.description = description || null
        if (isActive !== account!.is_active) patch.is_active = isActive
        return updateChartAccount(account!.id, patch)
      }
      const body: ChartAccountInput = { code, name, account_type: accountType, description: description || null }
      return createChartAccount(body)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['coa-accounts'] })
      toast.success(isEdit ? 'Account updated' : 'Account created')
      onClose()
    },
    onError: (err: any) => toast.error(err?.message || 'Failed to save account'),
  })

  const deactivate = useMutation({
    mutationFn: () => deactivateChartAccount(account!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['coa-accounts'] })
      toast.success('Account deactivated')
      onClose()
    },
    onError: (err: any) => toast.error(err?.message || 'Failed to deactivate'),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-md mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {isEdit ? 'Edit Account' : 'New Account'}
          </h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Code</label>
              <input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                disabled={isEdit && account!.is_system}
                placeholder="6300"
                className="w-full px-3 py-2 border rounded-lg text-sm font-mono disabled:opacity-50 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Office Supplies"
                className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Type</label>
            <select
              value={accountType}
              onChange={(e) => setAccountType(e.target.value as CoaAccountType)}
              disabled={isEdit}
              className="w-full px-3 py-2 border rounded-lg text-sm disabled:opacity-50 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            >
              {ACCOUNT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label} (normal balance: {t.normal})
                </option>
              ))}
            </select>
            {isEdit && (
              <p className="text-xs text-gray-400 mt-1">
                Type can't change once an account exists — it would flip the account's normal balance.
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            />
          </div>

          {isEdit && (
            <label className="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="rounded border-gray-300"
              />
              Active
            </label>
          )}
        </div>

        <div className="flex justify-between gap-2 p-4 border-t dark:border-gray-700">
          <div>
            {isEdit && account!.is_active && (
              <button
                onClick={() => deactivate.mutate()}
                disabled={deactivate.isPending}
                className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-950 rounded-lg disabled:opacity-50"
              >
                Deactivate
              </button>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
            >
              Cancel
            </button>
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || !code.trim() || !name.trim()}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              {isEdit ? 'Save' : 'Create'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
