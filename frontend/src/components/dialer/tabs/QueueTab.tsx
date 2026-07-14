/**
 * Dial Queue — work a list of numbers top to bottom, logging the outcome of
 * each call as you go.
 *
 * The queue lives in localStorage rather than a table: it's a per-person,
 * per-device working session, and keeping it client-side means it survives a
 * refresh without needing a schema. Wrap-up notes are NOT client-side — they
 * post to the real call log, so the contact's timeline reflects the call.
 *
 * This tab used to be a "coming in Phase D" stub.
 */
import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { List, Phone, Plus, SkipForward, Trash2, X } from 'lucide-react'
import { logCall, getMyNumber } from '@/api/communication'
import { listContacts } from '@/api/contacts'
import type { Contact } from '@/types/models'

const STORAGE_KEY = 'dialer.queue.v1'

type ItemStatus = 'pending' | 'done' | 'skipped'

interface QueueItem {
  id: string
  number: string
  name: string | null
  contactId: string | null
  status: ItemStatus
  note: string
}

function loadQueue(): QueueItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    // A corrupt entry must not brick the tab — start over.
    return []
  }
}

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

/** Accepts pasted numbers separated by commas, semicolons, or newlines. */
function parseNumbers(input: string): string[] {
  return input
    .split(/[\n,;]+/)
    .map((s) => s.trim())
    .filter((s) => s.replace(/\D/g, '').length >= 7)
}

interface Props {
  onDial: (number: string) => void
}

