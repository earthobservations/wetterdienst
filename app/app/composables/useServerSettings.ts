import type { ServerSettings } from '#shared/types/api'
import { RETRY_TRANSIENT } from '~/utils/fetch-retry'

/**
 * The backend's `GET /api/settings`: what a request leaves to the server's `WD_TS_*` variables
 * (GH-2359). Asked once per app load, by whatever needs it first, and shared from then on.
 *
 * `null` where there is no answer to start from: a backend without the endpoint (404), one that
 * failed, or one whose answer is no object. A caller then keeps its own defaults. A failure is not
 * kept, so the next caller asks again: a backend that was still starting answers it.
 */
export function useServerSettings(): Promise<ServerSettings | null> {
  const answer = useState<Promise<ServerSettings | null> | undefined>('server-settings', () => undefined)
  answer.value ??= $fetch<unknown>('/api/settings', { ...RETRY_TRANSIENT })
    .then(settings => settings !== null && typeof settings === 'object' ? settings as ServerSettings : null)
    .catch(() => {
      answer.value = undefined
      return null
    })
  return answer.value
}
