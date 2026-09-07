import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getPortalInvoices } from '../api/portal'
import { useTranslation } from 'react-i18next'

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    draft: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300',
    sent: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
    viewed: 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-400',
    paid: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
    overdue: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
    cancelled: 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400',
    partially_paid: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400',
  }
  return colors[status] ?? 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300'
}

export default function PortalInvoicesPage() {
  const { t } = useTranslation('ui')
  const { data, isLoading } = useQuery({
    queryKey: ['portal', 'invoices'],
    queryFn: getPortalInvoices,
  })

  const invoices = data?.data ?? []

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <h1 className="text-2xl font-bold">{t('ui:PortalInvoicesPage.invoices')}</h1>
          <nav className="flex gap-4 text-sm">
            <Link to="/portal" className="text-muted-foreground hover:text-foreground">{t('ui:PortalInvoicesPage.dashboard')}</Link>
            <Link to="/portal/invoices" className="font-medium text-foreground">{t('ui:PortalInvoicesPage.invoices')}</Link>
            <Link to="/portal/proposals" className="text-muted-foreground hover:text-foreground">{t('ui:PortalInvoicesPage.proposals')}</Link>
            <Link to="/portal/files" className="text-muted-foreground hover:text-foreground">{t('ui:PortalInvoicesPage.files')}</Link>
            <Link to="/portal/meetings" className="text-muted-foreground hover:text-foreground">{t('ui:PortalInvoicesPage.meetings')}</Link>
          </nav>
        </div>
      </header>

      <main className="p-6 max-w-5xl mx-auto">
        {isLoading ? (
          <p className="text-muted-foreground">{t('ui:PortalInvoicesPage.loadingInvoices')}</p>
        ) : invoices.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground">{t('ui:PortalInvoicesPage.noInvoicesFound')}</p>
          </div>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">{t('ui:PortalInvoicesPage.invoice')}</th>
                  <th className="text-left px-4 py-3 font-medium">{t('ui:PortalInvoicesPage.issueDate')}</th>
                  <th className="text-left px-4 py-3 font-medium">{t('ui:PortalInvoicesPage.dueDate')}</th>
                  <th className="text-right px-4 py-3 font-medium">{t('ui:PortalInvoicesPage.amount')}</th>
                  <th className="text-left px-4 py-3 font-medium">{t('ui:PortalInvoicesPage.status')}</th>
                  <th className="text-right px-4 py-3 font-medium">{t('ui:PortalInvoicesPage.action')}</th>
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
                         {t('ui:PortalInvoicesPage.payNow')}
                        </a>
                      ) : inv.status === 'paid' ? (
                        <span className="text-xs text-green-600 font-medium">{t('ui:PortalInvoicesPage.paid')}</span>
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
