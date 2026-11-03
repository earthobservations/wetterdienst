import type { Value } from '#shared/types/api'

/**
 * A synthetic, deterministic forecast in the long shape of `/api/values` (the series the meteogram
 * draws, under their canonical names), for the prototype page when no backend is at hand, for the
 * tests and for the render-time measurement. The numbers are no readings: a diurnal temperature, a
 * front every few days with rain, a veering wind, a drifting pressure.
 * @param startMs The first stamp, a whole hour
 * @param hours How many hourly stamps (240 is the ten days of a MOSMIX run)
 */
export function demoForecast(startMs: number, hours = 240, stationId = 'DEMO'): Value[] {
  const day = (h: number) => h / 24
  const wave = (h: number, period: number, phase = 0) => Math.sin(((h - phase) / period) * 2 * Math.PI)
  // a rain event every ~2.7 days, 5 to 9 hours long
  const front = (h: number) => {
    const cycle = h % 65
    return cycle >= 20 && cycle < 20 + 5 + (Math.floor(h / 65) * 2) % 5 ? 1 : 0
  }
  const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
  const round = (v: number, digits = 2) => Math.round(v * 10 ** digits) / 10 ** digits

  const curves: Record<string, (h: number) => number> = {
    temperature_air_2m: h => 6 + 4 * wave(h, 24, 9) + 2.5 * wave(day(h), 4.5) - 3 * front(h),
    temperature_dew_point_2m: h => 2.5 + 2 * wave(h, 24, 9) + 2 * wave(day(h), 4.5),
    precipitation_amount_significant_weather_last_1h: h => front(h) ? round(0.2 + 1.8 * Math.abs(wave(h, 5))) : 0,
    wind_speed: h => clamp(5 + 3 * wave(h, 31) + 4 * front(h), 0.4, 20),
    wind_direction: h => (((200 + h * 2.4 + 30 * wave(h, 13)) % 360) + 360) % 360,
    wind_gust_max_last_1h: h => clamp(9 + 4 * wave(h, 31) + 6 * front(h), 1, 30),
    cloud_cover_total: h => clamp(0.45 + 0.35 * wave(h, 19) + 0.4 * front(h), 0, 1),
    cloud_cover_below_2km: h => clamp(0.3 + 0.3 * wave(h, 17) + 0.5 * front(h), 0, 1),
    cloud_cover_between_2km_and_7km: h => clamp(0.3 + 0.3 * wave(h, 23) + 0.3 * front(h), 0, 1),
    cloud_cover_above_7km: h => clamp(0.2 + 0.25 * wave(h, 29), 0, 1),
    pressure_air_sea_level: h => 1013 + 7 * wave(h, 90) - 4 * front(h),
    weather_significant: h => front(h) ? 61 : (wave(h, 19) > 0.4 ? 3 : (wave(h, 19) > -0.3 ? 2 : 0)),
  }

  const values: Value[] = []
  for (const [parameter, curve] of Object.entries(curves)) {
    for (let h = 0; h < hours; h++) {
      values.push({
        station_id: stationId,
        resolution: 'hourly',
        dataset: 'large',
        parameter,
        timestamp: new Date(startMs + h * 3_600_000).toISOString().replace('.000Z', '+00:00'),
        value: round(curve(h), parameter === 'weather_significant' ? 0 : 2),
        quality_flags: null,
      })
    }
  }
  // MOSMIX's maximum and minimum, stamped every 12 hours at 06:00 and 18:00 UTC, over the 12 hours before
  for (let h = 0; h < hours; h++) {
    const stamp = startMs + h * 3_600_000
    const hourUtc = new Date(stamp).getUTCHours()
    if (hourUtc !== 6 && hourUtc !== 18)
      continue
    const window = Array.from({ length: 12 }, (_, i) => curves.temperature_air_2m!(Math.max(0, h - i)))
    for (const [parameter, pick] of [['temperature_air_max_2m_last_12h', Math.max], ['temperature_air_min_2m_last_12h', Math.min]] as const) {
      values.push({
        station_id: stationId,
        resolution: 'hourly',
        dataset: 'large',
        parameter,
        timestamp: new Date(stamp).toISOString().replace('.000Z', '+00:00'),
        value: round(pick(...window)),
        quality_flags: null,
      })
    }
  }
  return values
}
