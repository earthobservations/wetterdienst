/**
 * Supported UI languages with their display name.
 *
 * Keep this list in sync with the `locales` array in `nuxt.config.ts` and the
 * catalogs in `i18n/locales/*.json`. Used by the language pickers in the
 * settings popup and the settings page.
 */
export interface LanguageOption {
  value: string
  name: string
}

export const LANGUAGES: LanguageOption[] = [
  { value: 'de', name: 'Deutsch' },
  { value: 'en', name: 'English' },
  { value: 'fr', name: 'Français' },
  { value: 'es', name: 'Español' },
  { value: 'it', name: 'Italiano' },
  { value: 'pl', name: 'Polski' },
  { value: 'nl', name: 'Nederlands' },
  { value: 'cs', name: 'Čeština' },
  { value: 'da', name: 'Dansk' },
  { value: 'lb', name: 'Lëtzebuergesch' },
  { value: 'de-hh', name: 'Hamburgisch' },
]

/** Items for a USelect/USelectMenu: "Deutsch" with the locale code as value. */
export function languageSelectItems() {
  return LANGUAGES.map(l => ({ label: l.name, value: l.value }))
}
