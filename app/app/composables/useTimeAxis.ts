// The app's pages laid out along one axis of time (GH-3518): the climate stripes and the station histories lie in
// the past, the explorer's measurements reach up to the present, the home page is the present, and the forecast is
// the next ten days. The reference pages (providers, glossary, API, settings, about, legal) are off the axis.
//
// The frame draws the axis as its navigation (`AppTimeRail.vue`), every page header shows where on it the page
// sits (`AppPage.vue`), and the command palette jumps along it (`CommandPalette.vue`). One table for all three.

export type Zone = 'then' | 'now' | 'next' | 'reference'

export type AxisKey = 'stripes' | 'history' | 'explorer' | 'now' | 'forecast'
export type ReferenceKey = 'providers' | 'glossary' | 'api' | 'settings' | 'about' | 'support' | 'impressum' | 'datenschutz'
export type PageKey = AxisKey | ReferenceKey

/** Where the drawn axis puts the present, in per cent of its length: the past is long, the forecast ten days */
export const NOW_AT = 80

/** The forecast's reach: MOSMIX runs 240 hours ahead */
export const FORECAST_DAYS = 10

export interface AxisStop {
  key: AxisKey
  path: string
  icon: string
  zone: Exclude<Zone, 'reference'>
  /** The stretch of the drawn axis the page covers, in per cent */
  from: number
  to: number
}

// in the order of time, oldest first, as the rail draws them
export const AXIS_STOPS: AxisStop[] = [
  { key: 'stripes', path: '/stripes', icon: 'i-lucide-bar-chart-3', zone: 'then', from: 0, to: 76 },
  { key: 'history', path: '/history', icon: 'i-lucide-history', zone: 'then', from: 8, to: NOW_AT },
  { key: 'explorer', path: '/explorer', icon: 'i-lucide-table-2', zone: 'then', from: 34, to: NOW_AT },
  { key: 'now', path: '/', icon: 'i-lucide-locate-fixed', zone: 'now', from: NOW_AT, to: NOW_AT },
  { key: 'forecast', path: '/meteogram', icon: 'i-lucide-cloud-sun', zone: 'next', from: NOW_AT, to: 100 },
]

export interface ReferencePage {
  key: ReferenceKey
  path: string
  icon: string
  /** Shown in the rail, beside the axis; the others are reached from the footer, the menu and the palette */
  inRail: boolean
}

export const REFERENCE_PAGES: ReferencePage[] = [
  { key: 'providers', path: '/providers', icon: 'i-lucide-building-2', inRail: true },
  { key: 'glossary', path: '/glossary', icon: 'i-lucide-book-open', inRail: true },
  { key: 'api', path: '/api', icon: 'i-lucide-code', inRail: true },
  { key: 'settings', path: '/settings', icon: 'i-lucide-settings-2', inRail: false },
  { key: 'about', path: '/about', icon: 'i-lucide-info', inRail: false },
  { key: 'support', path: '/support', icon: 'i-lucide-heart', inRail: false },
  { key: 'impressum', path: '/impressum', icon: 'i-lucide-scale', inRail: false },
  { key: 'datenschutz', path: '/datenschutz', icon: 'i-lucide-shield', inRail: false },
]

/** The page a path belongs to: `/providers/dwd` is the providers' page, `/privacy` the privacy policy's */
export function pageOfPath(path: string): PageKey | null {
  const clean = path.replace(/\/+$/, '') || '/'
  if (clean === '/')
    return 'now'
  if (clean === '/privacy')
    return 'datenschutz'
  const stop = AXIS_STOPS.find(stop => stop.path !== '/' && (clean === stop.path || clean.startsWith(`${stop.path}/`)))
  if (stop)
    return stop.key
  return REFERENCE_PAGES.find(page => clean === page.path || clean.startsWith(`${page.path}/`))?.key ?? null
}

export function zoneOfPage(key: PageKey | null): Zone | null {
  if (key === null)
    return null
  return AXIS_STOPS.find(stop => stop.key === key)?.zone ?? 'reference'
}

/** The label of a page as the navigation names it */
export const PAGE_LABEL_KEYS: Record<PageKey, string> = {
  stripes: 'nav.stripes',
  history: 'nav.history',
  explorer: 'nav.explorer',
  now: 'axis.now',
  forecast: 'nav.meteogram',
  providers: 'nav.providers',
  glossary: 'nav.glossary',
  api: 'nav.api',
  settings: 'settings.title',
  about: 'footer.about',
  support: 'nav.support',
  impressum: 'footer.legal',
  datenschutz: 'footer.privacy',
}

/**
 * The words for where on the axis a page sits, in the language of the page: dates and years come from `Intl`, so
 * that they need no translation of their own.
 */
export function useTimeAxis() {
  const { t, localeProperties } = useI18n()
  const route = useRoute()

  // the moment the page was opened: the axis moves on with the day, not with the second
  const now = useState('time-axis-now', () => Date.now())
  const language = computed(() => localeProperties.value.language || 'en-GB')

  const today = computed(() => new Intl.DateTimeFormat(language.value, { weekday: 'long', day: 'numeric', month: 'long' }).format(now.value))
  const forecastEnd = computed(() => new Intl.DateTimeFormat(language.value, { weekday: 'short', day: 'numeric', month: 'short' })
    .format(now.value + FORECAST_DAYS * 86_400_000))
  const lastYear = computed(() => new Date(now.value).getFullYear() - 1)

  function span(key: PageKey): string {
    switch (key) {
      case 'stripes': return t('axis.spanStripes', { year: lastYear.value })
      case 'history': return t('axis.spanHistory')
      case 'explorer': return t('axis.spanExplorer')
      case 'now': return t('axis.spanNow', { date: today.value })
      case 'forecast': return t('axis.spanForecast', { date: forecastEnd.value })
      default: return t('axis.spanReference')
    }
  }

  const current = computed(() => pageOfPath(route.path))
  const zone = computed(() => zoneOfPage(current.value))

  return { now, today, lastYear, span, current, zone }
}
