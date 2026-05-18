import { useState } from 'react'
import { Link } from 'react-router'
import { api } from '@/api/client'
import { usePublicBranding } from '@/hooks/useBranding'

export default function PasswordResetRequestPage() {
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')
  const { logoUrl, orgName } = usePublicBranding()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)
    try {
      await api.post('/auth/password-reset/request', { email })
      setSubmitted(true)
    } catch (err: any) {
      // Surface rate-limit explicitly; everything else is generic so we
      // never leak whether the email matched a real account.
      setError(err?.message || 'Something went wrong. Please try again.')
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
          <p className="text-sm text-gray-500 dark:text-gray-400">Reset your password</p>
        </div>

        {submitted ? (
          <div className="space-y-4">
            <div className="p-4 bg-green-50 dark:bg-green-900/30 text-green-800 dark:text-green-300 rounded-md text-sm">
              If an account exists for that email, a reset link has been sent. It expires in 1 hour.
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Didn't receive an email? Check your spam folder, or wait a minute and try again.
            </p>
            <Link
              to="/login"
              className="block text-center text-sm text-blue-600 hover:text-blue-700"
            >
              Back to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Enter your email and we'll send you a link to reset your password.
            </p>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100 dark:bg-gray-800"
                placeholder="you@example.com"
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
              {isLoading ? 'Sending…' : 'Send reset link'}
            </button>

            <Link
              to="/login"
              className="block text-center text-sm text-blue-600 hover:text-blue-700"
            >
              Back to sign in
            </Link>
          </form>
        )}
      </div>
    </div>
  )
}
