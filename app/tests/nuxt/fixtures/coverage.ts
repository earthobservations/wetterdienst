import type { ProviderNetworkCoverageResponse } from '#shared/types/api'

// `/api/coverage?provider=dwd&network=observation`, as the backend's `discover()` answers it, cut
// down to the one resolution, dataset and parameter the tests pick. Every key it sends is here,
// and `satisfies` has `nuxt typecheck` hold the fixture to the contract. A fresh copy per call, so
// a test that changes its answer changes no other test's.
export function dailyClimateSummaryCoverage() {
  return {
    daily: {
      description: null,
      datasets: {
        climate_summary: {
          description: 'Daily station observations (temperature, pressure, precipitation, sunshine duration, etc.) for Germany.',
          parameters: [{
            name: 'temperature_air_max_2m',
            name_original: 'txk',
            unit_type: 'temperature',
            unit: 'degree_celsius',
            description: 'Daily maximum of temperature at 2 m height.',
          }],
        },
      },
    },
  } satisfies ProviderNetworkCoverageResponse
}
