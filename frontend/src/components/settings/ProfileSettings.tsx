import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { updateProfile } from '@/api/auth'
import { getMyNumber } from '@/api/communication'
import { useAuthStore } from '@/stores/authStore'
import VoicemailGreetingEditor from './VoicemailGreetingEditor'
import { useTranslation } from 'react-i18next'

export default function ProfileSettings() {
  const { t } = useTranslation('ui')
  const { user, fetchMe } = useAuthStore()
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [newPassword, setNewPassword] = useState('')
  const [fallbackPhone, setFallbackPhone] = useState(user?.fallback_phone || '')
  const [msg, setMsg] = useState('')

  const { data: myNumberData, isLoading: myNumberLoading } = useQuery({
    queryKey: ['my-number'],
    queryFn: () => getMyNumber(),
  })
  const myNumber = myNumberData?.data ?? null

  const mutation = useMutation({
    mutationFn: (data: { full_name?: string; password?: string; fallback_phone?: string }) =>
      updateProfile(data),
    onSuccess: () => {
      fetchMe()
      setMsg(t('ui:ProfileSettings.profileUpdated'))
      setNewPassword('')
      setTimeout(() => setMsg(''), 3000)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const updates: Record<string, string> = {}
    if (fullName !== user?.full_name) updates.full_name = fullName
    if (newPassword) updates.password = newPassword
    if (fallbackPhone !== (user?.fallback_phone || '')) updates.fallback_phone = fallbackPhone
    if (Object.keys(updates).length > 0) mutation.mutate(updates)
  }

  return (
    <div className="space-y-4">
      <section className="bg-white dark:bg-gray-900 border rounded-lg p-6">
      <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">{t('ui:ProfileSettings.profile')}</h2>
      <form onSubmit={handleSubmit} className="space-y-4 max-w-md">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:ProfileSettings.fullName')}</label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:ProfileSettings.email')}</label>
          <input
            type="email"
            value={user?.email || ''}
            disabled
            className="w-full px-3 py-2 border rounded-md bg-gray-50 dark:bg-gray-950 text-gray-500 dark:text-gray-400"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:ProfileSettings.newPassword')}</label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder={t('ui:ProfileSettings.leaveEmptyToKeepCurrent')}
            minLength={8}
            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
           {t('ui:ProfileSettings.fallbackPhoneCell')}
          </label>
          <input
            type="tel"
            value={fallbackPhone}
            onChange={(e) => setFallbackPhone(e.target.value)}
            placeholder="+12895551234"
            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
           {t('ui:ProfileSettings.e164FormatWhenSomeone')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
          >
           {t('ui:ProfileSettings.saveChanges')}
          </button>
          {msg && <span className="text-sm text-green-600">{msg}</span>}
        </div>
      </form>
      </section>

      <section className="bg-white dark:bg-gray-900 border rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
         {t('ui:ProfileSettings.yourPhoneNumber')}
        </h2>
        {myNumberLoading ? (
          <div className="text-sm text-gray-500 dark:text-gray-400">{t('ui:ProfileSettings.loading')}</div>
        ) : myNumber ? (
          <div>
            <div className="font-mono text-base text-gray-900 dark:text-gray-100">
              {myNumber.phone_number}
            </div>
            {myNumber.friendly_name && (
              <div className="text-sm text-gray-500 dark:text-gray-400">
                {myNumber.friendly_name}
              </div>
            )}
          </div>
        ) : (
          <div>
            <div className="text-sm text-gray-500 dark:text-gray-400">
             {t('ui:ProfileSettings.noPhoneNumberAssigned')}
            </div>
            <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
             {t('ui:ProfileSettings.askAnAdministratorToAssign')}
            </div>
          </div>
        )}
      </section>

      <VoicemailGreetingEditor />
    </div>
  )
}
