import type { SeoProvider } from '../../shared/utils/seo'

// The providers the backend has (`GET /api/providers`), for the head of each provider's page and for the sitemap
// (GH-4119). It is the list the pages of the app are made of too (`app/composables/useProviders.ts`), so a provider
// the backend gains has its page, its head and its sitemap entry with no edit here.
//
// The head and the sitemap must never fail or wait on the backend, so:
// - the answer is kept for an hour (`FRESH_MS`), and no page view costs a call. A request after that gets the list it
//   has at once and asks for the next one in the background (stale while revalidate), so only the very first request
//   of a process can wait, for at most `TIMEOUT_MS`;
// - a failed call keeps the list that is held, and is not tried again for `RETRY_MS`, so a backend that is down costs
//   one short wait per half minute and not one per request;
// - with no list at all (the backend never answered) the answer is an empty list: the head is the site's, as for any
//   path that is no page of the index, and the sitemap has the fixed pages.

/** How long a list is used without asking again */
export const FRESH_MS = 60 * 60 * 1000
/** How long after a failure the next call waits */
export const RETRY_MS = 30 * 1000
/** The longest a call to the backend may take; the first request of a process is the one that can wait for it */
export const TIMEOUT_MS = 2500

interface Held {
  providers: readonly SeoProvider[]
  /** When the list was read, or 0 if it never was */
  readAt: number
  /** When the next call may be made */
  nextTryAt: number
}

// one list for the process: the backend's answer is the same for every request
let held: Held = { providers: [], readAt: 0, nextTryAt: 0 }
let inFlight: Promise<void> | undefined

function isProvider(value: unknown): value is SeoProvider {
  if (value === null || typeof value !== 'object')
    return false
  const row = value as Record<string, unknown>
  return typeof row.provider === 'string' && typeof row.name_english === 'string'
    && typeof row.country === 'string' && Array.isArray(row.networks)
}

async function read(apiBase: string): Promise<SeoProvider[]> {
  const response = await globalThis.fetch(`${apiBase.replace(/\/+$/, '')}/providers`, {
    headers: { accept: 'application/json' },
    signal: AbortSignal.timeout(TIMEOUT_MS),
  })
  if (!response.ok)
    throw new Error(`the backend answered ${response.status}`)
  const body = await response.json() as { providers?: unknown }
  // a 200 of another kind (a page of a proxy, an answer of another API) is no list: it must not empty the one held
  if (!Array.isArray(body.providers) || body.providers.length === 0)
    throw new Error('the backend answered no list of providers')
  return body.providers.filter(isProvider).map(row => ({
    provider: row.provider,
    name_english: row.name_english,
    country: row.country,
    country_code: typeof row.country_code === 'string' ? row.country_code : null,
    networks: row.networks.filter((network): network is { kind: string } => typeof network?.kind === 'string')
      .map(network => ({ kind: network.kind })),
  }))
}

function refresh(apiBase: string, now: number): Promise<void> {
  // the next call waits whatever this one does: a success sets it again below
  held.nextTryAt = now + RETRY_MS
  inFlight = read(apiBase)
    .then((providers) => {
      held = { providers, readAt: now, nextTryAt: now + FRESH_MS }
    })
    .catch((error: unknown) => {
      console.warn(`The list of providers for the head and the sitemap could not be read (${error instanceof Error ? error.message : String(error)})); the list held, if there is one, is used.`)
    })
    .finally(() => {
      inFlight = undefined
    })
  return inFlight
}

/**
 * The providers of the backend, as the head and the sitemap use them.
 *
 * @param apiBase The backend's `/api` URL (`useApiBase()`)
 * @param now The time, for the tests
 * @returns The providers; the last list that was read if the backend cannot be reached, and none if it never was.
 * Never rejects.
 */
export async function loadProviders(apiBase: string, now: number = Date.now()): Promise<readonly SeoProvider[]> {
  if (inFlight)
    return held.readAt === 0 ? inFlight.then(() => held.providers) : held.providers
  if (now >= held.nextTryAt) {
    const call = refresh(apiBase, now)
    // the first list is waited for; a stale one is served while the next is read
    if (held.readAt === 0)
      await call
  }
  return held.providers
}

/** Forgets the list, for the tests. */
export function resetProviders(): void {
  held = { providers: [], readAt: 0, nextTryAt: 0 }
  inFlight = undefined
}
