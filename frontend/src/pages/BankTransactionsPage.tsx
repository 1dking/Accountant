import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Landmark, RefreshCw, ArrowUpRight, ArrowDownRight, Check, Filter, Sparkles, ListChecks, AlertTriangle, BookOpen, Search, X, Scale } from 'lucide-react'
import {
  listPlaidConnections,
  listPlaidTransactions,
  categorizePlaidTransaction,
  bulkCategorizePlaidTransactions,
  syncPlaidTransactions,
  applyCategorizationRules,
  aiCategorizeTransactions,
  getPlaidPossibleDuplicates,
  getPlaidReconciliation,
} from '@/api/integrations'
import { listCategories } from '@/api/cashbook'
import { listPersonalCategories, type PersonalCategory } from '@/api/personal'
import { ApiClientError } from '@/api/client'
import { formatDate } from '@/lib/utils'
import type { PlaidTransaction, TransactionCategory } from '@/types/models'
import { useTranslation } from 'react-i18next'

const formatCurrency = (amount: number, currency = 'CAD') =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency }).format(amount)

type CashbookEntryType = 'income' | 'expense'

/** Shown when categorizing a Plaid txn returns 409 PLAID_POSSIBLE_DUPLICATE.
 *  Puts the bank transaction next to the matching manual entry so the user
 *  decides: same transaction (skip, post nothing) or a separate charge (add). */
