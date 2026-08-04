import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Wallet, Plus, TrendingUp, TrendingDown, Trash2, Lock, Loader2 } from 'lucide-react'
import {
  listPersonalAccounts,
  createPersonalAccount,
  deletePersonalAccount,
  listPersonalTransactions,
  createPersonalTransaction,
  deletePersonalTransaction,
  getPersonalCashflow,
} from '@/api/personal'

function money(v: string | null | undefined): string {
  const n = parseFloat(v ?? '0')
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const today = () => new Date().toISOString().slice(0, 10)

export default function PersonalLedgerPage() {
  const qc = useQueryClient()
  const [showAccount, setShowAccount] = useState(false)
  const [showTxn, setShowTxn] = useState(false)

  const accountsQ = useQuery({ queryKey: ['personal-accounts'], queryFn: listPersonalAccounts })
  const cashflowQ = useQuery({ queryKey: ['personal-cashflow'], queryFn: () => getPersonalCashflow() })
  const txnsQ = useQuery({ queryKey: ['personal-transactions'], queryFn: () => listPersonalTransactions({ limit: 100 }) })

  const accounts = accountsQ.data?.data ?? []
  const cashflow = cashflowQ.data?.data
  const txns = txnsQ.data?.data ?? []

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['personal-accounts'] })
    qc.invalidateQueries({ queryKey: ['personal-cashflow'] })
    qc.invalidateQueries({ queryKey: ['personal-transactions'] })
  }

  const delAccount = useMutation({ mutationFn: deletePersonalAccount, onSuccess: invalidate })
  const delTxn = useMutation({ mutationFn: deletePersonalTransaction, onSuccess: invalidate })

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <Wallet className="w-6 h-6 text-gray-700 dark:text-gray-300" />
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Personal Finances</h1>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-1.5">
          <Lock className="w-3.5 h-3.5" />
          Private to you, encrypted, and completely separate from your business books &amp; taxes.
        </p>
      </div>

      {/* Cashflow summary */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-3">
          <div className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1"><TrendingUp className="w-3.5 h-3.5 text-green-600" /> Money in</div>
          <div className="text-lg font-semibold tabular-nums">${money(cashflow?.total_in)}</div>
        </div>
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-3">
          <div className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1"><TrendingDown className="w-3.5 h-3.5 text-red-600" /> Money out</div>
          <div className="text-lg font-semibold tabular-nums">${money(cashflow?.total_out)}</div>
        </div>
        <div className="rounded-xl border border-gray-900 dark:border-gray-100 p-3">
          <div className="text-xs text-gray-500 dark:text-gray-400">Net</div>
          <div className={`text-lg font-semibold tabular-nums ${parseFloat(cashflow?.net ?? '0') >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>${money(cashflow?.net)}</div>
        </div>
      </div>

      {/* Accounts */}
      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Accounts</h2>
          <button onClick={() => setShowAccount(true)} className="inline-flex items-center gap-1 text-sm px-2.5 py-1 rounded-lg bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900">
            <Plus className="w-3.5 h-3.5" /> Account
          </button>
        </div>
        {accountsQ.isLoading ? <Spinner /> : accounts.length === 0 ? (
          <Empty text="No personal accounts yet. Add one to start tracking." />
        ) : (
          <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
            {accounts.map((a) => (
              <div key={a.id} className="flex items-center justify-between px-4 py-2.5 border-t first:border-t-0 border-gray-100 dark:border-gray-800 text-sm">
                <span className="text-gray-900 dark:text-gray-100">{a.name}</span>
                <div className="flex items-center gap-3">
                  <span className="tabular-nums font-medium">${money(a.current_balance)}</span>
                  <button onClick={() => delAccount.mutate(a.id)} className="text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Transactions */}
      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Transactions</h2>
          <button
            onClick={() => setShowTxn(true)}
            disabled={accounts.length === 0}
            className="inline-flex items-center gap-1 text-sm px-2.5 py-1 rounded-lg bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900 disabled:opacity-40"
          >
            <Plus className="w-3.5 h-3.5" /> Transaction
          </button>
        </div>
        {txnsQ.isLoading ? <Spinner /> : txns.length === 0 ? (
          <Empty text="No transactions yet." />
        ) : (
          <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
            {txns.map((t) => (
              <div key={t.id} className="flex items-center justify-between gap-3 px-4 py-2.5 border-t first:border-t-0 border-gray-100 dark:border-gray-800 text-sm">
                <div className="min-w-0">
                  <div className="text-gray-900 dark:text-gray-100 truncate">{t.description}</div>
                  <div className="text-xs text-gray-400">{t.date}{t.category_name ? ` · ${t.category_name}` : ''}</div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className={`tabular-nums font-medium ${t.direction === 'in' ? 'text-green-600 dark:text-green-400' : 'text-gray-900 dark:text-gray-100'}`}>
                    {t.direction === 'in' ? '+' : '−'}${money(t.amount)}
                  </span>
                  <button onClick={() => delTxn.mutate(t.id)} className="text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {showAccount && <AccountModal onClose={() => setShowAccount(false)} onDone={() => { setShowAccount(false); invalidate() }} />}
      {showTxn && <TxnModal accounts={accounts} onClose={() => setShowTxn(false)} onDone={() => { setShowTxn(false); invalidate() }} />}
    </div>
  )
}

function Spinner() { return <div className="py-8 flex justify-center"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div> }
function Empty({ text }: { text: string }) {
  return <div className="px-4 py-8 text-center text-sm text-gray-400 border border-dashed border-gray-200 dark:border-gray-800 rounded-xl">{text}</div>
}

function AccountModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState('')
  const [opening, setOpening] = useState('0.00')
  const m = useMutation({
    mutationFn: () => createPersonalAccount({ name, opening_balance: opening, opening_balance_date: today() }),
    onSuccess: onDone,
  })
  return (
    <Modal title="Add personal account" onClose={onClose}>
      <label className="block text-xs text-gray-500 mb-1">Name</label>
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Personal Chequing" className={inputCls} />
      <label className="block text-xs text-gray-500 mb-1 mt-3">Opening balance</label>
      <input value={opening} onChange={(e) => setOpening(e.target.value)} inputMode="decimal" className={inputCls} />
      <ModalActions onClose={onClose} onSave={() => m.mutate()} saving={m.isPending} disabled={!name} />
    </Modal>
  )
}

function TxnModal({ accounts, onClose, onDone }: { accounts: { id: string; name: string }[]; onClose: () => void; onDone: () => void }) {
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? '')
  const [direction, setDirection] = useState<'in' | 'out'>('out')
  const [amount, setAmount] = useState('')
  const [description, setDescription] = useState('')
  const [d, setD] = useState(today())
  const m = useMutation({
    mutationFn: () => createPersonalTransaction({ account_id: accountId, date: d, direction, amount, description }),
    onSuccess: onDone,
  })
  return (
    <Modal title="Add transaction" onClose={onClose}>
      <label className="block text-xs text-gray-500 mb-1">Account</label>
      <select value={accountId} onChange={(e) => setAccountId(e.target.value)} className={inputCls}>
        {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
      </select>
      <div className="grid grid-cols-2 gap-2 mt-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Direction</label>
          <select value={direction} onChange={(e) => setDirection(e.target.value as 'in' | 'out')} className={inputCls}>
            <option value="out">Money out</option>
            <option value="in">Money in</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Amount</label>
          <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" placeholder="0.00" className={inputCls} />
        </div>
      </div>
      <label className="block text-xs text-gray-500 mb-1 mt-3">Description</label>
      <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="e.g. Groceries" className={inputCls} />
      <label className="block text-xs text-gray-500 mb-1 mt-3">Date</label>
      <input type="date" value={d} onChange={(e) => setD(e.target.value)} className={inputCls} />
      <ModalActions onClose={onClose} onSave={() => m.mutate()} saving={m.isPending} disabled={!accountId || !amount || !description} />
    </Modal>
  )
}

const inputCls = 'w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100'

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bg-white dark:bg-gray-900 rounded-2xl p-5 w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-3">{title}</h3>
        {children}
      </div>
    </div>
  )
}

function ModalActions({ onClose, onSave, saving, disabled }: { onClose: () => void; onSave: () => void; saving: boolean; disabled: boolean }) {
  return (
    <div className="flex justify-end gap-2 mt-5">
      <button onClick={onClose} className="px-3 py-1.5 text-sm rounded-lg text-gray-600 dark:text-gray-400">Cancel</button>
      <button onClick={onSave} disabled={disabled || saving} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900 disabled:opacity-40">
        {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />} Save
      </button>
    </div>
  )
}
