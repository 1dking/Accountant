import LegalDocument from '@/components/LegalDocument'

// OCIDM O-Brain Terms of Service — v1.0 (final). Version mirrored in
// backend/app/core/legal.py (TERMS_VERSION).
const CONTENT = `# O-Brain Terms of Service

**Version 1.0** · Effective date: July 1, 2026
OC Interactive Digital Agency Corp. ("OCIDM," "we," "us")
203-762 Upper James St, Hamilton, ON L9C 3A2, Canada · support@ocidm.io

## 1. Agreement

By creating an account or using O-Brain, you agree to these Terms and to our Privacy Policy. If you are
using O-Brain on behalf of a business, you represent that you are authorized to bind that business.

## 2. The service

O-Brain is an all-in-one business management platform including CRM, invoicing and proposals, bookkeeping
and accounting, bank-transaction sync (via Plaid), phone and messaging (via Twilio), video meetings (via
LiveKit), scheduling, document and file tools, automation, AI features, a client portal, and, for
eligible plans, white-label and multi-account ("operator") capabilities. We may update, add, or remove
features over time.

## 3. Accounts and eligibility

You must be at least 18 and provide accurate information. You are responsible for your account, your
users, and keeping credentials secure. We require multi-factor authentication for certain sensitive
actions, including connecting a bank account and accessing financial data. You are responsible for all
activity under your account.

## 4. Plans, billing, and payments

Paid plans are billed on a subscription basis (monthly or annual) at the prices shown at purchase, in
U.S. dollars (USD). Subscriptions renew automatically at the end of each billing period unless cancelled
before the renewal date. You may cancel at any time, and cancellation takes effect at the end of the
current billing period. Fees are non-refundable except where required by law. You are responsible for any
applicable taxes. Certain features are metered (for example, AI usage, phone, SMS, voice, and bank
connections); usage beyond included allowances may incur additional charges as disclosed. Payments are
processed by Stripe; where you collect payments from your own customers, funds route through your own
connected Stripe account.

## 5. Operators, sub-accounts, and reselling (white-label)

If your plan permits, you may operate O-Brain on behalf of your own clients under your own branding and
may resell access to them. If you do, you are the party responsible to your clients: you must have your
own agreement and privacy policy with them, obtain any required consents, set your own prices, handle
your clients' billing and support, and comply with all applicable laws. You are responsible for your
clients' use of the platform, and you agree to use it, and any data obtained through it, only for your
clients' benefit.

## 6. Third-party services

O-Brain integrates third-party services (including Plaid, Twilio, Stripe, LiveKit, Google, and AI
providers). Your use of those integrations is also subject to those providers' terms, and we are not
responsible for third-party services. Bank connections are provided via Plaid and are subject to Plaid's
end-user terms and privacy policy.

## 7. Your data and content

As between you and OCIDM, you own the data and content you put into O-Brain. You grant us the limited
rights needed to host, process, and display it to provide the service, including sending relevant data to
subprocessors (such as AI providers) to deliver features you use. You are responsible for having the
rights and consents needed for the data you enter, including your customers' information.

## 8. Acceptable use

You will not use O-Brain to: break the law; send unlawful, unsolicited, or spam messages, or violate
telemarketing and anti-spam rules (including Canada's CASL, the U.S. TCPA and CAN-SPAM, and carrier and
A2P requirements for SMS); infringe others' rights; upload malware; attempt to breach security or access
other tenants' data; or resell or misuse third-party data (including bank data) outside the permitted
purpose. We may suspend accounts that create security, legal, fraud, or abuse risk.

## 9. AI features

AI features generate outputs that may be inaccurate or incomplete. You are responsible for reviewing AI
output before relying on it, especially for financial, accounting, or legal matters. AI features are
tools, not professional advice.

## 10. Service availability and changes

We aim for reliable service but do not guarantee uninterrupted availability. We may modify or discontinue
features, with notice where practicable.

## 11. Disclaimers

The service is provided "as is" and "as available," without warranties of any kind to the fullest extent
permitted by law, including warranties of merchantability, fitness for a particular purpose, and
non-infringement. O-Brain does not provide accounting, tax, legal, or financial advice.

## 12. Limitation of liability

To the fullest extent permitted by law, OCIDM will not be liable for any indirect, incidental, special,
consequential, exemplary, or punitive damages, or for lost profits, revenues, or data. OCIDM's total
aggregate liability arising out of or relating to these Terms or the Service will not exceed the greater
of the amount you paid to OCIDM in the twelve (12) months before the event giving rise to the liability,
or one hundred dollars (CAD $100).

## 13. Termination

You may cancel at any time. We may suspend or terminate for breach of these Terms, non-payment, or legal
or security risk. On termination, your right to use the service ends; you may export your data before
termination, and we will delete or anonymize data as described in the Privacy Policy, subject to legal
retention.

## 14. Governing law and disputes

These Terms are governed by the laws of the Province of Ontario and the federal laws of Canada applicable
therein, without regard to conflict-of-laws rules. You and OCIDM submit to the exclusive jurisdiction of
the courts located in the Province of Ontario, Canada for any dispute arising out of or relating to these
Terms or the Service.

## 15. Changes to these Terms

We may update these Terms from time to time and will post the new version with an updated version number
and effective date. Continued use after changes take effect means you accept them.

## 16. Contact

OC Interactive Digital Agency Corp.
203-762 Upper James St, Hamilton, ON L9C 3A2, Canada · support@ocidm.io
`

export default function TermsPage() {
  return <LegalDocument content={CONTENT} />
}
