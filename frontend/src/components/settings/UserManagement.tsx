import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listUsers, updateUserRole, deactivateUser } from '@/api/auth'
import { useAuthStore } from '@/stores/authStore'
import { ROLES } from '@/lib/constants'
import { formatDate } from '@/lib/utils'

export default function UserManagement() {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()

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

  const users = data?.data ?? []

  return (
    <section className="bg-white border rounded-lg p-6">
      <h2 className="text-lg font-medium text-gray-900 mb-4">User Management</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left">
              <th className="pb-2 font-medium text-gray-500">Name</th>
              <th className="pb-2 font-medium text-gray-500">Email</th>
              <th className="pb-2 font-medium text-gray-500">Role</th>
              <th className="pb-2 font-medium text-gray-500">Joined</th>
              <th className="pb-2 font-medium text-gray-500">Status</th>
              <th className="pb-2 font-medium text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b">
                <td className="py-2 text-gray-900">{u.full_name}</td>
                <td className="py-2 text-gray-600">{u.email}</td>
                <td className="py-2">
                  <select
                    value={u.role}
                    onChange={(e) => roleMutation.mutate({ userId: u.id, role: e.target.value })}
                    disabled={u.id === user?.id}
                    className="text-sm border rounded px-2 py-1 bg-white disabled:opacity-50"
                  >
                    {ROLES.map((r) => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                  </select>
                </td>
                <td className="py-2 text-gray-500">{formatDate(u.created_at)}</td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${u.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="py-2">
                  {u.id !== user?.id && u.is_active && (
                    <button
                      onClick={() => { if (confirm(`Deactivate ${u.full_name}?`)) deactivateMutation.mutate(u.id) }}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Deactivate
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
