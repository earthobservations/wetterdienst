import type { ProvidersResponse } from '#shared/types/api'

/**
 * What the backend says each provider is, from `GET /api/providers`. The list and the detail page share
 * the one request, by its key: the answer is static and a few tens of kilobytes, so the second page asks
 * for nothing.
 *
 * `datasets: true`: the answer is the short form without it, and the detail page lists each network's resolutions
 * and datasets (GH-3536).
 *
 * Not awaited by the caller, as the other pages do not: a top-level `await` in a page suspends the route
 * behind the request, and with `ssr: false` its loading state could never be seen.
 */
export function useProviders() {
  return useFetch<ProvidersResponse>('/api/providers', { key: 'providers', query: { datasets: true } })
}
