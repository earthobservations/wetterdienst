export interface ParameterSelection {
  provider: string | undefined
  network: string | undefined
  resolution: Resolution | undefined
  dataset: string | undefined
  parameters: string[]
  dateRequired?: boolean
  /** what the network serves, from the coverage: a forecast's readings lie ahead of today */
  kind?: NetworkKind
}

export interface ParameterSelectionState {
  selection: ParameterSelection
}
