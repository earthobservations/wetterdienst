import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { clearNuxtState } from '#app'
import { useMyLocation } from '~/composables/useMyLocation'
import { DEFAULT_PLACE, usePlace } from '~/composables/usePlace'
import { LOCATE_TIMEOUT_MS, LOCATION_STORAGE_KEY } from '~/utils/geolocation'
import { LOCATION_STATE } from '../fixtures/state'

// "Use my location" (GH-3651): the one composable that calls the browser's Geolocation and Permissions APIs. The browser
// is mocked: `navigator.geolocation` answers with a fix or an error, `navigator.permissions` with a state.

interface Fix { latitude: number, longitude: number }
interface Failure { code: number, message?: string }

function mockGeolocation(answer: Fix | Failure) {
  const getCurrentPosition = vi.fn((success: (position: unknown) => void, failure: (error: unknown) => void) => {
    if ('code' in answer)
      failure({ code: answer.code, message: answer.message ?? '' })
    else
      success({ coords: { latitude: answer.latitude, longitude: answer.longitude, accuracy: 20 } })
  })
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition } })
  return getCurrentPosition
}

function mockPermission(state: PermissionState | 'throws' | 'missing') {
  if (state === 'missing') {
    Object.defineProperty(navigator, 'permissions', { configurable: true, value: undefined })
    return vi.fn()
  }
  const query = vi.fn(async () => {
    if (state === 'throws')
      throw new TypeError('geolocation is not a valid permission name')
    return { state }
  })
  Object.defineProperty(navigator, 'permissions', { configurable: true, value: { query } })
  return query
}

const Harness = defineComponent({
  setup() {
    return useMyLocation()
  },
  render: () => h('div'),
})
const mounted: Array<{ unmount: () => void }> = []
async function mountHarness() {
  const wrapper = await mountSuspended(Harness)
  mounted.push(wrapper)
  return wrapper.vm
}

beforeEach(() => {
  clearNuxtState(LOCATION_STATE)
})
afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  delete (navigator as any).geolocation
  delete (navigator as any).permissions
  vi.unstubAllGlobals()
  clearNuxtState(LOCATION_STATE)
})

describe('asking the browser', () => {
  it('is done on `locate()` and never on setup: a page that is only opened asks nothing', async () => {
    const getCurrentPosition = mockGeolocation({ latitude: 53.55, longitude: 9.99 })
    const query = mockPermission('prompt')
    const location = await mountHarness()
    expect(getCurrentPosition).not.toHaveBeenCalled()
    expect(query).not.toHaveBeenCalled()
    expect(location.position).toBeNull()
    expect(location.failure).toBeNull()
  })

  it('gives the position rounded to two decimals, and keeps it in memory only', async () => {
    const getCurrentPosition = mockGeolocation({ latitude: 53.551234, longitude: 9.993456 })
    mockPermission('granted')
    const location = await mountHarness()

    expect(await location.locate()).toEqual({ latitude: 53.55, longitude: 9.99 })
    expect(getCurrentPosition).toHaveBeenCalledTimes(1)
    expect(location.position).toEqual({ latitude: 53.55, longitude: 9.99 })
    expect(location.failure).toBeNull()
    expect(location.busy).toBe(false)
    // nothing is written to the browser: the reader did not ask for it
    expect(localStorage.length).toBe(0)
  })

  it('asks for a coarse position, within a time that ends: no high accuracy, a timeout', async () => {
    const getCurrentPosition = mockGeolocation({ latitude: 1, longitude: 2 })
    mockPermission('prompt')
    const location = await mountHarness()
    await location.locate()
    const options = (getCurrentPosition.mock.calls[0] as unknown as unknown[])[2] as PositionOptions
    expect(options.enableHighAccuracy).toBe(false)
    expect(options.timeout).toBeGreaterThan(0)
  })

  it('goes on where the Permissions API cannot tell: it throws on the name, or is not there', async () => {
    const getCurrentPosition = mockGeolocation({ latitude: 53.55, longitude: 9.99 })
    mockPermission('throws')
    const location = await mountHarness()
    expect(await location.locate()).toEqual({ latitude: 53.55, longitude: 9.99 })

    mockPermission('missing')
    expect(await location.locate()).toEqual({ latitude: 53.55, longitude: 9.99 })
    expect(getCurrentPosition).toHaveBeenCalledTimes(2)
  })
})

