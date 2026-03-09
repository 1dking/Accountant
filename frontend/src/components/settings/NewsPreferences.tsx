import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Loader2, Newspaper } from 'lucide-react'
import { api } from '@/api/client'
import { cn } from '@/lib/utils'

const INDUSTRIES = [
  'Marketing', 'Real Estate', 'Finance', 'Healthcare', 'Tech',
  'Legal', 'Retail', 'Construction', 'Food & Hospitality', 'Education',
]

const TOPICS = [
  'AI & Automation', 'Social Media', 'SEO', 'Economy',
  'Local Business', 'Hiring & HR', 'Tax & Compliance', 'Industry Trends',
]

interface NewsPrefs {
  industries: string[]
  topics: string[]
}

function MultiSelect({
  label,
  options,
  selected,
  onToggle,
}: {
  label: string
  options: string[]
  selected: string[]
  onToggle: (value: string) => void
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{label}</label>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const isSelected = selected.includes(opt)
          return (
            <button
              key={opt}
              type="button"
              onClick={() => onToggle(opt)}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium border transition-colors',
                isSelected
                  ? 'bg-blue-50 dark:bg-blue-900/30 border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-300'
                  : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-600'
              )}
            >
              {isSelected && <Check className="h-3.5 w-3.5" />}
              {opt}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default function NewsPreferences() {
  const queryClient = useQueryClient()
  const [industries, setIndustries] = useState<string[]>([])
  const [topics, setTopics] = useState<string[]>([])
  const [saved, setSaved] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['news-preferences'],
    queryFn: () => api.get<{ data: NewsPrefs }>('/news/preferences'),
  })

  useEffect(() => {
    if (data?.data) {
      setIndustries(data.data.industries || [])
      setTopics(data.data.topics || [])
    }
  }, [data])

  const mutation = useMutation({
    mutationFn: (prefs: NewsPrefs) => api.put('/news/preferences', prefs),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['news-preferences'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    },
  })

  const toggleIndustry = (val: string) => {
    setIndustries((prev) => prev.includes(val) ? prev.filter((v) => v !== val) : [...prev, val])
  }

  const toggleTopic = (val: string) => {
    setTopics((prev) => prev.includes(val) ? prev.filter((v) => v !== val) : [...prev, val])
  }

  const handleSave = () => {
    mutation.mutate({ industries, topics })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Newspaper className="h-5 w-5 text-blue-600" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">News Preferences</h2>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Choose your industries and topics to get personalized news in your daily briefing and O-Brain.
        </p>
      </div>

      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-6 space-y-6">
        <MultiSelect
          label="Industries"
          options={INDUSTRIES}
          selected={industries}
          onToggle={toggleIndustry}
        />

        <MultiSelect
          label="Topics"
          options={TOPICS}
          selected={topics}
          onToggle={toggleTopic}
        />

        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={handleSave}
            disabled={mutation.isPending}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {mutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : saved ? (
              <Check className="h-4 w-4" />
            ) : null}
            {saved ? 'Saved!' : 'Save Preferences'}
          </button>
          {industries.length === 0 && topics.length === 0 && (
            <p className="text-xs text-gray-400">Select at least one industry or topic to receive news</p>
          )}
        </div>
      </div>
    </div>
  )
}
