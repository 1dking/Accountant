/**
 * Widget iframe content — /embed/:widgetKey (no auth, outside AppShell).
 *
 * This is the ENTIRE embeddable widget: collapsed button + expanded
 * form, both rendered here. widget.js on the third-party page only
 * embeds this page in an iframe and resizes it on postMessage — every
 * API call (config, submit) happens from here, same-origin to the API,
 * so no CORS relaxation is needed anywhere in this feature.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { useQuery, useMutation } from '@tanstack/react-query'
import { MessageCircle, X, Send } from 'lucide-react'
import { widgetApi } from '@/api/widget'

const EXPANDED = { width: '360px', height: '480px' }
const COLLAPSED = { width: '64px', height: '64px' }

function postToParent(msg: Record<string, unknown>) {
  window.parent.postMessage({ source: 'obrain-widget', ...msg }, '*')
}

export default function WidgetFramePage() {
  const { widgetKey } = useParams<{ widgetKey: string }>()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [message, setMessage] = useState('')
  const [website, setWebsite] = useState('') // honeypot
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data } = useQuery({
    queryKey: ['public-widget-config', widgetKey],
    queryFn: () => widgetApi.getPublicConfig(widgetKey!),
    enabled: !!widgetKey,
  })
  const config = data?.data

  // This page only ever renders inside the tiny widget.js iframe — strip
  // the app's default body margin/background so the collapsed button and
  // expanded panel fill exactly the space the parent iframe gives them.
  useEffect(() => {
    const prevMargin = document.body.style.margin
    const prevBg = document.body.style.background
    document.body.style.margin = '0'
    document.body.style.background = 'transparent'
    return () => {
      document.body.style.margin = prevMargin
      document.body.style.background = prevBg
    }
  }, [])

  useEffect(() => {
    if (config?.position === 'bottom-left') {
      postToParent({ type: 'position', position: 'bottom-left' })
    }
  }, [config?.position])

  useEffect(() => {
    const size = open ? EXPANDED : COLLAPSED
    postToParent({ type: 'resize', width: size.width, height: size.height, expanded: open })
  }, [open])

  const submitMutation = useMutation({
    mutationFn: () =>
      widgetApi.submit(widgetKey!, {
        name: name.trim(),
        email: email.trim().toLowerCase(),
        phone: phone.trim() || undefined,
        message: message.trim() || undefined,
        website: website.trim() || undefined,
      }),
    onSuccess: () => setSent(true),
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : 'Could not send your message.')
    },
  })

  const submit = () => {
    if (!name.trim() || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      setError('Enter your name and a valid email')
      return
    }
    setError(null)
    submitMutation.mutate()
  }

  if (!config) {
    return <div className="w-full h-full" />
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="w-16 h-16 rounded-full flex items-center justify-center shadow-lg"
        style={{ background: config.button_color }}
        aria-label="Open contact widget"
      >
        <MessageCircle className="w-6 h-6 text-white" />
      </button>
    )
  }

  return (
    <div
      className="w-full h-full flex flex-col rounded-2xl overflow-hidden"
      style={{ background: config.bg_color, color: config.text_color }}
    >
      <div
        className="flex items-center justify-between px-4 py-3 shrink-0"
        style={{ background: config.button_color }}
      >
        <p className="text-sm font-semibold text-white">{config.greeting_title}</p>
        <button onClick={() => setOpen(false)} className="text-white/80 hover:text-white">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {sent ? (
          <div className="h-full flex items-center justify-center text-center">
            <p className="text-sm opacity-80">Thanks for reaching out — we'll be in touch soon.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {config.greeting_message && <p className="text-sm opacity-80">{config.greeting_message}</p>}
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              className="w-full rounded-lg border border-black/10 bg-white/70 px-3 py-2 text-sm text-gray-900 focus:outline-none"
            />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              className="w-full rounded-lg border border-black/10 bg-white/70 px-3 py-2 text-sm text-gray-900 focus:outline-none"
            />
            {config.collect_phone && (
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="Phone (optional)"
                className="w-full rounded-lg border border-black/10 bg-white/70 px-3 py-2 text-sm text-gray-900 focus:outline-none"
              />
            )}
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={3}
              placeholder="How can we help?"
              className="w-full rounded-lg border border-black/10 bg-white/70 px-3 py-2 text-sm text-gray-900 focus:outline-none"
            />
            {/* Honeypot — hidden from real visitors via CSS, not `type=hidden`
                (bots skip type=hidden less reliably than they skip
                off-screen-but-tabbable-looking fields). */}
            <input
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              tabIndex={-1}
              autoComplete="off"
              className="absolute -left-[9999px] w-px h-px opacity-0"
              aria-hidden="true"
            />
            {error && <p className="text-xs text-red-500">{error}</p>}
            <button
              onClick={submit}
              disabled={submitMutation.isPending}
              className="w-full flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              style={{ background: config.button_color }}
            >
              <Send className="w-4 h-4" />
              {submitMutation.isPending ? 'Sending…' : 'Send'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
