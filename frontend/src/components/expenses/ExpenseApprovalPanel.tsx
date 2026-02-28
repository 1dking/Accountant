import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { requestExpenseApproval, approveExpense, rejectExpense } from '@/api/accounting'
import { listUsers } from '@/api/auth'
import { useAuthStore } from '@/stores/authStore'
import { formatDate } from '@/lib/utils'
import { ShieldCheck, ShieldX, Clock, Send } from 'lucide-react'
import type { Expense, ExpenseApproval } from '@/types/models'

interface ExpenseApprovalPanelProps {
  expense: Expense
  approval: ExpenseApproval | null
}

export default function ExpenseApprovalPanel({ expense, approval }: ExpenseApprovalPanelProps) {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const canManage = user?.role === 'admin' || user?.role === 'accountant'

  const [assignedTo, setAssignedTo] = useState('')
  const [comment, setComment] = useState('')
  const [showReject, setShowReject] = useState(false)

  const { data: usersData } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers(),
    enabled: canManage && !approval,
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['expense', expense.id] })
    queryClient.invalidateQueries({ queryKey: ['pending-expense-approvals'] })
  }

  const requestMutation = useMutation({
    mutationFn: () => requestExpenseApproval(expense.id, assignedTo),
    onSuccess: invalidate,
  })

  const approveMutation = useMutation({
    mutationFn: () => approveExpense(expense.id, comment || undefined),
    onSuccess: () => { setComment(''); invalidate() },
  })

  const rejectMutation = useMutation({
    mutationFn: () => rejectExpense(expense.id, comment || undefined),
    onSuccess: () => { setComment(''); setShowReject(false); invalidate() },
  })

  const users = usersData?.data?.filter((u) => u.id !== user?.id && u.is_active) ?? []
  const isAdmin = user?.role === 'admin'
  const isAssignee = approval && user?.id === approval.assigned_to
  const isRequester = approval && user?.id === approval.requested_by
  const canResolve = isAssignee || isAdmin

  // Already resolved
  if (approval && approval.status !== 'pending') {
    return (
      <div className="bg-white rounded-lg border p-4">
        <h3 className="font-semibold text-gray-900 text-sm mb-3">Approval</h3>
        <div className="flex items-center gap-2">
          {approval.status === 'approved' ? (
            <ShieldCheck className="h-5 w-5 text-green-600" />
          ) : (
            <ShieldX className="h-5 w-5 text-red-600" />
          )}
          <div>
            <p className={`text-sm font-medium ${approval.status === 'approved' ? 'text-green-700' : 'text-red-700'}`}>
              {approval.status === 'approved' ? 'Approved' : 'Rejected'}
            </p>
            {approval.resolved_at && (
              <p className="text-xs text-gray-500">{formatDate(approval.resolved_at)}</p>
            )}
          </div>
        </div>
        {approval.comment && (
          <p className="mt-2 text-sm text-gray-600 bg-gray-50 rounded p-2">{approval.comment}</p>
        )}
      </div>
    )
  }

  // Pending approval - show actions for the assignee
  if (approval && approval.status === 'pending') {
    return (
      <div className="bg-amber-50 rounded-lg border border-amber-200 p-4">
        <h3 className="font-semibold text-amber-900 text-sm mb-3 flex items-center gap-1.5">
          <Clock className="h-4 w-4" />
          Pending Approval
        </h3>
        <p className="text-sm text-amber-800 mb-3">
          {isAssignee
            ? 'This expense is waiting for your review.'
            : isAdmin
              ? 'You can approve or reject this expense as an admin.'
              : isRequester
                ? 'You submitted this for approval.'
                : 'This expense is pending approval.'}
        </p>

        {canResolve && (
          <div className="space-y-2">
            {showReject ? (
              <div className="space-y-2">
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  rows={2}
                  placeholder="Reason for rejection..."
                  className="w-full px-3 py-1.5 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-red-400"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => rejectMutation.mutate()}
                    disabled={rejectMutation.isPending}
                    className="flex-1 px-3 py-1.5 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-50"
                  >
                    {rejectMutation.isPending ? 'Rejecting...' : 'Confirm Reject'}
                  </button>
                  <button
                    onClick={() => { setShowReject(false); setComment('') }}
                    className="px-3 py-1.5 text-sm border rounded-md hover:bg-white"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  rows={2}
                  placeholder="Optional comment..."
                  className="w-full px-3 py-1.5 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-amber-400"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => approveMutation.mutate()}
                    disabled={approveMutation.isPending}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50"
                  >
                    <ShieldCheck className="h-4 w-4" />
                    {approveMutation.isPending ? 'Approving...' : 'Approve'}
                  </button>
                  <button
                    onClick={() => setShowReject(true)}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-700 border border-red-300 rounded-md hover:bg-red-50"
                  >
                    <ShieldX className="h-4 w-4" />
                    Reject
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {(approveMutation.isError || rejectMutation.isError) && (
          <p className="mt-2 text-xs text-red-600">
            {((approveMutation.error || rejectMutation.error) as Error)?.message || 'Action failed'}
          </p>
        )}
      </div>
    )
  }

  // No approval yet - show request form
  if (!canManage) return null

  const handleAdminApprove = () => {
    // Admin self-assigns and immediately approves
    requestExpenseApproval(expense.id, user!.id).then(() => {
      approveExpense(expense.id, 'Admin approved').then(() => invalidate())
    })
  }

  return (
    <div className="bg-white rounded-lg border p-4">
      <h3 className="font-semibold text-gray-900 text-sm mb-3">Approval</h3>
      <div className="space-y-3">
        {isAdmin && (
          <button
            onClick={handleAdminApprove}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700"
          >
            <ShieldCheck className="h-4 w-4" />
            Approve (Admin)
          </button>
        )}
        <div>
          <label className="text-xs font-medium text-gray-500">Or assign to a reviewer</label>
          <select
            value={assignedTo}
            onChange={(e) => setAssignedTo(e.target.value)}
            className="w-full mt-1 px-3 py-1.5 text-sm border rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select a reviewer...</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name} ({u.role})
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={() => requestMutation.mutate()}
          disabled={!assignedTo || requestMutation.isPending}
          className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
          {requestMutation.isPending ? 'Submitting...' : 'Submit for Approval'}
        </button>
        {requestMutation.isError && (
          <p className="text-xs text-red-600">
            {(requestMutation.error as Error)?.message || 'Failed to request approval'}
          </p>
        )}
      </div>
    </div>
  )
}
