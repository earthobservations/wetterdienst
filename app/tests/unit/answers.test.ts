import type { Reading } from '../../app/utils/answers'
import type { Provider } from '../../shared/types/api'
import { DateTime } from 'luxon'
import { describe, expect, it } from 'vitest'
import {
  beaufort,
  hourlyNetworks,
  hourlyTemperatureIn,
  lastBoxingDay,
  lastSummer,
  RAIN_AMOUNT,
  RAIN_CHANCE,
  rainTomorrow,
  windOnDay,
  windWindow,
} from '../../app/utils/answers'

// The answers of the home page's questions are worked out from what the backend answers, and say nothing the
// data does not: these hold each to a few readings whose answer is known by hand.

const BERLIN = 'Europe/Berlin'
const NOW = DateTime.fromISO('2026-10-29T10:00:00', { zone: BERLIN })

/** MOSMIX's hourly readings from `from` on (UTC), the value at a full hour being the hour before it */
function hourly(parameter: string, from: string, values: number[]): Reading[] {
  const start = DateTime.fromISO(from, { zone: 'utc' })
  return values.map((value, index) => ({ parameter, timestamp: start.plus({ hours: index }).toISO()!, value }))
}

describe('will it rain tomorrow', () => {
  // tomorrow in Berlin is 30 October, 23:00 UTC on the 29th to 23:00 UTC on the 30th; its first hour's reading is at 00:00 UTC
  const dry = () => hourly(RAIN_AMOUNT, '2026-10-29T12:00:00Z', Array.from({ length: 48 }).fill(0))

  it('says no for a dry day, and the hours of the day in the place\'s time', () => {
    const answer = rainTomorrow(dry(), BERLIN, NOW)!
    expect(answer.verdict).toBe('no')
    expect(answer.day).toBe('2026-10-30')
    expect(answer.total).toBe(0)
    expect(answer.hours).toHaveLength(24)
    expect(answer.hours[0]!.label).toBe('00')
    expect(answer.wettest).toBeNull()
    expect(answer.maxChance).toBeNull()
  })

  it('says yes for a millimetre, and names the wettest hour', () => {
    const readings = dry().map(reading => reading.timestamp.startsWith('2026-10-30T14:00') ? { ...reading, value: 0.8 } : reading.timestamp.startsWith('2026-10-30T15:00') ? { ...reading, value: 0.4 } : reading)
    const answer = rainTomorrow(readings, BERLIN, NOW)!
    expect(answer.verdict).toBe('yes')
    expect(answer.total).toBe(1.2)
    expect(answer.wetHours).toBe(2)
    // 14:00 UTC is 15:00 in Berlin and closes the hour from 14:00
    expect(answer.wettest).toEqual({ hour: 14, amount: 0.8 })
  })

  it('says maybe for a little rain, and for a fair chance of it', () => {
    const little = dry().map(reading => reading.timestamp.startsWith('2026-10-30T10:00') ? { ...reading, value: 0.3 } : reading)
    expect(rainTomorrow(little, BERLIN, NOW)!.verdict).toBe('maybe')
    const chance = [...dry(), ...hourly(RAIN_CHANCE, '2026-10-30T00:00:00Z', [0.1, 0.4, 0.2])]
    const answer = rainTomorrow(chance, BERLIN, NOW)!
    expect(answer.verdict).toBe('maybe')
    expect(answer.maxChance).toBe(0.4)
  })

  it('gives no answer where the forecast does not reach most of the day', () => {
    expect(rainTomorrow(hourly(RAIN_AMOUNT, '2026-10-29T12:00:00Z', Array.from({ length: 20 }).fill(0)), BERLIN, NOW)).toBeNull()
  })
})

/** Monthly means of June, July and August from `first` to `last`, each summer `base(year)` */
function summers(first: number, last: number, base: (year: number) => number): Reading[] {
  return Array.from({ length: last - first + 1 }, (_, index) => first + index).flatMap(year => [6, 7, 8].map(month => ({
    parameter: 'temperature_air_mean_2m',
    timestamp: `${year}-0${month}-01T00:00:00.000000+00:00`,
    value: base(year),
  })))
}

describe('was last summer hotter than usual', () => {
  it('compares the last complete summer with 1991 to 2020', () => {
    const readings = summers(1986, 2026, year => year === 2026 ? 18 : 16)
    const answer = lastSummer(readings, NOW)!
    expect(answer.year).toBe(2026)
    expect(answer.normal).toBe(16)
    expect([answer.normalFrom, answer.normalTo]).toEqual([1991, 2020])
    expect(answer.anomaly).toBe(2)
    expect(answer.verdict).toBe('hotter')
    expect(answer.rank).toBe(1)
    expect(answer.summers).toBe(41)
    expect(answer.bars.at(-1)).toMatchObject({ label: '2026', value: 2, highlight: true })
  })

  it('does not count a summer that is not over, or one with a month missing', () => {
    const july = DateTime.fromISO('2026-07-15T12:00:00', { zone: BERLIN })
    expect(lastSummer(summers(1986, 2026, () => 16), july)!.year).toBe(2025)
    const gap = summers(1986, 2026, () => 16).filter(reading => !reading.timestamp.startsWith('2026-07'))
    expect(lastSummer(gap, NOW)!.year).toBe(2025)
  })

  it('calls half a degree either way usual, and below it cooler', () => {
    expect(lastSummer(summers(1986, 2026, year => year === 2026 ? 16.4 : 16), NOW)!.verdict).toBe('usual')
    expect(lastSummer(summers(1986, 2026, year => year === 2026 ? 15.2 : 16), NOW)!.verdict).toBe('cooler')
  })

  it('compares with the record before it where 1991 to 2020 is not covered, and gives no answer for a short one', () => {
    const answer = lastSummer(summers(2005, 2026, () => 16), NOW)!
    expect([answer.normalFrom, answer.normalTo]).toEqual([2005, 2025])
    expect(lastSummer(summers(2020, 2026, () => 16), NOW)).toBeNull()
  })
})

