/** Shared action-config editor -- a JSON textarea, used both by the legacy
 * step-list editor (WorkflowsPage) and the canvas node drawer
 * (NodeConfigDrawer). Kept intentionally simple: the action library is large
 * and admin-authored JSON configs (subject/body templates, webhook URLs,
 * tag names, etc.) already cover every action type without a bespoke form
 * per type. */
interface StepConfigFormProps {
  label?: string
  value: string
  onChange: (value: string) => void
  rows?: number
}

export default function StepConfigForm({ label = 'Action Config (JSON)', value, onChange, rows = 4 }: StepConfigFormProps) {
  let parseError: string | null = null
  if (value.trim()) {
    try {
      JSON.parse(value)
    } catch {
      parseError = 'Not valid JSON'
    }
  }

  return (
    <div>
      <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">{label}</label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        className={`w-full px-2 py-1.5 text-xs font-mono border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100 resize-none ${
          parseError
            ? 'border-red-300 dark:border-red-700'
            : 'border-gray-200 dark:border-gray-700'
        }`}
      />
      {parseError && <p className="text-[11px] text-red-500 mt-0.5">{parseError}</p>}
    </div>
  )
}
