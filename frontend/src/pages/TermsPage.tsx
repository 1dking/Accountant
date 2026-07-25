import LegalDocument from '@/components/LegalDocument'

// OCIDM O-Brain Terms of Service — v0.2. Version mirrored in
// backend/app/core/legal.py (TERMS_VERSION).
const CONTENT = `# O-Brain Terms of Service

**Version 0.2 — pending legal review** · Effective date: July 1, 2026
Provided by OC Interactive Digital Agency Corp. ("OCIDM," "we," "us")
203-762 Upper James St, Hamilton, ON L9C 3A2, Canada · support@ocidm.io

> **⚠️ This version has real company details filled in but has not yet been reviewed by a lawyer.**
> It accurately describes the O-Brain service. Sections marked **[LEGAL REVIEW]** — especially
> liability limits, disclaimers, and dispute terms — require qualified Canadian and U.S. counsel before
> this becomes final (v1.0). Publish this as the current terms until a reviewed v1.0 replaces it.

---

## 1. Agreement

By creating an account or using O-Brain, you agree to these Terms and to our Privacy Policy. If you are
using O-Brain on behalf of a business, you represent that you are authorized to bind that business.

## 2. The service

O-Brain is an all-in-one business management platform including CRM, invoicing and proposals,
bookkeeping and accounting, bank-transaction sync (via Plaid), phone and messaging (via Twilio), video
meetings (via LiveKit), scheduling, document and file tools, automation, AI features, a client portal,
and — for eligible plans — white-label and multi-account ("operator") capabilities. We may update,
add, or remove features over time.

## 3. Accounts and eligibility

You must be at least 18 and provide accurate information. You are responsible for your account,
your users, and keeping credentials secure. We require multi-factor authentication for certain sensitive
actions. You are responsible for all activity under your account.

## 4. Plans, billing, and payments

Paid plans are billed on a subscription basis (monthly or annual) at the prices shown at purchase, in
**U.S. dollars (USD)**. **[LEGAL REVIEW: confirm tax handling (GST/HST and U.S. sales tax), auto-renewal
disclosures required by some U.S. states and Canadian provinces, and cancellation/refund terms.]**
Certain features are **metered** (for example, AI usage, phone/SMS/voice, and bank connections); usage
beyond included allowances may incur additional charges as disclosed. Payments are processed by Stripe;
where you collect payments from your own customers, funds route through your own connected Stripe account.

## 5. Operators, sub-accounts, and reselling (white-label)

If your plan permits, you may operate O-Brain on behalf of your own clients under your own branding and
may resell access to them. If you do, you are the party responsible to your clients: you must have your
own agreement and privacy policy with them, obtain any required consents, set your own prices, handle
your clients' billing and support, and comply with all applicable laws. You are responsible for your
clients' use of the platform, and you agree to use it — and any data obtained through it — only for your
clients' benefit. **[LEGAL REVIEW: the reseller/operator relationship, markup billing, and responsibility
allocation should be governed by a separate operator agreement drafted by counsel; this section is a
summary only.]**

## 6. Third-party services

O-Brain integrates third-party services (including Plaid, Twilio, Stripe, LiveKit, Google, and AI
providers). Your use of those integrations is also subject to those providers' terms, and we are not
responsible for third-party services. Bank connections are provided via Plaid and are subject to Plaid's
end-user terms and privacy policy.

## 7. Your data and content

As between you and OCIDM, **you own the data and content you put into O-Brain.** You grant us the limited
rights needed to host, process, and display it to provide the service, including sending relevant data to
subprocessors (such as AI providers) to deliver features you use. You are responsible for having the
rights and consents needed for the data you enter, including your customers' information.

## 8. Acceptable use

You will not use O-Brain to: break the law; send unlawful, unsolicited, or spam messages, or violate
telemarketing/anti-spam rules (including Canada's CASL, U.S. TCPA/CAN-SPAM, and carrier/A2P requirements
for SMS); infringe others' rights; upload malware; attempt to breach security or access other tenants'
data; or resell or misuse third-party data (including bank data) outside the permitted purpose. We may
suspend accounts that create security, legal, fraud, or abuse risk. **[LEGAL REVIEW: confirm messaging/
telephony compliance obligations for Canada + U.S.]**

## 9. AI features

AI features generate outputs that may be inaccurate or incomplete. **You are responsible for reviewing
AI output before relying on it**, especially for financial, accounting, or legal matters. AI features are
tools, not professional advice.

## 10. Service availability and changes

We aim for reliable service but do not guarantee uninterrupted availability. We may modify or discontinue
features, with notice where practicable.

## 11. Disclaimers

**[LEGAL REVIEW — placeholder for counsel to finalize.]** The service is provided "as is" and "as
available," without warranties of any kind to the fullest extent permitted by law, including warranties
of merchantability, fitness for a particular purpose, and non-infringement. O-Brain does not provide
accounting, tax, legal, or financial advice.

## 12. Limitation of liability

**[LEGAL REVIEW — placeholder for counsel to finalize; liability caps and exclusions must be drafted and
localized for Canada + U.S.]** To the fullest extent permitted by law, OCIDM will not be liable for
indirect, incidental, special, consequential, or punitive damages, or for lost profits or data, and our
total liability will be limited as set out in the final, counsel-reviewed terms.

## 13. Termination

You may cancel at any time. We may suspend or terminate for breach of these Terms, non-payment, or legal/
security risk. On termination, your right to use the service ends; you may export your data before
termination, and we will delete or anonymize data as described in the Privacy Policy, subject to legal
retention. **[LEGAL REVIEW: confirm post-termination data handling and any legally required retention.]**

## 14. Governing law and disputes

These Terms are governed by the laws of the **Province of Ontario and the federal laws of Canada
applicable therein**, without regard to conflict-of-laws rules. The parties submit to the exclusive
jurisdiction of the **courts of the Province of Ontario, Canada**. **[LEGAL REVIEW: confirm venue, and
whether to add arbitration and/or a class-action waiver — these choices materially affect enforceability
for U.S. users and should be set by counsel.]**

## 15. Changes to these Terms

We may update these Terms and will post the new version with an updated version number and effective date.
Continued use after changes take effect means you accept them.

## 16. Contact

OC Interactive Digital Agency Corp.
203-762 Upper James St, Hamilton, ON L9C 3A2, Canada · support@ocidm.io
`

export default function TermsPage() {
  return <LegalDocument content={CONTENT} />
}
