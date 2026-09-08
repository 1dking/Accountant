import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Mail, Loader2, Plus, Trash2, Check, Sparkles, Globe, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'
import { domainsApi, type DomainPurchase } from '@/api/domains'

/**
 * Email — aggregate view across every domain we sold. Rows are
 * grouped by domain. Migadu is the source of truth for mailbox lists;
 * we just proxy through /api/domains/{id}/mailboxes.
 *
 * Domains still needing "Enable email" get a one-click card at the top
 * so a customer isn't forced to bounce over to /domains.
 */
export default function EmailPage() {
  const domainsQ = useQuery({
    queryKey: ['domains'],
    queryFn: async () => (await domainsApi.list()).data,
  })
  const domains = domainsQ.data ?? []
  const enabled = useMemo(
    () => domains.filter(d => d.email_enabled && (d.status === 'registered' || d.status === 'active')),
    [domains],
  )
  const eligible = useMemo(
    () => domains.filter(d => !d.email_enabled && (d.status === 'registered' || d.status === 'active')),
    [domains],
  )

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Mail className="h-6 w-6" /> Email
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Business mailboxes on your own domain. Powered by Migadu — real IMAP/SMTP,
          works in Apple Mail, Outlook, Gmail app, or the Migadu webmail.
        </p>
      </header>

      {domainsQ.isLoading ? (
        <div className="p-10 text-center text-sm text-gray-500"><Loader2 className="h-5 w-5 animate-spin mx-auto" /></div>
      ) : domains.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          {eligible.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Enable email on a domain</h2>
              {eligible.map(d => <EligibleRow key={d.id} d={d} />)}
            </section>
          )}

          {enabled.length === 0 && eligible.length === 0 && <EmptyState />}

          {enabled.map(d => <DomainMailboxes key={d.id} d={d} />)}
        </>
      )}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-gray-300 dark:border-gray-700 p-10 text-center">
      <Mail className="h-8 w-8 mx-auto text-gray-400" />
      <p className="text-sm text-gray-600 dark:text-gray-300 mt-3">
        You need a domain before you can create business mailboxes.
      </p>
      <Link to="/domains" className="inline-flex items-center gap-1 mt-4 text-sm text-blue-600 hover:text-blue-700">
        Go to Domains <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  )
}

