import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Globe, Loader2, Search, ShoppingCart, Trash2, Plus, Check, X, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'
import { domainsApi, type DomainCheck, type DomainPurchase } from '@/api/domains'

const DNS_TYPES = ['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'ALIAS', 'CAA']

function fmtMoney(cents: number, currency = 'USD') {
  const v = (cents || 0) / 100
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(v)
}

export default function DomainsPage() {
  const qc = useQueryClient()
  const [query, setQuery] = useState('')
  const [years, setYears] = useState(1)
  const [check, setCheck] = useState<DomainCheck | null>(null)
  const [dnsOpen, setDnsOpen] = useState<string | null>(null)

  const purchasesQ = useQuery({
    queryKey: ['domains'],
    queryFn: async () => (await domainsApi.list()).data,
  })

  const checkMut = useMutation({
    mutationFn: (d: string) => domainsApi.check(d).then(r => r.data),
    onSuccess: setCheck,
    onError: (e: Error) => toast.error(e.message || 'Check failed'),
  })

  const buyMut = useMutation({
    mutationFn: ({ d, y }: { d: string; y: number }) =>
      domainsApi.purchase(d, y).then(r => r.data),
    onSuccess: (r) => { window.location.href = r.checkout_url },
    onError: (e: Error) => toast.error(e.message || 'Purchase failed'),
  })

  const purchases = purchasesQ.data ?? []
  const canBuy = check && check.available && check.price_cents_retail > 0

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Globe className="h-6 w-6" /> Domains
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Buy and manage domain names for your sites. Prices include our small markup;
          we register through Porkbun and handle renewals for you.
        </p>
      </header>

      <section className="rounded-lg border border-gray-200 dark:border-gray-800 p-5 bg-white dark:bg-gray-900 space-y-4">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Search for a domain</h2>
        <form
          className="flex gap-2"
          onSubmit={(e) => { e.preventDefault(); if (query.trim()) checkMut.mutate(query.trim().toLowerCase()) }}
        >
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              autoFocus
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="example.com"
              className="w-full pl-9 pr-3 py-2 rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm"
            />
          </div>
          <select
            value={years}
            onChange={e => setYears(Number(e.target.value))}
            className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-2"
          >
            {[1, 2, 3, 5, 10].map(y => (
              <option key={y} value={y}>{y} year{y > 1 ? 's' : ''}</option>
            ))}
          </select>
          <button
            type="submit"
            disabled={!query.trim() || checkMut.isPending}
            className="px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium flex items-center gap-2"
          >
            {checkMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Check
          </button>
        </form>

        {check && (
          <div className={`rounded-md border p-4 ${check.available
            ? 'bg-emerald-50 border-emerald-200 dark:bg-emerald-950/30 dark:border-emerald-900'
            : 'bg-rose-50 border-rose-200 dark:bg-rose-950/30 dark:border-rose-900'}`}>
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-base font-medium text-gray-900 dark:text-white">
                  {check.available ? <Check className="h-4 w-4 text-emerald-600" /> : <X className="h-4 w-4 text-rose-600" />}
                  <span className="font-mono">{check.domain}</span>
                  {check.premium && <span className="text-[10px] uppercase tracking-wider text-amber-600">Premium</span>}
                </div>
                {check.available ? (
                  <div className="text-xs text-gray-600 dark:text-gray-300 mt-1">
                    {fmtMoney(check.price_cents_retail, check.currency)} for {years} year{years > 1 ? 's' : ''}
                    <span className="text-gray-400"> · renews at {fmtMoney(check.renewal_cents_retail, check.currency)}/yr</span>
                  </div>
                ) : (
                  <div className="text-xs text-gray-600 dark:text-gray-300 mt-1">
                    {check.error ? check.error : 'Not available for registration.'}
                  </div>
                )}
              </div>
              <button
                onClick={() => canBuy && buyMut.mutate({ d: check.domain, y: years })}
                disabled={!canBuy || buyMut.isPending}
                className="px-4 py-2 rounded-md bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-medium flex items-center gap-2"
              >
                {buyMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShoppingCart className="h-4 w-4" />}
                Buy — {fmtMoney((check.price_cents_retail || 0) * years, check.currency)}
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
        <div className="p-5 border-b border-gray-200 dark:border-gray-800">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Your domains</h2>
        </div>
        {purchasesQ.isLoading ? (
          <div className="p-8 text-center text-sm text-gray-500"><Loader2 className="h-5 w-5 animate-spin mx-auto" /></div>
        ) : purchases.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-500">No domains yet. Search above to register one.</div>
        ) : (
          <ul className="divide-y divide-gray-200 dark:divide-gray-800">
            {purchases.map(p => (
              <PurchaseRow key={p.id} p={p} open={dnsOpen === p.id} onToggle={() => setDnsOpen(dnsOpen === p.id ? null : p.id)} onChange={() => qc.invalidateQueries({ queryKey: ['domains'] })} />
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function PurchaseRow({ p, open, onToggle, onChange: _onChange }: {
  p: DomainPurchase; open: boolean; onToggle: () => void; onChange: () => void
}) {
  const statusColor = {
    pending: 'text-amber-600 bg-amber-50 dark:bg-amber-950/30',
    paid: 'text-amber-600 bg-amber-50 dark:bg-amber-950/30',
    registered: 'text-emerald-700 bg-emerald-50 dark:bg-emerald-950/30 dark:text-emerald-300',
    active: 'text-emerald-700 bg-emerald-50 dark:bg-emerald-950/30 dark:text-emerald-300',
    expired: 'text-rose-700 bg-rose-50 dark:bg-rose-950/30 dark:text-rose-300',
    failed: 'text-rose-700 bg-rose-50 dark:bg-rose-950/30 dark:text-rose-300',
    refunded: 'text-gray-600 bg-gray-100 dark:bg-gray-800',
  }[p.status] || 'text-gray-600 bg-gray-100'

  return (
    <li className="p-4">
      <div className="flex items-center gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm font-medium text-gray-900 dark:text-white">{p.domain}</span>
            <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded ${statusColor}`}>{p.status}</span>
            {p.expires_at && (
              <span className="text-xs text-gray-500">expires {new Date(p.expires_at).toLocaleDateString()}</span>
            )}
          </div>
          {p.notes && p.status === 'failed' && (
            <div className="text-xs text-rose-600 mt-1 whitespace-pre-wrap">{p.notes}</div>
          )}
        </div>
        <button
          onClick={onToggle}
          className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 flex items-center gap-1"
          disabled={p.status !== 'registered' && p.status !== 'active'}
        >
          {open ? 'Hide DNS' : 'Manage DNS'}
          {(p.status === 'registered' || p.status === 'active') && <ExternalLink className="h-3 w-3" />}
        </button>
      </div>

      {open && (p.status === 'registered' || p.status === 'active') && (
        <DnsPanel domainId={p.id} />
      )}
    </li>
  )
}

function DnsPanel({ domainId }: { domainId: string }) {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const dnsQ = useQuery({
    queryKey: ['dns', domainId],
    queryFn: async () => (await domainsApi.listDns(domainId)).data,
  })
  const deleteMut = useMutation({
    mutationFn: (rid: string) => domainsApi.deleteDns(domainId, rid),
    onSuccess: () => { toast.success('Record deleted'); qc.invalidateQueries({ queryKey: ['dns', domainId] }) },
    onError: (e: Error) => toast.error(e.message),
  })

  const records = dnsQ.data ?? []

  return (
    <div className="mt-4 rounded-md border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950/50 p-3">
      {dnsQ.isLoading ? (
        <div className="text-center py-4"><Loader2 className="h-4 w-4 animate-spin mx-auto text-gray-400" /></div>
      ) : (
        <>
          <table className="w-full text-xs">
            <thead className="text-gray-500">
              <tr className="text-left">
                <th className="py-1 pr-2 font-medium">Type</th>
                <th className="py-1 pr-2 font-medium">Name</th>
                <th className="py-1 pr-2 font-medium">Content</th>
                <th className="py-1 pr-2 font-medium">TTL</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {records.length === 0 && (
                <tr><td colSpan={5} className="py-4 text-center text-gray-500">No DNS records yet.</td></tr>
              )}
              {records.map(r => (
                <tr key={r.id} className="border-t border-gray-200 dark:border-gray-800">
                  <td className="py-1.5 pr-2 font-mono">{r.type}</td>
                  <td className="py-1.5 pr-2 font-mono">{r.name || '@'}</td>
                  <td className="py-1.5 pr-2 font-mono break-all">{r.content}</td>
                  <td className="py-1.5 pr-2 font-mono">{r.ttl}</td>
                  <td className="py-1.5 text-right">
                    <button
                      onClick={() => { if (confirm(`Delete ${r.type} record for ${r.name || '@'}?`)) deleteMut.mutate(String(r.id)) }}
                      className="text-rose-600 hover:text-rose-700 p-1"
                      title="Delete"
                    ><Trash2 className="h-3.5 w-3.5" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {showAdd ? (
            <AddDnsForm domainId={domainId} onDone={() => { setShowAdd(false); qc.invalidateQueries({ queryKey: ['dns', domainId] }) }} onCancel={() => setShowAdd(false)} />
          ) : (
            <button onClick={() => setShowAdd(true)} className="mt-3 text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1">
              <Plus className="h-3 w-3" /> Add record
            </button>
          )}
        </>
      )}
    </div>
  )
}

function AddDnsForm({ domainId, onDone, onCancel }: { domainId: string; onDone: () => void; onCancel: () => void }) {
  const [type, setType] = useState('A')
  const [name, setName] = useState('')
  const [content, setContent] = useState('')
  const [ttl, setTtl] = useState(600)
  const mut = useMutation({
    mutationFn: () => domainsApi.upsertDns(domainId, { type, name, content, ttl }),
    onSuccess: () => { toast.success('Record added'); onDone() },
    onError: (e: Error) => toast.error(e.message),
  })
  return (
    <form className="mt-3 flex flex-wrap gap-2 items-end" onSubmit={e => { e.preventDefault(); if (content.trim()) mut.mutate() }}>
      <select value={type} onChange={e => setType(e.target.value)} className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-xs px-2 py-1">
        {DNS_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
      </select>
      <input placeholder="name (blank = @)" value={name} onChange={e => setName(e.target.value)}
        className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-xs px-2 py-1 w-28 font-mono" />
      <input placeholder="content (e.g. 1.2.3.4)" value={content} onChange={e => setContent(e.target.value)}
        className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-xs px-2 py-1 flex-1 min-w-[220px] font-mono" />
      <input type="number" value={ttl} onChange={e => setTtl(Number(e.target.value))}
        className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-xs px-2 py-1 w-24" />
      <button type="submit" disabled={!content.trim() || mut.isPending}
        className="px-3 py-1 rounded-md bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs flex items-center gap-1">
        {mut.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />} Save
      </button>
      <button type="button" onClick={onCancel} className="text-xs text-gray-500 hover:text-gray-700">Cancel</button>
    </form>
  )
}
