/**
 * A MOSMIX-like forecast for the meteogram's tests: every series the chart draws, hourly for five days and every three
 * hours after, deterministic. Rain on the second evening, a cold night, a front that turns the wind, a thunderstorm.
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
  for (let h = 0; h <= hours; h++) {
    // hourly for five days, every three hours after
    if (h > 120 && h % 3 !== 0)
      continue
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
    const rain = h >= 40 && h < 50 ? Math.round((0.3 + (h - 40) * 0.25) * 10) / 10 : h >= 66 && h < 70 ? 0.8 : 0
    add('precipitation_amount_significant_weather_last_1h', h, rain)
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
  pressure_air_sea_level: 'hPa',
}
