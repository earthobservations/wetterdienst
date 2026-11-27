import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  dayOfRow,
  daysFromToday,
  forecastDays,
  isOutOfSeason,
  nearestUvPlace,
  POLLEN_CLASSES,
  pollenClass,
  pollenFill,
  pollenPartsOfState,
  pollenValuesQuery,
  rememberedPart,
  rememberPart,
  selectedPart,
  stateOfStation,
  stateQuery,
  statesOfRegion,
  UV_CLASSES,
  UV_COLORS,
  uvClass,
  uvPlaceQuery,
  uvValuesQuery,
} from '../../app/utils/uv-pollen'
import { observationStation, POLLEN_REGION_STATIONS, uvPlace } from '../helpers/uv-pollen'

// The "UV & pollen" panel's rules (GH-4501), without a request or a component: which pollen regions a state has, which place and
// which state a forecast station is given, what class a number is, and which days are shown.

/** The ids of the part-regions of a state, in the order the chips come */
const idsOf = (state: string) => pollenPartsOfState(state, POLLEN_REGION_STATIONS).map(part => part.id)

describe('the pollen regions of a state', () => {
  // DWD's 27 regions are one or two states each: Hamburg, Bremen, Berlin and Saarland have none of their own
  it.each([
    ['Schleswig-Holstein', ['11', '12']],
    ['Hamburg', ['11', '12']],
    ['Mecklenburg-Vorpommern', ['20']],
    ['Niedersachsen', ['31', '32']],
    ['Bremen', ['31', '32']],
    ['Nordrhein-Westfalen', ['41', '42', '43']],
    ['Brandenburg', ['50']],
    ['Berlin', ['50']],
    ['Sachsen-Anhalt', ['61', '62']],
    ['Thüringen', ['71', '72']],
    ['Sachsen', ['81', '82']],
    ['Hessen', ['91', '92']],
    ['Rheinland-Pfalz', ['101', '102', '103']],
    // the part that is named for the state is the first chip, and so the one that is preselected
    ['Saarland', ['103', '101', '102']],
    ['Baden-Württemberg', ['111', '112', '113']],
    ['Bayern', ['121', '122', '123', '124']],
  ])('%s has the part-regions %j', (state, ids) => {
    expect(idsOf(state)).toEqual(ids)
  })

  it('has one to four of them for each of the 16 states, and every one of the 27 regions belongs to a state', () => {
    const states = ['Schleswig-Holstein', 'Hamburg', 'Mecklenburg-Vorpommern', 'Niedersachsen', 'Bremen', 'Nordrhein-Westfalen', 'Brandenburg', 'Berlin', 'Sachsen-Anhalt', 'Thüringen', 'Sachsen', 'Hessen', 'Rheinland-Pfalz', 'Saarland', 'Baden-Württemberg', 'Bayern']
    expect(states).toHaveLength(16)
    for (const state of states)
      expect(idsOf(state).length).toBeGreaterThanOrEqual(1)
    for (const state of states)
      expect(idsOf(state).length).toBeLessThanOrEqual(4)
    const covered = new Set(states.flatMap(idsOf))
    expect([...covered].sort()).toEqual(POLLEN_REGION_STATIONS.map(region => region.station_id).sort())
  })

  it('compares a state whole: Sachsen is neither Sachsen-Anhalt nor Niedersachsen', () => {
    expect(idsOf('Sachsen')).not.toContain('61')
    expect(idsOf('Sachsen')).not.toContain('31')
    expect(idsOf('Niedersachsen')).not.toContain('81')
    expect(idsOf('Sachsen-Anhalt')).toEqual(['61', '62'])
  })

  it('finds no region for a state that is none, or that is not written as DWD writes it: no pollen part', () => {
    expect(idsOf('Österreich')).toEqual([])
    expect(idsOf('Sach')).toEqual([])
    expect(idsOf('')).toEqual([])
    expect(idsOf('   ')).toEqual([])
    expect(pollenPartsOfState('Sachsen', [])).toEqual([])
  })

  it('ignores the case and the spaces round a state', () => {
    expect(idsOf(' sachsen ')).toEqual(['81', '82'])
  })

  it('gives each part the words of its chip: its own name without the region\'s, the region\'s where it has no part', () => {
    expect(pollenPartsOfState('Sachsen', POLLEN_REGION_STATIONS).map(part => part.label)).toEqual(['Tiefland Sachsen', 'Mittelgebirge Sachsen'])
    expect(pollenPartsOfState('Mecklenburg-Vorpommern', POLLEN_REGION_STATIONS).map(part => part.label)).toEqual(['Mecklenburg-Vorpommern'])
    expect(pollenPartsOfState('Berlin', POLLEN_REGION_STATIONS).map(part => part.label)).toEqual(['Brandenburg und Berlin'])
    expect(pollenPartsOfState('Saarland', POLLEN_REGION_STATIONS)[0]).toEqual({ id: '103', label: 'Saarland', name: 'Rheinland-Pfalz und Saarland: Saarland' })
  })

  it('splits a region\'s states at "und"', () => {
    expect(statesOfRegion('Niedersachsen und Bremen')).toEqual(['Niedersachsen', 'Bremen'])
    expect(statesOfRegion('Rheinland-Pfalz und Saarland')).toEqual(['Rheinland-Pfalz', 'Saarland'])
    expect(statesOfRegion('Sachsen-Anhalt')).toEqual(['Sachsen-Anhalt'])
    expect(statesOfRegion('')).toEqual([])
  })
})

