<script setup lang="ts">
/**
 * PROTOTYPE (GH-3237): the forecast chart of `Meteogram.vue` drawn as SVG by the component itself, without
 * Plotly: d3-scale / d3-shape / d3-array for the numbers, Vue for the elements. Same props as `Meteogram.vue`
 * (which has no emits, so neither has this one). Shown on `/meteogram-svg` only.
 *
 * What it does that the Plotly chart cannot:
 * - the wind barbs are SVG in the same coordinate system as the lines (no canvas, no `_fullLayout`, no redraw
 *   on `plotly_afterplot`);
 * - the crosshair is stepped by the arrow keys, and the readout is an ordinary element that is hoverable,
 *   persistent and dismissed by Escape (WCAG 2.2 1.4.13), and announced by a live region;
 * - zoom and reset are buttons and keys (2.5.7), animated unless `prefers-reduced-motion`.
 */
import type { Value } from '#shared/types/api'
import type { Domain, PanelId, Series } from '~/utils/meteogram-svg'
import type { WeatherKind } from '~/utils/weather-kind'
import { scaleLinear } from 'd3-scale'
import { DateTime } from 'luxon'
import * as SunCalc from 'suncalc'
import tzLookup from 'tz-lookup'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { formatDayMonth, weekdayShort } from '~/utils/format'
import { classifyPrecip, extremeWindowHours, extremeWindowSteps, METEOGRAM_SERIES } from '~/utils/meteogram'
import {
  areaPath,
  barbIndices,
  buildSeries,
  cloudScaleFactor,
  dayAlpha,
  daySpan,
  dewPointFromHumidity,
  findFirstAvailable,
  hourTicks,
  interpAt,
  layoutPanels,
  linePath,
  localDays,
  nearestTimeIndex,
  numberFormatter,
  panDomain,
  PANEL_ORDER,
  panelDomain,
  revealInDomain,
  scaleCloud,
  shortDateTimeFormatter,
  stepIndex,
  tooltipLeft,
  valueTicks,
  windBarb,
  zoomDomain,
} from '~/utils/meteogram-svg'
import { WEATHER_SYMBOLS, weatherCodeToKind } from '~/utils/weather-kind'

const props = defineProps<{
  values: Value[]
  stationName?: string | null
  stationCoords?: { latitude: number | null, longitude: number | null } | null
  widget?: boolean
}>()

const { t, locale, localeProperties } = useI18n()
const language = computed(() => localeProperties.value.language ?? locale.value)
/** `formatNumber` of utils/format.ts, with its Intl formatters kept between calls */
const fmtNumber = computed(() => numberFormatter(locale.value))
const uid = useId()
const summaryId = `${uid}-summary`
const hintId = `${uid}-hint`

const HOUR_MS = 3_600_000
const CHART_HEIGHT = 540
const MARGIN = { top: 62, right: 10, left: 52, bottom: 8 }
const PANEL_GAP = 8

// ---------------------------------------------------------------------------------------------------
// state

const visiblePanels = ref<Record<PanelId, boolean>>({ temp: true, wind: true, precip: true, cloud: true, pressure: true })
watch(visiblePanels, (panels) => {
  // at least one panel stays on, as in Meteogram.vue
  if (!Object.values(panels).some(Boolean))
    visiblePanels.value.temp = true
}, { deep: true })

const horizonHours = ref<number | null>(null)
const horizonOptions = computed(() => [
  { label: '24h', value: 24 },
  { label: '3d', value: 72 },
  { label: '7d', value: 168 },
  { label: t('meteogram.chart.horizonAll'), value: null as number | null },
])

const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

// ---------------------------------------------------------------------------------------------------
// data

const series = computed(() => buildSeries(props.values ?? []))
const keys = computed(() => {
  const available = new Set(series.value.keys())
  const pick = (names: readonly string[]) => findFirstAvailable(names, available)
  return {
    weather: pick(METEOGRAM_SERIES.weather),
    precip: pick(METEOGRAM_SERIES.precipitation),
    temp: pick(METEOGRAM_SERIES.temperature),
    tx: pick(METEOGRAM_SERIES.temperatureMax),
    tn: pick(METEOGRAM_SERIES.temperatureMin),
    dew: pick(METEOGRAM_SERIES.dewPoint),
    humidity: pick(METEOGRAM_SERIES.humidity),
    wind: pick(METEOGRAM_SERIES.windSpeed),
    dir: pick(METEOGRAM_SERIES.windDirection),
    gust: pick(METEOGRAM_SERIES.gust),
    cloud: pick(METEOGRAM_SERIES.cloudCover),
    cloudLow: pick(METEOGRAM_SERIES.cloudCoverLow),
    cloudMid: pick(METEOGRAM_SERIES.cloudCoverMid),
    cloudHigh: pick(METEOGRAM_SERIES.cloudCoverHigh),
    pressure: pick(METEOGRAM_SERIES.pressure),
  }
})
const get = (key: string | undefined): Series | undefined => key ? series.value.get(key) : undefined

const dataSpan = computed<Domain | null>(() => {
  let lo = Number.POSITIVE_INFINITY
  let hi = Number.NEGATIVE_INFINITY
  for (const s of series.value.values()) {
    if (s.x.length) {
      lo = Math.min(lo, s.x[0]!)
      hi = Math.max(hi, s.x.at(-1)!)
    }
  }
  return Number.isFinite(lo) && hi > lo ? [lo, hi] : null
})
/** The span of the chart before any zoom: the data, cut at the horizon chosen */
const fullDomain = computed<Domain>(() => {
  const span = dataSpan.value ?? [0, 1]
  return horizonHours.value === null ? span : [span[0], Math.min(span[1], span[0] + horizonHours.value * HOUR_MS)]
})

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
const coords = computed(() => {
  const { latitude, longitude } = props.stationCoords ?? {}
  return latitude != null && longitude != null ? { latitude, longitude } : null
})

