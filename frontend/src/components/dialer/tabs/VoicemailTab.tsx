/**
 * Voicemail tab — voicemails with inline transcript + audio playback.
 *
 * Voicemails live in the same `call_logs` table as calls, distinguished by
 * `kind: 'voicemail'`, and carry `recording_url` plus a transcript. The data
 * was already there; this tab used to be a "coming in Phase B" stub.
 */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, Mail, Phone } from 'lucide-react'
import { formatRelativeTime } from '@/lib/utils'
import { listCalls } from '@/api/communication'
import { listContacts } from '@/api/contacts'
import type { CallLogEntry, Contact } from '@/types/models'

function formatPhone(raw: string): string {
  const digits = raw.replace(/\D/g, '')
  if (digits.length === 11 && digits.startsWith('1')) {
    return `(${digits.slice(1, 4)}) ${digits.slice(4, 7)}-${digits.slice(7)}`
  }
  if (digits.length === 10) {
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`
  }
  return raw
}

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return ''
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

interface Props {
  onDial: (number: string) => void
}

export default function VoicemailTab({ onDial }: Props) {
  const voicemailsQuery = useQuery({
    queryKey: ['dialer-voicemails'],
    queryFn: () => listCalls({ kind: 'voicemail', page_size: 50 }),
  })

  // Same 100 cap as RecentsTab — past it we fall back to the raw number.
  const contactsQuery = useQuery({
    queryKey: ['dialer-voicemail-contacts'],
    queryFn: () => listContacts({ page_size: 100 }),
  })

  const contactsByPhone = useMemo(() => {
    const map = new Map<string, Contact>()
    for (const contact of (contactsQuery.data?.data ?? []) as Contact[]) {
      if (contact.phone) map.set(contact.phone.replace(/\D/g, ''), contact)
    }
    return map
  }, [contactsQuery.data])

  const nameFor = (vm: CallLogEntry): string | null => {
    const contact = contactsByPhone.get(vm.from_number.replace(/\D/g, ''))
    return contact?.contact_name || contact?.company_name || null
  }

  const voicemails = (voicemailsQuery.data?.data ?? []) as CallLogEntry[]

  if (voicemailsQuery.isLoading) {
    return (
      <div className="px-6 py-12 flex justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-[color:var(--lg-text-secondary)]" />
      </div>
    )
  }

  if (voicemailsQuery.isError) {
    return (
      <div className="px-6 py-12 text-center">
        <p className="text-sm text-[color:var(--lg-text-secondary)]">
          Couldn't load voicemails. Try again in a moment.
        </p>
      </div>
    )
  }

  if (voicemails.length === 0) {
    return (
      <div className="px-6 py-12 text-center space-y-4">
        <div
          className="w-14 h-14 rounded-2xl mx-auto flex items-center justify-center"
          style={{
            background:
              'linear-gradient(135deg, rgba(0,212,255,0.16), rgba(139,92,246,0.16))',
            border: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          <Mail className="h-6 w-6 text-[color:var(--lg-text-secondary)]" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-[color:var(--lg-text-primary)]">
            No voicemails
          </h3>
          <p className="text-xs text-[color:var(--lg-text-secondary)] mt-2 max-w-[300px] mx-auto leading-relaxed">
            When someone leaves you a message it shows up here, with a
            transcript and playback.
          </p>
        </div>
      </div>
    )
  }

  return (
    <ul className="divide-y divide-white/5">
      {voicemails.map((vm) => {
        const name = nameFor(vm)
        const label = name || formatPhone(vm.from_number)
        const status = vm.voicemail_transcript_status

        return (
          <li key={vm.id} className="px-4 py-3 space-y-2">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-[color:var(--lg-text-primary)] truncate">
                  {label}
                </p>
                <p className="text-xs text-[color:var(--lg-text-secondary)]">
                  {formatRelativeTime(vm.created_at)}
                  {vm.recording_duration_seconds
                    ? ` · ${formatDuration(vm.recording_duration_seconds)}`
                    : ''}
                </p>
              </div>
              <button
                onClick={() => onDial(vm.from_number)}
                aria-label={`Call ${label} back`}
                className="shrink-0 p-2 rounded-full hover:bg-white/5 text-[color:var(--lg-text-secondary)] hover:text-[color:var(--lg-text-primary)] transition-colors"
              >
                <Phone className="h-4 w-4" />
              </button>
            </div>

            {vm.recording_url && (
              <audio
                controls
                preload="none"
                src={vm.recording_url}
                className="w-full h-8"
              />
            )}

            {vm.voicemail_transcript ? (
              <p className="text-xs text-[color:var(--lg-text-secondary)] leading-relaxed">
                {vm.voicemail_transcript}
              </p>
            ) : status === 'pending' ? (
              <p className="text-xs italic text-[color:var(--lg-text-secondary)]">
                Transcribing…
              </p>
            ) : status === 'failed' ? (
              <p className="text-xs italic text-[color:var(--lg-text-secondary)]">
                Transcript unavailable — play the recording above.
              </p>
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}
