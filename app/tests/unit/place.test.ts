import { describe, expect, it } from 'vitest'
import { currentConditions, distanceKm, nearestStation, placeName, placeOfStation, skyPhase, skyWeather, temperatureColor } from '../../app/utils/place'

describe('placeName', () => {
  it('writes a MOSMIX name in capitals as a place is written', () => {
    expect(placeName('BERLIN-TEMPELHOF')).toBe('Berlin-Tempelhof')
    expect(placeName('KOELN/BONN')).toBe('Koeln/Bonn')
    expect(placeName('ZUERICH (TOWN/VILLE)')).toBe('Zuerich (Town/Ville)')
  })

  it('leaves a name that is not all capitals as it is', () => {
    expect(placeName('Großenkneten')).toBe('Großenkneten')
  })
})

describe('placeOfStation', () => {
  it('is null for a station with no position', () => {
    expect(placeOfStation({ station_id: '1', name: 'X', latitude: null, longitude: 3 })).toBeNull()
    expect(placeOfStation({ station_id: '1', name: null, latitude: 1, longitude: 3 })).toEqual({ id: '1', name: '1', latitude: 1, longitude: 3 })
  })
})

describe('skyPhase', () => {
  // Berlin, 21 June 2026: the sun is high at noon and well below the horizon at midnight (UTC+2)
  it('tells the day from the night', () => {
    expect(skyPhase(52.5, 13.4, new Date('2026-06-21T10:00:00Z'))).toBe('day')
    expect(skyPhase(52.5, 13.4, new Date('2026-12-21T23:00:00Z'))).toBe('night')
  })

  it('tells the morning from the evening around sunrise and sunset', () => {
    // the sun is between 6° below and 6° above the horizon in Berlin on 21 December at 07:50 and 16:00 (UTC+1)
    expect(skyPhase(52.5, 13.4, new Date('2026-12-21T06:50:00Z'))).toBe('dawn')
    expect(skyPhase(52.5, 13.4, new Date('2026-12-21T15:00:00Z'))).toBe('dusk')
  })
})

describe('skyWeather', () => {
  it('draws the kind of weather, and the cloud cover where the kind is unknown', () => {
    expect(skyWeather('thunderstorm', null)).toBe('storm')
    expect(skyWeather('drizzle', 1)).toBe('rain')
    expect(skyWeather('blowingSnow', 1)).toBe('snow')
    expect(skyWeather(null, 0.1)).toBe('clear')
    expect(skyWeather(null, 0.5)).toBe('partly')
    expect(skyWeather(null, 0.9)).toBe('cloudy')
    expect(skyWeather(null, null)).toBe('clear')
  })
})

describe('currentConditions', () => {
  const hours = Array.from({ length: 14 }, (_, i) => `2026-10-29T${String(8 + i).padStart(2, '0')}:00:00+00:00`)
  const rows = hours.flatMap((timestamp, i) => [
    { parameter: 'temperature_air_2m', timestamp, value: 5 + i },
    { parameter: 'weather_significant', timestamp, value: i < 2 ? 61 : 3 },
    { parameter: 'cloud_cover_total', timestamp, value: 0.9 },
    { parameter: 'wind_speed', timestamp, value: 3.4 },
    { parameter: 'precipitation_amount_significant_weather_last_1h', timestamp, value: 0.2 },
  ])

  it('takes the first hour that has not ended, and the six after it for the rain', () => {
    const now = currentConditions(rows, new Date('2026-10-29T08:30:00Z'))!
    expect(now.at.toISOString()).toBe('2026-10-29T09:00:00.000Z')
    expect(now.temperature).toBe(6)
    expect(now.kind).toBe('rain')
    expect(now.sky).toBe('rain')
    expect(now.windSpeed).toBe(3.4)
    expect(now.precipitationNext6h).toBe(1.2)
    // every second hour after it
    expect(now.next.map(hour => hour.at.getUTCHours())).toEqual([11, 13, 15, 17, 19, 21])
    expect(now.next[0]!.sky).toBe('cloudy')
  })

  it('is null where the forecast has ended', () => {
    expect(currentConditions(rows, new Date('2026-10-30T12:00:00Z'))).toBeNull()
  })
})

describe('the place\'s neighbours', () => {
  it('measures distances on the earth and finds the nearest station', () => {
    expect(distanceKm({ latitude: 52.52, longitude: 13.4 }, { latitude: 48.14, longitude: 11.58 })).toBeCloseTo(504, -1)
    const stations = [{ id: 'm', latitude: 48.14, longitude: 11.58 }, { id: 'h', latitude: 53.55, longitude: 9.99 }]
    expect(nearestStation(stations, { latitude: 53, longitude: 10 })?.station.id).toBe('h')
    expect(nearestStation([], { latitude: 53, longitude: 10 })).toBeNull()
  })
})

describe('temperatureColor', () => {
  it('runs from the logo\'s blue to its coral', () => {
    expect(temperatureColor(-20)).toBe('var(--color-brand-700)')
    expect(temperatureColor(35)).toBe('var(--color-ember)')
    expect(temperatureColor(15)).toContain('color-mix')
  })
})
