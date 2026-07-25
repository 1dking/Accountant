import LegalDocument from '@/components/LegalDocument'

// OCIDM O-Brain Privacy Policy — v0.2. Source of truth for the copy is this
// file; the version string is mirrored in backend/app/core/legal.py
// (PRIVACY_POLICY_VERSION) which the Plaid consent record references.
const CONTENT = `# O-Brain Privacy Policy

**Version 0.2 — pending legal review** · Effective date: July 1, 2026
Operated by OC Interactive Digital Agency Corp. ("OCIDM," "we," "us")
203-762 Upper James St, Hamilton, ON L9C 3A2, Canada · support@ocidm.io

> **⚠️ This version has real company details filled in but has not yet been reviewed by a lawyer.**
> It accurately describes how O-Brain handles data. Sections marked **[LEGAL REVIEW]** contain
> decisions that require qualified Canadian and U.S. counsel before this becomes final (v1.0).
> Publish this as the current policy and reference its version (v0.2) in consent records until a
> reviewed v1.0 replaces it.

---

## 1. Who we are and what this covers

OCIDM operates O-Brain, an all-in-one business management platform (CRM, invoicing and proposals,
bookkeeping and accounting, bank-transaction sync, phone and messaging, video meetings, scheduling,
document tools, file storage, automation, an AI assistant, and a client portal). This policy explains
what information O-Brain collects, how we use it, who we share it with, and the choices and rights you
have. It applies to users in **Canada and the United States**.

## 2. How O-Brain's structure affects your data ("operators" and their clients)

O-Brain can be used directly by a business, or provided by an **operator** — such as an accountant or
agency — who manages accounts on behalf of *their own* clients under their own branding.

- For a business's **own account and the data it enters**, OCIDM generally acts as the party
  responsible for that data ("controller").
- When an **operator** uses O-Brain to serve their clients, the **operator** generally decides how
  their clients' data is handled, and OCIDM processes that data **on the operator's behalf**
  ("processor"). In that case, the operator's own privacy policy governs their clients' data, and
  those clients should direct privacy requests to the operator.

**[LEGAL REVIEW:** the controller/processor split between OCIDM and operators must be confirmed by
counsel and mirrored in the operator/white-label agreement, since it determines who is responsible to
end users and to regulators.**]**

## 3. Information we collect

**Account and identity information:** name, email, password (stored hashed), business details, and —
where required for verification (KYC) — identity information you submit.

**Business and customer records you enter or import:** contacts and CRM data, deals and pipelines,
proposals, invoices, estimates, expenses and income entries, tasks, notes, and documents.

**Financial and bank data:** bookkeeping records you create, and — if you connect a bank account —
**bank transaction data retrieved through Plaid** (see Section 5).

**Communications data:** if you use O-Brain's messaging features, the content and metadata of emails
(including via connected Gmail accounts), SMS and voice calls (via Twilio), and video meetings and
their recordings/transcripts (via LiveKit).

**Calendar and scheduling data:** bookings, availability, and — if connected — Google Calendar events.

**AI interactions:** the prompts, documents, and business data you submit to O-Brain's AI features, and
the responses generated.

**Technical and usage data:** log data, device/browser information, IP address, and activity within the
platform (including a security audit log of events such as sign-in, consent, and data-deletion).

**Payment information:** processed by Stripe; OCIDM does not store full card numbers.

## 4. How we use information

We use information to: provide and operate the platform and its features; sync and categorize your
financial data for your bookkeeping; power AI features you choose to use; send transactional messages
and the communications you initiate; secure the platform and prevent fraud/abuse; provide support; meet
legal and contractual obligations; and improve the service. **[LEGAL REVIEW:** confirm the lawful basis
/ consent framing appropriate for PIPEDA (Canada) and applicable U.S. state laws, and whether any use
requires separate opt-in.**]** We do **not sell** your personal information. **[LEGAL REVIEW:** confirm
"sale"/"share" definitions under California's CCPA/CPRA and add a "Do Not Sell or Share" statement if
applicable.**]**

## 5. Bank and financial data (Plaid)

If you choose to connect a bank account, you authorize O-Brain to retrieve your **bank transaction
data through Plaid Inc.** We use this data **solely to power your own bookkeeping, categorization, and
financial reporting within your account.** We do **not sell, share, or repurpose** your bank data. Your
use of the connection is also subject to **Plaid's end-user privacy policy** (https://plaid.com/legal).
You may disconnect a bank connection at any time, which removes that connection and its associated
transaction data from your account. **[LEGAL REVIEW:** confirm this section against Plaid's MSA
Schedule 1 consent and data-use requirements, and against GLBA where applicable to consumer financial
data.**]**

## 6. Artificial intelligence features

O-Brain includes AI features (an assistant, document/receipt extraction, transcription, summaries, and
coaching). When you use them, the relevant business data is sent to **AI service providers acting on our
behalf** to generate a result for you. We do not use your data to train third-party public models, and
our providers are contractually restricted to processing it to provide the service. **[LEGAL REVIEW:**
confirm each AI subprocessor's data-use and training terms and disclose accordingly; confirm whether any
automated processing requires specific notice.**]**

## 7. Who we share information with

We share information with **service providers ("subprocessors") that operate parts of O-Brain on our
behalf**, only as needed to provide the service:

- **Plaid** — bank-transaction connectivity
- **Stripe / Stripe Connect** — payment processing
- **Twilio** — voice and SMS
- **LiveKit** — video meetings, recordings, transcription
- **Google** — Gmail and Google Calendar connections you authorize
- **AI providers** (e.g., for the assistant, extraction, and transcription) — to generate AI results
- **DreamHost and cloud storage providers** — to host the platform and store your files

We also share information: with **operators** where you are their client; when you direct us to (e.g.,
sharing a document or portal access); to comply with **law or valid legal process**; to protect rights,
safety, and security; and in connection with a **business transfer** (merger, acquisition, or sale).
**[LEGAL REVIEW:** confirm a complete, current subprocessor list is maintained and published, as several
laws and the Plaid MSA expect one.**]**

## 8. How we protect information

We maintain administrative, technical, and physical safeguards appropriate to the sensitivity of the
data, including encryption of data in transit, application-layer encryption of sensitive credentials and
tokens, role-based access controls enforced server-side, multi-factor authentication for sensitive
actions, and security audit logging. No method of transmission or storage is perfectly secure. Details
are set out in our Information Security Policy.

## 9. Data retention

We keep information for as long as needed to provide the service and for legitimate business and legal
purposes, then delete or irreversibly anonymize it. **[LEGAL REVIEW:** set specific retention periods
by data type — bookkeeping/financial records often have multi-year legal retention requirements in both
Canada and the U.S.; bank-transaction data retention should align with the Plaid MSA; define what
survives account deletion and why.**]**

## 10. Your privacy rights and choices

Subject to applicable law, you may: **access** the information we hold about you, request **correction**
of inaccurate information, request **deletion** of your data, **export** a copy of your data, and
**withdraw consent** (including disconnecting bank or other integrations). O-Brain provides in-product
tools to export and to delete your data. To exercise a right, use the in-product tools or contact us at
**support@ocidm.io**.

- **Canada (PIPEDA):** you have rights of access and correction and may contact the Office of the Privacy
  Commissioner of Canada. **[LEGAL REVIEW]**
- **United States — California (CCPA/CPRA):** you may have rights to know, delete, correct, and to opt
  out of "sale"/"sharing," and not to be discriminated against for exercising them. **[LEGAL REVIEW:**
  add the specific California disclosures and categories if you have California users; add other U.S.
  state disclosures (e.g., Virginia, Colorado) as applicable.**]**

If you are an **operator's client**, please direct these requests to the operator, who controls your
data.

## 11. Where your information is processed

O-Brain is hosted on servers located in the **United States** (DreamHost, US East / Virginia region),
and several subprocessors listed above are also located in the **United States**. If you are in Canada,
your information — **including bank-transaction data** — is **transferred to and processed in the United
States**, where it may be subject to U.S. laws, including lawful access by U.S. authorities. By using
O-Brain, you acknowledge this cross-border transfer. **[LEGAL REVIEW:** confirm the cross-border
transfer disclosure and any consent wording required under PIPEDA.**]**

## 12. Children

O-Brain is a business product and is not intended for individuals under 18. We do not knowingly collect
personal information from children. **[LEGAL REVIEW: confirm age threshold and any COPPA considerations.]**

## 13. Changes to this policy

We may update this policy. We will post the new version with an updated version number and effective
date, and — where required — notify you. Your consent records reference the policy version in effect when
you connected a service.

## 14. Contact us

Privacy questions or requests: **support@ocidm.io**
OC Interactive Digital Agency Corp., 203-762 Upper James St, Hamilton, ON L9C 3A2, Canada
**[LEGAL REVIEW: add a designated privacy contact / DPO if required.]**
`

export default function PrivacyPolicyPage() {
  return <LegalDocument content={CONTENT} />
}
