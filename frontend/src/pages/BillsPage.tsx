import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Plus, ReceiptText, Loader2, Check, X, Trash2, CheckCircle2, Ban, Banknote } from 'lucide-react'
import {
  listBills,
  createBill,
  approveBill,
  payBill,
  voidBill,
  listChartAccounts,
  type VendorBill,
  type VendorBillLineInput,
  type BillStatus,
  type ChartAccount,
} from '@/api/accounting'
import { formatDate } from '@/lib/utils'

function money(n: string): string {
  return parseFloat(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const STATUS_STYLE: Record<BillStatus, string> = {
  draft: 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300',
  pending: 'bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300',
  approved: 'bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300',
  paid: 'bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-300',
  void: 'bg-red-50 dark:bg-red-950 text-red-600 dark:text-red-400',
}

export default function BillsPage() {
  const [creating, setCreating] = useState(false)
  const [paying, setPaying] = useState<VendorBill | null>(null)
  const { data, isLoading } = useQuery({ queryKey: ['bills'], queryFn: () => listBills() })
  const bills: VendorBill[] = data?.data ?? []

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <ReceiptText className="w-6 h-6 text-gray-700 dark:text-gray-300" />
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Bills (Accounts Payable)</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Money you owe vendors. Approving a bill posts the expense and the payable; paying it clears
            the payable against cash.
          </p>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" /> New bill
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      ) : bills.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-gray-200 dark:border-gray-700 rounded-xl">
          <ReceiptText className="w-10 h-10 mx-auto text-gray-300 dark:text-gray-600" />
          <p className="mt-3 text-gray-600 dark:text-gray-300 font-medium">No bills yet</p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Enter a vendor bill to track what you owe and when it's due.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {bills.map((b) => (
            <BillRow key={b.id} bill={b} onPay={() => setPaying(b)} />
          ))}
        </div>
      )}

      {creating && <NewBillModal onClose={() => setCreating(false)} />}
      {paying && <PayModal bill={paying} onClose={() => setPaying(null)} />}
    </div>
  )
}

