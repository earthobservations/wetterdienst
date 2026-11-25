// The languages of the app (GH-4106). One table for the browser and the server: `nuxt.config.ts` hands it to
// `@nuxtjs/i18n`, which chooses the language of the page at startup, and the server writes the head of the shell
// in the language that choice will be (`server/utils/seoHead.ts`). `nuxt.config.ts` reads this file before Nuxt
// exists, so it imports nothing of the app; the rule that picks a language is in `shared/utils/language.ts`.

export interface AppLocale {
  /** The code of the locale: the value of the `wd_lang` cookie and the `lang` of `<html>` */
  code: string
  /** The BCP 47 tag the browser's languages are matched against, and `og:locale` is written from */
  language: string
  /** The name of the language, in that language */
  name: string
  /** The file of its catalog in `i18n/locales` */
  file: string
}

/** The locales of the app, in the order of the language menu. */
export const LOCALES = [
  { code: 'de', language: 'de-DE', name: 'Deutsch', file: 'de.json' },
  { code: 'en', language: 'en-GB', name: 'English', file: 'en.json' },
  { code: 'fr', language: 'fr-FR', name: 'Français', file: 'fr.json' },
  { code: 'es', language: 'es-ES', name: 'Español', file: 'es.json' },
  { code: 'it', language: 'it-IT', name: 'Italiano', file: 'it.json' },
  { code: 'pl', language: 'pl-PL', name: 'Polski', file: 'pl.json' },
  { code: 'nl', language: 'nl-NL', name: 'Nederlands', file: 'nl.json' },
  { code: 'cs', language: 'cs-CZ', name: 'Čeština', file: 'cs.json' },
  { code: 'da', language: 'da-DK', name: 'Dansk', file: 'da.json' },
  { code: 'lb', language: 'lb-LU', name: 'Lëtzebuergesch', file: 'lb.json' },
  { code: 'de-hh', language: 'de-DE', name: 'Hamburgisch', file: 'de-hh.json' },
] as const satisfies readonly AppLocale[]

export type LocaleCode = typeof LOCALES[number]['code']

/** The language of a visitor whose browser asks for none that the app has. */
export const DEFAULT_LOCALE: LocaleCode = 'de'

/** The cookie that remembers the language a visitor picked. */
export const LANGUAGE_COOKIE = 'wd_lang'

/**
 * Whether a text is the code of a locale of the app, as `@nuxtjs/i18n` takes a cookie: exactly.
 *
 * @param value Any value, such as a cookie
 * @returns True for `de`, `en`, `de-hh` and the other codes of `LOCALES`
 */
export function isLocaleCode(value: unknown): value is LocaleCode {
  return typeof value === 'string' && LOCALES.some(locale => locale.code === value)
}
