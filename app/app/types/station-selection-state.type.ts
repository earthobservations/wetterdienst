import type { PlaceInLink } from '~/utils/place-link'

export type StationMode = 'station' | 'interpolation' | 'summary'

export type InterpolationSource = 'manual' | 'station'

export interface StationSelection {
  stations: Station[]
}

export interface InterpolationSelection {
  source: InterpolationSource
  latitude?: number
  longitude?: number
  /**
   * Metres above sea level. The backend brings each station's readings to this elevation before
   * using them, for the quantities that fall with it -- air temperature, dew point.
   */
  elevation?: number
  station?: Station
  /**
   * The place the coordinates are the position of (GH-3791), where they were found by its name: shown with the point, and kept in the link. It goes
   * where the coordinates are typed over or the point is given by a station. A place has no height: no elevation is taken from it.
   */
  place?: PlaceInLink
}

export interface DateRange {
  startDate?: string
  endDate?: string
}

export interface StationSelectionState {
  mode: StationMode
  selection: StationSelection
  interpolation: InterpolationSelection
  dateRange: DateRange
}
