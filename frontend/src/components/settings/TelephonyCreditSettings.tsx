import { useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { toast } from 'sonner'
import {
  Phone, Loader2, Plus, ArrowDownCircle, ArrowUpCircle, RefreshCw, Zap,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { billingApi, type TelephonyLedgerItem } from '@/api/billing'
import { ApiClientError } from '@/api/client'

const TOPUP_PRESETS = [10, 25, 50, 100]
const MIN_TOPUP = 5
const MAX_TOPUP = 500

const fmtUSD = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

/** Rates span dollars (a number) to sub-cents (a segment) — scale the precision. */
const fmtRate = (n: number) =>
  n >= 0.1 ? fmtUSD(n) : `$${n.toFixed(4)}`

function errMsg(err: unknown, fallback: string) {
  return err instanceof ApiClientError ? err.error?.message || fallback : fallback
}

function ledgerIsCredit(item: TelephonyLedgerItem) {
  return item.amount_usd < 0 || item.type === 'topup' || item.type === 'refund'
}

function ledgerLabel(item: TelephonyLedgerItem) {
  if (item.description) return item.description
  if (item.type === 'topup') return 'Credit top-up'
  if (item.unit) return `${item.unit}${item.quantity ? ` ×${item.quantity}` : ''}`
  return item.type
}

export default function TelephonyCreditSettings() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [customAmount, setCustomAmount] = useState('')
  const [pendingAmount, setPendingAmount] = useState<number | null>(null)

  const { data: creditRes, isLoading } = useQuery({
    queryKey: ['telephony-credit'],
    queryFn: () => billingApi.getTelephonyCredit(),
  })
  const credit = creditRes?.data

  const { data: ratesRes } = useQuery({
    queryKey: ['telephony-rates'],
    queryFn: () => billingApi.getTelephonyRates(),
  })
  const enabledRates = useMemo(
    () => (ratesRes?.data ?? []).filter((r) => r.is_enabled),
    [ratesRes],
  )

  const { data: ledgerRes } = useQuery({
    queryKey: ['telephony-ledger'],
    queryFn: () => billingApi.getTelephonyLedger(25),
  })
  const ledger = ledgerRes?.data ?? []

  // Auto top-up local form state, seeded from the server once loaded.
  const [autoEnabled, setAutoEnabled] = useState(false)
  const [autoThreshold, setAutoThreshold] = useState('10')
  const [autoAmount, setAutoAmount] = useState('25')
  useEffect(() => {
    if (!credit) return
    setAutoEnabled(credit.auto_topup_enabled)
    if (credit.auto_topup_threshold_usd) setAutoThreshold(String(credit.auto_topup_threshold_usd))
    if (credit.auto_topup_amount_usd) setAutoAmount(String(credit.auto_topup_amount_usd))
  }, [credit])

  // Handle the Stripe return for a top-up (success_url lands on ?tab=billing&topup=...).
  useEffect(() => {
    const status = searchParams.get('topup')
    if (!status) return
    const sessionId = searchParams.get('session_id')

    if (status === 'success' && sessionId) {
      billingApi
        .verifyTelephonyTopup(sessionId)
        .then((res) => {
          toast.success(`Credit added — balance is now ${fmtUSD(res?.data?.balance_usd ?? 0)}.`)
          queryClient.invalidateQueries({ queryKey: ['telephony-credit'] })
          queryClient.invalidateQueries({ queryKey: ['telephony-ledger'] })
        })
        .catch(() => toast.error('We could not confirm the top-up. If you were charged, it will appear shortly.'))
    } else if (status === 'cancelled') {
      toast('Top-up cancelled — no charge made.')
    }
    const next = new URLSearchParams(searchParams)
    next.delete('topup')
    next.delete('session_id')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams, queryClient])

  const topupMutation = useMutation({
    mutationFn: (amount: number) => billingApi.telephonyTopup(amount),
    onMutate: (amount) => setPendingAmount(amount),
    onSuccess: (res) => {
      const url = res?.data?.checkout_url
      if (url) {
        window.location.href = url
        return
      }
      toast.error('Could not start checkout. Please try again.')
      setPendingAmount(null)
    },
    onError: (err) => {
      toast.error(errMsg(err, 'Could not start the top-up. Please try again.'))
      setPendingAmount(null)
    },
  })

  const autoMutation = useMutation({
    mutationFn: () =>
      billingApi.setTelephonyAutoTopup({
        enabled: autoEnabled,
        threshold_usd: Number(autoThreshold) || undefined,
        amount_usd: Number(autoAmount) || undefined,
      }),
    onSuccess: () => {
      toast.success('Auto top-up saved.')
      queryClient.invalidateQueries({ queryKey: ['telephony-credit'] })
    },
    onError: (err) => toast.error(errMsg(err, 'Could not save auto top-up.')),
  })

  const startTopup = (amount: number) => {
    if (!Number.isFinite(amount) || amount < MIN_TOPUP || amount > MAX_TOPUP) {
      toast.error(`Enter an amount between ${fmtUSD(MIN_TOPUP)} and ${fmtUSD(MAX_TOPUP)}.`)
      return
    }
    topupMutation.mutate(Math.round(amount * 100) / 100)
  }

  const status = credit?.is_empty ? 'empty' : credit?.is_low ? 'low' : 'ok'
  const statusPill = {
    ok: { label: 'Healthy', cls: 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400' },
    low: { label: 'Low balance', cls: 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400' },
    empty: { label: 'Empty', cls: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400' },
  }[status]

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <div className="border-t border-gray-200 dark:border-gray-700 pt-8 space-y-6">
      <div className="flex items-center gap-2">
        <Phone className="w-5 h-5 text-blue-600" />
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Telephony credit</h3>
      </div>
      <p className="-mt-4 text-sm text-gray-500 dark:text-gray-400">
        Prepaid balance for phone numbers, outbound calls and texts. It's charged at your plan's
        rates as you use it — and incoming calls and texts keep working even at zero.
      </p>

      {/* Balance + top-up */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Balance hero */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Current balance
            </span>
            <span className={cn('text-[11px] font-semibold px-2 py-0.5 rounded-full', statusPill.cls)}>
              {statusPill.label}
            </span>
          </div>
          <div className="mt-2 text-4xl font-bold text-gray-900 dark:text-white tabular-nums">
            {fmtUSD(credit?.balance_usd ?? 0)}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-gray-400 dark:text-gray-500 text-xs">Purchased (all-time)</div>
              <div className="font-semibold text-gray-700 dark:text-gray-200 tabular-nums">
                {fmtUSD(credit?.lifetime_purchased_usd ?? 0)}
              </div>
            </div>
            <div>
              <div className="text-gray-400 dark:text-gray-500 text-xs">Spent (all-time)</div>
              <div className="font-semibold text-gray-700 dark:text-gray-200 tabular-nums">
                {fmtUSD(credit?.lifetime_spent_usd ?? 0)}
              </div>
            </div>
          </div>
        </div>

        {/* Top-up */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-5">
          <span className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Add credit
          </span>
          <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
            {TOPUP_PRESETS.map((amt) => {
              const busy = topupMutation.isPending && pendingAmount === amt
              return (
                <button
                  key={amt}
                  onClick={() => startTopup(amt)}
                  disabled={topupMutation.isPending}
                  className={cn(
                    'py-2 rounded-lg text-sm font-semibold border transition-colors inline-flex items-center justify-center gap-1.5',
                    'border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-800',
                    topupMutation.isPending && !busy && 'opacity-60',
                  )}
                >
                  {busy && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  ${amt}
                </button>
              )
            })}
          </div>
          <div className="mt-3 flex items-center gap-2">
            <div className="relative flex-1">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
              <input
                type="number"
                inputMode="decimal"
                min={MIN_TOPUP}
                max={MAX_TOPUP}
                value={customAmount}
                onChange={(e) => setCustomAmount(e.target.value)}
                placeholder="Custom"
                className="w-full pl-7 pr-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              onClick={() => startTopup(Number(customAmount))}
              disabled={topupMutation.isPending || !customAmount}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {topupMutation.isPending && pendingAmount === Number(customAmount)
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <Plus className="w-4 h-4" />}
              Add
            </button>
          </div>
          <p className="mt-2 text-[11px] text-gray-400 dark:text-gray-500">
            {fmtUSD(MIN_TOPUP)}–{fmtUSD(MAX_TOPUP)} per top-up. Secure checkout via Stripe.
          </p>
        </div>
      </div>

      {/* Auto top-up */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-500" />
            <div>
              <div className="text-sm font-semibold text-gray-900 dark:text-white">Auto top-up</div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Refill automatically before you run dry.
              </div>
            </div>
          </div>
          <button
            role="switch"
            aria-checked={autoEnabled}
            onClick={() => setAutoEnabled((v) => !v)}
            className={cn(
              'relative w-11 h-6 rounded-full transition-colors shrink-0',
              autoEnabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600',
            )}
          >
            <span className={cn(
              'absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform',
              autoEnabled ? 'translate-x-5' : 'translate-x-0.5',
            )} />
          </button>
        </div>

        {autoEnabled && (
          <div className="mt-4 flex flex-wrap items-end gap-4">
            <label className="text-sm">
              <span className="block text-xs text-gray-500 dark:text-gray-400 mb-1">When balance drops below</span>
              <div className="relative w-28">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
                <input
                  type="number" min={2} max={MAX_TOPUP} value={autoThreshold}
                  onChange={(e) => setAutoThreshold(e.target.value)}
                  className="w-full pl-7 pr-2 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </label>
            <label className="text-sm">
              <span className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Add this much</span>
              <div className="relative w-28">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
                <input
                  type="number" min={MIN_TOPUP} max={MAX_TOPUP} value={autoAmount}
                  onChange={(e) => setAutoAmount(e.target.value)}
                  className="w-full pl-7 pr-2 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </label>
          </div>
        )}

        {autoEnabled && !credit?.has_payment_method && (
          <p className="mt-3 text-xs text-amber-600 dark:text-amber-400">
            Make one manual top-up first — that saves your card so auto top-up has something to charge.
          </p>
        )}

        <button
          onClick={() => autoMutation.mutate()}
          disabled={autoMutation.isPending}
          className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-60"
        >
          {autoMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Save auto top-up
        </button>
      </div>

      {/* What you pay */}
      {enabledRates.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-5">
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">What you pay</h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2">
            {enabledRates.map((r) => (
              <div key={r.unit} className="flex items-baseline justify-between text-sm border-b border-gray-100 dark:border-gray-800 py-1.5">
                <span className="text-gray-600 dark:text-gray-300">{r.label}</span>
                <span className="font-semibold text-gray-900 dark:text-white tabular-nums">{fmtRate(r.price_usd)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent activity */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Recent activity</h4>
        {ledger.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-gray-500 py-4 text-center">
            No telephony transactions yet.
          </p>
        ) : (
          <ul className="divide-y divide-gray-100 dark:divide-gray-800">
            {ledger.map((item) => {
              const credited = ledgerIsCredit(item)
              const abs = Math.abs(item.amount_usd)
              return (
                <li key={item.id} className="flex items-center gap-3 py-2.5">
                  {credited
                    ? <ArrowDownCircle className="w-4 h-4 text-green-500 shrink-0" />
                    : <ArrowUpCircle className="w-4 h-4 text-gray-400 shrink-0" />}
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-gray-900 dark:text-white truncate">{ledgerLabel(item)}</div>
                    <div className="text-[11px] text-gray-400 dark:text-gray-500">
                      {new Date(item.created_at).toLocaleString('en-US', {
                        month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
                      })}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className={cn(
                      'text-sm font-semibold tabular-nums',
                      credited ? 'text-green-600 dark:text-green-400' : 'text-gray-900 dark:text-white',
                    )}>
                      {credited ? '+' : '−'}{fmtUSD(abs)}
                    </div>
                    <div className="text-[11px] text-gray-400 dark:text-gray-500 tabular-nums">
                      {fmtUSD(item.balance_after_usd)}
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
