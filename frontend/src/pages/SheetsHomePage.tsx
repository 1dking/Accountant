import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listOfficeDocs, createOfficeDoc } from '@/api/office'
import OfficeDocCard from '@/components/office/OfficeDocCard'
import { useDebounce } from '@/hooks/useDebounce'
import { Table2, Plus, Search, DollarSign, Receipt, TrendingUp, BookOpen } from 'lucide-react'
import { cn } from '@/lib/utils'

type ViewTab = 'owned' | 'shared' | 'starred'

const TEMPLATES = [
  { title: 'Blank', icon: Plus, description: 'Empty spreadsheet' },
  { title: 'Budget', icon: DollarSign, description: 'Budget tracker' },
  { title: 'Invoice', icon: Receipt, description: 'Invoice template' },
  { title: 'Expense Tracker', icon: TrendingUp, description: 'Track expenses' },
  { title: 'Ledger', icon: BookOpen, description: 'General ledger' },
]

export default function SheetsHomePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<ViewTab>('owned')
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 300)

  const { data, isLoading } = useQuery({
    queryKey: ['office-docs', 'spreadsheet', activeTab, debouncedSearch],
    queryFn: () =>
      listOfficeDocs({
        doc_type: 'spreadsheet',
        view: activeTab,
        search: debouncedSearch || undefined,
      }),
  })

  const documents = data?.data ?? []

  const createMutation = useMutation({
    mutationFn: (title: string) =>
      createOfficeDoc({ title: title || undefined, doc_type: 'spreadsheet' }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['office-docs'] })
      navigate(`/sheets/${res.data.id}`)
    },
  })

  const handleTemplateClick = (template: typeof TEMPLATES[0]) => {
    const title = template.title === 'Blank' ? 'Untitled spreadsheet' : template.title
    createMutation.mutate(title)
  }

  const tabs: { key: ViewTab; label: string }[] = [
    { key: 'owned', label: 'Owned by me' },
    { key: 'shared', label: 'Shared with me' },
    { key: 'starred', label: 'Starred' },
  ]

  return (
    <div className="min-h-[calc(100vh-49px)] bg-gray-50 dark:bg-gray-950">
      {/* Header with templates */}
      <div className="bg-white dark:bg-gray-900 border-b dark:border-gray-700">
        <div className="max-w-5xl mx-auto px-6 py-8">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <Table2 className="h-7 w-7 text-green-600" />
              Sheets
            </h1>
            <button
              onClick={() => createMutation.mutate('Untitled spreadsheet')}
              disabled={createMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              Blank Spreadsheet
            </button>
          </div>

          {/* Templates */}
          <div>
            <h2 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-3">Start a new spreadsheet</h2>
            <div className="flex gap-4">
              {TEMPLATES.map((template) => {
                const Icon = template.icon
                return (
                  <button
                    key={template.title}
                    onClick={() => handleTemplateClick(template)}
                    disabled={createMutation.isPending}
                    className="group flex flex-col items-center gap-2 p-4 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700 hover:border-green-400 hover:bg-green-50/50 dark:hover:bg-green-900/20 transition-colors w-32 disabled:opacity-50"
                  >
                    <div className="h-16 w-full bg-green-50 dark:bg-green-900/30 rounded flex items-center justify-center group-hover:bg-green-100 dark:group-hover:bg-green-900/50 transition-colors">
                      <Icon className="h-8 w-8 text-green-400 group-hover:text-green-600" />
                    </div>
                    <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{template.title}</span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Documents list */}
      <div className="max-w-5xl mx-auto px-6 py-6">
        {/* Search + Tabs */}
        <div className="flex items-center gap-4 mb-6">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 dark:text-gray-500" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search spreadsheets..."
              className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 dark:bg-gray-800 dark:text-gray-100"
            />
          </div>
          <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={cn(
                  'px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
                  activeTab === tab.key
                    ? 'bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100'
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Grid */}
        {isLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-48 bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 animate-pulse" />
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-16">
            <Table2 className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-gray-900 dark:text-gray-100 font-medium mb-1">
              {search ? 'No spreadsheets found' : 'No spreadsheets yet'}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {search
                ? 'Try a different search term'
                : 'Create a new spreadsheet to get started'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {documents.map((doc) => (
              <OfficeDocCard key={doc.id} document={doc} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
