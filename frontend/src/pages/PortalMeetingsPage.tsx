import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getPortalMeetings } from '../api/portal'

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    scheduled: 'bg-blue-100 text-blue-700',
    in_progress: 'bg-green-100 text-green-700',
    completed: 'bg-gray-100 text-gray-700',
    cancelled: 'bg-red-100 text-red-500',
  }
  return colors[status] ?? 'bg-gray-100 text-gray-700'
}

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export default function PortalMeetingsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['portal', 'meetings'],
    queryFn: getPortalMeetings,
  })

  const meetings = data?.data ?? []

  const upcoming = meetings.filter(
    (m) => m.status === 'scheduled' || m.status === 'in_progress'
  )
  const past = meetings.filter(
    (m) => m.status === 'completed' || m.status === 'cancelled'
  )

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <h1 className="text-2xl font-bold">Meetings</h1>
          <nav className="flex gap-4 text-sm">
            <Link to="/portal" className="text-muted-foreground hover:text-foreground">Dashboard</Link>
            <Link to="/portal/invoices" className="text-muted-foreground hover:text-foreground">Invoices</Link>
            <Link to="/portal/proposals" className="text-muted-foreground hover:text-foreground">Proposals</Link>
            <Link to="/portal/files" className="text-muted-foreground hover:text-foreground">Files</Link>
            <Link to="/portal/meetings" className="font-medium text-foreground">Meetings</Link>
          </nav>
        </div>
      </header>

      <main className="p-6 max-w-5xl mx-auto">
        {isLoading ? (
          <p className="text-muted-foreground">Loading meetings...</p>
        ) : meetings.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No meetings found.</p>
          </div>
        ) : (
          <div className="space-y-8">
            {upcoming.length > 0 && (
              <section>
                <h2 className="text-lg font-semibold mb-3">Upcoming</h2>
                <div className="space-y-3">
                  {upcoming.map((meeting) => (
                    <div key={meeting.id} className="border rounded-lg p-4 hover:bg-muted/30 transition-colors">
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-medium">{meeting.title}</h3>
                          <p className="text-sm text-muted-foreground mt-1">
                            {formatDateTime(meeting.scheduled_start)}
                            {meeting.scheduled_end && (
                              <> - {formatDateTime(meeting.scheduled_end)}</>
                            )}
                          </p>
                        </div>
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${statusBadge(meeting.status)}`}>
                          {meeting.status.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {past.length > 0 && (
              <section>
                <h2 className="text-lg font-semibold mb-3">Past</h2>
                <div className="space-y-3">
                  {past.map((meeting) => (
                    <div key={meeting.id} className="border rounded-lg p-4 opacity-70">
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-medium">{meeting.title}</h3>
                          <p className="text-sm text-muted-foreground mt-1">
                            {formatDateTime(meeting.scheduled_start)}
                          </p>
                        </div>
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${statusBadge(meeting.status)}`}>
                          {meeting.status.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
