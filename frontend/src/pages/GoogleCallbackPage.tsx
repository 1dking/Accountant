import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useAuthStore } from '@/stores/authStore'

export default function GoogleCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { fetchMe } = useAuthStore()
  const [error, setError] = useState('')

  useEffect(() => {
    const code = searchParams.get('code')
    if (!code) {
      setError('No authorization code received from Google.')
      return
    }

    const exchangeCode = async () => {
      try {
        const resp = await fetch('/api/auth/google/callback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code,
            redirect_uri: `${window.location.origin}/auth/google/callback`,
          }),
        })

        if (!resp.ok) {
          const body = await resp.json().catch(() => null)
          throw new Error(body?.error?.message || `Authentication failed (${resp.status})`)
        }

        const { data } = await resp.json()
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
        useAuthStore.setState({ isAuthenticated: true })
        await fetchMe()
        navigate('/', { replace: true })
      } catch (err: any) {
        setError(err.message || 'Google authentication failed.')
      }
    }

    exchangeCode()
  }, [searchParams, navigate, fetchMe])

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="w-full max-w-md p-8 bg-white dark:bg-gray-900 rounded-lg shadow-md text-center">
          <div className="text-red-600 dark:text-red-400 mb-4">{error}</div>
          <a href="/login" className="text-blue-600 hover:underline">Back to login</a>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
      <div className="w-full max-w-md p-8 bg-white dark:bg-gray-900 rounded-lg shadow-md text-center">
        <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
        <p className="text-gray-600 dark:text-gray-400">Signing in with Google...</p>
      </div>
    </div>
  )
}
