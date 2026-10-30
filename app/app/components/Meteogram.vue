<script setup lang="ts">
import type { SunTimes } from 'suncalc'
import type { Value } from '#shared/types/api'
import type { ChartTheme } from '~/utils/chart-theme'
import type { WeatherKind } from '~/utils/weather-kind'
import { DateTime } from 'luxon'
import tzLookup from 'tz-lookup'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { formatDayMonth, formatNumber, plotlyDateLocale, plotlyHoverFormat, plotlySeparators, weekdayShort } from '~/utils/format'
import { extremeWindowHours, extremeWindowSteps, interpSeries, METEOGRAM_SERIES, nearestNeighbor, resampleCadenceMs, wetBulbApprox } from '~/utils/meteogram'
import { WEATHER_SYMBOLS, weatherCodeToKind } from '~/utils/weather-kind'

const props = defineProps<{
  values: Value[]
  stationName?: string | null
  stationCoords?: { latitude: number | null, longitude: number | null } | null
  widget?: boolean
}>()

const { t, locale, localeProperties } = useI18n()

// The language's own tag (`en-GB`, `de-DE`), which the date formats read, where `locale` is the app's code (`en`)
const language = computed(() => localeProperties.value.language ?? locale.value)

const chartRef = ref<HTMLDivElement | null>(null)
let Plotly: any = null
// the theme the chart on the page was last drawn in, which its overlay of wind barbs is painted in
let drawnTheme: ChartTheme | null = null
// loaded once, as Plotly is: a drawing in the colours of a switched scheme, or of a print, has no wait for it
let SunCalc: typeof import('suncalc') | null = null
const plotlyLoaded = ref(false)
let overlayCanvas: HTMLCanvasElement | null = null
let overlayAttached = false

// The chart's chrome (paper, text, grid, hover label) is read from the app's CSS tokens for the colour
// scheme in force (utils/chart-theme.ts); a switch of the scheme draws the chart again below
const { theme, isDark } = useChartTheme()

// Compact mode toggles a denser, lower-height rendering of the meteogram.
const compact = ref(false)
const chartHeight = computed(() => (compact.value ? '320px' : '540px'))
// Limit how many days the compact view will show by default
const MAX_COMPACT_DAYS = 7
const LOCAL_STORAGE_KEY = 'meteogram.compact'

// Interactive panel visibility controls
const visiblePanels = ref({
  temp: true,
  wind: true,
  precip: true,
  cloud: true,
  pressure: true,
})

// Forecast horizon filter: null = show all data
const horizonHours = ref<number | null>(null)
const horizonOptions = computed(() => [
  { label: '24h', value: 24 },
  { label: '3d', value: 72 },
  { label: '7d', value: 168 },
  { label: t('meteogram.chart.horizonAll'), value: null },
])

// Ensure at least one panel is always active
watch(visiblePanels, (newVal) => {
  const anyActive = Object.values(newVal).some(v => v)
  if (!anyActive) {
    visiblePanels.value.temp = true
  }
}, { deep: true })

const seriesCache = computed(() => buildSeries(props.values ?? []))

// On mount try to restore user preference and auto-enable compact on small screens,
// with URL params taking precedence over localStorage.
onMounted(() => {
  try {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(LOCAL_STORAGE_KEY)
      if (stored !== null)
        compact.value = stored === 'true'
      else if (window.innerWidth <= 640)
        compact.value = true
    }
  }
  catch {
    // ignore
  }

  if (!props.widget) {
    const q = useRoute().query
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
    if (q.compact)
      compact.value = q.compact.toString() === 'true'

    const router = useRouter()
    const route = useRoute()
    // A rejected navigation (e.g. superseded by a subsequent replace() before this one resolves) would
    // otherwise be an unhandled promise rejection, as the pages that sync their state to the URL catch it.

    watch(horizonHours, (h) => {
      const q = { ...route.query } as Record<string, any>
      if (h !== null)
        q.horizon = String(h)
      else
        delete q.horizon
      void router.replace({ query: q }).catch(() => {})
    })

    watch(visiblePanels, (panels) => {
      const visible = (Object.keys(panels) as Array<keyof typeof panels>).filter(k => panels[k])
      const q = { ...route.query } as Record<string, any>
      if (visible.length < 5)
        q.panels = visible.join(',')
      else
        delete q.panels
      void router.replace({ query: q }).catch(() => {})
    }, { deep: true })

    watch(compact, (c) => {
      const q = { ...route.query } as Record<string, any>
      q.compact = c ? 'true' : 'false'
      void router.replace({ query: q }).catch(() => {})
    })
  }
})

// overlay redraw handler ref for attach/detach
let overlayRedrawHandler: ((ev?: any) => void) | null = null

// Expose a reset function that re-applies original Plotly layout
function resetChart() {
  horizonHours.value = null
  if (!chartRef.value || !plotlyLoaded.value)
    return
  try {
    const el = chartRef.value as any
    Plotly.relayout(el, { 'xaxis.autorange': true })
    requestRender(false)
  }
  catch {
    // ignore
  }
}

function toggleCompact() {
  compact.value = !compact.value
  try {
    if (typeof window !== 'undefined') {
      localStorage.setItem(LOCAL_STORAGE_KEY, String(compact.value))
    }
  }
  catch {
    // ignore
  }
}

onUnmounted(() => {
  try {
    cleanupPlotlyOverlayHandlers()
  }
  catch {
    // ignore
  }
  try {
    cleanupOverlay()
  }
  catch {
    // ignore
  }
  if (Plotly && chartRef.value) {
    try {
      Plotly.purge(chartRef.value)
    }
    catch {
      // ignore
    }
  }
})

const compactLabel = computed(() => compact.value ? t('meteogram.chart.viewNormal') : t('meteogram.chart.viewCompact'))

// Toolbar timezone label (updated when chart renders)
const toolbarTzLabel = ref<string>('UTC')

const compactDays = computed(() => {
  const out: { date: any, kind: WeatherKind, weekday: string, dayMonth: string, tempLabel?: string | null, precipLabel?: string | null, isToday: boolean }[] = []
  const series = seriesCache.value
  const available = new Set(series.keys())
  const weatherKey = findFirstAvailable(METEOGRAM_SERIES.weather, available)
  const precipKey = findFirstAvailable(METEOGRAM_SERIES.precipitation, available)
  const tempKey = findFirstAvailable(METEOGRAM_SERIES.temperature, available)
  const cloudKey = findFirstAvailable(METEOGRAM_SERIES.cloudCover, available)

  // determine timezone
  let stationTZ = 'UTC'
  if (props.stationCoords?.latitude != null && props.stationCoords?.longitude != null) {
    try {
      stationTZ = tzLookup(props.stationCoords.latitude, props.stationCoords.longitude)
    }
    catch {
      stationTZ = 'UTC'
    }
  }

  const localNow = DateTime.now().setZone(stationTZ)

  const allTimes = [...series.values()].flatMap(s => s.x.map(d => d.getTime()))
  if (!allTimes.length) {
    return out
  }
  const minTime = Math.min(...allTimes)
  const maxTime = Math.max(...allTimes)

  let dt = DateTime.fromMillis(minTime, { zone: stationTZ }).startOf('day')
  const last = DateTime.fromMillis(maxTime, { zone: stationTZ }).startOf('day')
  while (dt.toMillis() <= last.toMillis()) {
    const startUTC = dt.toUTC().toMillis()
    const endUTC = dt.plus({ days: 1 }).toUTC().toMillis()

    // null while neither a weather code nor the fallback below has said
    let kind: WeatherKind | null = null

    // Prefer significant weather codes when available
    if (weatherKey && series.has(weatherKey)) {
      const ws = series.get(weatherKey)!
      const allCounts = new Map<number, number>()

      for (let i = 0; i < ws.x.length; i++) {
        const t = ws.x[i]!.getTime()
        if (t >= startUTC && t < endUTC) {
          const raw = ws.y[i]
          const code = typeof raw === 'number' ? Math.round(raw) : Number.parseInt(String(raw))
          if (!Number.isNaN(code)) {
            allCounts.set(code, (allCounts.get(code) ?? 0) + 1)
          }
        }
      }

      if (allCounts.size > 0) {
        // Choose best code: if any code with severity >= 3 occurs at least 2 times,
        // we pick the one with highest severity. Otherwise, we choose the most frequent code.
        const getWeatherSeverity = (code: number): number => {
          if (code >= 95 && code <= 99)
            return 9 // thunderstorm
          if (code >= 80 && code <= 86)
            return 8 // showers
          if (code >= 70 && code <= 79)
            return 7 // snow
          if (code >= 60 && code <= 69)
            return 6 // rain
          if (code >= 50 && code <= 59)
            return 5 // drizzle
          if (code >= 40 && code <= 49)
            return 4 // fog
          if (code === 3)
            return 3 // overcast / cloudy
          if (code === 2)
            return 2 // partly cloudy
          if (code === 1)
            return 1 // mostly clear
          return 0 // clear / sunny / default
        }

        let best = -1
        let highestSeverity = -1
        let mostFrequent = -1
        let maxCount = -1

        for (const [c, cnt] of allCounts) {
          if (cnt > maxCount) {
            mostFrequent = c
            maxCount = cnt
          }
          const sev = getWeatherSeverity(c)
          if (sev >= 3 && cnt >= 2) {
            if (sev > highestSeverity) {
              highestSeverity = sev
              best = c
            }
          }
        }

        // If no significant weather with count >= 2, fall back to most frequent
        if (best === -1) {
          best = mostFrequent
        }

        if (best !== -1) {
          kind = weatherCodeToKind(best)
        }
      }
    }

    let minT = Number.POSITIVE_INFINITY
    let maxT = Number.NEGATIVE_INFINITY
    if (tempKey && series.has(tempKey)) {
      const ts = series.get(tempKey)!
      for (let i = 0; i < ts.x.length; i++) {
        const t = ts.x[i]!.getTime()
        if (t >= startUTC && t < endUTC) {
          const val = Number(ts.y[i] ?? Number.NaN)
          if (!Number.isNaN(val)) {
            minT = Math.min(minT, val)
            maxT = Math.max(maxT, val)
          }
        }
      }
    }

    // Precipitation total for the day (always computed)
    let dayPrecip = 0
    if (precipKey && series.has(precipKey)) {
      const ps = series.get(precipKey)!
      for (let i = 0; i < ps.x.length; i++) {
        const t = ps.x[i]!.getTime()
        if (t >= startUTC && t < endUTC)
          dayPrecip += Number(ps.y[i] ?? 0)
      }
    }

    // Fallback heuristics: cloud cover
    if (kind === null) {
      let cloudSum = 0
      let cloudCount = 0
      if (cloudKey && series.has(cloudKey)) {
        const cs = series.get(cloudKey)!
        const nonNullY = cs.y.filter((v): v is number => v !== null && v !== undefined)
        const scaleFactor = cloudScaleFactor(nonNullY)
        for (let i = 0; i < cs.x.length; i++) {
          const t = cs.x[i]!.getTime()
          if (t >= startUTC && t < endUTC) {
            cloudSum += (cs.y[i] ?? 0) * scaleFactor
            cloudCount++
          }
        }
      }
      const avgCloud = cloudCount ? (cloudSum / cloudCount) : 0
      if (dayPrecip > 0.5)
        kind = (Number.isFinite(minT) && minT <= 0.5) ? 'snow' : 'rain'
      else if (avgCloud >= 70)
        kind = 'cloudy'
      else if (avgCloud >= 30)
        kind = 'partlyCloudy'
      else
        kind = 'clear'
    }

    const tempLabel = Number.isFinite(minT) && Number.isFinite(maxT) ? `${Math.round(minT)} / ${Math.round(maxT)}°C` : null
    const precipLabel = dayPrecip >= 0.1 ? `${formatNumber(dayPrecip, locale.value, 1)} mm` : null
    const isToday = dt.hasSame(localNow, 'day')
    out.push({ date: dt, kind: kind ?? 'clear', weekday: weekdayShort(dt, language.value), dayMonth: formatDayMonth(dt, language.value), tempLabel, precipLabel, isToday })
    dt = dt.plus({ days: 1 })
  }
  // Limit number of days shown in compact mode for readability
  if (out.length > MAX_COMPACT_DAYS) {
    return out.slice(0, MAX_COMPACT_DAYS)
  }
  return out
})

