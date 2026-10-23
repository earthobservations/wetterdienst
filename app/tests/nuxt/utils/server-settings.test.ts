import { describe, expect, it } from 'vitest'
import { MAX_ADDITIONAL_STATIONS, MAX_STATION_DISTANCE, serverDataSettings } from '~/utils/server-settings'

function server(interpolate: Record<string, unknown>): Parameters<typeof serverDataSettings>[0] {
  return { interpolate } as unknown as Parameters<typeof serverDataSettings>[0]
}

describe('the interpolation settings of the server, within what a request may send', () => {
  it('takes the values within the bounds as they are', () => {
    const settings = serverDataSettings(server({
      interpolation_station_distance_homogeneous: MAX_STATION_DISTANCE,
      interpolation_station_distance_heterogeneous: 30,
      min_gain_of_value_pairs: 0.2,
      num_additional_stations: MAX_ADDITIONAL_STATIONS,
    }))

    expect(settings.stationDistanceHomogeneous).toBe(MAX_STATION_DISTANCE)
    expect(settings.stationDistanceHeterogeneous).toBe(30)
    expect(settings.minGainOfValuePairs).toBe(0.2)
    expect(settings.numAdditionalStations).toBe(MAX_ADDITIONAL_STATIONS)
  })

  it('leaves a radius past the bound to the server, as an infinite one, and holds the count to it', () => {
    const settings = serverDataSettings(server({
      interpolation_station_distance_homogeneous: MAX_STATION_DISTANCE + 1,
      min_gain_of_value_pairs: 0,
      num_additional_stations: 25,
    }))

    expect(settings.stationDistanceHomogeneous).toBe(Number.POSITIVE_INFINITY)
    // a gain of 0 is not one a request may send: the explorer keeps its own
    expect(settings.minGainOfValuePairs).toBeUndefined()
    expect(settings.numAdditionalStations).toBe(MAX_ADDITIONAL_STATIONS)
  })
})