/** Everything drawn that does not depend on the window or the width: the stamps, and each series on its own scale */
const model = computed(() => {
  const k = keys.value
  const temp = get(k.temp)
  const wind = get(k.wind)
  const precip = get(k.precip)
  const gust = get(k.gust)
  const dir = get(k.dir)
  const pressure = get(k.pressure)
  const cloud = get(k.cloud)
  const cloudLayers = {
    high: get(k.cloudHigh) && scaleCloud(get(k.cloudHigh)!),
    mid: get(k.cloudMid) && scaleCloud(get(k.cloudMid)!),
    low: get(k.cloudLow) && scaleCloud(get(k.cloudLow)!),
    total: cloud && scaleCloud(cloud),
  }

  // the maximum and minimum held over the hours they cover, as in Meteogram.vue (GH-2647)
  const span = dataSpan.value ?? [0, 1]
  const stepMs = HOUR_MS
  const steps = (key: string | undefined) => {
    const raw = get(key)
    return raw ? extremeWindowSteps(raw.x.map(ms => new Date(ms)), raw.y, extremeWindowHours(key!) * HOUR_MS, span[0], span[1], stepMs) : null
  }
  const tx = steps(k.tx)
  const tn = steps(k.tn)
  const hasTxTn = !!(tx?.x.length && tn?.x.length)

  // the dew point, from the series or from the humidity and the temperature
  let dew: Series | undefined = get(k.dew)
  if (!dew && temp && get(k.humidity)) {
    const humidity = get(k.humidity)!
    const x: number[] = []
    const y: number[] = []
    temp.x.forEach((ms, i) => {
      const rh = interpAt(humidity, ms)
      const td = rh === null ? null : dewPointFromHumidity(temp.y[i]!, rh)
      if (td !== null) {
        x.push(ms)
        y.push(td)
      }
    })
    dew = x.length ? { x, y } : undefined
  }

  // precipitation by phase, from the temperature (and the humidity where there is one)
  const phases = precip
    ? precip.x.map((ms) => {
        const tv = temp ? interpAt(temp, ms) : null
        if (tv === null)
          return 'rain' as const
        const humidity = get(k.humidity)
        const rh = humidity ? interpAt(humidity, ms) : null
        return classifyPrecip(tv, rh ?? undefined)
      })
    : []

  const weather = get(k.weather)
  const kinds = new Map<number, WeatherKind>()
  weather?.x.forEach((ms, i) => {
    const kind = weatherCodeToKind(weather.y[i])
    if (kind)
      kinds.set(ms, kind)
  })

  // the stamps the crosshair steps over: those of the densest of the main series
  const grid = [temp, wind, precip, cloud, pressure]
    .filter((s): s is Series => !!s)
    .reduce<number[]>((best, s) => s.x.length > best.length ? s.x : best, [])

  const domains: Partial<Record<PanelId, Domain>> = {}
  if (wind) {
    domains.wind = panelDomain('wind', [...wind.y, ...(gust?.y ?? [])])
  }
  if (precip)
    domains.precip = panelDomain('precip', precip.y)
  if (cloud)
    domains.cloud = panelDomain('cloud', [])
  if (temp) {
    const all = [...temp.y, ...(hasTxTn ? [...tx!.y, ...tn!.y].filter((v): v is number => v !== null) : []), ...(dew?.y ?? [])]
    domains.temp = panelDomain('temp', all)
  }
  if (pressure)
    domains.pressure = panelDomain('pressure', pressure.y)

  return { temp, wind, precip, gust, dir, pressure, cloudLayers, tx, tn, hasTxTn, dew, phases, kinds, grid, domains }
})

const panelsShown = computed(() => PANEL_ORDER.filter(id => visiblePanels.value[id] && model.value.domains[id]))

// ---------------------------------------------------------------------------------------------------
// the window: a target the keys and buttons set, and the animated one that is drawn

const target = ref<Domain>([0, 1])
const domain = ref<Domain>([0, 1])
let raf = 0

function goTo(next: Domain, animate = true) {
  target.value = next
  if (typeof cancelAnimationFrame !== 'undefined')
    cancelAnimationFrame(raf)
  if (!animate || reducedMotion.value || typeof requestAnimationFrame === 'undefined') {
    domain.value = next
    return
  }
  const from = domain.value
  const t0 = performance.now()
  const step = (now: number) => {
    const k = Math.min(1, (now - t0) / 180)
    const e = 1 - (1 - k) ** 3
    domain.value = [from[0] + (next[0] - from[0]) * e, from[1] + (next[1] - from[1]) * e]
    if (k < 1)
      raf = requestAnimationFrame(step)
  }
  raf = requestAnimationFrame(step)
}
onBeforeUnmount(() => typeof cancelAnimationFrame !== 'undefined' && cancelAnimationFrame(raf))

watch(fullDomain, full => goTo(full, false), { immediate: true })

const zoomed = computed(() => target.value[0] > fullDomain.value[0] + 1 || target.value[1] < fullDomain.value[1] - 1)

// ---------------------------------------------------------------------------------------------------
// the crosshair and its readout

const frame = useTemplateRef<HTMLElement>('frame')
const plot = useTemplateRef<HTMLElement>('plot')
const svgEl = useTemplateRef<SVGSVGElement>('svgEl')
const { width: measuredWidth } = useElementSize(frame)
const width = computed(() => Math.max(300, measuredWidth.value || 800))

const hoverIdx = ref<number | null>(null)
const focusIdx = ref<number | null>(null)
const tipY = ref(MARGIN.top + 8)
const dismissed = ref(false)
const announce = ref('')
const activeIdx = computed(() => hoverIdx.value ?? focusIdx.value)
const tipShown = computed(() => activeIdx.value !== null && !dismissed.value && model.value.grid.length > 0)

const plotW = computed(() => width.value - MARGIN.left - MARGIN.right)
const plotH = computed(() => CHART_HEIGHT - MARGIN.top - MARGIN.bottom)
const x = computed(() => scaleLinear().domain(domain.value).range([0, plotW.value]))

function clientToIndex(clientX: number): number | null {
  const svg = svgEl.value
  if (!svg || !model.value.grid.length)
    return null
  const rect = svg.getBoundingClientRect()
  const px = clientX - rect.left - MARGIN.left
  if (px < 0 || px > plotW.value)
    return null
  return nearestTimeIndex(model.value.grid, x.value.invert(px))
}

let lastPointer: [number, number] = [Number.NaN, Number.NaN]
function onPointerMove(event: PointerEvent) {
  const idx = clientToIndex(event.clientX)
  if (idx === null)
    return
  const moved = event.clientX !== lastPointer[0] || event.clientY !== lastPointer[1]
  lastPointer = [event.clientX, event.clientY]
  // Escape holds the readout away until the pointer moves on, as utils/chart-hover.ts does for Plotly's label
  if (dismissed.value && moved)
    dismissed.value = false
  hoverIdx.value = idx
  const rect = frame.value?.getBoundingClientRect()
  if (rect)
    tipY.value = Math.max(8, Math.min(CHART_HEIGHT - 150, event.clientY - rect.top - 24))
}

function onPointerDown(event: PointerEvent) {
  // a tap selects a stamp and the readout stays (persistent) until it is dismissed or the next tap elsewhere
  if (event.pointerType === 'touch')
    onPointerMove(event)
}

function onFramePointerLeave(event: PointerEvent) {
  // a finger that lifts "leaves" too: a touch readout stays until closed or a tap elsewhere
  if (event.pointerType === 'touch')
    return
  hoverIdx.value = null
  dismissed.value = false
}

function dismiss() {
  dismissed.value = true
}