// The station's time zone, which the times of the table are written in, as the chart's axis is
const stationTimeZone = computed(() => {
  const { latitude, longitude } = props.stationCoords ?? {}
  if (latitude == null || longitude == null)
    return 'UTC'
  try {
    return tzLookup(latitude, longitude)
  }
  catch {
    return 'UTC'
  }
})

// What the chart draws, as a table and a sentence (WCAG 1.1.1, 1.3.1, and 1.4.13 for the values that appear
// on hover only): the panels that are shown, one column for each series they plot, one row for each time
// the forecast has a value, as far as the horizon chosen reaches. The values are the forecast's own, in
// the units the chart labels them in, not the chart's resampled curve.
const chartTable = computed(() => {
  const series = seriesCache.value
  if (!series.size)
    return null
  const available = new Set(series.keys())
  const pick = (names: readonly string[]) => findFirstAvailable(names, available)
  const panels = visiblePanels.value
  const specs: { shown: boolean, key: string | undefined, label: string, digits: number, percent?: boolean, main?: boolean }[] = [
    { shown: panels.temp, key: pick(METEOGRAM_SERIES.temperature), label: t('meteogram.chart.seriesTemperature'), digits: 1, main: true },
    { shown: panels.temp, key: pick(METEOGRAM_SERIES.temperatureMax), label: t('meteogram.chart.seriesMaxTemp'), digits: 1 },
    { shown: panels.temp, key: pick(METEOGRAM_SERIES.temperatureMin), label: t('meteogram.chart.seriesMinTemp'), digits: 1 },
    { shown: panels.temp, key: pick(METEOGRAM_SERIES.dewPoint), label: `${t('meteogram.chart.seriesDewPoint')} °C`, digits: 1 },
    { shown: panels.wind, key: pick(METEOGRAM_SERIES.windSpeed), label: t('meteogram.chart.seriesWind'), digits: 1 },
    { shown: panels.wind, key: pick(METEOGRAM_SERIES.windDirection), label: `${t('meteogram.chart.seriesDirection')} °`, digits: 0 },
    { shown: panels.wind, key: pick(METEOGRAM_SERIES.gust), label: t('meteogram.chart.seriesWindGust'), digits: 1 },
    { shown: panels.precip, key: pick(METEOGRAM_SERIES.precipitation), label: `${t('meteogram.chart.panelPrecipitation')} mm`, digits: 2 },
    { shown: panels.cloud, key: pick(METEOGRAM_SERIES.cloudCover), label: t('meteogram.chart.seriesTotalCloud'), digits: 0, percent: true },
    { shown: panels.cloud, key: pick(METEOGRAM_SERIES.cloudCoverLow), label: t('meteogram.chart.seriesLowClouds'), digits: 0, percent: true },
    { shown: panels.cloud, key: pick(METEOGRAM_SERIES.cloudCoverMid), label: t('meteogram.chart.seriesMidClouds'), digits: 0, percent: true },
    { shown: panels.cloud, key: pick(METEOGRAM_SERIES.cloudCoverHigh), label: t('meteogram.chart.seriesHighClouds'), digits: 0, percent: true },
    { shown: panels.pressure, key: pick(METEOGRAM_SERIES.pressure), label: t('meteogram.chart.seriesPressure'), digits: 1 },
  ]
  const columns = specs.filter((spec): spec is typeof spec & { key: string } => spec.shown && spec.key !== undefined)
  if (!columns.length)
    return null

  const firstTime = Math.min(...[...series.values()].flatMap(s => s.x.map(d => d.getTime())))
  const lastShown = horizonHours.value !== null ? firstTime + horizonHours.value * 3_600_000 : Number.POSITIVE_INFINITY
  const byTime = new Map<number, (number | null)[]>()
  columns.forEach((column, index) => {
    const s = series.get(column.key)!
    // a fraction or an oktas count is a percentage on the chart, and so here
    const scale = column.percent ? cloudScaleFactor(s.y) : 1
    s.x.forEach((date, i) => {
      const ms = date.getTime()
      if (ms > lastShown)
        return
      const row = byTime.get(ms) ?? Array.from<number | null>({ length: columns.length }).fill(null)
      row[index] = s.y[i]! * scale
      byTime.set(ms, row)
    })
  })
  const times = [...byTime.keys()].sort((a, b) => a - b)
  if (!times.length)
    return null

  const writeTime = (ms: number) => DateTime.fromMillis(ms, { zone: stationTimeZone.value }).setLocale(language.value).toLocaleString(DateTime.DATETIME_SHORT)
  const main = columns.findIndex(column => column.main)
  const temperatures = main < 0 ? [] : times.map(ms => byTime.get(ms)![main]).filter((v): v is number => v !== null && v !== undefined)
  return {
    columns: [t('meteogram.chart.tableTime', { zone: stationTimeZone.value }), ...columns.map(column => column.label)],
    rows: times.map(ms => [
      writeTime(ms),
      ...byTime.get(ms)!.map((value, index) => value === null ? '–' : formatNumber(value, locale.value, columns[index]!.digits)),
    ]),
    summary: [
      t('meteogram.chart.summaryRange', { from: writeTime(times[0]!), to: writeTime(times.at(-1)!) }),
      ...(temperatures.length
        ? [t('meteogram.chart.summaryTemperature', { min: formatNumber(Math.min(...temperatures), locale.value, 1), max: formatNumber(Math.max(...temperatures), locale.value, 1) })]
        : []),
      t('common.chartTableHint'),
    ].join(' '),
  }
})
const summaryId = useId()
const chartLabel = computed(() => props.stationName ? t('meteogram.chart.label', { name: props.stationName }) : t('meteogram.chart.labelNoStation'))

// Calculate summary statistics for the loaded forecast period
const summaryStats = computed(() => {
  const series = seriesCache.value
  if (!series.size)
    return null
  const available = new Set(series.keys())

  const tempKey = findFirstAvailable(METEOGRAM_SERIES.temperature, available)
  const precipKey = findFirstAvailable(METEOGRAM_SERIES.precipitation, available)
  const gustKey = findFirstAvailable(METEOGRAM_SERIES.gust, available)
  const cloudKey = findFirstAvailable(METEOGRAM_SERIES.cloudCover, available)
  const pressureKey = findFirstAvailable(METEOGRAM_SERIES.pressure, available)

  let minTemp = Number.POSITIVE_INFINITY
  let maxTemp = Number.NEGATIVE_INFINITY
  if (tempKey && series.has(tempKey)) {
    const s = series.get(tempKey)!
    s.y.forEach((v) => {
      if (v !== null && !Number.isNaN(v)) {
        minTemp = Math.min(minTemp, v)
        maxTemp = Math.max(maxTemp, v)
      }
    })
  }

  let totalPrecip = 0
  if (precipKey && series.has(precipKey)) {
    const s = series.get(precipKey)!
    s.y.forEach((v) => {
      if (v !== null && !Number.isNaN(v)) {
        totalPrecip += v
      }
    })
  }

  let maxGust = 0
  if (gustKey && series.has(gustKey)) {
    const s = series.get(gustKey)!
    s.y.forEach((v) => {
      if (v !== null && !Number.isNaN(v)) {
        maxGust = Math.max(maxGust, v)
      }
    })
  }

  let avgCloud = 0
  if (cloudKey && series.has(cloudKey)) {
    const s = series.get(cloudKey)!
    const valid = s.y.filter(v => v !== null && !Number.isNaN(v))
    if (valid.length > 0) {
      const sum = valid.reduce((acc, val) => acc + val, 0)
      const scale = cloudScaleFactor(valid)
      avgCloud = (sum / valid.length) * scale
    }
  }

  let minPres = Number.POSITIVE_INFINITY
  let maxPres = Number.NEGATIVE_INFINITY
  if (pressureKey && series.has(pressureKey)) {
    const s = series.get(pressureKey)!
    s.y.forEach((v) => {
      if (v !== null && !Number.isNaN(v)) {
        minPres = Math.min(minPres, v)
        maxPres = Math.max(maxPres, v)
      }
    })
  }

  return {
    temp: Number.isFinite(minTemp) ? { min: Math.round(minTemp), max: Math.round(maxTemp) } : null,
    precip: totalPrecip,
    gust: maxGust,
    cloud: Math.round(avgCloud),
    pressure: Number.isFinite(minPres) ? { min: Math.round(minPres), max: Math.round(maxPres) } : null,
  }
})

function ensureOverlay() {
  if (!chartRef.value)
    return
  if (!overlayCanvas) {
    const c = document.createElement('canvas')
    c.className = 'meteogram-overlay-canvas'
    c.style.position = 'absolute'
    c.style.left = '0'
    c.style.top = '0'
    c.style.width = '100%'
    c.style.height = '100%'
    c.style.pointerEvents = 'none'
    c.style.zIndex = '11'
    const el = chartRef.value
    const cs = window.getComputedStyle(el)
    if (cs.position === 'static')
      el.style.position = 'relative'
    el.appendChild(c)
    overlayCanvas = c
  }
}

function cleanupOverlay() {
  try {
    if (overlayRedrawHandler && typeof window !== 'undefined') {
      try {
        window.removeEventListener('resize', overlayRedrawHandler)
      }
      catch {
        // ignore
      }
    }
  }
  catch {
    // ignore
  }
  try {
    if (overlayCanvas && overlayCanvas.parentElement) {
      overlayCanvas.parentElement.removeChild(overlayCanvas)
    }
  }
  catch {
    // ignore
  }
  overlayCanvas = null
  overlayAttached = false
  overlayRedrawHandler = null
}

function updateOverlaySize() {
  if (!overlayCanvas || !chartRef.value)
    return
  const dpr = window.devicePixelRatio || 1
  const w = chartRef.value.clientWidth
  const h = chartRef.value.clientHeight
  overlayCanvas.width = Math.round(w * dpr)
  overlayCanvas.height = Math.round(h * dpr)
  overlayCanvas.style.width = `${w}px`
  overlayCanvas.style.height = `${h}px`
  const ctx = overlayCanvas.getContext('2d')
  if (!ctx)
    return
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.scale(dpr, dpr)
  ctx.clearRect(0, 0, w, h)
}

