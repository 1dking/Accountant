import LegalDocument from '@/components/LegalDocument'

// OCIDM O-Brain Privacy Policy — v1.1 (final; v1.0 + the periodic-review
// commitment in §9/§13). The version string is mirrored in
// backend/app/core/legal.py (PRIVACY_POLICY_VERSION); every Plaid consent record
// stamps the version that was in effect when the user connected, so bump BOTH
// together and never edit a version in place once consents reference it.
const CONTENT = `# O-Brain Privacy Policy

**Version 1.1** · Effective date: July 26, 2026
OC Interactive Digital Agency Corp. ("OCIDM," "we," "us")
203-762 Upper James St, Hamilton, ON L9C 3A2, Canada · support@ocidm.io

This Privacy Policy explains what information the O-Brain platform collects, how we use it, who we
share it with, and the choices and rights you have. It applies to users in Canada and the United States.

## 1. Who we are

OCIDM operates O-Brain, an all-in-one business management platform (CRM, invoicing and proposals,
bookkeeping and accounting, bank-transaction sync, phone and messaging, video meetings, scheduling,
document tools, file storage, automation, an AI assistant, and a client portal).

## 2. Operators and their clients

O-Brain can be used directly by a business, or provided by an operator (such as an accountant or agency)
who manages accounts on behalf of their own clients under their own branding. For a business's own
account and the data it enters, OCIDM acts as the controller of that data. When an operator uses O-Brain
to serve their clients, the operator determines how their clients' data is handled and OCIDM processes
that data on the operator's behalf as a processor. In that case, the operator's own privacy policy governs
their clients' data, and those clients should direct privacy requests to the operator.

## 3. Information we collect

**Account and identity information:** name, email, password (stored hashed), business details, and, where
required for verification, identity information you submit.

**Business and customer records you enter or import:** contacts and CRM data, deals and pipelines,
proposals, invoices, estimates, expenses and income entries, tasks, notes, and documents.

**Financial and bank data:** bookkeeping records you create, and, if you connect a bank account, bank
transaction data retrieved through Plaid (see Section 5).

**Communications data:** if you use O-Brain's messaging features, the content and metadata of emails
(including via connected Gmail accounts), SMS and voice calls (via Twilio), and video meetings and their
recordings and transcripts (via LiveKit).

**Calendar and scheduling data:** bookings, availability, and, if connected, Google Calendar events.

**AI interactions:** the prompts, documents, and business data you submit to O-Brain's AI features, and
the responses generated.

**Technical and usage data:** log data, device and browser information, IP address, and activity within
the platform, including a security audit log of events such as sign-in, consent, and data deletion.

**Payment information:** processed by Stripe; OCIDM does not store full card numbers.

## 4. How we use information

We use information to provide and operate the platform and its features; sync and categorize your
financial data for your bookkeeping; power AI features you choose to use; send transactional messages and
the communications you initiate; secure the platform and prevent fraud and abuse; provide support; meet
legal and contractual obligations; and improve the Service. We process your information to perform our
contract with you, with your consent (which you may withdraw), to comply with legal obligations, and for
legitimate business interests such as securing the Service. We do not sell your personal information.

## 5. Bank and financial data (Plaid)

If you choose to connect a bank account, you authorize O-Brain to retrieve your bank transaction data
through Plaid Inc. We use this data solely to power your own bookkeeping, categorization, and financial
reporting within your account. We do not sell, share, or repurpose your bank data. Your use of the
connection is also subject to Plaid's end-user privacy policy (https://plaid.com/legal). You may
disconnect a bank connection at any time, which removes that connection and its associated transaction
data from your account, subject to the retention requirements in Section 9.

## 6. Artificial intelligence features

O-Brain includes AI features (an assistant, document and receipt extraction, transcription, summaries,
and coaching). When you use them, the relevant business data is sent to AI service providers acting on
our behalf to generate a result for you. We do not use your data to train third-party public models, and
our providers are contractually restricted to processing it to provide the service.

## 7. Who we share information with

We share information with service providers ("subprocessors") that operate parts of O-Brain on our
behalf, only as needed to provide the service:

- Plaid, for bank-transaction connectivity
- Stripe and Stripe Connect, for payment processing
- Twilio, for voice and SMS
- LiveKit, for video meetings, recordings, and transcription
- Google, for Gmail and Google Calendar connections you authorize
- AI providers, to generate AI results
- DreamHost and cloud storage providers, to host the platform and store your files

We also share information with operators where you are their client; when you direct us to (for example,
sharing a document or portal access); to comply with law or valid legal process; to protect rights,
safety, and security; and in connection with a business transfer (merger, acquisition, or sale).

## 8. How we protect information

We maintain administrative, technical, and physical safeguards appropriate to the sensitivity of the
data, including:

- Encryption of data in transit using TLS 1.2 or higher
- Encryption at rest of consumer financial data retrieved from Plaid, and of sensitive credentials and
  access tokens, at the application layer
- Phishing-resistant multi-factor authentication (passkeys / WebAuthn) and authenticator-app codes,
  required before connecting a bank account or accessing financial data
- Role-based access controls enforced on the server, with records private by default
- Automated vulnerability scanning of our software and dependencies, with timely patching
- A security audit log of access, consent, and data-deletion events

No method of transmission or storage is perfectly secure, but we work to protect your information using
current, industry-standard practices.

## 9. Data retention

We retain personal information for as long as your account is active and as needed to provide the
Service. Financial, invoicing, and bookkeeping records are retained for the periods required by
applicable tax and accounting laws (generally at least six years in Canada and up to seven years in the
United States), even after account closure, after which they are deleted or irreversibly anonymized. Bank
connection data is deleted when you disconnect an account or close your account, subject to these legal
retention requirements. You may request deletion of your data at any time, and we will honor it except
where retention is legally required.

We review these retention periods, and the deletion practices described in this section, at least
annually and whenever our practices change, to confirm they remain accurate and compliant with
applicable data privacy laws (see Section 13).

## 10. Your privacy rights and choices

Subject to applicable law, you may access the information we hold about you, request correction of
inaccurate information, request deletion of your data, export a copy of your data, and withdraw consent
(including disconnecting bank or other integrations). O-Brain provides in-product tools to export and
delete your data. To exercise a right, use the in-product tools or contact us at support@ocidm.io.

**Canada (PIPEDA):** you have rights of access and correction and may contact the Office of the Privacy
Commissioner of Canada.

**United States, California (CCPA/CPRA):** if you are a California resident, you have the right to know
what personal information we collect and how we use it, to access and delete it, to correct inaccurate
information, and to opt out of the "sale" or "sharing" of personal information. We do not sell or share
your personal information as those terms are defined under the CCPA, and we will not discriminate against
you for exercising your rights. To exercise these rights, contact support@ocidm.io.

If you are an operator's client, please direct these requests to the operator, who controls your data.

## 11. Where your information is processed

O-Brain is hosted on servers located in the United States (DreamHost, US East / Virginia region), and
several subprocessors listed above are also located in the United States. If you are in Canada, your
information, including bank-transaction data, is transferred to and processed in the United States, where
it may be subject to U.S. laws, including lawful access by U.S. authorities. By using O-Brain, you
acknowledge this cross-border transfer.

## 12. Children

O-Brain is a business product and is not intended for individuals under 18. We do not knowingly collect
personal information from children.

## 13. Review of, and changes to, this policy

We review this policy at least **annually**, and additionally whenever there is a material change to how
we handle information, for example: a new service provider, a new category of information collected, a
new jurisdiction we serve, or a change to a retention period. Each review confirms that this policy still
reflects our actual practices, including the retention periods in Section 9, the safeguards in Section 8,
and the service providers listed in Section 7. Reviews are recorded with the date and reviewer.

We may update this policy from time to time. We will post the new version with an updated version number
and effective date, and, where required, notify you. Your consent records reference the policy version in
effect when you connected a service, so a later revision does not change what you previously agreed to.

## 14. Contact us

Privacy questions or requests: support@ocidm.io
OC Interactive Digital Agency Corp., 203-762 Upper James St, Hamilton, ON L9C 3A2, Canada
`

export default function PrivacyPolicyPage() {
  return <LegalDocument content={CONTENT} />
}
