import { useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getExpense, updateExpense, deleteExpense, listCategories, getExpenseApproval } from '@/api/accounting'
import CategoryBadge from '@/components/expenses/CategoryBadge'
import ExpenseApprovalPanel from '@/components/expenses/ExpenseApprovalPanel'
import { useAuthStore } from '@/stores/authStore'
import { formatDate } from '@/lib/utils'
import { EXPENSE_STATUSES, PAYMENT_METHODS } from '@/lib/constants'
import { ArrowLeft, FileText, Pencil, Trash2 } from 'lucide-react'
import type { ExpenseStatus, PaymentMethod } from '@/types/models'

function formatCurrency(amount: number, currency: string = 'USD'): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount)
}

export default function ExpenseDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const canEdit = user?.role === 'admin' || user?.role === 'accountant'

  const [editing, setEditing] = useState(false)
  const [vendorName, setVendorName] = useState('')
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState('')
  const [expenseDate, setExpenseDate] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [paymentMethod, setPaymentMethod] = useState('')
  const [status, setStatus] = useState('')
  const [notes, setNotes] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['expense', id],
    queryFn: () => getExpense(id!),
    enabled: !!id,
  })

  const { data: categoriesData } = useQuery({
    queryKey: ['expense-categories'],
    queryFn: () => listCategories(),
  })

  const { data: approvalData } = useQuery({
    queryKey: ['expense-approval', id],
    queryFn: () => getExpenseApproval(id!),
    enabled: !!id,
  })

  const updateMutation = useMutation({
    mutationFn: () =>
      updateExpense(id!, {
        vendor_name: vendorName || undefined,
        description: description || undefined,
        amount: amount ? parseFloat(amount) : undefined,
        date: expenseDate || undefined,
        category_id: categoryId || undefined,
        payment_method: (paymentMethod as PaymentMethod) || undefined,
        status: (status as ExpenseStatus) || undefined,
        notes: notes || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense', id] })
      setEditing(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteExpense(id!),
    onSuccess: () => navigate('/expenses'),
  })

  const expense = data?.data
  const categories = categoriesData?.data ?? []
  const approval = approvalData?.data ?? null

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/3" />
          <div className="h-64 bg-gray-200 rounded" />
        </div>
      </div>
    )
  }

  if (!expense) {
    return (
      <div className="p-6 text-center">
        <h2 className="text-lg font-medium text-gray-900">Expense not found</h2>
        <button onClick={() => navigate('/expenses')} className="mt-2 text-blue-600 hover:underline">
          Back to expenses
        </button>
      </div>
    )
  }

  const statusInfo = EXPENSE_STATUSES.find((s) => s.value === expense.status)

  const startEditing = () => {
    setVendorName(expense.vendor_name || '')
    setDescription(expense.description || '')
    setAmount(String(expense.amount))
    setExpenseDate(expense.date)
    setCategoryId(expense.category_id || '')
    setPaymentMethod(expense.payment_method || '')
    setStatus(expense.status)
    setNotes(expense.notes || '')
    setEditing(true)
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => navigate('/expenses')}
          className="flex items-center gap-1 text-sm text-blue-600 hover:underline mb-3"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to expenses
        </button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {expense.vendor_name || 'Expense'}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              {statusInfo && (
                <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${statusInfo.color}`}>
                  {statusInfo.label}
                </span>
              )}
              <CategoryBadge category={expense.category} />
            </div>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold text-gray-900">
              {formatCurrency(expense.amount, expense.currency)}
            </p>
            <p className="text-sm text-gray-500">{formatDate(expense.date)}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Details card */}
          <div className="bg-white rounded-lg border p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">Details</h3>
              <div className="flex gap-2">
                {canEdit && !editing && (
                  <button onClick={startEditing} className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700">
                    <Pencil className="h-3.5 w-3.5" />
                    Edit
                  </button>
                )}
                {user?.role === 'admin' && (
                  <button
                    onClick={() => { if (confirm('Delete this expense?')) deleteMutation.mutate() }}
                    className="flex items-center gap-1 text-sm text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete
                  </button>
                )}
              </div>
            </div>

            {editing ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-gray-500">Vendor</label>
                    <input value={vendorName} onChange={(e) => setVendorName(e.target.value)}
                      className="w-full mt-1 px-3 py-1.5 text-sm border rounded-md" placeholder="Vendor name" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500">Amount</label>
                    <input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)}
                      className="w-full mt-1 px-3 py-1.5 text-sm border rounded-md" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500">Date</label>
                    <input type="date" value={expenseDate} onChange={(e) => setExpenseDate(e.target.value)}
                      className="w-full mt-1 px-3 py-1.5 text-sm border rounded-md" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500">Category</label>
                    <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}
                      className="w-full mt-1 px-3 py-1.5 text-sm border rounded-md bg-white">
                      <option value="">Uncategorized</option>
                      {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500">Payment Method</label>
                    <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}
                      className="w-full mt-1 px-3 py-1.5 text-sm border rounded-md bg-white">
                      <option value="">Not specified</option>
                      {PAYMENT_METHODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500">Status</label>
                    <select value={status} onChange={(e) => setStatus(e.target.value)}
                      className="w-full mt-1 px-3 py-1.5 text-sm border rounded-md bg-white">
                      {EXPENSE_STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500">Description</label>
                  <input value={description} onChange={(e) => setDescription(e.target.value)}
                    className="w-full mt-1 px-3 py-1.5 text-sm border rounded-md" placeholder="Description" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500">Notes</label>
                  <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3}
                    className="w-full mt-1 px-3 py-1.5 text-sm border rounded-md" placeholder="Additional notes..." />
                </div>
                <div className="flex gap-2">
                  <button onClick={() => updateMutation.mutate()}
                    className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700">
                    Save
                  </button>
                  <button onClick={() => setEditing(false)}
                    className="px-4 py-1.5 text-sm border rounded-md hover:bg-gray-50">
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Vendor</span>
                  <p className="text-gray-900 font-medium">{expense.vendor_name || '-'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Amount</span>
                  <p className="text-gray-900 font-medium">{formatCurrency(expense.amount, expense.currency)}</p>
                </div>
                <div>
                  <span className="text-gray-500">Date</span>
                  <p className="text-gray-900">{formatDate(expense.date)}</p>
                </div>
                <div>
                  <span className="text-gray-500">Payment Method</span>
                  <p className="text-gray-900 capitalize">{expense.payment_method?.replace('_', ' ') || '-'}</p>
                </div>
                {expense.tax_amount != null && (
                  <div>
                    <span className="text-gray-500">Tax</span>
                    <p className="text-gray-900">{formatCurrency(expense.tax_amount, expense.currency)}</p>
                  </div>
                )}
                {expense.description && (
                  <div className="col-span-2">
                    <span className="text-gray-500">Description</span>
                    <p className="text-gray-900">{expense.description}</p>
                  </div>
                )}
                {expense.notes && (
                  <div className="col-span-2">
                    <span className="text-gray-500">Notes</span>
                    <p className="text-gray-700">{expense.notes}</p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Line items */}
          {expense.line_items.length > 0 && (
            <div className="bg-white rounded-lg border p-5">
              <h3 className="font-semibold text-gray-900 mb-3">Line Items</h3>
              <table className="w-full text-sm">
                <thead className="border-b">
                  <tr>
                    <th className="text-left pb-2 text-gray-500 font-medium">Item</th>
                    <th className="text-right pb-2 text-gray-500 font-medium">Qty</th>
                    <th className="text-right pb-2 text-gray-500 font-medium">Unit Price</th>
                    <th className="text-right pb-2 text-gray-500 font-medium">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {expense.line_items.map((item) => (
                    <tr key={item.id}>
                      <td className="py-2 text-gray-900">{item.description}</td>
                      <td className="py-2 text-right text-gray-600">{item.quantity ?? '-'}</td>
                      <td className="py-2 text-right text-gray-600">
                        {item.unit_price != null ? formatCurrency(item.unit_price, expense.currency) : '-'}
                      </td>
                      <td className="py-2 text-right font-medium text-gray-900">
                        {formatCurrency(item.total, expense.currency)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Linked receipt */}
          {expense.document_id && (
            <div className="bg-white rounded-lg border p-4">
              <h3 className="font-semibold text-gray-900 text-sm mb-2">Linked Receipt</h3>
              <button
                onClick={() => navigate(`/documents/${expense.document_id}`)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-blue-600 bg-blue-50 rounded-md hover:bg-blue-100"
              >
                <FileText className="h-4 w-4" />
                View Document
              </button>
            </div>
          )}

          {/* AI suggestion */}
          {expense.ai_category_suggestion && (
            <div className="bg-purple-50 rounded-lg border border-purple-200 p-4">
              <h3 className="font-semibold text-purple-900 text-sm mb-1">AI Suggestion</h3>
              <p className="text-sm text-purple-700 capitalize">
                {expense.ai_category_suggestion.replace(/_/g, ' ')}
              </p>
            </div>
          )}

          {/* Approval */}
          <ExpenseApprovalPanel expense={expense} approval={approval} />
        </div>
      </div>
    </div>
  )
}
