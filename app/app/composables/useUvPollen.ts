import type { MaybeRefOrGetter } from 'vue'
import type { Station, StationsResponse, Value, ValuesResponse } from '#shared/types/api'
import type { PollenPart, UvPlace } from '~/utils/uv-pollen'
import { shallowRef, toValue, watch } from 'vue'
import { API_FETCH, readJsonAnswer } from '~/utils/api-answer'
import { pollenRegions } from '~/utils/pollen-regions'
import { nearestUvPlace, pollenPartsOfState, pollenRegionsQuery, pollenValuesQuery, stateOfStation, stateQuery, uvPlaceQuery, uvValuesQuery } from '~/utils/uv-pollen'
import { inWarningBox } from '~/utils/warnings'

/** The UV index of the place nearest to the forecast station: the place and how far it is, and the rows of the file */
export interface UvAnswer {
  place: UvPlace
  rows: Value[]
}

/** The pollen load of the part-regions of the forecast station's state: the state, its parts and the rows of all of them */
export interface PollenAnswer {
  state: string
  parts: PollenPart[]
  rows: Value[]
}

/** The position a forecast is of, and the station that has it (a new station at the same position is a new forecast) */
export interface ForecastPoint {
  stationId: string
  latitude: number | null | undefined
  longitude: number | null | undefined
}

/**
 * The UV index and the pollen load for a forecast station (GH-4501), each its own request that the forecast does not wait for and
 * whose failure only its own part shows: the answer of the one that failed, or has nothing to say (no place within reach, no
 * region for the state, a file DWD has not written), is `null`, and the panel shows the other alone. Each request has its ticket,
 * so that the answer of a station that was left meanwhile is not applied, as the snow forecast's is not.
 *
 * Nothing is asked for a station outside Germany (`inWarningBox`, the app's rule for it): both products are DWD's and cover
 * Germany only.
 */
export function useUvPollen(point: MaybeRefOrGetter<ForecastPoint | null>) {
  const uv = shallowRef<UvAnswer | null>(null)
  const pollen = shallowRef<PollenAnswer | null>(null)
  let uvTicket = 0
  let pollenTicket = 0

  async function readValues(query: Record<string, string>): Promise<Value[] | null> {
    const res = await fetch(`/api/values?${new URLSearchParams(query)}`)
    if (!res.ok)
      return null
    const json = await readJsonAnswer<ValuesResponse>('/api/values', res)
    return json.values ?? []
  }

  async function fetchUv(here: { latitude: number, longitude: number }, ticket: number) {
    try {
      const res = await $fetch<StationsResponse>('/api/stations', { query: uvPlaceQuery(here), ...API_FETCH })
      const place = nearestUvPlace(here, res.stations ?? [])
      if (!place || ticket !== uvTicket)
        return
      const rows = await readValues(uvValuesQuery(place.station.station_id))
      if (ticket === uvTicket && rows?.length)
        uv.value = { place, rows }
    }
    catch {
      // no UV part: the rest of the panel and the forecast stand
    }
  }

  async function fetchPollen(here: { latitude: number, longitude: number }, ticket: number) {
    try {
      const nearest = await $fetch<StationsResponse>('/api/stations', { query: stateQuery(here), ...API_FETCH })
      const state = stateOfStation(here, nearest.stations ?? [])
      if (!state || ticket !== pollenTicket)
        return
      const regions = await pollenRegions(() => $fetch<{ stations: Station[] }>('/api/stations', { query: pollenRegionsQuery(), ...API_FETCH }))
      const parts = pollenPartsOfState(state, regions)
      if (!parts.length || ticket !== pollenTicket)
        return
      const rows = await readValues(pollenValuesQuery(parts.map(part => part.id)))
      if (ticket === pollenTicket && rows?.length)
        pollen.value = { state, parts, rows }
    }
    catch {
      // no pollen part
    }
  }

  watch(
    // the station and its position: a new forecast is asked for when either changes
    () => {
      const here = toValue(point)
      return here ? `${here.stationId}|${here.latitude}|${here.longitude}` : ''
    },
    () => {
      const here = toValue(point)
      // the answers of the station before are not applied, whatever they are
      const ticketOfUv = ++uvTicket
      const ticketOfPollen = ++pollenTicket
      uv.value = null
      pollen.value = null
      if (!here || here.latitude == null || here.longitude == null)
        return
      const position = { latitude: here.latitude, longitude: here.longitude }
      if (!inWarningBox(position))
        return
      void fetchUv(position, ticketOfUv)
      void fetchPollen(position, ticketOfPollen)
    },
    { immediate: true },
  )

  return { uv, pollen }
}
