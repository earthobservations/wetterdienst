export interface ParameterSelection {
  provider: string | undefined
  network: string | undefined
  resolution: string | undefined
  dataset: string | undefined
  parameters: string[]
}

export interface ParameterSelectionState {
  selection: ParameterSelection
}
