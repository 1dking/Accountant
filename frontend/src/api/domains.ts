import { api } from './client'

export type DomainCheck = {
  domain: string
  tld: string
  available: boolean
  premium?: boolean
  currency: string
  price_cents_wholesale: number
  price_cents_retail: number
  renewal_cents_wholesale: number
  renewal_cents_retail: number
  markup_pct: number
  error?: string
}

export type DomainPurchase = {
  id: string
  domain: string
  tld: string
  status: 'pending' | 'paid' | 'registered' | 'active' | 'expired' | 'failed' | 'refunded'
  years: number
  price_cents_paid: number
  price_cents_wholesale: number
  currency: string
  registered_at: string | null
  expires_at: string | null
  auto_renew: boolean
  partner: string
  email_enabled: boolean
  notes: string | null
  created_at: string | null
}

export type Mailbox = {
  local_part: string
  address: string
  name: string
  is_internal?: boolean
  storage_usage?: number
}

export type DnsRecord = {
  id: string
  name: string
  type: string
  content: string
  ttl: string | number
  prio?: string | number | null
  notes?: string | null
}

export const domainsApi = {
  check: (domain: string) =>
    api.post<{ data: DomainCheck }>('/domains/check', { domain }),

  purchase: (domain: string, years = 1) =>
    api.post<{ data: { checkout_url: string; session_id: string; purchase_id: string } }>(
      '/domains/purchase', { domain, years },
    ),

  list: () => api.get<{ data: DomainPurchase[] }>('/domains'),

  get: (id: string) => api.get<{ data: DomainPurchase }>(`/domains/${id}`),

  listDns: (id: string) =>
    api.get<{ data: DnsRecord[] }>(`/domains/${id}/dns`),

  upsertDns: (id: string, body: {
    type: string; content: string; name?: string; ttl?: number;
    priority?: number | null; record_id?: string | null;
  }) => api.post(`/domains/${id}/dns`, body),

  deleteDns: (id: string, recordId: string) =>
    api.delete(`/domains/${id}/dns/${recordId}`),

  // Email hosting (Migadu)
  enableEmail: (id: string) =>
    api.post<{ data: { enabled: boolean; records_created: number; records_skipped: number; note: string } }>(
      `/domains/${id}/email/enable`,
    ),

  listMailboxes: (id: string) =>
    api.get<{ data: Mailbox[] }>(`/domains/${id}/mailboxes`),

  createMailbox: (id: string, body: { local_part: string; name: string; password: string }) =>
    api.post<{ data: Mailbox }>(`/domains/${id}/mailboxes`, body),

  deleteMailbox: (id: string, localPart: string) =>
    api.delete(`/domains/${id}/mailboxes/${localPart}`),

  resetMailboxPassword: (id: string, localPart: string, password: string) =>
    api.put(`/domains/${id}/mailboxes/${localPart}/password`, { password }),

  emailStatus: (id: string) =>
    api.get<{ data: { email_enabled: boolean; active: boolean; state: string; can_send?: boolean; can_receive?: boolean } }>(
      `/domains/${id}/email/status`,
    ),

  // CRM inbox (IMAP/SMTP)
  inboxList: (id: string, localPart: string, limit = 30) =>
    api.get<{ data: InboxMessage[] }>(`/domains/${id}/mailboxes/${localPart}/inbox?limit=${limit}`),

  inboxMessage: (id: string, localPart: string, uid: string) =>
    api.get<{ data: InboxMessageFull }>(`/domains/${id}/mailboxes/${localPart}/inbox/${uid}`),

  inboxSend: (id: string, localPart: string, body: { to: string; subject: string; body: string; in_reply_to?: string }) =>
    api.post<{ data: { sent: boolean; message_id: string } }>(`/domains/${id}/mailboxes/${localPart}/send`, body),
}

export type InboxMessage = {
  uid: string; from: string; to: string; subject: string; date: string; message_id: string; seen: boolean
}
export type InboxMessageFull = InboxMessage & { text: string; html: string }

