import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/authStore'
import { usePublicBranding } from '@/hooks/useBranding'

export default function PasswordResetConfirmPage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const { fetchMe } = useAuthStore()
  const { logoUrl, orgName } = usePublicBranding()

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!token) {
      setError('This reset link is missing its token. Request a new one.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }

    setIsLoading(true)
    try {
      const response: any = await api.post('/auth/password-reset/confirm', {
        token,
        new_password: password,
      })
      localStorage.setItem('access_token', response.data.access_token)
      localStorage.setItem('refresh_token', response.data.refresh_token)
      await fetchMe()
      const isMobile = window.innerWidth < 768
      navigate(isMobile ? '/brain' : '/')
    } catch (err: any) {
      setError(
        err?.message ||
          'This reset link is no longer valid. Request a new one.',
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
      <div className="w-full max-w-md p-8 bg-white dark:bg-gray-900 rounded-lg shadow-md">
        <div className="flex flex-col items-center mb-6">
          {logoUrl ? (
            <img src={logoUrl} alt={orgName} className="h-10 max-w-[200px] object-contain mb-3" />
          ) : (
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-1">
              {orgName}
            </h1>
          )}
          <p className="text-sm text-gray-500 dark:text-gray-400">Choose a new password</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              New password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoFocus
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100 dark:bg-gray-800"
              placeholder="At least 8 characters"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Must include uppercase, lowercase, and a digit.
            </p>
          </div>

          <div>
            <label htmlFor="confirm" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Confirm new password
            </label>
            <input
              id="confirm"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              minLength={8}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100 dark:bg-gray-800"
              placeholder="Re-enter to confirm"
            />
          </div>

          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded-md text-sm" role="alert">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {isLoading ? 'Setting password…' : 'Set new password & sign in'}
          </button>

          <Link
            to="/login"
            className="block text-center text-sm text-blue-600 hover:text-blue-700"
          >
            Back to sign in
          </Link>
        </form>
      </div>
    </div>
  )
}
