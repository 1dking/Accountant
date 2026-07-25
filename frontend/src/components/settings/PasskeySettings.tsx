import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Fingerprint, Trash2, Plus, ShieldCheck } from 'lucide-react'
import {
  listPasskeys,
  registerPasskey,
  removePasskey,
  isPasskeySupported,
  type PasskeyInfo,
} from '@/api/webauthn'
import { formatDate } from '@/lib/utils'

export default function PasskeySettings() {
  const queryClient = useQueryClient()
  const [deviceName, setDeviceName] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const supported = isPasskeySupported()

  const { data } = useQuery({
    queryKey: ['passkeys'],
    queryFn: listPasskeys,
    enabled: supported,
  })

  const registerMutation = useMutation({
    mutationFn: () => registerPasskey(deviceName.trim() || 'Passkey'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['passkeys'] })
      setDeviceName('')
      setErr('')
      setMsg('Passkey registered.')
      setTimeout(() => setMsg(''), 3000)
    },
    onError: (e: any) => {
      setErr(e?.message || 'Could not register passkey.')
    },
  })

  const removeMutation = useMutation({
    mutationFn: (id: string) => removePasskey(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['passkeys'] }),
  })

  const passkeys: PasskeyInfo[] = data?.data ?? []

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-blue-500" />
          Passkeys (two-factor)
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          A passkey (Face ID, Touch ID, Windows Hello, or a security key) is a phishing-resistant
          second factor. It works alongside your authenticator app — either one satisfies
          two-factor authentication.
        </p>
      </div>

      {!supported && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
          This browser doesn&apos;t support passkeys. Use an authenticator-app (TOTP) code instead.
        </div>
      )}

      {msg && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-700">{msg}</div>
      )}
      {err && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{err}</div>
      )}

      {supported && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            registerMutation.mutate()
          }}
          className="bg-white dark:bg-gray-900 border rounded-lg p-4 flex flex-col sm:flex-row gap-3 sm:items-end"
        >
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Device name
            </label>
            <input
              type="text"
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
              placeholder="e.g. My iPhone, Work laptop, YubiKey"
              maxLength={100}
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={registerMutation.isPending}
            className="flex items-center justify-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <Plus className="w-4 h-4" />
            {registerMutation.isPending ? 'Waiting for device…' : 'Add a passkey'}
          </button>
        </form>
      )}

      <div className="space-y-2">
        {passkeys.map((pk) => (
          <div
            key={pk.id}
            className="bg-white dark:bg-gray-900 border rounded-lg p-4 flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <Fingerprint className="w-5 h-5 text-blue-500" />
              <div>
                <div className="font-medium text-gray-900 dark:text-gray-100">{pk.device_name}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  Added {formatDate(pk.created_at)}
                  {pk.last_used_at ? ` · Last used ${formatDate(pk.last_used_at)}` : ' · Never used'}
                </div>
              </div>
            </div>
            <button
              onClick={() => {
                if (confirm(`Remove passkey "${pk.device_name}"?`)) removeMutation.mutate(pk.id)
              }}
              className="p-1.5 text-red-500 hover:bg-red-50 rounded"
              title="Remove passkey"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}

        {supported && passkeys.length === 0 && (
          <div className="text-center py-8 bg-white dark:bg-gray-900 border rounded-lg">
            <Fingerprint className="w-9 h-9 text-gray-300 mx-auto mb-2" />
            <p className="text-gray-500 dark:text-gray-400 text-sm">No passkeys registered yet.</p>
          </div>
        )}
      </div>

      <div className="bg-gray-50 dark:bg-gray-950 border rounded-lg p-4 text-xs text-gray-500 dark:text-gray-400">
        If you lose all your passkeys, you can still sign in with your authenticator app (TOTP) and
        recovery codes. We never send a passkey reset link by email — that would reintroduce the
        phishing risk passkeys are designed to remove.
      </div>
    </div>
  )
}
