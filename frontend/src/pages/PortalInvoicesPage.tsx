import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getPortalInvoices } from '../api/portal'

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-700',
    sent: 'bg-blue-100 text-blue-700',
    viewed: 'bg-indigo-100 text-indigo-700',
    paid: 'bg-green-100 text-green-700',
    overdue: 'bg-red-100 text-red-700',
    cancelled: 'bg-gray-100 text-gray-500',
    partially_paid: 'bg-yellow-100 text-yellow-700',
  }
  return colors[status] ?? 'bg-gray-100 text-gray-700'
}

export default function PortalInvoicesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['portal', 'invoices'],
    queryFn: getPortalInvoices,
  })

  const invoices = data?.data ?? []

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <h1 className="text-2xl font-bold">Invoices</h1>
          <nav className="flex gap-4 text-sm">
            <Link to="/portal" className="text-muted-foreground hover:text-foreground">Dashboard</Link>
            <Link to="/portal/invoices" className="font-medium text-foreground">Invoices</Link>
            <Link to="/portal/proposals" className="text-muted-foreground hover:text-foreground">Proposals</Link>
            <Link to="/portal/files" className="text-muted-foreground hover:text-foreground">Files</Link>
            <Link to="/portal/meetings" className="text-muted-foreground hover:text-foreground">Meetings</Link>
          </nav>
        </div>
      </header>

      <main className="p-6 max-w-5xl mx-auto">
        {isLoading ? (
          <p className="text-muted-foreground">Loading invoices...</p>
        ) : invoices.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No invoices found.</p>
          </div>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Invoice #</th>
                  <th className="text-left px-4 py-3 font-medium">Issue Date</th>
                  <th className="text-left px-4 py-3 font-medium">Due Date</th>
                  <th className="text-right px-4 py-3 font-medium">Amount</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-right px-4 py-3 font-medium">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium">{inv.invoice_number}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {new Date(inv.issue_date).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {new Date(inv.due_date).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right font-medium">
                      {inv.currency === 'USD' ? '$' : inv.currency}{' '}
                      {inv.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${statusBadge(inv.status)}`}>
                        {inv.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {inv.payment_url && inv.status !== 'paid' ? (
                        <a
                          href={inv.payment_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-block px-3 py-1 bg-primary text-primary-foreground text-xs font-medium rounded hover:opacity-90"
                        >
                          Pay Now
                        </a>
                      ) : inv.status === 'paid' ? (
                        <span className="text-xs text-green-600 font-medium">Paid</span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}
