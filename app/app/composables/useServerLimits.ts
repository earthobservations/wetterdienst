import type { Ref } from 'vue'
import type { RowLimits } from '~/utils/row-window'
import { RETRY_TRANSIENT } from '~/utils/fetch-retry'
import { DEFAULT_ROW_LIMITS } from '~/utils/row-window'

/** A limit as `GET /api/version` reports it: a whole number, 0 for none; anything else is left to the default. */
function limit(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : fallback
}

/** The limits of an answer of `GET /api/version`, the documented defaults for what it does not say. */
export function limitsOf(answer: unknown): RowLimits {
  const reported = (answer as { limits?: Partial<Record<keyof RowLimits, unknown>> } | null | undefined)?.limits
  return {
    max_rows: limit(reported?.max_rows, DEFAULT_ROW_LIMITS.max_rows),
    max_stations: limit(reported?.max_stations, DEFAULT_ROW_LIMITS.max_stations),
    max_stream_rows: limit(reported?.max_stream_rows, DEFAULT_ROW_LIMITS.max_stream_rows),
  }
}

/**
 * The limits the REST API holds a request to (`limits` of `GET /api/version`), as a ref that starts at
 * the documented defaults and takes the server's once it has answered. Asked once per app load, by
 * whatever needs it first, and shared. A server that does not report them, or fails, leaves the
 * defaults, and a failure other than the 404 is asked again by the next caller.
 */
export function useServerLimits(): Ref<RowLimits> {
  const limits = useState<RowLimits>('server-limits', () => ({ ...DEFAULT_ROW_LIMITS }))
  const asked = useState<boolean>('server-limits-asked', () => false)
  if (!asked.value) {
    asked.value = true
    $fetch<unknown>('/api/version', { ...RETRY_TRANSIENT })
      .then((answer) => {
        limits.value = limitsOf(answer)
      })
      .catch((error: { statusCode?: number }) => {
        if (error?.statusCode !== 404)
          asked.value = false
      })
  }
  return limits
}
