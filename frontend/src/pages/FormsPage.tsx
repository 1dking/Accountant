import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  ClipboardList,
  Plus,
  Trash2,
  Pencil,
  Code2,
  Eye,
  EyeOff,
  ChevronDown,
  ChevronRight,
  Loader2,
  X,
  ExternalLink,
} from 'lucide-react'
import {
  listForms,
  createForm,
  getForm,
  updateForm,
  deleteForm,
  getSubmissions,
  type FormCreateData,
  type FormUpdateData,
} from '@/api/forms'
import type { FormListItem, FormDef, FormSubmission } from '@/types/models'

const THANK_YOU_TYPES = [
  { value: 'message', label: 'Show Message' },
  { value: 'redirect', label: 'Redirect URL' },
]

export default function FormsPage() {
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [fieldsJson, setFieldsJson] = useState(
    '[\n  { "name": "name", "type": "text", "label": "Full Name", "required": true },\n  { "name": "email", "type": "email", "label": "Email", "required": true },\n  { "name": "message", "type": "textarea", "label": "Message", "required": false }\n]'
  )
  const [thankYouType, setThankYouType] = useState('message')
  const [thankYouConfigJson, setThankYouConfigJson] = useState(
    '{ "message": "Thank you for your submission!" }'
  )
  const [styleJson, setStyleJson] = useState('{}')
  const [isActive, setIsActive] = useState(true)

  // Queries
  const { data: formsData, isLoading } = useQuery({
    queryKey: ['forms'],
    queryFn: () => listForms(),
  })
  const forms: FormListItem[] = formsData?.data ?? []

  const { data: submissionsData } = useQuery({
    queryKey: ['form-submissions', expandedId],
    queryFn: () => getSubmissions(expandedId!),
    enabled: !!expandedId,
  })
  const submissions: FormSubmission[] = submissionsData?.data ?? []

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: FormCreateData) => createForm(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['forms'] })
      toast.success('Form created')
      closeDialog()
    },
    onError: (err: any) => toast.error(err.message || 'Failed to create form'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: FormUpdateData }) =>
      updateForm(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['forms'] })
      toast.success('Form updated')
      closeDialog()
    },
    onError: (err: any) => toast.error(err.message || 'Failed to update form'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteForm(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['forms'] })
      toast.success('Form deleted')
    },
    onError: (err: any) => toast.error(err.message || 'Failed to delete form'),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      updateForm(id, { is_active: active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['forms'] })
    },
    onError: (err: any) => toast.error(err.message || 'Failed to toggle form'),
  })

  function closeDialog() {
    setDialogOpen(false)
    setEditingId(null)
    setName('')
    setDescription('')
    setFieldsJson(
      '[\n  { "name": "name", "type": "text", "label": "Full Name", "required": true },\n  { "name": "email", "type": "email", "label": "Email", "required": true },\n  { "name": "message", "type": "textarea", "label": "Message", "required": false }\n]'
    )
    setThankYouType('message')
    setThankYouConfigJson('{ "message": "Thank you for your submission!" }')
    setStyleJson('{}')
    setIsActive(true)
  }

  async function openEdit(id: string) {
    try {
      const res = await getForm(id)
      const form: FormDef = res.data
      setEditingId(id)
      setName(form.name)
      setDescription(form.description ?? '')
      setFieldsJson(form.fields_json)
      setThankYouType(form.thank_you_type)
      setThankYouConfigJson(form.thank_you_config_json ?? '{}')
      setStyleJson(form.style_json ?? '{}')
      setIsActive(form.is_active)
      setDialogOpen(true)
    } catch {
      toast.error('Failed to load form')
    }
  }

  function handleSave() {
    if (!name.trim()) {
      toast.error('Name is required')
      return
    }
    // Validate JSON
    try {
      JSON.parse(fieldsJson)
    } catch {
      toast.error('Fields JSON is not valid JSON')
      return
    }

    const payload = {
      name: name.trim(),
      description: description.trim() || undefined,
      fields_json: fieldsJson,
      thank_you_type: thankYouType,
      thank_you_config_json: thankYouConfigJson || undefined,
      style_json: styleJson || undefined,
      is_active: isActive,
    }
    if (editingId) {
      updateMutation.mutate({ id: editingId, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  function handleDelete(id: string) {
    if (confirm('Delete this form? This cannot be undone.')) {
      deleteMutation.mutate(id)
    }
  }

  function getPublicUrl(id: string) {
    return `${window.location.origin}/api/forms/public/${id}`
  }

  function copyPublicUrl(id: string) {
    navigator.clipboard.writeText(getPublicUrl(id))
    toast.success('Public URL copied to clipboard')
  }

  function copyEmbedCode(id: string) {
    const url = getPublicUrl(id)
    const code = `<iframe src="${url}" width="100%" height="600" frameborder="0" style="border: none; border-radius: 8px;"></iframe>`
    navigator.clipboard.writeText(code)
    toast.success('Embed code copied to clipboard')
  }

  function parseSubmissionData(jsonStr: string): Record<string, unknown> {
    try {
      return JSON.parse(jsonStr)
    } catch {
      return { raw: jsonStr }
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <ClipboardList className="h-6 w-6 text-emerald-500" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Forms</h1>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Form
        </button>
      </div>

      {/* Forms list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-gray-400">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : forms.length === 0 ? (
        <div className="text-center py-20 text-gray-400 dark:text-gray-500">
          <ClipboardList className="h-12 w-12 mx-auto mb-3 opacity-50" />
          <p className="text-lg font-medium">No forms yet</p>
          <p className="text-sm mt-1">
            Create a form to collect data from clients and contacts.
          </p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400 w-8" />
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Name
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Status
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Submissions
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Last Submission
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Created
                </th>
                <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {forms.map((form) => {
                const isExpanded = expandedId === form.id
                return (
                  <FormRow
                    key={form.id}
                    form={form}
                    isExpanded={isExpanded}
                    submissions={isExpanded ? submissions : []}
                    onToggleExpand={() =>
                      setExpandedId(isExpanded ? null : form.id)
                    }
                    onToggleActive={() =>
                      toggleMutation.mutate({
                        id: form.id,
                        active: !form.is_active,
                      })
                    }
                    onEdit={() => openEdit(form.id)}
                    onDelete={() => handleDelete(form.id)}
                    onCopyUrl={() => copyPublicUrl(form.id)}
                    onCopyEmbed={() => copyEmbedCode(form.id)}
                    parseSubmissionData={parseSubmissionData}
                  />
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Dialog */}
      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-10 bg-black/40">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-2xl max-h-[85vh] overflow-y-auto">
            {/* Dialog Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {editingId ? 'Edit Form' : 'New Form'}
              </h2>
              <button
                onClick={closeDialog}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="px-6 py-4 space-y-5">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Form Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Contact Us"
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Optional description..."
                  rows={2}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100 resize-none"
                />
              </div>

              {/* Active toggle */}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setIsActive(!isActive)}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                    isActive ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
                  }`}
                >
                  <span
                    className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                      isActive ? 'translate-x-4.5' : 'translate-x-0.5'
                    }`}
                  />
                </button>
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {isActive ? 'Active' : 'Inactive'}
                </span>
              </div>

              {/* Fields JSON */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Fields (JSON)
                </label>
                <p className="text-xs text-gray-400 dark:text-gray-500 mb-1">
                  Array of objects with name, type (text/email/phone/textarea/select/checkbox/number), label, required, options (for select)
                </p>
                <textarea
                  value={fieldsJson}
                  onChange={(e) => setFieldsJson(e.target.value)}
                  rows={8}
                  className="w-full px-3 py-2 text-sm font-mono border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100 resize-y"
                />
              </div>

              {/* Thank you type */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Thank You Action
                  </label>
                  <select
                    value={thankYouType}
                    onChange={(e) => setThankYouType(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                  >
                    {THANK_YOU_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Config (JSON)
                  </label>
                  <input
                    type="text"
                    value={thankYouConfigJson}
                    onChange={(e) => setThankYouConfigJson(e.target.value)}
                    placeholder='{ "message": "Thanks!" }'
                    className="w-full px-3 py-2 text-sm font-mono border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                  />
                </div>
              </div>

              {/* Style JSON */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Style Overrides (JSON, optional)
                </label>
                <textarea
                  value={styleJson}
                  onChange={(e) => setStyleJson(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 text-sm font-mono border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100 resize-none"
                />
              </div>
            </div>

            {/* Dialog Footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 dark:border-gray-700">
              <button
                onClick={closeDialog}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {isSaving && <Loader2 className="h-4 w-4 animate-spin" />}
                {editingId ? 'Save Changes' : 'Create Form'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

interface FormRowProps {
  form: FormListItem
  isExpanded: boolean
  submissions: FormSubmission[]
  onToggleExpand: () => void
  onToggleActive: () => void
  onEdit: () => void
  onDelete: () => void
  onCopyUrl: () => void
  onCopyEmbed: () => void
  parseSubmissionData: (json: string) => Record<string, unknown>
}

function FormRow({
  form,
  isExpanded,
  submissions,
  onToggleExpand,
  onToggleActive,
  onEdit,
  onDelete,
  onCopyUrl,
  onCopyEmbed,
  parseSubmissionData,
}: FormRowProps) {
  return (
    <>
      <tr className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50/50 dark:hover:bg-gray-800/30">
        <td className="px-4 py-3">
          <button
            onClick={onToggleExpand}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
        </td>
        <td className="px-4 py-3">
          <button
            onClick={onToggleExpand}
            className="text-sm font-medium text-gray-900 dark:text-gray-100 hover:text-blue-600 dark:hover:text-blue-400"
          >
            {form.name}
          </button>
        </td>
        <td className="px-4 py-3 text-center">
          <button onClick={onToggleActive}>
            {form.is_active ? (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400">
                <Eye className="h-3.5 w-3.5" /> Active
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-gray-400 dark:text-gray-500">
                <EyeOff className="h-3.5 w-3.5" /> Inactive
              </span>
            )}
          </button>
        </td>
        <td className="px-4 py-3 text-center text-sm text-gray-600 dark:text-gray-400">
          {form.submission_count}
        </td>
        <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
          {form.last_submission_at
            ? new Date(form.last_submission_at).toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })
            : '--'}
        </td>
        <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
          {new Date(form.created_at).toLocaleDateString()}
        </td>
        <td className="px-4 py-3 text-right">
          <div className="flex items-center justify-end gap-1">
            <button
              onClick={onCopyUrl}
              className="p-1.5 rounded-lg text-gray-400 hover:text-emerald-600 dark:hover:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/20"
              title="Copy public URL"
            >
              <ExternalLink className="h-4 w-4" />
            </button>
            <button
              onClick={onCopyEmbed}
              className="p-1.5 rounded-lg text-gray-400 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/20"
              title="Copy embed code"
            >
              <Code2 className="h-4 w-4" />
            </button>
            <button
              onClick={onEdit}
              className="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20"
              title="Edit"
            >
              <Pencil className="h-4 w-4" />
            </button>
            <button
              onClick={onDelete}
              className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
              title="Delete"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </td>
      </tr>

      {/* Submissions */}
      {isExpanded && (
        <tr>
          <td colSpan={7} className="px-4 py-3 bg-gray-50 dark:bg-gray-800/30">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
              Submissions ({form.submission_count})
            </p>
            {submissions.length === 0 ? (
              <p className="text-xs text-gray-400 dark:text-gray-500">
                No submissions yet.
              </p>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {submissions.map((sub) => {
                  const data = parseSubmissionData(sub.data_json)
                  return (
                    <div
                      key={sub.id}
                      className="p-3 rounded-lg bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-700"
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs text-gray-400 dark:text-gray-500">
                          {new Date(sub.submitted_at).toLocaleString()}
                        </span>
                        {sub.contact_id && (
                          <span className="text-xs text-blue-500">
                            Contact: {sub.contact_id.slice(0, 8)}...
                          </span>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                        {Object.entries(data).map(([key, val]) => (
                          <div key={key} className="text-xs">
                            <span className="font-medium text-gray-600 dark:text-gray-400">
                              {key}:{' '}
                            </span>
                            <span className="text-gray-800 dark:text-gray-200">
                              {String(val)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}
