import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import {
  Kanban,
  Plus,
  Search,
  DollarSign,
  User,
  Calendar,
} from 'lucide-react'
import { listProposals, type ProposalListItem, type ProposalStatus } from '@/api/proposals'
import { formatDate } from '@/lib/utils'

const PIPELINE_STAGES: { status: ProposalStatus; label: string; color: string }[] = [
  { status: 'draft', label: 'Draft', color: 'bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700' },
  { status: 'sent', label: 'Sent', color: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800' },
  { status: 'viewed', label: 'Viewed', color: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800' },
  { status: 'signed', label: 'Won', color: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' },
  { status: 'declined', label: 'Lost', color: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800' },
]

function formatCurrency(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 }).format(value)
}

export default function PipelinesPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['proposals', { page_size: '200' }],
    queryFn: () => listProposals({ page_size: '200' }),
  })

  const proposals: ProposalListItem[] = data?.data ?? []

  const filtered = proposals.filter((p) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      p.title.toLowerCase().includes(q) ||
      p.contact?.company_name?.toLowerCase().includes(q) ||
      p.contact?.contact_name?.toLowerCase().includes(q)
    )
  })

  const getStageProposals = (status: ProposalStatus) =>
    filtered.filter((p) => p.status === status)

  const getStageTotal = (status: ProposalStatus) =>
    getStageProposals(status).reduce((sum, p) => sum + (p.value || 0), 0)

  return (
    <div className="p-6 h-full flex flex-col">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Kanban className="h-6 w-6" />
            Sales Pipeline
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Visual overview of your proposal pipeline
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 text-sm w-64"
              placeholder="Search proposals..."
            />
          </div>
          <button
            onClick={() => navigate('/proposals')}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition text-sm"
          >
            <Plus className="h-4 w-4" />
            New Proposal
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex-1 flex items-center justify-center text-gray-400">Loading pipeline...</div>
      ) : (
        <div className="flex-1 overflow-x-auto">
          <div className="flex gap-4 h-full min-w-max pb-4">
            {PIPELINE_STAGES.map((stage) => {
              const items = getStageProposals(stage.status)
              const total = getStageTotal(stage.status)
              return (
                <div key={stage.status} className="w-72 flex flex-col">
                  {/* Column header */}
                  <div className={`rounded-t-xl border px-4 py-3 ${stage.color}`}>
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                        {stage.label}
                      </h3>
                      <span className="text-xs bg-white/80 dark:bg-gray-900/80 text-gray-600 dark:text-gray-400 px-2 py-0.5 rounded-full font-medium">
                        {items.length}
                      </span>
                    </div>
                    {total > 0 && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {formatCurrency(total)}
                      </p>
                    )}
                  </div>

                  {/* Cards */}
                  <div className="flex-1 overflow-y-auto space-y-2 p-2 bg-gray-50/50 dark:bg-gray-800/30 rounded-b-xl border border-t-0 border-gray-200 dark:border-gray-700">
                    {items.length === 0 ? (
                      <p className="text-xs text-gray-400 dark:text-gray-500 text-center py-8">
                        No proposals
                      </p>
                    ) : (
                      items.map((proposal) => (
                        <button
                          key={proposal.id}
                          onClick={() => navigate(`/proposals/${proposal.id}/edit`)}
                          className="w-full text-left bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 hover:border-blue-300 dark:hover:border-blue-700 transition-colors shadow-sm"
                        >
                          <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                            {proposal.title}
                          </p>
                          {proposal.contact && (
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-1 truncate">
                              <User className="h-3 w-3" />
                              {proposal.contact.company_name || proposal.contact.contact_name}
                            </p>
                          )}
                          <div className="flex items-center justify-between mt-2">
                            {proposal.value > 0 && (
                              <span className="text-xs font-medium text-green-600 dark:text-green-400 flex items-center gap-0.5">
                                <DollarSign className="h-3 w-3" />
                                {formatCurrency(proposal.value)}
                              </span>
                            )}
                            <span className="text-[10px] text-gray-400 dark:text-gray-500 flex items-center gap-0.5 ml-auto">
                              <Calendar className="h-3 w-3" />
                              {formatDate(proposal.created_at)}
                            </span>
                          </div>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