describe('a refusal', () => {
  it('is the failure `denied`, with no position, and nothing else breaks', async () => {
    mockGeolocation({ code: 1, message: 'User denied Geolocation' })
    mockPermission('prompt')
    const location = await mountHarness()
    expect(await location.locate()).toBeNull()
    expect(location.failure).toBe('denied')
    expect(location.position).toBeNull()
    expect(location.busy).toBe(false)
  })

  it('that the Permissions API already reports as `denied` is not asked for again: the browser is not called', async () => {
    const getCurrentPosition = mockGeolocation({ latitude: 53.55, longitude: 9.99 })
    const query = mockPermission('denied')
    const location = await mountHarness()

    expect(await location.locate()).toBeNull()
    expect(location.failure).toBe('denied')
    expect(query).toHaveBeenCalledWith({ name: 'geolocation' })
    expect(getCurrentPosition).not.toHaveBeenCalled()
  })

  it('is asked about again at the next press, as the reader may have allowed it since', async () => {
    const getCurrentPosition = mockGeolocation({ latitude: 53.55, longitude: 9.99 })
    mockPermission('denied')
    const location = await mountHarness()
    expect(await location.locate()).toBeNull()

    mockPermission('granted')
    expect(await location.locate()).toEqual({ latitude: 53.55, longitude: 9.99 })
    expect(location.failure).toBeNull()
    expect(getCurrentPosition).toHaveBeenCalledTimes(1)
  })
})

describe('where there is no position', () => {
  it('is `unsupported` for a browser without the Geolocation API', async () => {
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: undefined })
    mockPermission('prompt')
    const location = await mountHarness()
    expect(await location.locate()).toBeNull()
    expect(location.failure).toBe('unsupported')
  })

  it('is `unavailable` where the device cannot tell', async () => {
    mockGeolocation({ code: 2 })
    mockPermission('prompt')
    const location = await mountHarness()
    expect(await location.locate()).toBeNull()
    expect(location.failure).toBe('unavailable')
  })

  it('is `timeout` where the fix takes too long', async () => {
    mockGeolocation({ code: 3 })
    mockPermission('prompt')
    const location = await mountHarness()
    expect(await location.locate()).toBeNull()
    expect(location.failure).toBe('timeout')
  })

  it('is `unavailable` for an error that is none of the browser\'s own', async () => {
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { getCurrentPosition: (_success: unknown, failure: (error: unknown) => void) => failure(new Error('odd')) },
    })
    mockPermission('prompt')
    const location = await mountHarness()
    expect(await location.locate()).toBeNull()
    expect(location.failure).toBe('unavailable')
  })

  it('clears a failure at the next press that succeeds', async () => {
    mockGeolocation({ code: 3 })
    mockPermission('prompt')
    const location = await mountHarness()
    await location.locate()
    expect(location.failure).toBe('timeout')

    mockGeolocation({ latitude: 48.137, longitude: 11.575 })
    expect(await location.locate()).toEqual({ latitude: 48.14, longitude: 11.58 })
    expect(location.failure).toBeNull()
  })
})

