import { withData } from '~/utils/format'

/**
 * The language to hand `Intl` and `toLocale*String` for the active locale: its language tag (`en-GB`, `de-DE`), not the
 * app's code (`en`, `lb`, `de-hh`), and one the browser has data for. Chrome has none for Luxembourgish, so a bare `lb`
 * would be written in the system's language. A locale with no tag is its code.
 */
export function useFormatLanguage() {
  const { locale, localeProperties } = useI18n()
  return computed(() => withData(localeProperties.value.language ?? locale.value, Intl.DateTimeFormat.supportedLocalesOf))
}
