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
