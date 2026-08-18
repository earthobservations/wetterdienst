export interface ParameterSelection {
  provider: string | undefined
  network: string | undefined
  resolution: Resolution | undefined
  dataset: string | undefined
  parameters: string[]
  dateRequired?: boolean
}

export interface ParameterSelectionState {
  selection: ParameterSelection
}
