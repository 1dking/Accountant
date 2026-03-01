import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, X, GripVertical, Zap } from 'lucide-react'
import {
  listCategorizationRules,
  createCategorizationRule,
  updateCategorizationRule,
  deleteCategorizationRule,
  applyCategorizationRules,
} from '@/api/integrations'
import { listCategories } from '@/api/accounting'
import type {
  CategorizationRule,
  CategorizationRuleCreate,
  CategorizationRuleUpdate,
  CategorizationMatchField,
  CategorizationMatchType,
  ExpenseCategory,
} from '@/types/models'

const MATCH_FIELD_LABELS: Record<CategorizationMatchField, string> = {
  name: 'Transaction Name',
  merchant_name: 'Merchant Name',
  category: 'Plaid Category',
}

const MATCH_TYPE_LABELS: Record<CategorizationMatchType, string> = {
  contains: 'Contains',
  exact: 'Exact Match',
  starts_with: 'Starts With',
  regex: 'Regex',
}

interface RuleFormData {
  name: string
  match_field: CategorizationMatchField
  match_type: CategorizationMatchType
  match_value: string
  assign_category_id: string
  priority: number
  is_active: boolean
}

const EMPTY_FORM: RuleFormData = {
  name: '',
  match_field: 'name',
  match_type: 'contains',
  match_value: '',
  assign_category_id: '',
  priority: 0,
  is_active: true,
}

