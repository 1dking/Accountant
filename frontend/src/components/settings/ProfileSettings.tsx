import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { updateProfile } from '@/api/auth'
import { useAuthStore } from '@/stores/authStore'

export default function ProfileSettings() {
  const { user, fetchMe } = useAuthStore()
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [newPassword, setNewPassword] = useState('')
  const [msg, setMsg] = useState('')

  const mutation = useMutation({
    mutationFn: (data: { full_name?: string; password?: string }) => updateProfile(data),
    onSuccess: () => {
      fetchMe()
      setMsg('Profile updated')
      setNewPassword('')
      setTimeout(() => setMsg(''), 3000)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const updates: Record<string, string> = {}
    if (fullName !== user?.full_name) updates.full_name = fullName
    if (newPassword) updates.password = newPassword
    if (Object.keys(updates).length > 0) mutation.mutate(updates)
  }

  return (
    <section className="bg-white dark:bg-gray-900 border rounded-lg p-6">
      <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Profile</h2>
      <form onSubmit={handleSubmit} className="space-y-4 max-w-md">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Full Name</label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
          <input
            type="email"
            value={user?.email || ''}
            disabled
            className="w-full px-3 py-2 border rounded-md bg-gray-50 dark:bg-gray-950 text-gray-500 dark:text-gray-400"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">New Password</label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Leave empty to keep current"
            minLength={8}
            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
          >
            Save Changes
          </button>
          {msg && <span className="text-sm text-green-600">{msg}</span>}
        </div>
      </form>
    </section>
  )
}
