import { useState } from 'react'
import { useParams } from 'react-router'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getPublicForm, submitPublicForm } from '@/api/forms'
import { CheckCircle, Loader2, AlertCircle } from 'lucide-react'

interface FormField {
  name: string
  type: string
  label: string
  required?: boolean
}

function parseFields(fieldsJson: string): FormField[] {
  try {
    const parsed = JSON.parse(fieldsJson)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

interface ThankYouConfig {
  message?: string
  url?: string
}

function parseThankYouConfig(json: string | undefined | null): ThankYouConfig {
  if (!json) return {}
  try {
    return JSON.parse(json)
  } catch {
    return {}
  }
}

export default function PublicFormPage() {
  const { formId } = useParams<{ formId: string }>()
  const [values, setValues] = useState<Record<string, string>>({})
  const [validationError, setValidationError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['public-form', formId],
    queryFn: () => getPublicForm(formId!),
    enabled: !!formId,
  })

  const submitMutation = useMutation({
    mutationFn: () => submitPublicForm(formId!, values),
    onSuccess: () => {
      const form = data?.data
      if (form?.thank_you_type === 'redirect') {
        const url = parseThankYouConfig(form.thank_you_config_json).url
        if (url) {
          window.location.href = url
          return
        }
      }
      setSubmitted(true)
    },
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
        <Loader2 className="h-8 w-8 text-blue-500 animate-spin" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-400 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
            Form not found
          </h1>
          <p className="text-gray-500 dark:text-gray-400">
            This link may have expired or is no longer valid.
          </p>
        </div>
      </div>
    )
  }

  const form = data.data
  const fields = parseFields(form.fields_json)
  const thankYou = parseThankYouConfig(form.thank_you_config_json)

  if (submitted) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white dark:bg-gray-900 rounded-xl shadow-sm border p-8 text-center">
          <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-4" />
          <p className="text-gray-900 dark:text-gray-100 font-medium">
            {thankYou.message || 'Thank you for your submission!'}
          </p>
        </div>
      </div>
    )
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const missing = fields.find((f) => f.required && !values[f.name]?.trim())
    if (missing) {
      setValidationError(`${missing.label || missing.name} is required`)
      return
    }
    setValidationError(null)
    submitMutation.mutate()
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center px-4 py-8">
      <div className="max-w-md w-full bg-white dark:bg-gray-900 rounded-xl shadow-sm border p-8">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-1">
          {form.name}
        </h1>
        {form.description && (
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">{form.description}</p>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {fields.map((field) => (
            <div key={field.name}>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {field.label || field.name}
                {field.required && <span className="text-red-500 ml-0.5">*</span>}
              </label>
              {field.type === 'textarea' ? (
                <textarea
                  value={values[field.name] || ''}
                  onChange={(e) => setValues((v) => ({ ...v, [field.name]: e.target.value }))}
                  rows={4}
                  className="w-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                />
              ) : (
                <input
                  type={['text', 'email', 'tel', 'number', 'date'].includes(field.type) ? field.type : 'text'}
                  value={values[field.name] || ''}
                  onChange={(e) => setValues((v) => ({ ...v, [field.name]: e.target.value }))}
                  className="w-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                />
              )}
            </div>
          ))}

          {validationError && (
            <p className="text-sm text-red-600">{validationError}</p>
          )}
          {submitMutation.isError && (
            <p className="text-sm text-red-600">Submission failed. Please try again.</p>
          )}

          <button
            type="submit"
            disabled={submitMutation.isPending}
            className="w-full px-6 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {submitMutation.isPending ? 'Submitting...' : 'Submit'}
          </button>
        </form>
      </div>
    </div>
  )
}
