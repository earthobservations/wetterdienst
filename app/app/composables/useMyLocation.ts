import type { LocationFailure } from '~/utils/geolocation'
import type { Point } from '~/utils/map-tool'
import {
  failureOfCode,
  forgetRememberedPosition,
  POSITION_OPTIONS,
  readRememberedPosition,
  roundPosition,
  writeRememberedPosition,
} from '~/utils/geolocation'

/**
 * The reader's own position (GH-3651), and the one place that calls the browser's Geolocation and Permissions APIs.
 *
 * - The browser is asked only by `locate()`, which a button calls on a press: never on load. A permission that the
 *   Permissions API says is `denied` is not asked for again (the browser would answer without a prompt): the failure
 *   `denied` is set, and the page shows how to allow it.
 * - The position is rounded to two decimals (about 1 km) before it leaves this composable, so nothing downstream
 *   sees a more exact one.
 * - It is kept in memory, shared by every place that asks; with "remember" ticked also in localStorage
 *   (`wd-location`), where a later press of the button uses it without asking the browser, until the reader forgets it.
 * - A refusal, no support, no fix and a timeout are failures to tell, not errors: nothing else is affected.
 */
export function useMyLocation() {
  const position = useState<Point | null>('wd-location-position', () => null)
  const failure = useState<LocationFailure | null>('wd-location-failure', () => null)
  const busy = useState<boolean>('wd-location-busy', () => false)
  const remember = useState<boolean>('wd-location-remember', () => false)
  /** Whether the storage was looked at in this visit: once, when a component first asks, as a client-side read */
  const loaded = useState<boolean>('wd-location-loaded', () => false)

  if (import.meta.client && !loaded.value) {
    loaded.value = true
    const remembered = readRememberedPosition()
    if (remembered) {
      position.value = remembered
      remember.value = true
    }
  }

  /** Whether the position in hand is the one remembered in this browser */
  const remembered = computed(() => remember.value && position.value !== null)

  /** The state of the permission as the Permissions API tells it, or null where it cannot */
  async function permissionState(): Promise<PermissionState | null> {
    try {
      if (!navigator.permissions?.query)
        return null
      return (await navigator.permissions.query({ name: 'geolocation' as PermissionName })).state
    }
    catch {
      // Safari and others that know the API but not this name: the browser's own prompt does the asking
      return null
    }
  }

  function currentPosition(): Promise<Point> {
    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        fix => resolve({ latitude: fix.coords.latitude, longitude: fix.coords.longitude }),
        error => reject(error),
        POSITION_OPTIONS,
      )
    })
  }

  /**
   * The reader's position, rounded, or null with `failure` set. Asks the browser, unless a position is remembered or the
   * permission is known to be refused.
   */
  async function locate(): Promise<Point | null> {
    if (busy.value)
      return null
    failure.value = null
    if (position.value && remember.value)
      return position.value
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      failure.value = 'unsupported'
      return null
    }
    busy.value = true
    try {
      if (await permissionState() === 'denied') {
        failure.value = 'denied'
        return null
      }
      const fix = roundPosition(await currentPosition())
      position.value = fix
      if (remember.value)
        writeRememberedPosition(fix)
      return fix
    }
    catch (error) {
      const code = (error as { code?: unknown } | null)?.code
      failure.value = failureOfCode(typeof code === 'number' ? code : 2)
      return null
    }
    finally {
      busy.value = false
    }
  }

  /** Ticks or unticks "remember": ticked, the position in hand is kept in the browser; unticked, what was kept is deleted */
  function setRemember(on: boolean) {
    remember.value = on
    if (!on)
      forgetRememberedPosition()
    else if (position.value)
      writeRememberedPosition(position.value)
  }

  /** The position is forgotten: in memory and in the browser */
  function forget() {
    position.value = null
    remember.value = false
    failure.value = null
    forgetRememberedPosition()
  }

  return { position, failure, busy, remember, remembered, locate, setRemember, forget }
}
