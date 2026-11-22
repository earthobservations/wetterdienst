import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { useNuxtApp } from '#app'
import { useWarnings } from '~/composables/useWarnings'
import { WARNINGS_REFRESH_MS, WARNINGS_STALE_AFTER_MS } from '~/utils/warnings'
import { alertsAnswer, emptyAlerts } from '../../helpers/warnings-answer'

// The refresh of DWD's weather warnings (GH-4295): the snapshot is asked for while the layer or a banner wants it and the tab is in
// front, again every 5 minutes (the backend keeps the latest snapshot that long, so asking sooner asks for the same file), and not at all
// when nothing wants it or the tab is in the background. A snapshot that fails to refresh is kept, and said to be old once it is three
// refreshes behind by the server's clock; the language of the page decides the product asked for.

const fetched = vi.fn()
let visibility: 'visible' | 'hidden' = 'visible'
const scopes: Array<ReturnType<typeof effectScope>> = []
const START = new Date('2026-11-22T12:00:00Z')

function setVisibility(state: 'visible' | 'hidden') {
  visibility = state
  document.dispatchEvent(new Event('visibilitychange'))
}

function mount(initial = true) {
  const wanted = ref(initial)
  const scope = effectScope()
  scopes.push(scope)
  const warnings = scope.run(() => useWarnings(() => wanted.value, { load: product => fetched(product) }))!
  return { wanted, warnings, scope }
}

async function settle() {
  await vi.advanceTimersByTimeAsync(0)
  await nextTick()
}

beforeEach(async () => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'], now: START })
  visibility = 'visible'
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility })
  fetched.mockReset()
  fetched.mockImplementation(async () => alertsAnswer({ now: Date.now() }))
  vi.useRealTimers()
  await useNuxtApp().$i18n.setLocale('en')
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'], now: START })
})

afterEach(() => {
  scopes.splice(0).forEach(scope => scope.stop())
  vi.useRealTimers()
  setVisibility('visible')
})

describe('the snapshot of the warnings', () => {
  it('is not asked for while nothing wants it', async () => {
    const { warnings } = mount(false)
    await vi.advanceTimersByTimeAsync(WARNINGS_REFRESH_MS * 3)
    expect(fetched).not.toHaveBeenCalled()
    expect(warnings.status.value).toBe('idle')
  })

  it('is asked for at once when it is wanted, in the product of the page, and read into warnings', async () => {
    const { warnings } = mount()
    expect(warnings.status.value).toBe('pending')
    await settle()
    expect(fetched).toHaveBeenCalledExactlyOnceWith('en')
    expect(warnings.status.value).toBe('success')
    expect(warnings.snapshot.value!.warnings).toHaveLength(6)
  })

  it('is a quiet day\'s empty list, which is a snapshot like any other', async () => {
    fetched.mockImplementation(async () => emptyAlerts(Date.now()))
    const { warnings } = mount()
    await settle()
    expect(warnings.status.value).toBe('success')
    expect(warnings.snapshot.value!.warnings).toEqual([])
  })

  it('is asked for again every 5 minutes, and not before: the backend keeps the snapshot that long', async () => {
    mount()
    await settle()
    expect(WARNINGS_REFRESH_MS).toBe(5 * 60 * 1000)
    await vi.advanceTimersByTimeAsync(WARNINGS_REFRESH_MS - 1)
    expect(fetched).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(fetched).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(WARNINGS_REFRESH_MS)
    expect(fetched).toHaveBeenCalledTimes(3)
  })

  it('takes the new snapshot in place of the old one', async () => {
    const { warnings } = mount()
    await settle()
    fetched.mockImplementation(async () => emptyAlerts(Date.now()))
    await vi.advanceTimersByTimeAsync(WARNINGS_REFRESH_MS)
    expect(warnings.snapshot.value!.warnings).toEqual([])
  })

  it('stops when nothing wants it any more, with no timer left waiting', async () => {
    const { wanted } = mount()
    await settle()
    wanted.value = false
    await nextTick()
    expect(vi.getTimerCount()).toBe(0)
    await vi.advanceTimersByTimeAsync(WARNINGS_REFRESH_MS * 4)
    expect(fetched).toHaveBeenCalledTimes(1)
  })

  it('stops while the tab is in the background, and asks at once when it is back', async () => {
    mount()
    await settle()
    setVisibility('hidden')
    await nextTick()
    expect(vi.getTimerCount()).toBe(0)
    await vi.advanceTimersByTimeAsync(WARNINGS_REFRESH_MS * 4)
    expect(fetched).toHaveBeenCalledTimes(1)
    setVisibility('visible')
    await settle()
    expect(fetched).toHaveBeenCalledTimes(2)
  })

  it('leaves no timer when its scope is stopped', async () => {
    const { scope } = mount()
    await settle()
    expect(vi.getTimerCount()).toBe(1)
    scope.stop()
    expect(vi.getTimerCount()).toBe(0)
  })
})

