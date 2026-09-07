import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { QRCodeSVG } from 'qrcode.react'
import { ShieldCheck, ShieldOff, KeyRound, Copy, Check, AlertTriangle } from 'lucide-react'
import { getMfaStatus, startMfaEnrollment, confirmMfaEnrollment, disableMfa, type MfaEnrollment } from '@/api/mfa'
import { formatDate } from '@/lib/utils'
import { useTranslation } from 'react-i18next'

/**
 * Authenticator-app (TOTP) enrolment.
 *
 * Why this exists: until 2026-09-06 the backend had enrol/confirm/disable
 * endpoints but nothing in Settings called them. A user with only a passkey
 * therefore had ONE factor and NO recovery codes — a lost or absent key was a
 * hard lockout (that is exactly what happened to both prod admins). Recovery
 * codes are minted here, on confirm, and shown once.
 */
export default function AuthenticatorSettings() {
  const { t } = useTranslation('ui')
  const qc = useQueryClient()
  const [enrollment, setEnrollment] = useState<MfaEnrollment | null>(null)
  const [code, setCode] = useState('')
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null)
  const [disableCode, setDisableCode] = useState('')
  const [err, setErr] = useState('')
  const [copied, setCopied] = useState(false)

  const { data, isLoading } = useQuery({ queryKey: ['mfa-status'], queryFn: getMfaStatus })
  const status = data?.data

  const start = useMutation({
    mutationFn: startMfaEnrollment,
    onSuccess: (r) => { setEnrollment(r.data); setCode(''); setErr('') },
    onError: (e: any) => setErr(e?.message || 'Could not start enrolment.'),
  })
  const confirmEnroll = useMutation({
    mutationFn: () => confirmMfaEnrollment(code.trim()),
    onSuccess: (r) => {
      setRecoveryCodes(r.data.recovery_codes)
      setEnrollment(null)
      setCode('')
      setErr('')
      qc.invalidateQueries({ queryKey: ['mfa-status'] })
    },
    onError: (e: any) => setErr(e?.message || 'That code was not accepted. Codes change every 30 seconds — try the current one.'),
  })
  const disable = useMutation({
    mutationFn: () => disableMfa(disableCode.trim()),
    onSuccess: () => { setDisableCode(''); setErr(''); setRecoveryCodes(null); qc.invalidateQueries({ queryKey: ['mfa-status'] }) },
    onError: (e: any) => setErr(e?.message || 'Could not turn off the authenticator.'),
  })

  const copyCodes = async () => {
    if (!recoveryCodes) return
    try {
      await navigator.clipboard.writeText(recoveryCodes.join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard blocked — codes are still on screen */
    }
  }

  const inp = 'w-full px-3 py-2 border rounded-md text-sm font-mono tracking-widest focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-600 text-gray-900 dark:text-gray-100'

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-blue-500" />
         {t('ui:AuthenticatorSettings.authenticatorAppTwoFactor')}
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
         {t('ui:AuthenticatorSettings.a6DigitCodeFrom')} <strong>{t('ui:AuthenticatorSettings.recoveryCodes')}</strong>{t('ui:AuthenticatorSettings.theSafetyNetIfYou')}
        </p>
      </div>

      {err && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /> {err}
        </div>
      )}

      {/* ---- Recovery codes: shown ONCE, right after confirm ---- */}
      {recoveryCodes && (
        <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-300 dark:border-amber-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-2 font-medium text-amber-900 dark:text-amber-200">
            <KeyRound className="w-5 h-5" /> {t('ui:AuthenticatorSettings.saveTheseRecoveryCodesNow')}
          </div>
          <p className="text-sm text-amber-800 dark:text-amber-300">
           {t('ui:AuthenticatorSettings.eachCodeSignsYouIn')}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-sm">
            {recoveryCodes.map((c) => (
              <div key={c} className="bg-white dark:bg-gray-900 border rounded px-2 py-1.5 text-center text-gray-900 dark:text-gray-100 select-all">{c}</div>
            ))}
          </div>
          <div className="flex gap-2">
            <button onClick={copyCodes} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-800 dark:text-gray-200">
              {copied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
              {copied ? t('ui:AuthenticatorSettings.copied') : t('ui:AuthenticatorSettings.copyAll')}
            </button>
            <button onClick={() => setRecoveryCodes(null)} className="px-3 py-1.5 text-sm text-amber-900 dark:text-amber-200 hover:underline">
             {t('ui:AuthenticatorSettings.iVeSavedThem')}
            </button>
          </div>
        </div>
      )}

      {/* ---- Status card ---- */}
      {!isLoading && status && !enrollment && (
        <div className="bg-white dark:bg-gray-900 border rounded-lg p-4">
          {status.mfa_enabled ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-green-700 dark:text-green-400 font-medium">
                <ShieldCheck className="w-5 h-5" /> {t('ui:AuthenticatorSettings.authenticatorAppIsOn')}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
               {t('ui:AuthenticatorSettings.enrolled')} {status.enrolled_at ? formatDate(status.enrolled_at) : ''} ·{' '}
                {status.recovery_codes_remaining} {t('ui:AuthenticatorSettings.recoveryCode')}{status.recovery_codes_remaining === 1 ? '' : 's'} left
                {status.recovery_codes_remaining <= 2 && (
                  <span className="ml-2 text-amber-700 dark:text-amber-400">{t('ui:AuthenticatorSettings.runningLowTurnOffAnd')}</span>
                )}
              </div>
              <form
                onSubmit={(e) => { e.preventDefault(); if (window.confirm(t('ui:AuthenticatorSettings.turnOffTheAuthenticatorApp'))) disable.mutate() }}
                className="flex flex-col sm:flex-row gap-2 sm:items-end pt-2 border-t dark:border-gray-800"
              >
                <div className="flex-1 max-w-xs">
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{t('ui:AuthenticatorSettings.currentCodeOrARecovery')}</label>
                  <input className={inp} value={disableCode} onChange={(e) => setDisableCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" placeholder="123 456" />
                </div>
                <button type="submit" disabled={disable.isPending || !disableCode.trim()} className="flex items-center gap-1.5 px-4 py-2 text-sm border border-red-200 text-red-600 rounded-lg hover:bg-red-50 dark:hover:bg-red-950 disabled:opacity-50">
                  <ShieldOff className="w-4 h-4" /> {t('ui:AuthenticatorSettings.turnOff')}
                </button>
              </form>
            </div>
          ) : (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <div className="font-medium text-gray-900 dark:text-gray-100">{t('ui:AuthenticatorSettings.notSetUp')}</div>
                <div className="text-sm text-gray-500 dark:text-gray-400">{t('ui:AuthenticatorSettings.takesAboutAMinuteYou')}</div>
              </div>
              <button onClick={() => start.mutate()} disabled={start.isPending} className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                <ShieldCheck className="w-4 h-4" /> {start.isPending ? t('ui:AuthenticatorSettings.preparing') : t('ui:AuthenticatorSettings.setUpAuthenticator')}
              </button>
            </div>
          )}
        </div>
      )}

      {/* ---- Enrolment: QR + first code ---- */}
      {enrollment && (
        <div className="bg-white dark:bg-gray-900 border rounded-lg p-4 grid grid-cols-1 md:grid-cols-[auto,1fr] gap-6">
          <div className="flex flex-col items-center gap-2">
            <div className="bg-white p-3 rounded-lg border">
              <QRCodeSVG value={enrollment.otpauth_uri} size={176} level="M" includeMargin={false} />
            </div>
            <div className="text-[11px] text-gray-500 text-center max-w-[200px]">
             {t('ui:AuthenticatorSettings.canTScanEnterThis')}
              <div className="font-mono text-xs mt-1 break-all select-all text-gray-800 dark:text-gray-200">{enrollment.secret}</div>
            </div>
          </div>
          <form onSubmit={(e) => { e.preventDefault(); confirmEnroll.mutate() }} className="space-y-3">
            <ol className="text-sm text-gray-700 dark:text-gray-300 space-y-1.5 list-decimal pl-5">
              <li>{t('ui:AuthenticatorSettings.openYourAuthenticatorAppAnd')} <strong>{t('ui:AuthenticatorSettings.add')}</strong> / <strong>+</strong>.</li>
              <li>{t('ui:AuthenticatorSettings.scanTheQrCodeOr')}</li>
              <li>{t('ui:AuthenticatorSettings.enterThe6DigitCode')}</li>
            </ol>
            <div className="max-w-xs">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{t('ui:AuthenticatorSettings.n6DigitCode')}</label>
              <input className={inp} value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" placeholder="123 456" autoFocus maxLength={8} />
            </div>
            <div className="flex gap-2">
              <button type="submit" disabled={confirmEnroll.isPending || code.trim().length < 6} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                {confirmEnroll.isPending ? t('ui:AuthenticatorSettings.checking') : t('ui:AuthenticatorSettings.confirmAndTurnOn')}
              </button>
              <button type="button" onClick={() => { setEnrollment(null); setCode(''); setErr('') }} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:underline">
               {t('ui:AuthenticatorSettings.cancel')}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-gray-50 dark:bg-gray-950 border rounded-lg p-4 text-xs text-gray-500 dark:text-gray-400">
       {t('ui:AuthenticatorSettings.lostEverythingPhonePasskeyAnd')}
      </div>
    </div>
  )
}
