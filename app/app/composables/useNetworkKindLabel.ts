import type { NetworkKind } from '#shared/types/api'
import { NETWORK_KIND_KEYS } from '#shared/utils/seo'

// the catalog key of each kind is shared with the head of a provider's page (`shared/utils/seo.ts`); a kind the
// backend gains and this list lacks fails the type check here
const KEYS = NETWORK_KIND_KEYS satisfies Record<NetworkKind, string>

/** Names what a network serves -- measurements, forecasts, radar -- in the active language. */
export function useNetworkKindLabel() {
  const { t } = useI18n()

  function networkKindLabel(kind: NetworkKind): string {
    return KEYS[kind] ? t(KEYS[kind]) : kind
  }

  return { networkKindLabel }
}
