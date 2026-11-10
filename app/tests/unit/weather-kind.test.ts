import type { WeatherKind } from '../../app/utils/weather-kind'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { WEATHER_ICONS, WEATHER_KINDS, weatherCodeToKind } from '../../app/utils/weather-kind'

// The day cards of the compact forecast name the weather in words for a screen reader (WCAG 1.1.1), so the
// name has to be right for every present-weather code `ww` of the WMO's table 4677 it is given for. The
// ranges below are the table's: a code is listed with the phenomenon the table gives it.
const range = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, i) => from + i)

const TABLE: [WeatherKind | null, number[]][] = [
  ['clear', [0]],
  ['partlyCloudy', [1, 2]],
  ['cloudy', [3]],
  // 04-06 haze, smoke, widespread dust in suspension
  [null, range(4, 6)],
  // 07 blowing dust or sand, 08 dust whirls, 09 dust or sand storm in sight
  ['dust', range(7, 9)],
  // 10 mist, 11-12 patches of shallow fog
  ['fog', range(10, 12)],
  // 13 lightning without thunder, 14-16 precipitation in sight, not (or not near) the station
  [null, range(13, 16)],
  ['thunderstorm', [17]],
  ['wind', [18]],
  // 19 funnel cloud (tornado or waterspout): what happened, not the sky of the day (GH-3965)
  ['funnelCloud', [19]],
  // 20-29: the hour before, not at the observation
  ['drizzle', [20]],
  ['rain', [21, 24, 25]],
  ['snow', [22, 26]],
  ['sleet', [23]],
  [null, [27]],
  ['fog', [28]],
  ['thunderstorm', [29]],
  // 30-35 duststorm or sandstorm, 36-39 drifting or blowing snow
  ['dust', range(30, 35)],
  ['blowingSnow', range(36, 39)],
  ['fog', range(40, 49)],
  // 50-55 drizzle, 56-57 freezing drizzle, 58-59 drizzle and rain
  ['drizzle', range(50, 59)],
  // 60-65 rain, 66-67 freezing rain
  ['rain', range(60, 67)],
  // 68-69 rain or drizzle and snow
  ['sleet', [68, 69]],
  // 70-75 snow, 76 diamond dust, 77 snow grains, 78 snow crystals
  ['snow', range(70, 78)],
  // 79 ice pellets
  ['sleet', [79]],
  // 80-82 rain showers, 83-84 rain and snow showers, 85-86 snow showers, 87-90 showers of snow pellets or hail
  ['rain', range(80, 82)],
  ['sleet', [83, 84]],
  ['snow', [85, 86]],
  [null, range(87, 90)],
  // 91-94 thunderstorm in the hour before, 95-99 thunderstorm
  ['thunderstorm', range(91, 99)],
]

describe('the weather kind of a WMO present-weather code', () => {
  it('lists every code of 0 to 99 once', () => {
    expect(TABLE.flatMap(([, codes]) => codes).sort((a, b) => a - b)).toEqual(range(0, 99))
  })

  it.each(TABLE.flatMap(([kind, codes]) => codes.map(code => [code, kind] as const)))('names code %i as %s', (code, kind) => {
    expect(weatherCodeToKind(code)).toBe(kind)
  })

  // DWD's list of the codes MOSMIX and DMO deliver as `ww` (mosmix_element_weather_xls.xlsx, 15.03.2021): all of
  // them name a kind, so the forecast never falls back on the heuristic for a code it was given
  it('names a kind for every code DWD delivers in the forecasts', () => {
    const delivered = [0, 1, 2, 3, 45, 49, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 68, 69, 71, 73, 75, 80, 81, 82, 83, 84, 85, 86, 95]
    for (const code of delivered)
      expect(weatherCodeToKind(code), `code ${code}`).not.toBeNull()
  })

  it('names nothing for no code, a code outside the table or a number that is none', () => {
    for (const code of [null, undefined, Number.NaN, 100, 120, -1])
      expect(weatherCodeToKind(code)).toBeNull()
  })

  it('rounds a code that is not whole', () => {
    expect(weatherCodeToKind(60.4)).toBe('rain')
  })
})

describe('the icons and words of the weather kinds', () => {
  const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8')) as { meteogram: { chart: { weather: Record<string, string> } } }

  it('has an icon for every kind, and a word in the catalog for every kind', () => {
    expect(Object.keys(WEATHER_ICONS).sort()).toEqual([...WEATHER_KINDS].sort())
    expect(Object.keys(en.meteogram.chart.weather).sort()).toEqual([...WEATHER_KINDS].sort())
  })

  // the names are Phosphor's and are literals of the module, so the scan of the build and icon-names.test.ts hold
  // them too; this one holds that every kind has one that is no emoji and that the kinds a reader tells apart
  // are not drawn alike where the words are all there is to tell them by
  it('draws every kind as a Phosphor icon, and no emoji', () => {
    for (const icon of Object.values(WEATHER_ICONS))
      expect(icon).toMatch(/^i-ph-[a-z-]+$/)
  })

  // the table, as it is drawn: a change of an icon is a change of this test too
  it('is the table of icons the issue asks for', () => {
    expect(WEATHER_ICONS).toStrictEqual({
      thunderstorm: 'i-ph-cloud-lightning',
      rain: 'i-ph-cloud-rain',
      snow: 'i-ph-cloud-snow',
      sleet: 'i-ph-cloud-snow',
      drizzle: 'i-ph-drop-half',
      fog: 'i-ph-cloud-fog',
      wind: 'i-ph-wind',
      dust: 'i-ph-dots-nine',
      funnelCloud: 'i-ph-tornado',
      blowingSnow: 'i-ph-snowflake',
      cloudy: 'i-ph-cloud',
      partlyCloudy: 'i-ph-cloud-sun',
      clear: 'i-ph-sun',
    })
  })

  it('draws the drizzle other than the drop that stands before the amount of rain of a day card', () => {
    expect(Object.values(WEATHER_ICONS)).not.toContain('i-ph-drop')
  })

  it('draws the sky, the rain, the snow and the fog differently', () => {
    const drawn = ['clear', 'partlyCloudy', 'cloudy', 'rain', 'snow', 'fog', 'thunderstorm', 'wind'] as const
    expect(new Set(drawn.map(kind => WEATHER_ICONS[kind])).size).toBe(drawn.length)
  })

  it('draws the funnel cloud and the dust storm differently: the words are all a reader of the icon has', () => {
    expect(WEATHER_ICONS.funnelCloud).not.toBe(WEATHER_ICONS.dust)
  })

  it('names the funnel cloud for what it is, not as dust or as a clear sky', () => {
    expect(en.meteogram.chart.weather[weatherCodeToKind(19)!]).toBe('Funnel cloud')
  })

  it('names the dust and the snow storms for what they are, not as a thunderstorm', () => {
    expect(en.meteogram.chart.weather[weatherCodeToKind(33)!]).toBe('Dust or sand storm')
    expect(en.meteogram.chart.weather[weatherCodeToKind(38)!]).toBe('Blowing snow')
    expect(en.meteogram.chart.weather[weatherCodeToKind(69)!]).toBe('Sleet')
  })
})