describe('how windy was it on a day', () => {
  function days(gusts: Record<string, number>, means: Record<string, number> = {}): Reading[] {
    return [
      ...Object.entries(gusts).map(([day, value]) => ({ parameter: 'wind_gust_max', timestamp: `${day}T00:00:00+00:00`, value })),
      ...Object.entries(means).map(([day, value]) => ({ parameter: 'wind_speed_mean', timestamp: `${day}T00:00:00+00:00`, value })),
    ]
  }

  it('knows the Beaufort scale at its edges', () => {
    expect([0, 0.3, 3.3, 3.4, 10.8, 17.1, 17.2, 32.7, 40].map(beaufort)).toEqual([0, 1, 2, 3, 6, 7, 8, 12, 12])
  })

  it('judges a day by its strongest gust, and against the days around it', () => {
    const answer = windOnDay(days({ '2025-12-25': 12, '2025-12-26': 22, '2025-12-27': 9 }, { '2025-12-26': 9.5 }), '2025-12-26')!
    expect(answer.verdict).toBe('stormy')
    expect(answer.gustBeaufort).toBe(9)
    expect(answer.beaufort).toBe(5)
    expect([answer.stronger, answer.around]).toEqual([0, 2])
    expect(answer.bars.map(bar => bar.highlight)).toEqual([false, true, false])
    expect(answer.barsAreGusts).toBe(true)
  })

  it('judges by the mean where no gust is published, and gives no answer for a day without readings', () => {
    const answer = windOnDay(days({}, { '2025-12-26': 3 }), '2025-12-26')!
    expect(answer.verdict).toBe('calm')
    expect(answer.barsAreGusts).toBe(false)
    expect(windOnDay(days({ '2025-12-25': 12 }), '2025-12-26')).toBeNull()
  })

  it('means last year\'s 26 December until this year\'s readings can be in, and fetches no day of the future', () => {
    expect(lastBoxingDay(NOW)).toBe('2025-12-26')
    expect(lastBoxingDay(DateTime.fromISO('2026-12-28T09:00:00'))).toBe('2026-12-26')
    expect(windWindow('2025-12-26', NOW)).toEqual({ from: '2025-12-19', to: '2026-01-02' })
    expect(windWindow('2026-10-27', NOW)).toEqual({ from: '2026-10-20', to: '2026-10-28' })
  })
})

describe('where can I download hourly temperatures', () => {
  const network = (name: string, kind: Provider['networks'][number]['kind'], resolutions: string[]) => ({
    network: name,
    kind,
    url: '',
    copyright: '',
    auth: false,
    date_required: false,
    parameters: 1,
    resolutions: resolutions.map(resolution => ({ name: resolution, datasets: [] })),
  })

  it('asks only the measurement networks with an hourly resolution', () => {
    const providers = [
      { provider: 'dwd', networks: [network('observation', 'observation', ['hourly', 'daily']), network('mosmix', 'forecast', ['hourly']), network('radar', 'radar', [])] },
      { provider: 'aemet', networks: [network('observation', 'observation', ['daily'])] },
    ] as unknown as Provider[]
    expect(hourlyNetworks(providers).map(({ provider, network }) => `${provider.provider}/${network}`)).toEqual(['dwd/observation'])
  })

  it('finds the hourly air temperature, the dataset named for it first', () => {
    const parameter = (name: string) => ({ name, name_original: name, unit_type: 'temperature', unit: 'degree_celsius', unit_source: undefined, description: '' })
    expect(hourlyTemperatureIn({
      hourly: {
        description: null,
        datasets: {
          moisture: { description: null, parameters: [parameter('temperature_air_2m')] },
          temperature_air: { description: null, parameters: [parameter('temperature_air_2m')] },
        },
      },
    } as any)).toEqual({ dataset: 'temperature_air', parameter: 'temperature_air_2m' })
    expect(hourlyTemperatureIn({ hourly: { description: null, datasets: { data: { description: null, parameters: [parameter('temperature_air_mean_2m')] } } } } as any))
      .toEqual({ dataset: 'data', parameter: 'temperature_air_mean_2m' })
    expect(hourlyTemperatureIn({ daily: { description: null, datasets: {} } } as any)).toBeNull()
  })
})