function drawBarb(ctx: CanvasRenderingContext2D, px: number, py: number, dirFrom: number, speed: number) {
  // Standard meteorological wind barbs: speed encoded in knots
  // Pennant = 50 kt, full barb = 10 kt, half barb = 5 kt
  // A knot is a nautical mile -- 1852 m exactly -- per hour, which is how the API converts it too;
  // rounded to 1.944 a speed either side of a barb boundary could be drawn as the next barb up
  const kt = (speed * 3600) / 1852
  const scale = compact.value ? 0.78 : 1.0
  // in the colours the chart was drawn in, which a switch of the scheme is yet to redraw it in
  const barbColor = (drawnTheme ?? theme.value).textStrong
  ctx.strokeStyle = barbColor
  ctx.fillStyle = barbColor
  ctx.lineWidth = Math.max(1, 1.5 * scale)

  if (kt < 2.5) {
    // Calm: draw a small circle at the observation point
    ctx.beginPath()
    ctx.arc(px, py, Math.round(4 * scale), 0, 2 * Math.PI)
    ctx.stroke()
    return
  }

  // Shaft: tip at (px, py), tail extends in the "from" direction
  const rad = (dirFrom * Math.PI) / 180
  const shaftLen = Math.round(20 * scale)
  const tailX = px + shaftLen * Math.sin(rad)
  const tailY = py - shaftLen * Math.cos(rad)
  const shaftUX = (tailX - px) / shaftLen
  const shaftUY = (tailY - py) / shaftLen

  // Barb perpendicular: 90° CW from tip→tail = left of wind (NH convention)
  const barbPerpX = -Math.cos(rad)
  const barbPerpY = -Math.sin(rad)
  const barbLen = Math.round(8 * scale)
  const barbSpacing = Math.round(5 * scale)

  let remaining = kt
  const pennants = Math.floor(remaining / 50)
  remaining -= pennants * 50
  const fullBarbs = Math.floor(remaining / 10)
  remaining -= fullBarbs * 10
  const halfBarbs = remaining >= 5 ? 1 : 0

  ctx.beginPath()
  ctx.moveTo(px, py)
  ctx.lineTo(tailX, tailY)
  ctx.stroke()

  let offset = 0
  for (let i = 0; i < pennants; i++) {
    const bx = tailX - offset * shaftUX
    const by = tailY - offset * shaftUY
    const bx2 = tailX - (offset + barbSpacing * 2) * shaftUX
    const by2 = tailY - (offset + barbSpacing * 2) * shaftUY
    ctx.beginPath()
    ctx.moveTo(bx, by)
    ctx.lineTo(bx + barbLen * barbPerpX, by + barbLen * barbPerpY)
    ctx.lineTo(bx2, by2)
    ctx.closePath()
    ctx.fill()
    offset += barbSpacing * 2 + Math.round(2 * scale)
  }
  for (let i = 0; i < fullBarbs; i++) {
    const bx = tailX - offset * shaftUX
    const by = tailY - offset * shaftUY
    ctx.beginPath()
    ctx.moveTo(bx, by)
    ctx.lineTo(bx + barbLen * barbPerpX, by + barbLen * barbPerpY)
    ctx.stroke()
    offset += barbSpacing
  }
  if (halfBarbs > 0) {
    if (pennants === 0 && fullBarbs === 0)
      offset += barbSpacing
    const bx = tailX - offset * shaftUX
    const by = tailY - offset * shaftUY
    ctx.beginPath()
    ctx.moveTo(bx, by)
    ctx.lineTo(bx + Math.round(barbLen * 0.5) * barbPerpX, by + Math.round(barbLen * 0.5) * barbPerpY)
    ctx.stroke()
  }
}

function drawWindBarbs(arrowInfos: { timeMs: number, dir: number, speed: number }[], minTime: number, maxTime: number, layoutObj: any, axisRange: [number, number], axisDomain: [number, number]) {
  if (!chartRef.value || !visiblePanels.value.wind)
    return
  ensureOverlay()
  updateOverlaySize()
  if (!overlayCanvas)
    return
  const ctx = overlayCanvas.getContext('2d')
  if (!ctx)
    return

  const rect = chartRef.value.getBoundingClientRect()
  const margin = layoutObj?.margin ?? { l: 48, r: 8, t: 8, b: 32 }
  const plotLeft = margin.l
  const plotTop = margin.t
  const plotWidth = rect.width - margin.l - margin.r
  const plotHeight = rect.height - margin.t - margin.b

  function xToPx(timeMs: number) {
    const t = (timeMs - minTime) / Math.max(1, (maxTime - minTime))
    return plotLeft + t * plotWidth
  }

  const domainLow = axisDomain[0]
  const domainHigh = axisDomain[1]
  const axisMin = axisRange[0]
  const axisMax = axisRange[1]

  function yToPx(value: number) {
    const frac = (value - axisMin) / Math.max(1e-6, (axisMax - axisMin))
    const paperY = domainLow + frac * (domainHigh - domainLow)
    return plotTop + (1 - paperY) * plotHeight
  }

  // Clip to the plot area so barbs outside the visible time window
  // (e.g. after zooming) cannot bleed into the margins.
  ctx.save()
  ctx.beginPath()
  ctx.rect(plotLeft, plotTop, plotWidth, plotHeight)
  ctx.clip()

  for (const a of arrowInfos) {
    const px = xToPx(a.timeMs)
    const py = yToPx(a.speed)
    drawBarb(ctx, px, py, a.dir, a.speed)
  }

  ctx.restore()
}

function attachOverlayListeners(getParams: () => { arrowInfos: { timeMs: number, dir: number, speed: number }[], minTime: number, maxTime: number, layoutObj: any, axisRange: [number, number], axisDomain: [number, number] }) {
  if (!chartRef.value)
    return
  if (overlayAttached)
    return
  // plotly_relayout fires BEFORE _fullLayout is updated, so drawing barbs
  // there uses a stale range and produces misplaced artefacts. Just clear
  // the canvas immediately so the wind panel is blank while Plotly re-renders
  // its SVG, then do the real redraw in plotly_afterplot when _fullLayout is
  // definitively up to date.
  const clearOnly = () => {
    ensureOverlay()
    updateOverlaySize() // resets canvas & clears
  }

  const redraw = () => {
    const p = getParams()
    // Read the live zoomed range from Plotly's internal layout so barbs are
    // positioned against the current viewport, not the full data span.
    let minTime = p.minTime
    let maxTime = p.maxTime
    try {
      const xRange = (chartRef.value as any)?._fullLayout?.xaxis?.range
      if (xRange?.[0] != null && xRange?.[1] != null) {
        const t0 = new Date(xRange[0]).getTime()
        const t1 = new Date(xRange[1]).getTime()
        if (Number.isFinite(t0) && Number.isFinite(t1) && t0 < t1) {
          minTime = t0
          maxTime = t1
        }
      }
    }
    catch { /* ignore */ }
    drawWindBarbs(p.arrowInfos, minTime, maxTime, p.layoutObj, p.axisRange, p.axisDomain)
  }
  try {
    if ((chartRef.value as any).on) {
      ;(chartRef.value as any).on('plotly_relayout', clearOnly)
      ;(chartRef.value as any).on('plotly_afterplot', redraw)
      ;(chartRef.value as any).__overlay_handlers = ((chartRef.value as any).__overlay_handlers || [])
      ;(chartRef.value as any).__overlay_handlers.push({ name: 'plotly_relayout', fn: clearOnly })
      ;(chartRef.value as any).__overlay_handlers.push({ name: 'plotly_afterplot', fn: redraw })
    }
  }
  catch {
    // ignore
  }
  overlayRedrawHandler = redraw
  window.addEventListener('resize', redraw)
  overlayAttached = true
  // Plotly emits plotly_afterplot of the drawing before the promise of newPlot resolves, and these
  // handlers are attached once it has: the chart's first afterplot is already gone. Without this
  // the barbs are absent until something makes Plotly draw again (a resize of the window).
  redraw()
}

function cleanupPlotlyOverlayHandlers() {
  if (!chartRef.value)
    return
  try {
    const el = chartRef.value as any
    const handlers = el.__overlay_handlers as { name: string, fn: any }[] | undefined
    if (handlers && el.removeAllListeners) {
      for (const h of handlers) {
        try {
          if (el.removeListener) {
            el.removeListener(h.name, h.fn)
          }
        }
        catch {
          // ignore
        }
        try {
          if (el.removeAllListeners) {
            el.removeAllListeners(h.name)
          }
        }
        catch {
          // ignore
        }
      }
    }
    el.__overlay_handlers = []
  }
  catch {
    // ignore
  }
}

function findFirstAvailable(names: readonly string[], available: Set<string>) {
  for (const n of names) {
    if (available.has(n))
      return n
  }
  return undefined
}

function cloudScaleFactor(values: number[]): number {
  const maxY = values.length > 0 ? Math.max(...values) : 0
  if (maxY <= 1.01)
    return 100 // fraction 0–1 → percent
  if (maxY <= 8.01)
    return 12.5 // oktas 0–8 → percent
  return 1
}

function buildSeries(values: Value[]) {
  const series = new Map<string, { x: Date[], y: number[] }>()
  for (const v of values) {
    const p = String(v.parameter)
    if (!series.has(p))
      series.set(p, { x: [], y: [] })
    if (v.value !== null && v.value !== undefined) {
      series.get(p)!.x.push(new Date(v.timestamp))
      series.get(p)!.y.push(v.value)
    }
  }
  for (const [, s] of series) {
    const pairs = s.x.map((d, i) => ({ d, y: s.y[i]! })).sort((a, b) => a.d.getTime() - b.d.getTime())
    s.x = pairs.map(p => p.d)
    s.y = pairs.map(p => p.y)
  }
  return series
}

function windArrow(fromDeg: number): string {
  const a = ['↓', '↙', '←', '↖', '↑', '↗', '→', '↘']
  return a[Math.round(((fromDeg % 360) + 360) % 360 / 45) % 8]!
}

function getMidnights(startMs: number, endMs: number, tz: string = 'UTC'): Date[] {
  const result: Date[] = []
  let dt = DateTime.fromMillis(startMs, { zone: tz }).startOf('day').plus({ days: 1 })
  while (dt.toMillis() < endMs) {
    result.push(dt.toJSDate())
    dt = dt.plus({ days: 1 })
  }
  return result
}

function getCalendarDays(startMs: number, endMs: number, tz: string = 'UTC'): Date[] {
  const days: Date[] = []
  let dt = DateTime.fromMillis(startMs, { zone: tz }).startOf('day')
  const endDt = DateTime.fromMillis(endMs, { zone: tz }).startOf('day')
  while (dt.toMillis() <= endDt.toMillis()) {
    days.push(dt.toJSDate())
    dt = dt.plus({ days: 1 })
  }
  return days
}

function resampleSeries(
  series: Map<string, { x: Date[], y: number[] }>,
  minTime: number,
  maxTime: number,
  stepKeys: Set<string> = new Set(),
): Map<string, { x: Date[], y: number[] }> {
  const cadenceMs = resampleCadenceMs(minTime, maxTime)
  const resampled = new Map<string, { x: Date[], y: number[] }>()

  for (const [key, s] of series) {
    const newX: Date[] = []
    const newY: number[] = []
    const startTick = Math.ceil(minTime / cadenceMs) * cadenceMs
    for (let t = startTick; t <= maxTime; t += cadenceMs) {
      const val = stepKeys.has(key) ? nearestNeighbor(s.x, s.y, t) : interpSeries(s.x, s.y, t)
      if (val !== null) {
        newX.push(new Date(t))
        newY.push(val)
      }
    }
    if (newX.length > 0) {
      resampled.set(key, { x: newX, y: newY })
    }
  }
  return resampled
}