function EligibleRow({ d }: { d: DomainPurchase }) {
  const qc = useQueryClient()
  const enableMut = useMutation({
    mutationFn: () => domainsApi.enableEmail(d.id).then(r => r.data),
    onSuccess: (r) => {
      toast.success(`Email on ${d.domain} — ${r.records_created} DNS records added`)
      qc.invalidateQueries({ queryKey: ['domains'] })
    },
    onError: (e: Error) => toast.error(e.message),
  })
  return (
    <div className="rounded-md border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 flex items-center gap-4">
      <Globe className="h-5 w-5 text-gray-400 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="font-mono text-sm font-medium text-gray-900 dark:text-white">{d.domain}</div>
        <div className="text-xs text-gray-500 mt-0.5">
          Enable to add MX / SPF / DKIM / DMARC records to your DNS automatically. Propagates in ~15 min.
        </div>
      </div>
      <button
        onClick={() => enableMut.mutate()}
        disabled={enableMut.isPending}
        className="px-3 py-2 rounded-md bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-medium flex items-center gap-1.5"
      >
        {enableMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
        Enable email
      </button>
    </div>
  )
}

function DomainMailboxes({ d }: { d: DomainPurchase }) {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const mailQ = useQuery({
    queryKey: ['mailboxes', d.id],
    queryFn: async () => (await domainsApi.listMailboxes(d.id)).data,
  })
  const deleteMut = useMutation({
    mutationFn: (local: string) => domainsApi.deleteMailbox(d.id, local),
    onSuccess: () => { toast.success('Mailbox deleted'); qc.invalidateQueries({ queryKey: ['mailboxes', d.id] }) },
    onError: (e: Error) => toast.error(e.message),
  })
  const mailboxes = mailQ.data ?? []

  return (
    <section className="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
      <div className="p-4 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <Globe className="h-4 w-4 text-emerald-600 shrink-0" />
          <span className="font-mono text-sm font-medium text-gray-900 dark:text-white truncate">{d.domain}</span>
          <span className="text-[10px] uppercase tracking-wider text-emerald-700 bg-emerald-50 dark:bg-emerald-950/30 dark:text-emerald-300 px-2 py-0.5 rounded">Email on</span>
        </div>
        {!showAdd && (
          <button
            onClick={() => setShowAdd(true)}
            className="text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1"
          >
            <Plus className="h-3 w-3" /> Add mailbox
          </button>
        )}
      </div>
      <div className="p-4">
        {mailQ.isLoading ? (
          <div className="text-center py-4"><Loader2 className="h-4 w-4 animate-spin mx-auto text-gray-400" /></div>
        ) : mailQ.isError ? (
          <div className="text-sm text-rose-600 dark:text-rose-300">
            Couldn’t load mailboxes: {(mailQ.error as Error)?.message || 'server error'}
          </div>
        ) : mailboxes.length === 0 && !showAdd ? (
          <div className="text-sm text-gray-500">No mailboxes yet on this domain.</div>
        ) : (
          <ul className="divide-y divide-gray-200 dark:divide-gray-800">
            {mailboxes.map(m => (
              <li key={m.local_part} className="py-2 flex items-center gap-3 text-sm">
                <Mail className="h-3.5 w-3.5 text-gray-400" />
                <span className="font-mono flex-1">{m.address || `${m.local_part}@${d.domain}`}</span>
                {m.name && <span className="text-gray-500 text-xs">{m.name}</span>}
                <button
                  onClick={() => { if (confirm(`Delete ${m.local_part}@${d.domain}? Mail cannot be recovered.`)) deleteMut.mutate(m.local_part) }}
                  className="text-rose-600 hover:text-rose-700 p-1"
                  title="Delete mailbox"
                ><Trash2 className="h-3.5 w-3.5" /></button>
              </li>
            ))}
          </ul>
        )}
        {showAdd && (
          <AddForm domainId={d.id} domain={d.domain}
            onDone={() => { setShowAdd(false); qc.invalidateQueries({ queryKey: ['mailboxes', d.id] }) }}
            onCancel={() => setShowAdd(false)} />
        )}
      </div>
    </section>
  )
}

function AddForm({ domainId, domain, onDone, onCancel }: {
  domainId: string; domain: string; onDone: () => void; onCancel: () => void;
}) {
  const [local, setLocal] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const mut = useMutation({
    mutationFn: () => domainsApi.createMailbox(domainId, { local_part: local, name, password }),
    onSuccess: () => { toast.success('Mailbox created'); onDone() },
    onError: (e: Error) => toast.error(e.message),
  })
  const canSubmit = local && name && password.length >= 12 && !mut.isPending
  return (
    <form className="mt-3 flex flex-wrap gap-2 items-end" onSubmit={e => { e.preventDefault(); if (canSubmit) mut.mutate() }}>
      <div className="flex items-center gap-1">
        <input value={local} onChange={e => setLocal(e.target.value.toLowerCase())} placeholder="jane"
          className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-2 py-1.5 w-32 font-mono" />
        <span className="text-sm text-gray-500">@{domain}</span>
      </div>
      <input value={name} onChange={e => setName(e.target.value)} placeholder="Full name"
        className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-2 py-1.5 w-40" />
      <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password (12+ chars)"
        className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-2 py-1.5 flex-1 min-w-[200px]" />
      <button type="submit" disabled={!canSubmit}
        className="px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm flex items-center gap-1">
        {mut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />} Create
      </button>
      <button type="button" onClick={onCancel} className="text-sm text-gray-500 hover:text-gray-700">Cancel</button>
    </form>
  )
}