describe('the language of the page', () => {
  it('asks again, in the product DWD writes the language in, when the language changes', async () => {
    mount()
    await settle()
    vi.useRealTimers()
    await useNuxtApp().$i18n.setLocale('pl')
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'], now: START })
    await settle()
    expect(fetched.mock.calls.map(call => call[0])).toEqual(['en', 'mul'])
    vi.useRealTimers()
    await useNuxtApp().$i18n.setLocale('cs')
    await vi.waitFor(() => expect(fetched.mock.calls.map(call => call[0])).toEqual(['en', 'mul', 'de']))
  })

  it('does not ask for a change of the language while nothing wants the snapshot', async () => {
    mount(false)
    vi.useRealTimers()
    await useNuxtApp().$i18n.setLocale('fr')
    expect(fetched).not.toHaveBeenCalled()
  })
})

describe('a request that fails', () => {
  it('is an error where no snapshot ever came, which Retry asks again', async () => {
    fetched.mockRejectedValueOnce(new Error('offline'))
    const { warnings } = mount()
    await settle()
    expect(warnings.status.value).toBe('error')
    expect(warnings.snapshot.value).toBeNull()
    await warnings.retry()
    await settle()
    expect(warnings.status.value).toBe('success')
  })

  it('keeps the snapshot in hand and says the refresh failed, and an answer that is no list of warnings is a failure too', async () => {
    const { warnings } = mount()
    await settle()
    fetched.mockResolvedValue('<html>')
    await vi.advanceTimersByTimeAsync(WARNINGS_REFRESH_MS)
    expect(warnings.refreshFailed.value).toBe(true)
    expect(warnings.snapshot.value!.warnings).toHaveLength(6)
    expect(warnings.status.value).toBe('success')
  })

  it('is old once it is more than 15 minutes behind by the server\'s clock, and not before', async () => {
    const { warnings } = mount()
    await settle()
    expect(WARNINGS_STALE_AFTER_MS).toBe(15 * 60 * 1000)
    expect(warnings.stale.value).toBe(false)
    // the refreshes fail: the snapshot ages with the clock
    fetched.mockRejectedValue(new Error('offline'))
    await vi.advanceTimersByTimeAsync(WARNINGS_REFRESH_MS * 3)
    expect(warnings.refreshFailed.value).toBe(true)
    expect(warnings.stale.value).toBe(false)
    await vi.advanceTimersByTimeAsync(WARNINGS_REFRESH_MS)
    expect(warnings.stale.value).toBe(true)
  })

  it('judges its age by the server\'s clock, not a device clock that is wrong', async () => {
    // the device is an hour ahead of the server: an answer that came now is not old
    fetched.mockImplementation(async () => alertsAnswer({ now: Date.now() - 60 * 60 * 1000 }))
    const { warnings } = mount()
    await settle()
    expect(warnings.snapshot.value!.clockSkewMs).toBeLessThan(-59 * 60 * 1000)
    expect(warnings.stale.value).toBe(false)
  })
})
