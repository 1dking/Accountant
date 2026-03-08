import { useState, useEffect } from 'react'
import { Plus, Trash2, Code2 } from 'lucide-react'

interface TrackingPixelsSettingsProps {
  value: string
  onChange: (json: string) => void
}

interface CustomScript {
  name: string
  code: string
  placement: 'head' | 'body_start' | 'body_end'
  active: boolean
}

interface TrackingConfig {
  facebook_pixel?: string
  ga4?: string
  gtm?: string
  tiktok?: string
  linkedin?: string
  custom_scripts?: CustomScript[]
}

const PIXEL_FIELDS = [
  { key: 'facebook_pixel', label: 'Facebook Pixel ID', placeholder: '123456789012345' },
  { key: 'ga4', label: 'Google Analytics 4 ID', placeholder: 'G-XXXXXXXXXX' },
  { key: 'gtm', label: 'GTM Container ID', placeholder: 'GTM-XXXXXXX' },
  { key: 'tiktok', label: 'TikTok Pixel ID', placeholder: 'CXXXXXXXXXXXXXXXXX' },
  { key: 'linkedin', label: 'LinkedIn Insight Tag ID', placeholder: '1234567' },
] as const

const PLACEMENT_OPTIONS = [
  { value: 'head', label: 'Head' },
  { value: 'body_start', label: 'Body Start' },
  { value: 'body_end', label: 'Body End' },
]

function parseConfig(value: string): TrackingConfig {
  try {
    const parsed = JSON.parse(value)
    return typeof parsed === 'object' && parsed !== null ? parsed : {}
  } catch {
    return {}
  }
}

export default function TrackingPixelsSettings({ value, onChange }: TrackingPixelsSettingsProps) {
  const [config, setConfig] = useState<TrackingConfig>(() => parseConfig(value))

  useEffect(() => {
    setConfig(parseConfig(value))
  }, [value])

  function update(next: TrackingConfig) {
    setConfig(next)
    onChange(JSON.stringify(next))
  }

  function handlePixelChange(key: string, val: string) {
    const next = { ...config, [key]: val || undefined }
    if (!val) delete next[key as keyof TrackingConfig]
    update(next)
  }

  function addScript() {
    const scripts = [...(config.custom_scripts ?? [])]
    scripts.push({ name: '', code: '', placement: 'head', active: true })
    update({ ...config, custom_scripts: scripts })
  }

  function updateScript(index: number, field: keyof CustomScript, val: string | boolean) {
    const scripts = [...(config.custom_scripts ?? [])]
    scripts[index] = { ...scripts[index], [field]: val }
    update({ ...config, custom_scripts: scripts })
  }

  function deleteScript(index: number) {
    const scripts = [...(config.custom_scripts ?? [])]
    scripts.splice(index, 1)
    update({ ...config, custom_scripts: scripts.length > 0 ? scripts : undefined })
  }

  const scripts = config.custom_scripts ?? []

  return (
    <div className="space-y-6">
      {/* Tracking Pixel IDs */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Tracking Pixels</h3>
        <div className="space-y-3">
          {PIXEL_FIELDS.map((field) => (
            <div key={field.key}>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                {field.label}
              </label>
              <input
                type="text"
                value={(config as Record<string, any>)[field.key] ?? ''}
                onChange={(e) => handlePixelChange(field.key, e.target.value.trim())}
                placeholder={field.placeholder}
                className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg
                  bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100
                  placeholder-gray-400 dark:placeholder-gray-500
                  focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Custom Scripts */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Code2 className="w-4 h-4 text-gray-500 dark:text-gray-400" />
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Custom Scripts</h3>
          </div>
          <button
            type="button"
            onClick={addScript}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-blue-600 dark:text-blue-400
              bg-blue-50 dark:bg-blue-900/30 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Script
          </button>
        </div>

        {scripts.length === 0 && (
          <p className="text-xs text-gray-400 dark:text-gray-500 italic">
            No custom scripts added. Click "Add Script" to inject custom tracking code.
          </p>
        )}

        <div className="space-y-4">
          {scripts.map((script, i) => (
            <div
              key={i}
              className={`border rounded-lg p-4 space-y-3 transition-colors ${
                script.active
                  ? 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800'
                  : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 opacity-60'
              }`}
            >
              <div className="flex items-center gap-3">
                {/* Script name */}
                <input
                  type="text"
                  value={script.name}
                  onChange={(e) => updateScript(i, 'name', e.target.value)}
                  placeholder="Script name"
                  className="flex-1 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md
                    bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100
                    placeholder-gray-400 dark:placeholder-gray-500
                    focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />

                {/* Placement dropdown */}
                <select
                  value={script.placement}
                  onChange={(e) => updateScript(i, 'placement', e.target.value)}
                  className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md
                    bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100
                    focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {PLACEMENT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>

                {/* Active toggle */}
                <button
                  type="button"
                  onClick={() => updateScript(i, 'active', !script.active)}
                  className={`relative w-10 h-5 rounded-full transition-colors flex-shrink-0 ${
                    script.active ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
                  }`}
                  title={script.active ? 'Active' : 'Inactive'}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                      script.active ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>

                {/* Delete */}
                <button
                  type="button"
                  onClick={() => deleteScript(i)}
                  className="p-1.5 rounded-md text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors flex-shrink-0"
                  title="Delete script"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              {/* Code textarea */}
              <textarea
                value={script.code}
                onChange={(e) => updateScript(i, 'code', e.target.value)}
                placeholder="<script>&#10;  // Your tracking code here&#10;</script>"
                rows={4}
                className="w-full px-3 py-2 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded-md
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100
                  placeholder-gray-400 dark:placeholder-gray-500
                  focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
