import type { ChipApi, ChipContext, ChipEnv } from '../../app/utils/ask/chip'
import { describe, expect, it, vi } from 'vitest'
import { stationOf } from '../../app/utils/ask/chip'
import { day } from '../../app/utils/ask/chips/day'
import { download } from '../../app/utils/ask/chips/download'
import { rain } from '../../app/utils/ask/chips/rain'
import { season } from '../../app/utils/ask/chips/season'
import { PLACE_REACH_KM } from '../../app/utils/place-stations'

// The questions about a town found by its name (GH-3791): the measurements are read at the station nearest to it, the forecast at the nearest forecast point,
// and where that is farther than the reach nothing is fetched and the question says there is none near. A place that is a station is as it always was.

const STATION_PLACE = { id: '02564', name: 'Kiel-Holtenau', latitude: 54.3776, longitude: 10.1424 }
const TOWN = { id: '00125', name: 'Bad Tölz', latitude: 47.7614, longitude: 11.5583, town: { station: { id: '00125', name: 'Andechs-Rothenfeld', latitude: 47.9794, longitude: 11.1888, distanceKm: 36.8 } } }

const POINT = { station_id: 'M0814', name: 'BAD TOELZ', region: null, latitude: 47.77, longitude: 11.55, elevation: 668, start_timestamp: null, end_timestamp: null }

/** The requests of a question, answered as the test says; a forecast point that has the distance the backend gives it, or none */
function api(point: Record<string, unknown> | null) {
  const values = vi.fn(async () => ({ readings: [], units: {} }))
  const stations = vi.fn(async () => point ? [point] : [])
  return { values, stations, providers: vi.fn(), coverage: vi.fn(), alerts: vi.fn(), kept: vi.fn() } as unknown as ChipApi & { values: typeof values, stations: typeof stations }
}
const context = (place: ChipContext['place']): ChipContext => ({ place, choices: {}, now: () => ({}) as never, formatLanguage: 'en', locale: 'en', unitTarget: () => 'millimeter' })
function env(place: ChipEnv['place']): ChipEnv {
  return {
    t: (key, params) => `${key} ${JSON.stringify(params ?? {})}`,
    place,
    number: (value, digits = 1) => value.toFixed(digits),
    percent: value => `${value * 100}%`,
    unitText: unit => unit,
    dayText: day => day,
    now: () => ({}) as never,
  }
}

describe('the station a question about a place is read at', () => {
  it('is the place itself where the place is a station, and the nearest station where it is a town', () => {
    expect(stationOf(STATION_PLACE)).toEqual({ id: '02564', name: 'Kiel-Holtenau' })
    expect(stationOf(TOWN)).toEqual({ id: '00125', name: 'Andechs-Rothenfeld' })
  })

  it('is what the questions that read a station say they read', () => {
    expect(season.readsStation).toBe(true)
    expect(day.readsStation).toBe(true)
    // the forecast finds its own nearest point and says so itself
    expect(rain.readsStation).toBeUndefined()
  })
})

