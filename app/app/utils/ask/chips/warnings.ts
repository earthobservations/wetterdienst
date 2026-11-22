import type { Warning, WarningSnapshot } from '../../warnings'
import type { AnswerAction, AnswerQuote, NumberLine } from '../chip'
import { clockOf, inWarningBox, notOver, productFor, WARNING_BOX, WARNINGS_REFRESH_MS, WARNINGS_STALE_AFTER_MS, warningsAt, withoutOutline, wordsOf } from '../../warnings'
import { defineChip } from '../chip'

// Are there warnings here? DWD's official weather warnings for the position of the place (GH-4295). The warning is DWD's statement: the answer
// says whether a warning of DWD has an area that contains the position, and quotes DWD's own words for each. It never rates a warning, says
// what to do, shortens or rewords a text, or says that there is nothing to fear: "no warning of DWD covers the place" is all it says of a quiet
// sky. Where DWD has no warnings (outside Germany and the sea round it) it says that no warnings source covers the place.

/** What it fetches: the latest snapshot of the community product, in the language the page reads DWD's texts in (the product `productFor` names) */
const FETCH = { provider: 'dwd', network: 'alerts' } as const

interface Loaded {
  /** The snapshot; null where the place is outside DWD's box and nothing was asked */
  snapshot: WarningSnapshot | null
  /** The locale of the page, whose texts are read where DWD has them (`textFor`) */
  locale: string
  /** The language the page writes times in */
  formatLanguage: string
}

interface WarningsAnswer {
  /** The warnings, not yet over, whose polygon contains the place, in the order of the lists */
  here: Warning[]
  /** How many warnings DWD names by area alone (the sea, a coast): they are not matched to a place */
  namedOnly: number
  /** The warnings in all, not yet over, anywhere */
  total: number
}

