import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getPortalProposals } from '../api/portal'

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    draft: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300',
    sent: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
    viewed: 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-400',
    accepted: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
    rejected: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
    signed: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
    expired: 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400',
  }
  return colors[status] ?? 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300'
}

export default function PortalProposalsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['portal', 'proposals'],
    queryFn: getPortalProposals,
  })

  const proposals = data?.data ?? []

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <h1 className="text-2xl font-bold">Proposals</h1>
          <nav className="flex gap-4 text-sm">
            <Link to="/portal" className="text-muted-foreground hover:text-foreground">Dashboard</Link>
            <Link to="/portal/invoices" className="text-muted-foreground hover:text-foreground">Invoices</Link>
            <Link to="/portal/proposals" className="font-medium text-foreground">Proposals</Link>
            <Link to="/portal/files" className="text-muted-foreground hover:text-foreground">Files</Link>
            <Link to="/portal/meetings" className="text-muted-foreground hover:text-foreground">Meetings</Link>
          </nav>
        </div>
      </header>

      <main className="p-6 max-w-5xl mx-auto">
        {isLoading ? (
          <p className="text-muted-foreground">Loading proposals...</p>
        ) : proposals.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No proposals found.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {proposals.map((proposal) => (
              <div key={proposal.id} className="border rounded-lg p-4 hover:bg-muted/30 transition-colors">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium">{proposal.title}</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Created {new Date(proposal.created_at).toLocaleDateString()}
                      {proposal.total != null && (
                        <> -- ${proposal.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}</>
                      )}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${statusBadge(proposal.status)}`}>
                      {proposal.status}
                    </span>
                    {proposal.signing_token && proposal.status !== 'signed' && proposal.status !== 'rejected' && (
                      <Link
                        to={`/proposals/sign/${proposal.signing_token}`}
                        className="inline-block px-3 py-1 bg-primary text-primary-foreground text-xs font-medium rounded hover:opacity-90"
                      >
                        Review & Sign
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
