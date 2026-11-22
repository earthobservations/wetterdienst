import type { DateTime } from 'luxon'
import type { Station, Value } from '#shared/types/api'
import type { NearbyAnswer } from '../../compare-answers'
import type { AnswerAction, NumberLine } from '../chip'
import { NEARBY_MAX_KM, NEARBY_MIN_DAYS, NEARBY_PARAMETER, NEARBY_SAME_BAND, NEARBY_WINDOW_DAYS, nearbyDaysWithBoth, nearbyWarmer, nearbyWindow } from '../../compare-answers'
import { defineChip } from '../chip'

// Is it warmer here than at a station nearby? DWD's daily mean temperature of the place's station and of the nearest other one that
// reports now, over the last thirty days (GH-4296). The Compare tool shows the two stations side by side.

const SCALE = {
  warmer: 'ask.nearby.warmer',
  cooler: 'ask.nearby.cooler',
  same: 'ask.nearby.same',
} as const

const FETCH = { provider: 'dwd', network: 'observation', resolution: 'daily', dataset: 'climate_summary', parameter: NEARBY_PARAMETER } as const

/** A station of the list with the distance the ranked request gives */
type Ranked = Station & { distance?: number }

interface Loaded {
  /** The place's own station of the list (its height), where the list has it */
  here: Ranked | null
  /** The nearest other station that reports now, within `NEARBY_MAX_KM` */
  other: Ranked
  readings: Value[]
  units: Record<string, string>
}

/** How many of the stations nearest to the place are looked through for one that reports now: the nearest ones include closed stations */
const CANDIDATES = 12
/** A station reports now where its record reaches into the last ten days */
const REPORTS_WITHIN_DAYS = 10

/** The same two stations side by side in the Compare tool, over the days the answer is about */
function compareLink(here: string, other: string, now: DateTime) {
  const { from, to } = nearbyWindow(now)
  return { path: '/compare', query: { compare: 'stations', resolution: FETCH.resolution, parameter: FETCH.parameter, stations: `${here},${other}`, startDate: from, endDate: to } }
}

/** The same data in the Explorer: the daily mean temperature of both stations over those days */
function explorerLink(here: string, other: string, now: DateTime) {
  const { from, to } = nearbyWindow(now)
  return { path: '/explorer', query: { mode: 'station', provider: FETCH.provider, network: FETCH.network, resolution: FETCH.resolution, dataset: FETCH.dataset, parameters: FETCH.parameter, stations: `${here},${other}`, startDate: from, endDate: to } }
}