export default function CategorizationRules() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<RuleFormData>({ ...EMPTY_FORM })
  const [msg, setMsg] = useState('')

  const { data: rulesData, isLoading } = useQuery({
    queryKey: ['categorization-rules'],
    queryFn: listCategorizationRules,
  })

  const { data: categoriesData } = useQuery({
    queryKey: ['expense-categories'],
    queryFn: listCategories,
  })

  const rules: CategorizationRule[] = rulesData?.data ?? []
  const categories: ExpenseCategory[] = categoriesData?.data ?? []

  const createMutation = useMutation({
    mutationFn: (data: CategorizationRuleCreate) => createCategorizationRule(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categorization-rules'] })
      resetForm()
      flash('Rule created successfully')
    },
    onError: () => flash('Failed to create rule'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: CategorizationRuleUpdate }) =>
      updateCategorizationRule(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categorization-rules'] })
      resetForm()
      flash('Rule updated successfully')
    },
    onError: () => flash('Failed to update rule'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteCategorizationRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categorization-rules'] })
      flash('Rule deleted')
    },
    onError: () => flash('Failed to delete rule'),
  })

  const applyMutation = useMutation({
    mutationFn: applyCategorizationRules,
    onSuccess: (resp) => {
      queryClient.invalidateQueries({ queryKey: ['plaid-transactions'] })
      flash(resp.data?.detail ?? 'Rules applied')
    },
    onError: () => flash('Failed to apply rules'),
  })

  function flash(message: string) {
    setMsg(message)
    setTimeout(() => setMsg(''), 3000)
  }

  function resetForm() {
    setForm({ ...EMPTY_FORM })
    setEditingId(null)
    setShowForm(false)
  }

  function startEdit(rule: CategorizationRule) {
    setForm({
      name: rule.name,
      match_field: rule.match_field,
      match_type: rule.match_type,
      match_value: rule.match_value,
      assign_category_id: rule.assign_category_id,
      priority: rule.priority,
      is_active: rule.is_active,
    })
    setEditingId(rule.id)
    setShowForm(true)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.name || !form.match_value || !form.assign_category_id) return

    if (editingId) {
      updateMutation.mutate({ id: editingId, data: form })
    } else {
      createMutation.mutate(form)
    }
  }

  function getCategoryName(categoryId: string): string {
    const cat = categories.find((c) => c.id === categoryId)
    return cat?.name ?? 'Unknown'
  }

  const isSaving = createMutation.isPending || updateMutation.isPending

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">Auto-Categorization Rules</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Automatically categorize bank transactions based on matching rules.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => applyMutation.mutate()}
            disabled={applyMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-2 text-sm border border-blue-200 text-blue-600 dark:text-blue-400 rounded-lg hover:bg-blue-50 disabled:opacity-50"
          >
            <Zap className={`w-4 h-4 ${applyMutation.isPending ? 'animate-pulse' : ''}`} />
            {applyMutation.isPending ? 'Applying...' : 'Apply Rules'}
          </button>
          {!showForm && (
            <button
              onClick={() => { resetForm(); setShowForm(true) }}
              className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <Plus className="w-4 h-4" />
              Add Rule
            </button>
          )}
        </div>
      </div>

      {msg && (
        <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">
          {msg}
        </div>
      )}

      {/* Create / Edit Form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {editingId ? 'Edit Rule' : 'New Rule'}
            </h3>
            <button type="button" onClick={resetForm} className="text-gray-400 dark:text-gray-500 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Rule Name</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. AWS Cloud Services"
                required
                className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Assign Category</label>
              <select
                value={form.assign_category_id}
                onChange={(e) => setForm({ ...form, assign_category_id: e.target.value })}
                required
                className="w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select category...</option>
                {categories.map((cat) => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Match Field</label>
              <select
                value={form.match_field}
                onChange={(e) => setForm({ ...form, match_field: e.target.value as CategorizationMatchField })}
                className="w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {Object.entries(MATCH_FIELD_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Match Type</label>
              <select
                value={form.match_type}
                onChange={(e) => setForm({ ...form, match_type: e.target.value as CategorizationMatchType })}
                className="w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {Object.entries(MATCH_TYPE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Match Value</label>
              <input
                type="text"
                value={form.match_value}
                onChange={(e) => setForm({ ...form, match_value: e.target.value })}
                placeholder={form.match_type === 'regex' ? 'e.g. AWS|Amazon Web' : 'e.g. AWS'}
                required
                className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Priority</label>
              <input
                type="number"
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) || 0 })}
                min={0}
                className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Higher priority rules match first</p>
            </div>
            <div className="flex items-center pt-6">
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  className="rounded border-gray-300 dark:border-gray-600 text-blue-600 dark:text-blue-400 focus:ring-blue-500"
                />
                Active
              </label>
            </div>
          </div>

          <div className="flex items-center gap-2 pt-2">
            <button
              type="submit"
              disabled={isSaving}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {isSaving ? 'Saving...' : editingId ? 'Update Rule' : 'Create Rule'}
            </button>
            <button
              type="button"
              onClick={resetForm}
              className="px-4 py-2 text-sm border rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Rules Table */}
      {isLoading ? (
        <p className="text-gray-400 dark:text-gray-500 py-8 text-center text-sm">Loading rules...</p>
      ) : rules.length > 0 ? (
        <div className="bg-white dark:bg-gray-900 border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 dark:bg-gray-950">
                <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium w-8"></th>
                <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Name</th>
                <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Match</th>
                <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Category</th>
                <th className="text-center px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Priority</th>
                <th className="text-center px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Status</th>
                <th className="text-right px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id} className="border-b hover:bg-gray-50 dark:hover:bg-gray-800">
                  <td className="px-4 py-3 text-gray-300">
                    <GripVertical className="w-4 h-4" />
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{rule.name}</td>
                  <td className="px-4 py-3">
                    <div className="text-gray-600 dark:text-gray-400">
                      <span className="text-xs bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded mr-1">
                        {MATCH_FIELD_LABELS[rule.match_field]}
                      </span>
                      <span className="text-xs text-gray-400 dark:text-gray-500 mr-1">
                        {MATCH_TYPE_LABELS[rule.match_type]}
                      </span>
                      <span className="text-xs font-mono bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded">
                        {rule.match_value}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{getCategoryName(rule.assign_category_id)}</td>
                  <td className="px-4 py-3 text-center text-gray-500 dark:text-gray-400">{rule.priority}</td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        rule.is_active
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 dark:bg-gray-800 text-gray-500'
                      }`}
                    >
                      {rule.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center gap-1 justify-end">
                      <button
                        onClick={() => startEdit(rule)}
                        className="p-1 text-gray-400 dark:text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded"
                        title="Edit"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`Delete rule "${rule.name}"?`)) {
                            deleteMutation.mutate(rule.id)
                          }
                        }}
                        className="p-1 text-gray-400 dark:text-gray-500 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-12 bg-white dark:bg-gray-900 border rounded-lg">
          <Zap className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400 text-sm">No categorization rules yet.</p>
          <p className="text-gray-400 dark:text-gray-500 text-xs mt-1">
            Create a rule to automatically categorize bank transactions.
          </p>
        </div>
      )}

      <div className="bg-gray-50 dark:bg-gray-950 border rounded-lg p-4 text-sm text-gray-600 dark:text-gray-400">
        <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">How rules work</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500 dark:text-gray-400">
          <li>Rules match against transaction fields (name, merchant, or Plaid category)</li>
          <li>Higher priority rules are checked first</li>
          <li>When a rule matches, the transaction is automatically categorized as an expense</li>
          <li>Rules run automatically when new transactions are synced from Plaid</li>
          <li>Use "Apply Rules" to re-process existing uncategorized transactions</li>
        </ul>
      </div>
    </div>
  )
}
