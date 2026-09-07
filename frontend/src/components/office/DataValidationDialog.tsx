import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ValidationRule } from '@/lib/spreadsheet/types'
import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'

interface DataValidationDialogProps {
  open: boolean
  onClose: () => void
  currentValidation: ValidationRule | null
  onSave: (rule: ValidationRule | null) => void
}

type ValidationType = ValidationRule['type']

const VALIDATION_TYPES: { value: ValidationType; label: string; description: string }[] = [
  { value: 'number', label: i18n.t('ui:DataValidationDialog.number'), description: i18n.t('ui:DataValidationDialog.allowOnlyNumbersWithinA') },
  { value: 'list', label: i18n.t('ui:DataValidationDialog.list'), description: i18n.t('ui:DataValidationDialog.allowOnlyValuesFromA') },
  { value: 'text_length', label: i18n.t('ui:DataValidationDialog.textLength'), description: i18n.t('ui:DataValidationDialog.limitTextToASpecific') },
  { value: 'date', label: i18n.t('ui:DataValidationDialog.date'), description: i18n.t('ui:DataValidationDialog.allowOnlyDatesWithinA') },
  { value: 'custom', label: i18n.t('ui:DataValidationDialog.customFormula'), description: i18n.t('ui:DataValidationDialog.useACustomFormulaFor') },
]

interface EditorState {
  type: ValidationType
  min: string
  max: string
  listValues: string
  customFormula: string
  showWarning: boolean
  warningMessage: string
}

function validationToEditorState(rule: ValidationRule | null): EditorState {
  if (!rule) {
    return {
      type: 'number',
      min: '',
      max: '',
      listValues: '',
      customFormula: '',
      showWarning: true,
      warningMessage: '',
    }
  }

  return {
    type: rule.type,
    min: rule.min != null ? String(rule.min) : '',
    max: rule.max != null ? String(rule.max) : '',
    listValues: rule.listValues?.join(', ') ?? '',
    customFormula: rule.customFormula ?? '',
    showWarning: rule.showWarning ?? true,
    warningMessage: rule.warningMessage ?? '',
  }
}

function editorStateToRule(state: EditorState): ValidationRule {
  const rule: ValidationRule = {
    type: state.type,
    showWarning: state.showWarning,
    warningMessage: state.warningMessage || undefined,
  }

  switch (state.type) {
    case 'number': {
      if (state.min !== '') rule.min = parseFloat(state.min)
      if (state.max !== '') rule.max = parseFloat(state.max)
      break
    }
    case 'list': {
      rule.listValues = state.listValues
        .split(',')
        .map((v) => v.trim())
        .filter((v) => v.length > 0)
      break
    }
    case 'text_length': {
      if (state.min !== '') rule.min = parseInt(state.min, 10)
      if (state.max !== '') rule.max = parseInt(state.max, 10)
      break
    }
    case 'date': {
      // Store date constraints as unix timestamps for comparison
      if (state.min !== '') rule.min = new Date(state.min).getTime()
      if (state.max !== '') rule.max = new Date(state.max).getTime()
      break
    }
    case 'custom': {
      rule.customFormula = state.customFormula || undefined
      break
    }
  }

  return rule
}

