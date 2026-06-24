/**
 * Supported UI languages with their display name and flag.
 *
 * Keep this list in sync with the `locales` array in `nuxt.config.ts` and the
 * catalogs in `i18n/locales/*.json`. Used by the language pickers in the
 * settings popup and the settings page.
 */
export interface LanguageOption {
  value: string
  name: string
  flag: string
}

export const LANGUAGES: LanguageOption[] = [
  { value: 'de', name: 'Deutsch', flag: '🇩🇪' },
  { value: 'en', name: 'English', flag: '🇬🇧' },
  { value: 'fr', name: 'Français', flag: '🇫🇷' },
  { value: 'es', name: 'Español', flag: '🇪🇸' },
  { value: 'it', name: 'Italiano', flag: '🇮🇹' },
  { value: 'pl', name: 'Polski', flag: '🇵🇱' },
  { value: 'nl', name: 'Nederlands', flag: '🇳🇱' },
  { value: 'cs', name: 'Čeština', flag: '🇨🇿' },
  { value: 'da', name: 'Dansk', flag: '🇩🇰' },
  { value: 'lb', name: 'Lëtzebuergesch', flag: '🇱🇺' },
  { value: 'de-hh', name: 'Hamburgisch', flag: '⚓' },
]

/** Items for a USelect/USelectMenu: "🇩🇪 Deutsch" with the locale code as value. */
export function languageSelectItems() {
  return LANGUAGES.map(l => ({ label: `${l.flag} ${l.name}`, value: l.value }))
}
