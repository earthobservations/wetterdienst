/**
 * What a day card of the compact view shows for the weather: a symbol, and the words it stands for
 * (`meteogram.chart.weather.<kind>`), which the card gives to a screen reader as the symbol is hidden
 * from it (WCAG 1.1.1). The name has to be right for every code the symbol is drawn for.
 */
export type WeatherKind = 'thunderstorm' | 'rain' | 'snow' | 'sleet' | 'drizzle' | 'fog' | 'wind' | 'dust' | 'blowingSnow' | 'cloudy' | 'partlyCloudy' | 'clear'

export const WEATHER_KINDS: readonly WeatherKind[] = ['thunderstorm', 'rain', 'snow', 'sleet', 'drizzle', 'fog', 'wind', 'dust', 'blowingSnow', 'cloudy', 'partlyCloudy', 'clear']

export const WEATHER_SYMBOLS: Record<WeatherKind, string> = {
  thunderstorm: '⛈',
  rain: '🌧',
  snow: '🌨',
  sleet: '🌨',
  drizzle: '💧',
  fog: '🌫',
  wind: '💨',
  dust: '🌪',
  blowingSnow: '🌨',
  cloudy: '☁',
  partlyCloudy: '⛅',
  clear: '☀',
}

/**
 * The kind of weather a WMO present-weather code `ww` (table 4677, 0..99) stands for, null where it
 * stands for none the card can name (haze, smoke, a funnel cloud, precipitation in sight but not at
 * the station, hail): the card then judges from the cloud cover and the rain of the day.
 *
 * - 00-03 the state of the sky; 04-06 haze, smoke, dust in suspension: none
 * - 07-09 blowing dust or sand, dust whirls, a dust or sand storm in sight: dust
 * - 10-12 mist, shallow fog: fog; 13 lightning, 14-16 precipitation in sight, 19 funnel cloud: none;
 *   17 thunderstorm without precipitation: thunderstorm; 18 squalls: wind
 * - 20-29 phenomena of the hour before, not at the observation: 20 drizzle, 21 rain, 22 snow, 23 rain and
 *   snow, 24 freezing drizzle or rain, 25 rain showers, 26 snow showers, 28 fog, 29 thunderstorm; 27 hail: none
 * - 30-35 dust or sand storm; 36-39 drifting or blowing snow
 * - 40-49 fog; 50-59 drizzle (also freezing, and with rain); 60-67 rain (also freezing)
 * - 68-69 rain and snow, 79 ice pellets: sleet; 70-78 snow in its forms
 * - 80-82 rain showers; 83-84 rain and snow showers: sleet; 85-86 snow showers; 87-90 showers of hail: none
 * - 91-99 thunderstorm, at the observation or in the hour before
 */
export function weatherCodeToKind(code: number | null | undefined): WeatherKind | null {
  if (code === null || code === undefined || !Number.isFinite(code))
    return null
  const c = Math.round(code)
  if (c === 0)
    return 'clear'
  if (c === 1 || c === 2)
    return 'partlyCloudy'
  if (c === 3)
    return 'cloudy'
  if (c >= 7 && c <= 9)
    return 'dust'
  if (c >= 10 && c <= 12)
    return 'fog'
  if (c === 17)
    return 'thunderstorm'
  if (c === 18)
    return 'wind'
  if (c === 20)
    return 'drizzle'
  if (c === 21 || c === 24 || c === 25)
    return 'rain'
  if (c === 22 || c === 26)
    return 'snow'
  if (c === 23)
    return 'sleet'
  if (c === 28)
    return 'fog'
  if (c === 29)
    return 'thunderstorm'
  if (c >= 30 && c <= 35)
    return 'dust'
  if (c >= 36 && c <= 39)
    return 'blowingSnow'
  if (c >= 40 && c <= 49)
    return 'fog'
  if (c >= 50 && c <= 59)
    return 'drizzle'
  if (c >= 60 && c <= 67)
    return 'rain'
  if (c === 68 || c === 69 || c === 79)
    return 'sleet'
  if (c >= 70 && c <= 78)
    return 'snow'
  if (c >= 80 && c <= 82)
    return 'rain'
  if (c === 83 || c === 84)
    return 'sleet'
  if (c === 85 || c === 86)
    return 'snow'
  if (c >= 91 && c <= 99)
    return 'thunderstorm'
  return null
}
