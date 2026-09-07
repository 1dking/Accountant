import { useTranslation } from 'react-i18next'
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

// French version of the same v1.0 — required for Quebec users (Charter of the
// French language, s. 55: contracts of adhesion must be drawn up in French).
// Keep the version number and effective date identical to CONTENT above.
const CONTENT_FR = `# Conditions d'utilisation d'O-Brain

**Version 1.0** · Date d'entrée en vigueur : 1er juillet 2026
OC Interactive Digital Agency Corp. (« OCIDM », « nous »)
203-762 Upper James St, Hamilton (Ontario) L9C 3A2, Canada · support@ocidm.io

## 1. Entente

En créant un compte ou en utilisant O-Brain, vous acceptez les présentes conditions ainsi que notre
Politique de confidentialité. Si vous utilisez O-Brain au nom d'une entreprise, vous déclarez être
autorisé à engager cette entreprise.

## 2. Le service

O-Brain est une plateforme tout-en-un de gestion d'entreprise comprenant un CRM, la facturation et les
propositions, la tenue de livres et la comptabilité, la synchronisation des transactions bancaires (via
Plaid), la téléphonie et la messagerie (via Twilio), les visioconférences (via LiveKit), la planification,
des outils de documents et de fichiers, l'automatisation, des fonctions d'IA, un portail client et, pour
les forfaits admissibles, des capacités de marque blanche et de comptes multiples (« opérateur »). Nous
pouvons mettre à jour, ajouter ou retirer des fonctions au fil du temps.

## 3. Comptes et admissibilité

Vous devez avoir au moins 18 ans et fournir des renseignements exacts. Vous êtes responsable de votre
compte, de vos utilisateurs et de la protection de vos identifiants. Nous exigeons l'authentification
multifacteur pour certaines actions sensibles, dont la connexion d'un compte bancaire et l'accès aux
données financières. Vous êtes responsable de toute activité effectuée sous votre compte.

## 4. Forfaits, facturation et paiements

Les forfaits payants sont facturés par abonnement (mensuel ou annuel) aux prix affichés au moment de
l'achat, en dollars américains (USD). Les abonnements se renouvellent automatiquement à la fin de chaque
période de facturation, sauf annulation avant la date de renouvellement. Vous pouvez annuler en tout temps;
l'annulation prend effet à la fin de la période de facturation en cours. Les frais ne sont pas
remboursables, sauf lorsque la loi l'exige. Vous êtes responsable des taxes applicables. Certaines
fonctions sont facturées à l'utilisation (par exemple l'IA, la téléphonie, les SMS, la voix et les
connexions bancaires); l'utilisation au-delà des allocations incluses peut entraîner des frais
supplémentaires, tels que divulgués. Les paiements sont traités par Stripe; lorsque vous percevez des
paiements de vos propres clients, les fonds transitent par votre propre compte Stripe connecté.

## 5. Opérateurs, sous-comptes et revente (marque blanche)

Si votre forfait le permet, vous pouvez exploiter O-Brain au nom de vos propres clients sous votre propre
marque et leur en revendre l'accès. Dans ce cas, vous êtes la partie responsable envers vos clients : vous
devez avoir votre propre entente et votre propre politique de confidentialité avec eux, obtenir les
consentements requis, fixer vos propres prix, gérer leur facturation et leur soutien, et respecter toutes
les lois applicables. Vous êtes responsable de l'utilisation de la plateforme par vos clients et vous vous
engagez à l'utiliser, ainsi que toute donnée obtenue par son entremise, uniquement au bénéfice de vos
clients.

## 6. Services de tiers

O-Brain intègre des services de tiers (dont Plaid, Twilio, Stripe, LiveKit, Google et des fournisseurs
d'IA). Votre utilisation de ces intégrations est aussi assujettie aux conditions de ces fournisseurs, et
nous ne sommes pas responsables des services de tiers. Les connexions bancaires sont fournies via Plaid et
sont assujetties aux conditions d'utilisation et à la politique de confidentialité de Plaid.

## 7. Vos données et votre contenu

Entre vous et OCIDM, vous êtes propriétaire des données et du contenu que vous placez dans O-Brain. Vous
nous accordez les droits limités nécessaires pour les héberger, les traiter et les afficher afin de fournir
le service, y compris la transmission des données pertinentes à des sous-traitants (comme les fournisseurs
d'IA) pour offrir les fonctions que vous utilisez. Vous êtes responsable de détenir les droits et
consentements requis pour les données que vous saisissez, y compris les renseignements de vos clients.

## 8. Utilisation acceptable

Vous n'utiliserez pas O-Brain pour : enfreindre la loi; envoyer des messages illégaux, non sollicités ou
indésirables, ou violer les règles de télémarketing et anti-pourriel (dont la LCAP au Canada, la TCPA et la
loi CAN-SPAM aux États-Unis, ainsi que les exigences des opérateurs et A2P pour les SMS); porter atteinte
aux droits d'autrui; téléverser des logiciels malveillants; tenter de compromettre la sécurité ou d'accéder
aux données d'autres locataires; ou revendre ou détourner des données de tiers (y compris des données
bancaires) hors de l'usage permis. Nous pouvons suspendre les comptes présentant un risque de sécurité,
juridique, de fraude ou d'abus.

## 9. Fonctions d'IA

Les fonctions d'IA génèrent des résultats qui peuvent être inexacts ou incomplets. Vous êtes responsable de
réviser les résultats de l'IA avant de vous y fier, particulièrement en matière financière, comptable ou
juridique. Les fonctions d'IA sont des outils, non des conseils professionnels.

## 10. Disponibilité du service et modifications

Nous visons un service fiable, mais ne garantissons pas une disponibilité ininterrompue. Nous pouvons
modifier ou retirer des fonctions, avec préavis lorsque cela est raisonnablement possible.

## 11. Exclusions de garantie

Le service est fourni « tel quel » et « selon la disponibilité », sans garantie d'aucune sorte dans toute
la mesure permise par la loi, y compris les garanties de qualité marchande, d'adaptation à un usage
particulier et d'absence de contrefaçon. O-Brain ne fournit pas de conseils comptables, fiscaux, juridiques
ou financiers.

## 12. Limitation de responsabilité

Dans toute la mesure permise par la loi, OCIDM ne sera pas responsable des dommages indirects, accessoires,
particuliers, consécutifs, exemplaires ou punitifs, ni des pertes de profits, de revenus ou de données. La
responsabilité globale totale d'OCIDM découlant des présentes conditions ou du service ne dépassera pas le
plus élevé des montants suivants : le montant que vous avez payé à OCIDM au cours des douze (12) mois
précédant l'événement à l'origine de la responsabilité, ou cent dollars (100 $ CA).

## 13. Résiliation

Vous pouvez annuler en tout temps. Nous pouvons suspendre ou résilier votre compte en cas de manquement aux
présentes conditions, de non-paiement ou de risque juridique ou de sécurité. À la résiliation, votre droit
d'utiliser le service prend fin; vous pouvez exporter vos données avant la résiliation, et nous supprimerons
ou anonymiserons les données comme décrit dans la Politique de confidentialité, sous réserve des obligations
légales de conservation.

## 14. Droit applicable et différends

Les présentes conditions sont régies par les lois de la province de l'Ontario et les lois fédérales du
Canada qui s'y appliquent, sans égard aux règles de conflit de lois. Vous et OCIDM reconnaissez la
compétence exclusive des tribunaux situés dans la province de l'Ontario, au Canada, pour tout différend
découlant des présentes conditions ou du service.

## 15. Modifications des présentes conditions

Nous pouvons mettre à jour les présentes conditions de temps à autre et publierons la nouvelle version
avec un numéro de version et une date d'entrée en vigueur à jour. La poursuite de l'utilisation après
l'entrée en vigueur des modifications vaut acceptation de celles-ci.

## 16. Nous joindre

OC Interactive Digital Agency Corp.
203-762 Upper James St, Hamilton (Ontario) L9C 3A2, Canada · support@ocidm.io
`

export default function TermsPage() {
  const { i18n } = useTranslation()
  return <LegalDocument content={i18n.language === 'fr-CA' ? CONTENT_FR : CONTENT} />
}
