import type { LocationFailure } from '~/utils/geolocation'
import type { Point } from '~/utils/map-tool'
import {
  failureOfCode,
  forgetRememberedPosition,
  LOCATE_TIMEOUT_MS,
  POSITION_OPTIONS,
  readRememberedPosition,
  roundPosition,
  writeRememberedPosition,
} from '~/utils/geolocation'

/** The latest press that asked the browser: an answer of an earlier one is not the reader's latest and is dropped (all instances share it) */
let latestPress = 0

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
 *   "Remember" can be ticked only with a position in hand, and forgetting takes the position too, so that the state
 *   is one of three: no position, a position for this visit, a position kept in the browser (GH-4010).
 * - A refusal, no support, no fix and a timeout are failures to tell, not errors: nothing else is affected.
 */
export function useMyLocation() {
  const { dropPositionPlace } = usePlace()
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
   * permission is known to be refused. The wait ends in the failure `timeout` after `LOCATE_TIMEOUT_MS` whatever the
   * browser does (a permission prompt that is ignored never ends), and a press while one is waiting takes its place: that
   * one is let go, its answer is dropped, and the browser is asked again.
   */
  async function locate(): Promise<Point | null> {
    failure.value = null
    if (position.value && remember.value)
      return position.value
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      failure.value = 'unsupported'
      return null
    }
    const mine = ++latestPress
    busy.value = true
    let clock: ReturnType<typeof setTimeout> | undefined
    try {
      const timedOut = new Promise<never>((_resolve, reject) => {
        clock = setTimeout(reject, LOCATE_TIMEOUT_MS, { code: 3 })
      })
      const asked = (async () => {
        if (await permissionState() === 'denied')
          throw Object.assign(new Error('permission denied'), { code: 1 })
        return currentPosition()
      })()
      const fix = roundPosition(await Promise.race([asked, timedOut]))
      if (mine !== latestPress)
        return null
      position.value = fix
      if (remember.value)
        writeRememberedPosition(fix)
      return fix
    }
    catch (error) {
      if (mine !== latestPress)
        return null
      const code = (error as { code?: unknown } | null)?.code
      failure.value = failureOfCode(typeof code === 'number' ? code : 2)
      return null
    }
    finally {
      clearTimeout(clock)
      if (mine === latestPress)
        busy.value = false
    }
  }

  /**
   * Ticks or unticks "remember": ticked, the position in hand is kept in the browser; unticked, what was kept is deleted.
   * It cannot be ticked with no position in hand (GH-4010): there would be nothing to keep, and the box would say that
   * something is kept when nothing is. The component shows the box only while a position is in hand.
   */
  function setRemember(on: boolean) {
    if (on && !position.value)
      return
    remember.value = on
    if (!on) {
      forgetRememberedPosition()
      // what was kept for the position goes with it; the place stays for the visit
      dropPositionPlace(false)
    }
    else if (position.value) {
      writeRememberedPosition(position.value)
    }
  }

  /** The position is forgotten: in memory and in the browser */
  function forget() {
    position.value = null
    remember.value = false
    failure.value = null
    forgetRememberedPosition()
    dropPositionPlace(true)
  }

  return { position, failure, busy, remember, remembered, locate, setRemember, forget }
}
