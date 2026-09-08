import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Mail, Loader2, Plus, Trash2, Check, Sparkles, Globe, ArrowRight, KeyRound, Copy, Inbox, Send, RefreshCw, ChevronLeft } from 'lucide-react'
import { toast } from 'sonner'
import { domainsApi, type DomainPurchase, type InboxMessageFull } from '@/api/domains'
import { genPassword } from '@/lib/genPassword'

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
  // Poll activation status every 60s while inactive so the banner clears
  // itself the moment Migadu finishes verifying (no manual refresh).
  const statusQ = useQuery({
    queryKey: ['email-status', d.id],
    queryFn: async () => (await domainsApi.emailStatus(d.id)).data,
    refetchInterval: (q) => (q.state.data?.active ? false : 60_000),
  })
  const activating = statusQ.data ? !statusQ.data.active : false
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
        {activating && (
          <div className="mb-3 rounded-md border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 px-3 py-2 text-xs text-amber-800 dark:text-amber-200 flex items-start gap-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin mt-0.5 shrink-0" />
            <span>
              <strong>Email is activating.</strong> Migadu is verifying this domain’s DNS — usually ready within a
              few hours (up to 24h after setup). You can create mailboxes now, but logging into them (webmail, phone,
              mail apps) will only work once verification finishes. This page updates automatically.
            </span>
          </div>
        )}
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
              <MailboxRow key={m.local_part} domainId={d.id}
                localPart={m.local_part} address={m.address || `${m.local_part}@${d.domain}`}
                name={m.name}
                onDeleted={() => qc.invalidateQueries({ queryKey: ['mailboxes', d.id] })} />
            ))}
          </ul>
        )}
        {showAdd && (
          <AddForm domainId={d.id} domain={d.domain}
            onDone={() => { setShowAdd(false); qc.invalidateQueries({ queryKey: ['mailboxes', d.id] }) }}
            onCancel={() => setShowAdd(false)} />
        )}
        {mailboxes.length > 0 && <MailboxAccessHelp />}
      </div>
    </section>
  )
}

function MailboxRow({ domainId, localPart, address, name, onDeleted }: {
  domainId: string; localPart: string; address: string; name?: string; onDeleted: () => void;
}) {
  const [resetting, setResetting] = useState(false)
  const [inboxOpen, setInboxOpen] = useState(false)
  const [pw, setPw] = useState('')
  const deleteMut = useMutation({
    mutationFn: () => domainsApi.deleteMailbox(domainId, localPart),
    onSuccess: () => { toast.success('Mailbox deleted'); onDeleted() },
    onError: (e: Error) => toast.error(e.message),
  })
  const resetMut = useMutation({
    mutationFn: () => domainsApi.resetMailboxPassword(domainId, localPart, pw),
    onSuccess: () => { toast.success('Password updated'); setResetting(false); setPw('') },
    onError: (e: Error) => toast.error(e.message),
  })
  return (
    <li className="py-2 text-sm">
      <div className="flex items-center gap-3">
        <Mail className="h-3.5 w-3.5 text-gray-400 shrink-0" />
        <span className="font-mono flex-1 min-w-0 truncate">{address}</span>
        {name && <span className="text-gray-500 text-xs">{name}</span>}
        <button onClick={() => setInboxOpen(v => !v)}
          className={`p-1 ${inboxOpen ? 'text-blue-600' : 'text-gray-500 hover:text-blue-600'}`} title="Open inbox">
          <Inbox className="h-3.5 w-3.5" />
        </button>
        <button onClick={() => { setResetting(v => !v); if (!resetting && !pw) setPw(genPassword()) }}
          className="text-gray-500 hover:text-blue-600 p-1" title="Reset password">
          <KeyRound className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => { if (confirm(`Delete ${address}? Mail cannot be recovered.`)) deleteMut.mutate() }}
          className="text-rose-600 hover:text-rose-700 p-1" title="Delete mailbox">
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      {resetting && (
        <div className="mt-2 ml-6 flex flex-wrap items-center gap-2">
          <input value={pw} onChange={e => setPw(e.target.value)}
            className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-2 py-1.5 font-mono flex-1 min-w-[220px]" />
          <button type="button" onClick={() => setPw(genPassword())}
            className="text-xs px-2 py-1.5 rounded border border-gray-300 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center gap-1">
            <Sparkles className="h-3 w-3" /> Generate
          </button>
          <button type="button" onClick={() => { navigator.clipboard?.writeText(pw); toast.success('Copied') }}
            className="text-xs px-2 py-1.5 rounded border border-gray-300 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center gap-1">
            <Copy className="h-3 w-3" /> Copy
          </button>
          <button type="button" disabled={pw.length < 12 || resetMut.isPending} onClick={() => resetMut.mutate()}
            className="text-xs px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white flex items-center gap-1">
            {resetMut.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />} Save password
          </button>
          <button type="button" onClick={() => { setResetting(false); setPw('') }} className="text-xs text-gray-500 hover:text-gray-700">Cancel</button>
        </div>
      )}
      {inboxOpen && <MailboxInbox domainId={domainId} localPart={localPart} address={address} />}
    </li>
  )
}

