import type { ProvidersResponse } from '#shared/types/api'

/**
 * What the backend says each provider is, from `GET /api/providers`. The list and the detail page share
 * the one request, by its key: the answer is static and a few tens of kilobytes, so the second page asks
 * for nothing.
 *
 * `with_datasets: true`: the backend answers the short form without it, and the detail page lists each
 * network's resolutions and datasets (GH-3536). A backend that predates the parameter refuses it with a
 * 422 (it forbids query parameters it does not know), so that answer is asked for again without it: the
 * networks then come without `resolutions`, which the pages read as "not listed".
 *
 * Not awaited by the caller, as the other pages do not: a top-level `await` in a page suspends the route
 * behind the request, and with `ssr: false` its loading state could never be seen.
 */
export function useProviders() {
  return useAsyncData<ProvidersResponse>('providers', async () => {
    try {
      return await $fetch<ProvidersResponse>('/api/providers', { query: { with_datasets: true } })
    }
    catch (error) {
      if ((error as { statusCode?: number }).statusCode !== 422)
        throw error
      return await $fetch<ProvidersResponse>('/api/providers')
    }
  })
}