// Escape dismisses whatever the readout belongs to, where the focus is: the pointer rests on the chart and
// the focus is elsewhere (1.4.13 asks for it without moving either). Not consumed, so a dialog still closes.
const stopKeys = useEventListener(() => document, 'keydown', (event: KeyboardEvent) => {
  if (event.key === 'Escape' && tipShown.value)
    dismiss()
})
// a tap outside the chart takes a touch readout away
const stopTaps = useEventListener(() => document, 'pointerdown', (event: PointerEvent) => {
  if (event.pointerType === 'touch' && !frame.value?.parentElement?.contains(event.target as Node)) {
    hoverIdx.value = null
  }
})
onBeforeUnmount(() => {
  stopKeys()
  stopTaps()
})

function firstVisibleIndex(): number {
  const grid = model.value.grid
  const i = grid.findIndex(ms => ms >= domain.value[0])
  return i < 0 ? 0 : i
}

function focusVisible(): boolean {
  try {
    return plot.value?.matches(':focus-visible') ?? false
  }
  catch {
    // an engine that does not know the selector: treat the focus as the keyboard's, the safe side
    return true
  }
}

function onFocus() {
  // a pointer click focuses the chart too, and must not leave a readout behind: only a key does
  if (focusVisible() && focusIdx.value === null && model.value.grid.length) {
    focusIdx.value = firstVisibleIndex()
    dismissed.value = false
    say()
  }
}
function onBlur() {
  focusIdx.value = null
}

function zoomBy(factor: number) {
  const anchor = activeIdx.value !== null ? model.value.grid[activeIdx.value]! : (target.value[0] + target.value[1]) / 2
  const next = zoomDomain(target.value, fullDomain.value, factor, anchor)
  goTo(next)
}

function resetView() {
  horizonHours.value = null
  goTo(fullDomain.value)
}

function onKeydown(event: KeyboardEvent) {
  if (event.altKey || event.ctrlKey || event.metaKey)
    return
  if (event.key === '+' || event.key === '=') {
    event.preventDefault()
    zoomBy(2)
    return
  }
  if (event.key === '-' || event.key === '_') {
    event.preventDefault()
    zoomBy(0.5)
    return
  }
  if (event.key === '0') {
    event.preventDefault()
    resetView()
    return
  }
  const grid = model.value.grid
  const current = focusIdx.value ?? hoverIdx.value
  const next = stepIndex(current, event.key, event.shiftKey, grid.length, 24, firstVisibleIndex())
  if (next === null)
    return
  event.preventDefault()
  focusIdx.value = next
  hoverIdx.value = null
  dismissed.value = false
  // the crosshair is never left outside the window
  goTo(revealInDomain(target.value, fullDomain.value, grid[next]!))
  tipY.value = MARGIN.top + 8
  say()
}

function pan(direction: -1 | 1) {
  goTo(panDomain(target.value, fullDomain.value, direction * (target.value[1] - target.value[0]) / 2))
}

// ---------------------------------------------------------------------------------------------------
// the scene: every element, as numbers and path data

const localTime = (ms: number) => DateTime.fromMillis(ms, { zone: stationTimeZone.value })

const scene = computed(() => {
  const m = model.value
  const xs = x.value
  const dom = domain.value
  const boxes = layoutPanels(panelsShown.value, plotH.value, PANEL_GAP)
  const days = localDays(dom[0], dom[1], stationTimeZone.value)
  const spanHours = (dom[1] - dom[0]) / HOUR_MS
  const dayPx = plotW.value / Math.max(1, spanHours / 24)

  const noonCloud = (noonMs: number) => {
    const total = m.cloudLayers.total
    if (!total)
      return 0
    const v = interpAt(total, noonMs)
    return v === null ? 0 : v / 100
  }
  const bands = days.flatMap((day) => {
    const span = daySpan(day, coords.value, coords.value ? SunCalc : null)
    if (span.fromMs === null || span.toMs === null)
      return []
    const noon = day.dt.plus({ hours: 12 }).toMillis()
    return [{ key: day.startMs, x0: xs(span.fromMs), x1: xs(span.toMs), alpha: coords.value ? dayAlpha(noonCloud(noon)) : 0.55 }]
  })
  const midnights = days.slice(1).map(d => xs(d.startMs))
  const dayLabels = days.flatMap((day) => {
    const tenAm = day.dt.plus({ hours: 10 }).toMillis()
    if (tenAm < dom[0] || tenAm > dom[1])
      return []
    const weekday = weekdayShort(day.dt, language.value)
    const dayMonth = formatDayMonth(day.dt, language.value)
    const full = dayPx >= 5.5 * `${weekday} ${dayMonth}`.length
    return [{ key: day.startMs, x: xs(tenAm), weekday, dayMonth: full ? dayMonth : '', weekend: day.dt.weekday >= 6, small: dayPx < 50 }]
  })
  const ticks = hourTicks(dom[0], dom[1], plotW.value, stationTimeZone.value).map(tick => ({ ...tick, x: xs(tick.ms) }))
  const now = Date.now()
  const nowX = now > dom[0] && now < dom[1] ? xs(now) : null

  // weather symbols along the top, as many as leave 30 px
  const kindTimes = [...m.kinds.keys()].filter(ms => ms >= dom[0] && ms <= dom[1])
  const every = Math.max(1, Math.ceil(30 / Math.max(0.001, (plotW.value / Math.max(1, spanHours)))))
  const symbols = kindTimes.filter((_, i) => i % every === 0).map(ms => ({ ms, x: xs(ms), symbol: WEATHER_SYMBOLS[m.kinds.get(ms)!] }))

  const panels = boxes.map((box) => {
    const domainY = m.domains[box.id]!
    const y = scaleLinear().domain(domainY).range([box.height, 0])
    const ticksY = valueTicks(domainY, box.id === 'temp' ? 4 : 3).map(v => ({ v, y: y(v), label: fmtNumber.value(v, Number.isInteger(v) ? 0 : 1) }))
    const out: Record<string, any> = { id: box.id, box, ticks: ticksY, zero: box.id === 'temp' && domainY[0] < 0 ? y(0) : null }
    const px = (ms: number) => xs(ms)
    if (box.id === 'temp' && m.temp) {
      const base = y(Math.max(domainY[0], Math.min(domainY[1], 0)))
      out.fill = areaPath(m.temp.x, m.temp.y, px, y, base)
      out.line = linePath(m.temp.x, m.temp.y, px, y)
      if (m.hasTxTn) {
        out.max = linePath(m.tx!.x.map(d => d.getTime()), m.tx!.y, px, y, true)
        out.min = linePath(m.tn!.x.map(d => d.getTime()), m.tn!.y, px, y, true)
      }
      if (m.dew)
        out.dew = linePath(m.dew.x, m.dew.y, px, y)
    }
    if (box.id === 'precip' && m.precip) {
      const step = m.precip.x.length > 1 ? (m.precip.x.at(-1)! - m.precip.x[0]!) / (m.precip.x.length - 1) : HOUR_MS
      const barW = Math.max(1, Math.abs(px(m.precip.x[0]! + step) - px(m.precip.x[0]!)) * 0.9)
      out.bars = m.precip.x.flatMap((ms, i) => {
        const v = m.precip!.y[i]!
        if (v <= 0 || ms < dom[0] - step || ms > dom[1] + step)
          return []
        return [{ key: ms, x: px(ms) - barW / 2, y: y(v), w: barW, h: Math.max(0, box.height - y(v)), phase: m.phases[i]! }]
      })
    }
    if (box.id === 'cloud') {
      const layer = (s: Series | undefined) => s ? { line: linePath(s.x, s.y, px, y), fill: areaPath(s.x, s.y, px, y, box.height) } : null
      out.high = layer(m.cloudLayers.high)
      out.mid = layer(m.cloudLayers.mid)
      out.low = layer(m.cloudLayers.low)
      out.total = m.cloudLayers.total ? linePath(m.cloudLayers.total.x, m.cloudLayers.total.y, px, y) : null
    }
    if (box.id === 'pressure' && m.pressure) {
      out.line = linePath(m.pressure.x, m.pressure.y, px, y)
      out.fill = areaPath(m.pressure.x, m.pressure.y, px, y, box.height)
    }
    if (box.id === 'wind' && m.wind) {
      out.fill = areaPath(m.wind.x, m.wind.y, px, y, box.height)
      out.line = linePath(m.wind.x, m.wind.y, px, y)
      if (m.gust)
        out.gust = linePath(m.gust.x, m.gust.y, px, y)
      const scale = plotW.value < 480 ? 0.78 : 1
      out.barbs = barbIndices(m.wind.x, dom, plotW.value).map((i) => {
        const dirDeg = m.dir ? valueAt(m.dir, m.wind!.x[i]!) ?? null : null
        return { key: m.wind!.x[i]!, x: px(m.wind!.x[i]!), y: y(m.wind!.y[i]!), barb: dirDeg === null ? null : windBarb(dirDeg, m.wind!.y[i]!, scale), scale }
      })
    }
    return out
  })

  return { boxes, bands, midnights, dayLabels, ticks, nowX, symbols, panels, panelDividers: boxes.slice(0, -1).map(b => b.bottom + PANEL_GAP / 2) }
})

