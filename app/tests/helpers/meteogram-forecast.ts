/**
 * A MOSMIX-like forecast for the meteogram's tests: every series the chart draws, hourly for the whole run (MOSMIX-L has
 * no "hourly, then 3-hourly" layout any more: every element keeps its cadence to the last step), deterministic. Rain on
 * the second evening, a cold night, a front that turns the wind, a thunderstorm. The rain also has the 6, 12 and 24 hour totals
 * MOSMIX gives, each the sum of the hourly amounts it covers, so that every cadence says the same (`planPrecipitation` then
 * takes the hourly amounts throughout; `mosmix-run.ts` has real runs, where it does not).
 */
export interface ForecastOptions {
  /** the first stamp, ISO */
  start?: string
  /** the hours the run covers */
  hours?: number
  /** the series to leave out, by the parameter name */
  without?: string[]
}

export const FORECAST_START = '2026-10-01T00:00:00+00:00'

export interface ForecastValue {
  station_id: string
  resolution: string
  dataset: string
  parameter: string
  timestamp: string
  value: number | null
  quality_flags: null
}

export function forecastValues({ start = FORECAST_START, hours = 240, without = [] }: ForecastOptions = {}): ForecastValue[] {
  const t0 = new Date(start).getTime()
  const out: ForecastValue[] = []
  const add = (parameter: string, offset: number, value: number | null) => {
    if (without.includes(parameter))
      return
    out.push({ station_id: '10384', resolution: 'hourly', dataset: 'large', parameter, timestamp: new Date(t0 + offset * 3_600_000).toISOString().replace('Z', '+00:00'), value, quality_flags: null })
  }
  const rainOf = (h: number) => h >= 40 && h < 50 ? Math.round((0.3 + (h - 40) * 0.25) * 10) / 10 : h >= 66 && h < 70 ? 0.8 : 0
  for (let h = 0; h <= hours; h++) {
    const day = Math.sin(((h % 24) - 9) / 24 * 2 * Math.PI)
    const temperature = 8 + 6 * day + (h > 60 && h < 80 ? -4 : 0)
    add('temperature_air_2m', h, Math.round(temperature * 10) / 10)
    add('temperature_dew_point_2m', h, Math.round((temperature - 3 - 2 * Math.cos(h / 12)) * 10) / 10)
    add('wind_speed', h, Math.round((4 + 3 * Math.sin(h / 9) + (h > 40 && h < 52 ? 6 : 0)) * 10) / 10)
    add('wind_direction', h, (200 + 6 * h) % 360)
    add('wind_gust_max_last_1h', h, Math.round((8 + 5 * Math.sin(h / 9) + (h > 40 && h < 52 ? 8 : 0)) * 10) / 10)
    const cloud = Math.max(0, Math.min(100, 55 + 45 * Math.sin(h / 14)))
    add('cloud_cover_total', h, Math.round(cloud))
    add('cloud_cover_below_2km', h, Math.round(cloud * 0.6))
    add('cloud_cover_between_2km_and_7km', h, Math.round(cloud * 0.5))
    add('cloud_cover_above_7km', h, Math.round(cloud * 0.8))
    const rain = rainOf(h)
    add('precipitation_amount_significant_weather_last_1h', h, rain)
    // the totals over the hours before the stamp: at the multiples of 6, 12 and 24 hours of the run (DWD's are at 00, 06, 12, 18 UTC; the
    // fixture starts on a day's 00)
    for (const [window, name] of [[6, 'last_6h'], [12, 'last_12h'], [24, 'last_24h']] as const) {
      if (h >= window && h % window === 0)
        add(`precipitation_amount_significant_weather_${name}`, h, Math.round(Array.from({ length: window }, (_, k) => rainOf(h - k)).reduce((sum, v) => sum + v, 0) * 10) / 10)
    }
    add('weather_significant', h, h === 44 ? 95 : rain > 0 ? 61 : cloud > 70 ? 3 : 0)
    add('pressure_air_sea_level', h, Math.round((1013 + 7 * Math.sin(h / 40)) * 10) / 10)
    if (h % 12 === 11) {
      add('temperature_air_max_2m_last_12h', h, Math.round((temperature + 2) * 10) / 10)
      add('temperature_air_min_2m_last_12h', h, Math.round((temperature - 6) * 10) / 10)
    }
  }
  return out
}

/** The units the answer would report for them, as `unitsOfAnswer` has it */
export const FORECAST_UNITS: Record<string, string> = {
  temperature_air_2m: '°C',
  temperature_dew_point_2m: '°C',
  temperature_air_max_2m_last_12h: '°C',
  temperature_air_min_2m_last_12h: '°C',
  wind_speed: 'm/s',
  wind_gust_max_last_1h: 'm/s',
  wind_direction: '°',
  cloud_cover_total: '%',
  cloud_cover_below_2km: '%',
  cloud_cover_between_2km_and_7km: '%',
  cloud_cover_above_7km: '%',
  precipitation_amount_significant_weather_last_1h: 'mm',
  precipitation_amount_significant_weather_last_6h: 'mm',
  precipitation_amount_significant_weather_last_12h: 'mm',
  precipitation_amount_significant_weather_last_24h: 'mm',
  pressure_air_sea_level: 'hPa',
}

/** The units the snow request's answer reports its three series in */
export const SNOW_UNITS: Record<string, string> = {
  snow_depth_new_last_3h: 'cm',
  snow_depth: 'cm',
  probability_snow_depth_new_gt_10cm_last_24h: '%',
}

export interface SnowOptions {
  /** the first stamp, ISO: on a 3-hourly UTC step */
  start?: string
  /** the hours the run covers: DWD's is 48 */
  hours?: number
  /** also stamp the hours between the steps, as DWD does for some stations (rolling windows) */
  offGrid?: boolean
  /** the series to leave out, by the parameter name */
  without?: string[]
}

/**
 * The snow forecast of a MOSMIX-SNOW station as `/api/values` answers it (Zugspitzplatt, `Z914`): the new snow of the 3 hours
 * before each step, the snow depth and the chance of more than 10 cm within 24 hours at the 00, 03, ..., 21 UTC steps, and,
 * with `offGrid`, a value of each at the hours between, which are no steps of the product and are left out of the panel.
 * Snow falls from hour 12 to 27 of the run.
 */
export function snowForecastValues({ start = FORECAST_START, hours = 48, offGrid = false, without = [] }: SnowOptions = {}): ForecastValue[] {
  const t0 = new Date(start).getTime()
  const out: ForecastValue[] = []
  const add = (parameter: string, h: number, value: number | null) => {
    if (without.includes(parameter))
      return
    out.push({ station_id: 'Z914', resolution: 'hourly', dataset: 'snow', parameter, timestamp: new Date(t0 + h * 3_600_000).toISOString().replace('Z', '+00:00'), value, quality_flags: null })
  }
  let depth = 120
  for (let h = 0; h <= hours; h++) {
    const step = new Date(t0 + h * 3_600_000).getUTCHours() % 3 === 0
    if (!step && !offGrid)
      continue
    const fresh = h >= 12 && h < 27 ? Math.round((1 + 3 * Math.sin((h - 12) / 15 * Math.PI)) * 10) / 10 : 0
    if (step)
      depth += fresh
    add('snow_depth_new_last_3h', h, step ? fresh : 99)
    add('snow_depth', h, step ? Math.round(depth * 10) / 10 : 999)
    add('probability_snow_depth_new_gt_10cm_last_24h', h, step ? Math.round(Math.min(100, Math.max(0, (h - 6) * 4))) : 77)
  }
  return out
}
