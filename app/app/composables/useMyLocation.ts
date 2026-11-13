import type { LocationFailure } from '~/utils/geolocation'
import type { Point } from '~/utils/map-tool'
import { PLACE_STORAGE_KEY } from '~/composables/usePlace'
import {
  failureOfCode,
  forgetRememberedPosition,
  LOCATE_TIMEOUT_MS,
  LOCATION_STORAGE_KEY,
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
 * - A stored position is used only while the browser's permission is not `denied` (GH-4014): a press, and the load of a
 *   page that uses the station the position made (`checking` holds that page's questions back until the answer is in),
 *   finds it withdrawn, deletes the stored position and its station, as "Forget" does, and sets `withdrawn` so that the
 *   reader is told. Where the Permissions API cannot tell, the stored position is used as before.
 * - What another tab does to the storage reaches this one (the `storage` event, and a look at the storage when a
 *   control is set up, a press uses a stored position, or the page comes back from the back/forward cache): a position
 *   forgotten there is forgotten here, one stored there is taken here, unless this tab holds a position of its own for
 *   the visit (GH-4014). A press never uses a stored position that the storage no longer holds.
 * - A refusal, no support, no fix and a timeout are failures to tell, not errors: nothing else is affected.
 */
export function useMyLocation() {
  const { place, dropPositionPlace, followStoredPlace } = usePlace()
  const position = useState<Point | null>('wd-location-position', () => null)
  const failure = useState<LocationFailure | null>('wd-location-failure', () => null)
  const busy = useState<boolean>('wd-location-busy', () => false)
  const remember = useState<boolean>('wd-location-remember', () => false)
  /** The browser refused to keep the position (blocked or full storage): it is for this visit only, and the reader is told (GH-4014) */
  const notKept = useState<boolean>('wd-location-not-kept', () => false)
  /** How many times the browser refused: the alert is keyed on it, so that a second refusal is announced again (GH-4014) */
  const notKeptCount = useState<number>('wd-location-not-kept-count', () => 0)
  /** The browser's permission was found withdrawn on a press, and the stored position deleted: the reader is told (GH-4014) */
  const withdrawn = useState<boolean>('wd-location-withdrawn', () => false)
  /** The stored position is being checked against the browser's permission at load: what is asked about its station waits (GH-4014) */
  const checking = useState<boolean>('wd-location-checking', () => false)
  /** Whether the storage was looked at in this visit: once, when a component first asks, as a client-side read */
  const loaded = useState<boolean>('wd-location-loaded', () => false)
  const firstLook = !loaded.value

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

  /** The browser did not keep the position: the reader is told, each time */
  function refused() {
    notKept.value = true
    notKeptCount.value++
  }

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
   * Looks at the browser's permission before the stored position is used (GH-4014). `denied`: the position and its
   * station are deleted as "Forget" does and `withdrawn` is set. Where the browser cannot tell, or says anything else,
   * the position is used. A later press, or a forget, takes the place of this one (`overtaken`): it holds `checking` on
   * until it has its own answer, or ends it with the forget.
   */
  async function checkStoredPermission(): Promise<'allowed' | 'withdrawn' | 'overtaken'> {
    const mine = ++latestPress
    // a press that waited for the browser is dropped by this one, and no longer clears `busy`
    busy.value = false
    const state = await permissionState()
    if (mine !== latestPress)
      return 'overtaken'
    if (state === 'denied') {
      forget()
      withdrawn.value = true
      return 'withdrawn'
    }
    checking.value = false
    return 'allowed'
  }

  /**
   * The reader's position, rounded, or null with `failure` set. Asks the browser, unless a position is remembered or the
   * permission is known to be refused. The wait ends in the failure `timeout` after `LOCATE_TIMEOUT_MS` whatever the
   * browser does (a permission prompt that is ignored never ends), and a press while one is waiting takes its place: that
   * one is let go, its answer is dropped, and the browser is asked again.
   */
  async function locate(): Promise<Point | null> {
    failure.value = null
    notKept.value = false
    withdrawn.value = false
    // a position that another tab forgot while no control here was listening is not used: this press asks the browser, as
    // one with nothing stored does
    syncLocation()
    if (position.value && remember.value) {
      const checked = await checkStoredPermission()
      return checked === 'allowed' ? position.value : null
    }
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
      // "remember" was ticked while this press waited: the new position replaces the stored one, or, where the browser
      // refuses it now, the old one is not kept either (the control would name a position that is not the one in hand)
      if (remember.value && !writeRememberedPosition(fix)) {
        forgetRememberedPosition()
        remember.value = false
        refused()
      }
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
   * Ticks "remember": the position in hand is kept in the browser. It cannot be ticked with no position in hand
   * (GH-4010): there would be nothing to keep, and the state would say that something is kept when nothing is. The
   * component shows the box only while a position is in hand. There is no unticking: the box gives way to the "Stored"
   * control once the position is stored, and `forget()` is the one way back. It is ticked only if the browser kept the
   * position: where it refuses (GH-4014), `remember` stays off, `notKept` is set, and the box stays for another try.
   */
  function rememberPosition() {
    if (!position.value)
      return
    if (!writeRememberedPosition(position.value)) {
      refused()
      return
    }
    notKept.value = false
    remember.value = true
  }

  /**
   * The position is forgotten: in memory and in the browser. What is in flight goes too (GH-4014): a press that still
   * waits for the browser is dropped, as a later press would drop it, so that its answer does not bring the position
   * back for the visit. The pages drop their lookups of the nearest station when the position goes.
   */
  function forget() {
    latestPress++
    busy.value = false
    position.value = null
    remember.value = false
    notKept.value = false
    failure.value = null
    withdrawn.value = false
    checking.value = false
    forgetRememberedPosition()
    dropPositionPlace()
  }

  /**
   * This tab follows what the browser keeps (GH-4014): a remembered position that the storage no longer holds is
   * forgotten, one that it holds in place of this tab's is taken. A position that is only for this visit is the tab's own
   * and is kept, and a position stored elsewhere is taken only where this tab has none of its own.
   */
  function syncLocation() {
    if (!import.meta.client)
      return
    const kept = readRememberedPosition()
    if (!kept) {
      if (remember.value)
        forget()
    }
    else if ((!position.value || remember.value) && (!remembered.value || kept.latitude !== position.value?.latitude || kept.longitude !== position.value?.longitude)) {
      position.value = kept
      remember.value = true
      notKept.value = false
      withdrawn.value = false
      failure.value = null
    }
  }

  /**
   * Another tab changed the storage (GH-4014): this tab follows what is kept, so that it does not show "Stored" or use a
   * position that was forgotten there (`syncLocation`), and the place that the position made follows the place kept.
   */
  function onStorage(event: StorageEvent) {
    if (event.key !== null && event.key !== LOCATION_STORAGE_KEY && event.key !== PLACE_STORAGE_KEY)
      return
    if (event.key === null || event.key === LOCATION_STORAGE_KEY)
      syncLocation()
    if (remember.value)
      followStoredPlace()
  }

  /** A page that comes back from the back/forward cache has missed the events of the time it was away */
  function onPageShow(event: PageTransitionEvent) {
    if (!event.persisted)
      return
    syncLocation()
    if (remember.value)
      followStoredPlace()
  }

  /**
   * The load of a page that uses the station that the position made (GH-4014): the permission is looked at before that
   * station is asked about, and `checking` holds the page's questions back meanwhile. A position that made no station
   * is used only by a press, which looks at the permission itself.
   */
  function checkOnLoad() {
    if (!remember.value || !position.value || !place.value.fromPosition || checking.value)
      return
    checking.value = true
    void checkStoredPermission()
  }

  if (import.meta.client) {
    // a control set up later in the visit has not seen what other tabs did meanwhile
    if (!firstLook)
      syncLocation()
    if (remember.value)
      followStoredPlace()
    checkOnLoad()
    if (getCurrentScope()) {
      window.addEventListener('storage', onStorage)
      window.addEventListener('pageshow', onPageShow)
      onScopeDispose(() => {
        window.removeEventListener('storage', onStorage)
        window.removeEventListener('pageshow', onPageShow)
      })
    }
  }

  return { position, failure, busy, remember, notKept, notKeptCount, withdrawn, checking, remembered, locate, rememberPosition, forget }
}