function BillRow({ bill, onPay }: { bill: VendorBill; onPay: () => void }) {
  const queryClient = useQueryClient()
  const [expanded, setExpanded] = useState(false)
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['bills'] })
    queryClient.invalidateQueries({ queryKey: ['trial-balance'] })
    queryClient.invalidateQueries({ queryKey: ['general-ledger'] })
  }
  const approve = useMutation({
    mutationFn: () => approveBill(bill.id),
    onSuccess: () => { invalidate(); toast.success('Bill approved and posted') },
    onError: (e: any) => toast.error(e?.message || 'Failed to approve'),
  })
  const voidM = useMutation({
    mutationFn: () => voidBill(bill.id),
    onSuccess: () => { invalidate(); toast.success('Bill voided') },
    onError: (e: any) => toast.error(e?.message || 'Failed to void'),
  })

  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3">
        <button onClick={() => setExpanded((v) => !v)} className="flex items-center gap-3 flex-1 text-left min-w-0">
          <span className="font-mono text-xs text-gray-400 w-24 shrink-0 truncate">{bill.bill_number}</span>
          <span className="text-sm text-gray-900 dark:text-gray-100 flex-1 truncate">{bill.vendor_name}</span>
          <span className="text-xs text-gray-400 w-24 shrink-0">{formatDate(bill.bill_date)}</span>
          <span className={`text-[11px] px-1.5 py-0.5 rounded ${STATUS_STYLE[bill.status]}`}>{bill.status}</span>
          <span className="text-sm font-medium tabular-nums w-24 text-right">${money(bill.total_amount)}</span>
        </button>
      </div>
      {expanded && (
        <div className="border-t border-gray-100 dark:border-gray-800 px-4 py-3 bg-gray-50/50 dark:bg-gray-900/30 space-y-2">
          <table className="w-full text-sm">
            <tbody>
              {bill.lines.map((ln) => (
                <tr key={ln.id} className="text-gray-700 dark:text-gray-300">
                  <td className="py-0.5">
                    <span className="font-mono text-gray-400 mr-2">{ln.account_code}</span>
                    {ln.account_name}
                    {ln.description && <span className="text-gray-400"> — {ln.description}</span>}
                  </td>
                  <td className="py-0.5 text-right tabular-nums">{money(ln.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex justify-end gap-2 pt-1">
            {(bill.status === 'draft' || bill.status === 'pending') && (
              <button
                onClick={() => approve.mutate()}
                disabled={approve.isPending}
                className="flex items-center gap-1 text-xs text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950 px-2 py-1 rounded disabled:opacity-50"
              >
                <CheckCircle2 className="w-3.5 h-3.5" /> Approve
              </button>
            )}
            {bill.status === 'approved' && (
              <button
                onClick={onPay}
                className="flex items-center gap-1 text-xs text-green-600 hover:bg-green-50 dark:hover:bg-green-950 px-2 py-1 rounded"
              >
                <Banknote className="w-3.5 h-3.5" /> Pay
              </button>
            )}
            {bill.status !== 'paid' && bill.status !== 'void' && (
              <button
                onClick={() => voidM.mutate()}
                disabled={voidM.isPending}
                className="flex items-center gap-1 text-xs text-red-600 hover:bg-red-50 dark:hover:bg-red-950 px-2 py-1 rounded disabled:opacity-50"
              >
                <Ban className="w-3.5 h-3.5" /> Void
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

type DraftLine = { account_id: string; description: string; amount: string }
const emptyLine = (): DraftLine => ({ account_id: '', description: '', amount: '' })

function NewBillModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [vendorName, setVendorName] = useState('')
  const [billNumber, setBillNumber] = useState('')
  const [billDate, setBillDate] = useState(new Date().toISOString().slice(0, 10))
  const [dueDate, setDueDate] = useState('')
  const [lines, setLines] = useState<DraftLine[]>([emptyLine()])

  const { data: accountsData } = useQuery({ queryKey: ['coa-accounts', false], queryFn: () => listChartAccounts({}) })
  // Bills post to expense (or asset) accounts.
  const accounts: ChartAccount[] = (accountsData?.data ?? []).filter(
    (a) => a.account_type === 'expense' || a.account_type === 'asset',
  )

  const total = useMemo(() => lines.reduce((s, l) => s + (parseFloat(l.amount) || 0), 0), [lines])
  const setLine = (i: number, patch: Partial<DraftLine>) =>
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))

  const mutation = useMutation({
    mutationFn: () => {
      const payloadLines: VendorBillLineInput[] = lines
        .filter((l) => l.account_id && parseFloat(l.amount) > 0)
        .map((l) => ({ account_id: l.account_id, description: l.description || null, amount: (parseFloat(l.amount)).toFixed(2) }))
      return createBill({
        vendor_name: vendorName,
        bill_number: billNumber || null,
        bill_date: billDate,
        due_date: dueDate || null,
        lines: payloadLines,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bills'] })
      toast.success('Bill created')
      onClose()
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to create bill'),
  })

  const canSubmit = vendorName.trim() && total > 0 && lines.some((l) => l.account_id && parseFloat(l.amount) > 0)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">New Bill</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"><X className="w-5 h-5" /></button>
        </div>

        <div className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Vendor</label>
              <input type="text" value={vendorName} onChange={(e) => setVendorName(e.target.value)} placeholder="Acme Supplies"
                className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Bill # (optional)</label>
              <input type="text" value={billNumber} onChange={(e) => setBillNumber(e.target.value)} placeholder="auto"
                className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Bill date</label>
                <input type="date" value={billDate} onChange={(e) => setBillDate(e.target.value)}
                  className="w-full px-2 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Due</label>
                <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)}
                  className="w-full px-2 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100" />
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center text-xs text-gray-400 px-1">
              <span className="flex-1">Expense account</span>
              <span className="w-40">Description</span>
              <span className="w-24 text-right">Amount</span>
              <span className="w-8" />
            </div>
            {lines.map((line, i) => (
              <div key={i} className="flex items-center gap-2">
                <select value={line.account_id} onChange={(e) => setLine(i, { account_id: e.target.value })}
                  className="flex-1 px-2 py-1.5 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100">
                  <option value="">Select account…</option>
                  {accounts.map((a) => (<option key={a.id} value={a.id}>{a.code} — {a.name}</option>))}
                </select>
                <input type="text" value={line.description} onChange={(e) => setLine(i, { description: e.target.value })}
                  className="w-40 px-2 py-1.5 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100" />
                <input type="number" step="0.01" min="0" value={line.amount} onChange={(e) => setLine(i, { amount: e.target.value })}
                  className="w-24 px-2 py-1.5 border rounded-lg text-sm text-right dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100" />
                <button onClick={() => setLines((p) => (p.length > 1 ? p.filter((_, idx) => idx !== i) : p))}
                  disabled={lines.length <= 1} className="p-1.5 text-gray-400 hover:text-red-600 disabled:opacity-30 rounded">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
            <button onClick={() => setLines((p) => [...p, emptyLine()])} className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 px-1 pt-1">
              <Plus className="w-4 h-4" /> Add line
            </button>
          </div>

          <div className="flex items-center justify-end gap-2 text-sm border-t dark:border-gray-700 pt-3">
            <span className="text-gray-400">Total</span>
            <span className="tabular-nums font-medium text-gray-900 dark:text-gray-100">${money(total.toFixed(2))}</span>
          </div>
        </div>

        <div className="flex justify-end gap-2 p-4 border-t dark:border-gray-700">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">Cancel</button>
          <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !canSubmit}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Create bill
          </button>
        </div>
      </div>
    </div>
  )
}

function PayModal({ bill, onClose }: { bill: VendorBill; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [cashId, setCashId] = useState('')
  const [payDate, setPayDate] = useState(new Date().toISOString().slice(0, 10))

  const { data: accountsData } = useQuery({ queryKey: ['coa-accounts', false], queryFn: () => listChartAccounts({}) })
  const assets: ChartAccount[] = (accountsData?.data ?? []).filter((a) => a.account_type === 'asset')

  const mutation = useMutation({
    mutationFn: () => payBill(bill.id, cashId, payDate),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bills'] })
      queryClient.invalidateQueries({ queryKey: ['trial-balance'] })
      queryClient.invalidateQueries({ queryKey: ['general-ledger'] })
      toast.success('Bill paid')
      onClose()
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to record payment'),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Pay {bill.bill_number}</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-4 space-y-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Paying <span className="font-medium text-gray-900 dark:text-gray-100">${money(bill.total_amount)}</span> to {bill.vendor_name}.
          </p>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Pay from</label>
            <select value={cashId} onChange={(e) => setCashId(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100">
              <option value="">Select cash / bank account…</option>
              {assets.map((a) => (<option key={a.id} value={a.id}>{a.code} — {a.name}</option>))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Payment date</label>
            <input type="date" value={payDate} onChange={(e) => setPayDate(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100" />
          </div>
        </div>
        <div className="flex justify-end gap-2 p-4 border-t dark:border-gray-700">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">Cancel</button>
          <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !cashId}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50">
            {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Banknote className="w-4 h-4" />} Record payment
          </button>
        </div>
      </div>
    </div>
  )
}
