/**
 * Left column of the contact detail page: identity card, address,
 * lead info, settings, tags, dates, tax id, notes.
 *
 * Pure-presentational — receives the contact + tag state + mutation
 * callbacks via props. No data fetching here. Page owns all queries.
 */
import { useEffect, useRef, useState } from 'react'
import {
  Bell, BellOff, Briefcase, Building2, Calendar, Mail,
  MapPin, Pencil, Phone, Tag, User, X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { getInitials, formatDate } from './contactDetailUtils'
import { useTranslation } from 'react-i18next'

const LEAD_SOURCES = [
  'Website', 'Referral', 'Social Media', 'Cold Outreach', 'Ads', 'Event', 'Other',
]

// ---------------------------------------------------------------------------
// Inline editable field — click to edit, blur or Enter to commit.
// Local to LeftPanel because no other panel uses inline-edit semantics.
// ---------------------------------------------------------------------------

function InlineField({
  label,
  value,
  onSave,
  type = 'text',
  placeholder,
  icon: Icon,
}: {
  label: string
  value: string
  onSave: (v: string) => void
  type?: string
  placeholder?: string
  icon?: React.ElementType
}) {
  const { t } = useTranslation('ui')
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { setDraft(value) }, [value])
  useEffect(() => { if (editing) inputRef.current?.focus() }, [editing])

  const commit = () => {
    setEditing(false)
    if (draft !== value) onSave(draft)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') commit()
    if (e.key === 'Escape') { setDraft(value); setEditing(false) }
  }

  return (
    <div className="group">
      <label className="block text-[10px] uppercase tracking-wider font-semibold text-gray-400 dark:text-gray-500 mb-0.5">
        {label}
      </label>
      {editing ? (
        <input
          ref={inputRef}
          type={type}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full px-2 py-1 text-sm border border-blue-400 dark:border-blue-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      ) : (
        <div
          onClick={() => setEditing(true)}
          className="flex items-center gap-1.5 px-2 py-1 -mx-2 rounded cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors min-h-[28px]"
        >
          {Icon && <Icon className="h-3.5 w-3.5 text-gray-400 dark:text-gray-500 shrink-0" />}
          <span className={cn('text-sm', value ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400 dark:text-gray-500 italic')}>
            {value || placeholder || t('ui:ContactDetailLeftPanel.clickToAdd')}
          </span>
          <Pencil className="h-3 w-3 text-gray-300 dark:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity ml-auto shrink-0" />
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
  contact: any
  tags: any[]
  allTags: string[]
  tagInput: string
  setTagInput: (v: string) => void
  showTagSuggestions: boolean
  setShowTagSuggestions: (v: boolean) => void
  tagSuggestions: string[]
  activities: any[]
  saveField: (key: string, value: any) => void
  onAddTag: (tag: string) => void
  onRemoveTag: (tag: string) => void
}

// ---------------------------------------------------------------------------
// NotesEditor — on-blur auto-save textarea. Replaces the legacy
// window.prompt() UX. Local draft state lets the user type freely; we
// only persist when focus leaves the textarea AND the value actually
// changed. Esc reverts the draft.
// ---------------------------------------------------------------------------

function NotesEditor({
  value,
  onSave,
}: {
  value: string
  onSave: (v: string) => void
}) {
  const { t } = useTranslation('ui')
  const [draft, setDraft] = useState(value)

  useEffect(() => { setDraft(value) }, [value])

  const commit = () => {
    if (draft !== value) onSave(draft)
  }

  return (
    <div>
      <label className="block text-[10px] uppercase tracking-wider font-semibold text-gray-400 dark:text-gray-500 mb-0.5">
       {t('ui:ContactDetailLeftPanel.notes')}
      </label>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            setDraft(value)
            ;(e.target as HTMLTextAreaElement).blur()
          }
        }}
        rows={3}
        placeholder={t('ui:ContactDetailLeftPanel.notesAboutThisContact')}
        className="w-full px-2 py-1.5 text-sm rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ContactDetailLeftPanel({
  contact,
  tags,
  allTags: _allTags,
  tagInput,
  setTagInput,
  showTagSuggestions,
  setShowTagSuggestions,
  tagSuggestions,
  activities,
  saveField,
  onAddTag,
  onRemoveTag,
}: Props) {
  const { t } = useTranslation('ui')
  const initials = getInitials(contact.contact_name, contact.company_name)

  return (
    <div className="w-full md:w-80 shrink-0 overflow-y-auto border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-950 p-5 space-y-6">

      {/* Contact Info */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-3">{t('ui:ContactDetailLeftPanel.contactInfo')}</h3>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-14 h-14 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center text-blue-700 dark:text-blue-300 text-lg font-bold shrink-0">
            {initials}
          </div>
          <div className="min-w-0">
            <InlineField
              label={t('ui:ContactDetailLeftPanel.fullName')}
              value={contact.contact_name || ''}
              onSave={(v) => saveField('contact_name', v)}
              placeholder={t('ui:ContactDetailLeftPanel.addName')}
              icon={User}
            />
          </div>
        </div>

        <div className="space-y-2">
          <InlineField
            label={t('ui:ContactDetailLeftPanel.email')}
            value={contact.email || ''}
            onSave={(v) => saveField('email', v)}
            type="email"
            placeholder={t('ui:ContactDetailLeftPanel.addEmail')}
            icon={Mail}
          />
          <InlineField
            label={t('ui:ContactDetailLeftPanel.phone')}
            value={contact.phone || ''}
            onSave={(v) => saveField('phone', v)}
            type="tel"
            placeholder={t('ui:ContactDetailLeftPanel.addPhone')}
            icon={Phone}
          />
          <InlineField
            label={t('ui:ContactDetailLeftPanel.company')}
            value={contact.company_name}
            onSave={(v) => saveField('company_name', v || contact.company_name)}
            placeholder={t('ui:ContactDetailLeftPanel.companyName')}
            icon={Building2}
          />
          <InlineField
            label={t('ui:ContactDetailLeftPanel.jobTitle')}
            value={contact.job_title || ''}
            onSave={(v) => saveField('job_title', v)}
            placeholder={t('ui:ContactDetailLeftPanel.addJobTitle')}
            icon={Briefcase}
          />
        </div>
      </div>

      <hr className="border-gray-200 dark:border-gray-700" />

      {/* Address */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-3 flex items-center gap-1.5">
          <MapPin className="h-3.5 w-3.5" /> {t('ui:ContactDetailLeftPanel.address')}
        </h3>
        <div className="space-y-2">
          <InlineField label={t('ui:ContactDetailLeftPanel.street')} value={contact.address_line1 || ''} onSave={(v) => saveField('address_line1', v)} placeholder={t('ui:ContactDetailLeftPanel.streetAddress')} />
          <InlineField label={t('ui:ContactDetailLeftPanel.aptSuite')} value={contact.address_line2 || ''} onSave={(v) => saveField('address_line2', v)} placeholder={t('ui:ContactDetailLeftPanel.aptSuiteUnit')} />
          <InlineField label={t('ui:ContactDetailLeftPanel.city')} value={contact.city || ''} onSave={(v) => saveField('city', v)} placeholder={t('ui:ContactDetailLeftPanel.city')} />
          <InlineField label={t('ui:ContactDetailLeftPanel.provinceState')} value={contact.state || ''} onSave={(v) => saveField('state', v)} placeholder={t('ui:ContactDetailLeftPanel.stateProvince')} />
          <InlineField label={t('ui:ContactDetailLeftPanel.postalZip')} value={contact.zip_code || ''} onSave={(v) => saveField('zip_code', v)} placeholder={t('ui:ContactDetailLeftPanel.postalCode')} />
          <InlineField label={t('ui:ContactDetailLeftPanel.country')} value={contact.country || ''} onSave={(v) => saveField('country', v)} placeholder={t('ui:ContactDetailLeftPanel.country')} />
        </div>
      </div>

      <hr className="border-gray-200 dark:border-gray-700" />

      {/* Lead Info */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-3">{t('ui:ContactDetailLeftPanel.leadInfo')}</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-[10px] uppercase tracking-wider font-semibold text-gray-400 dark:text-gray-500 mb-0.5">{t('ui:ContactDetailLeftPanel.type')}</label>
            <select
              value={contact.type}
              onChange={(e) => saveField('type', e.target.value)}
              className="w-full px-2 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
            >
              <option value="client">{t('ui:ContactDetailLeftPanel.client')}</option>
              <option value="vendor">{t('ui:ContactDetailLeftPanel.vendor')}</option>
              <option value="both">{t('ui:ContactDetailLeftPanel.both')}</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-wider font-semibold text-gray-400 dark:text-gray-500 mb-0.5">{t('ui:ContactDetailLeftPanel.leadSource')}</label>
            <select
              value={contact.lead_source || ''}
              onChange={(e) => saveField('lead_source', e.target.value)}
              className="w-full px-2 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
            >
              <option value="">{t('ui:ContactDetailLeftPanel.select')}</option>
              {LEAD_SOURCES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-wider font-semibold text-gray-400 dark:text-gray-500 mb-0.5">{t('ui:ContactDetailLeftPanel.assignedUser')}</label>
            <p className="text-sm text-gray-600 dark:text-gray-400 px-2 py-1">
              {contact.assigned_user_id || t('ui:ContactDetailLeftPanel.unassigned')}
            </p>
          </div>
        </div>
      </div>

      <hr className="border-gray-200 dark:border-gray-700" />

      {/* Settings */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-3">{t('ui:ContactDetailLeftPanel.settings')}</h3>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {contact.dnd_enabled ? (
              <BellOff className="h-4 w-4 text-red-500" />
            ) : (
              <Bell className="h-4 w-4 text-gray-400" />
            )}
            <span className="text-sm text-gray-700 dark:text-gray-300">{t('ui:ContactDetailLeftPanel.doNotDisturb')}</span>
          </div>
          <button
            onClick={() => saveField('dnd_enabled', !contact.dnd_enabled)}
            className={cn(
              'relative w-10 h-5 rounded-full transition-colors',
              contact.dnd_enabled ? 'bg-red-500' : 'bg-gray-300 dark:bg-gray-600',
            )}
          >
            <div
              className={cn(
                'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform',
                contact.dnd_enabled ? 'translate-x-5' : 'translate-x-0.5',
              )}
            />
          </button>
        </div>
        {/* Email absorption opt-out — defaults ON. Flip OFF for
            personal contacts mixed into the CRM whose emails
            shouldn't be summarized into the memory layer. */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'inline-block w-4 h-4 rounded-sm text-center text-[10px] leading-4 font-bold',
                contact.email_absorption_enabled !== false
                  ? 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500',
              )}
            >
              ✉
            </span>
            <span
              className="text-sm text-gray-700 dark:text-gray-300"
              title={t('ui:ContactDetailLeftPanel.whenOnEmailsToFrom')}
            >
             {t('ui:ContactDetailLeftPanel.absorbEmails')}
            </span>
          </div>
          <button
            onClick={() =>
              saveField(
                'email_absorption_enabled',
                !(contact.email_absorption_enabled !== false),
              )
            }
            className={cn(
              'relative w-10 h-5 rounded-full transition-colors',
              contact.email_absorption_enabled !== false
                ? 'bg-indigo-500'
                : 'bg-gray-300 dark:bg-gray-600',
            )}
          >
            <div
              className={cn(
                'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform',
                contact.email_absorption_enabled !== false ? 'translate-x-5' : 'translate-x-0.5',
              )}
            />
          </button>
        </div>
      </div>

      <hr className="border-gray-200 dark:border-gray-700" />

      {/* Tags */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-3 flex items-center gap-1.5">
          <Tag className="h-3.5 w-3.5" /> {t('ui:ContactDetailLeftPanel.tags')}
        </h3>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {tags.length === 0 && (
            <span className="text-xs text-gray-400 dark:text-gray-500 italic">{t('ui:ContactDetailLeftPanel.noTags')}</span>
          )}
          {tags.map((t: any) => {
            const name = t.tag_name || t.name || t
            return (
              <span
                key={name}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400"
              >
                {name}
                <button
                  onClick={() => onRemoveTag(name)}
                  className="hover:text-red-500 transition-colors"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            )
          })}
        </div>
        <div className="relative">
          <input
            type="text"
            value={tagInput}
            onChange={(e) => { setTagInput(e.target.value); setShowTagSuggestions(true) }}
            onFocus={() => setShowTagSuggestions(true)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && tagInput.trim()) {
                e.preventDefault()
                onAddTag(tagInput)
              }
            }}
            placeholder={t('ui:ContactDetailLeftPanel.addTag')}
            className="w-full px-2 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {showTagSuggestions && tagInput && tagSuggestions.length > 0 && (
            <div className="absolute z-10 top-full left-0 right-0 mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg max-h-32 overflow-y-auto">
              {tagSuggestions.slice(0, 8).map((s) => (
                <button
                  key={s}
                  onClick={() => onAddTag(s)}
                  className="w-full text-left px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <hr className="border-gray-200 dark:border-gray-700" />

      {/* Dates */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-3 flex items-center gap-1.5">
          <Calendar className="h-3.5 w-3.5" /> {t('ui:ContactDetailLeftPanel.dates')}
        </h3>
        <div className="space-y-1.5 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">{t('ui:ContactDetailLeftPanel.created')}</span>
            <span className="text-gray-700 dark:text-gray-300">{formatDate(contact.created_at)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">{t('ui:ContactDetailLeftPanel.updated')}</span>
            <span className="text-gray-700 dark:text-gray-300">{formatDate(contact.updated_at)}</span>
          </div>
          {activities.length > 0 && (
            <div className="flex justify-between">
              <span className="text-gray-500 dark:text-gray-400">{t('ui:ContactDetailLeftPanel.lastActivity')}</span>
              <span className="text-gray-700 dark:text-gray-300">{formatDate(activities[0].created_at)}</span>
            </div>
          )}
        </div>
      </div>

      <hr className="border-gray-200 dark:border-gray-700" />

      {/* Tax ID / Notes */}
      <div className="space-y-2">
        <InlineField
          label={t('ui:ContactDetailLeftPanel.taxId')}
          value={contact.tax_id || ''}
          onSave={(v) => saveField('tax_id', v)}
          placeholder={t('ui:ContactDetailLeftPanel.addTaxId')}
        />
        <NotesEditor
          value={contact.notes || ''}
          onSave={(v) => saveField('notes', v)}
        />
      </div>
    </div>
  )
}
