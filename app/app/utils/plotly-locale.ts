import { plotlyDateLocale } from './format'

// The language of a Plotly chart (GH-3625). Plotly's basic bundle writes English: the names of the buttons
// of its modebar ("Zoom", "Pan", "Download plot as a PNG") and of the weekdays and months of a date axis.
// Plotly's own translations (`plotly.js-locales`, one small module for each language, loaded when a
// chart is drawn in it) and the names Intl has for the dates make a chart say them in the language of the
// page. One helper for every chart of the app: `{ ...(await plotlyLocaleConfig(locale, language)) }` in a config.

/** What a Plotly locale holds that the app uses: the buttons' and the hover texts' names, and the dates' */
export interface PlotlyLocale {
  dictionary?: Record<string, string>
  format: ReturnType<typeof plotlyDateLocale>['format']
}

/** The two keys of a Plotly config that make a chart speak a language */
export interface PlotlyLocaleConfig {
  locale: string
  locales: Record<string, PlotlyLocale>
}

type Dictionary = Record<string, string>

// The languages Plotly has a translation of the buttons in, among the app's locales (`code` in nuxt.config.ts).
// Each is its own chunk, so a page in German does not load the others. Polish and Danish are not here: Plotly
// ships their date names only, as an empty dictionary (their dates are Intl's), so there is nothing to load,
// and their buttons stay English; Dutch has a part of its texts.
const DICTIONARIES: Record<string, () => Promise<{ default: { dictionary: Dictionary } }>> = {
  de: () => import('plotly.js-locales/de'),
  fr: () => import('plotly.js-locales/fr'),
  es: () => import('plotly.js-locales/es'),
  it: () => import('plotly.js-locales/it'),
  nl: () => import('plotly.js-locales/nl'),
  cs: () => import('plotly.js-locales/cs'),
}

// Plotly has no translation of Luxembourgish, and none of Hamburg's German: the nearest it has is German
const FALLBACKS: Record<string, string> = { 'lb': 'de', 'de-hh': 'de' }

/** The code of the translation Plotly has for the app's locale `code`, or undefined where it has none (English, Polish, Danish) */
export function plotlyDictionaryCode(code: string): string | undefined {
  const own = FALLBACKS[code] ?? code
  return Object.hasOwn(DICTIONARIES, own) ? own : undefined
}

const loading = new Map<string, Promise<Dictionary | undefined>>()

/** What `plotlyDictionary` answers, and whether the language has one that could not be loaded */
async function loadDictionary(code: string): Promise<{ dictionary: Dictionary | undefined, failed: boolean }> {
  const own = plotlyDictionaryCode(code)
  if (!own)
    return { dictionary: undefined, failed: false }
  let pending = loading.get(own)
  if (!pending) {
    pending = DICTIONARIES[own]!().then(module => module.default.dictionary, () => {
      loading.delete(own)
      return undefined
    })
    loading.set(own, pending)
  }
  const dictionary = await pending
  return { dictionary, failed: dictionary === undefined }
}

/**
 * The translation Plotly has for the app's locale `code`, undefined for English and the languages it has none
 * of, and where it could not be loaded (a chart then says its buttons in English, which is no reason for it not
 * to be drawn; the next drawing asks again).
 */
export async function plotlyDictionary(code: string): Promise<Dictionary | undefined> {
  return (await loadDictionary(code)).dictionary
}

/**
 * The `locale` and `locales` of a Plotly config for the page's language: `code` is the app's locale
 * (`de`, `lb`), `language` the tag it stands for (`de-DE`, `lb-LU`) that the dates are written in. The
 * locale is registered in the config under the language's tag, not in Plotly's global registry, so that
 * `lb` and `de-hh` have their own dates on German's buttons.
 * @example
 * await plotlyLocaleConfig('de', 'de-DE') // { locale: 'de-DE', locales: { 'de-DE': { dictionary: { Pan: 'Verschieben', ... }, format } } }
 */
export async function plotlyLocaleConfig(code: string, language: string): Promise<PlotlyLocaleConfig> {
  return (await plotlyLocaleConfigOrFailure(code, language)).config
}

/**
 * The same, and whether the language's buttons could not be loaded, so that a config made of the English
 * fallback is not kept as the language's: the caller that keeps one asks again where `failed`.
 */
export async function plotlyLocaleConfigOrFailure(code: string, language: string): Promise<{ config: PlotlyLocaleConfig, failed: boolean }> {
  const { dictionary, failed } = await loadDictionary(code)
  return {
    config: { locale: language, locales: { [language]: { ...(dictionary ? { dictionary } : {}), ...plotlyDateLocale(language) } } },
    failed,
  }
}

/**
 * Plotly's text `english` in the language of the config: the name of a button the app adds itself (its camera),
 * which Plotly does not translate as it does its own. English where the language has no word for it.
 * @example
 * plotlyText(await plotlyLocaleConfig('de', 'de-DE'), 'Download plot as a PNG') // 'Graphen als PNG herunterladen'
 */
export function plotlyText(config: PlotlyLocaleConfig, english: string): string {
  return config.locales[config.locale]?.dictionary?.[english] ?? english
}
