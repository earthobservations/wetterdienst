// What the command palette finds for a query (GH-3518), apart from the component so that it can be tested alone.

/** Lower case and without accents, so that "munchen" finds "München" and "cesky" finds "Český" */
export function normalizeSearch(text: string): string {
  return text
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/ß/g, 'ss')
    .trim()
}

export interface Searchable {
  label: string
  description?: string
  keywords?: string
}

/**
 * How well an entry answers a query, or null for not at all. Every word of the query has to be in the entry
 * (its label, description or keywords); the label starting with the query ranks first, a word of the label
 * starting with it next, then the rest.
 */
export function searchScore(entry: Searchable, query: string): number | null {
  const words = normalizeSearch(query).split(/\s+/).filter(Boolean)
  if (!words.length)
    return 0
  const label = normalizeSearch(entry.label)
  const haystack = `${label} ${normalizeSearch(entry.description ?? '')} ${normalizeSearch(entry.keywords ?? '')}`
  if (!words.every(word => haystack.includes(word)))
    return null
  const whole = words.join(' ')
  if (label.startsWith(whole))
    return 3
  if (label.split(/[\s(),.\-/]+/).some(part => part.startsWith(words[0]!)))
    return 2
  return label.includes(words[0]!) ? 1 : 0
}

/** The entries that answer the query, best first, the order they came in among equals */
export function rankEntries<T extends Searchable>(entries: T[], query: string, limit = Number.POSITIVE_INFINITY): T[] {
  return entries
    .map((entry, index) => ({ entry, index, score: searchScore(entry, query) }))
    .filter((hit): hit is { entry: T, index: number, score: number } => hit.score !== null)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .slice(0, limit)
    .map(hit => hit.entry)
}

/** The index of the next entry of `count`, moving by `step` and coming round at either end; -1 for none */
export function stepIndex(current: number, step: number, count: number): number {
  if (count <= 0)
    return -1
  if (current < 0)
    return step > 0 ? 0 : count - 1
  return (current + step + count) % count
}
