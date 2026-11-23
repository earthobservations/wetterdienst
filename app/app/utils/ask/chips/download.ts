import type { TemperatureSource } from '../../answers'
import type { AnswerAction, ChipApi, ChipPlace, NumberLine } from '../chip'
import { COVERAGE_REQUESTS_AT_ONCE, HOURLY_TEMPERATURE, hourlyNetworks, hourlyTemperatureIn, mapLimited } from '../../answers'
import { flagEmoji } from '../../country'
import { PLACE_REACH_KM } from '../../place-stations'
import { defineChip, stationOf } from '../chip'

// Where can I download hourly temperatures? The backend's providers and their coverage (GH-3518). The answer does not depend
// on the place or the language, so what is found is kept for the visit.

/**
 * The state key the services found are kept under: the services that publish hourly air temperature are looked up once
 * for the visit and not again for each place the reader tries. The coverage of each measurement network is asked for a
 * few at a time: the list of providers does not say which have an hourly resolution, and those that have none answer a
 * 404, which is no answer to keep.
 */
export const SOURCES_STATE = 'download-sources'

async function findSources(api: ChipApi): Promise<TemperatureSource[]> {
  const found = await mapLimited(hourlyNetworks(await api.providers()), COVERAGE_REQUESTS_AT_ONCE, async ({ provider, network }) => {
    try {
      const coverage = await api.coverage({ provider: provider.provider, network, resolutions: 'hourly' })
      const hit = hourlyTemperatureIn(coverage)
      return hit ? { provider: provider.provider, name: provider.name_short, countryCode: provider.country_code, network, ...hit } : null
    }
    catch {
      // a network whose coverage could not be read is left out of the list, not guessed at
      return null
    }
  })
  return found.filter((source): source is TemperatureSource => source !== null)
}

/** Whether the place's own station is the DWD measuring stations' and is one to name: a station within reach, or a place that is a station (GH-3791: a town beyond 50 km has none, and no station is offered for it) */
const hasStation = (place: ChipPlace) => !place.town || place.town.station.distanceKm <= PLACE_REACH_KM

function sourceLink(source: TemperatureSource, place: ChipPlace) {
  return {
    path: '/explorer',
    query: {
      mode: 'station',
      provider: source.provider,
      network: source.network,
      resolution: 'hourly',
      dataset: source.dataset,
      parameters: source.parameter,
      // the place's station, where the service is the place's own and the place has one near it
      ...(source.provider === 'dwd' && source.network === 'observation' && hasStation(place) ? { stations: stationOf(place).id } : {}),
    },
  }
}

export const download = defineChip({
  id: 'download',
  icon: 'i-ph-download-simple',
  tool: 'explorer',
  question: env => env.t('ask.q.download'),
  from: 'ask.from.download',
  // the answer is a count of services, a sentence of its own: there is no scale
  scale: {},
  verdictStyle: 'sentence',
  credit: null,
  i18n: [
    'ask.q.download',
    'ask.from.download',
    'ask.download.answer',
    'ask.download.detail',
    'ask.download.none',
    'ask.download.api',
    'ask.download.station',
  ],

  async load({ formatLanguage }, api): Promise<TemperatureSource[]> {
    const found = await api.kept(SOURCES_STATE, () => findSources(api))
    const collator = new Intl.Collator(formatLanguage)
    return found
      // the place's own service first, the rest by name
      .toSorted((a, b) => Number(b.provider === 'dwd') - Number(a.provider === 'dwd') || collator.compare(a.name, b.name))
  },

  answer: sources => sources.length ? sources : null,

  present: (sources, _loaded, { t, place, number }) => ({
    verdict: t('ask.download.answer', { count: sources.length }),
    details: [t('ask.download.detail')],
    chart: null,
    list: {
      testId: 'answer-sources',
      items: sources.map(source => ({
        key: `${source.provider}/${source.network}`,
        to: sourceLink(source, place),
        mark: flagEmoji(source.countryCode),
        title: source.name,
        detail: `${source.network} · ${source.dataset}`,
        // the station the link opens: named as the station it is, and for a town with its distance from it ("Andechs-Rothenfeld, 37 km from Bad Tölz"), not by the name of the town
        ...(source.provider === 'dwd' && source.network === 'observation' && hasStation(place)
          ? { place: place.town ? t('ask.download.station', { station: stationOf(place).name, distance: number(place.town.station.distanceKm, 0), place: place.name }) : place.name }
          : {}),
      })),
    },
    note: '',
  }),

  explanation: {
    topics: ['temperature', 'observation-forecast-derived'],
    steps: ['providers', 'coverage', 'order'],
    formulas: [],
    rules: [
      { id: 'networks', kind: 'selection', cites: [], own: true },
      { id: 'hourly-temperature', kind: 'selection', own: true, cites: [{ work: 'wmo-8-i', at: '§2.1.4.2.1' }] },
      { id: 'order', kind: 'selection', cites: [], own: true },
    ],
    limits: ['coverage', 'definitions', 'licences'],
    data: {
      provider: null,
      network: null,
      dataset: null,
      parameters: [],
      // a list of services, not a dataset: the Explorer holds the data of each, the Providers page the list
      open: () => null,
    },
    numbers: (sources): NumberLine[] => [
      { id: 'count', params: { count: sources.length } },
      { id: 'parameters', params: { names: HOURLY_TEMPERATURE.join(', ') } },
    ],
  },

  empty: (_loaded, { t }) => t('ask.download.none'),

  actions: ({ t }): AnswerAction[] => [{ key: 'api', label: t('ask.download.api'), to: '/api' }],
})
