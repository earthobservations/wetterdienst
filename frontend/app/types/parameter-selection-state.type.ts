import type { Resolution } from '#types/api.types'

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