// ---------------------------------------------------------------------------------------------------
// the readout

interface TipRow { key: string, label: string, text: string, color: string }

function valueAt(s: Series | undefined, ms: number): number | undefined {
  if (!s)
    return undefined
  // the series' own stamp, or the nearest one within an hour (the lines are not resampled)
  const i = nearestTimeIndex(s.x, ms)
  return i >= 0 && Math.abs(s.x[i]! - ms) <= HOUR_MS / 2 ? s.y[i] : undefined
}

const tip = computed(() => {
  const idx = activeIdx.value
  const m = model.value
  if (idx === null || !m.grid.length)
    return null
  const ms = m.grid[Math.min(idx, m.grid.length - 1)]!
  const dt = localTime(ms)
  const f = (v: number, d: number) => fmtNumber.value(v, d)
  const rows: TipRow[] = []
  const add = (key: string, label: string, v: number | undefined, unit: string, digits: number, color: string, extra = '') => {
    if (v !== undefined && !Number.isNaN(v))
      rows.push({ key, label, text: `${f(v, digits)}${unit}${extra}`, color })
  }
  const shown = visiblePanels.value
  if (shown.temp) {
    add('temp', m.hasTxTn ? t('meteogram.chart.hoverMeanTemp') : t('meteogram.chart.hoverTemperature'), valueAt(m.temp, ms), '°C', 1, 'var(--mg-temp)')
    if (m.hasTxTn) {
      add('tx', t('meteogram.chart.hoverMaxTemp'), valueAt({ x: m.tx!.x.map(d => d.getTime()), y: m.tx!.y.map(v => v ?? Number.NaN) }, ms), '°C', 1, 'var(--mg-max)')
      add('tn', t('meteogram.chart.hoverMinTemp'), valueAt({ x: m.tn!.x.map(d => d.getTime()), y: m.tn!.y.map(v => v ?? Number.NaN) }, ms), '°C', 1, 'var(--mg-min)')
    }
    add('dew', t('meteogram.chart.hoverDewPoint'), valueAt(m.dew, ms), '°C', 1, 'var(--mg-dew)')
  }
  if (shown.wind) {
    const dir = valueAt(m.dir, ms)
    add('wind', dir === undefined ? t('meteogram.chart.hoverWindSpeed') : t('meteogram.chart.hoverWind'), valueAt(m.wind, ms), ' m/s', 1, 'var(--mg-wind)', dir === undefined ? '' : ` → ${f(dir, 0)}°`)
    add('gust', t('meteogram.chart.hoverWindGust'), valueAt(m.gust, ms), ' m/s', 1, 'var(--mg-wind)')
  }
  if (shown.precip && m.precip) {
    const i = nearestTimeIndex(m.precip.x, ms)
    const phase = i >= 0 ? m.phases[i] : undefined
    const label = phase === 'snow' ? t('meteogram.chart.hoverSnow') : phase === 'mixed' ? t('meteogram.chart.hoverMixed') : t('meteogram.chart.hoverRain')
    add('precip', label, valueAt(m.precip, ms), ' mm', 2, 'var(--mg-precip)')
  }
  if (shown.cloud) {
    const c = m.cloudLayers
    add('cloud', t('meteogram.chart.hoverTotalCloud'), valueAt(c.total, ms), '%', 0, 'var(--mg-cloud)')
    add('high', t('meteogram.chart.hoverHighClouds'), valueAt(c.high, ms), '%', 0, 'var(--mg-cloud)')
    add('mid', t('meteogram.chart.hoverMidClouds'), valueAt(c.mid, ms), '%', 0, 'var(--mg-cloud)')
    add('low', t('meteogram.chart.hoverLowClouds'), valueAt(c.low, ms), '%', 0, 'var(--mg-cloud)')
  }
  if (shown.pressure)
    add('pressure', t('meteogram.chart.hoverPressure'), valueAt(m.pressure, ms), ' hPa', 1, 'var(--mg-pressure)')

  const kind = m.kinds.get(ms)
  let sun = ''
  if (coords.value) {
    const span = daySpan({ startMs: dt.startOf('day').toMillis(), endMs: 0, dt: dt.startOf('day') }, coords.value, SunCalc)
    if (span.sunriseMs !== null && span.sunsetMs !== null)
      sun = t('meteogram.chart.sunTimes', { rise: localTime(span.sunriseMs).toFormat('HH:mm'), set: localTime(span.sunsetMs).toFormat('HH:mm') })
  }
  return {
    ms,
    heading: `${weekdayShort(dt, language.value)} ${formatDayMonth(dt, language.value)} ${dt.toFormat('HH:mm')}`,
    weather: kind ? { symbol: WEATHER_SYMBOLS[kind], text: t(`meteogram.chart.weather.${kind}`) } : null,
    sun,
    rows,
  }
})