let isRendering = false
let renderPending = false
// The newest render threw -- Plotly's import or its drawing -- and the chart area says so; failures
// counted, so a Retry that fails too is told again
const renderFailed = ref(false)
const renderFailures = ref(0)
// The newest render could not import the chart's code: Plotly, or suncalc for the day bands. Where a
// redeploy has replaced its chunk, a Retry asks for the same chunk again and fails every time, and
// only reloading the page loads the new one: the chart area says so, and offers the reload. Set by
// the render under way, which is one at a time, and taken up as it fails
const chartCodeNotLoaded = ref(false)
let codeImportFailed = false
// a Retry that works hands its focus on to the chart it drew
const chartNotice = useTemplateRef<HTMLElement>('chartNotice')
useFocusAfterRetry(renderFailed, chartNotice, chartRef)

function importChartCode<T>(load: () => Promise<T>): Promise<T> {
  return load().catch((error) => {
    codeImportFailed = true
    throw error
  })
}

function reloadPage() {
  // forced: the user's click, not a reload loop, which is what Nuxt's guard stops. Unforced, a
  // second click within ten seconds of a first that did not help would do nothing
  reloadNuxtApp({ force: true })
}

async function renderChart() {
  if (isRendering) {
    renderPending = true
    return
  }
  isRendering = true
  renderPending = false

  codeImportFailed = false
  try {
    await renderChartActual()
    renderFailed.value = false
  }
  catch (error) {
    console.error('The chart could not be drawn', error)
    // a render queued meanwhile draws next, and tells its own outcome
    if (!renderPending) {
      renderFailed.value = true
      chartCodeNotLoaded.value = codeImportFailed
      renderFailures.value++
    }
  }
  finally {
    isRendering = false
    if (renderPending) {
      void renderChart()
    }
  }
}

// Whether the next drawing keeps the zoom the chart is in: only a drawing in other colours (the scheme
// switched, a print) does, and drawings asked for are merged while one is under way, so a drawing for
// anything else (a horizon, a panel, new values) among them starts the chart over. null: none asked for
let keepZoomNext: boolean | null = null

function requestRender(keepZoom: boolean) {
  keepZoomNext = (keepZoomNext ?? true) && keepZoom
  void renderChart()
}

