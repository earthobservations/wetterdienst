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
   * Metres above sea level. The backend brings each station's readings to this height before
   * using them, for the quantities that fall with it -- air temperature, dew point.
   */
  elevation?: number
  station?: Station
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
