/**
 * The matching of the command palette (AppPalette.vue, GH-3518): what a typed query finds among the pages, the
 * settings and the forecast's stations.
 */

/** A text as the palette compares it: lower case, without accents, and without the spaces at either end */
export function normalise(text: string): string {
  return text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().trim()
}

/**
 * The forms a query is looked for in. The MOSMIX station list writes German names without umlauts
 * (`MUENCHEN`, `ZUERICH`), so "München" is looked for as "munchen" and as "muenchen".
 */
export function queryForms(query: string): string[] {
  const plain = normalise(query)
  const spelled = query.toLowerCase().trim().replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
  return [...new Set([plain, normalise(spelled)])].filter(Boolean)
}

/** Whether any of the texts holds any form of the query; an empty query finds everything */
export function matches(query: string, ...texts: Array<string | null | undefined>): boolean {
  const forms = queryForms(query)
  if (!forms.length)
    return true
  const haystack = texts.filter((text): text is string => Boolean(text)).map(normalise)
  return forms.some(form => haystack.some(text => text.includes(form)))
}

/**
 * The stations whose name or identifier holds the query, those whose name starts with it first, at most `limit`.
 * Nothing for a query of fewer than two letters, which would find hundreds.
 */
export function findStations<T extends { station_id: string, name: string | null }>(stations: T[], query: string, limit = 6): T[] {
  const forms = queryForms(query)
  if (!forms.length || forms.every(form => form.length < 2))
    return []
  const scored: Array<{ station: T, rank: number }> = []
  for (const station of stations) {
    const name = normalise(station.name ?? '')
    const id = station.station_id.toLowerCase()
    let rank = Number.POSITIVE_INFINITY
    for (const form of forms) {
      if (id === form || name.startsWith(form))
        rank = Math.min(rank, 0)
      else if (name.includes(form) || id.startsWith(form))
        rank = Math.min(rank, 1)
    }
    if (Number.isFinite(rank))
      scored.push({ station, rank })
  }
  return scored
    .sort((a, b) => a.rank - b.rank || (a.station.name ?? '').localeCompare(b.station.name ?? ''))
    .slice(0, limit)
    .map(entry => entry.station)
}