/** What a screen reader hears when the keys step the crosshair: the time, the weather, every value */
function say() {
  // computed lazily: `tip` follows `focusIdx`, set just before
  queueMicrotask(() => {
    const v = tip.value
    announce.value = v ? [v.heading, v.weather?.text, ...v.rows.map(r => `${r.label} ${r.text}`)].filter(Boolean).join('. ') : ''
  })
}

const crossX = computed(() => tip.value ? x.value(tip.value.ms) : null)
const TIP_WIDTH = 190
const tipStyle = computed(() => {
  if (crossX.value === null)
    return {}
  // the readout is as tall as its rows (about 17 px each, 70 for the heading, weather and sun), kept inside the card
  const height = 70 + 17 * (tip.value?.rows.length ?? 0)
  const top = Math.max(8, Math.min(tipY.value, CHART_HEIGHT - height - 8))
  return {
    left: `${tooltipLeft(MARGIN.left + crossX.value, TIP_WIDTH, width.value, 6)}px`,
    top: `${top}px`,
    width: `${TIP_WIDTH}px`,
  }
})

// ---------------------------------------------------------------------------------------------------
// the text alternative: the sentence and the table, as Meteogram.vue gives them (plus the weather)

const chartLabel = computed(() => props.stationName ? t('meteogram.chart.label', { name: props.stationName }) : t('meteogram.chart.labelNoStation'))

const chartTable = computed(() => {
  const s = series.value
  if (!s.size)
    return null
  const k = keys.value
  const panels = visiblePanels.value
  const specs: { shown: boolean, key: string | undefined, label: string, digits: number, percent?: boolean, main?: boolean }[] = [
    { shown: panels.temp, key: k.temp, label: t('meteogram.chart.seriesTemperature'), digits: 1, main: true },
    { shown: panels.temp, key: k.tx, label: t('meteogram.chart.seriesMaxTemp'), digits: 1 },
    { shown: panels.temp, key: k.tn, label: t('meteogram.chart.seriesMinTemp'), digits: 1 },
    { shown: panels.temp, key: k.dew, label: `${t('meteogram.chart.seriesDewPoint')} °C`, digits: 1 },
    { shown: panels.wind, key: k.wind, label: t('meteogram.chart.seriesWind'), digits: 1 },
    { shown: panels.wind, key: k.dir, label: `${t('meteogram.chart.seriesDirection')} °`, digits: 0 },
    { shown: panels.wind, key: k.gust, label: t('meteogram.chart.seriesWindGust'), digits: 1 },
    { shown: panels.precip, key: k.precip, label: `${t('meteogram.chart.panelPrecipitation')} mm`, digits: 2 },
    { shown: panels.cloud, key: k.cloud, label: t('meteogram.chart.seriesTotalCloud'), digits: 0, percent: true },
    { shown: panels.cloud, key: k.cloudLow, label: t('meteogram.chart.seriesLowClouds'), digits: 0, percent: true },
    { shown: panels.cloud, key: k.cloudMid, label: t('meteogram.chart.seriesMidClouds'), digits: 0, percent: true },
    { shown: panels.cloud, key: k.cloudHigh, label: t('meteogram.chart.seriesHighClouds'), digits: 0, percent: true },
    { shown: panels.pressure, key: k.pressure, label: t('meteogram.chart.seriesPressure'), digits: 1 },
  ]
  const columns = specs.filter((spec): spec is typeof spec & { key: string } => spec.shown && spec.key !== undefined)
  if (!columns.length)
    return null
  const lastShown = fullDomain.value[1]
  const byTime = new Map<number, (number | null)[]>()
  columns.forEach((column, index) => {
    const ser = s.get(column.key)!
    const scale = column.percent ? cloudScaleFactor(ser.y) : 1
    ser.x.forEach((ms, i) => {
      if (ms > lastShown)
        return
      const row = byTime.get(ms) ?? Array.from<number | null>({ length: columns.length }).fill(null)
      row[index] = ser.y[i]! * scale
      byTime.set(ms, row)
    })
  })
  const times = [...byTime.keys()].sort((a, b) => a - b)
  if (!times.length)
    return null
  const write = shortDateTimeFormatter(language.value, stationTimeZone.value)
  const main = columns.findIndex(column => column.main)
  const temperatures = main < 0 ? [] : times.map(ms => byTime.get(ms)![main]).filter((v): v is number => v !== null && v !== undefined)
  const kinds = model.value.kinds
  const withWeather = kinds.size > 0
  return {
    columns: [t('meteogram.chart.tableTime', { zone: stationTimeZone.value }), ...(withWeather ? [t('meteogram.chart.panelWeather')] : []), ...columns.map(column => column.label)],
    rows: times.map(ms => [
      write(ms),
      ...(withWeather ? [kinds.has(ms) ? t(`meteogram.chart.weather.${kinds.get(ms)}`) : '–'] : []),
      ...byTime.get(ms)!.map((value, index) => value === null ? '–' : fmtNumber.value(value, columns[index]!.digits)),
    ]),
    summary: [
      t('meteogram.chart.summaryRange', { from: write(times[0]!), to: write(times.at(-1)!) }),
      ...(temperatures.length
        ? [t('meteogram.chart.summaryTemperature', { min: fmtNumber.value(Math.min(...temperatures), 1), max: fmtNumber.value(Math.max(...temperatures), 1) })]
        : []),
      t('common.chartTableHint'),
    ].join(' '),
  }
})

const toolbarTzLabel = computed(() => {
  const zone = stationTimeZone.value
  const offset = DateTime.fromMillis(fullDomain.value[0], { zone }).offset
  const sign = offset >= 0 ? '+' : '-'
  const h = String(Math.floor(Math.abs(offset) / 60)).padStart(2, '0')
  const mm = String(Math.abs(offset) % 60).padStart(2, '0')
  return `${zone} (UTC${sign}${h}:${mm})`
})

const panelButtons: { id: PanelId, icon: string, label: string, tone: string }[] = [
  { id: 'temp', icon: 'i-lucide-thermometer', label: 'meteogram.chart.panelTemperature', tone: 'red' },
  { id: 'wind', icon: 'i-lucide-wind', label: 'meteogram.chart.panelWind', tone: 'cyan' },
  { id: 'precip', icon: 'i-lucide-cloud-rain', label: 'meteogram.chart.panelPrecipitation', tone: 'blue' },
  { id: 'cloud', icon: 'i-lucide-cloud', label: 'meteogram.chart.panelCloud', tone: 'slate' },
  { id: 'pressure', icon: 'i-lucide-gauge', label: 'meteogram.chart.panelPressure', tone: 'lime' },
]
const axisTitle: Record<PanelId, string> = {
  wind: 'meteogram.chart.axisWind',
  precip: 'meteogram.chart.axisPrecip',
  cloud: 'meteogram.chart.axisCloud',
  temp: 'meteogram.chart.axisTemp',
  pressure: 'meteogram.chart.axisPressure',
}