export function DuplicateDialog({ txn, asType, currency = 'CAD', onSkip, onConfirm, confirming }: {
  txn: PlaidTransaction
  asType: 'expense' | 'income' | 'cashbook'
  currency?: string
  onSkip: () => void
  onConfirm: () => void
  confirming: boolean
}) {
  const { t } = useTranslation('ui')
  const { data, isLoading } = useQuery({
    queryKey: ['plaid-possible-duplicates', txn.id],
    queryFn: () => getPlaidPossibleDuplicates(txn.id),
  })
  const candidates = data?.data?.possible_duplicates ?? []
  const destinationLabel = asType === 'cashbook' ? 'cashbook entry' : asType

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onSkip}>
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-amber-500" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('ui:BankTransactionsPage.possibleDuplicate')}</h3>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
         {t('ui:BankTransactionsPage.thisBankTransactionLooksLike')} {destinationLabel} {t('ui:BankTransactionsPage.wouldCountItTwice')}
        </p>
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="border rounded-lg p-3">
            <div className="text-[11px] uppercase tracking-wide text-gray-400 mb-1">{t('ui:BankTransactionsPage.fromYourBank')}</div>
            <div className="font-medium text-gray-900 dark:text-gray-100">{txn.merchant_name || txn.name}</div>
            <div className="text-sm text-gray-500 dark:text-gray-400">{formatDate(txn.date)}</div>
            <div className="text-sm font-semibold mt-1">{formatCurrency(txn.amount, currency)}</div>
          </div>
          <div className="border border-amber-200 dark:border-amber-800 rounded-lg p-3 bg-amber-50 dark:bg-amber-900/20">
            <div className="text-[11px] uppercase tracking-wide text-amber-600 dark:text-amber-400 mb-1">{t('ui:BankTransactionsPage.alreadyInYourBooks')}</div>
            {isLoading ? (
              <div className="text-sm text-gray-400">{t('ui:BankTransactionsPage.loading')}</div>
            ) : candidates.length === 0 ? (
              <div className="text-sm text-gray-400">{t('ui:BankTransactionsPage.noMatchFound')}</div>
            ) : candidates.map((c) => (
              <div key={c.id} className="mb-2 last:mb-0">
                <div className="font-medium text-gray-900 dark:text-gray-100">{c.description || t('ui:BankTransactionsPage.noDescription')}</div>
                <div className="text-sm text-gray-500 dark:text-gray-400">{formatDate(c.date)} · {c.kind}</div>
                <div className="text-sm font-semibold">{formatCurrency(Number(c.amount), currency)}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-6 flex flex-col sm:flex-row items-stretch sm:items-center sm:justify-end gap-2">
          <button
            onClick={onSkip}
            disabled={confirming}
            className="px-4 py-2 text-sm border rounded-lg text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
          >
           {t('ui:BankTransactionsPage.skipSameTransaction')}
          </button>
          <button
            onClick={onConfirm}
            disabled={confirming}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {confirming ? t('ui:BankTransactionsPage.adding') : t('ui:BankTransactionsPage.addAnywaySeparateCharge')}
          </button>
        </div>
      </div>
    </div>
  )
}

/** "Send to Cashbook" — the primary destination. Mirrors the Email Scanner's
 *  import modal: account is shown read-only (auto-created from the bank), the
 *  user confirms the direction and optionally a category, then it posts via the
 *  same create_entry the rest of the Cashbook uses. */
function CashbookDestinationModal({ txn, accountLabel, currency, categories, personalCategories, submitting, onClose, onConfirm }: {
  txn: PlaidTransaction
  accountLabel: string
  currency: string
  categories: TransactionCategory[]
  personalCategories: PersonalCategory[]
  submitting: boolean
  onClose: () => void
  onConfirm: (payload: { categoryId?: string; personalCategoryId?: string; entryType: CashbookEntryType; scope: 'business' | 'personal' }) => void
}) {
  const { t } = useTranslation('ui')
  const [entryType, setEntryType] = useState<CashbookEntryType>(txn.is_income ? 'income' : 'expense')
  const [scope, setScope] = useState<'business' | 'personal'>('business')
  const [categoryId, setCategoryId] = useState<string>('')
  const [personalCategoryId, setPersonalCategoryId] = useState<string>('')

  const visibleCategories = categories.filter(
    (c) => c.category_type === entryType || c.category_type === 'both' || c.category_type === 'equity',
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-blue-600" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('ui:BankTransactionsPage.sendToCashbook')}</h3>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
         {t('ui:BankTransactionsPage.postsThisBankTransactionTo')}
        </p>

        <div className="mt-4 rounded-lg border border-gray-200 dark:border-gray-700 p-3 space-y-1">
          <div className="flex justify-between gap-3 text-sm">
            <span className="text-gray-500 dark:text-gray-400 shrink-0">{t('ui:BankTransactionsPage.account')}</span>
            <span className="font-medium text-gray-900 dark:text-gray-100 text-right truncate">{accountLabel}</span>
          </div>
          <div className="flex justify-between gap-3 text-sm">
            <span className="text-gray-500 dark:text-gray-400 shrink-0">{t('ui:BankTransactionsPage.date')}</span>
            <span className="text-gray-900 dark:text-gray-100">{formatDate(txn.date)}</span>
          </div>
          <div className="flex justify-between gap-3 text-sm">
            <span className="text-gray-500 dark:text-gray-400 shrink-0">{t('ui:BankTransactionsPage.description')}</span>
            <span className="text-gray-900 dark:text-gray-100 text-right truncate">{txn.merchant_name || txn.name}</span>
          </div>
          <div className="flex justify-between gap-3 text-sm">
            <span className="text-gray-500 dark:text-gray-400 shrink-0">{t('ui:BankTransactionsPage.amount')}</span>
            <span className="font-semibold text-gray-900 dark:text-gray-100">{formatCurrency(txn.amount, currency)}</span>
          </div>
        </div>

        <div className="mt-4">
          <label className="text-xs uppercase tracking-wide text-gray-400 dark:text-gray-500">{t('ui:BankTransactionsPage.thisIsA')}</label>
          <div className="mt-1 flex gap-2">
            <button
              type="button"
              onClick={() => setScope('business')}
              className={`flex-1 px-3 py-2 text-sm rounded-lg border ${scope === 'business' ? 'border-blue-300 bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300' : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'}`}
            >
             {t('ui:BankTransactionsPage.business')}
            </button>
            <button
              type="button"
              onClick={() => setScope('personal')}
              className={`flex-1 px-3 py-2 text-sm rounded-lg border ${scope === 'personal' ? 'border-purple-300 bg-purple-50 text-purple-700 dark:bg-purple-900/20 dark:text-purple-300' : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'}`}
            >
             {t('ui:BankTransactionsPage.personal')}
            </button>
          </div>
          {scope === 'personal' && (
            <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
             {t('ui:BankTransactionsPage.postsAsOwnerSDraw')}
            </p>
          )}
        </div>

        <div className="mt-4">
          <label className="text-xs uppercase tracking-wide text-gray-400 dark:text-gray-500">{t('ui:BankTransactionsPage.type')}</label>
          <div className="mt-1 flex gap-2">
            <button
              type="button"
              onClick={() => { setEntryType('expense'); setCategoryId('') }}
              className={`flex-1 px-3 py-2 text-sm rounded-lg border ${entryType === 'expense' ? 'border-red-300 bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-300' : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'}`}
            >
             {t('ui:BankTransactionsPage.expense')}
            </button>
            <button
              type="button"
              onClick={() => { setEntryType('income'); setCategoryId('') }}
              className={`flex-1 px-3 py-2 text-sm rounded-lg border ${entryType === 'income' ? 'border-green-300 bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-300' : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'}`}
            >
             {t('ui:BankTransactionsPage.income')}
            </button>
          </div>
        </div>

        <div className="mt-4">
          <label className="text-xs uppercase tracking-wide text-gray-400 dark:text-gray-500">{t('ui:BankTransactionsPage.categoryOptional')}</label>
          {scope === 'business' ? (
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="mt-1 w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">{t('ui:BankTransactionsPage.uncategorized')}</option>
              {visibleCategories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          ) : (
            <select
              value={personalCategoryId}
              onChange={(e) => setPersonalCategoryId(e.target.value)}
              className="mt-1 w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">{t('ui:BankTransactionsPage.uncategorized')}</option>
              {personalCategories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          )}
        </div>

        <div className="mt-6 flex items-center justify-end gap-2">
          <button
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 text-sm border rounded-lg text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
          >
           {t('ui:BankTransactionsPage.cancel')}
          </button>
          <button
            onClick={() => onConfirm({
              categoryId: scope === 'business' ? (categoryId || undefined) : undefined,
              personalCategoryId: scope === 'personal' ? (personalCategoryId || undefined) : undefined,
              entryType, scope,
            })}
            disabled={submitting}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? t('ui:BankTransactionsPage.posting') : scope === 'personal' ? t('ui:BankTransactionsPage.postAsPersonal') : t('ui:BankTransactionsPage.postToCashbook')}
          </button>
        </div>
      </div>
    </div>
  )
}

type CategorizeVars = {
  txn: PlaidTransaction
  asType: 'expense' | 'income' | 'cashbook' | 'ignore'
  categoryId?: string
  entryType?: CashbookEntryType
  scope?: 'business' | 'personal'
  personalCategoryId?: string
  confirm?: boolean
}

/** Bulk "Send to Cashbook" — posts many selected transactions at once. Each
 *  lands in its own auto-created bank account; the user picks a direction and an
 *  optional category applied to all. */
function BulkCashbookModal({ count, categories, personalCategories, submitting, onClose, onConfirm }: {
  count: number
  categories: TransactionCategory[]
  personalCategories: PersonalCategory[]
  submitting: boolean
  onClose: () => void
  onConfirm: (payload: { categoryId?: string; personalCategoryId?: string; entryType?: CashbookEntryType; scope: 'business' | 'personal' }) => void
}) {
  const { t } = useTranslation('ui')
  const [entryMode, setEntryMode] = useState<'auto' | 'expense' | 'income'>('auto')
  const [scope, setScope] = useState<'business' | 'personal'>('business')
  const [categoryId, setCategoryId] = useState<string>('')
  const [personalCategoryId, setPersonalCategoryId] = useState<string>('')
  const visibleCategories = categories.filter(
    (c) => entryMode === 'auto' || c.category_type === entryMode || c.category_type === 'both' || c.category_type === 'equity',
  )
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-blue-600" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('ui:BankTransactionsPage.send')} {count} {t('ui:BankTransactionsPage.toCashbook')}</h3>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
         {t('ui:BankTransactionsPage.postsAll')} {count} {t('ui:BankTransactionsPage.selectedTransactionsToYourCashbook')}
        </p>
        <div className="mt-4">
          <label className="text-xs uppercase tracking-wide text-gray-400 dark:text-gray-500">{t('ui:BankTransactionsPage.theseAre')}</label>
          <div className="mt-1 flex gap-2">
            <button type="button" onClick={() => setScope('business')}
              className={`flex-1 px-3 py-2 text-sm rounded-lg border ${scope === 'business' ? 'border-blue-300 bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300' : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'}`}>{t('ui:BankTransactionsPage.business')}</button>
            <button type="button" onClick={() => setScope('personal')}
              className={`flex-1 px-3 py-2 text-sm rounded-lg border ${scope === 'personal' ? 'border-purple-300 bg-purple-50 text-purple-700 dark:bg-purple-900/20 dark:text-purple-300' : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'}`}>{t('ui:BankTransactionsPage.personal')}</button>
          </div>
          {scope === 'personal' && (
            <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">{t('ui:BankTransactionsPage.all')} {count} {t('ui:BankTransactionsPage.postAsOwnerSDraw')}</p>
          )}
        </div>
        <div className="mt-4">
          <label className="text-xs uppercase tracking-wide text-gray-400 dark:text-gray-500">{t('ui:BankTransactionsPage.type')}</label>
          <div className="mt-1 grid grid-cols-3 gap-2">
            {(['auto', 'expense', 'income'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => { setEntryMode(m); setCategoryId('') }}
                className={`px-3 py-2 text-sm rounded-lg border capitalize ${entryMode === m ? 'border-blue-400 bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300' : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'}`}
              >
                {m === 'auto' ? t('ui:BankTransactionsPage.auto') : m}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-1">{t('ui:BankTransactionsPage.autoUsesEachTransactionS')}</p>
        </div>
        <div className="mt-4">
          <label className="text-xs uppercase tracking-wide text-gray-400 dark:text-gray-500">{t('ui:BankTransactionsPage.categoryOptionalAppliedToAll')}</label>
          {scope === 'business' ? (
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="mt-1 w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">{t('ui:BankTransactionsPage.uncategorized')}</option>
              {visibleCategories.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
            </select>
          ) : (
            <select
              value={personalCategoryId}
              onChange={(e) => setPersonalCategoryId(e.target.value)}
              className="mt-1 w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">{t('ui:BankTransactionsPage.uncategorized')}</option>
              {personalCategories.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
            </select>
          )}
        </div>
        <div className="mt-6 flex items-center justify-end gap-2">
          <button onClick={onClose} disabled={submitting} className="px-4 py-2 text-sm border rounded-lg text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50">{t('ui:BankTransactionsPage.cancel')}</button>
          <button
            onClick={() => onConfirm({
              categoryId: scope === 'business' ? (categoryId || undefined) : undefined,
              personalCategoryId: scope === 'personal' ? (personalCategoryId || undefined) : undefined,
              entryType: entryMode === 'auto' ? undefined : entryMode,
              scope,
            })}
            disabled={submitting}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? t('ui:BankTransactionsPage.postingCount', { count }) : scope === 'personal' ? t('ui:BankTransactionsPage.postCountAsPersonal', { count }) : t('ui:BankTransactionsPage.postCountToCashbook', { count })}
          </button>
        </div>
      </div>
    </div>
  )
}

/** "Does my book match my bank?" — per connected bank, book balance vs the
 *  bank's own balance, plus how many synced transactions aren't booked yet. */
function ReconciliationCard() {
  const { t } = useTranslation('ui')
  const { data } = useQuery({ queryKey: ['plaid-reconciliation'], queryFn: getPlaidReconciliation })
  const rows = data?.data ?? []
  if (rows.length === 0) return null
  return (
    <div className="bg-white dark:bg-gray-900 border rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <Scale className="w-4 h-4 text-gray-500 dark:text-gray-400" />
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('ui:BankTransactionsPage.reconciliation')}</h2>
        <span className="text-xs text-gray-400 dark:text-gray-500">{t('ui:BankTransactionsPage.doesYourBookMatchYour')}</span>
      </div>
      <div className="space-y-2">
        {rows.map((r) => {
          const book = r.book_balance != null ? Number(r.book_balance) : null
          const bank = r.bank_balance != null ? Number(r.bank_balance) : null
          const diff = r.difference != null ? Number(r.difference) : null
          const off = diff != null && Math.abs(diff) >= 0.01
          return (
            <div key={r.connection_id} className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm border-t border-gray-100 dark:border-gray-800 pt-2 first:border-t-0 first:pt-0">
              <div className="font-medium text-gray-900 dark:text-gray-100 min-w-[130px]">
                {r.institution_name}
                {r.owner_name && <span className="text-xs text-gray-400 ml-1">· {r.owner_name}</span>}
              </div>
              <div className="text-gray-500 dark:text-gray-400">{t('ui:BankTransactionsPage.book')} <span className="font-mono text-gray-900 dark:text-gray-100">{book != null ? formatCurrency(book, r.currency) : '—'}</span></div>
              <div className="text-gray-500 dark:text-gray-400">{t('ui:BankTransactionsPage.bank')} <span className="font-mono text-gray-900 dark:text-gray-100">{bank != null ? formatCurrency(bank, r.currency) : '—'}</span></div>
              <div className="ml-auto">
                {r.reconciled ? (
                  <span className="flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400"><Check className="w-3.5 h-3.5" /> {t('ui:BankTransactionsPage.reconciled')}</span>
                ) : r.unbooked_count > 0 ? (
                  <span className="text-xs font-medium text-amber-600 dark:text-amber-400">{r.unbooked_count} un-booked</span>
                ) : !r.balance_known ? (
                  <span className="text-xs text-gray-400">{t('ui:BankTransactionsPage.syncToCompareBalance')}</span>
                ) : off ? (
                  <span className="text-xs font-medium text-amber-600 dark:text-amber-400">{t('ui:BankTransactionsPage.offBy')} {formatCurrency(Math.abs(diff!), r.currency)}</span>
                ) : (
                  <span className="text-xs text-gray-400">—</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function BankTransactionsPage() {
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [connectionId, setConnectionId] = useState<string>('')
  const [filterCategorized, setFilterCategorized] = useState<string>('')
  const [filterType, setFilterType] = useState<string>('')
  const [page, setPage] = useState(1)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [selectedTxnIds, setSelectedTxnIds] = useState<Set<string>>(new Set())
  const [bulkOpen, setBulkOpen] = useState(false)

  const { data: connectionsData } = useQuery({
    queryKey: ['plaid-connections'],
    queryFn: listPlaidConnections,
  })

  const { data: categoriesData } = useQuery({
    queryKey: ['cashbook-categories'],
    queryFn: () => listCategories(),
  })
  const categories: TransactionCategory[] = categoriesData?.data ?? []

  const { data: personalCategoriesData } = useQuery({
    queryKey: ['personal-categories'],
    queryFn: listPersonalCategories,
  })
  const personalCategories: PersonalCategory[] = personalCategoriesData?.data ?? []

  const { data: txnData, isLoading } = useQuery({
    queryKey: ['plaid-transactions', connectionId, filterCategorized, filterType, search, page],
    queryFn: () => listPlaidTransactions({
      connection_id: connectionId || undefined,
      is_categorized: filterCategorized === '' ? undefined : filterCategorized === 'true',
      is_income: filterType === '' ? undefined : filterType === 'income',
      search: search || undefined,
      page,
      // While searching, load all matches on one page so "select all" covers them.
      page_size: search ? 500 : 50,
    }),
  })

  const syncMutation = useMutation({
    mutationFn: syncPlaidTransactions,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plaid-transactions'] })
      queryClient.invalidateQueries({ queryKey: ['plaid-connections'] })
      queryClient.invalidateQueries({ queryKey: ['plaid-reconciliation'] })
    },
  })

  const [dupDialog, setDupDialog] = useState<{ txn: PlaidTransaction; asType: 'expense' | 'income' | 'cashbook'; categoryId?: string; entryType?: CashbookEntryType; scope?: 'business' | 'personal'; personalCategoryId?: string } | null>(null)
  const [cashbookModal, setCashbookModal] = useState<PlaidTransaction | null>(null)

  const categorizeMutation = useMutation({
    mutationFn: ({ txn, asType, categoryId, entryType, scope, personalCategoryId, confirm }: CategorizeVars) =>
      categorizePlaidTransaction(txn.id, {
        as_type: asType,
        category_id: categoryId,
        entry_type: entryType,
        scope,
        personal_category_id: personalCategoryId,
        confirm_duplicate: confirm,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plaid-transactions'] })
      // A cashbook post creates/updates an account + entry — refresh the
      // Cashbook views so the new CIBC tab and row appear immediately.
      queryClient.invalidateQueries({ queryKey: ['cashbook-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })
      queryClient.invalidateQueries({ queryKey: ['plaid-reconciliation'] })
      // Personal copy may have been created — refresh Personal mode views.
      queryClient.invalidateQueries({ queryKey: ['personal-cashflow'] })
      queryClient.invalidateQueries({ queryKey: ['personal-transactions'] })
      queryClient.invalidateQueries({ queryKey: ['personal-accounts'] })
      setDupDialog(null)
      setCashbookModal(null)
    },
    onError: (err, variables) => {
      // Server flagged a likely duplicate — open the confirm dialog instead of
      // failing. (ignore never posts, so it can't collide.)
      if (
        err instanceof ApiClientError &&
        err.status === 409 &&
        err.error?.code === 'PLAID_POSSIBLE_DUPLICATE' &&
        (variables.asType === 'expense' || variables.asType === 'income' || variables.asType === 'cashbook')
      ) {
        setDupDialog({ txn: variables.txn, asType: variables.asType, categoryId: variables.categoryId, entryType: variables.entryType, scope: variables.scope, personalCategoryId: variables.personalCategoryId })
        setCashbookModal(null)
      }
    },
  })

  const bulkMutation = useMutation({
    mutationFn: (payload: { txnIds: string[]; categoryId?: string; entryType?: CashbookEntryType; scope?: 'business' | 'personal'; personalCategoryId?: string }) =>
      bulkCategorizePlaidTransactions({
        txn_ids: payload.txnIds,
        as_type: 'cashbook',
        category_id: payload.categoryId,
        entry_type: payload.entryType,
        scope: payload.scope,
        personal_category_id: payload.personalCategoryId,
      }),
    onSuccess: (resp) => {
      const d = (resp as any)?.data
      queryClient.invalidateQueries({ queryKey: ['plaid-transactions'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })
      queryClient.invalidateQueries({ queryKey: ['plaid-reconciliation'] })
      setSelectedTxnIds(new Set())
      setBulkOpen(false)
      if (d?.errors?.length) toast.warning(t('ui:BankTransactionsPage.postedPostedOfTotalLength', { posted: d.posted, total: d.total, length: d.errors.length }))
      else toast.success(t('ui:BankTransactionsPage.postedV0TransactionV1To', { v0: d?.posted ?? 0, v1: d?.posted === 1 ? '' : 's' }))
    },
    onError: (err: any) => toast.error(err?.message || 'Bulk post failed.'),
  })

  const applyRulesMutation = useMutation({
    mutationFn: applyCategorizationRules,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plaid-transactions'] }),
  })

  const aiCategorizeMutation = useMutation({
    mutationFn: aiCategorizeTransactions,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plaid-transactions'] }),
  })

  const connections = connectionsData?.data ?? []
  const transactions: PlaidTransaction[] = txnData?.data ?? []
  const meta = txnData?.meta ?? { total: 0, page: 1, page_size: 50 }
  const totalPages = Math.ceil(meta.total / meta.page_size)

  // Client-side join: Plaid account_id -> a friendly "CIBC Chequing …1234"
  // label + its native currency, flattened from every connection's accounts.
  const accountMetaMap = useMemo(() => {
    const m = new Map<string, { label: string; currency: string; owner: string }>()
    for (const conn of connections) {
      for (const a of (conn.accounts ?? []) as Array<{ account_id: string; name: string; mask: string | null; iso_currency_code?: string | null }>) {
        const mask = a.mask ? ` …${a.mask}` : ''
        m.set(a.account_id, {
          label: `${conn.institution_name} ${a.name}${mask}`.trim(),
          currency: (a.iso_currency_code || 'CAD').toUpperCase(),
          owner: conn.owner_name || '',
        })
      }
    }
    return m
  }, [connections])

  const accountLabelFor = (txn: PlaidTransaction) => accountMetaMap.get(txn.account_id)?.label ?? '—'
  const currencyFor = (txn: PlaidTransaction) => accountMetaMap.get(txn.account_id)?.currency ?? 'CAD'
  const accountOwnerFor = (txn: PlaidTransaction) => accountMetaMap.get(txn.account_id)?.owner ?? ''

  // More than one distinct bank owner => this feed is shared across the org.
  const distinctOwners = useMemo(
    () => new Set(connections.map((c) => c.owner_name).filter(Boolean)),
    [connections],
  )
  const isSharedWorkspace = distinctOwners.size > 1

  const uncategorized = transactions.filter((t) => !t.is_categorized)
  const allUncatSelected = uncategorized.length > 0 && uncategorized.every((t) => selectedTxnIds.has(t.id))
  const toggleTxn = (id: string) => setSelectedTxnIds((prev) => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id); else next.add(id)
    return next
  })
  const toggleAllUncategorized = () =>
    setSelectedTxnIds(allUncatSelected ? new Set() : new Set(uncategorized.map((t) => t.id)))
  const runSearch = () => { setSearch(searchInput.trim()); setPage(1); setSelectedTxnIds(new Set()) }
  const clearSearch = () => { setSearchInput(''); setSearch(''); setPage(1); setSelectedTxnIds(new Set()) }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('ui:BankTransactionsPage.bankScanner')}</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
           {t('ui:BankTransactionsPage.reviewSyncedBankTransactionsAnd')}
          </p>
        </div>
        {connections.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => applyRulesMutation.mutate()}
              disabled={applyRulesMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
            >
              <ListChecks className="w-4 h-4" />
              {applyRulesMutation.isPending ? t('ui:BankTransactionsPage.applying') : t('ui:BankTransactionsPage.applyRules')}
            </button>
            <button
              onClick={() => aiCategorizeMutation.mutate()}
              disabled={aiCategorizeMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-2 text-sm border border-purple-300 text-purple-700 rounded-lg hover:bg-purple-50 disabled:opacity-50"
            >
              <Sparkles className={`w-4 h-4 ${aiCategorizeMutation.isPending ? 'animate-pulse' : ''}`} />
              {aiCategorizeMutation.isPending ? t('ui:BankTransactionsPage.categorizing') : t('ui:BankTransactionsPage.aiCategorize')}
            </button>
            <button
              onClick={() => {
                if (connectionId) syncMutation.mutate(connectionId)
                else connections.forEach((c) => syncMutation.mutate(c.id))
              }}
              disabled={syncMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
             {t('ui:BankTransactionsPage.sync')}
            </button>
          </div>
        )}
      </div>

      {isSharedWorkspace && (
        <div className="flex items-center gap-2 rounded-lg border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-900/20 px-4 py-2 text-sm text-blue-700 dark:text-blue-300">
          <Landmark className="w-4 h-4 shrink-0" />
          <span>{t('ui:BankTransactionsPage.bankDataIsSharedWith')}</span>
        </div>
      )}

      {connections.length > 0 && <ReconciliationCard />}

      {/* Filters */}
      <div className="bg-white dark:bg-gray-900 border rounded-lg p-4 flex flex-wrap gap-3 items-center">
        <Filter className="w-4 h-4 text-gray-400 dark:text-gray-500" />
        <select
          value={connectionId}
          onChange={(e) => { setConnectionId(e.target.value); setPage(1) }}
          className="px-3 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">{t('ui:BankTransactionsPage.allBanks')}</option>
          {connections.map((c) => (
            <option key={c.id} value={c.id}>{c.institution_name}</option>
          ))}
        </select>
        <select
          value={filterCategorized}
          onChange={(e) => { setFilterCategorized(e.target.value); setPage(1) }}
          className="px-3 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">{t('ui:BankTransactionsPage.allStatus')}</option>
          <option value="false">{t('ui:BankTransactionsPage.uncategorized')}</option>
          <option value="true">{t('ui:BankTransactionsPage.categorized')}</option>
        </select>
        <select
          value={filterType}
          onChange={(e) => { setFilterType(e.target.value); setPage(1) }}
          className="px-3 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">{t('ui:BankTransactionsPage.allTypes')}</option>
          <option value="expense">{t('ui:BankTransactionsPage.expenses')}</option>
          <option value="income">{t('ui:BankTransactionsPage.income')}</option>
        </select>
        <form onSubmit={(e) => { e.preventDefault(); runSearch() }} className="flex items-center gap-1">
          <div className="relative">
            <Search className="w-4 h-4 text-gray-400 absolute left-2 top-1/2 -translate-y-1/2" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder={t('ui:BankTransactionsPage.searchANameEG')}
              className="pl-8 pr-7 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-56"
            />
            {searchInput && (
              <button type="button" onClick={clearSearch} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600" title={t('ui:BankTransactionsPage.clear')}>
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          <button type="submit" className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-800 border rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700">
           {t('ui:BankTransactionsPage.search')}
          </button>
        </form>
        <span className="text-sm text-gray-400 dark:text-gray-500 ml-auto">
          {search && <span className="text-blue-500">"{search}" · </span>}
          {meta.total} transaction{meta.total !== 1 ? 's' : ''}
        </span>
      </div>

      {selectedTxnIds.size > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-blue-300 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 px-4 py-2.5">
          <span className="text-sm text-blue-800 dark:text-blue-300 font-medium">{selectedTxnIds.size} selected</span>
          <div className="flex items-center gap-2">
            <button onClick={() => setSelectedTxnIds(new Set())} className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:underline">{t('ui:BankTransactionsPage.clear')}</button>
            <button onClick={() => setBulkOpen(true)} className="flex items-center gap-1.5 px-4 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <BookOpen className="w-4 h-4" /> {t('ui:BankTransactionsPage.send')} {selectedTxnIds.size} {t('ui:BankTransactionsPage.toCashbook')}
            </button>
          </div>
        </div>
      )}

      {/* Transactions */}
      {isLoading ? (
        <p className="text-gray-400 dark:text-gray-500 py-8 text-center text-sm">{t('ui:BankTransactionsPage.loadingTransactions')}</p>
      ) : transactions.length > 0 ? (
        <>
          <div className="bg-white dark:bg-gray-900 border rounded-lg overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50 dark:bg-gray-950">
                  <th className="w-10 px-4 py-3">
                    <input
                      type="checkbox"
                      checked={allUncatSelected}
                      onChange={toggleAllUncategorized}
                      className="h-4 w-4 rounded border-gray-300 dark:border-gray-600"
                      title={t('ui:BankTransactionsPage.selectAllUncategorized')}
                    />
                  </th>
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">{t('ui:BankTransactionsPage.date')}</th>
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">{t('ui:BankTransactionsPage.description')}</th>
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">{t('ui:BankTransactionsPage.account')}</th>
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">{t('ui:BankTransactionsPage.category')}</th>
                  <th className="text-right px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">{t('ui:BankTransactionsPage.amount')}</th>
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">{t('ui:BankTransactionsPage.status')}</th>
                  <th className="text-right px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">{t('ui:BankTransactionsPage.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <tr key={txn.id} className={`border-b hover:bg-gray-50 dark:hover:bg-gray-800 ${selectedTxnIds.has(txn.id) ? 'bg-blue-50/50 dark:bg-blue-900/10' : ''}`}>
                    <td className="px-4 py-3">
                      {!txn.is_categorized && (
                        <input
                          type="checkbox"
                          checked={selectedTxnIds.has(txn.id)}
                          onChange={() => toggleTxn(txn.id)}
                          className="h-4 w-4 rounded border-gray-300 dark:border-gray-600"
                        />
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">{formatDate(txn.date)}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900 dark:text-gray-100">{txn.merchant_name || txn.name}</div>
                      {txn.merchant_name && txn.name !== txn.merchant_name && (
                        <div className="text-xs text-gray-400 dark:text-gray-500">{txn.name}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs whitespace-nowrap">
                      {accountLabelFor(txn)}
                      {isSharedWorkspace && accountOwnerFor(txn) && (
                        <div className="text-[11px] text-gray-400 dark:text-gray-500">{accountOwnerFor(txn)}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs">{txn.category || '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={`flex items-center justify-end gap-1 font-medium ${txn.is_income ? 'text-green-600' : 'text-gray-900 dark:text-gray-100'}`}>
                        {txn.is_income ? <ArrowDownRight className="w-3.5 h-3.5" /> : <ArrowUpRight className="w-3.5 h-3.5" />}
                        {formatCurrency(txn.amount, currencyFor(txn))}
                      </span>
                      {txn.pending && <span className="text-xs text-amber-500">{t('ui:BankTransactionsPage.pending')}</span>}
                    </td>
                    <td className="px-4 py-3">
                      {txn.is_categorized ? (
                        <span className="flex items-center gap-1 text-xs text-green-600">
                          <Check className="w-3.5 h-3.5" />
                          {txn.matched_cashbook_entry_id ? t('ui:BankTransactionsPage.cashbook') : txn.matched_expense_id ? t('ui:BankTransactionsPage.expense') : txn.matched_income_id ? t('ui:BankTransactionsPage.income') : t('ui:BankTransactionsPage.ignored')}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400 dark:text-gray-500">{t('ui:BankTransactionsPage.uncategorized')}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {!txn.is_categorized && (
                        <div className="flex items-center gap-1 justify-end">
                          <button
                            onClick={() => setCashbookModal(txn)}
                            disabled={categorizeMutation.isPending}
                            className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                          >
                            <BookOpen className="w-3.5 h-3.5" />
                           {t('ui:BankTransactionsPage.cashbook')}
                          </button>
                          <button
                            onClick={() => categorizeMutation.mutate({ txn, asType: 'expense' })}
                            disabled={categorizeMutation.isPending}
                            className="px-2 py-1 text-xs border rounded hover:bg-red-50 text-red-600 border-red-200"
                          >
                           {t('ui:BankTransactionsPage.expense')}
                          </button>
                          <button
                            onClick={() => categorizeMutation.mutate({ txn, asType: 'income' })}
                            disabled={categorizeMutation.isPending}
                            className="px-2 py-1 text-xs border rounded hover:bg-green-50 text-green-600 border-green-200"
                          >
                           {t('ui:BankTransactionsPage.income')}
                          </button>
                          <button
                            onClick={() => categorizeMutation.mutate({ txn, asType: 'ignore' })}
                            disabled={categorizeMutation.isPending}
                            className="px-2 py-1 text-xs border rounded hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400"
                          >
                           {t('ui:BankTransactionsPage.ignore')}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800"
              >
               {t('ui:BankTransactionsPage.previous')}
              </button>
              <span className="text-sm text-gray-500 dark:text-gray-400">
               {t('ui:BankTransactionsPage.page')} {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800"
              >
               {t('ui:BankTransactionsPage.next')}
              </button>
            </div>
          )}
        </>
      ) : connections.length === 0 ? (
        <div className="text-center py-16 bg-white dark:bg-gray-900 border rounded-lg">
          <Landmark className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400">{t('ui:BankTransactionsPage.noBankAccountsConnected')}</p>
          <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">
           {t('ui:BankTransactionsPage.goToSettingsBankingTo')}
          </p>
        </div>
      ) : (
        <div className="text-center py-16 bg-white dark:bg-gray-900 border rounded-lg">
          <Landmark className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400">{t('ui:BankTransactionsPage.noTransactionsFound')}</p>
          <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">
           {t('ui:BankTransactionsPage.clickSyncToImportTransactions')}
          </p>
        </div>
      )}

      {bulkOpen && (
        <BulkCashbookModal
          count={selectedTxnIds.size}
          categories={categories}
          personalCategories={personalCategories}
          submitting={bulkMutation.isPending}
          onClose={() => setBulkOpen(false)}
          onConfirm={({ categoryId, entryType, scope, personalCategoryId }) =>
            bulkMutation.mutate({ txnIds: Array.from(selectedTxnIds), categoryId, entryType, scope, personalCategoryId })
          }
        />
      )}

      {cashbookModal && (
        <CashbookDestinationModal
          txn={cashbookModal}
          accountLabel={accountLabelFor(cashbookModal)}
          currency={currencyFor(cashbookModal)}
          categories={categories}
          personalCategories={personalCategories}
          submitting={categorizeMutation.isPending}
          onClose={() => setCashbookModal(null)}
          onConfirm={({ categoryId, personalCategoryId, entryType, scope }) =>
            categorizeMutation.mutate({ txn: cashbookModal, asType: 'cashbook', categoryId, personalCategoryId, entryType, scope })
          }
        />
      )}

      {dupDialog && (
        <DuplicateDialog
          txn={dupDialog.txn}
          asType={dupDialog.asType}
          currency={currencyFor(dupDialog.txn)}
          confirming={categorizeMutation.isPending}
          onSkip={() => setDupDialog(null)}
          onConfirm={() => categorizeMutation.mutate({ txn: dupDialog.txn, asType: dupDialog.asType, categoryId: dupDialog.categoryId, entryType: dupDialog.entryType, scope: dupDialog.scope, personalCategoryId: dupDialog.personalCategoryId, confirm: true })}
        />
      )}
    </div>
  )
}
