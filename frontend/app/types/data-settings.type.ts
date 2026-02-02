export interface DataSettings {
    humanize: boolean
    convertUnits: boolean
    unitTargets: Record<string, string>
    // Values-specific settings
    shape: 'long' | 'wide'
    skipEmpty: boolean
    skipThreshold: number
    skipCriteria: 'min' | 'mean' | 'max'
    dropNulls: boolean
    // Geo-specific settings
    useNearbyStationDistance: number
    useStationDistancePerParameter: Record<string, number>
    minGainOfValuePairs: number
    numAdditionalStations: number
}
