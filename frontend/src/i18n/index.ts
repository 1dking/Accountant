/**
 * i18n bootstrap — react-i18next with en (default) and fr-CA.
 *
 * Why stored-preference, not URL-locale: `featureForPath(location.pathname)`
 * in lib/features.ts gates modules on the raw path, and 101 routes are flat
 * English slugs. A `/fr` prefix would break that gate everywhere. The user's
 * choice lives in localStorage('locale') — the same pre-paint pattern
 * index.html already uses for 'theme' — and is mirrored onto <html lang>.
 *
 * Namespaces are per feature area so a page only loads what it renders.
 * New strings go here first; the ~2,400 legacy strings are bulk-keyed in
 * sprint 6 (fr-CA fill). Bill 96 s.52.1 requires the French UI before Quebec
 * launch, so every new user-facing string from sprint 1 on is keyed.
 */
import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

import enCommon from './locales/en/common.json'
import enTax from './locales/en/tax.json'
import enPayroll from './locales/en/payroll.json'
import frCommon from './locales/fr-CA/common.json'
import frTax from './locales/fr-CA/tax.json'
import frPayroll from './locales/fr-CA/payroll.json'

export const SUPPORTED_LOCALES = ['en', 'fr-CA'] as const
export type Locale = (typeof SUPPORTED_LOCALES)[number]
export const LOCALE_STORAGE_KEY = 'locale'

export const resources = {
  en: { common: enCommon, tax: enTax, payroll: enPayroll },
  'fr-CA': { common: frCommon, tax: frTax, payroll: frPayroll },
} as const

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'en',
    supportedLngs: [...SUPPORTED_LOCALES],
    ns: ['common', 'tax', 'payroll'],
    defaultNS: 'common',
    detection: {
      // Explicit choice first; browser language only as a first-run default.
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: LOCALE_STORAGE_KEY,
      caches: ['localStorage'],
      // Map fr, fr-FR, fr-* to fr-CA; everything else falls to en.
      convertDetectedLanguage: (lng: string) => (lng.toLowerCase().startsWith('fr') ? 'fr-CA' : 'en'),
    },
    interpolation: { escapeValue: false }, // React already escapes
    returnNull: false,
  })

// Keep <html lang> honest for screen readers, hyphenation, and Bill 96 audits.
function syncHtmlLang(lng: string) {
  try {
    document.documentElement.lang = lng
  } catch {
    /* SSR / tests */
  }
}
syncHtmlLang(i18n.language)
i18n.on('languageChanged', syncHtmlLang)

export function setLocale(locale: Locale) {
  return i18n.changeLanguage(locale)
}

export default i18n