describe('a prompt that is ignored', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('ends in the failure `timeout` after the clock of the page, which counts the time the prompt is open', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    // the browser never answers: the prompt is open
    const getCurrentPosition = vi.fn()
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition } })
    mockPermission('prompt')
    const location = await mountHarness()

    const press = location.locate()
    await vi.advanceTimersByTimeAsync(0)
    expect(location.busy).toBe(true)
    await vi.advanceTimersByTimeAsync(LOCATE_TIMEOUT_MS - 1)
    expect(location.busy).toBe(true)
    await vi.advanceTimersByTimeAsync(1)
    expect(await press).toBeNull()
    expect(location.failure).toBe('timeout')
    expect(location.busy).toBe(false)

    // and the next press works
    mockGeolocation({ latitude: 53.55, longitude: 9.99 })
    expect(await location.locate()).toEqual({ latitude: 53.55, longitude: 9.99 })
    expect(location.failure).toBeNull()
  })

  it('is taken over by the next press: the first is let go with no answer, the second asks again and gives its own', async () => {
    mockPermission('granted')
    const successes: Array<(position: unknown) => void> = []
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { getCurrentPosition: vi.fn((success: (position: unknown) => void) => void successes.push(success)) },
    })
    const location = await mountHarness()

    const first = location.locate()
    await vi.waitFor(() => expect(successes).toHaveLength(1))
    const second = location.locate()
    await vi.waitFor(() => expect(successes).toHaveLength(2))
    expect(location.busy).toBe(true)

    successes[1]!({ coords: { latitude: 48.137, longitude: 11.575 } })
    expect(await second).toEqual({ latitude: 48.14, longitude: 11.58 })
    // the answer of the first that comes late is not the reader's latest
    successes[0]!({ coords: { latitude: 1, longitude: 2 } })
    expect(await first).toBeNull()
    expect(location.position).toEqual({ latitude: 48.14, longitude: 11.58 })
    expect(location.busy).toBe(false)
    expect(location.failure).toBeNull()
  })
})

describe('what was kept for the position', () => {
  const placeFromPosition = { id: '01975', name: 'Hamburg-Fuhlsbüttel', latitude: 53.63, longitude: 10, region: 'Hamburg', fromPosition: true }

  it('goes when the reader forgets it: the place derived from it, in the browser and in the page', async () => {
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify({ latitude: 53.6, longitude: 10.05 }))
    localStorage.setItem('wd-place', JSON.stringify(placeFromPosition))
    const wrapper = await mountSuspended(Harness)
    mounted.push(wrapper)
    usePlace().place.value = placeFromPosition
    wrapper.vm.forget()
    expect(localStorage.getItem('wd-place')).toBeNull()
    expect(localStorage.getItem(LOCATION_STORAGE_KEY)).toBeNull()
    expect(usePlace().place.value).toEqual(DEFAULT_PLACE)
  })

  it('leaves a place the reader chose themselves', async () => {
    const chosen = { id: '00183', name: 'Arkona', latitude: 54.68, longitude: 13.43, region: 'Mecklenburg-Vorpommern' }
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify({ latitude: 53.6, longitude: 10.05 }))
    localStorage.setItem('wd-place', JSON.stringify(chosen))
    const wrapper = await mountSuspended(Harness)
    mounted.push(wrapper)
    usePlace().place.value = chosen
    wrapper.vm.forget()
    expect(JSON.parse(localStorage.getItem('wd-place')!).id).toBe('00183')
    expect(usePlace().place.value).toEqual(chosen)
  })

  it('gives the page back the place the reader chose, where the derived one was kept for the visit only', async () => {
    const chosen = { id: '00183', name: 'Arkona', latitude: 54.68, longitude: 13.43, region: 'Mecklenburg-Vorpommern' }
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify({ latitude: 53.6, longitude: 10.05 }))
    localStorage.setItem('wd-place', JSON.stringify(chosen))
    const wrapper = await mountSuspended(Harness)
    mounted.push(wrapper)
    usePlace().place.value = placeFromPosition
    wrapper.vm.forget()
    expect(JSON.parse(localStorage.getItem('wd-place')!).id).toBe('00183')
    expect(usePlace().place.value).toEqual(chosen)
  })
})

