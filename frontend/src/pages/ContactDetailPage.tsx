import { useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Pencil, Trash2, X, Check } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { getContact, updateContact, deleteContact } from '@/api/contacts'

export default function ContactDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const canEdit = user?.role === 'admin' || user?.role === 'accountant'

  const [editing, setEditing] = useState(false)
  const [formData, setFormData] = useState<Record<string, any>>({})

  const { data, isLoading } = useQuery({
    queryKey: ['contact', id],
    queryFn: () => getContact(id!),
    enabled: !!id,
  })

  const updateMutation = useMutation({
    mutationFn: (updates: Record<string, any>) => updateContact(id!, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact', id] })
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      setEditing(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteContact(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      navigate('/contacts')
    },
  })

  const contact = data?.data

  if (isLoading) {
    return <div className="p-6"><div className="animate-pulse h-8 w-48 bg-gray-200 dark:bg-gray-700 rounded" /></div>
  }

  if (!contact) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500 dark:text-gray-400">Contact not found</p>
        <button onClick={() => navigate('/contacts')} className="text-blue-600 dark:text-blue-400 hover:underline mt-2 text-sm">
          Back to Contacts
        </button>
      </div>
    )
  }

  const startEditing = () => {
    setFormData({
      type: contact.type,
      company_name: contact.company_name,
      contact_name: contact.contact_name || '',
      email: contact.email || '',
      phone: contact.phone || '',
      address_line1: contact.address_line1 || '',
      address_line2: contact.address_line2 || '',
      city: contact.city || '',
      state: contact.state || '',
      zip_code: contact.zip_code || '',
      country: contact.country,
      tax_id: contact.tax_id || '',
      notes: contact.notes || '',
    })
    setEditing(true)
  }

  const saveEdit = () => {
    const updates: Record<string, any> = {}
    for (const [key, value] of Object.entries(formData)) {
      if (value !== '' || key === 'company_name') {
        updates[key] = value || null
      }
    }
    updates.company_name = formData.company_name
    updates.type = formData.type
    updates.country = formData.country || 'US'
    updateMutation.mutate(updates)
  }

  const field = (label: string, key: string, type = 'text') => (
    <div>
      <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{label}</label>
      {editing ? (
        key === 'type' ? (
          <select
            value={formData[key] || ''}
            onChange={(e) => setFormData({ ...formData, [key]: e.target.value })}
            className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="client">Client</option>
            <option value="vendor">Vendor</option>
            <option value="both">Client & Vendor</option>
          </select>
        ) : key === 'notes' ? (
          <textarea
            value={formData[key] || ''}
            onChange={(e) => setFormData({ ...formData, [key]: e.target.value })}
            rows={3}
            className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        ) : (
          <input
            type={type}
            value={formData[key] || ''}
            onChange={(e) => setFormData({ ...formData, [key]: e.target.value })}
            className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        )
      ) : (
        <p className="text-sm text-gray-900 dark:text-gray-100">
          {key === 'type'
            ? (contact as any)[key] === 'both' ? 'Client & Vendor' : ((contact as any)[key] as string)?.charAt(0).toUpperCase() + ((contact as any)[key] as string)?.slice(1)
            : (contact as any)[key] || '—'}
        </p>
      )}
    </div>
  )

  return (
    <div className="p-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/contacts')} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
          <ArrowLeft className="h-5 w-5 text-gray-500 dark:text-gray-400" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{contact.company_name}</h1>
          {contact.contact_name && (
            <p className="text-sm text-gray-500 dark:text-gray-400">{contact.contact_name}</p>
          )}
        </div>
        {canEdit && !editing && (
          <div className="flex gap-2">
            <button onClick={startEditing} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
              <Pencil className="h-3.5 w-3.5" /> Edit
            </button>
            <button
              onClick={() => { if (confirm('Delete this contact?')) deleteMutation.mutate() }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-red-200 text-red-600 rounded-lg hover:bg-red-50"
            >
              <Trash2 className="h-3.5 w-3.5" /> Delete
            </button>
          </div>
        )}
        {editing && (
          <div className="flex gap-2">
            <button onClick={() => setEditing(false)} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
              <X className="h-3.5 w-3.5" /> Cancel
            </button>
            <button
              onClick={saveEdit}
              disabled={updateMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <Check className="h-3.5 w-3.5" /> Save
            </button>
          </div>
        )}
      </div>

      {/* Details */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {field('Company Name', 'company_name')}
          {field('Contact Name', 'contact_name')}
          {field('Type', 'type')}
          {field('Email', 'email', 'email')}
          {field('Phone', 'phone', 'tel')}
          {field('Tax ID', 'tax_id')}
        </div>

        <hr className="my-5 border-gray-100 dark:border-gray-700" />
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Address</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {field('Address Line 1', 'address_line1')}
          {field('Address Line 2', 'address_line2')}
          {field('City', 'city')}
          {field('State', 'state')}
          {field('ZIP Code', 'zip_code')}
          {field('Country', 'country')}
        </div>

        <hr className="my-5 border-gray-100 dark:border-gray-700" />
        {field('Notes', 'notes')}
      </div>
    </div>
  )
}