export const nearby = defineChip({
  id: 'nearby',
  icon: 'i-ph-thermometer-simple',
  tool: 'compare',
  quantity: 'temperature',
  question: env => env.t('ask.q.nearby'),
  from: 'ask.from.nearby',
  scale: SCALE,
  credit: { provider: 'dwd', fallback: 'Deutscher Wetterdienst' },
  i18n: [
    'ask.q.nearby',
    'ask.from.nearby',
    ...Object.values(SCALE),
    'ask.nearby.detail',
    'ask.nearby.where',
    'ask.nearby.whereNoHeight',
    'ask.nearby.chart',
    'ask.nearby.none',
    'ask.nearby.noneDays',
    'ask.nearby.open',
  ],

  async load({ place, now, unitTarget }, api): Promise<Loaded | null> {
    const ranked: Ranked[] = await api.stations({ provider: FETCH.provider, network: FETCH.network, parameters: `${FETCH.resolution}/${FETCH.dataset}`, latitude: place.latitude, longitude: place.longitude, rank: CANDIDATES })
    const since = now().toUTC().startOf('day').minus({ days: REPORTS_WITHIN_DAYS }).toISODate()!
    const other = ranked.find(station => station.station_id !== place.id && (station.distance ?? 0) <= NEARBY_MAX_KM && (!station.end_timestamp || station.end_timestamp.slice(0, 10) >= since))
    if (!other)
      return null
    const { from, to } = nearbyWindow(now())
    const { readings, units } = await api.values({
      provider: FETCH.provider,
      network: FETCH.network,
      parameters: `${FETCH.resolution}/${FETCH.dataset}/${FETCH.parameter}`,
      stations: `${place.id},${other.station_id}`,
      timestamp: `${from}/${to}`,
      unit_targets: JSON.stringify({ temperature: unitTarget('temperature') }),
    })
    return { here: ranked.find(station => station.station_id === place.id) ?? null, other, readings, units }
  },

  answer: (loaded, { place, now }): NearbyAnswer | null => loaded
    ? nearbyWarmer(loaded.readings, place.id, loaded.other.station_id, now(), loaded.units[NEARBY_PARAMETER])
    : null,

  present(answer, loaded, env) {
    const { t, number, unitText, place } = env
    const unit = unitText(answer.unit)
    const other = loaded!.other
    const name = other.name ?? other.station_id
    const distance = other.distance
    const heights = other.elevation != null && loaded!.here?.elevation != null
    return {
      verdict: t(SCALE[answer.verdict], { difference: number(Math.abs(answer.difference)), unit, name }),
      details: [t('ask.nearby.detail', { days: answer.days, here: number(answer.here), there: number(answer.there), unit, name })],
      chart: { bars: answer.bars, caption: t('ask.nearby.chart', { name, unit }), unit, diverging: true, every: 7, emphasis: 'all' },
      list: null,
      note: heights
        ? t('ask.nearby.where', { name, id: other.station_id, distance: number(distance ?? 0), there: number(other.elevation!, 0), place: place.name, here: number(loaded!.here!.elevation!, 0) })
        : t('ask.nearby.whereNoHeight', { name, id: other.station_id, distance: number(distance ?? 0), place: place.name }),
    }
  },

  explanation: {
    topics: ['temperature', 'time'],
    steps: ['station', 'days', 'means', 'verdict'],
    formulas: ['means'],
    rules: [
      // what is read
      { id: 'daily-mean', kind: 'selection', cites: [{ work: 'dwd-daily-kl', at: 'TMK' }] },
      // which station, which days
      { id: 'nearest-station', kind: 'selection', values: { maxKm: NEARBY_MAX_KM, reportsDays: REPORTS_WITHIN_DAYS }, cites: [], own: true },
      { id: 'window', kind: 'window', values: { windowDays: NEARBY_WINDOW_DAYS }, cites: [], own: true },
      { id: 'common-days', kind: 'fallback', values: { minDays: NEARBY_MIN_DAYS }, cites: [], own: true },
      // how they are averaged and judged
      { id: 'mean-difference', kind: 'statistic', cites: [], own: true },
      { id: 'same-band', kind: 'band', values: { band: NEARBY_SAME_BAND }, cites: [], own: true },
    ],
    limits: ['height', 'recent', 'station', 'days', 'band'],
    data: {
      provider: FETCH.provider,
      network: FETCH.network,
      dataset: `${FETCH.resolution}/${FETCH.dataset}`,
      parameters: [FETCH.parameter],
      open: (env, _choices, loaded) => loaded ? explorerLink(env.place.id, loaded.other.station_id, env.now()) : null,
    },
    numbers(answer, loaded, { number, unitText, place }) {
      const unit = unitText(answer.unit)
      const other = loaded!.other
      const lines: NumberLine[] = [
        { id: 'station', params: { name: place.name, id: place.id } },
        { id: 'other', params: { name: other.name ?? other.station_id, id: other.station_id, distance: number(other.distance ?? 0) } },
        { id: 'days', params: { days: answer.days, window: NEARBY_WINDOW_DAYS, from: answer.from, to: answer.to } },
        { id: 'means', params: { here: number(answer.here), there: number(answer.there), unit } },
        { id: 'difference', params: { difference: number(answer.difference), unit } },
        { id: 'band', params: { band: number(NEARBY_SAME_BAND) } },
      ]
      return lines
    },
  },

  empty: (loaded, { t, place, now }) => {
    if (!loaded)
      return t('ask.nearby.none', { distance: NEARBY_MAX_KM })
    return t('ask.nearby.noneDays', { name: loaded.other.name ?? loaded.other.station_id, count: nearbyDaysWithBoth(loaded.readings, place.id, loaded.other.station_id, now()), min: NEARBY_MIN_DAYS })
  },

  actions: (env, _choices, loaded): AnswerAction[] => loaded
    ? [{ key: 'compare', label: env.t('ask.nearby.open'), tool: 'compare', to: compareLink(env.place.id, loaded.other.station_id, env.now()) }]
    : [],
})