export default function DataValidationDialog({
  open,
  onClose,
  currentValidation,
  onSave,
}: DataValidationDialogProps) {
  const { t } = useTranslation('ui')
  const [editor, setEditor] = useState<EditorState>(validationToEditorState(currentValidation))
  const [errors, setErrors] = useState<Record<string, string>>({})

  // Reset when dialog opens or currentValidation changes
  useEffect(() => {
    if (open) {
      setEditor(validationToEditorState(currentValidation))
      setErrors({})
    }
  }, [open, currentValidation])

  if (!open) return null

  function validate(): boolean {
    const newErrors: Record<string, string> = {}

    switch (editor.type) {
      case 'number': {
        if (editor.min !== '' && isNaN(parseFloat(editor.min))) {
          newErrors.min = 'Must be a valid number'
        }
        if (editor.max !== '' && isNaN(parseFloat(editor.max))) {
          newErrors.max = 'Must be a valid number'
        }
        if (
          editor.min !== '' &&
          editor.max !== '' &&
          !isNaN(parseFloat(editor.min)) &&
          !isNaN(parseFloat(editor.max)) &&
          parseFloat(editor.min) > parseFloat(editor.max)
        ) {
          newErrors.min = 'Min must be less than or equal to max'
        }
        break
      }
      case 'list': {
        const values = editor.listValues
          .split(',')
          .map((v) => v.trim())
          .filter((v) => v.length > 0)
        if (values.length === 0) {
          newErrors.listValues = 'Enter at least one value'
        }
        break
      }
      case 'text_length': {
        if (editor.min !== '' && (isNaN(parseInt(editor.min, 10)) || parseInt(editor.min, 10) < 0)) {
          newErrors.min = 'Must be a non-negative integer'
        }
        if (editor.max !== '' && (isNaN(parseInt(editor.max, 10)) || parseInt(editor.max, 10) < 0)) {
          newErrors.max = 'Must be a non-negative integer'
        }
        if (
          editor.min !== '' &&
          editor.max !== '' &&
          !isNaN(parseInt(editor.min, 10)) &&
          !isNaN(parseInt(editor.max, 10)) &&
          parseInt(editor.min, 10) > parseInt(editor.max, 10)
        ) {
          newErrors.min = 'Min must be less than or equal to max'
        }
        break
      }
      case 'date': {
        if (editor.min !== '' && isNaN(new Date(editor.min).getTime())) {
          newErrors.min = 'Invalid date'
        }
        if (editor.max !== '' && isNaN(new Date(editor.max).getTime())) {
          newErrors.max = 'Invalid date'
        }
        if (
          editor.min !== '' &&
          editor.max !== '' &&
          !isNaN(new Date(editor.min).getTime()) &&
          !isNaN(new Date(editor.max).getTime()) &&
          new Date(editor.min).getTime() > new Date(editor.max).getTime()
        ) {
          newErrors.min = 'Start date must be before end date'
        }
        break
      }
      case 'custom': {
        if (!editor.customFormula.trim()) {
          newErrors.customFormula = 'Enter a formula'
        }
        break
      }
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  function handleSave() {
    if (!validate()) return
    const rule = editorStateToRule(editor)
    onSave(rule)
    onClose()
  }

  function handleRemoveValidation() {
    onSave(null)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-full max-w-md mx-4 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
           {t('ui:DataValidationDialog.dataValidation')}
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-gray-400 dark:text-gray-500 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 dark:hover:text-gray-300 dark:hover:bg-gray-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="px-5 py-4 space-y-4">
          {/* Validation type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
             {t('ui:DataValidationDialog.validationType')}
            </label>
            <select
              value={editor.type}
              onChange={(e) => {
                setEditor((prev) => ({ ...prev, type: e.target.value as ValidationType }))
                setErrors({})
              }}
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {VALIDATION_TYPES.map((vt) => (
                <option key={vt.value} value={vt.value}>
                  {vt.label}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {VALIDATION_TYPES.find((vt) => vt.value === editor.type)?.description}
            </p>
          </div>

          {/* Type-specific inputs */}
          {editor.type === 'number' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                 {t('ui:DataValidationDialog.minimum')}
                </label>
                <input
                  type="number"
                  value={editor.min}
                  onChange={(e) => {
                    setEditor((prev) => ({ ...prev, min: e.target.value }))
                    setErrors((prev) => ({ ...prev, min: '' }))
                  }}
                  placeholder={t('ui:DataValidationDialog.noLimit')}
                  className={cn(
                    'w-full px-3 py-1.5 text-sm border rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500',
                    errors.min
                      ? 'border-red-400 dark:border-red-600'
                      : 'border-gray-300 dark:border-gray-600'
                  )}
                />
                {errors.min && (
                  <p className="text-xs text-red-500 dark:text-red-400 mt-0.5">{errors.min}</p>
                )}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                 {t('ui:DataValidationDialog.maximum')}
                </label>
                <input
                  type="number"
                  value={editor.max}
                  onChange={(e) => {
                    setEditor((prev) => ({ ...prev, max: e.target.value }))
                    setErrors((prev) => ({ ...prev, max: '' }))
                  }}
                  placeholder={t('ui:DataValidationDialog.noLimit')}
                  className={cn(
                    'w-full px-3 py-1.5 text-sm border rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500',
                    errors.max
                      ? 'border-red-400 dark:border-red-600'
                      : 'border-gray-300 dark:border-gray-600'
                  )}
                />
                {errors.max && (
                  <p className="text-xs text-red-500 dark:text-red-400 mt-0.5">{errors.max}</p>
                )}
              </div>
            </div>
          )}

          {editor.type === 'list' && (
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
               {t('ui:DataValidationDialog.allowedValuesCommaSeparated')}
              </label>
              <textarea
                value={editor.listValues}
                onChange={(e) => {
                  setEditor((prev) => ({ ...prev, listValues: e.target.value }))
                  setErrors((prev) => ({ ...prev, listValues: '' }))
                }}
                placeholder={t('ui:DataValidationDialog.option1Option2Option')}
                rows={3}
                className={cn(
                  'w-full px-3 py-1.5 text-sm border rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none',
                  errors.listValues
                    ? 'border-red-400 dark:border-red-600'
                    : 'border-gray-300 dark:border-gray-600'
                )}
              />
              {errors.listValues && (
                <p className="text-xs text-red-500 dark:text-red-400 mt-0.5">{errors.listValues}</p>
              )}
              {editor.listValues && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {editor.listValues
                    .split(',')
                    .map((v) => v.trim())
                    .filter((v) => v.length > 0).length}{' '}
                 {t('ui:DataValidationDialog.valueSDefined')}
                </p>
              )}
            </div>
          )}

          {editor.type === 'text_length' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                 {t('ui:DataValidationDialog.minLength')}
                </label>
                <input
                  type="number"
                  min="0"
                  value={editor.min}
                  onChange={(e) => {
                    setEditor((prev) => ({ ...prev, min: e.target.value }))
                    setErrors((prev) => ({ ...prev, min: '' }))
                  }}
                  placeholder={t('ui:DataValidationDialog.noLimit')}
                  className={cn(
                    'w-full px-3 py-1.5 text-sm border rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500',
                    errors.min
                      ? 'border-red-400 dark:border-red-600'
                      : 'border-gray-300 dark:border-gray-600'
                  )}
                />
                {errors.min && (
                  <p className="text-xs text-red-500 dark:text-red-400 mt-0.5">{errors.min}</p>
                )}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                 {t('ui:DataValidationDialog.maxLength')}
                </label>
                <input
                  type="number"
                  min="0"
                  value={editor.max}
                  onChange={(e) => {
                    setEditor((prev) => ({ ...prev, max: e.target.value }))
                    setErrors((prev) => ({ ...prev, max: '' }))
                  }}
                  placeholder={t('ui:DataValidationDialog.noLimit')}
                  className={cn(
                    'w-full px-3 py-1.5 text-sm border rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500',
                    errors.max
                      ? 'border-red-400 dark:border-red-600'
                      : 'border-gray-300 dark:border-gray-600'
                  )}
                />
                {errors.max && (
                  <p className="text-xs text-red-500 dark:text-red-400 mt-0.5">{errors.max}</p>
                )}
              </div>
            </div>
          )}

          {editor.type === 'date' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                 {t('ui:DataValidationDialog.earliestDate')}
                </label>
                <input
                  type="date"
                  value={editor.min}
                  onChange={(e) => {
                    setEditor((prev) => ({ ...prev, min: e.target.value }))
                    setErrors((prev) => ({ ...prev, min: '' }))
                  }}
                  className={cn(
                    'w-full px-3 py-1.5 text-sm border rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500',
                    errors.min
                      ? 'border-red-400 dark:border-red-600'
                      : 'border-gray-300 dark:border-gray-600'
                  )}
                />
                {errors.min && (
                  <p className="text-xs text-red-500 dark:text-red-400 mt-0.5">{errors.min}</p>
                )}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                 {t('ui:DataValidationDialog.latestDate')}
                </label>
                <input
                  type="date"
                  value={editor.max}
                  onChange={(e) => {
                    setEditor((prev) => ({ ...prev, max: e.target.value }))
                    setErrors((prev) => ({ ...prev, max: '' }))
                  }}
                  className={cn(
                    'w-full px-3 py-1.5 text-sm border rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500',
                    errors.max
                      ? 'border-red-400 dark:border-red-600'
                      : 'border-gray-300 dark:border-gray-600'
                  )}
                />
                {errors.max && (
                  <p className="text-xs text-red-500 dark:text-red-400 mt-0.5">{errors.max}</p>
                )}
              </div>
            </div>
          )}

          {editor.type === 'custom' && (
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
               {t('ui:DataValidationDialog.customFormula_2')}
              </label>
              <input
                type="text"
                value={editor.customFormula}
                onChange={(e) => {
                  setEditor((prev) => ({ ...prev, customFormula: e.target.value }))
                  setErrors((prev) => ({ ...prev, customFormula: '' }))
                }}
                placeholder={t('ui:DataValidationDialog.andA10A1100')}
                className={cn(
                  'w-full px-3 py-1.5 text-sm font-mono border rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500',
                  errors.customFormula
                    ? 'border-red-400 dark:border-red-600'
                    : 'border-gray-300 dark:border-gray-600'
                )}
              />
              {errors.customFormula && (
                <p className="text-xs text-red-500 dark:text-red-400 mt-0.5">
                  {errors.customFormula}
                </p>
              )}
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
               {t('ui:DataValidationDialog.formulaShouldReturnTrueFor')}
              </p>
            </div>
          )}

          {/* Warning options */}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-4 space-y-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={editor.showWarning}
                onChange={(e) =>
                  setEditor((prev) => ({ ...prev, showWarning: e.target.checked }))
                }
                className="rounded border-gray-300 dark:border-gray-600 text-blue-600 dark:text-blue-400 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">
               {t('ui:DataValidationDialog.showWarningOnInvalidInput')}
              </span>
            </label>

            {editor.showWarning && (
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                 {t('ui:DataValidationDialog.warningMessage')}
                </label>
                <input
                  type="text"
                  value={editor.warningMessage}
                  onChange={(e) =>
                    setEditor((prev) => ({ ...prev, warningMessage: e.target.value }))
                  }
                  placeholder={t('ui:DataValidationDialog.invalidInputPleaseEnterA')}
                  className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-gray-200 dark:border-gray-700 flex items-center gap-2">
          {currentValidation && (
            <button
              onClick={handleRemoveValidation}
              className="px-3 py-2 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md"
            >
             {t('ui:DataValidationDialog.removeValidation')}
            </button>
          )}
          <div className="flex-1" />
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
          >
           {t('ui:DataValidationDialog.cancel')}
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
          >
           {t('ui:DataValidationDialog.save')}
          </button>
        </div>
      </div>
    </div>
  )
}
