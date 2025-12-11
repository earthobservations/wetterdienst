export interface Value {
  station_id: string
  resolution: string
  dataset: string
  parameter: string
  date: string
  value: number | null
  quality: number | null
  taken_station_id?: string
  taken_station_ids?: string
}