describe('"remember"', () => {
  it('is off at first, and a position is then kept in memory only', async () => {
    mockGeolocation({ latitude: 53.55, longitude: 9.99 })
    mockPermission('granted')
    const location = await mountHarness()
    expect(location.remember).toBe(false)
    await location.locate()
    expect(localStorage.getItem(LOCATION_STORAGE_KEY)).toBeNull()
  })

  it('cannot be ticked with no position in hand: nothing would be kept, and the state would say that something is (GH-4010)', async () => {
    mockGeolocation({ latitude: 53.551234, longitude: 9.993456 })
    mockPermission('granted')
    const location = await mountHarness()
    location.rememberPosition()
    expect(location.remember).toBe(false)
    expect(location.remembered).toBe(false)
    await location.locate()
    expect(localStorage.getItem(LOCATION_STORAGE_KEY)).toBeNull()
    expect(location.remembered).toBe(false)
  })

  it('stores the position again after a forget, when it is pressed for and ticked again (GH-4010)', async () => {
    mockGeolocation({ latitude: 53.551234, longitude: 9.993456 })
    mockPermission('granted')
    const location = await mountHarness()
    await location.locate()
    location.rememberPosition()
    expect(location.remembered).toBe(true)
    location.forget()
    expect(location.remembered).toBe(false)
    expect(localStorage.getItem(LOCATION_STORAGE_KEY)).toBeNull()

    // ticked with nothing in hand, it stays unticked and stores nothing
    location.rememberPosition()
    expect(location.remember).toBe(false)
    expect(localStorage.getItem(LOCATION_STORAGE_KEY)).toBeNull()

    await location.locate()
    location.rememberPosition()
    expect(JSON.parse(localStorage.getItem(LOCATION_STORAGE_KEY)!)).toEqual({ latitude: 53.55, longitude: 9.99 })
    expect(location.remembered).toBe(true)
  })

  it('keeps the position in hand when it is ticked after the press', async () => {
    mockGeolocation({ latitude: 53.55, longitude: 9.99 })
    mockPermission('granted')
    const location = await mountHarness()
    await location.locate()
    expect(localStorage.length).toBe(0)
    location.rememberPosition()
    expect(JSON.parse(localStorage.getItem(LOCATION_STORAGE_KEY)!)).toEqual({ latitude: 53.55, longitude: 9.99 })
  })

  it('is read back on a later visit without asking the browser for a position, and a press then uses it', async () => {
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify({ latitude: 52.52, longitude: 13.4 }))
    const getCurrentPosition = mockGeolocation({ latitude: 1, longitude: 2 })
    const query = mockPermission('granted')
    const location = await mountHarness()

    expect(location.remember).toBe(true)
    expect(location.position).toEqual({ latitude: 52.52, longitude: 13.4 })
    expect(await location.locate()).toEqual({ latitude: 52.52, longitude: 13.4 })
    expect(getCurrentPosition).not.toHaveBeenCalled()
    // the permission is looked at (GH-4014), the position is not asked for again
    expect(query).toHaveBeenCalledTimes(1)
  })

  it('is forgotten with the position: memory and browser', async () => {
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify({ latitude: 52.52, longitude: 13.4 }))
    const location = await mountHarness()
    location.forget()
    expect(location.position).toBeNull()
    expect(location.remember).toBe(false)
    expect(localStorage.getItem(LOCATION_STORAGE_KEY)).toBeNull()
  })

  it('is no failure where the browser refuses its storage: the position is for the visit', async () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new DOMException('blocked', 'SecurityError')
      },
      setItem: () => {
        throw new DOMException('full', 'QuotaExceededError')
      },
      removeItem: () => {},
    })
    mockGeolocation({ latitude: 53.55, longitude: 9.99 })
    mockPermission('granted')
    const location = await mountHarness()
    expect(await location.locate()).toEqual({ latitude: 53.55, longitude: 9.99 })
    location.rememberPosition()
    expect(location.position).toEqual({ latitude: 53.55, longitude: 9.99 })
  })

  // GH-4014: a write that the browser refuses is not "stored"
  describe('where the browser refuses the write', () => {
    function refuseWrites() {
      vi.stubGlobal('localStorage', {
        getItem: () => null,
        setItem: () => {
          throw new DOMException('full', 'QuotaExceededError')
        },
        removeItem: () => {},
      })
      return () => vi.unstubAllGlobals()
    }

    it('stays off, and says so with `notKept`, when it is ticked', async () => {
      mockGeolocation({ latitude: 53.55, longitude: 9.99 })
      mockPermission('granted')
      const location = await mountHarness()
      await location.locate()
      const allow = refuseWrites()

      location.rememberPosition()
      expect(location.remember).toBe(false)
      expect(location.remembered).toBe(false)
      expect(location.notKept).toBe(true)
      // the position is still in hand, for this visit
      expect(location.position).toEqual({ latitude: 53.55, longitude: 9.99 })

      // ticked again where the browser allows it: stored, and no longer told
      allow()
      location.rememberPosition()
      expect(location.remember).toBe(true)
      expect(location.remembered).toBe(true)
      expect(location.notKept).toBe(false)
      expect(JSON.parse(localStorage.getItem(LOCATION_STORAGE_KEY)!)).toEqual({ latitude: 53.55, longitude: 9.99 })
    })

    it('does not keep the old position as the stored one when a later press, with "remember" ticked meanwhile, cannot write the new one', async () => {
      mockPermission('granted')
      const answers: Array<(position: unknown) => void> = []
      Object.defineProperty(navigator, 'geolocation', {
        configurable: true,
        value: { getCurrentPosition: vi.fn((success: (position: unknown) => void) => void answers.push(success)) },
      })
      const location = await mountHarness()
      const first = location.locate()
      await vi.waitFor(() => expect(answers).toHaveLength(1))
      answers[0]!({ coords: { latitude: 53.55, longitude: 9.99 } })
      await first

      // the second press waits; the box is ticked (the write works), then the browser refuses the write of the late fix
      const second = location.locate()
      await vi.waitFor(() => expect(answers).toHaveLength(2))
      location.rememberPosition()
      expect(location.remembered).toBe(true)
      expect(JSON.parse(localStorage.getItem(LOCATION_STORAGE_KEY)!)).toEqual({ latitude: 53.55, longitude: 9.99 })
      const real = globalThis.localStorage
      vi.stubGlobal('localStorage', {
        getItem: (key: string) => real.getItem(key),
        setItem: () => {
          throw new DOMException('full', 'QuotaExceededError')
        },
        removeItem: (key: string) => real.removeItem(key),
      })
      answers[1]!({ coords: { latitude: 48.137, longitude: 11.575 } })
      await second

      expect(location.position).toEqual({ latitude: 48.14, longitude: 11.58 })
      expect(location.remember).toBe(false)
      expect(location.remembered).toBe(false)
      expect(location.notKept).toBe(true)
      // the old position is not left behind as if it were the one in hand
      expect(real.getItem(LOCATION_STORAGE_KEY)).toBeNull()
      vi.unstubAllGlobals()
    })

    it('counts each refusal, so that the alert can be announced again', async () => {
      mockGeolocation({ latitude: 53.55, longitude: 9.99 })
      mockPermission('granted')
      const location = await mountHarness()
      await location.locate()
      const allow = refuseWrites()
      location.rememberPosition()
      location.rememberPosition()
      expect(location.notKeptCount).toBe(2)
      allow()
    })

    it('is cleared by the next press and by a forget', async () => {
      mockGeolocation({ latitude: 53.55, longitude: 9.99 })
      mockPermission('granted')
      const location = await mountHarness()
      await location.locate()
      const allow = refuseWrites()
      location.rememberPosition()
      expect(location.notKept).toBe(true)
      await location.locate()
      expect(location.notKept).toBe(false)
      location.rememberPosition()
      expect(location.notKept).toBe(true)
      location.forget()
      expect(location.notKept).toBe(false)
      allow()
    })
  })
})

