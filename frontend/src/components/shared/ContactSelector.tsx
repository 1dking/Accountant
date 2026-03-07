import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listContacts } from '@/api/contacts'
import { Search, X, User, Building2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ContactListItem } from '@/types/models'

interface ContactSelectorProps {
  value: string | null
  onChange: (contactId: string | null, contact?: ContactListItem) => void
  placeholder?: string
  className?: string
  disabled?: boolean
  /** Show only contacts of this type */
  filterType?: 'client' | 'vendor' | 'lead' | 'partner'
}

export default function ContactSelector({
  value,
  onChange,
  placeholder = 'Select contact...',
  className,
  disabled,
  filterType,
}: ContactSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [search, setSearch] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Fetch contacts
  const { data: contactsData } = useQuery({
    queryKey: ['contacts-selector', search, filterType],
    queryFn: () =>
      listContacts({
        search: search || undefined,
        type: filterType,
        is_active: true,
        page_size: 50,
      }),
  })
  const contacts: ContactListItem[] = contactsData?.data ?? []

  // Find the selected contact
  const selectedContact = contacts.find((c) => c.id === value)

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Focus input when opening
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isOpen])

  const handleSelect = (contact: ContactListItem) => {
    onChange(contact.id, contact)
    setIsOpen(false)
    setSearch('')
  }

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    onChange(null)
    setSearch('')
  }

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      {/* Trigger button */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'w-full flex items-center gap-2 px-3 py-2 text-sm border rounded-md transition-colors text-left',
          'dark:border-gray-600 dark:bg-gray-800',
          'focus:outline-none focus:ring-2 focus:ring-blue-500',
          disabled && 'opacity-50 cursor-not-allowed',
          !disabled && 'hover:border-gray-400 dark:hover:border-gray-500',
        )}
      >
        {selectedContact ? (
          <>
            {selectedContact.type === 'client' ? (
              <User className="h-4 w-4 text-blue-500 shrink-0" />
            ) : (
              <Building2 className="h-4 w-4 text-purple-500 shrink-0" />
            )}
            <span className="flex-1 truncate text-gray-900 dark:text-gray-100">
              {selectedContact.company_name}
              {selectedContact.contact_name && (
                <span className="text-gray-500 dark:text-gray-400 ml-1">
                  — {selectedContact.contact_name}
                </span>
              )}
            </span>
            <button
              type="button"
              onClick={handleClear}
              className="p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
            >
              <X className="h-3 w-3 text-gray-400" />
            </button>
          </>
        ) : (
          <span className="text-gray-400 dark:text-gray-500">{placeholder}</span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 mt-1 w-full bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg overflow-hidden">
          {/* Search input */}
          <div className="p-2 border-b border-gray-100 dark:border-gray-700">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
              <input
                ref={inputRef}
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search contacts..."
                className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-gray-800 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Contact list */}
          <div className="max-h-60 overflow-y-auto">
            {contacts.length === 0 ? (
              <div className="px-3 py-4 text-sm text-gray-500 dark:text-gray-400 text-center">
                No contacts found
              </div>
            ) : (
              contacts.map((contact) => (
                <button
                  key={contact.id}
                  type="button"
                  onClick={() => handleSelect(contact)}
                  className={cn(
                    'w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors',
                    contact.id === value && 'bg-blue-50 dark:bg-blue-900/20',
                  )}
                >
                  {contact.type === 'client' ? (
                    <User className="h-4 w-4 text-blue-500 shrink-0" />
                  ) : (
                    <Building2 className="h-4 w-4 text-purple-500 shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 dark:text-gray-100 truncate">
                      {contact.company_name}
                    </p>
                    {contact.contact_name && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                        {contact.contact_name}
                      </p>
                    )}
                  </div>
                  {contact.email && (
                    <span className="text-xs text-gray-400 dark:text-gray-500 truncate max-w-[120px]">
                      {contact.email}
                    </span>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
