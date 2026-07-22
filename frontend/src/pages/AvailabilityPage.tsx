/**
 * Availability — /availability (authenticated).
 *
 * Arivio-style availability editor (design ported from Arivio's
 * Settings → Availability): weekly-hours grid, meeting duration,
 * buffer, notice/advance windows, timezone. Writes the existing
 * SchedulingCalendar fields (availability_json, duration_minutes,
 * buffer_minutes, min_notice_hours, max_advance_days, timezone) — the
 * backend slot computation already consumes exactly this shape.
 *
 * The weekly grid edits ONE window per day (Arivio's model). The
 * backend JSON supports multiple windows per day; if an existing
 * calendar has more than one, only the first is shown and saving
 * writes back what the grid shows.
 *
 * An Advanced section keeps multi-calendar management (create/select/
 * delete, team & round-robin types) so those existing backend features
 * stay reachable after the old SchedulingPage was retired.
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CalendarDays, ChevronDown, ChevronRight, Save, Trash2 } from 'lucide-react'
import { schedulingApi } from '@/api/scheduling'
import { toast } from 'sonner'

interface CalendarItem {
  id: string
  name: string
  slug: string
  calendar_type: string
  duration_minutes: number
  is_active: boolean
}

interface CalendarDetail extends CalendarItem {
  description: string | null
  buffer_minutes: number
  max_advance_days: number
  min_notice_hours: number
  availability_json: string | null
  timezone: string
}

const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] as const

type DayRow = { enabled: boolean; start: string; end: string }
type WeekGrid = Record<(typeof DAYS)[number], DayRow>

const DEFAULT_GRID: WeekGrid = Object.fromEntries(
  DAYS.map((d) => [
    d,
    { enabled: !['saturday', 'sunday'].includes(d), start: '09:00', end: '17:00' },
  ])
) as WeekGrid

const TIMEZONES = [
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Toronto',
  'America/Vancouver',
  'Europe/London',
  'Europe/Paris',
  'Australia/Sydney',
]

function gridFromJson(json: string | null): WeekGrid {
  if (!json) return { ...DEFAULT_GRID }
  try {
    const parsed = JSON.parse(json) as Record<string, Array<{ start: string; end: string }>>
    return Object.fromEntries(
      DAYS.map((d) => {
        const windows = parsed[d]
        if (windows && windows.length > 0) {
          return [d, { enabled: true, start: windows[0].start, end: windows[0].end }]
        }
        return [d, { enabled: false, start: '09:00', end: '17:00' }]
      })
    ) as WeekGrid
  } catch {
    return { ...DEFAULT_GRID }
  }
}

function gridToJson(grid: WeekGrid): string {
  const out: Record<string, Array<{ start: string; end: string }>> = {}
  for (const d of DAYS) {
    if (grid[d].enabled) out[d] = [{ start: grid[d].start, end: grid[d].end }]
  }
  return JSON.stringify(out)
}

const INPUT =
  'px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100'

export default function AvailabilityPage() {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const [grid, setGrid] = useState<WeekGrid>({ ...DEFAULT_GRID })
  const [duration, setDuration] = useState(30)
  const [buffer, setBuffer] = useState(0)
  const [minNotice, setMinNotice] = useState(1)
  const [maxAdvance, setMaxAdvance] = useState(60)
  const [tz, setTz] = useState('America/New_York')

  const { data: calendarsData, isLoading } = useQuery({
    queryKey: ['scheduling-calendars'],
    queryFn: () => schedulingApi.listCalendars() as Promise<{ data: CalendarItem[] }>,
  })
  const calendars = calendarsData?.data ?? []
  const activeId = selectedId ?? calendars[0]?.id ?? null

  const { data: detailData } = useQuery({
    queryKey: ['scheduling-calendar', activeId],
    queryFn: () => schedulingApi.getCalendar(activeId!) as Promise<{ data: CalendarDetail }>,
    enabled: !!activeId,
  })
  const detail = detailData?.data

  // Render-time state sync (React's documented "adjusting state when a
  // prop changes" pattern) — re-seed the form whenever a different
  // calendar's detail arrives, without an effect.
  const [syncedId, setSyncedId] = useState<string | null>(null)
  if (detail && detail.id !== syncedId) {
    setSyncedId(detail.id)
    setGrid(gridFromJson(detail.availability_json))
    setDuration(detail.duration_minutes)
    setBuffer(detail.buffer_minutes)
    setMinNotice(detail.min_notice_hours)
    setMaxAdvance(detail.max_advance_days)
    setTz(detail.timezone)
  }

  const createMutation = useMutation({
    mutationFn: () => schedulingApi.createCalendar({ name: 'Meetings' }),
    onSuccess: (res: unknown) => {
      queryClient.invalidateQueries({ queryKey: ['scheduling-calendars'] })
      const created = (res as { data?: { id?: string } })?.data
      if (created?.id) setSelectedId(created.id)
      toast.success('Booking calendar created')
    },
  })

  const saveMutation = useMutation({
    mutationFn: () =>
      schedulingApi.updateCalendar(activeId!, {
        availability_json: gridToJson(grid),
        duration_minutes: duration,
        buffer_minutes: buffer,
        min_notice_hours: minNotice,
        max_advance_days: maxAdvance,
        timezone: tz,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduling-calendar', activeId] })
      toast.success('Availability saved')
    },
    onError: () => toast.error('Failed to save availability'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => schedulingApi.deleteCalendar(id),
    onSuccess: () => {
      setSelectedId(null)
      queryClient.invalidateQueries({ queryKey: ['scheduling-calendars'] })
      toast.success('Calendar deleted')
    },
  })

  if (isLoading) {
    return <div className="p-6 text-gray-500">Loading availability…</div>
  }

  if (calendars.length === 0) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <div className="text-center py-16 bg-white dark:bg-gray-900 border rounded-lg">
          <CalendarDays className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">
            Set up your booking calendar
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4 max-w-sm mx-auto">
            Create a calendar to share a public booking link where clients pick a time that works.
          </p>
          <button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
            className="px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50 hover:opacity-90"
            style={{ background: 'var(--brand-primary)' }}
          >
            {createMutation.isPending ? 'Creating…' : 'Create booking calendar'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Availability</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Set your weekly hours and meeting preferences.
          </p>
        </div>
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || !activeId}
          className="flex items-center gap-2 px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50 hover:opacity-90"
          style={{ background: 'var(--brand-primary)' }}
        >
          <Save className="w-4 h-4" />
          {saveMutation.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>

      {calendars.length > 1 && (
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Calendar</label>
          <select value={activeId ?? ''} onChange={(e) => setSelectedId(e.target.value)} className={INPUT}>
            {calendars.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.calendar_type})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Weekly hours grid */}
      <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 mb-4">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Weekly hours</h2>
        <div className="space-y-2">
          {DAYS.map((d) => (
            <div key={d} className="flex items-center gap-3">
              <label className="flex items-center gap-2 w-32">
                <input
                  type="checkbox"
                  checked={grid[d].enabled}
                  onChange={(e) => setGrid((g) => ({ ...g, [d]: { ...g[d], enabled: e.target.checked } }))}
                />
                <span className="text-sm capitalize text-gray-700 dark:text-gray-300">{d}</span>
              </label>
              {grid[d].enabled ? (
                <div className="flex items-center gap-2">
                  <input
                    type="time"
                    value={grid[d].start}
                    onChange={(e) => setGrid((g) => ({ ...g, [d]: { ...g[d], start: e.target.value } }))}
                    className={INPUT}
                  />
                  <span className="text-gray-400 text-sm">to</span>
                  <input
                    type="time"
                    value={grid[d].end}
                    onChange={(e) => setGrid((g) => ({ ...g, [d]: { ...g[d], end: e.target.value } }))}
                    className={INPUT}
                  />
                </div>
              ) : (
                <span className="text-sm text-gray-400">Unavailable</span>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Meeting preferences */}
      <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 mb-4">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Meeting preferences</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Duration</label>
            <select value={duration} onChange={(e) => setDuration(Number(e.target.value))} className={`${INPUT} w-full`}>
              {[15, 20, 30, 45, 60, 90].map((m) => (
                <option key={m} value={m}>{m} minutes</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Buffer between meetings</label>
            <select value={buffer} onChange={(e) => setBuffer(Number(e.target.value))} className={`${INPUT} w-full`}>
              {[0, 5, 10, 15, 30].map((m) => (
                <option key={m} value={m}>{m === 0 ? 'None' : `${m} minutes`}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Minimum notice</label>
            <select value={minNotice} onChange={(e) => setMinNotice(Number(e.target.value))} className={`${INPUT} w-full`}>
              {[0, 1, 2, 4, 12, 24, 48].map((h) => (
                <option key={h} value={h}>{h === 0 ? 'None' : `${h} hour${h === 1 ? '' : 's'}`}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Book up to</label>
            <select value={maxAdvance} onChange={(e) => setMaxAdvance(Number(e.target.value))} className={`${INPUT} w-full`}>
              {[14, 30, 60, 90, 180].map((d) => (
                <option key={d} value={d}>{d} days ahead</option>
              ))}
            </select>
          </div>
          <div className="col-span-2">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Timezone</label>
            <select value={tz} onChange={(e) => setTz(e.target.value)} className={`${INPUT} w-full`}>
              {(TIMEZONES.includes(tz) ? TIMEZONES : [tz, ...TIMEZONES]).map((z) => (
                <option key={z} value={z}>{z}</option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {/* Advanced: multi-calendar management */}
      <section className="bg-white dark:bg-gray-900 border rounded-lg p-5">
        <button
          onClick={() => setShowAdvanced((s) => !s)}
          className="flex items-center gap-1.5 text-sm font-semibold text-gray-900 dark:text-gray-100"
        >
          {showAdvanced ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          Advanced — calendars & teams
        </button>
        {showAdvanced && (
          <div className="mt-4 space-y-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Multiple calendars support team and round-robin booking. Each has its own public link.
            </p>
            {calendars.map((c) => (
              <div key={c.id} className="flex items-center justify-between border rounded-lg p-3">
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    {c.name}
                    <span className="ml-2 text-xs text-gray-400 capitalize">{c.calendar_type.replace('_', ' ')}</span>
                  </p>
                  <p className="text-xs text-gray-500 font-mono mt-0.5">/book/{c.slug}</p>
                </div>
                <button
                  onClick={() => {
                    if (confirm(`Delete calendar "${c.name}"? Its public link will stop working.`)) {
                      deleteMutation.mutate(c.id)
                    }
                  }}
                  className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-950 rounded"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
            <button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending}
              className="text-sm text-[var(--brand-primary)] hover:underline disabled:opacity-50"
            >
              + New calendar
            </button>
          </div>
        )}
      </section>
    </div>
  )
}