// GH-4014: "Forget" lets go of a press that still waits for the browser
describe('"forget" during a press', () => {
  it('drops the position that the browser gives late, and is no longer busy', async () => {
    mockPermission('granted')
    const answers: Array<(position: unknown) => void> = []
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { getCurrentPosition: vi.fn((success: (position: unknown) => void) => void answers.push(success)) },
    })
    const location = await mountHarness()

    const press = location.locate()
    await vi.waitFor(() => expect(answers).toHaveLength(1))
    expect(location.busy).toBe(true)
    location.forget()
    expect(location.busy).toBe(false)

    answers[0]!({ coords: { latitude: 48.137, longitude: 11.575 } })
    expect(await press).toBeNull()
    expect(location.position).toBeNull()
    expect(location.failure).toBeNull()
    expect(location.busy).toBe(false)
  })

  it('drops the failure that the browser gives late too', async () => {
    mockPermission('granted')
    const failures: Array<(error: unknown) => void> = []
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { getCurrentPosition: vi.fn((_ok: unknown, failure: (error: unknown) => void) => void failures.push(failure)) },
    })
    const location = await mountHarness()

    const press = location.locate()
    await vi.waitFor(() => expect(failures).toHaveLength(1))
    location.forget()
    failures[0]!({ code: 1 })
    expect(await press).toBeNull()
    expect(location.failure).toBeNull()
  })
})