describe('the rain question for a town', () => {
  it('fetches the forecast of the point nearest the town where it is within reach, and names it', async () => {
    const backend = api({ ...POINT, distance: 1.2 })
    const loaded = await rain.load(context(TOWN), backend) as { far: boolean, point: { station_id: string } }
    expect(loaded.far).toBe(false)
    expect(backend.stations).toHaveBeenCalledWith(expect.objectContaining({ latitude: 47.7614, longitude: 11.5583, rank: 1 }))
    expect(backend.values).toHaveBeenCalledWith(expect.objectContaining({ stations: 'M0814' }))
    expect(rain.actions(env(TOWN), {}, loaded)).toHaveLength(1)
  })

  it('fetches no forecast where the nearest point is farther than the reach, answers nothing and says there is none near, naming it', async () => {
    const backend = api({ ...POINT, name: 'MUENCHEN-STADT', station_id: '10865', distance: PLACE_REACH_KM + 0.1 })
    const loaded = await rain.load(context(TOWN), backend) as { far: boolean }
    expect(loaded.far).toBe(true)
    expect(backend.values).not.toHaveBeenCalled()
    expect(rain.answer(loaded, context(TOWN))).toBeNull()
    const said = rain.empty(loaded, env(TOWN), {})
    expect(said).toContain('ask.rain.far')
    expect(said).toContain('"reach":50')
    expect(said).toContain('MUENCHEN-STADT')
    expect(said).toContain('"place":"Bad Tölz"')
    // no link into the forecast of a point that is another place's
    expect(rain.actions(env(TOWN), {}, loaded)).toEqual([])
  })

  it('is within reach at exactly the reach', async () => {
    const backend = api({ ...POINT, distance: PLACE_REACH_KM })
    const loaded = await rain.load(context(TOWN), backend) as { far: boolean }
    expect(loaded.far).toBe(false)
  })

  it('takes the distance from the positions where the backend gives none', async () => {
    // a point 1 degree of latitude from the town, about 111 km
    const backend = api({ ...POINT, latitude: 48.7614, longitude: 11.5583 })
    const loaded = await rain.load(context(TOWN), backend) as { far: boolean }
    expect(loaded.far).toBe(true)
  })

  it('is as it was for a station, whatever the distance of the forecast point: a station is the place, not a town to be reached', async () => {
    const backend = api({ ...POINT, distance: 400 })
    const loaded = await rain.load(context(STATION_PLACE), backend) as { far: boolean }
    expect(loaded.far).toBe(false)
    expect(backend.values).toHaveBeenCalled()
  })

  it('says none for a place with no forecast point at all, as it did', async () => {
    expect(await rain.load(context(TOWN), api(null))).toBeNull()
  })
})

describe('the download question for a town (GH-3791)', () => {
  const sources = [
    { provider: 'dwd', name: 'DWD', countryCode: 'DE', network: 'observation', dataset: 'temperature_air', parameter: 'temperature_air_mean_2m' },
    { provider: 'noaa', name: 'NOAA', countryCode: 'US', network: 'ghcn', dataset: 'data', parameter: 'temperature_air_mean_2m' },
  ] as never
  const view = (place: Parameters<typeof env>[0]) => download.present(sources, sources, env(place), {})
  const itemOf = (place: Parameters<typeof env>[0], provider: string) => view(place).list!.items.find(item => item.key.startsWith(provider))!

  it('labels the DWD row with the station, its distance and the town, and opens that station, where the station is within reach', () => {
    const item = itemOf(TOWN, 'dwd')
    expect(item.place).toContain('ask.download.station')
    expect(item.place).toContain('"station":"Andechs-Rothenfeld"')
    expect(item.place).toContain('"distance":"37"')
    expect(item.place).toContain('"place":"Bad Tölz"')
    expect((item.to as { query: Record<string, string> }).query.stations).toBe('00125')
  })

  it('names the town and no station for a station that is the place, as it did', () => {
    const item = itemOf(STATION_PLACE, 'dwd')
    expect(item.place).toBe('Kiel-Holtenau')
    expect((item.to as { query: Record<string, string> }).query.stations).toBe('02564')
  })

  it('offers no station and names none beyond 50 km: the row opens the service, and says nothing of a place it does not serve', () => {
    const far = { ...TOWN, town: { station: { ...TOWN.town.station, distanceKm: 466 } } }
    const item = itemOf(far, 'dwd')
    expect(item.place).toBeUndefined()
    expect((item.to as { query: Record<string, string> }).query).not.toHaveProperty('stations')
  })

  it('has no station in the row of another service, whatever the place', () => {
    const item = itemOf(TOWN, 'noaa')
    expect(item.place).toBeUndefined()
    expect((item.to as { query: Record<string, string> }).query).not.toHaveProperty('stations')
  })
})
