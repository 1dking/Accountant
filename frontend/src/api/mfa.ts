import { api } from './client'

export interface MfaStatus {
  mfa_enabled: boolean
  enrolled_at: string | null
  recovery_codes_remaining: number
}

export interface MfaEnrollment {
  /** Base32 shared secret — shown for manual entry when the QR can't be scanned. */
  secret: string
  /** otpauth:// URI — render as a QR code. */
  otpauth_uri: string
}

export const getMfaStatus = () => api.get<{ data: MfaStatus }>('/auth/mfa/status')
export const startMfaEnrollment = () => api.post<{ data: MfaEnrollment }>('/auth/mfa/enroll')
export const confirmMfaEnrollment = (code: string) =>
  api.post<{ data: { recovery_codes: string[] } }>('/auth/mfa/enroll/confirm', { code })
export const disableMfa = (code: string) => api.post<{ data: { mfa_enabled: boolean } }>('/auth/mfa/disable', { code })