const STORED = { latitude: 52.52, longitude: 13.4 }
const STORED_PLACE = { id: '00433', name: 'Berlin-Tempelhof', latitude: 52.47, longitude: 13.4, region: 'Berlin', fromPosition: true }

/** What another tab does to the storage: the entry is changed, and the event that the browser sends to this tab follows */
function otherTab(key: string, value: string | null) {
  if (value === null)
    localStorage.removeItem(key)
  else
    localStorage.setItem(key, value)
  window.dispatchEvent(new StorageEvent('storage', { key, newValue: value, storageArea: localStorage }))
}

// GH-4014: a stored position is not used once the browser's permission is withdrawn
describe('a stored position and the permission of the browser', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify(STORED))
    localStorage.setItem('wd-place', JSON.stringify(STORED_PLACE))
  })
  afterEach(() => localStorage.clear())

  it('is deleted with its station when the permission is `denied`: nothing is returned, the browser is not asked, the reader is told', async () => {
    const getCurrentPosition = mockGeolocation({ latitude: 1, longitude: 2 })
    mockPermission('denied')
    const location = await mountHarness()
    expect(location.remember).toBe(true)

    expect(await location.locate()).toBeNull()
    expect(getCurrentPosition).not.toHaveBeenCalled()
    expect(location.position).toBeNull()
    expect(location.remember).toBe(false)
    expect(location.withdrawn).toBe(true)
    expect(location.failure).toBeNull()
    expect(localStorage.getItem(LOCATION_STORAGE_KEY)).toBeNull()
    expect(localStorage.getItem('wd-place')).toBeNull()
  })

  it('takes the place that the position made with it', async () => {
    mockGeolocation({ latitude: 1, longitude: 2 })
    mockPermission('denied')
    const { place } = usePlace()
    place.value = STORED_PLACE
    const location = await mountHarness()
    await location.locate()
    expect(place.value).toEqual(DEFAULT_PLACE)
  })

  it('takes the telling back at the next press', async () => {
    mockGeolocation({ latitude: 48.137, longitude: 11.575 })
    const query = mockPermission('denied')
    const location = await mountHarness()
    await location.locate()
    expect(location.withdrawn).toBe(true)
    query.mockResolvedValue({ state: 'granted' } as never)
    await location.locate()
    expect(location.withdrawn).toBe(false)
  })

  it.each(['granted', 'prompt'] as const)('is used when the permission is `%s`', async (state) => {
    const getCurrentPosition = mockGeolocation({ latitude: 1, longitude: 2 })
    mockPermission(state)
    const location = await mountHarness()
    expect(await location.locate()).toEqual(STORED)
    expect(getCurrentPosition).not.toHaveBeenCalled()
    expect(location.withdrawn).toBe(false)
    expect(localStorage.getItem(LOCATION_STORAGE_KEY)).not.toBeNull()
    expect(localStorage.getItem('wd-place')).not.toBeNull()
  })

  it.each(['missing', 'throws'] as const)('is used where the Permissions API is %s', async (how) => {
    const getCurrentPosition = mockGeolocation({ latitude: 1, longitude: 2 })
    mockPermission(how)
    const location = await mountHarness()
    expect(await location.locate()).toEqual(STORED)
    expect(getCurrentPosition).not.toHaveBeenCalled()
    expect(location.withdrawn).toBe(false)
    expect(location.position).toEqual(STORED)
    expect(localStorage.getItem(LOCATION_STORAGE_KEY)).not.toBeNull()
    expect(localStorage.getItem('wd-place')).not.toBeNull()
  })

  it('is not told of by a press that a forget overtook while the permission was looked at', async () => {
    mockGeolocation({ latitude: 1, longitude: 2 })
    mockPermission('denied')
    const location = await mountHarness()
    const press = location.locate()
    location.forget()
    expect(await press).toBeNull()
    expect(location.position).toBeNull()
    // the reader forgot it: the press that was overtaken does not tell about a withdrawn permission
    expect(location.withdrawn).toBe(false)
  })
})

