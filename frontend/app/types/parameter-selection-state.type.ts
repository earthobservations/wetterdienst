// Resolution values from backend wetterdienst/metadata/resolution.py
export type Resolution
  = '1_minute'
    | '5_minutes'
    | '10_minutes'
    | '15_minutes'
    | 'hourly'
    | '6_hour'
    | 'subdaily'
    | 'daily'
    | 'monthly'
    | 'annual'
    | 'undefined'
    | 'dynamic'

export interface ParameterSelection {
  provider: string | undefined
  network: string | undefined
  resolution: Resolution | undefined
  dataset: string | undefined
  parameters: string[]
}

export interface ParameterSelectionState {
  selection: ParameterSelection
}
