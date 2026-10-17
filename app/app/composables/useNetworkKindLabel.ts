import type { NetworkKind } from '#shared/types/api'

/** The catalog key of each kind of network, reusing the names the home page gives the kinds of data */
const KEYS: Record<NetworkKind, string> = {
  observation: 'home.kindObservationsTitle',
  forecast: 'home.kindForecastsTitle',
  derived: 'providers.kindDerived',
  radar: 'home.kindRadarTitle',
  alerts: 'home.kindAlertsTitle',
}

/** Names what a network serves -- measurements, forecasts, radar -- in the active language. */
export function useNetworkKindLabel() {
  const { t } = useI18n()

  function networkKindLabel(kind: NetworkKind): string {
    return KEYS[kind] ? t(KEYS[kind]) : kind
  }

  return { networkKindLabel }
}
