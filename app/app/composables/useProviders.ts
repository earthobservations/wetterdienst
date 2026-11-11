import type { ProvidersResponse } from '#shared/types/api'

/**
 * What the backend says each provider is and which networks it has, from `GET /api/providers`. The pages, the
 * Explorer's selects and the command palette share the one request, by its key: the answer is static and about
 * 20 kilobytes, so the next one asks for nothing. What a network offers (its resolutions, datasets and
 * parameters) is not in it: that is `GET /api/coverage` of the network, asked for where one is chosen.
 *
 * Not awaited by the caller, as the other pages do not: a top-level `await` in a page suspends the route
 * behind the request, and with `ssr: false` its loading state could never be seen.
 */
export function useProviders() {
  return useFetch<ProvidersResponse>('/api/providers', { key: 'providers', ...API_ANSWER })
}
