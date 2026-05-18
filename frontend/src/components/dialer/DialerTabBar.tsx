/**
 * Five-tab navigation for the dialer drawer. Tab metadata + active
 * state live here; tab content lives in the parent which switches
 * on the active key.
 */
import { Clock, Grid3x3, List, Mail, Users } from 'lucide-react'
import { cn } from '@/lib/utils'

export type DialerTabKey = 'recents' | 'contacts' | 'keypad' | 'voicemail' | 'queue'

const TABS: {
  key: DialerTabKey
  label: string
  icon: React.ElementType
}[] = [
  { key: 'recents', label: 'Recents', icon: Clock },
  { key: 'contacts', label: 'Contacts', icon: Users },
  { key: 'keypad', label: 'Keypad', icon: Grid3x3 },
  { key: 'voicemail', label: 'Voicemail', icon: Mail },
  { key: 'queue', label: 'Queue', icon: List },
]

export default function DialerTabBar({
  active,
  onChange,
  badges,
}: {
  active: DialerTabKey
  onChange: (key: DialerTabKey) => void
  badges?: Partial<Record<DialerTabKey, number>>
}) {
  return (
    <nav
      className="grid grid-cols-5 border-b border-white/10 shrink-0"
      aria-label="Dialer sections"
    >
      {TABS.map(({ key, label, icon: Icon }) => {
        const isActive = key === active
        const badge = badges?.[key]
        return (
          <button
            key={key}
            onClick={() => onChange(key)}
            aria-current={isActive ? 'page' : undefined}
            className={cn(
              'relative flex flex-col items-center gap-1 py-3 text-[11px] font-medium',
              'transition-colors',
              isActive
                ? 'text-[color:var(--lg-text-primary)]'
                : 'text-[color:var(--lg-text-muted)] hover:text-[color:var(--lg-text-secondary)]',
            )}
          >
            <span className="relative">
              <Icon className="h-4 w-4" />
              {badge != null && badge > 0 && (
                <span className="absolute -top-1.5 -right-2 min-w-[14px] h-[14px] px-1 rounded-full bg-pink-500 text-white text-[9px] font-bold flex items-center justify-center lg-breathing">
                  {badge > 9 ? '9+' : badge}
                </span>
              )}
            </span>
            <span>{label}</span>
            {isActive && (
              <span
                aria-hidden="true"
                className="absolute bottom-0 left-1/2 -translate-x-1/2 h-[2px] w-8 rounded-full"
                style={{
                  background:
                    'linear-gradient(90deg, #00d4ff, #8b5cf6, #ec4899)',
                  boxShadow: '0 0 8px rgba(139, 92, 246, 0.5)',
                }}
              />
            )}
          </button>
        )
      })}
    </nav>
  )
}