describe('the state of a forecast station', () => {
  const dresden = { latitude: 51.13, longitude: 13.75 }

  it('is the region of the nearest station of the observation network', () => {
    const stations = [
      observationStation('00001', 'Far', 'Bayern', 48.1, 11.5),
      observationStation('01048', 'Dresden-Klotzsche', 'Sachsen', 51.1278, 13.7543),
    ]
    expect(stateOfStation(dresden, stations)).toBe('Sachsen')
  })

  it('is none where the nearest station is farther than 50 km: a station in another country inside the box of Germany has no state of ours', () => {
    expect(stateOfStation({ latitude: 52.3, longitude: 4.77 }, [observationStation('02290', 'Emden', 'Niedersachsen', 53.35, 7.2)])).toBeNull()
    // 50 km is the reach, the same as for a place's station
    expect(stateOfStation({ latitude: 51.0, longitude: 13.75 }, [observationStation('a', 'A', 'Sachsen', 51.0 + 49 / 111.2, 13.75)])).toBe('Sachsen')
    expect(stateOfStation({ latitude: 51.0, longitude: 13.75 }, [observationStation('a', 'A', 'Sachsen', 51.0 + 51 / 111.2, 13.75)])).toBeNull()
  })

  it('is none where the stations have no region, and for no station', () => {
    expect(stateOfStation(dresden, [observationStation('a', 'A', '', 51.13, 13.75)])).toBeNull()
    expect(stateOfStation(dresden, [{ ...observationStation('a', 'A', 'Sachsen', 51.13, 13.75), region: null }])).toBeNull()
    expect(stateOfStation(dresden, [])).toBeNull()
  })

  it('trims the name of the state', () => {
    expect(stateOfStation(dresden, [observationStation('a', 'A', ' Sachsen ', 51.13, 13.75)])).toBe('Sachsen')
  })
})

describe('the place of the UV index', () => {
  const dresden = uvPlace('dresden', 'Dresden', 51.1278, 13.7543)

  it('is the nearest place within 100 km, with its distance', () => {
    const found = nearestUvPlace({ latitude: 51.2, longitude: 13.75 }, [uvPlace('berlin', 'Berlin', 52.4676, 13.402), dresden])
    expect(found?.station.name).toBe('Dresden')
    expect(found?.distanceKm).toBeCloseTo(8, 0)
  })

  it('is none beyond 100 km, and a place at 99 km is one', () => {
    const at = (km: number) => uvPlace('p', 'P', 50 + km / 111.195, 10)
    expect(nearestUvPlace({ latitude: 50, longitude: 10 }, [at(99)])?.station.station_id).toBe('p')
    expect(nearestUvPlace({ latitude: 50, longitude: 10 }, [at(101)])).toBeNull()
  })

  it('is none for no place, and for one that has no position', () => {
    expect(nearestUvPlace({ latitude: 51, longitude: 13 }, [])).toBeNull()
    expect(nearestUvPlace({ latitude: 51, longitude: 13 }, [{ ...dresden, latitude: null, longitude: null }])).toBeNull()
  })
})

