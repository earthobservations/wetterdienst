// What the search finds (GH-3518): the matching of the command palette (AppCommandPalette.vue), apart from the
// component so that a test can hold it.

export interface PaletteItem {
  id: string
  label: string
  /** One line that says what it is for */
  description?: string
  /** More words it is found by, which it does not show (a provider's English name, a language's code) */
  keywords?: string
  icon?: string
  tile?: string
  /** A place of the app, or another site (`external`) */
  to?: string
  external?: boolean
  /** An action: a theme, a language */
  run?: () => void
  /** The current theme or language: marked, and still choosable */
  current?: boolean
}

export interface PaletteGroup {
  id: string
  label: string
  items: PaletteItem[]
}

/** Lower case, without accents: `München` is found by `munchen`, `Čeština` by `cestina` */
export function fold(text: string): string {
  return text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
}

/**
 * How well an item answers a query, or null for not at all. Every word of the query has to be in its name, its
 * description or its keywords; a name that starts with the query comes first, then one that holds it, then the rest.
 */
export function scoreOf(item: PaletteItem, query: string): number | null {
  const words = fold(query).split(/\s+/).filter(Boolean)
  if (!words.length)
    return 0
  const label = fold(item.label)
  const all = `${label} ${fold(item.description ?? '')} ${fold(item.keywords ?? '')}`
  if (!words.every(word => all.includes(word)))
    return null
  const whole = words.join(' ')
  if (label.startsWith(whole))
    return 3
  if (label.split(/[\s(-]+/).some(part => part.startsWith(words[0]!)))
    return 2
  return label.includes(words[0]!) ? 1 : 0
}

/** The groups with the items that answer the query, best first within a group; a group with none is left out */
export function filterGroups(groups: PaletteGroup[], query: string): PaletteGroup[] {
  return groups
    .map((group) => {
      const scored = group.items
        .map((item, index) => ({ item, index, score: scoreOf(item, query) }))
        .filter((entry): entry is { item: PaletteItem, index: number, score: number } => entry.score !== null)
        .sort((a, b) => b.score - a.score || a.index - b.index)
      return { ...group, items: scored.map(entry => entry.item) }
    })
    .filter(group => group.items.length > 0)
}