defineExpose({ scene, tip, activeIdx, domain, target, tipShown, dismissed })
</script>

<template>
  <div class="mg">
    <UEmpty
      v-if="!values || values.length === 0"
      icon="i-lucide-cloud-off"
      :title="t('meteogram.chart.noData')"
    />

    <div v-else class="space-y-5">
      <!-- the same controls as Meteogram.vue's toolbar, as buttons that say whether they are on (aria-pressed),
           and the zoom the Plotly chart has by dragging: buttons (2.5.7) -->
      <div v-if="!widget" class="mg-toolbar flex flex-col md:flex-row md:items-center justify-between gap-4 bg-gray-50/70 dark:bg-gray-800/40 p-3.5 rounded-xl border border-gray-100 dark:border-gray-800 shadow-sm">
        <div class="flex flex-wrap items-center gap-2 min-w-0">
          <div class="flex items-center gap-1" role="group" :aria-label="t('meteogram.chart.panels')">
            <span class="text-xs font-bold text-gray-600 dark:text-gray-400 uppercase tracking-widest mr-1 select-none" aria-hidden="true">{{ t('meteogram.chart.panels') }}</span>
            <button
              v-for="button in panelButtons"
              :key="button.id"
              type="button"
              :title="t(button.label)"
              :aria-label="t(button.label)"
              :aria-pressed="visiblePanels[button.id]"
              class="mg-panel-toggle inline-flex items-center p-1.5 rounded-full border cursor-pointer select-none"
              :class="visiblePanels[button.id]
                ? 'bg-gray-100 dark:bg-gray-800 border-gray-400 dark:border-gray-500 text-gray-900 dark:text-gray-100'
                : 'bg-white/40 dark:bg-gray-900/40 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400'"
              @click="visiblePanels[button.id] = !visiblePanels[button.id]"
            >
              <UIcon :name="button.icon" class="w-3.5 h-3.5" />
            </button>
          </div>
          <div class="flex items-center bg-gray-100 dark:bg-gray-800/70 rounded-lg p-0.5 gap-0.5" role="group" :aria-label="t('meteogram.chart.horizonAll')">
            <button
              v-for="opt in horizonOptions"
              :key="String(opt.value)"
              type="button"
              :aria-pressed="horizonHours === opt.value"
              class="text-xs px-2.5 py-1 rounded-md select-none cursor-pointer"
              :class="horizonHours === opt.value
                ? 'bg-white dark:bg-gray-700 shadow-sm text-gray-900 dark:text-white font-semibold'
                : 'text-gray-700 dark:text-gray-300'"
              @click="horizonHours = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>
        <div class="flex items-center gap-2 ml-auto shrink-0">
          <div class="hidden sm:block text-xs text-gray-600 dark:text-gray-400 select-none truncate max-w-[200px]">
            {{ toolbarTzLabel }}
          </div>
          <UButton icon="i-lucide-zoom-in" size="sm" variant="outline" color="neutral" :aria-label="t('meteogram.chart.zoomIn')" :title="t('meteogram.chart.zoomIn')" @click="zoomBy(2)" />
          <UButton icon="i-lucide-zoom-out" size="sm" variant="outline" color="neutral" :aria-label="t('meteogram.chart.zoomOut')" :title="t('meteogram.chart.zoomOut')" :disabled="!zoomed" @click="zoomBy(0.5)" />
          <UButton icon="i-lucide-chevron-left" size="sm" variant="outline" color="neutral" :aria-label="t('meteogram.chart.panLeft')" :title="t('meteogram.chart.panLeft')" :disabled="!zoomed" @click="pan(-1)" />
          <UButton icon="i-lucide-chevron-right" size="sm" variant="outline" color="neutral" :aria-label="t('meteogram.chart.panRight')" :title="t('meteogram.chart.panRight')" :disabled="!zoomed" @click="pan(1)" />
          <UButton icon="i-lucide-rotate-ccw" size="sm" variant="outline" color="neutral" :aria-label="t('meteogram.chart.resetZoom')" :title="t('meteogram.chart.resetZoom')" @click="resetView" />
        </div>
      </div>

      <div class="mg-card rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm overflow-hidden">
        <div ref="frame" class="mg-frame relative" :style="{ height: `${CHART_HEIGHT}px` }" @pointerleave="onFramePointerLeave">
          <!-- the focusable chart: a figure described by its summary and the keys; the SVG inside is a picture of it
               (aria-hidden), the readout and the table carry the values -->
          <div
            ref="plot"
            role="figure"
            tabindex="0"
            class="mg-plot"
            :aria-label="chartLabel"
            :aria-describedby="chartTable ? `${summaryId} ${hintId}` : hintId"
            aria-keyshortcuts="ArrowLeft ArrowRight Shift+ArrowLeft Shift+ArrowRight PageUp PageDown Home End + - 0 Escape"
            @keydown="onKeydown"
            @focus="onFocus"
            @blur="onBlur"
          >
            <svg
              ref="svgEl"
              :width="width"
              :height="CHART_HEIGHT"
              :viewBox="`0 0 ${width} ${CHART_HEIGHT}`"
              aria-hidden="true"
              focusable="false"
              class="mg-svg"
              @pointermove="onPointerMove"
              @pointerdown="onPointerDown"
            >
              <defs>
                <clipPath v-for="p in scene.panels" :id="`${uid}-clip-${p.id}`" :key="p.id">
                  <rect x="0" y="0" :width="plotW" :height="p.box.height" />
                </clipPath>
                <clipPath :id="`${uid}-clip-all`">
                  <rect x="0" :y="-MARGIN.top" :width="plotW" :height="plotH + MARGIN.top" />
                </clipPath>
              </defs>
              <g :transform="`translate(${MARGIN.left},${MARGIN.top})`">
                <!-- day bands, from sunrise to sunset, and the midnights -->
                <g :clip-path="`url(#${uid}-clip-all)`">
                  <rect v-for="band in scene.bands" :key="band.key" class="mg-day" :x="band.x0" y="0" :width="Math.max(0, band.x1 - band.x0)" :height="plotH" :fill-opacity="band.alpha" />
                  <line v-for="(mx, i) in scene.midnights" :key="`m${i}`" class="mg-midnight" :x1="mx" :x2="mx" y1="0" :y2="plotH" />
                </g>

                <!-- the shared time axis, on top: weekday and date, weather symbols, local hours -->
                <g class="mg-axis-top">
                  <text v-for="d in scene.dayLabels" :key="d.key" :x="d.x" y="-48" text-anchor="middle" :font-size="d.small ? 8 : 10" :class="d.weekend ? 'mg-weekend' : 'mg-day-label'">
                    <tspan font-weight="700">{{ d.weekday }}</tspan><tspan v-if="d.dayMonth" dx="3">{{ d.dayMonth }}</tspan>
                  </text>
                  <text v-for="s in scene.symbols" :key="s.ms" :x="s.x" y="-26" text-anchor="middle" font-size="15">{{ s.symbol }}</text>
                  <g v-for="tick in scene.ticks" :key="tick.ms">
                    <line :x1="tick.x" :x2="tick.x" y1="-5" y2="0" class="mg-tick-line" />
                    <text :x="tick.x" y="-9" text-anchor="middle" font-size="9" class="mg-tick">{{ tick.label }}</text>
                  </g>
                </g>

                <!-- one panel each: grid and value axis, then the series, clipped to the window -->
                <g v-for="p in scene.panels" :key="p.id" :transform="`translate(0,${p.box.top})`">
                  <g class="mg-grid">
                    <line v-for="tk in p.ticks" :key="tk.v" x1="0" :x2="plotW" :y1="tk.y" :y2="tk.y" />
                    <line v-if="p.zero !== null" class="mg-zero" x1="0" :x2="plotW" :y1="p.zero" :y2="p.zero" />
                  </g>
                  <text v-for="tk in p.ticks" :key="`t${tk.v}`" :x="-6" :y="tk.y" dy="0.32em" text-anchor="end" font-size="9" :class="`mg-tick mg-c-${p.id}`">{{ tk.label }}</text>
                  <text :transform="`translate(${-MARGIN.left + 9},${p.box.height / 2}) rotate(-90)`" text-anchor="middle" font-size="9" :class="`mg-tick mg-c-${p.id}`">{{ t(axisTitle[p.id as PanelId]) }}</text>

                  <g :clip-path="`url(#${uid}-clip-${p.id})`">
                    <template v-if="p.id === 'temp'">
                      <path class="mg-fill mg-f-temp" :d="p.fill" />
                      <path v-if="p.max" class="mg-line mg-dash mg-s-max" :d="p.max" />
                      <path v-if="p.min" class="mg-line mg-dash mg-s-min" :d="p.min" />
                      <path v-if="p.dew" class="mg-line mg-s-dew" :d="p.dew" />
                      <path class="mg-line mg-s-temp" stroke-width="2" :d="p.line" />
                    </template>
                    <template v-else-if="p.id === 'precip'">
                      <rect v-for="bar in p.bars" :key="bar.key" :class="`mg-bar mg-bar-${bar.phase}`" :x="bar.x" :y="bar.y" :width="bar.w" :height="bar.h" />
                    </template>
                    <template v-else-if="p.id === 'cloud'">
                      <template v-for="layer in ['high', 'mid', 'low']" :key="layer">
                        <template v-if="p[layer]">
                          <path :class="`mg-fill mg-cloud-${layer}`" :d="p[layer].fill" />
                          <path :class="`mg-line mg-cloud-line-${layer}`" stroke-width="1" :d="p[layer].line" />
                        </template>
                      </template>
                      <path v-if="p.total" class="mg-line mg-s-cloud" stroke-width="2" :d="p.total" />
                    </template>
                    <template v-else-if="p.id === 'pressure'">
                      <path class="mg-fill mg-f-pressure" :d="p.fill" />
                      <path class="mg-line mg-s-pressure" :d="p.line" />
                    </template>
                    <template v-else-if="p.id === 'wind'">
                      <path class="mg-fill mg-f-wind" :d="p.fill" />
                      <path v-if="p.gust" class="mg-line mg-dash mg-s-wind" stroke-width="1.6" :d="p.gust" />
                      <path class="mg-line mg-s-wind" stroke-width="2" :d="p.line" />
                      <!-- the barbs, in the coordinate system of the line they sit on -->
                      <g v-for="b in p.barbs" :key="b.key" class="mg-barb" :transform="`translate(${b.x},${b.y})`">
                        <template v-if="b.barb">
                          <circle v-if="b.barb.calm" r="1" :cx="0" :cy="0" :style="{ r: `${b.barb.radius}px` }" fill="none" />
                          <template v-else>
                            <path :d="b.barb.shaft" fill="none" />
                            <path v-if="b.barb.barbs" :d="b.barb.barbs" fill="none" />
                            <path v-for="(pennant, i) in b.barb.pennants" :key="i" :d="pennant" class="mg-pennant" />
                          </template>
                        </template>
                      </g>
                    </template>
                  </g>
                </g>

                <line v-for="(dy, i) in scene.panelDividers" :key="`d${i}`" class="mg-divider" x1="0" :x2="plotW" :y1="dy" :y2="dy" />

                <!-- now -->
                <line v-if="scene.nowX !== null" class="mg-now" :x1="scene.nowX" :x2="scene.nowX" y1="0" :y2="plotH" />

                <!-- the crosshair, which moves with the pointer or the keys -->
                <g v-if="tip && !dismissed && crossX !== null" class="mg-cross" :style="{ transform: `translateX(${crossX}px)` }">
                  <line x1="0" x2="0" :y1="-MARGIN.top + 54" :y2="plotH" />
                </g>
              </g>
            </svg>
          </div>

          <!-- the readout: an ordinary element beside the crosshair. Hoverable (the pointer can move onto it, it
               overlaps the row of the pointer), persistent (it stays while the pointer is on the chart or on it,
               or the chart has the focus) and dismissible (Escape, or its button), WCAG 2.2 1.4.13 -->
          <div
            v-if="tip && tipShown"
            class="mg-tip"
            :style="tipStyle"
            data-testid="mg-tooltip"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="font-semibold text-gray-900 dark:text-gray-100">
                {{ tip.heading }}
              </div>
              <button type="button" class="mg-tip-close" :aria-label="t('common.close')" :title="t('common.close')" @click="dismiss">
                <UIcon name="i-lucide-x" class="w-3.5 h-3.5" />
              </button>
            </div>
            <div v-if="tip.weather" class="mt-0.5">
              <span aria-hidden="true">{{ tip.weather.symbol }}</span> {{ tip.weather.text }}
            </div>
            <div v-if="tip.sun" class="text-gray-700 dark:text-gray-300">
              {{ tip.sun }}
            </div>
            <dl class="mt-1 space-y-0.5">
              <div v-for="row in tip.rows" :key="row.key" class="flex justify-between gap-3">
                <dt class="flex items-center gap-1.5 text-gray-700 dark:text-gray-300">
                  <span class="mg-swatch" :style="{ background: row.color }" aria-hidden="true" />{{ row.label }}
                </dt>
                <dd class="font-medium text-gray-900 dark:text-gray-100 tabular-nums">
                  {{ row.text }}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </div>

      <p :id="hintId" class="sr-only">
        {{ t('meteogram.chart.keyboardHint') }}
      </p>
      <!-- spoken when the keys step the crosshair; not on hover, which would talk over a pointer user -->
      <p class="sr-only" aria-live="polite" aria-atomic="true">
        {{ announce }}
      </p>
      <template v-if="chartTable">
        <p :id="summaryId" class="sr-only">
          {{ chartTable.summary }}
        </p>
        <ChartTable :caption="chartLabel" :columns="chartTable.columns" :rows="chartTable.rows" />
      </template>
    </div>
  </div>
