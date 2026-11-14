import type { WeatherKind } from './weather-kind'

/**
 * The weather symbols of the forecast chart: the set of Yr (Yr/NRK), as `public/yr-symbols/` holds it, in its light and dark
 * mode. The files are those of the repository nrkno/yr-weather-symbols (symbols/lightmode and symbols/darkmode), unchanged.
 * Their LICENSE is CC BY 4.0: the credit is under the chart (`meteogram.chart.symbolsCredit`) and, with the licence text, at
 * the end of `/third-party-licenses.txt`.
 *
 * The set names its symbols by the number of the Yr API (`01d` clear sky by day, `01n` by night, `04` cloudy). A
 * symbol is the picture only: the words for it are `meteogram.chart.weather.<kind>` (GH-3223), and the symbols are
 * hidden from assistive technology.
 */

/** The files of the set the chart draws: `public/yr-symbols/<mode>/<id>.svg` */
export const YR_SYMBOLS = ['01d', '01n', '03d', '03n', '04', '46', '09', '10', '47', '12', '49', '13', '50', '15', '22'] as const
export type YrSymbol = typeof YR_SYMBOLS[number]

/** The sky as the symbols have it: clear, partly cloudy and cloudy */
export type Sky = 'clear' | 'partlyCloudy' | 'cloudy'

export interface SymbolInput {
  kind: WeatherKind
  /** whether the sun is down: the sky symbols have a night variant */
  night: boolean
  /** the precipitation of the hour in millimetres, which tells a light rain from a heavy one; null where unknown */
  precipitationMm: number | null
  /** the sky from the cloud cover, for the kinds that say nothing of it (wind, dust, a funnel cloud) */
  sky: Sky
}

function skySymbol(sky: Sky, night: boolean): YrSymbol {
  if (sky === 'clear')
    return night ? '01n' : '01d'
  if (sky === 'partlyCloudy')
    return night ? '03n' : '03d'
  return '04'
}

/**
 * The symbol for the weather of an hour. Yr has none for wind, dust, a funnel cloud or blowing snow: the first three are
 * drawn as the sky the cloud cover makes and blowing snow as light snow, and the words say what the picture does not.
 */
export function yrSymbolFor({ kind, night, precipitationMm, sky }: SymbolInput): YrSymbol {
  const mm = precipitationMm ?? 0
  switch (kind) {
    case 'thunderstorm':
      return '22'
    case 'rain':
      return mm >= 4 ? '10' : mm > 0 && mm < 0.5 ? '46' : '09'
    case 'drizzle':
      return '46'
    case 'sleet':
      return mm > 0 && mm < 0.5 ? '47' : '12'
    case 'snow':
      return mm >= 2 ? '50' : mm > 0 && mm < 0.3 ? '49' : '13'
    case 'blowingSnow':
      return '49'
    case 'fog':
      return '15'
    case 'clear':
      return skySymbol('clear', night)
    case 'partlyCloudy':
      return skySymbol('partlyCloudy', night)
    case 'cloudy':
      return '04'
    default:
      // wind, dust, funnelCloud
      return skySymbol(sky, night)
  }
}

/** The address of a symbol's file, in the mode that reads on the page */
export function yrSymbolUrl(symbol: YrSymbol, dark: boolean): string {
  return `/yr-symbols/${dark ? 'darkmode' : 'lightmode'}/${symbol}.svg`
}
