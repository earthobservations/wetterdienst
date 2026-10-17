import type { Provider, ProvidersResponse } from '#shared/types/api'

const CC_BY = {
  spdx_id: 'CC-BY-4.0',
  name: 'Creative Commons Attribution 4.0 International',
  url: 'https://creativecommons.org/licenses/by/4.0/',
}

// `GET /api/providers`, as the backend answers it, cut down to five providers that between them show
// every case a card and a page tell apart: a licence with an SPDX identifier, a key, a provider that
// states no terms, one of several countries, and the standalone networks that have no resolutions.
// `satisfies` has `nuxt typecheck` hold the fixture to the contract. A fresh copy per call, so a test
// that changes its answer changes no other test's.
export function providers(): Provider[] {
  return [
    {
      provider: 'dwd',
      name_local: 'Deutscher Wetterdienst',
      name_english: 'German Weather Service',
      country: 'Germany',
      country_code: 'DE',
      license: CC_BY,
      attribution: 'Source: Deutscher Wetterdienst',
      networks: [
        {
          network: 'observation',
          kind: 'observation',
          url: 'https://opendata.dwd.de/climate_environment/CDC/',
          copyright: '© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)',
          auth: false,
          date_required: false,
          parameters: 12,
          resolutions: [
            { name: 'daily', datasets: [{ name: 'climate_summary', parameters: 8 }] },
            { name: 'hourly', datasets: [{ name: 'temperature_air', parameters: 4 }] },
          ],
        },
        {
          network: 'radar',
          kind: 'radar',
          url: 'https://opendata.dwd.de/weather/radar/',
          copyright: '© Deutscher Wetterdienst (DWD), radar products',
          auth: false,
          date_required: false,
          parameters: 0,
          resolutions: [],
        },
      ],
    },
    {
      provider: 'aemet',
      name_local: 'Agencia Estatal de Meteorología',
      name_english: 'State Meteorological Agency of Spain',
      country: 'Spain',
      country_code: 'ES',
      license: null,
      attribution: null,
      networks: [
        {
          network: 'observation',
          kind: 'observation',
          url: 'https://opendata.aemet.es/',
          copyright: '© AEMET',
          auth: true,
          date_required: true,
          parameters: 6,
          resolutions: [{ name: 'daily', datasets: [{ name: 'data', parameters: 6 }] }],
        },
      ],
    },
    {
      provider: 'metno',
      name_local: 'Meteorologisk institutt',
      name_english: 'Norwegian Meteorological Institute',
      country: 'Norway',
      country_code: 'NO',
      license: { spdx_id: 'CC-BY-4.0 OR NLOD-2.0', name: 'CC BY 4.0 or NLOD 2.0', url: 'https://api.met.no/doc/License' },
      attribution: 'Data from the Norwegian Meteorological Institute',
      networks: [
        {
          network: 'frost',
          kind: 'observation',
          url: 'https://frost.met.no/',
          copyright: '© MET Norway',
          auth: true,
          date_required: false,
          parameters: 5,
          resolutions: [{ name: 'hourly', datasets: [{ name: 'data', parameters: 5 }] }],
        },
      ],
    },
    {
      provider: 'mosmix',
      name_local: 'Vorhersagedienst',
      name_english: 'Forecast Service',
      country: 'Luxembourg',
      country_code: 'LU',
      license: CC_BY,
      attribution: 'Source: the service',
      networks: [
        {
          network: 'forecast',
          kind: 'forecast',
          url: 'https://example.org/forecast/',
          copyright: '© the service',
          auth: false,
          date_required: false,
          parameters: 3,
          resolutions: [{ name: 'hourly', datasets: [{ name: 'small', parameters: 3 }] }],
        },
      ],
    },
    {
      provider: 'eumetnet',
      name_local: 'EUMETNET',
      name_english: 'EUMETNET',
      country: 'Europe',
      country_code: 'ZZ',
      license: null,
      attribution: null,
      networks: [
        {
          network: 'opera',
          kind: 'radar',
          url: 'https://example.org/opera/',
          copyright: '© EUMETNET',
          auth: false,
          date_required: false,
          parameters: 0,
          resolutions: [],
        },
      ],
    },
  ]
}

export function providersResponse(): ProvidersResponse {
  const all = providers()
  return {
    metadata: {
      api_version: '1',
      schema_version: '1',
      retrieved_at: '2026-10-17T10:00:00.000000+00:00',
      counts: { providers: all.length, networks: all.reduce((sum, provider) => sum + provider.networks.length, 0) },
      warnings: [],
    },
    providers: all,
  } satisfies ProvidersResponse
}