// GH-4014: what another tab does to the storage
describe('another tab', () => {
  beforeEach(() => {
    localStorage.clear()
  })
  afterEach(() => localStorage.clear())

  it('forgets the position there: this tab forgets it too, with the place it made', async () => {
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify(STORED))
    const { place } = usePlace()
    place.value = STORED_PLACE
    const location = await mountHarness()
    expect(location.remembered).toBe(true)

    otherTab('wd-place', null)
    otherTab(LOCATION_STORAGE_KEY, null)
    expect(location.position).toBeNull()
    expect(location.remember).toBe(false)
    expect(location.remembered).toBe(false)
    expect(place.value).toEqual(DEFAULT_PLACE)
  })

  it('does not take the position of this tab for the visit away when the stored one is forgotten', async () => {
    mockGeolocation({ latitude: 53.55, longitude: 9.99 })
    mockPermission('granted')
    const location = await mountHarness()
    await location.locate()
    expect(location.remember).toBe(false)

    otherTab(LOCATION_STORAGE_KEY, null)
    expect(location.position).toEqual({ latitude: 53.55, longitude: 9.99 })
  })

  it('stores a position there: this tab shows it as stored, unless it holds one of its own for the visit', async () => {
    const location = await mountHarness()
    expect(location.position).toBeNull()
    otherTab(LOCATION_STORAGE_KEY, JSON.stringify(STORED))
    expect(location.position).toEqual(STORED)
    expect(location.remembered).toBe(true)

    clearNuxtState(LOCATION_STATE)
    localStorage.clear()
    mockGeolocation({ latitude: 53.55, longitude: 9.99 })
    mockPermission('granted')
    const second = await mountHarness()
    await second.locate()
    otherTab(LOCATION_STORAGE_KEY, JSON.stringify(STORED))
    expect(second.position).toEqual({ latitude: 53.55, longitude: 9.99 })
    expect(second.remember).toBe(false)
  })

  it('chooses another place there: the place that the stored position made here gives way to it, and the position stays', async () => {
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify(STORED))
    const { place } = usePlace()
    place.value = STORED_PLACE
    const location = await mountHarness()
    const chosen = { id: '00183', name: 'Alfhausen', latitude: 52.4, longitude: 7.9, region: 'Niedersachsen', fromPosition: false }

    otherTab('wd-place', JSON.stringify(chosen))
    expect(place.value).toMatchObject({ id: '00183', name: 'Alfhausen' })
    expect(location.position).toEqual(STORED)
  })

  it('leaves other entries alone', async () => {
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify(STORED))
    const { place } = usePlace()
    place.value = STORED_PLACE
    const location = await mountHarness()
    // the entries differ from this tab's, but no event says so: only the event of another key comes
    localStorage.removeItem(LOCATION_STORAGE_KEY)
    localStorage.setItem('wd-place', JSON.stringify({ ...STORED_PLACE, fromPosition: false }))
    otherTab('wd_lang', 'de')
    expect(location.position).toEqual(STORED)
    expect(place.value).toEqual(STORED_PLACE)
  })

  it('stops being listened to when the page is gone', async () => {
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify(STORED))
    const wrapper = await mountSuspended(Harness)
    const location = wrapper.vm
    wrapper.unmount()
    otherTab(LOCATION_STORAGE_KEY, null)
    expect(location.position).toEqual(STORED)
  })
})
