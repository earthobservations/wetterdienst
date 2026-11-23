import { timestampDate } from './timestamp'

/**
 * The credit of a provider's data as the app shows it beside a map layer: read from the `metadata.provider` block of an answer
 * (the licence and the credit line the provider states) and written as a line of the map's attribution. The thunderstorm cells
 * (GH-4208) and the radar frames (GH-3788) are DWD's, and each says so with its own answer's terms.
 */

/** The terms the data is published under, from the `metadata` block of the answer */
export interface ProviderCredit {
  /** The credit line the provider asks for ("Source: Deutscher Wetterdienst") */
  attribution: string | null
  copyright: string | null
  /** The licence: its name, its SPDX identifier where it has one, and the page of its terms */
  license: { name: string, spdx: string | null, url: string } | null
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const text = (value: unknown): string | null => typeof value === 'string' && value.trim() !== '' ? value : null

/**
 * How far the device's clock is from the server's, in milliseconds (server minus device), read from the answer's own `retrieved_at` when
 * it was parsed: a page that judges the age of a radar frame or a scan against `Date.now()` of a phone with the wrong time would call a
 * fresh loop stale or an old one fresh (GH-3788). 0 where the answer has no time.
 */
export function clockSkew(metadata: unknown, deviceNow: number = Date.now()): number {
  const retrieved = isRecord(metadata) ? text(metadata.retrieved_at) : null
  const at = retrieved ? timestampDate(retrieved) : null
  return at ? at.getTime() - deviceNow : 0
}

/** The credit of an answer's `metadata` block, or null where it holds none */
export function creditOf(metadata: unknown): ProviderCredit | null {
  const provider = isRecord(metadata) && isRecord(metadata.provider) ? metadata.provider : null
  if (!provider)
    return null
  const license = isRecord(provider.license) && text(provider.license.name) && text(provider.license.url)
    ? { name: text(provider.license.name)!, spdx: text(provider.license.spdx_id), url: text(provider.license.url)! }
    : null
  const credit = { attribution: text(provider.attribution), copyright: text(provider.copyright), license }
  return credit.attribution || credit.copyright || credit.license ? credit : null
}

const escapeHtml = (value: string) => value.replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', '\'': '&#39;' })[character]!)

/**
 * The credit of a layer's data as a line of the map's attribution (Leaflet takes HTML): the provider's credit line, the
 * product, and the licence as a link to its terms. Both come from the answer, so they are escaped, and a link is made only
 * for an `http(s)` address.
 */
export function creditHtml(credit: { text: string, license: { label: string, url: string } | null }): string {
  const link = credit.license && /^https?:\/\//i.test(credit.license.url)
    ? `, <a href="${escapeHtml(credit.license.url)}" target="_blank" rel="noopener">${escapeHtml(credit.license.label)}</a>`
    : ''
  return `${escapeHtml(credit.text)}${link}`
}

// -------------------------------------------------------------------------------------------- the credit beside provider data

/**
 * The terms the app writes beside provider data and into a file of it (GH-4255): the credit line the provider states and the
 * licence it publishes under, as `GET /api/providers` lists them (`Provider.attribution` and `Provider.license`) and as the
 * `metadata.provider` block of an answer holds them (the same two fields). Nothing of it is written in the app: a provider's
 * credit is the provider's.
 */
export interface ProviderTerms {
  attribution?: string | null
  license?: { name: string, url: string } | null
}

/** The terms of the provider `id` in the list `GET /api/providers` answered, or null where the list is not there or has no such provider */
export function termsOfProvider(providers: readonly ({ provider: string } & ProviderTerms)[] | undefined | null, id: string | null | undefined): ProviderTerms | null {
  const found = id ? providers?.find(provider => provider.provider === id) : undefined
  return found ? { attribution: found.attribution ?? null, license: found.license ?? null } : null
}

// -------------------------------------------------------------------------------------------- the label of a credit line (GH-4333)

/**
 * The leading labels of a provider's credit line that the app writes in the reader's language, with the key of `credit` that holds
 * the word. A provider's credit line is its own ("Source: Deutscher Wetterdienst", "© SMHI", "GeoSphere Austria", a text in Polish),
 * and only a label that is an English word the provider put before its name is the app's to translate; the words after it stay as
 * the provider wrote them. The longer label comes first. These are the labels the credit lines of the backend's providers start with
 * (`attribution` in the `metadata.py` of each provider: "Source:" at DWD, IPMA, MeteoSwiss and AEMET, "Data Source:" at ECCC).
 */
export const CREDIT_LABELS = [
  { pattern: /^data source\s*:\s*/i, key: 'dataSource' },
  { pattern: /^source\s*:\s*/i, key: 'source' },
] as const

/** The words of the labels in the reader's language, and the colon that follows a label there (`common.colon`: French sets a no-break space before it) */
export interface CreditLabels {
  source: string
  dataSource: string
  colon: string
}

/**
 * A provider's credit line with its leading label in the reader's language: "Source: Deutscher Wetterdienst" is "Quelle: Deutscher
 * Wetterdienst" in German. A credit line that starts with no known label, or is nothing but one, is returned as it is.
 */
export function localizedCredit(attribution: string, labels: CreditLabels): string {
  for (const { pattern, key } of CREDIT_LABELS) {
    const match = pattern.exec(attribution)
    if (match) {
      const rest = attribution.slice(match[0].length)
      return rest.trim() === '' ? attribution : `${labels[key]}${labels.colon} ${rest}`
    }
  }
  return attribution
}

/** The address of a licence's terms as a link, only where it is `http(s)`: the text comes from the API, and `javascript:` is never one */
export const safeHref = (url: string | null | undefined): string | null => url && /^https?:\/\//i.test(url) ? url : null

/**
 * The lines of a file of data that carry the credit (GH-4255): the provider's credit line, the licence with its address, and
 * what wetterdienst did to the data, each as one line of text and none where the terms hold nothing (the note is always
 * there). The same texts as the page shows beside the data.
 *
 * @param terms - The provider's terms, or null where they are not known
 * @param licence - Writes the licence's line from its name and address (`credit.licence`)
 * @param note - The processing note, in the language of the page
 * @param fallback - The credit line where the provider states none
 */
export function creditLines(terms: ProviderTerms | null, licence: (name: string, url: string) => string, note: string, fallback = ''): string[] {
  const licenceLine = terms?.license ? licence(terms.license.name, terms.license.url) : ''
  return [terms?.attribution || fallback, licenceLine, note].filter(line => line.trim() !== '')
}