async function renderChartActual() {
  const keepZoom = keepZoomNext ?? false
  keepZoomNext = null
  await nextTick()
  if (!chartRef.value) {
    try {
      cleanupPlotlyOverlayHandlers()
    }
    catch {}
    try {
      cleanupOverlay()
    }
    catch {}
    return
  }

  const vals = props.values ?? []
  if (!vals.length) {
    try {
      cleanupPlotlyOverlayHandlers()
    }
    catch {}
    try {
      cleanupOverlay()
    }
    catch {}
    if (Plotly && chartRef.value)
      Plotly.purge(chartRef.value)
    return
  }

  if (!plotlyLoaded.value) {
    Plotly = await importChartCode(() => import('plotly.js-basic-dist-min'))
    plotlyLoaded.value = true
  }

  const series = seriesCache.value
  const available = new Set(series.keys())

  const tempKey = findFirstAvailable(METEOGRAM_SERIES.temperature, available)
  const precipKey = findFirstAvailable(METEOGRAM_SERIES.precipitation, available)
  const windKey = findFirstAvailable(METEOGRAM_SERIES.windSpeed, available)
  const windDirKey = findFirstAvailable(METEOGRAM_SERIES.windDirection, available)
  const gustKey = findFirstAvailable(METEOGRAM_SERIES.gust, available)
  const cloudKey = findFirstAvailable(METEOGRAM_SERIES.cloudCover, available)
  const cloudLowKey = findFirstAvailable(METEOGRAM_SERIES.cloudCoverLow, available)
  const cloudMidKey = findFirstAvailable(METEOGRAM_SERIES.cloudCoverMid, available)
  const cloudHighKey = findFirstAvailable(METEOGRAM_SERIES.cloudCoverHigh, available)
  const humidityKey = findFirstAvailable(METEOGRAM_SERIES.humidity, available)
  const dewKey = findFirstAvailable(METEOGRAM_SERIES.dewPoint, available)
  const pressureKey = findFirstAvailable(METEOGRAM_SERIES.pressure, available)
  const txKey = findFirstAvailable(METEOGRAM_SERIES.temperatureMax, available)
  const tnKey = findFirstAvailable(METEOGRAM_SERIES.temperatureMin, available)

  const allTimes = [...series.values()].flatMap(s => s.x.map(d => d.getTime()))
  const minTime = Math.min(...allTimes)
  const maxTime = Math.max(...allTimes)
  const displayMaxTime = horizonHours.value !== null
    ? Math.min(maxTime, minTime + horizonHours.value * 3_600_000)
    : maxTime

  // Resample all series to fixed cadence; precipitation uses nearest-neighbor (not interpolated)
  const precipStepKeys = new Set([precipKey].filter((k): k is string => !!k))
  const resampledSeries = resampleSeries(series, minTime, displayMaxTime, precipStepKeys)

  // Normalize cloud fraction parameters to percentages
  const cloudParams = [cloudKey, cloudLowKey, cloudMidKey, cloudHighKey].filter((x): x is string => !!x)
  for (const k of cloudParams) {
    if (!resampledSeries.has(k))
      continue
    const s = resampledSeries.get(k)!
    if (!s || !s.y || s.y.length === 0)
      continue
    const scale = cloudScaleFactor(s.y.map(v => v ?? 0))
    if (scale !== 1) {
      s.y = s.y.map(v => (v ?? 0) * scale)
      resampledSeries.set(k, s)
    }
  }

  // Build mapping of original ISO date strings
  const isoMap = new Map<number, string>()
  for (const v of vals) {
    try {
      const ms = new Date(String(v.timestamp)).getTime()
      if (!isoMap.has(ms))
        isoMap.set(ms, String(v.timestamp))
    }
    catch { /* ignore */ }
  }
  const isoMs = Array.from(isoMap.keys()).sort((a, b) => a - b)
  const isoDates = isoMs.map(m => new Date(m))

  // Determine timezone
  let stationTZ = 'UTC'
  if (props.stationCoords?.latitude != null && props.stationCoords?.longitude != null) {
    try {
      stationTZ = tzLookup(props.stationCoords.latitude, props.stationCoords.longitude)
    }
    catch {
      stationTZ = 'UTC'
    }
  }

  // Build custom tick values & labels
  let customTickVals: string[] | undefined
  let customTickText: string[] | undefined
  // extra layout padding requested by annotations (top/right)
  const extraTop = 0
  const extraRight = 0
  const annotations: any[] = []

  // Available plot width drives tick density — avoids overlap on narrow mobile screens.
  const plotInnerWidth = Math.max(200, (chartRef.value?.clientWidth ?? 800) - 56)
  const rangeHours = (displayMaxTime - minTime) / 3_600_000

  if (isoDates.length > 0) {
    // Each "HH:mm" label needs ~36 px minimum to avoid overlap.
    const maxTicks = Math.floor(plotInnerWidth / 36)
    let tickMs: number
    if (rangeHours <= 24) {
      tickMs = 1 * 3_600_000
    }
    else if (rangeHours <= 48 && maxTicks >= 16) {
      tickMs = 3 * 3_600_000
    }
    else if (rangeHours <= 48) {
      tickMs = 6 * 3_600_000
    }
    else {
      // Pick the coarsest granularity that still fits within maxTicks.
      const candidates = [6, 12, 24, 48]
      tickMs = 24 * 3_600_000
      for (const h of candidates) {
        if (Math.ceil(rangeHours / h) <= maxTicks) {
          tickMs = h * 3_600_000
          break
        }
      }
    }

    const startTick = Math.ceil(minTime / tickMs) * tickMs
    const tickVals: string[] = []
    const tickText: string[] = []
    for (let t = startTick; t <= displayMaxTime; t += tickMs) {
      tickVals.push(new Date(t).toISOString())
      try {
        const utcDt = DateTime.fromMillis(t, { zone: 'UTC' })
        const localDt = utcDt.setZone(stationTZ)
        const label = localDt.toFormat('HH:mm')
        tickText.push(label)
      }
      catch {
        const d = new Date(t)
        const label = `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`
        tickText.push(label)
      }
    }
    customTickVals = tickVals
    customTickText = tickText

    // Compute a toolbar-friendly timezone label and store it for display above the chart.
    try {
      let tzLabel = stationTZ
      try {
        const offsetMin = DateTime.fromMillis(minTime, { zone: stationTZ }).offset
        const sign = offsetMin >= 0 ? '+' : '-'
        const h = String(Math.floor(Math.abs(offsetMin) / 60)).padStart(2, '0')
        const m = String(Math.abs(offsetMin) % 60).padStart(2, '0')
        tzLabel = `${stationTZ} (UTC${sign}${h}:${m})`
      }
      catch {
        // ignore offset formatting errors
      }
      toolbarTzLabel.value = tzLabel
      // keep extraTop/extraRight at defaults (we no longer need extra plot margins)
    }
    catch {
      // ignore
    }
  }

  // Build cloud fraction lookup
  const cloudMap = new Map<number, number>()
  if (cloudKey) {
    const cs = resampledSeries.get(cloudKey)!
    cs.x.forEach((d, i) => cloudMap.set(d.getTime(), (cs.y[i] ?? 0) / 100))
  }

  // Build per-day day-band shapes
  const dayShapes: any[] = []
  const days = getCalendarDays(minTime, displayMaxTime, stationTZ)
  if (props.stationCoords && props.stationCoords.latitude != null && props.stationCoords.longitude != null) {
    SunCalc ??= await importChartCode(() => import('suncalc'))
    const lat = props.stationCoords.latitude
    const lon = props.stationCoords.longitude
    for (const day of days) {
      const localDayDt = DateTime.fromMillis(day.getTime(), { zone: stationTZ })
      const localNoon = localDayDt.plus({ hours: 12 }).toJSDate()
      const times: SunTimes = SunCalc.getTimes(localNoon, lat, lon)
      const sunrise = times.sunrise ?? times.sunriseEnd ?? localDayDt.plus({ hours: 4 }).toJSDate()
      const sunset = times.sunset ?? times.sunsetStart ?? localDayDt.plus({ hours: 20 }).toJSDate()
      const middayCf = cloudMap.get(localNoon.getTime()) ?? 0
      const alpha = 0.55 - Math.min(0.35, middayCf * 0.5)
      dayShapes.push({
        type: 'rect',
        xref: 'x',
        yref: 'paper',
        x0: sunrise.toISOString(),
        x1: sunset.toISOString(),
        y0: 0,
        y1: 1,
        fillcolor: isDark.value ? `rgba(250,204,21,${alpha * 0.15})` : `rgba(253,244,180,${alpha})`,
        line: { width: 0 },
        layer: 'below',
      })
    }
  }
  else {
    for (const day of days) {
      const localDayDt = DateTime.fromMillis(day.getTime(), { zone: stationTZ })
      const x0 = localDayDt.plus({ hours: 4 }).toJSDate()
      const x1 = localDayDt.plus({ hours: 20 }).toJSDate()
      dayShapes.push({
        type: 'rect',
        xref: 'x',
        yref: 'paper',
        x0: x0.toISOString(),
        x1: x1.toISOString(),
        y0: 0,
        y1: 1,
        fillcolor: isDark.value ? 'rgba(250,204,21,0.08)' : 'rgba(253,244,180,0.55)',
        line: { width: 0 },
        layer: 'below',
      })
    }
  }

  // Day separators
  const separators: any[] = getMidnights(minTime, displayMaxTime, stationTZ).map(m => ({
    type: 'line',
    xref: 'x',
    yref: 'paper',
    x0: m.toISOString(),
    x1: m.toISOString(),
    y0: 0,
    y1: 1,
    line: { color: isDark.value ? 'rgba(244,244,245,0.08)' : 'rgba(55,65,81,0.08)', width: 1, dash: 'dot' },
  }))

  // "Now" marker
  const nowMs = Date.now()
  if (nowMs > minTime && nowMs < displayMaxTime) {
    separators.push({
      type: 'line',
      xref: 'x',
      yref: 'paper',
      x0: new Date(nowMs).toISOString(),
      x1: new Date(nowMs).toISOString(),
      y0: 0,
      y1: 1,
      line: { color: isDark.value ? 'rgba(251,146,60,0.75)' : 'rgba(234,88,12,0.75)', width: 1.5 },
    })
  }

  // Day names annotations (all date parts computed in station-local timezone)
  const totalDays = Math.max(1, rangeHours / 24)
  const dayWidthPx = plotInnerWidth / totalDays
  for (const day of getCalendarDays(minTime, displayMaxTime, stationTZ)) {
    const localDt = DateTime.fromMillis(day.getTime(), { zone: stationTZ })
    const tenAm = localDt.plus({ hours: 10 }).toJSDate()
    if (tenAm.getTime() < minTime || tenAm.getTime() > displayMaxTime)
      continue
    const dayMonth = formatDayMonth(localDt, language.value)
    const isWeekend = localDt.weekday >= 6 // 6=Sat, 7=Sun in Luxon
    // On narrow screens drop the date suffix to prevent overlap; shrink font below 50 px/day.
    const annotFontSize = dayWidthPx < 50 ? 8 : 10
    // The date is 5.5 px per character wide or more: 44 px for the eight characters of "Mo 05.10", which
    // a language that writes the date longer ("Čt 15. 10.") needs more of
    const weekday = weekdayShort(localDt, language.value)
    const annotText = dayWidthPx < 5.5 * `${weekday} ${dayMonth}`.length
      ? `<b>${weekday}</b>`
      : `<b>${weekday}</b> ${dayMonth}`
    annotations.push({
      x: tenAm.toISOString(),
      y: 1.06,
      xref: 'x',
      yref: 'paper',
      text: annotText,
      showarrow: false,
      font: { size: annotFontSize, color: isWeekend ? '#ef4444' : theme.value.text },
      xanchor: 'center',
      yanchor: 'bottom',
    })
  }

  // Traces
  const traces: any[] = []

  // 1. Temperature & Dew Point
  let tempMinY = 0
  let tempMaxY = 25
  if (tempKey && visiblePanels.value.temp) {
    const s = resampledSeries.get(tempKey)!
    tempMinY = Math.min(0, ...s.y)
    tempMaxY = Math.max(...s.y)
    const xs = s.x.map(d => d.toISOString())

    // The maximum and minimum are held across the hours each covers, not resampled to a line between
    // their few stamps, which let the curve out of the band (GH-2647)
    const stepMs = resampleCadenceMs(minTime, displayMaxTime)
    const extremeSteps = (key: string | undefined) => {
      const raw = key ? series.get(key) : undefined
      return raw ? extremeWindowSteps(raw.x, raw.y, extremeWindowHours(key!) * 3_600_000, minTime, displayMaxTime, stepMs) : null
    }
    const sTx = extremeSteps(txKey)
    const sTn = extremeSteps(tnKey)
    const hasTxTn = !!(sTx?.x.length && sTn?.x.length)

    const dewLookup = new Map<string, number>()
    if (dewKey && resampledSeries.has(dewKey)) {
      const ds = resampledSeries.get(dewKey)!
      ds.x.forEach((d, i) => dewLookup.set(d.toISOString(), ds.y[i]!))
    }
    else if (humidityKey && resampledSeries.has(humidityKey)) {
      const hs = resampledSeries.get(humidityKey)!
      for (let i = 0; i < xs.length; i++) {
        const tMs = new Date(xs[i]!).getTime()
        const rh = interpSeries(hs.x, hs.y, tMs)
        const T = s.y[i]
        if (rh !== null && T !== undefined && !Number.isNaN(T)) {
          let rhPct = rh
          if (rhPct <= 1)
            rhPct = rhPct * 100
          const a = 17.27
          const b = 237.7
          const alpha = (a * T) / (b + T) + Math.log(rhPct / 100)
          const td = (b * alpha) / (a - alpha)
          dewLookup.set(xs[i]!, td)
        }
      }
    }

    traces.push({
      name: hasTxTn ? t('meteogram.chart.seriesMeanTemp') : t('meteogram.chart.seriesTemperature'),
      x: xs,
      y: s.y,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#ef4444', width: 2, shape: 'spline' },
      fill: 'tozeroy',
      fillcolor: isDark.value ? 'rgba(239,68,68,0.02)' : 'rgba(239,68,68,0.04)',
      yaxis: 'y3',
      hovertemplate: hasTxTn
        ? `<b>${t('meteogram.chart.hoverMeanTemp')}</b>: %{y:.1f}°C<extra></extra>`
        : `<b>${t('meteogram.chart.hoverTemperature')}</b>: %{y:.1f}°C<extra></extra>`,
    })

    if (hasTxTn && sTx && sTn) {
      traces.push({
        name: t('meteogram.chart.seriesMaxTemp'),
        x: sTx.x.map(d => d.toISOString()),
        y: sTx.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: isDark.value ? '#fca5a5' : '#b91c1c', width: 1.5, dash: 'dash', shape: 'vh' },
        yaxis: 'y3',
        hovertemplate: `<b>${t('meteogram.chart.hoverMaxTemp')}</b>: %{y:.1f}°C<extra></extra>`,
        showlegend: false,
      })
      traces.push({
        name: t('meteogram.chart.seriesMinTemp'),
        x: sTn.x.map(d => d.toISOString()),
        y: sTn.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: isDark.value ? '#93c5fd' : '#1d4ed8', width: 1.5, dash: 'dash', shape: 'vh' },
        yaxis: 'y3',
        hovertemplate: `<b>${t('meteogram.chart.hoverMinTemp')}</b>: %{y:.1f}°C<extra></extra>`,
        showlegend: false,
      })
      tempMinY = Math.min(tempMinY, ...sTn.y.filter((v): v is number => v !== null))
      tempMaxY = Math.max(tempMaxY, ...sTx.y.filter((v): v is number => v !== null))
    }

    if (dewKey && resampledSeries.has(dewKey)) {
      const ds = resampledSeries.get(dewKey)!
      const dxs = ds.x.map(d => d.toISOString())
      traces.push({
        name: t('meteogram.chart.seriesDewPoint'),
        x: dxs,
        y: ds.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: '#a855f7', width: 1.6, shape: 'spline' },
        yaxis: 'y3',
        hovertemplate: `<b>${t('meteogram.chart.hoverDewPoint')}</b>: %{y:.1f}°C<extra></extra>`,
        showlegend: false,
      })
      tempMinY = Math.min(tempMinY, ...ds.y)
      tempMaxY = Math.max(tempMaxY, ...ds.y)
    }
    else if (humidityKey && resampledSeries.has(humidityKey)) {
      const hs = resampledSeries.get(humidityKey)!
      const dewXs: string[] = []
      const dewYs: number[] = []
      for (let i = 0; i < xs.length; i++) {
        const tIso = xs[i]!
        const tMs = new Date(tIso).getTime()
        const rh = interpSeries(hs.x, hs.y, tMs)
        if (rh === null || rh === undefined)
          continue
        let rhPct = rh
        if (rhPct <= 1)
          rhPct = rhPct * 100
        const a = 17.27
        const b = 237.7
        const T = s.y[i] ?? Number.NaN
        if (Number.isNaN(T) || rhPct <= 0)
          continue
        const alpha = (a * T) / (b + T) + Math.log(rhPct / 100)
        const td = (b * alpha) / (a - alpha)
        dewXs.push(tIso)
        dewYs.push(td)
      }
      if (dewXs.length) {
        traces.push({
          name: t('meteogram.chart.seriesDewPoint'),
          x: dewXs,
          y: dewYs,
          type: 'scatter',
          mode: 'lines',
          line: { color: '#a855f7', width: 1.6, shape: 'spline' },
          yaxis: 'y3',
          hovertemplate: `<b>${t('meteogram.chart.hoverDewPoint')}</b>: %{y:.1f}°C<extra></extra>`,
          showlegend: false,
        })
        tempMinY = Math.min(tempMinY, ...dewYs)
        tempMaxY = Math.max(tempMaxY, ...dewYs)
      }
    }
  }

  // 2. Precipitation
  if (precipKey && visiblePanels.value.precip) {
    const s = resampledSeries.get(precipKey)!
    const rainYs: number[] = []
    const snowYs: number[] = []
    const mixedYs: number[] = []
    const pxs = s.x.map(d => d.toISOString())
    for (let i = 0; i < pxs.length; i++) {
      const tIso = pxs[i]!
      const pVal = s.y[i] ?? 0
      let isSnow = false
      let isMixed = false
      if (tempKey && resampledSeries.has(tempKey)) {
        const tSeries = resampledSeries.get(tempKey)!
        const tval = interpSeries(tSeries.x, tSeries.y, new Date(tIso).getTime())
        if (tval !== null && !Number.isNaN(tval)) {
          let tw = tval
          if (humidityKey && resampledSeries.has(humidityKey)) {
            const hSeries = resampledSeries.get(humidityKey)!
            const rh = interpSeries(hSeries.x, hSeries.y, new Date(tIso).getTime())
            if (rh !== null) {
              let rhPct = rh
              if (rhPct <= 1)
                rhPct = rhPct * 100
              tw = wetBulbApprox(tval, rhPct)
            }
          }
          if (tw <= 0.5)
            isSnow = true
          else if (tw <= 2.0)
            isMixed = true
          else isSnow = false
        }
      }
      if (isSnow) {
        snowYs.push(pVal)
        rainYs.push(0)
        mixedYs.push(0)
      }
      else if (isMixed) {
        mixedYs.push(pVal)
        rainYs.push(0)
        snowYs.push(0)
      }
      else {
        rainYs.push(pVal)
        snowYs.push(0)
        mixedYs.push(0)
      }
    }

    traces.push({ name: t('meteogram.chart.seriesRain'), x: pxs, y: rainYs, type: 'bar', marker: { color: '#3b82f6' }, yaxis: 'y2', hovertemplate: `<b>${t('meteogram.chart.hoverRain')}</b><br>%{y:.2f} mm<extra></extra>`, visible: true })
    traces.push({ name: t('meteogram.chart.seriesMixed'), x: pxs, y: mixedYs, type: 'bar', marker: { color: '#0ea5e9' }, yaxis: 'y2', hovertemplate: `<b>${t('meteogram.chart.hoverMixed')}</b><br>%{y:.2f} mm<extra></extra>`, visible: true })
    traces.push({ name: t('meteogram.chart.seriesSnow'), x: pxs, y: snowYs, type: 'bar', marker: { color: isDark.value ? '#9ca3af' : '#cbd5e1' }, yaxis: 'y2', hovertemplate: `<b>${t('meteogram.chart.hoverSnow')}</b><br>%{y:.2f} mm<extra></extra>`, visible: true })
  }

  // 3. Pressure
  let pressureMin = 1000
  let pressureMax = 1020
  if (pressureKey && visiblePanels.value.pressure) {
    const ps = resampledSeries.get(pressureKey)!
    const pxs = ps.x.map(d => d.toISOString())
    traces.push({
      name: t('meteogram.chart.seriesPressure'),
      x: pxs,
      y: ps.y,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#84cc16', width: 1.6, shape: 'spline' },
      fill: 'tozeroy',
      fillcolor: isDark.value ? 'rgba(132,204,22,0.02)' : 'rgba(132,204,22,0.04)',
      yaxis: 'y4',
      hovertemplate: `<b>${t('meteogram.chart.hoverPressure')}</b><br>%{y:.1f} hPa<extra></extra>`,
    })
    pressureMin = Math.min(...ps.y)
    pressureMax = Math.max(...ps.y)
  }

  // 4. Wind & Gusts
  let windMaxY = 10
  if (windKey && visiblePanels.value.wind) {
    const s = resampledSeries.get(windKey)!
    windMaxY = Math.max(...s.y, 5)

    const gustSeries = (gustKey && resampledSeries.has(gustKey)) ? resampledSeries.get(gustKey)! : undefined
    if (gustSeries) {
      windMaxY = Math.max(windMaxY, ...gustSeries.y)
    }

    // Build per-timestep direction lookup for wind speed hover
    const dirByMs = new Map<number, number>()
    if (windDirKey) {
      const dirS = resampledSeries.get(windDirKey)!
      dirS.x.forEach((d, i) => dirByMs.set(d.getTime(), Math.round(dirS.y[i]!)))
    }
    const windSpeedCustom = s.x.map(d => dirByMs.get(d.getTime()) ?? null)
    const hasDir = windSpeedCustom.some(v => v !== null)

    traces.push({
      name: t('meteogram.chart.seriesWind'),
      x: s.x.map(d => d.toISOString()),
      y: s.y,
      customdata: windSpeedCustom,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#06b6d4', width: 2, shape: 'spline' },
      fill: 'tozeroy',
      fillcolor: isDark.value ? 'rgba(6,182,212,0.04)' : 'rgba(6,182,212,0.08)',
      yaxis: 'y',
      hovertemplate: hasDir
        ? `<b>${t('meteogram.chart.hoverWind')}</b> %{y:.1f} m/s → %{customdata:.0f}°<extra></extra>`
        : `<b>${t('meteogram.chart.hoverWindSpeed')}</b> %{y:.1f} m/s<extra></extra>`,
    })

    if (gustSeries) {
      traces.push({
        name: t('meteogram.chart.seriesWindGust'),
        x: gustSeries.x.map(d => d.toISOString()),
        y: gustSeries.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: '#06b6d4', width: 1.6, dash: 'dash', shape: 'spline' },
        yaxis: 'y',
        hovertemplate: `<b>${t('meteogram.chart.hoverWindGust')}</b> %{y:.1f} m/s<extra></extra>`,
      })
    }

    if (windDirKey) {
      const dirS = resampledSeries.get(windDirKey)!
      const dirMap = new Map<number, number>()
      dirS.x.forEach((d, i) => dirMap.set(d.getTime(), dirS.y[i]!))

      const arrowX: string[] = []
      const arrowText: string[] = []
      s.x.forEach((date, i) => {
        if (i % 3 !== 0)
          return
        const dir = dirMap.get(date.getTime())
        if (dir !== undefined) {
          arrowX.push(date.toISOString())
          arrowText.push(windArrow(dir))
        }
      })

      traces.push({
        name: t('meteogram.chart.seriesDirection'),
        x: arrowX,
        y: Array.from({ length: arrowX.length }).fill(windMaxY * 1.36),
        text: arrowText,
        type: 'scatter',
        mode: 'text',
        textfont: { size: 13, color: isDark.value ? 'rgba(255,255,255,0.7)' : 'rgba(15,23,42,0.85)' },
        hoverinfo: 'skip',
        yaxis: 'y',
        showlegend: false,
      })
    }
  }

  // 5. Cloud Layers (Low, Mid, High & Total)
  if (cloudKey && visiblePanels.value.cloud) {
    // Overlapping cloud layers by altitude
    if (cloudHighKey && resampledSeries.has(cloudHighKey)) {
      const s = resampledSeries.get(cloudHighKey)!
      traces.push({
        name: t('meteogram.chart.seriesHighClouds'),
        x: s.x.map(d => d.toISOString()),
        y: s.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: isDark.value ? '#64748b' : '#cbd5e1', width: 1, shape: 'spline' },
        fill: 'tozeroy',
        fillcolor: isDark.value ? 'rgba(148,163,184,0.1)' : 'rgba(203,213,225,0.15)',
        yaxis: 'y5',
        hovertemplate: `<b>${t('meteogram.chart.hoverHighClouds')}</b><br>%{y:.0f}%<extra></extra>`,
      })
    }

    if (cloudMidKey && resampledSeries.has(cloudMidKey)) {
      const s = resampledSeries.get(cloudMidKey)!
      traces.push({
        name: t('meteogram.chart.seriesMidClouds'),
        x: s.x.map(d => d.toISOString()),
        y: s.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: isDark.value ? '#475569' : '#94a3b8', width: 1, shape: 'spline' },
        fill: 'tozeroy',
        fillcolor: isDark.value ? 'rgba(100,116,139,0.15)' : 'rgba(148,163,184,0.22)',
        yaxis: 'y5',
        hovertemplate: `<b>${t('meteogram.chart.hoverMidClouds')}</b><br>%{y:.0f}%<extra></extra>`,
      })
    }

    if (cloudLowKey && resampledSeries.has(cloudLowKey)) {
      const s = resampledSeries.get(cloudLowKey)!
      traces.push({
        name: t('meteogram.chart.seriesLowClouds'),
        x: s.x.map(d => d.toISOString()),
        y: s.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: isDark.value ? '#334155' : '#64748b', width: 1, shape: 'spline' },
        fill: 'tozeroy',
        fillcolor: isDark.value ? 'rgba(71,85,105,0.22)' : 'rgba(100,116,139,0.3)',
        yaxis: 'y5',
        hovertemplate: `<b>${t('meteogram.chart.hoverLowClouds')}</b><br>%{y:.0f}%<extra></extra>`,
      })
    }

    // Total Cloud Cover line on top
    const s = resampledSeries.get(cloudKey)!
    traces.push({
      name: t('meteogram.chart.seriesTotalCloud'),
      x: s.x.map(d => d.toISOString()),
      y: s.y,
      type: 'scatter',
      mode: 'lines',
      line: { color: isDark.value ? '#e4e4e7' : '#334155', width: 2, shape: 'spline' },
      yaxis: 'y5',
      hovertemplate: `<b>${t('meteogram.chart.hoverTotalCloud')}</b><br>%{y:.0f}%<extra></extra>`,
    })
  }

  // Panel geometry calculations
  const gap = compact.value ? 0.006 : 0.01
  const panelOrder = [
    { id: 'wind', present: !!windKey && visiblePanels.value.wind },
    { id: 'precip', present: !!precipKey && visiblePanels.value.precip },
    { id: 'cloud', present: !!cloudKey && !compact.value && visiblePanels.value.cloud },
    { id: 'temp', present: !!tempKey && visiblePanels.value.temp },
    { id: 'pressure', present: !!pressureKey && visiblePanels.value.pressure },
  ]

  const panels = panelOrder.filter(p => p.present)
  const nPanels = Math.max(1, panels.length)
  const totalGap = gap * Math.max(0, nPanels - 1)
  const panelHeight = (1 - totalGap) / nPanels

  const domains: Record<string, [number, number]> = {}
  let currentTop = 1.0
  for (const p of panels) {
    const top = currentTop
    const bottom = top - panelHeight
    domains[p.id] = [bottom, top]
    currentTop = bottom - gap
  }

  // Dark-on-light or light-on-dark tokens
  // washes of the text colour for the hairlines; the tick labels are the muted text colour itself, as
  // a wash of 65 % of the text colour is 3.9:1 on white
  const W = (a: number) => withAlpha(theme.value.text, a)
  const GRID = W(0.08)
  const TICK = theme.value.textMuted
  const ZERO = W(0.20)

  // Panel divider lines
  const dividers: any[] = []
  const panelIds = panels.map(p => p.id)
  for (let i = 0; i < panelIds.length - 1; i++) {
    const id = panelIds[i]!
    const bottom = domains[id] ? domains[id][0] : 0
    const width = compact.value ? 0.8 : 1
    dividers.push({ type: 'line', xref: 'paper', yref: 'paper', x0: 0, x1: 1, y0: bottom, y1: bottom, line: { color: W(0.18), width } })
  }

  // Compute default axis ranges per panel
  const axisRanges: Record<string, [number, number]> = {}
  axisRanges.wind = [0, windMaxY * 1.60]

  if (precipKey && resampledSeries.has(precipKey)) {
    const ps = resampledSeries.get(precipKey)!
    const pMax = Math.max(...ps.y.map(v => (v ?? 0)))
    axisRanges.precip = [0, Math.max(1, pMax * 1.15)]
  }
  else {
    axisRanges.precip = [0, 1]
  }

  axisRanges.cloud = [0, 100]
  axisRanges.temp = [tempMinY - 1, tempMaxY + 3]
  axisRanges.pressure = [pressureMin - 2, pressureMax + 2]

  const originalRanges: Record<string, [number, number]> = {
    wind: [0, windMaxY * 1.60],
    precip: axisRanges.precip,
    cloud: [0, 100],
    temp: [tempMinY - 1, tempMaxY + 3],
    pressure: [pressureMin - 2, pressureMax + 2],
  }

  const nticksMap: Record<string, number> = { wind: 4, precip: 3, cloud: 3, temp: 4, pressure: 3 }
  const axisTickVals: Record<string, number[]> = {}

  function niceNum(range: number, round: boolean) {
    if (range <= 0)
      return 1
    const exp = Math.floor(Math.log10(range))
    const f = range / 10 ** exp
    let nf = 1
    if (round) {
      if (f < 1.5)
        nf = 1
      else if (f < 3)
        nf = 2
      else if (f < 7)
        nf = 5
      else nf = 10
    }
    else {
      if (f <= 1)
        nf = 1
      else if (f <= 2)
        nf = 2
      else if (f <= 5)
        nf = 5
      else nf = 10
    }
    return nf * 10 ** exp
  }

  function niceTickSpacing(range: number, n: number) {
    if (n <= 1)
      return Math.max(1, range)
    const raw = range / Math.max(1, n - 1)
    return niceNum(raw, true)
  }

  for (const k of Object.keys(nticksMap)) {
    const key = k as keyof typeof nticksMap
    const rng = originalRanges[key as string] || [0, 1]
    const lo = rng[0]
    const hi = rng[1]
    if (!(hi > lo)) {
      axisTickVals[key] = [lo]
      continue
    }
    const n = nticksMap[key]
    if (n === undefined)
      continue
    const adjustedN = compact.value ? Math.max(2, Math.round(n * 0.8)) : n
    const step = niceTickSpacing(hi - lo, adjustedN)
    const niceHi = Math.ceil(hi / step) * step
    const ticks: number[] = []
    const count = Math.max(1, Math.ceil((niceHi - lo) / step) + 1)
    for (let i = 0; i < count; i++) ticks.push(Number((lo + i * step).toFixed(6)))
    axisTickVals[key] = ticks
  }

  for (let i = 0; i < panels.length - 1; i++) {
    const belowId = panels[i + 1]!.id
    const belowTicks = axisTickVals[belowId] ?? []
    if (belowTicks.length > 0) {
      belowTicks.pop()
      axisTickVals[belowId] = belowTicks
    }
  }

  for (const k of Object.keys(originalRanges)) {
    const key = k as keyof typeof originalRanges
    const rng = originalRanges[key as string]
    if (!rng)
      continue
    const lo = rng[0]
    const hi = rng[1]
    if (!(hi > lo))
      continue
    const ticks = axisTickVals[key] ?? []
    if (ticks.length === 0)
      continue
    const step = niceTickSpacing(hi - lo, Math.max(2, ticks.length))
    const niceHi = Math.ceil(hi / step) * step
    const newCount = Math.max(1, Math.ceil((niceHi - lo) / step) + 1)
    const newTicks: number[] = []
    for (let i = 0; i < newCount; i++) newTicks.push(Number((lo + i * step).toFixed(6)))
    axisTickVals[key] = newTicks
  }

  // Filter traces dynamically depending on panel visibility
  const axisToPanel: Record<string, string> = { y: 'wind', y2: 'precip', y3: 'temp', y4: 'pressure', y5: 'cloud' }
  const activeTraces = traces.filter((tr) => {
    const yaxisName = tr.yaxis || 'y'
    const panelId = axisToPanel[yaxisName]
    return !panelId || visiblePanels.value[panelId as keyof typeof visiblePanels.value] !== false
  })

  // Layout
  const layout: any = {
    autosize: true,
    // the hover texts and the axes write the language's decimal separator, as Plotly writes a point otherwise
    separators: plotlySeparators(locale.value),
    margin: { l: 48, r: 8 + extraRight, t: (compact.value ? 44 : 72) + extraTop, b: compact.value ? 4 : 8 },
    font: { family: '"Inter", system-ui, sans-serif', size: 11 },
    hovermode: 'x unified',
    hoverlabel: { font: { family: '"Inter", system-ui, sans-serif' } },
    bargap: 0.05,
    barmode: 'stack',
    shapes: [...dayShapes, ...separators, ...dividers],
    annotations,
    showlegend: false,

    xaxis: {
      type: 'date',
      domain: [0, 1],
      anchor: 'free',
      side: 'top',
      position: 1.0,
      showgrid: false,
      linecolor: 'rgba(0,0,0,0)',
      tickformat: '%H',
      hoverformat: plotlyHoverFormat(language.value),
      dtick: 6 * 3_600_000,
      tickfont: { size: compact.value ? 7 : 9, color: TICK },
      tickcolor: W(0.25),
      range: [new Date(minTime).toISOString(), new Date(displayMaxTime).toISOString()],
      ...(customTickVals ? { tickvals: customTickVals, ticktext: customTickText } : {}),
    },

    yaxis: {
      visible: !!domains.wind,
      domain: domains.wind ?? [0, 0],
      title: { text: t('meteogram.chart.axisWind'), font: { size: 9, color: '#06b6d4' }, standoff: 2 },
      gridcolor: GRID,
      linecolor: 'rgba(0,0,0,0)',
      zeroline: false,
      rangemode: 'tozero',
      range: originalRanges.wind,
      tickvals: axisTickVals.wind ?? undefined,
      tickfont: { size: compact.value ? 7 : 9, color: '#06b6d4' },
      tickcolor: 'rgba(6,182,212,0.45)',
      nticks: 4,
      fixedrange: true,
    },

    yaxis2: {
      visible: !!domains.precip,
      domain: domains.precip ?? [0, 0],
      title: { text: t('meteogram.chart.axisPrecip'), font: { size: 9, color: '#3b82f6' }, standoff: 2 },
      gridcolor: GRID,
      linecolor: 'rgba(0,0,0,0)',
      zeroline: false,
      rangemode: 'tozero',
      range: originalRanges.precip,
      tickvals: axisTickVals.precip ?? undefined,
      tickfont: { size: compact.value ? 7 : 9, color: '#3b82f6' },
      tickcolor: 'rgba(37,99,235,0.45)',
      nticks: 3,
      fixedrange: true,
    },

    yaxis5: {
      visible: !!domains.cloud,
      domain: domains.cloud ?? [0, 0],
      title: { text: t('meteogram.chart.axisCloud'), font: { size: 9, color: theme.value.textMuted }, standoff: 2 },
      gridcolor: GRID,
      linecolor: 'rgba(0,0,0,0)',
      zeroline: false,
      range: originalRanges.cloud,
      tickvals: axisTickVals.cloud ?? undefined,
      tickfont: { size: compact.value ? 7 : 9, color: theme.value.textMuted },
      tickcolor: 'rgba(148,163,184,0.45)',
      nticks: 3,
      fixedrange: true,
    },

    yaxis3: {
      visible: !!domains.temp,
      domain: domains.temp ?? [0, 0],
      title: { text: t('meteogram.chart.axisTemp'), font: { size: 9, color: '#ef4444' }, standoff: 2 },
      gridcolor: GRID,
      linecolor: 'rgba(0,0,0,0)',
      zeroline: true,
      zerolinecolor: ZERO,
      zerolinewidth: 1,
      range: originalRanges.temp,
      tickvals: axisTickVals.temp ?? undefined,
      tickfont: { size: compact.value ? 7 : 9, color: '#ef4444' },
      tickcolor: 'rgba(239,68,68,0.45)',
      fixedrange: true,
    },

    yaxis4: {
      visible: !!domains.pressure,
      domain: domains.pressure ?? [0, 0],
      title: { text: t('meteogram.chart.axisPressure'), font: { size: 9, color: '#84cc16' }, standoff: 2 },
      gridcolor: GRID,
      linecolor: 'rgba(0,0,0,0)',
      zeroline: false,
      rangemode: 'normal',
      range: originalRanges.pressure,
      tickvals: axisTickVals.pressure ?? undefined,
      tickfont: { size: compact.value ? 7 : 9, color: '#84cc16' },
      tickcolor: 'rgba(132,204,22,0.45)',
      nticks: 3,
      fixedrange: true,
    },
  }

  const isTouchDevice = typeof window !== 'undefined' && window.matchMedia('(hover: none) and (pointer: coarse)').matches
  // the weekday of the hover heading is written by Plotly, which knows English only unless it is given the language
  const config = { responsive: true, displayModeBar: false, locale: language.value, locales: { [language.value]: plotlyDateLocale(language.value) }, ...(isTouchDevice ? { dragmode: 'pan', scrollZoom: false } : {}) }

  if (chartRef.value) {
    try {
      cleanupPlotlyOverlayHandlers()
    }
    catch {}
    try {
      cleanupOverlay()
    }
    catch {}
    // the time range the chart shows now, if it is a redraw of the same chart in other colours
    const kept = keepZoom ? drawnRanges(chartRef.value).xaxis : undefined
    // the theme it is drawn in is taken before the drawing, which a switch of the scheme can come in the middle of
    const drawnIn = theme.value
    drawnTheme = drawnIn
    Plotly.purge(chartRef.value)
    await Plotly.newPlot(chartRef.value, activeTraces, themedLayout(layout, drawnIn), config)
    // said at once, before anything after it can fail: the chart is drawn in these colours whatever follows
    markChartScheme(chartRef.value, drawnIn)
    // drawn in the range of the layout, which is what the chart's reset goes back to, and then moved to the one it was in
    if (kept)
      await Plotly.relayout(chartRef.value, { 'xaxis.range': kept.range })

    // Setup overlay drawing of wind barbs using a canvas overlay
    if (typeof window !== 'undefined' && windKey && chartRef.value && visiblePanels.value.wind) {
      const arrowInfos: { timeMs: number, dir: number, speed: number }[] = []
      const s = resampledSeries.get(windKey)!
      const dirSeries = windDirKey ? resampledSeries.get(windDirKey) : undefined
      const subsample = compact.value ? 2 : 3
      for (let i = 0; i < s.x.length; i++) {
        if (i % subsample !== 0)
          continue
        const timeMs = s.x[i]!.getTime()
        const speed = s.y[i] ?? 0
        const dir = dirSeries ? (dirSeries.y[i] ?? dirSeries.y[0] ?? 0) : 0
        arrowInfos.push({ timeMs, dir, speed })
      }

      const gustSeriesY = (gustKey ? resampledSeries.get(gustKey)?.y : undefined) ?? [0]
      const axisMax = Math.max(1, ...((resampledSeries.get(windKey)?.y) ?? [10]), ...gustSeriesY)
      const axisDomain = domains.wind ? domains.wind : [0, 0]
      const getParams = () => ({ arrowInfos, minTime, maxTime: displayMaxTime, layoutObj: layout, axisRange: [0, axisMax] as [number, number], axisDomain: axisDomain as [number, number] })
      attachOverlayListeners(getParams)
    }
  }
}