function MailboxInbox({ domainId, localPart, address }: { domainId: string; localPart: string; address: string }) {
  const [openUid, setOpenUid] = useState<string | null>(null)
  const [composing, setComposing] = useState(false)
  const listQ = useQuery({
    queryKey: ['inbox', domainId, localPart],
    queryFn: async () => (await domainsApi.inboxList(domainId, localPart, 30)).data,
  })
  const msgQ = useQuery({
    queryKey: ['inbox-msg', domainId, localPart, openUid],
    queryFn: async () => (await domainsApi.inboxMessage(domainId, localPart, openUid!)).data,
    enabled: !!openUid,
  })
  const messages = listQ.data ?? []

  return (
    <div className="mt-3 ml-6 rounded-md border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950/50">
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-800">
        <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
          <Inbox className="h-3.5 w-3.5" /> Inbox — {address}
        </span>
        <div className="flex items-center gap-2">
          <button onClick={() => listQ.refetch()} className="text-gray-500 hover:text-blue-600 p-1" title="Refresh">
            <RefreshCw className={`h-3.5 w-3.5 ${listQ.isFetching ? 'animate-spin' : ''}`} />
          </button>
          <button onClick={() => { setComposing(true); setOpenUid(null) }}
            className="text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1">
            <Send className="h-3 w-3" /> Compose
          </button>
        </div>
      </div>

      {composing ? (
        <ComposeForm address={address} domainId={domainId} localPart={localPart}
          onClose={() => setComposing(false)} onSent={() => { setComposing(false); listQ.refetch() }} />
      ) : openUid ? (
        <MessageView msg={msgQ.data} loading={msgQ.isLoading} error={msgQ.error as Error | null}
          onBack={() => setOpenUid(null)}
          onReply={() => { setComposing(true) }} />
      ) : listQ.isLoading ? (
        <div className="py-6 text-center"><Loader2 className="h-4 w-4 animate-spin mx-auto text-gray-400" /></div>
      ) : listQ.isError ? (
        <div className="py-4 px-3 text-xs text-rose-600 dark:text-rose-300">
          Couldn’t load inbox: {(listQ.error as Error)?.message || 'connection error'}
        </div>
      ) : messages.length === 0 ? (
        <div className="py-6 text-center text-xs text-gray-500">No messages yet. Mail sent to {address} will appear here.</div>
      ) : (
        <ul className="divide-y divide-gray-200 dark:divide-gray-800 max-h-80 overflow-y-auto">
          {messages.map(m => (
            <li key={m.uid}>
              <button onClick={() => setOpenUid(m.uid)}
                className="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-800/50 flex items-center gap-2">
                {!m.seen && <span className="h-2 w-2 rounded-full bg-blue-600 shrink-0" />}
                <span className={`text-xs truncate flex-1 ${m.seen ? 'text-gray-600 dark:text-gray-400' : 'font-semibold text-gray-900 dark:text-white'}`}>
                  {m.from}
                </span>
                <span className="text-xs text-gray-800 dark:text-gray-200 truncate flex-[2]">{m.subject}</span>
                <span className="text-[10px] text-gray-400 shrink-0">{m.date?.replace(/\s*\(.*\)$/, '').slice(0, 22)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function MessageView({ msg, loading, error, onBack, onReply }: {
  msg?: InboxMessageFull; loading: boolean; error: Error | null; onBack: () => void; onReply: () => void;
}) {
  return (
    <div className="p-3">
      <div className="flex items-center justify-between mb-2">
        <button onClick={onBack} className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1">
          <ChevronLeft className="h-3.5 w-3.5" /> Back
        </button>
        <button onClick={onReply} className="text-xs px-2 py-1 rounded border border-gray-300 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center gap-1">
          <Send className="h-3 w-3" /> Reply
        </button>
      </div>
      {loading ? (
        <div className="py-6 text-center"><Loader2 className="h-4 w-4 animate-spin mx-auto text-gray-400" /></div>
      ) : error ? (
        <div className="text-xs text-rose-600 dark:text-rose-300">Couldn’t open message: {error.message}</div>
      ) : msg ? (
        <div>
          <div className="text-sm font-semibold text-gray-900 dark:text-white">{msg.subject}</div>
          <div className="text-xs text-gray-500 mt-0.5">From: <span className="font-mono">{msg.from}</span></div>
          <div className="text-xs text-gray-500">{msg.date}</div>
          <div className="mt-3 border-t border-gray-200 dark:border-gray-800 pt-3">
            {msg.html ? (
              <div className="prose prose-sm dark:prose-invert max-w-none text-sm overflow-x-auto"
                dangerouslySetInnerHTML={{ __html: msg.html }} />
            ) : (
              <pre className="text-sm whitespace-pre-wrap font-sans text-gray-800 dark:text-gray-200">{msg.text || '(empty message)'}</pre>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}

function ComposeForm({ address, domainId, localPart, onClose, onSent }: {
  address: string; domainId: string; localPart: string; onClose: () => void; onSent: () => void;
}) {
  const [to, setTo] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const sendMut = useMutation({
    mutationFn: () => domainsApi.inboxSend(domainId, localPart, { to, subject, body }),
    onSuccess: () => { toast.success('Sent'); onSent() },
    onError: (e: Error) => toast.error(e.message || 'Send failed'),
  })
  return (
    <form className="p-3 space-y-2" onSubmit={e => { e.preventDefault(); if (to.trim()) sendMut.mutate() }}>
      <div className="text-[11px] text-gray-500">From: <span className="font-mono">{address}</span></div>
      <input value={to} onChange={e => setTo(e.target.value)} placeholder="To (email address)"
        className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-2 py-1.5" />
      <input value={subject} onChange={e => setSubject(e.target.value)} placeholder="Subject"
        className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-2 py-1.5" />
      <textarea value={body} onChange={e => setBody(e.target.value)} placeholder="Write your message…" rows={6}
        className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-2 py-1.5" />
      <div className="flex items-center gap-2">
        <button type="submit" disabled={!to.trim() || sendMut.isPending}
          className="px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm flex items-center gap-1">
          {sendMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />} Send
        </button>
        <button type="button" onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700">Cancel</button>
        <span className="text-[11px] text-gray-400">Sending activates once the domain finishes outbound verification.</span>
      </div>
    </form>
  )
}

function MailboxAccessHelp() {
  return (
    <div className="mt-4 pt-3 border-t border-gray-200 dark:border-gray-800 text-xs text-gray-600 dark:text-gray-400 space-y-1">
      <div className="font-semibold text-gray-700 dark:text-gray-300">How to log in</div>
      <div><strong>Webmail:</strong> <a href="https://webmail.migadu.com" target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">webmail.migadu.com</a> — sign in with the full email address and its password.</div>
      <div><strong>Mail apps</strong> (Apple Mail / Outlook / Gmail app) — add an account with:</div>
      <div className="font-mono pl-3 leading-relaxed">
        IMAP: imap.migadu.com · port 993 · SSL/TLS<br />
        SMTP: smtp.migadu.com · port 465 · SSL/TLS<br />
        Username: the full email address · Password: the mailbox password
      </div>
      <div className="text-gray-500">If you just enabled email, allow ~15 min for DNS to propagate before the first login.</div>
    </div>
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
    <div className="mt-3">
      <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
        The <strong>address</strong> is what people email; the <strong>display name</strong> is what shows on messages
        {' '}you send (e.g. “Nathan O”, not an email address); the <strong>password</strong> is what you’ll use to log
        {' '}into webmail and mail apps.
      </p>
      <form className="flex flex-wrap gap-2 items-end" onSubmit={e => { e.preventDefault(); if (canSubmit) mut.mutate() }}>
        <label className="flex flex-col gap-0.5">
          <span className="text-[10px] uppercase tracking-wider text-gray-400">Address</span>
          <div className="flex items-center gap-1">
            <input value={local} onChange={e => setLocal(e.target.value.toLowerCase())} placeholder="jane"
              className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-2 py-1.5 w-32 font-mono" />
            <span className="text-sm text-gray-500">@{domain}</span>
          </div>
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-[10px] uppercase tracking-wider text-gray-400">Display name</span>
          <input value={name} onChange={e => setName(e.target.value)} placeholder="Nathan O"
            className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-2 py-1.5 w-40" />
        </label>
        <label className="flex flex-col gap-0.5 flex-1 min-w-[200px]">
          <span className="text-[10px] uppercase tracking-wider text-gray-400">Password (12+ chars)</span>
          <div className="flex gap-1">
            <input type="text" value={password} onChange={e => setPassword(e.target.value)} placeholder="click Generate →"
              className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-2 py-1.5 font-mono flex-1" />
            <button type="button" onClick={() => setPassword(genPassword())}
              className="text-xs px-2 rounded border border-gray-300 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center gap-1" title="Generate strong password">
              <Sparkles className="h-3 w-3" />
            </button>
            <button type="button" onClick={() => { navigator.clipboard?.writeText(password); toast.success('Copied') }}
              disabled={!password} className="text-xs px-2 rounded border border-gray-300 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-40 flex items-center gap-1" title="Copy">
              <Copy className="h-3 w-3" />
            </button>
          </div>
        </label>
        <button type="submit" disabled={!canSubmit}
          className="px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm flex items-center gap-1">
          {mut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />} Create
        </button>
        <button type="button" onClick={onCancel} className="text-sm text-gray-500 hover:text-gray-700 pb-1.5">Cancel</button>
      </form>
    </div>
  )
}