export default function QueueTab({ onDial }: Props) {
  const queryClient = useQueryClient()
  const [items, setItems] = useState<QueueItem[]>(loadQueue)
  const [showAdd, setShowAdd] = useState(false)
  const [numbersInput, setNumbersInput] = useState('')
  const [contactSearch, setContactSearch] = useState('')

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
  }, [items])

  const myNumberQuery = useQuery({
    queryKey: ['dialer-my-number'],
    queryFn: () => getMyNumber(),
  })

  const contactsQuery = useQuery({
    queryKey: ['dialer-queue-contacts', contactSearch],
    queryFn: () => listContacts({ search: contactSearch || undefined, page_size: 20 }),
    enabled: showAdd,
  })

  const logMutation = useMutation({
    mutationFn: (item: QueueItem) =>
      logCall({
        contact_id: item.contactId ?? undefined,
        direction: 'outbound',
        from_number:
          (myNumberQuery.data?.data as { phone_number?: string } | undefined)
            ?.phone_number ?? '',
        to_number: item.number,
        notes: item.note || undefined,
        outcome: item.status === 'done' ? 'completed' : 'skipped',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dialer-recents'] })
    },
    onError: (err) =>
      toast.error(
        `Call logged locally but not saved: ${
          err instanceof Error ? err.message : 'Unknown error'
        }`,
      ),
  })

  const pending = items.filter((i) => i.status === 'pending')
  const current = pending[0] ?? null
  const doneCount = items.filter((i) => i.status !== 'pending').length

  const progress = items.length > 0 ? Math.round((doneCount / items.length) * 100) : 0

  const addNumbers = () => {
    const parsed = parseNumbers(numbersInput)
    if (parsed.length === 0) return
    setItems((prev) => [
      ...prev,
      ...parsed.map((number, idx) => ({
        id: `${Date.now()}-${idx}`,
        number,
        name: null,
        contactId: null,
        status: 'pending' as ItemStatus,
        note: '',
      })),
    ])
    setNumbersInput('')
    setShowAdd(false)
  }

  const addContact = (contact: Contact) => {
    if (!contact.phone) return
    setItems((prev) => [
      ...prev,
      {
        id: `${Date.now()}-${contact.id}`,
        number: contact.phone!,
        name: contact.contact_name || contact.company_name,
        contactId: contact.id,
        status: 'pending',
        note: '',
      },
    ])
  }

  const resolve = (id: string, status: ItemStatus) => {
    const item = items.find((i) => i.id === id)
    if (!item) return
    const resolved = { ...item, status }
    setItems((prev) => prev.map((i) => (i.id === id ? resolved : i)))
    logMutation.mutate(resolved)
  }

  const setNote = (id: string, note: string) => {
    setItems((prev) => prev.map((i) => (i.id === id ? { ...i, note } : i)))
  }

  const removeItem = (id: string) =>
    setItems((prev) => prev.filter((i) => i.id !== id))

  const clearQueue = () => setItems([])

  const searchResults = useMemo(
    () => ((contactsQuery.data?.data ?? []) as Contact[]).filter((c) => c.phone),
    [contactsQuery.data],
  )

  return (
    <div className="px-4 py-3 space-y-3">
      {/* Progress + actions */}
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[color:var(--lg-text-primary)]">
            Dial Queue
          </p>
          <p className="text-xs text-[color:var(--lg-text-secondary)]">
            {items.length === 0
              ? 'Nothing queued'
              : `${doneCount} of ${items.length} done · ${progress}%`}
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => setShowAdd((v) => !v)}
            aria-label="Add to queue"
            className="p-2 rounded-full hover:bg-white/5 text-[color:var(--lg-text-secondary)] hover:text-[color:var(--lg-text-primary)]"
          >
            {showAdd ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          </button>
          {items.length > 0 && (
            <button
              onClick={clearQueue}
              aria-label="Clear queue"
              className="p-2 rounded-full hover:bg-white/5 text-[color:var(--lg-text-secondary)] hover:text-red-400"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {items.length > 0 && (
        <div className="h-1 rounded-full bg-white/5 overflow-hidden">
          <div
            className="h-full bg-[color:var(--lg-accent,#00d4ff)] transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {/* Add panel */}
      {showAdd && (
        <div className="space-y-2 p-3 rounded-lg bg-white/[0.03] border border-white/5">
          <textarea
            value={numbersInput}
            onChange={(e) => setNumbersInput(e.target.value)}
            placeholder="Paste numbers, one per line or comma-separated"
            rows={2}
            className="w-full px-2 py-1.5 text-xs rounded bg-white/5 border border-white/10 text-[color:var(--lg-text-primary)] placeholder:text-[color:var(--lg-text-secondary)]"
          />
          <button
            onClick={addNumbers}
            disabled={parseNumbers(numbersInput).length === 0}
            className="w-full py-1.5 text-xs font-medium rounded bg-white/10 hover:bg-white/15 disabled:opacity-40 disabled:cursor-not-allowed text-[color:var(--lg-text-primary)]"
          >
            Add {parseNumbers(numbersInput).length || ''} number
            {parseNumbers(numbersInput).length === 1 ? '' : 's'}
          </button>

          <input
            type="text"
            value={contactSearch}
            onChange={(e) => setContactSearch(e.target.value)}
            placeholder="…or search contacts"
            className="w-full px-2 py-1.5 text-xs rounded bg-white/5 border border-white/10 text-[color:var(--lg-text-primary)] placeholder:text-[color:var(--lg-text-secondary)]"
          />
          {searchResults.length > 0 && (
            <ul className="max-h-32 overflow-y-auto">
              {searchResults.map((contact) => (
                <li key={contact.id}>
                  <button
                    onClick={() => addContact(contact)}
                    className="w-full flex items-center justify-between px-2 py-1.5 text-xs text-left rounded hover:bg-white/5"
                  >
                    <span className="truncate text-[color:var(--lg-text-primary)]">
                      {contact.contact_name || contact.company_name}
                    </span>
                    <Plus className="h-3 w-3 shrink-0 text-[color:var(--lg-text-secondary)]" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Empty state */}
      {items.length === 0 && !showAdd && (
        <div className="px-6 py-10 text-center space-y-4">
          <div
            className="w-14 h-14 rounded-2xl mx-auto flex items-center justify-center"
            style={{
              background:
                'linear-gradient(135deg, rgba(0,212,255,0.16), rgba(139,92,246,0.16))',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <List className="h-6 w-6 text-[color:var(--lg-text-secondary)]" />
          </div>
          <p className="text-xs text-[color:var(--lg-text-secondary)] max-w-[300px] mx-auto leading-relaxed">
            Build a queue from your contacts or paste a list of numbers, then
            work through it call by call.
          </p>
        </div>
      )}

      {/* Current call */}
      {current && (
        <div className="p-3 rounded-lg bg-white/[0.05] border border-white/10 space-y-2">
          <p className="text-xs uppercase tracking-wide text-[color:var(--lg-text-secondary)]">
            Up next
          </p>
          <p className="text-sm font-medium text-[color:var(--lg-text-primary)]">
            {current.name || formatPhone(current.number)}
          </p>
          {current.name && (
            <p className="text-xs text-[color:var(--lg-text-secondary)]">
              {formatPhone(current.number)}
            </p>
          )}
          <textarea
            value={current.note}
            onChange={(e) => setNote(current.id, e.target.value)}
            placeholder="Wrap-up notes…"
            rows={2}
            className="w-full px-2 py-1.5 text-xs rounded bg-white/5 border border-white/10 text-[color:var(--lg-text-primary)] placeholder:text-[color:var(--lg-text-secondary)]"
          />
          <div className="flex gap-2">
            <button
              onClick={() => onDial(current.number)}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium rounded-lg bg-emerald-500/90 hover:bg-emerald-500 text-white"
            >
              <Phone className="h-3.5 w-3.5" /> Call
            </button>
            <button
              onClick={() => resolve(current.id, 'done')}
              className="flex-1 py-2 text-xs font-medium rounded-lg bg-white/10 hover:bg-white/15 text-[color:var(--lg-text-primary)]"
            >
              Done
            </button>
            <button
              onClick={() => resolve(current.id, 'skipped')}
              aria-label="Skip"
              className="px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-[color:var(--lg-text-secondary)]"
            >
              <SkipForward className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Remaining */}
      {pending.length > 1 && (
        <ul className="divide-y divide-white/5">
          {pending.slice(1).map((item) => (
            <li
              key={item.id}
              className="group flex items-center justify-between gap-2 py-2"
            >
              <span className="text-xs text-[color:var(--lg-text-secondary)] truncate">
                {item.name || formatPhone(item.number)}
              </span>
              <button
                onClick={() => removeItem(item.id)}
                aria-label={`Remove ${item.name || item.number}`}
                className="shrink-0 p-1 opacity-0 group-hover:opacity-100 text-[color:var(--lg-text-secondary)] hover:text-red-400"
              >
                <X className="h-3 w-3" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
