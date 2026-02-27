import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Users, Plus, Search } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { listContacts, type ContactFilters } from '@/api/contacts'
import type { ContactListItem } from '@/types/models'

const TYPE_TABS = [
  { value: '', label: 'All' },
  { value: 'client', label: 'Clients' },
  { value: 'vendor', label: 'Vendors' },
  { value: 'both', label: 'Both' },
]

export default function ContactsPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const canEdit = user?.role === 'admin' || user?.role === 'accountant'

  const [filters, setFilters] = useState<ContactFilters>({ page: 1, page_size: 25 })
  const [search, setSearch] = useState('')
  const [typeTab, setTypeTab] = useState('')

  const { data } = useQuery({
    queryKey: ['contacts', { ...filters, search: search || undefined, type: typeTab || undefined }],
    queryFn: () => listContacts({ ...filters, search: search || undefined, type: typeTab || undefined }),
  })

  const contacts: ContactListItem[] = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Contacts</h1>
        {canEdit && (
          <button
            onClick={() => navigate('/contacts/new')}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Contact
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setFilters(f => ({ ...f, page: 1 })) }}
            placeholder="Search contacts..."
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {TYPE_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => { setTypeTab(tab.value); setFilters(f => ({ ...f, page: 1 })) }}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                typeTab === tab.value
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left">
              <th className="px-5 py-3 font-medium text-gray-500">Company</th>
              <th className="px-5 py-3 font-medium text-gray-500">Contact</th>
              <th className="px-5 py-3 font-medium text-gray-500">Type</th>
              <th className="px-5 py-3 font-medium text-gray-500">Email</th>
              <th className="px-5 py-3 font-medium text-gray-500">Phone</th>
              <th className="px-5 py-3 font-medium text-gray-500">Location</th>
            </tr>
          </thead>
          <tbody>
            {contacts.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-12 text-center text-gray-400">
                  <Users className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  No contacts found
                </td>
              </tr>
            ) : (
              contacts.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => navigate(`/contacts/${c.id}`)}
                  className="border-b border-gray-50 hover:bg-gray-50/50 cursor-pointer transition-colors"
                >
                  <td className="px-5 py-3 font-medium text-gray-900">{c.company_name}</td>
                  <td className="px-5 py-3 text-gray-600">{c.contact_name || '—'}</td>
                  <td className="px-5 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      c.type === 'client' ? 'bg-blue-100 text-blue-700' :
                      c.type === 'vendor' ? 'bg-purple-100 text-purple-700' :
                      'bg-emerald-100 text-emerald-700'
                    }`}>
                      {c.type === 'both' ? 'Client & Vendor' : c.type.charAt(0).toUpperCase() + c.type.slice(1)}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-600">{c.email || '—'}</td>
                  <td className="px-5 py-3 text-gray-600">{c.phone || '—'}</td>
                  <td className="px-5 py-3 text-gray-600">
                    {[c.city, c.state].filter(Boolean).join(', ') || '—'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {meta && meta.total_pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">
            Page {meta.page} of {meta.total_pages} ({meta.total_count} contacts)
          </p>
          <div className="flex gap-2">
            <button
              disabled={meta.page <= 1}
              onClick={() => setFilters(f => ({ ...f, page: (f.page ?? 1) - 1 }))}
              className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-50 hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              disabled={meta.page >= meta.total_pages}
              onClick={() => setFilters(f => ({ ...f, page: (f.page ?? 1) + 1 }))}
              className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-50 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
