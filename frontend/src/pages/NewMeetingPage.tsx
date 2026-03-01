import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Plus, X } from 'lucide-react'
import { createMeeting } from '@/api/meetings'
import { listContacts } from '@/api/contacts'

export default function NewMeetingPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [title, setTitle] = useState('')
  const [scheduledStart, setScheduledStart] = useState('')
  const [scheduledEnd, setScheduledEnd] = useState('')
  const [description, setDescription] = useState('')
  const [contactId, setContactId] = useState('')
  const [recordMeeting, setRecordMeeting] = useState(true)
  const [participantEmail, setParticipantEmail] = useState('')
  const [participantEmails, setParticipantEmails] = useState<string[]>([])
  const [error, setError] = useState('')

  const { data: contactsData } = useQuery({
    queryKey: ['contacts', { page_size: 200 }],
    queryFn: () => listContacts({ page_size: 200 }),
  })
  const contacts = contactsData?.data ?? []

  const mutation = useMutation({
    mutationFn: () =>
      createMeeting({
        title,
        scheduled_start: new Date(scheduledStart).toISOString(),
        scheduled_end: scheduledEnd ? new Date(scheduledEnd).toISOString() : undefined,
        description: description || undefined,
        contact_id: contactId || undefined,
        record_meeting: recordMeeting,
        participant_emails: participantEmails.length > 0 ? participantEmails : undefined,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] })
      navigate(`/meetings/${data.data.id}`)
    },
    onError: (err: any) => {
      setError(err?.message || 'Failed to create meeting')
    },
  })

  const addEmail = () => {
    const trimmed = participantEmail.trim()
    if (trimmed && !participantEmails.includes(trimmed)) {
      setParticipantEmails([...participantEmails, trimmed])
      setParticipantEmail('')
    }
  }

  const removeEmail = (email: string) => {
    setParticipantEmails(participantEmails.filter((e) => e !== email))
  }

  const isValid = title.trim().length > 0 && scheduledStart.length > 0

  return (
    <div className="p-6 max-w-2xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/meetings')} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
          <ArrowLeft className="h-5 w-5 text-gray-500 dark:text-gray-400" />
        </button>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Schedule Meeting</h1>
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5">
        <div className="space-y-4">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Title *</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Meeting title"
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Date/Time */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Start Date & Time *</label>
              <input
                type="datetime-local"
                value={scheduledStart}
                onChange={(e) => setScheduledStart(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">End Date & Time</label>
              <input
                type="datetime-local"
                value={scheduledEnd}
                onChange={(e) => setScheduledEnd(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Meeting description or agenda..."
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Contact */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Contact</label>
            <select
              value={contactId}
              onChange={(e) => setContactId(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">No contact</option>
              {contacts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.company_name}{c.contact_name ? ` - ${c.contact_name}` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Record Meeting */}
          <div className="flex items-center gap-3">
            <input
              id="record-meeting"
              type="checkbox"
              checked={recordMeeting}
              onChange={(e) => setRecordMeeting(e.target.checked)}
              className="h-4 w-4 text-blue-600 dark:text-blue-400 border-gray-300 dark:border-gray-600 rounded focus:ring-blue-500"
            />
            <label htmlFor="record-meeting" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Record this meeting
            </label>
          </div>

          {/* Participant emails */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Participant Emails</label>
            <div className="flex gap-2">
              <input
                type="email"
                value={participantEmail}
                onChange={(e) => setParticipantEmail(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addEmail() } }}
                placeholder="email@example.com"
                className="flex-1 px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="button"
                onClick={addEmail}
                className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                Add
              </button>
            </div>
            {participantEmails.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {participantEmails.map((email) => (
                  <span
                    key={email}
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium bg-blue-50 dark:bg-blue-900/30 text-blue-700 rounded-full"
                  >
                    {email}
                    <button
                      onClick={() => removeEmail(email)}
                      className="hover:text-blue-900"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {error && <p className="text-sm text-red-600 mt-3">{error}</p>}

        <div className="mt-5 flex gap-3">
          <button
            onClick={() => mutation.mutate()}
            disabled={!isValid || mutation.isPending}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? 'Creating...' : 'Schedule Meeting'}
          </button>
          <button
            onClick={() => navigate('/meetings')}
            className="px-4 py-2 text-sm font-medium border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