describe('the WHO class of a UV index', () => {
  it.each([
    [0, 'low'],
    [1, 'low'],
    [2, 'low'],
    [3, 'moderate'],
    [5, 'moderate'],
    [6, 'high'],
    [7, 'high'],
    [8, 'veryHigh'],
    [10, 'veryHigh'],
    [11, 'extreme'],
    [14, 'extreme'],
  ])('%s is %s', (value, cls) => {
    expect(uvClass(value)).toBe(cls)
  })

  it('rounds a number between two indices to the nearest, as the WHO does', () => {
    expect(uvClass(2.4)).toBe('low')
    expect(uvClass(2.6)).toBe('moderate')
    expect(uvClass(10.6)).toBe('extreme')
  })

  it('is none for a day with no value', () => {
    expect(uvClass(null)).toBeNull()
    expect(uvClass(undefined)).toBeNull()
    expect(uvClass(Number.NaN)).toBeNull()
  })

  it('has the five classes, each in a colour whose number is legible on it (4.5:1, WCAG 1.4.3)', () => {
    expect(Object.keys(UV_COLORS)).toEqual([...UV_CLASSES])
    const luminance = (hex: string) => {
      const [r, g, b] = [1, 3, 5].map(at => Number.parseInt(hex.slice(at, at + 2), 16) / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
      return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
    }
    for (const cls of UV_CLASSES) {
      const [hi, lo] = [luminance(UV_COLORS[cls].fill), luminance(UV_COLORS[cls].text)].sort((a, b) => b - a)
      expect((hi! + 0.05) / (lo! + 0.05), cls).toBeGreaterThanOrEqual(4.5)
    }
  })
})

describe('the class of a pollen level', () => {
  it('has DWD\'s seven steps, 0 to 3 in steps of a half', () => {
    expect([0, 0.5, 1, 1.5, 2, 2.5, 3].map(pollenClass)).toEqual(['none', 'noneToLow', 'low', 'lowToMedium', 'medium', 'mediumToHigh', 'high'])
    expect(POLLEN_CLASSES).toHaveLength(7)
  })

  it('is none for no value, and for a number that is no step', () => {
    for (const level of [null, undefined, Number.NaN, 0.25, 3.5, -1, 4])
      expect(pollenClass(level)).toBeNull()
  })

  it('fills the scale by the level: nothing for no value, all of it for the highest', () => {
    expect(pollenFill(null)).toBe(0)
    expect(pollenFill(0)).toBe(0)
    expect(pollenFill(1.5)).toBe(0.5)
    expect(pollenFill(3)).toBe(1)
    expect(pollenFill(7)).toBe(0)
  })
})

describe('out of season', () => {
  it('is every level being 0 or none', () => {
    expect(isOutOfSeason([{ value: 0 }, { value: 0 }, { value: null }])).toBe(true)
    expect(isOutOfSeason([{ value: null }, { value: null }])).toBe(true)
    expect(isOutOfSeason([])).toBe(true)
  })

  it('is not so with one level above 0, a half step included', () => {
    expect(isOutOfSeason([{ value: 0 }, { value: 0.5 }, { value: null }])).toBe(false)
    expect(isOutOfSeason([{ value: 3 }])).toBe(false)
  })
})

describe('the days shown', () => {
  const rows = (...days: string[]) => days.map(day => ({ timestamp: `${day}T00:00:00+00:00` }))

  it('reads the German date of a row from its timestamp, which is the date at 00:00 UTC', () => {
    expect(dayOfRow({ timestamp: '2026-11-27T00:00:00+00:00' })).toBe('2026-11-27')
    expect(dayOfRow({ timestamp: 'x' })).toBeNull()
    expect(dayOfRow({ timestamp: '2026-13-45T00:00:00+00:00' })).toBeNull()
  })

  it('is today and the two days after, whatever the order of the rows, each once', () => {
    expect(forecastDays(rows('2026-11-29', '2026-11-27', '2026-11-28', '2026-11-27'), '2026-11-27')).toEqual(['2026-11-27', '2026-11-28', '2026-11-29'])
  })

  it('leaves out a day before today, which a file not yet replaced still holds, and shows no more than three', () => {
    expect(forecastDays(rows('2026-11-26', '2026-11-27', '2026-11-28'), '2026-11-27')).toEqual(['2026-11-27', '2026-11-28'])
    expect(forecastDays(rows('2026-11-27', '2026-11-28', '2026-11-29', '2026-11-30'), '2026-11-27')).toHaveLength(3)
  })

  it('has none where every day is over, or the rows have no date', () => {
    expect(forecastDays(rows('2026-11-20'), '2026-11-27')).toEqual([])
    expect(forecastDays([{ timestamp: 'x' }], '2026-11-27')).toEqual([])
    expect(forecastDays([], '2026-11-27')).toEqual([])
  })

  it('counts calendar days from today, over the end of a month and the change of the clock', () => {
    expect(daysFromToday('2026-11-27', '2026-11-27')).toBe(0)
    expect(daysFromToday('2026-12-01', '2026-11-30')).toBe(1)
    expect(daysFromToday('2026-03-30', '2026-03-28')).toBe(2)
    expect(daysFromToday('2026-10-27', '2026-10-24')).toBe(3)
  })
})

describe('the queries', () => {
  it('asks the nearest place of the UV index for a position, and its values by the place\'s id', () => {
    expect(uvPlaceQuery({ latitude: 51.13, longitude: 13.75 })).toEqual({ provider: 'dwd', network: 'uvi', parameters: 'daily/data', latitude: '51.13', longitude: '13.75', rank: '1' })
    expect(uvValuesQuery('dresden')).toMatchObject({ provider: 'dwd', network: 'uvi', parameters: 'daily/data/uv_index_max', stations: 'dresden', shape: 'long' })
  })

  it('asks the nearest station of the observation network for the state of a position', () => {
    expect(stateQuery({ latitude: 51.13, longitude: 13.75 })).toEqual({ provider: 'dwd', network: 'observation', parameters: 'daily/climate_summary', latitude: '51.13', longitude: '13.75', rank: '1' })
  })

  it('asks the eight pollen types of the parts of a state in one request', () => {
    const query = pollenValuesQuery(['81', '82'])
    expect(query.stations).toBe('81,82')
    expect(query.parameters!.split(',')).toEqual([
      'daily/data/pollen_load_hazel',
      'daily/data/pollen_load_alder',
      'daily/data/pollen_load_ash',
      'daily/data/pollen_load_birch',
      'daily/data/pollen_load_grass',
      'daily/data/pollen_load_rye',
      'daily/data/pollen_load_mugwort',
      'daily/data/pollen_load_ragweed',
    ])
    expect(query).toMatchObject({ provider: 'dwd', network: 'pollen' })
  })
})

describe('what the reader chose', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('is remembered for a state on its own: Sachsen\'s choice is not Bayern\'s', () => {
    expect(rememberedPart('Sachsen')).toBeNull()
    rememberPart('Sachsen', '82')
    rememberPart('Bayern', '124')
    expect(rememberedPart('Sachsen')).toBe('82')
    expect(rememberedPart('Bayern')).toBe('124')
    expect(rememberedPart('Hessen')).toBeNull()
  })

  it('takes the remembered part where it is still one of the state\'s, else the first', () => {
    const parts = pollenPartsOfState('Sachsen', POLLEN_REGION_STATIONS)
    expect(selectedPart(parts, '82')?.id).toBe('82')
    expect(selectedPart(parts, null)?.id).toBe('81')
    // a part DWD has since dropped, or another state's, is not one
    expect(selectedPart(parts, '999')?.id).toBe('81')
    expect(selectedPart([], '81')).toBeNull()
  })

  it('works with no storage at all: nothing is remembered and nothing fails', () => {
    const refusing = {
      getItem: () => {
        throw new DOMException('denied', 'SecurityError')
      },
      setItem: () => {
        throw new DOMException('quota', 'QuotaExceededError')
      },
    }
    vi.stubGlobal('localStorage', refusing)
    expect(() => rememberPart('Sachsen', '82')).not.toThrow()
    expect(rememberedPart('Sachsen')).toBeNull()
  })

  it('reads what is no JSON, or no object, as nothing chosen', () => {
    localStorage.setItem('wd-pollen-part', 'not json')
    expect(rememberedPart('Sachsen')).toBeNull()
    localStorage.setItem('wd-pollen-part', '["81"]')
    expect(rememberedPart('Sachsen')).toBeNull()
    localStorage.setItem('wd-pollen-part', '{"Sachsen":82}')
    expect(rememberedPart('Sachsen')).toBeNull()
    // and the next choice replaces it
    rememberPart('Sachsen', '82')
    expect(rememberedPart('Sachsen')).toBe('82')
  })
})
