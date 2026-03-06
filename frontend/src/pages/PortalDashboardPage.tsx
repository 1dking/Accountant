import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getPortalDashboard } from '../api/portal'

export default function PortalDashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['portal', 'dashboard'],
    queryFn: getPortalDashboard,
  })

  const dashboard = data?.data

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">
              Welcome{dashboard?.contact_name ? `, ${dashboard.contact_name}` : ''}
            </h1>
            <p className="text-muted-foreground">{dashboard?.company_name}</p>
          </div>
          <nav className="flex gap-4 text-sm">
            <Link to="/portal" className="font-medium text-foreground">Dashboard</Link>
            <Link to="/portal/invoices" className="text-muted-foreground hover:text-foreground">Invoices</Link>
            <Link to="/portal/proposals" className="text-muted-foreground hover:text-foreground">Proposals</Link>
            <Link to="/portal/files" className="text-muted-foreground hover:text-foreground">Files</Link>
            <Link to="/portal/meetings" className="text-muted-foreground hover:text-foreground">Meetings</Link>
          </nav>
        </div>
      </header>

      <main className="p-6 max-w-5xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <Link to="/portal/invoices" className="border rounded-lg p-4 hover:bg-accent transition-colors">
            <div className="text-sm text-muted-foreground">Pending Invoices</div>
            <div className="text-2xl font-bold mt-1">{dashboard?.pending_invoices ?? 0}</div>
            <div className="text-sm text-muted-foreground mt-1">
              ${(dashboard?.total_outstanding ?? 0).toLocaleString()} outstanding
            </div>
          </Link>

          <Link to="/portal/proposals" className="border rounded-lg p-4 hover:bg-accent transition-colors">
            <div className="text-sm text-muted-foreground">Proposals</div>
            <div className="text-2xl font-bold mt-1">{dashboard?.pending_proposals ?? 0}</div>
            <div className="text-sm text-muted-foreground mt-1">awaiting response</div>
          </Link>

          <Link to="/portal/files" className="border rounded-lg p-4 hover:bg-accent transition-colors">
            <div className="text-sm text-muted-foreground">Shared Files</div>
            <div className="text-2xl font-bold mt-1">{dashboard?.shared_files ?? 0}</div>
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border rounded-lg p-4">
            <div className="text-sm text-muted-foreground">Upcoming Meetings</div>
            <div className="text-2xl font-bold mt-1">{dashboard?.upcoming_meetings ?? 0}</div>
            <Link to="/portal/meetings" className="text-sm text-primary hover:underline mt-2 inline-block">
              View all meetings
            </Link>
          </div>

          <div className="border rounded-lg p-4">
            <div className="text-sm text-muted-foreground">Total Outstanding</div>
            <div className="text-2xl font-bold mt-1">
              ${(dashboard?.total_outstanding ?? 0).toLocaleString()}
            </div>
            <Link to="/portal/invoices" className="text-sm text-primary hover:underline mt-2 inline-block">
              View invoices
            </Link>
          </div>
        </div>
      </main>
    </div>
  )
}