</template>

<style scoped>
/* Tokens: one set for each theme, defined on the component as the rest of the app takes its colours from the
   Tailwind palette. Every one is at least 4.5:1 against the page and against a day band in its theme
   (checked: text labels in the series colours need it; the lines need 3:1). */
.mg {
  --mg-temp: #dc2626;
  --mg-max: #b91c1c;
  --mg-min: #1d4ed8;
  --mg-dew: #7e22ce;
  --mg-wind: #0e7490;
  --mg-precip: #1d4ed8;
  --mg-mixed: #0369a1;
  --mg-snow: #5b6b80;
  --mg-cloud: #475569;
  --mg-pressure: #4d7c0f;
  --mg-ink: #0f172a;
  --mg-muted: #4b5563;
  --mg-weekend: #dc2626;
  --mg-now: #c2410c;
  --mg-grid: rgb(55 65 81 / 0.1);
  --mg-divider: rgb(55 65 81 / 0.25);
  --mg-day: 253 244 180;
  --mg-tip-bg: #ffffff;
  --mg-tip-border: #d1d5db;
}

.mg-plot { display: block; outline-offset: -2px; touch-action: pan-y; }
.mg-svg { display: block; max-width: none; touch-action: pan-y; user-select: none; }

.mg-day { fill: rgb(var(--mg-day)); }
.mg-midnight { stroke: var(--mg-grid); stroke-dasharray: 1 3; }
.mg-grid line { stroke: var(--mg-grid); }
.mg-grid .mg-zero { stroke: var(--mg-divider); }
.mg-divider { stroke: var(--mg-divider); }
.mg-now { stroke: var(--mg-now); stroke-width: 1.5; }
.mg-tick { fill: var(--mg-muted); }
.mg-tick-line { stroke: var(--mg-divider); }
.mg-day-label { fill: var(--mg-ink); }
.mg-weekend { fill: var(--mg-weekend); }
.mg-c-temp { fill: var(--mg-temp); }
.mg-c-wind { fill: var(--mg-wind); }
.mg-c-precip { fill: var(--mg-precip); }
.mg-c-cloud { fill: var(--mg-cloud); }
.mg-c-pressure { fill: var(--mg-pressure); }