export const warnings = defineChip({
  id: 'warnings',
  icon: 'i-ph-warning',
  tool: 'map',
  question: env => env.t('ask.q.warnings'),
  from: 'ask.from.warnings',
  // the answer is a sentence of its own, as the download question's: DWD's words are quoted, and no scale of ours rates them
  scale: {},
  verdictStyle: 'sentence',
  credit: { provider: 'dwd', fallback: 'Deutscher Wetterdienst' },
  i18n: [
    'ask.q.warnings',
    'ask.from.warnings',
    'ask.warnings.none',
    'ask.warnings.some',
    'ask.warnings.highest',
    'ask.warnings.namedOnly',
    'ask.warnings.quote',
    'ask.warnings.outside',
    'ask.warnings.open',
    'ask.warnings.checked',
    'warnings.level.1',
    'warnings.level.2',
    'warnings.level.3',
    'warnings.level.4',
    'warnings.level.preliminary',
    'warnings.level.unknown',
    'warnings.levelOf',
    'warnings.inForce',
    'warnings.upcoming',
    'warnings.fromTo',
    'warnings.fromOpen',
    'warnings.until',
    'warnings.issued',
    'warnings.areasMore',
    'warnings.untitled',
    'warnings.textGerman',
  ],

  async load({ place, formatLanguage, locale }, api): Promise<Loaded> {
    // outside the box of DWD's warnings nothing is asked: no source of warnings covers the place
    if (!inWarningBox(place))
      return { snapshot: null, locale, formatLanguage }
    return { snapshot: await api.alerts(productFor(locale).product), locale, formatLanguage }
  },

  answer(loaded, { place, now }): WarningsAnswer | null {
    if (!loaded.snapshot)
      return null
    // by the server's clock, as the answer's own time says it was (the device's may be wrong)
    const at = now().toMillis() + loaded.snapshot.clockSkewMs
    const all = loaded.snapshot.warnings
    return {
      here: warningsAt(all, place, at),
      namedOnly: withoutOutline(all, at).length,
      total: notOver(all, at).length,
    }
  },

  present(answer, loaded, env) {
    const { t, place } = env
    const at = env.now().toMillis() + (loaded!.snapshot?.clockSkewMs ?? 0)
    const quotes: AnswerQuote[] = answer.here.map((warning) => {
      const words = wordsOf(warning, t, loaded!.locale, loaded!.formatLanguage, at)
      const paragraphs = [words.text.headline, words.text.description, words.text.instruction].filter((paragraph): paragraph is string => paragraph !== null)
      return {
        key: warning.id,
        heading: words.title,
        facts: [
          `${words.level} · ${words.phase}${words.validity ? ` · ${words.validity}` : ''}`,
          ...(words.issued ? [t('warnings.issued', { time: words.issued })] : []),
        ],
        paragraphs,
        lang: words.language,
        note: words.inLocale ? '' : t('warnings.textGerman'),
      }
    })
    const checked = clockOf(loaded!.snapshot?.retrievedAt ?? null, loaded!.formatLanguage, at)
    const notes = [
      answer.here.length ? t('ask.warnings.quote') : '',
      answer.namedOnly ? t('ask.warnings.namedOnly', { count: answer.namedOnly, place: place.name }) : '',
      checked ? t('ask.warnings.checked', { time: checked }) : '',
    ].filter(note => note !== '')
    return {
      verdict: answer.here.length ? t('ask.warnings.some', { place: place.name }) : t('ask.warnings.none', { place: place.name }),
      // the highest level the warnings of DWD have, in its own word: a fact of the data, and no rating of ours
      details: answer.here.length ? [t('ask.warnings.highest', { level: wordsOf(answer.here[0]!, t, loaded!.locale, loaded!.formatLanguage, at).level })] : [],
      chart: null,
      list: null,
      quotes,
      note: notes.join(' '),
    }
  },

  explanation: {
    topics: ['time', 'observation-forecast-derived'],
    steps: ['snapshot', 'place', 'inforce', 'words'],
    formulas: [],
    rules: [
      // which warnings, and which of them count
      { id: 'product', kind: 'selection', cites: [{ work: 'dwd-cap-profile', at: '§1.1' }] },
      { id: 'dropped', kind: 'selection', cites: [{ work: 'dwd-cap-profile', at: '§2.2.1.4, §2.2.1.5, §2.2.2.4' }] },
      // what a warning says
      { id: 'levels', kind: 'band', cites: [{ work: 'dwd-cap-profile', at: '§2.2.2.6, §3.5' }] },
      { id: 'preliminary', kind: 'selection', cites: [{ work: 'dwd-cap-profile', at: '§2.2.2.5, §2.2.2.13, §3.1.2' }] },
      { id: 'health-colours', kind: 'selection', cites: [{ work: 'dwd-cap-profile', at: '§2.2.2.8, §3.1.5, §3.5' }] },
      { id: 'in-force', kind: 'window', own: true, cites: [{ work: 'dwd-cap-profile', at: '§2.2.2.10, §2.2.2.11' }] },
      // which warnings are for the place
      { id: 'polygon', kind: 'selection', cites: [{ work: 'dwd-cap-profile', at: '§2.2.3.3' }] },
      { id: 'edge', kind: 'selection', own: true, cites: [] },
      { id: 'named-only', kind: 'selection', own: true, cites: [{ work: 'dwd-cap-profile', at: '§2.2.3.3, §3.6.1' }] },
      { id: 'coverage', kind: 'selection', own: true, values: { west: WARNING_BOX.west, south: WARNING_BOX.south, east: WARNING_BOX.east, north: WARNING_BOX.north }, cites: [] },
      // how it is told
      { id: 'language', kind: 'selection', own: true, cites: [] },
      { id: 'order', kind: 'selection', own: true, cites: [] },
      { id: 'refresh', kind: 'window', own: true, values: { minutes: WARNINGS_REFRESH_MS / 60_000, staleMinutes: WARNINGS_STALE_AFTER_MS / 60_000 }, cites: [] },
    ],
    limits: ['statement', 'polygon', 'named', 'altitude', 'time'],
    data: {
      provider: FETCH.provider,
      network: FETCH.network,
      dataset: null,
      parameters: [],
      // the warnings are no dataset of the Explorer: the map is where they are seen
      open: () => null,
    },
    numbers(answer, loaded, env): NumberLine[] {
      const { place, number } = env
      const at = env.now().toMillis() + (loaded.snapshot?.clockSkewMs ?? 0)
      const checked = clockOf(loaded.snapshot?.retrievedAt ?? null, loaded.formatLanguage, at)
      const latest = clockOf(loaded.snapshot?.latestIssue ?? null, loaded.formatLanguage, at)
      const lines: NumberLine[] = [
        { id: 'place', params: { place: place.name, latitude: number(place.latitude, 4), longitude: number(place.longitude, 4) } },
        { id: 'count', params: { here: answer.here.length, total: answer.total } },
        { id: 'named', params: { count: answer.namedOnly } },
      ]
      if (checked)
        lines.push({ id: 'checked', params: { time: checked, latest: latest || '–' } })
      return lines
    },
  },

  empty: (_loaded, env) => env.t('ask.warnings.outside', { place: env.place.name }),

  // into the map with the warnings on, at the place: where DWD's outlines are seen, and the list of all of them
  actions: (env): AnswerAction[] => [{
    key: 'map',
    label: env.t('ask.warnings.open'),
    tool: 'map',
    to: { path: '/map', query: { warnings: '1', lat: env.place.latitude.toFixed(4), lon: env.place.longitude.toFixed(4) } },
  }],
})
