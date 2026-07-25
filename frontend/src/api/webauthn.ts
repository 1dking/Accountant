import { api } from './client'

// --- base64url <-> ArrayBuffer (WebAuthn transfers binary as base64url JSON) ---
function b64urlToBuf(s: string): ArrayBuffer {
  const pad = '='.repeat((4 - (s.length % 4)) % 4)
  const b64 = (s + pad).replace(/-/g, '+').replace(/_/g, '/')
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return bytes.buffer
}

function bufToB64url(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf)
  let bin = ''
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i])
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

export function isPasskeySupported(): boolean {
  return typeof window !== 'undefined' && !!window.PublicKeyCredential && !!navigator.credentials
}

export interface PasskeyInfo {
  id: string
  device_name: string
  created_at: string
  last_used_at: string | null
}

// --- Registration ---
export async function registerPasskey(deviceName: string) {
  const { data: options } = await api.post<{ data: any }>('/auth/webauthn/register/begin')

  const publicKey: any = {
    ...options,
    challenge: b64urlToBuf(options.challenge),
    user: { ...options.user, id: b64urlToBuf(options.user.id) },
    excludeCredentials: (options.excludeCredentials || []).map((c: any) => ({
      ...c,
      id: b64urlToBuf(c.id),
    })),
  }

  const cred = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential | null
  if (!cred) throw new Error('Passkey registration was cancelled.')
  const resp = cred.response as AuthenticatorAttestationResponse

  const credential = {
    id: cred.id,
    rawId: bufToB64url(cred.rawId),
    type: cred.type,
    response: {
      attestationObject: bufToB64url(resp.attestationObject),
      clientDataJSON: bufToB64url(resp.clientDataJSON),
      transports: typeof resp.getTransports === 'function' ? resp.getTransports() : [],
    },
    clientExtensionResults:
      typeof cred.getClientExtensionResults === 'function' ? cred.getClientExtensionResults() : {},
  }

  return api.post<{ data: PasskeyInfo }>('/auth/webauthn/register/finish', {
    credential,
    device_name: deviceName,
  })
}

// --- Management ---
export async function listPasskeys() {
  return api.get<{ data: PasskeyInfo[] }>('/auth/webauthn/credentials')
}

export async function removePasskey(id: string) {
  return api.delete<{ data: { removed: boolean } }>(`/auth/webauthn/credentials/${id}`)
}

// --- Login (second factor) ---
export async function passkeyLogin(mfaToken: string) {
  const { data: options } = await api.post<{ data: any }>('/auth/webauthn/login/begin', {
    mfa_token: mfaToken,
  })

  const publicKey: any = {
    ...options,
    challenge: b64urlToBuf(options.challenge),
    allowCredentials: (options.allowCredentials || []).map((c: any) => ({
      ...c,
      id: b64urlToBuf(c.id),
    })),
  }

  const cred = (await navigator.credentials.get({ publicKey })) as PublicKeyCredential | null
  if (!cred) throw new Error('Passkey sign-in was cancelled.')
  const resp = cred.response as AuthenticatorAssertionResponse

  const credential = {
    id: cred.id,
    rawId: bufToB64url(cred.rawId),
    type: cred.type,
    response: {
      authenticatorData: bufToB64url(resp.authenticatorData),
      clientDataJSON: bufToB64url(resp.clientDataJSON),
      signature: bufToB64url(resp.signature),
      userHandle: resp.userHandle ? bufToB64url(resp.userHandle) : null,
    },
  }

  return api.post<{ data: { access_token: string; refresh_token: string } }>(
    '/auth/webauthn/login/verify',
    { mfa_token: mfaToken, credential },
  )
}
