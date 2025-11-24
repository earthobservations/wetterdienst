export type ParameterSelection = {
      provider: string | undefined
      network: string | undefined
      resolution: string | undefined
      dataset: string | undefined
      parameters: string[]
}
export type ParameterSelectionState = {
    selection: ParameterSelection
}
