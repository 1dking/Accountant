import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listUsers, createUser, updateUser, updateUserRole, deactivateUser } from '@/api/auth'
import { useAuthStore } from '@/stores/authStore'
import { ROLES } from '@/lib/constants'
import { formatDate } from '@/lib/utils'
import { UserPlus, Pencil, X } from 'lucide-react'

export default function UserManagement() {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('viewer')
  const [formError, setFormError] = useState('')

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editEmail, setEditEmail] = useState('')
  const [editFullName, setEditFullName] = useState('')
  const [editPassword, setEditPassword] = useState('')
  const [editCashbookAccess, setEditCashbookAccess] = useState<'personal' | 'org'>('personal')
  const [editError, setEditError] = useState('')

  const { data } = useQuery({
    queryKey: ['users'],
    queryFn: listUsers,
  })

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) => updateUserRole(userId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })

  const deactivateMutation = useMutation({
    mutationFn: deactivateUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowForm(false)
      setEmail('')
      setFullName('')
      setPassword('')
      setRole('viewer')
      setFormError('')
    },
    onError: (err: any) => {
      setFormError(err.message || 'Failed to create user')
    },
  })

  const editMutation = useMutation({
    mutationFn: ({ userId, data }: { userId: string; data: { email?: string; password?: string; full_name?: string; cashbook_access?: string } }) =>
      updateUser(userId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setEditingId(null)
      setEditError('')
    },
    onError: (err: any) => {
      setEditError(err.message || 'Failed to update user')
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    createMutation.mutate({ email, password, full_name: fullName, role })
  }

  const startEdit = (u: any) => {
    setEditingId(u.id)
    setEditEmail(u.email)
    setEditFullName(u.full_name)
    setEditPassword('')
    setEditCashbookAccess(u.cashbook_access || 'personal')
    setEditError('')
  }

  const handleEdit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingId) return
    const data: { email?: string; password?: string; full_name?: string; cashbook_access?: string } = {}
    const currentUser = users.find((u) => u.id === editingId)
    if (editEmail !== currentUser?.email) data.email = editEmail
    if (editFullName !== currentUser?.full_name) data.full_name = editFullName
    if (editPassword) data.password = editPassword
    if (editCashbookAccess !== currentUser?.cashbook_access) data.cashbook_access = editCashbookAccess
    if (Object.keys(data).length === 0) {
      setEditingId(null)
      return
    }
    editMutation.mutate({ userId: editingId, data })
  }

  const users = data?.data ?? []

  return (
    <section className="bg-white dark:bg-gray-900 border rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">User Management</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          <UserPlus className="w-4 h-4" />
          Add User
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 p-4 bg-gray-50 dark:bg-gray-950 rounded-lg space-y-3">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Create New User</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              placeholder="Full Name"
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm text-gray-900 dark:text-gray-100"
            />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="Email"
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm text-gray-900 dark:text-gray-100"
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              placeholder="Password (min 8 chars)"
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm text-gray-900 dark:text-gray-100"
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
            >
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>
          {formError && (
            <p className="text-sm text-red-600">{formError}</p>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {createMutation.isPending ? 'Creating...' : 'Create User'}
            </button>
            <button
              type="button"
              onClick={() => { setShowForm(false); setFormError('') }}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-200 dark:bg-gray-700 rounded-md hover:bg-gray-300"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Edit form */}
      {editingId && (
        <form onSubmit={handleEdit} className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/30 rounded-lg space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Edit User</h3>
            <button type="button" onClick={() => setEditingId(null)} className="text-gray-400 dark:text-gray-500 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Full Name</label>
              <input
                type="text"
                value={editFullName}
                onChange={(e) => setEditFullName(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm text-gray-900 dark:text-gray-100"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Email</label>
              <input
                type="email"
                value={editEmail}
                onChange={(e) => setEditEmail(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm text-gray-900 dark:text-gray-100"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">New Password (leave blank to keep)</label>
              <input
                type="password"
                value={editPassword}
                onChange={(e) => setEditPassword(e.target.value)}
                minLength={8}
                placeholder="••••••••"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm text-gray-900 dark:text-gray-100"
              />
            </div>
          </div>
          {/* Org Cashbook Access toggle */}
          <div className="flex items-center gap-3">
            <label className="text-xs text-gray-500 dark:text-gray-400">Org Cashbook Access</label>
            {(() => {
              const editTarget = users.find((u) => u.id === editingId)
              const isAdmin = editTarget?.role === 'admin'
              return (
                <button
                  type="button"
                  disabled={isAdmin}
                  onClick={() => setEditCashbookAccess(editCashbookAccess === 'org' ? 'personal' : 'org')}
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                    editCashbookAccess === 'org' || isAdmin ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
                  } ${isAdmin ? 'opacity-70 cursor-not-allowed' : ''}`}
                >
                  <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    editCashbookAccess === 'org' || isAdmin ? 'translate-x-4' : 'translate-x-0'
                  }`} />
                </button>
              )
            })()}
            <span className="text-xs text-gray-400">
              {editCashbookAccess === 'org' ? 'Sees shared org cashbook' : 'Sees personal cashbook only'}
            </span>
            {(() => {
              const editTarget = users.find((u) => u.id === editingId)
              return editTarget?.role === 'admin' ? (
                <span className="text-xs text-amber-500">(Admin always has org access)</span>
              ) : null
            })()}
          </div>
          {editError && (
            <p className="text-sm text-red-600">{editError}</p>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={editMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {editMutation.isPending ? 'Saving...' : 'Save Changes'}
            </button>
            <button
              type="button"
              onClick={() => setEditingId(null)}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-200 dark:bg-gray-700 rounded-md hover:bg-gray-300"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left">
              <th className="pb-2 font-medium text-gray-500 dark:text-gray-400">Name</th>
              <th className="pb-2 font-medium text-gray-500 dark:text-gray-400">Email</th>
              <th className="pb-2 font-medium text-gray-500 dark:text-gray-400">Role</th>
              <th className="pb-2 font-medium text-gray-500 dark:text-gray-400">Cashbook</th>
              <th className="pb-2 font-medium text-gray-500 dark:text-gray-400">Joined</th>
              <th className="pb-2 font-medium text-gray-500 dark:text-gray-400">Status</th>
              <th className="pb-2 font-medium text-gray-500 dark:text-gray-400">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className={`border-b ${editingId === u.id ? 'bg-blue-50' : ''}`}>
                <td className="py-2 text-gray-900 dark:text-gray-100">{u.full_name}</td>
                <td className="py-2 text-gray-600 dark:text-gray-400">{u.email}</td>
                <td className="py-2">
                  <select
                    value={u.role}
                    onChange={(e) => roleMutation.mutate({ userId: u.id, role: e.target.value })}
                    disabled={u.id === user?.id}
                    className="text-sm border rounded px-2 py-1 bg-white dark:bg-gray-900 disabled:opacity-50"
                  >
                    {ROLES.map((r) => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                  </select>
                </td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${
                    u.cashbook_access === 'org' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
                  }`}>
                    {u.cashbook_access === 'org' ? 'Org' : 'Personal'}
                  </span>
                </td>
                <td className="py-2 text-gray-500 dark:text-gray-400">{formatDate(u.created_at)}</td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${u.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="py-2">
                  <div className="flex items-center gap-2">
                    {u.id !== user?.id && (
                      <button
                        onClick={() => startEdit(u)}
                        className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
                      >
                        <Pencil className="w-3 h-3" />
                        Edit
                      </button>
                    )}
                    {u.id !== user?.id && u.is_active && (
                      <button
                        onClick={() => { if (confirm(`Deactivate ${u.full_name}?`)) deactivateMutation.mutate(u.id) }}
                        className="text-xs text-red-600 hover:underline"
                      >
                        Deactivate
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
