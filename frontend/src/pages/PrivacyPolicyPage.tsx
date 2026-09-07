import { useTranslation } from 'react-i18next'
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

// French version of the same v1.1 (Quebec: Charter of the French language;
// Law 25 privacy notices must be available in French). Same version number
// and effective date as CONTENT — consent records reference the version, so
// the two texts must always be bumped together.
const CONTENT_FR = `# Politique de confidentialité d'O-Brain

**Version 1.1** · Date d'entrée en vigueur : 26 juillet 2026
OC Interactive Digital Agency Corp. (« OCIDM », « nous »)
203-762 Upper James St, Hamilton (Ontario) L9C 3A2, Canada · support@ocidm.io

La présente politique explique quels renseignements la plateforme O-Brain recueille, comment nous les
utilisons, avec qui nous les partageons, ainsi que les choix et les droits dont vous disposez. Elle
s'applique aux utilisateurs au Canada et aux États-Unis.

## 1. Qui nous sommes

OCIDM exploite O-Brain, une plateforme tout-en-un de gestion d'entreprise (CRM, facturation et
propositions, tenue de livres et comptabilité, synchronisation des transactions bancaires, téléphonie et
messagerie, visioconférences, planification, outils de documents, stockage de fichiers, automatisation,
assistant IA et portail client).

## 2. Opérateurs et leurs clients

O-Brain peut être utilisé directement par une entreprise, ou fourni par un opérateur (comme un comptable
ou une agence) qui gère des comptes au nom de ses propres clients sous sa propre marque. Pour le compte
d'une entreprise et les données qu'elle y saisit, OCIDM agit comme responsable du traitement de ces
données. Lorsqu'un opérateur utilise O-Brain pour servir ses clients, c'est l'opérateur qui détermine
comment les données de ses clients sont traitées, et OCIDM traite ces données pour le compte de
l'opérateur, à titre de sous-traitant. Dans ce cas, la politique de confidentialité de l'opérateur régit
les données de ses clients, et ceux-ci doivent adresser leurs demandes relatives à la vie privée à
l'opérateur.

## 3. Renseignements que nous recueillons

**Renseignements de compte et d'identité :** nom, courriel, mot de passe (conservé haché), coordonnées de
l'entreprise et, lorsque requis pour vérification, les renseignements d'identité que vous fournissez.

**Dossiers d'affaires et de clients que vous saisissez ou importez :** contacts et données du CRM, affaires
et pipelines, propositions, factures, devis, dépenses et revenus, tâches, notes et documents.

**Données financières et bancaires :** les registres comptables que vous créez et, si vous connectez un
compte bancaire, les données de transactions bancaires obtenues par l'entremise de Plaid (voir la section 5).

**Données de communication :** si vous utilisez les fonctions de messagerie d'O-Brain, le contenu et les
métadonnées des courriels (y compris via les comptes Gmail connectés), des SMS et des appels vocaux (via
Twilio), ainsi que des visioconférences et de leurs enregistrements et transcriptions (via LiveKit).

**Données de calendrier et de planification :** réservations, disponibilités et, si connecté, événements
Google Agenda.

**Interactions avec l'IA :** les requêtes, documents et données d'entreprise que vous soumettez aux fonctions
d'IA d'O-Brain, et les réponses générées.

**Données techniques et d'utilisation :** données de journalisation, renseignements sur l'appareil et le
navigateur, adresse IP et activité dans la plateforme, y compris un journal d'audit de sécurité des
événements tels que la connexion, le consentement et la suppression de données.

**Renseignements de paiement :** traités par Stripe; OCIDM ne conserve pas les numéros de carte complets.

## 4. Comment nous utilisons les renseignements

Nous utilisons les renseignements pour fournir et exploiter la plateforme et ses fonctions; synchroniser et
catégoriser vos données financières pour votre tenue de livres; alimenter les fonctions d'IA que vous
choisissez d'utiliser; envoyer des messages transactionnels et les communications que vous lancez; sécuriser
la plateforme et prévenir la fraude et les abus; offrir du soutien; respecter nos obligations légales et
contractuelles; et améliorer le service. Nous traitons vos renseignements pour exécuter notre contrat avec
vous, avec votre consentement (que vous pouvez retirer), pour respecter nos obligations légales et pour des
intérêts commerciaux légitimes comme la sécurisation du service. Nous ne vendons pas vos renseignements
personnels.

## 5. Données bancaires et financières (Plaid)

Si vous choisissez de connecter un compte bancaire, vous autorisez O-Brain à récupérer vos données de
transactions bancaires par l'entremise de Plaid Inc. Nous utilisons ces données uniquement pour alimenter
votre propre tenue de livres, votre catégorisation et vos rapports financiers dans votre compte. Nous ne
vendons, ne partageons ni ne réutilisons vos données bancaires à d'autres fins. Votre utilisation de la
connexion est aussi assujettie à la politique de confidentialité de Plaid (https://plaid.com/legal). Vous
pouvez déconnecter une connexion bancaire en tout temps, ce qui retire cette connexion et les données de
transactions associées de votre compte, sous réserve des exigences de conservation de la section 9.

## 6. Fonctions d'intelligence artificielle

O-Brain comprend des fonctions d'IA (un assistant, l'extraction de documents et de reçus, la transcription,
des résumés et du coaching). Lorsque vous les utilisez, les données d'entreprise pertinentes sont
transmises à des fournisseurs de services d'IA agissant pour notre compte afin de générer un résultat pour
vous. Nous n'utilisons pas vos données pour entraîner des modèles publics de tiers, et nos fournisseurs sont
contractuellement limités à les traiter pour fournir le service.

## 7. Avec qui nous partageons les renseignements

Nous partageons des renseignements avec des fournisseurs de services (« sous-traitants ») qui exploitent des
parties d'O-Brain pour notre compte, uniquement dans la mesure nécessaire pour fournir le service :

- Plaid, pour la connectivité des transactions bancaires
- Stripe et Stripe Connect, pour le traitement des paiements
- Twilio, pour la voix et les SMS
- LiveKit, pour les visioconférences, les enregistrements et la transcription
- Google, pour les connexions Gmail et Google Agenda que vous autorisez
- Des fournisseurs d'IA, pour générer les résultats d'IA
- DreamHost et des fournisseurs de stockage infonuagique, pour héberger la plateforme et conserver vos fichiers

Nous partageons aussi des renseignements avec les opérateurs dont vous êtes le client; lorsque vous nous le
demandez (par exemple en partageant un document ou un accès au portail); pour nous conformer à la loi ou à
une procédure judiciaire valide; pour protéger les droits, la sûreté et la sécurité; et dans le cadre d'un
transfert d'entreprise (fusion, acquisition ou vente).

## 8. Comment nous protégeons les renseignements

Nous maintenons des mesures de protection administratives, techniques et physiques adaptées à la
sensibilité des données, notamment :

- Le chiffrement des données en transit avec TLS 1.2 ou supérieur
- Le chiffrement au repos des données financières de consommateurs obtenues de Plaid, ainsi que des
  identifiants et jetons d'accès sensibles, au niveau applicatif
- Une authentification multifacteur résistante à l'hameçonnage (clés d'accès / WebAuthn) et des codes
  d'application d'authentification, exigés avant de connecter un compte bancaire ou d'accéder aux données
  financières
- Des contrôles d'accès fondés sur les rôles appliqués côté serveur, avec des dossiers privés par défaut
- Une analyse automatisée des vulnérabilités de nos logiciels et dépendances, avec des correctifs appliqués
  rapidement
- Un journal d'audit de sécurité des événements d'accès, de consentement et de suppression de données

Aucune méthode de transmission ou de stockage n'est parfaitement sécuritaire, mais nous protégeons vos
renseignements selon les pratiques actuelles reconnues de l'industrie.

## 9. Conservation des données

Nous conservons les renseignements personnels tant que votre compte est actif et aussi longtemps que
nécessaire pour fournir le service. Les registres financiers, de facturation et comptables sont conservés
pendant les périodes exigées par les lois fiscales et comptables applicables (généralement au moins six ans
au Canada et jusqu'à sept ans aux États-Unis), même après la fermeture du compte, après quoi ils sont
supprimés ou irréversiblement anonymisés. Les données de connexion bancaire sont supprimées lorsque vous
déconnectez un compte ou fermez votre compte, sous réserve de ces exigences légales de conservation. Vous
pouvez demander la suppression de vos données en tout temps, et nous y donnerons suite sauf lorsque la
conservation est exigée par la loi.

Nous révisons ces périodes de conservation, ainsi que les pratiques de suppression décrites dans la présente
section, au moins une fois par année et chaque fois que nos pratiques changent, afin de confirmer qu'elles
demeurent exactes et conformes aux lois applicables en matière de protection des renseignements personnels
(voir la section 13).

## 10. Vos droits et vos choix en matière de vie privée

Sous réserve de la loi applicable, vous pouvez accéder aux renseignements que nous détenons à votre sujet,
demander la correction de renseignements inexacts, demander la suppression de vos données, exporter une
copie de vos données et retirer votre consentement (y compris en déconnectant les intégrations bancaires ou
autres). O-Brain offre des outils intégrés pour exporter et supprimer vos données. Pour exercer un droit,
utilisez les outils intégrés ou écrivez-nous à support@ocidm.io.

**Canada (LPRPDE et Loi 25 au Québec) :** vous avez des droits d'accès et de rectification et pouvez
communiquer avec le Commissariat à la protection de la vie privée du Canada ou, au Québec, avec la
Commission d'accès à l'information.

**États-Unis, Californie (CCPA/CPRA) :** si vous résidez en Californie, vous avez le droit de savoir quels
renseignements personnels nous recueillons et comment nous les utilisons, d'y accéder et de les supprimer,
de corriger les renseignements inexacts et de refuser la « vente » ou le « partage » de renseignements
personnels. Nous ne vendons ni ne partageons vos renseignements personnels au sens de la CCPA, et nous ne
vous pénaliserons pas pour avoir exercé vos droits. Pour exercer ces droits, écrivez à support@ocidm.io.

Si vous êtes le client d'un opérateur, veuillez adresser ces demandes à l'opérateur, qui contrôle vos
données.

## 11. Où vos renseignements sont traités

O-Brain est hébergé sur des serveurs situés aux États-Unis (DreamHost, région US East / Virginie), et
plusieurs des sous-traitants énumérés ci-dessus sont aussi situés aux États-Unis. Si vous êtes au Canada,
vos renseignements, y compris les données de transactions bancaires, sont transférés et traités aux
États-Unis, où ils peuvent être assujettis aux lois américaines, y compris l'accès légal par les autorités
américaines. En utilisant O-Brain, vous reconnaissez ce transfert transfrontalier.

## 12. Enfants

O-Brain est un produit destiné aux entreprises et ne s'adresse pas aux personnes de moins de 18 ans. Nous
ne recueillons pas sciemment de renseignements personnels auprès d'enfants.

## 13. Révision et modification de la présente politique

Nous révisons la présente politique au moins **une fois par année**, et chaque fois qu'un changement
important survient dans la façon dont nous traitons les renseignements, par exemple : un nouveau fournisseur
de services, une nouvelle catégorie de renseignements recueillis, un nouveau territoire desservi ou une
modification d'une période de conservation. Chaque révision confirme que la présente politique reflète
toujours nos pratiques réelles, y compris les périodes de conservation de la section 9, les mesures de
protection de la section 8 et les fournisseurs de services énumérés à la section 7. Les révisions sont
consignées avec la date et le nom du réviseur.

Nous pouvons mettre à jour la présente politique de temps à autre. Nous publierons la nouvelle version avec
un numéro de version et une date d'entrée en vigueur à jour et, lorsque requis, nous vous en aviserons. Vos
dossiers de consentement font référence à la version de la politique en vigueur au moment où vous avez
connecté un service; une révision ultérieure ne modifie donc pas ce que vous avez précédemment accepté.

## 14. Nous joindre

Questions ou demandes relatives à la vie privée : support@ocidm.io
OC Interactive Digital Agency Corp., 203-762 Upper James St, Hamilton (Ontario) L9C 3A2, Canada
`

export default function PrivacyPolicyPage() {
  const { i18n } = useTranslation()
  return <LegalDocument content={i18n.language === 'fr-CA' ? CONTENT_FR : CONTENT} />
}
