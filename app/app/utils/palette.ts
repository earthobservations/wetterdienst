// What the search finds (GH-3518): the matching of the command palette (AppCommandPalette.vue), apart from the
// component so that a test can hold it.

import type { Hit } from './search-index'

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
  /** The last item of a group that has more results than it shows: it leads to the page that has them all */
  more?: boolean
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

// ------------------------------------------------------------------------------------------------ the groups (GH-3790)

/**
 * The order of the groups, which follows what a reader most likely means: a point they typed, then stations, then the
 * pages (which a name finds: `glossary` is the Glossary before any text that says the word), then the words of the app and,
 * last, the actions. A group that is not named comes last.
 */
export const GROUP_ORDER = [
  'place',
  'stations',
  'stations-map',
  'tools',
  'reference',
  'providers',
  'project',
  'questions',
  'measurement',
  'method',
  'glossary',
  'settings',
  'theme',
  'language',
] as const

/** The groups in `GROUP_ORDER`, each as it is: the order of the groups of one kind is kept, a group with no items is left out */
export function orderGroups(groups: PaletteGroup[]): PaletteGroup[] {
  const rank = (group: PaletteGroup) => {
    const at = (GROUP_ORDER as readonly string[]).indexOf(group.id)
    return at === -1 ? GROUP_ORDER.length : at
  }
  return groups
    .map((group, index) => ({ group, index }))
    .filter(({ group }) => group.items.length > 0)
    .sort((a, b) => rank(a.group) - rank(b.group) || a.index - b.index)
    .map(({ group }) => group)
}

/** How many results each group of the words of the app shows before its "more" */
export const GROUP_LIMITS: Record<string, number> = {
  questions: 4,
  measurement: 3,
  method: 3,
  glossary: 4,
  settings: 3,
  project: 3,
}

/**
 * The few results a group shows. Where there are more than `limit`, the first `limit` stay and a last item, which the
 * caller makes (`more`, told how many are left out), leads to the page that has them all. A group that is one result
 * over the limit shows it: a "1 more" is no shorter than the result.
 */
export function limitItems(items: PaletteItem[], limit: number, more?: (hidden: number) => PaletteItem): PaletteItem[] {
  if (items.length <= limit + 1)
    return items
  const shown = items.slice(0, limit)
  return more ? [...shown, more(items.length - limit)] : shown
}

/** The line under a result of the app's own words: where in the page it is, then what it says */
export function hitDescription(hit: Pick<Hit, 'context' | 'summary'>): string {
  return [hit.context, hit.summary].filter(Boolean).join(' · ')
}

/** A result of the app's own words as an item of the search: it leads to its page and anchor */
export function itemOfHit(hit: Hit, icon: string): PaletteItem {
  return { id: `hit-${hit.to}`, label: hit.title, description: hitDescription(hit) || undefined, icon, to: hit.to }
}

/** How the live region says what there is: the number of results, then the number in each group (`label`, the group's name) */
export function countsByGroup(groups: PaletteGroup[], say: (group: string, count: number) => string): string {
  return groups.map(group => say(group.label, group.items.filter(item => !item.more).length)).join('. ')
}
