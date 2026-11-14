import type { MeteogramView } from '~/utils/meteogram'
import { meteogramView, meteogramViewFromQuery } from '~/utils/meteogram'

export type PanelId = 'temp' | 'wind' | 'precip' | 'cloud' | 'pressure'

const LOCAL_STORAGE_KEY = 'meteogram.view'
// the key from before the table was a view: `true` for the compact overview, `false` for the chart
const LEGACY_STORAGE_KEY = 'meteogram.compact'

// The view last chosen. The old key held only whether the view was the compact overview: its value is taken over
// once, as the same choice under the new key, and the old key is gone.
function storedView(): MeteogramView | null {
  try {
    const stored = meteogramView(localStorage.getItem(LOCAL_STORAGE_KEY))
    if (stored)
      return stored
    const legacy = localStorage.getItem(LEGACY_STORAGE_KEY)
    if (legacy === null)
      return null
    const migrated = legacy === 'true' ? 'compact' : 'chart'
    localStorage.setItem(LOCAL_STORAGE_KEY, migrated)
    localStorage.removeItem(LEGACY_STORAGE_KEY)
    return migrated
  }
  catch {
    return null
  }
}

/**
 * What the reader chose of the forecast: the view (the chart, the day cards, the table), the panels that are shown and
 * how many hours of the run. The view is remembered in local storage and all three are written to the address
 * (`?view=table&panels=temp,wind&horizon=72`) and read from it on load, so that a link opens what it was copied from.
 * The widget reads and writes no address; the day rows alone (`daysOnly`) choose nothing, and keep nothing.
 */
export function useMeteogramView(options: { daysOnly?: boolean, widget?: boolean }) {
  const view = ref<MeteogramView>(options.daysOnly ? 'compact' : 'chart')
  const compact = computed(() => view.value === 'compact')

  const visiblePanels = ref<Record<PanelId, boolean>>({
    temp: true,
    wind: true,
    precip: true,
    cloud: true,
    pressure: true,
  })
  // Forecast horizon filter: null = show all data
  const horizonHours = ref<number | null>(null)

  // Ensure at least one panel is always active
  watch(visiblePanels, (newVal) => {
    if (!Object.values(newVal).some(v => v))
      visiblePanels.value.temp = true
  }, { deep: true })

  // A choice of the reader's: remembered. A view that a link or the small screen gave is not.
  function chooseView(next: MeteogramView) {
    view.value = next
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, next)
    }
    catch {
      // ignore
    }
  }

  // On mount try to restore user preference and auto-enable compact on small screens,
  // with URL params taking precedence over localStorage.
  onMounted(() => {
    // the day rows and nothing else: no preference to restore, and no link to write
    if (options.daysOnly)
      return
    const stored = storedView()
    // the widget has no control to leave the table with: it shows the chart or the day cards
    if (stored && !(options.widget && stored === 'table'))
      view.value = stored
    // in rem, so that a reader who has set a larger text size gets the compact view sooner (GH-3518)
    else if (!stored && window.matchMedia('(max-width: 40rem)').matches)
      view.value = 'compact'

    if (options.widget)
      return
    const route = useRoute()
    const router = useRouter()
    const q = route.query
    if (q.horizon) {
      const h = Number(q.horizon.toString())
      if (Number.isFinite(h) && h > 0)
        horizonHours.value = h
    }
    if (q.panels) {
      const names = q.panels.toString().split(',').filter(Boolean)
      visiblePanels.value = {
        temp: names.includes('temp'),
        wind: names.includes('wind'),
        precip: names.includes('precip'),
        cloud: names.includes('cloud'),
        pressure: names.includes('pressure'),
      }
    }
    // `compact=true` is the link of the time the table was no view: it still opens the compact overview
    const linked = meteogramViewFromQuery(q)
    if (linked)
      view.value = linked

    // A rejected navigation (e.g. superseded by a subsequent replace() before this one resolves) would
    // otherwise be an unhandled promise rejection, as the pages that sync their state to the URL catch it.
    const write = (change: (query: Record<string, any>) => void) => {
      const query = { ...route.query } as Record<string, any>
      change(query)
      void router.replace({ query }).catch(() => {})
    }

    watch(horizonHours, (h) => {
      write((query) => {
        if (h !== null)
          query.horizon = String(h)
        else
          delete query.horizon
      })
    })

    watch(visiblePanels, (panels) => {
      const visible = (Object.keys(panels) as PanelId[]).filter(k => panels[k])
      write((query) => {
        if (visible.length < 5)
          query.panels = visible.join(',')
        else
          delete query.panels
      })
    }, { deep: true })

    watch(view, (v) => {
      write((query) => {
        query.view = v
        delete query.compact
      })
    })
  })

  return { view, compact, visiblePanels, horizonHours, chooseView }
}