.mg-line { fill: none; stroke-linejoin: round; stroke-linecap: round; stroke-width: 1.6; }
.mg-dash { stroke-dasharray: 5 3; }
.mg-s-temp { stroke: var(--mg-temp); }
.mg-s-max { stroke: var(--mg-max); stroke-width: 1.5; }
.mg-s-min { stroke: var(--mg-min); stroke-width: 1.5; }
.mg-s-dew { stroke: var(--mg-dew); }
.mg-s-wind { stroke: var(--mg-wind); }
.mg-s-cloud { stroke: var(--mg-cloud); }
.mg-s-pressure { stroke: var(--mg-pressure); }
.mg-fill { stroke: none; }
.mg-f-temp { fill: var(--mg-temp); fill-opacity: 0.06; }
.mg-f-wind { fill: var(--mg-wind); fill-opacity: 0.1; }
.mg-f-pressure { fill: var(--mg-pressure); fill-opacity: 0.08; }
.mg-cloud-high { fill: var(--mg-cloud); fill-opacity: 0.1; }
.mg-cloud-mid { fill: var(--mg-cloud); fill-opacity: 0.18; }
.mg-cloud-low { fill: var(--mg-cloud); fill-opacity: 0.28; }
.mg-cloud-line-high { stroke: var(--mg-cloud); stroke-opacity: 0.4; }
.mg-cloud-line-mid { stroke: var(--mg-cloud); stroke-opacity: 0.6; }
.mg-cloud-line-low { stroke: var(--mg-cloud); stroke-opacity: 0.8; }
.mg-bar-rain { fill: var(--mg-precip); }
.mg-bar-mixed { fill: var(--mg-mixed); }
.mg-bar-snow { fill: var(--mg-snow); }

.mg-barb path, .mg-barb circle { stroke: var(--mg-ink); stroke-width: 1.5; stroke-linecap: round; }
.mg-barb .mg-pennant { fill: var(--mg-ink); }

.mg-cross line { stroke: var(--mg-ink); stroke-width: 1; stroke-opacity: 0.7; }

.mg-tip {
  position: absolute;
  z-index: 20;
  padding: 0.5rem 0.625rem;
  font-size: 0.75rem;
  line-height: 1.25;
  background: var(--mg-tip-bg);
  border: 1px solid var(--mg-tip-border);
  border-radius: 0.5rem;
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.15);
}
.mg-tip-close {
  display: inline-flex;
  padding: 0.125rem;
  margin: -0.125rem;
  color: var(--mg-muted);
  border-radius: 0.25rem;
  cursor: pointer;
}
.mg-swatch { display: inline-block; width: 0.5rem; height: 0.5rem; border-radius: 9999px; }

/* Motion only for a visitor who has not asked for less (WCAG 2.3.3): the crosshair glides, the readout fades.
   The zoom's own animation is a script, which reads the same query. */
@media (prefers-reduced-motion: no-preference) {
  .mg-cross { transition: transform 90ms ease-out; }
  .mg-tip { animation: mg-tip-in 120ms ease-out; }
}
@keyframes mg-tip-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>

<!-- the dark theme, unscoped: a scoped `:global(.dark) .mg` is compiled to `.dark` alone, which the component's own tokens then override -->
<style>
.dark .mg {
  --mg-temp: #f87171;
  --mg-max: #fca5a5;
  --mg-min: #93c5fd;
  --mg-dew: #d8b4fe;
  --mg-wind: #22d3ee;
  --mg-precip: #60a5fa;
  --mg-mixed: #38bdf8;
  --mg-snow: #cbd5e1;
  --mg-cloud: #cbd5e1;
  --mg-pressure: #a3e635;
  --mg-ink: #f4f4f5;
  --mg-muted: #9ca3af;
  --mg-weekend: #f87171;
  --mg-now: #fb923c;
  --mg-grid: rgb(244 244 245 / 0.1);
  --mg-divider: rgb(244 244 245 / 0.25);
  --mg-day: 250 204 21;
  --mg-tip-bg: #1f2937;
  --mg-tip-border: #4b5563;
}
.dark .mg .mg-day {
  opacity: 0.25;
}
</style>