watch(
  () => props.values,
  () => {
    requestRender(false)
  },
  { immediate: true, deep: true },
)
watch(
  compact,
  () => {
    requestRender(false)
  },
)
watch(
  theme,
  () => {
    requestRender(true)
  },
)
watch(
  locale,
  () => {
    requestRender(false)
  },
)
watch(
  visiblePanels,
  () => {
    requestRender(false)
  },
  { deep: true },
)
watch(
  horizonHours,
  () => {
    requestRender(false)
  },
)
</script>

<template>
  <div>
    <UEmpty
      v-if="!values || values.length === 0"
      icon="i-lucide-cloud-off"
      :title="t('meteogram.chart.noData')"
    />

    <div v-if="values && values.length > 0" class="space-y-5">
      <!-- Premium Overhauled Filter / Controls Toolbar -->
      <div v-if="!widget" class="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-gray-50/70 dark:bg-gray-800/40 p-3.5 rounded-xl border border-gray-100 dark:border-gray-800 shadow-sm">
        <!-- Left group: panel toggles + horizon selector (wraps as a unit on narrow viewports) -->
        <div v-if="!compact" class="flex flex-wrap items-center gap-2 min-w-0">
          <!-- Interactive Panel Selectors -->
          <div class="flex items-center gap-1">
            <span class="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest mr-1 select-none">{{ t('meteogram.chart.panels') }}</span>

            <button
              type="button"
              :title="t('meteogram.chart.panelTemperature')"
              class="inline-flex items-center p-1.5 rounded-full border transition-all duration-200 cursor-pointer select-none active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none"
              :class="[
                visiblePanels.temp
                  ? 'bg-red-500/10 border-red-200/60 text-red-600 dark:border-red-900/40 dark:text-red-400 ring-1 ring-red-400/10'
                  : 'bg-white/40 dark:bg-gray-900/40 border-gray-200/80 dark:border-gray-800/80 text-gray-500 dark:text-gray-400 hover:bg-white dark:hover:bg-gray-900 hover:text-gray-700 dark:hover:text-gray-200 hover:border-gray-300 dark:hover:border-gray-700',
              ]"
              @click="visiblePanels.temp = !visiblePanels.temp"
            >
              <UIcon name="i-lucide-thermometer" class="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              :title="t('meteogram.chart.panelWind')"
              class="inline-flex items-center p-1.5 rounded-full border transition-all duration-200 cursor-pointer select-none active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none"
              :class="[
                visiblePanels.wind
                  ? 'bg-cyan-500/10 border-cyan-200/60 text-cyan-600 dark:border-cyan-900/40 dark:text-cyan-400 ring-1 ring-cyan-400/10'
                  : 'bg-white/40 dark:bg-gray-900/40 border-gray-200/80 dark:border-gray-800/80 text-gray-500 dark:text-gray-400 hover:bg-white dark:hover:bg-gray-900 hover:text-gray-700 dark:hover:text-gray-200 hover:border-gray-300 dark:hover:border-gray-700',
              ]"
              @click="visiblePanels.wind = !visiblePanels.wind"
            >
              <UIcon name="i-lucide-wind" class="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              :title="t('meteogram.chart.panelPrecipitation')"
              class="inline-flex items-center p-1.5 rounded-full border transition-all duration-200 cursor-pointer select-none active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none"
              :class="[
                visiblePanels.precip
                  ? 'bg-blue-500/10 border-blue-200/60 text-blue-600 dark:border-blue-900/40 dark:text-blue-400 ring-1 ring-blue-400/10'
                  : 'bg-white/40 dark:bg-gray-900/40 border-gray-200/80 dark:border-gray-800/80 text-gray-500 dark:text-gray-400 hover:bg-white dark:hover:bg-gray-900 hover:text-gray-700 dark:hover:text-gray-200 hover:border-gray-300 dark:hover:border-gray-700',
              ]"
              @click="visiblePanels.precip = !visiblePanels.precip"
            >
              <UIcon name="i-lucide-cloud-rain" class="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              :title="t('meteogram.chart.panelCloud')"
              class="inline-flex items-center p-1.5 rounded-full border transition-all duration-200 cursor-pointer select-none active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none"
              :class="[
                visiblePanels.cloud
                  ? 'bg-slate-500/10 border-slate-200/60 text-slate-600 dark:border-slate-800/60 dark:text-slate-300 ring-1 ring-slate-400/10'
                  : 'bg-white/40 dark:bg-gray-900/40 border-gray-200/80 dark:border-gray-800/80 text-gray-500 dark:text-gray-400 hover:bg-white dark:hover:bg-gray-900 hover:text-gray-700 dark:hover:text-gray-200 hover:border-gray-300 dark:hover:border-gray-700',
              ]"
              :disabled="compact"
              @click="visiblePanels.cloud = !visiblePanels.cloud"
            >
              <UIcon name="i-lucide-cloud" class="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              :title="t('meteogram.chart.panelPressure')"
              class="inline-flex items-center p-1.5 rounded-full border transition-all duration-200 cursor-pointer select-none active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none"
              :class="[
                visiblePanels.pressure
                  ? 'bg-lime-500/10 border-lime-200/60 text-lime-600 dark:border-lime-900/40 dark:text-lime-400 ring-1 ring-lime-400/10'
                  : 'bg-white/40 dark:bg-gray-900/40 border-gray-200/80 dark:border-gray-800/80 text-gray-500 dark:text-gray-400 hover:bg-white dark:hover:bg-gray-900 hover:text-gray-700 dark:hover:text-gray-200 hover:border-gray-300 dark:hover:border-gray-700',
              ]"
              @click="visiblePanels.pressure = !visiblePanels.pressure"
            >
              <UIcon name="i-lucide-gauge" class="w-3.5 h-3.5" />
            </button>
          </div>

          <!-- Forecast Horizon Selector -->
          <div class="flex items-center bg-gray-100 dark:bg-gray-800/70 rounded-lg p-0.5 gap-0.5">
            <button
              v-for="opt in horizonOptions"
              :key="String(opt.value)"
              type="button"
              class="text-xs px-2.5 py-1 rounded-md transition-all duration-150 select-none cursor-pointer"
              :class="horizonHours === opt.value
                ? 'bg-white dark:bg-gray-700 shadow-sm text-gray-900 dark:text-white font-semibold'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-300'"
              @click="horizonHours = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <!-- View Controls & Zoom Reset -->
        <div class="flex items-center gap-2 ml-auto shrink-0">
          <div v-if="!compact" class="hidden sm:block text-xs text-gray-500 dark:text-gray-400 select-none truncate max-w-[160px]">
            {{ toolbarTzLabel }}
          </div>
          <UButton
            v-if="!compact"
            icon="i-lucide-rotate-ccw"
            size="sm"
            variant="outline"
            color="neutral"
            :title="t('meteogram.chart.resetZoom')"
            @click="resetChart"
          />
          <UButton
            :icon="compact ? 'i-lucide-chart-line' : 'i-lucide-layout-grid'"
            size="sm"
            color="primary"
            :title="compactLabel"
            @click="toggleCompact"
          >
            <span class="hidden sm:inline">{{ compactLabel }}</span>
          </UButton>
        </div>
      </div>

      <!-- Summary stats: same order as the panel toggles (temp/wind/precip/cloud/pressure) -->
      <div v-if="summaryStats && !widget" class="flex flex-wrap gap-x-5 gap-y-2 px-1 text-sm">
        <div v-if="summaryStats.temp" class="flex items-center gap-1.5">
          <UIcon name="i-lucide-thermometer" class="w-4 h-4 text-red-500 shrink-0" />
          <span class="text-blue-600 dark:text-blue-400 font-semibold">{{ summaryStats.temp.min }}°</span>
          <span class="text-gray-500 dark:text-gray-400">/</span>
          <span class="text-red-600 dark:text-red-400 font-semibold">{{ summaryStats.temp.max }}°C</span>
        </div>
        <div class="flex items-center gap-1.5">
          <UIcon name="i-lucide-wind" class="w-4 h-4 text-cyan-500 shrink-0" />
          <span class="font-semibold text-gray-800 dark:text-gray-100">{{ formatNumber(summaryStats.gust, locale, 1) }}</span>
          <span class="text-gray-500 dark:text-gray-400 text-xs">m/s</span>
          <span class="text-cyan-700 dark:text-cyan-400 text-xs">({{ Math.round(summaryStats.gust * 3.6) }} km/h)</span>
        </div>
        <div class="flex items-center gap-1.5">
          <UIcon name="i-lucide-cloud-rain" class="w-4 h-4 text-blue-500 shrink-0" />
          <span class="font-semibold text-gray-800 dark:text-gray-100">{{ formatNumber(summaryStats.precip, locale, 1) }}</span>
          <span class="text-gray-500 dark:text-gray-400 text-xs">mm</span>
        </div>
        <div class="flex items-center gap-1.5">
          <UIcon name="i-lucide-cloud" class="w-4 h-4 text-slate-400 shrink-0" />
          <span class="font-semibold text-gray-800 dark:text-gray-100">{{ summaryStats.cloud }}</span>
          <span class="text-gray-500 dark:text-gray-400 text-xs">%</span>
        </div>
        <div v-if="summaryStats.pressure" class="flex items-center gap-1.5">
          <UIcon name="i-lucide-gauge" class="w-4 h-4 text-lime-500 shrink-0" />
          <span class="font-semibold text-gray-800 dark:text-gray-100">{{ summaryStats.pressure.min }}–{{ summaryStats.pressure.max }}</span>
          <span class="text-gray-500 dark:text-gray-400 text-xs">hPa</span>
        </div>
      </div>

      <!-- Main Interactive Chart Container -->
      <div v-if="!compact">
        <div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm overflow-hidden">
          <div
            v-if="renderFailed"
            ref="chartNotice"
            class="flex flex-wrap items-center justify-center gap-3 p-4 text-red-600 dark:text-red-400"
          >
            <!-- mounted anew for each failure, so a Retry that fails too is announced again; the
                 button stays, and keeps its focus -->
            <span :key="renderFailures" role="alert" class="text-center">
              <span class="font-medium">{{ t('dataViewer.chartNotDrawn') }}</span>
              <!-- a sentence apart from the note, which ends with no full stop: the alert's text, as
                   a screen reader reads it, otherwise runs the two together -->
              <template v-if="chartCodeNotLoaded">
                <span class="sr-only">{{ '. ' }}</span>
                <span class="block text-sm">{{ t('dataViewer.chartCodeNotLoaded') }}</span>
              </template>
            </span>
            <UButton :label="t('common.retry')" icon="i-lucide-rotate-cw" size="sm" color="neutral" variant="outline" @click="requestRender(false)" />
            <UButton v-if="chartCodeNotLoaded" :label="t('common.reloadPage')" icon="i-lucide-refresh-cw" size="sm" color="neutral" variant="outline" @click="reloadPage()" />
          </div>
          <!-- a figure, as the app's other charts, and no landmark; drawn without Plotly's modebar, it holds
               no controls of Plotly's to keep reachable. Described by what it shows; the table has the values -->
          <div
            ref="chartRef" tabindex="-1" role="figure"
            :aria-label="chartLabel"
            :aria-describedby="chartTable ? summaryId : undefined"
            :style="{ width: '100%', height: chartHeight, position: 'relative' }"
          />
        </div>
        <template v-if="chartTable">
          <p :id="summaryId" class="sr-only">
            {{ chartTable.summary }}
          </p>
          <ChartTable :caption="chartLabel" :columns="chartTable.columns" :rows="chartTable.rows" />
        </template>
      </div>

      <!-- Premium Compact Overview Grid -->
      <div v-else class="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-950 shadow-md p-4">
        <div class="flex items-center justify-start gap-4 overflow-x-auto whitespace-nowrap py-1 px-1">
          <template v-for="(d, idx) in compactDays" :key="idx">
            <div
              class="inline-flex flex-col items-center justify-center text-center p-4 rounded-2xl border transition-all duration-300 min-w-[105px] flex-shrink-0" :class="[
                d.isToday
                  ? 'bg-blue-500/5 dark:bg-blue-500/10 border-blue-400 dark:border-blue-800 ring-1 ring-blue-400/20 shadow-md shadow-blue-500/5'
                  : 'bg-gray-50/50 dark:bg-gray-900/30 border-gray-100 dark:border-gray-800 hover:bg-gray-100 dark:hover:bg-gray-900/70 hover:border-gray-200 dark:hover:border-gray-700',
              ]"
            >
              <div class="text-xs font-bold text-gray-600 dark:text-gray-400 uppercase tracking-widest mb-1">
                {{ d.isToday ? t('meteogram.chart.today') : d.weekday }}
              </div>
              <!-- the symbol is a decoration; the words are what a screen reader reads (WCAG 1.1.1) -->
              <div class="text-3xl my-3 filter drop-shadow-sm select-none animate-bounce-slow" aria-hidden="true">
                {{ WEATHER_SYMBOLS[d.kind] }}
              </div>
              <div class="sr-only">
                {{ t(`meteogram.chart.weather.${d.kind}`) }}
              </div>
              <div class="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">
                {{ d.dayMonth }}
              </div>
              <div v-if="d.tempLabel" class="text-xs font-extrabold text-gray-700 dark:text-gray-200 mt-1 bg-white dark:bg-gray-800/80 px-2 py-0.5 rounded-lg border border-gray-100 dark:border-gray-700 shadow-xs">
                {{ d.tempLabel }}
              </div>
              <div v-if="d.precipLabel" class="text-xs font-semibold text-blue-600 dark:text-blue-400 mt-1 select-none">
                <span aria-hidden="true">💧</span>
                <span class="sr-only">{{ t('meteogram.chart.panelPrecipitation') }}: </span>{{ d.precipLabel }}
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Smooth custom bounce animation for weather emojis. Once, and not at all for a visitor who asked
   for less motion: movement that starts by itself and goes on for more than five seconds needs a way
   to be stopped (WCAG 2.2.2), and a decoration is not worth one. */
@keyframes bounce-slow {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}
@media (prefers-reduced-motion: no-preference) {
  .animate-bounce-slow {
    animation: bounce-slow 4s ease-in-out 1;
  }
}
</style>
