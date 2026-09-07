import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  listTrash,
  getTrashCount,
  emptyTrash,
  restoreAllTrash,
  restoreEntry,
  permanentDeleteEntry,
  restoreAccount,
  permanentDeleteAccount,
} from '@/api/cashbook'
import { formatDate } from '@/lib/utils'
import {
  Trash2,
  RotateCcw,
  AlertTriangle,
  Clock,
  ChevronLeft,
  ChevronRight,
  XCircle,
  Package,
  CreditCard,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'

const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000

function daysUntilPermanentDeletion(deletedAt: string | null, updatedAt: string): number {
  const refDate = deletedAt || updatedAt
  const deletedTime = new Date(refDate).getTime()
  const expiresAt = deletedTime + THIRTY_DAYS_MS
  const remaining = Math.ceil((expiresAt - Date.now()) / (24 * 60 * 60 * 1000))
  return Math.max(0, remaining)
}

export default function TrashPage() {
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [confirmAction, setConfirmAction] = useState<'empty' | 'delete-entry' | 'delete-account' | null>(null)
  const [confirmId, setConfirmId] = useState<string | null>(null)

  const { data: trashData, isLoading } = useQuery({
    queryKey: ['cashbook-trash', page],
    queryFn: () => listTrash(page, 50),
  })

  const { data: countData } = useQuery({
    queryKey: ['cashbook-trash-count'],
    queryFn: getTrashCount,
  })

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['cashbook-trash'] })
    queryClient.invalidateQueries({ queryKey: ['cashbook-trash-count'] })
    queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
    queryClient.invalidateQueries({ queryKey: ['cashbook-accounts'] })
  }

  const restoreEntryMutation = useMutation({
    mutationFn: (id: string) => restoreEntry(id),
    onSuccess: () => { toast.success(t('ui:TrashPage.entryRestored')); invalidateAll() },
    onError: (e: any) => toast.error(e?.error?.message || 'Failed to restore entry'),
  })

  const permanentDeleteEntryMutation = useMutation({
    mutationFn: (id: string) => permanentDeleteEntry(id),
    onSuccess: () => { toast.success(t('ui:TrashPage.entryPermanentlyDeleted')); invalidateAll(); setConfirmAction(null); setConfirmId(null) },
    onError: (e: any) => toast.error(e?.error?.message || 'Failed to delete entry'),
  })

  const restoreAccountMutation = useMutation({
    mutationFn: (id: string) => restoreAccount(id),
    onSuccess: () => { toast.success(t('ui:TrashPage.accountRestored')); invalidateAll() },
    onError: (e: any) => toast.error(e?.error?.message || 'Failed to restore account'),
  })

  const permanentDeleteAccountMutation = useMutation({
    mutationFn: (id: string) => permanentDeleteAccount(id),
    onSuccess: () => { toast.success(t('ui:TrashPage.accountPermanentlyDeleted')); invalidateAll(); setConfirmAction(null); setConfirmId(null) },
    onError: (e: any) => toast.error(e?.error?.message || 'Failed to delete account'),
  })

  const emptyTrashMutation = useMutation({
    mutationFn: emptyTrash,
    onSuccess: (res) => {
      const d = res.data
      toast.success(t('ui:TrashPage.emptiedTrashDeletedEntriesEntries', { deleted_entries: d.deleted_entries, deleted_accounts: d.deleted_accounts }))
      invalidateAll()
      setConfirmAction(null)
    },
    onError: (e: any) => toast.error(e?.error?.message || 'Failed to empty trash'),
  })

  const restoreAllMutation = useMutation({
    mutationFn: restoreAllTrash,
    onSuccess: (res) => {
      const d = res.data
      toast.success(t('ui:TrashPage.restoredRestoredEntriesEntriesRestored', { restored_entries: d.restored_entries, restored_accounts: d.restored_accounts }))
      invalidateAll()
    },
    onError: (e: any) => toast.error(e?.error?.message || 'Failed to restore all'),
  })

  const entries = trashData?.data?.entries || []
  const accounts = trashData?.data?.accounts || []
  const meta = trashData?.meta
  const totalCount = countData?.data?.total || 0

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Trash2 className="h-6 w-6 text-gray-400" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('ui:TrashPage.trash')}</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
             {t('ui:TrashPage.itemsArePermanentlyDeletedAfter')}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => restoreAllMutation.mutate()}
            disabled={totalCount === 0 || restoreAllMutation.isPending}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <RotateCcw className="h-4 w-4" />
           {t('ui:TrashPage.restoreAll')}
          </button>
          <button
            onClick={() => setConfirmAction('empty')}
            disabled={totalCount === 0 || emptyTrashMutation.isPending}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <XCircle className="h-4 w-4" />
           {t('ui:TrashPage.emptyTrash')}
          </button>
        </div>
      </div>

      {/* Empty state */}
      {!isLoading && entries.length === 0 && accounts.length === 0 && (
        <div className="text-center py-16">
          <Trash2 className="h-12 w-12 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">{t('ui:TrashPage.trashIsEmpty')}</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('ui:TrashPage.deletedEntriesAndAccountsWill')}</p>
        </div>
      )}

      {/* Deleted Accounts Section */}
      {accounts.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <CreditCard className="h-4 w-4" />
           {t('ui:TrashPage.deletedAccounts')}{accounts.length})
          </h2>
          <div className="space-y-2">
            {accounts.map((account) => {
              const daysLeft = daysUntilPermanentDeletion(null, account.updated_at)
              return (
                <div
                  key={account.id}
                  className="flex items-center justify-between p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="h-10 w-10 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
                      <CreditCard className="h-5 w-5 text-gray-400" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-gray-900 dark:text-gray-100 truncate">{account.name}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {account.account_type} &middot; {account.currency} {t('ui:TrashPage.balance')}{Number(account.opening_balance).toFixed(2)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className={`text-xs flex items-center gap-1 ${daysLeft <= 7 ? 'text-red-500' : 'text-gray-400 dark:text-gray-500'}`}>
                      <Clock className="h-3 w-3" />
                      {daysLeft}{t('ui:TrashPage.dLeft')}
                    </span>
                    <button
                      onClick={() => restoreAccountMutation.mutate(account.id)}
                      disabled={restoreAccountMutation.isPending}
                      className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 rounded-md hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
                    >
                      <RotateCcw className="h-3 w-3" /> {t('ui:TrashPage.restore')}
                    </button>
                    <button
                      onClick={() => { setConfirmAction('delete-account'); setConfirmId(account.id) }}
                      className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 rounded-md hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors"
                    >
                      <XCircle className="h-3 w-3" /> {t('ui:TrashPage.delete')}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Deleted Entries Section */}
      {entries.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Package className="h-4 w-4" />
           {t('ui:TrashPage.deletedEntries')}{meta?.total_count ?? entries.length})
          </h2>
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  <th className="px-4 py-3">{t('ui:TrashPage.date')}</th>
                  <th className="px-4 py-3">{t('ui:TrashPage.description')}</th>
                  <th className="px-4 py-3">{t('ui:TrashPage.account')}</th>
                  <th className="px-4 py-3">{t('ui:TrashPage.type')}</th>
                  <th className="px-4 py-3 text-right">{t('ui:TrashPage.amount')}</th>
                  <th className="px-4 py-3">{t('ui:TrashPage.deleted')}</th>
                  <th className="px-4 py-3 text-right">{t('ui:TrashPage.actions')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {entries.map((entry) => {
                  const daysLeft = daysUntilPermanentDeletion(entry.deleted_at, entry.updated_at)
                  return (
                    <tr key={entry.id} className="hover:bg-gray-50 dark:hover:bg-gray-750">
                      <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 whitespace-nowrap">
                        {formatDate(entry.date)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 max-w-[200px] truncate">
                        {entry.description}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">
                        {entry.account_name || '—'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          entry.entry_type === 'income'
                            ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                            : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                        }`}>
                          {entry.entry_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm font-medium text-right whitespace-nowrap">
                        <span className={entry.entry_type === 'income' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                          {entry.entry_type === 'income' ? '+' : '-'}${Number(entry.total_amount).toFixed(2)}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={`text-xs flex items-center gap-1 ${daysLeft <= 7 ? 'text-red-500' : 'text-gray-400 dark:text-gray-500'}`}>
                          <Clock className="h-3 w-3" />
                          {daysLeft}{t('ui:TrashPage.dLeft')}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => restoreEntryMutation.mutate(entry.id)}
                            disabled={restoreEntryMutation.isPending}
                            className="p-1.5 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-md transition-colors"
                            title={t('ui:TrashPage.restore')}
                          >
                            <RotateCcw className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => { setConfirmAction('delete-entry'); setConfirmId(entry.id) }}
                            className="p-1.5 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-md transition-colors"
                            title={t('ui:TrashPage.deletePermanently')}
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {meta && meta.total_pages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-gray-500 dark:text-gray-400">
               {t('ui:TrashPage.page')} {meta.page} of {meta.total_pages} ({meta.total_count} {t('ui:TrashPage.entries')}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="p-2 rounded-lg border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setPage(p => Math.min(meta.total_pages, p + 1))}
                  disabled={page >= meta.total_pages}
                  className="p-2 rounded-lg border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="text-center py-16">
          <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('ui:TrashPage.loadingTrash')}</p>
        </div>
      )}

      {/* Confirmation Modal */}
      {confirmAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="h-10 w-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {confirmAction === 'empty' ? t('ui:TrashPage.emptyTrash_2') : t('ui:TrashPage.deletePermanently_2')}
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                 {t('ui:TrashPage.thisCannotBeUndone')}
                </p>
              </div>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-300 mb-6">
              {confirmAction === 'empty'
                ? t('ui:TrashPage.allItemsInTheTrash')
                : t('ui:TrashPage.thisItemWillBePermanently')}
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setConfirmAction(null); setConfirmId(null) }}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              >
               {t('ui:TrashPage.cancel')}
              </button>
              <button
                onClick={() => {
                  if (confirmAction === 'empty') emptyTrashMutation.mutate()
                  else if (confirmAction === 'delete-entry' && confirmId) permanentDeleteEntryMutation.mutate(confirmId)
                  else if (confirmAction === 'delete-account' && confirmId) permanentDeleteAccountMutation.mutate(confirmId)
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
              >
                {confirmAction === 'empty' ? t('ui:TrashPage.emptyTrash') : t('ui:TrashPage.deletePermanently_3')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
