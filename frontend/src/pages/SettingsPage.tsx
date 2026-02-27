import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router'
import { User, Mail, Inbox, Landmark, CreditCard, MessageSquare, Bell, Lock, Receipt } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'
import ProfileSettings from '@/components/settings/ProfileSettings'
import UserManagement from '@/components/settings/UserManagement'
import SmtpSettings from '@/components/settings/SmtpSettings'
import GmailSettings from '@/components/settings/GmailSettings'
import PlaidSettings from '@/components/settings/PlaidSettings'
import StripeSettings from '@/components/settings/StripeSettings'
import SmsSettings from '@/components/settings/SmsSettings'
import CategorizationRules from '@/components/settings/CategorizationRules'
import ReminderSettings from '@/components/settings/ReminderSettings'
import PeriodSettings from '@/components/settings/PeriodSettings'
import TaxSettings from '@/components/settings/TaxSettings'

const TABS: { id: string; label: string; icon: typeof User; adminOnly?: boolean }[] = [
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'users', label: 'Users', icon: User, adminOnly: true },
  { id: 'email', label: 'Email (SMTP)', icon: Mail },
  { id: 'gmail', label: 'Gmail', icon: Inbox },
  { id: 'banking', label: 'Banking', icon: Landmark },
  { id: 'payments', label: 'Payments', icon: CreditCard },
  { id: 'tax', label: 'Sales Tax', icon: Receipt },
  { id: 'sms', label: 'SMS', icon: MessageSquare },
  { id: 'reminders', label: 'Reminders', icon: Bell },
  { id: 'periods', label: 'Periods', icon: Lock, adminOnly: true },
]

export default function SettingsPage() {
  const { user } = useAuthStore()
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'profile')

  useEffect(() => {
    const tab = searchParams.get('tab')
    if (tab) setActiveTab(tab)
  }, [searchParams])

  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId)
    setSearchParams({ tab: tabId })
  }

  const visibleTabs = TABS.filter(t => !t.adminOnly || user?.role === 'admin')

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      <div className="flex flex-col md:flex-row gap-6">
        {/* Tab nav */}
        <nav className="md:w-48 shrink-0">
          <div className="flex md:flex-col gap-1 overflow-x-auto md:overflow-visible pb-2 md:pb-0">
            {visibleTabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors',
                    activeTab === tab.id
                      ? 'bg-blue-50 text-blue-600'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              )
            })}
          </div>
        </nav>

        {/* Tab content */}
        <div className="flex-1 min-w-0">
          {activeTab === 'profile' && <ProfileSettings />}
          {activeTab === 'users' && user?.role === 'admin' && <UserManagement />}
          {activeTab === 'email' && <SmtpSettings />}
          {activeTab === 'gmail' && <GmailSettings />}
          {activeTab === 'banking' && (
            <>
              <PlaidSettings />
              <div className="mt-8">
                <CategorizationRules />
              </div>
            </>
          )}
          {activeTab === 'payments' && <StripeSettings />}
          {activeTab === 'tax' && <TaxSettings />}
          {activeTab === 'sms' && <SmsSettings />}
          {activeTab === 'reminders' && <ReminderSettings />}
          {activeTab === 'periods' && user?.role === 'admin' && <PeriodSettings />}
        </div>
      </div>
    </div>
  )
}
