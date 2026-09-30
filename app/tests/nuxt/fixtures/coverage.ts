import type { ProviderNetworkCoverageResponse } from '#shared/types/api'

// `/api/coverage?provider=dwd&network=observation` cut down to the one resolution, dataset and
// parameter the tests pick. Every key the backend's `discover()` sends is here, and `satisfies`
// has `nuxt typecheck` hold it to the contract; the descriptions are null, as the backend sends
// where the source has none.
export const DAILY_CLIMATE_SUMMARY_COVERAGE = {
  daily: {
    description: null,
    datasets: {
      climate_summary: {
        description: null,
        parameters: [{
          name: 'temperature_air_max_200',
          name_original: 'txk',
          unit_type: 'temperature',
          unit: 'degree_celsius',
          description: null,
        }],
      },
    },
  },
} satisfies ProviderNetworkCoverageResponse
