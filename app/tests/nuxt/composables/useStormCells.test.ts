import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { useStormCells } from '~/composables/useStormCells'
import { REFRESH_MS } from '~/utils/storm-cells'
import { emptyScan, exampleScan, recentReference } from '../../helpers/storm-cells-answer'

// The refresh of the map's thunderstorm cells (GH-4208): the scan is asked for while the layer is shown and the tab is in
// front, again every 5 minutes (DWD writes a scan that often), and not at all when the layer is off or the tab is in the
// background. A scan that fails to refresh is kept; one that never came is an error that Retry asks again.

const fetched = vi.fn()
let visibility: 'visible' | 'hidden' = 'visible'
const scopes: Array<ReturnType<typeof effectScope>> = []

function setVisibility(state: 'visible' | 'hidden') {
  visibility = state
  document.dispatchEvent(new Event('visibilitychange'))
}

/** The composable in a scope of its own, as a page has it, with the layer's switch */
function mount(initial = true) {
  const on = ref(initial)
  const scope = effectScope()
  scopes.push(scope)
  const storm = scope.run(() => useStormCells(() => on.value, { load: () => fetched() }))!
  return { on, storm, scope }
}

/** The microtasks of an answer that is on its way, settled; the timers stay as they are */
async function settle() {
  await vi.advanceTimersByTimeAsync(0)
  await nextTick()
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'], now: new Date('2026-11-17T22:20:00Z') })
  visibility = 'visible'
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility })
  fetched.mockReset()
  fetched.mockResolvedValue(emptyScan())
})

afterEach(() => {
  scopes.splice(0).forEach(scope => scope.stop())
  vi.useRealTimers()
  setVisibility('visible')
})

describe('the scan of the thunderstorm cells', () => {
  it('is not asked for while the layer is off', async () => {
    const { storm } = mount(false)
    await vi.advanceTimersByTimeAsync(REFRESH_MS * 3)
    expect(fetched).not.toHaveBeenCalled()
    expect(storm.status.value).toBe('idle')
    expect(storm.scan.value).toBeNull()
  })

  it('is asked for at once when the layer is shown, and read into a scan', async () => {
    fetched.mockResolvedValue(exampleScan())
    const { storm } = mount()
    expect(storm.status.value).toBe('pending')
    await settle()
    expect(fetched).toHaveBeenCalledTimes(1)
    expect(storm.status.value).toBe('success')
    expect(storm.scan.value!.cells).toHaveLength(4)
  })

  it('is an empty scan, which is a scan: it says when it was true', async () => {
    const { storm } = mount()
    await settle()
    expect(storm.status.value).toBe('success')
    expect(storm.scan.value!.cells).toEqual([])
    expect(storm.scan.value!.referenceTime).toBe(recentReference())
  })

  it('is asked for again every 5 minutes, and not before', async () => {
    mount()
    await settle()
    expect(REFRESH_MS).toBe(5 * 60 * 1000)
    await vi.advanceTimersByTimeAsync(REFRESH_MS - 1)
    expect(fetched).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(fetched).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(REFRESH_MS)
    expect(fetched).toHaveBeenCalledTimes(3)
  })

  it('takes the new scan in place of the old one', async () => {
    const { storm } = mount()
    await settle()
    expect(storm.scan.value!.cells).toHaveLength(0)
    fetched.mockResolvedValue(exampleScan())
    await vi.advanceTimersByTimeAsync(REFRESH_MS)
    expect(storm.scan.value!.cells).toHaveLength(4)
  })
})

describe('where nothing is asked for', () => {
  it('stops when the layer is switched off, with no timer left waiting', async () => {
    const { on } = mount()
    await settle()
    on.value = false
    await nextTick()
    expect(vi.getTimerCount()).toBe(0)
    await vi.advanceTimersByTimeAsync(REFRESH_MS * 4)
    expect(fetched).toHaveBeenCalledTimes(1)
  })

  it('stops while the tab is in the background, with no timer left waiting', async () => {
    mount()
    await settle()
    setVisibility('hidden')
    await nextTick()
    expect(vi.getTimerCount()).toBe(0)
    await vi.advanceTimersByTimeAsync(REFRESH_MS * 4)
    expect(fetched).toHaveBeenCalledTimes(1)
  })

  it('does not ask at all for a tab that is hidden where the layer is switched on', async () => {
    setVisibility('hidden')
    mount()
    await vi.advanceTimersByTimeAsync(REFRESH_MS * 2)
    expect(fetched).not.toHaveBeenCalled()
    // and asks as soon as the tab is in front
    setVisibility('visible')
    await settle()
    expect(fetched).toHaveBeenCalledTimes(1)
  })

  it('asks at once when the tab comes back, whatever the age of the scan it holds, and waits the interval again after it', async () => {
    mount()
    await settle()
    setVisibility('hidden')
    await nextTick()
    // back after 2 minutes: the scan is asked for at once, so that what is shown is of the minute the reader is back
    vi.setSystemTime(Date.now() + 2 * 60_000)
    setVisibility('visible')
    await settle()
    expect(fetched).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(REFRESH_MS - 1)
    expect(fetched).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(1)
    expect(fetched).toHaveBeenCalledTimes(3)
  })

  it('asks at once when the layer is switched on again, and keeps the scan it has meanwhile', async () => {
    const { on, storm } = mount()
    await settle()
    on.value = false
    await nextTick()
    vi.setSystemTime(Date.now() + 20 * 60_000)
    expect(storm.scan.value).not.toBeNull()
    on.value = true
    await settle()
    expect(fetched).toHaveBeenCalledTimes(2)
  })

  it('drops an answer that arrives after the layer was switched off, and schedules nothing for it', async () => {
    let release!: (answer: unknown) => void
    fetched.mockReturnValueOnce(new Promise((resolve) => {
      release = resolve
    }))
    const { on, storm } = mount()
    await nextTick()
    on.value = false
    await nextTick()
    release(exampleScan())
    await settle()
    expect(storm.scan.value).toBeNull()
    expect(storm.status.value).toBe('idle')
    expect(vi.getTimerCount()).toBe(0)
  })

  it('leaves no timer when its scope is stopped', async () => {
    const { scope } = mount()
    await settle()
    expect(vi.getTimerCount()).toBe(1)
    scope.stop()
    expect(vi.getTimerCount()).toBe(0)
  })
})

describe('a request that fails', () => {
  it('is an error where no scan ever came, which Retry asks again', async () => {
    fetched.mockRejectedValueOnce(new Error('offline'))
    const { storm } = mount()
    await settle()
    expect(storm.status.value).toBe('error')
    expect(storm.scan.value).toBeNull()
    await storm.retry()
    await settle()
    expect(storm.status.value).toBe('success')
    expect(fetched).toHaveBeenCalledTimes(2)
  })

  it('is asked for again at the next refresh, not at once', async () => {
    fetched.mockRejectedValue(new Error('offline'))
    mount()
    await settle()
    await vi.advanceTimersByTimeAsync(REFRESH_MS - 1)
    expect(fetched).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(fetched).toHaveBeenCalledTimes(2)
  })

  it('keeps the scan in hand when a refresh fails, says so, and clears it when the next one comes', async () => {
    fetched.mockResolvedValueOnce(exampleScan())
    const { storm } = mount()
    await settle()
    fetched.mockRejectedValueOnce(new Error('offline'))
    await vi.advanceTimersByTimeAsync(REFRESH_MS)
    expect(storm.status.value).toBe('success')
    expect(storm.scan.value!.cells).toHaveLength(4)
    expect(storm.refreshFailed.value).toBe(true)
    fetched.mockResolvedValueOnce(emptyScan('2026-11-17T22:25:00.000000+00:00'))
    await vi.advanceTimersByTimeAsync(REFRESH_MS)
    expect(storm.refreshFailed.value).toBe(false)
    expect(storm.scan.value!.referenceTime).toBe('2026-11-17T22:25:00.000000+00:00')
  })

  it('is an error where the answer has no list of cells, which is no quiet sky', async () => {
    fetched.mockResolvedValueOnce({ detail: 'a page' })
    const { storm } = mount()
    await settle()
    expect(storm.status.value).toBe('error')
  })
})

describe('a scan that has aged', () => {
  it('is out of date once its reference time is more than 20 minutes behind, which is read when the answer comes', async () => {
    // the scan of 22:10, the time 22:20
    const { storm } = mount()
    await settle()
    expect(storm.outdated.value).toBe(false)
    // the next request fails, 15 minutes on: the scan in hand is 25 minutes old
    fetched.mockRejectedValue(new Error('offline'))
    await vi.advanceTimersByTimeAsync(REFRESH_MS)
    expect(storm.outdated.value).toBe(false)
    await vi.advanceTimersByTimeAsync(REFRESH_MS)
    // 22:30 and 22:10: 20 minutes exactly is not more
    expect(storm.outdated.value).toBe(false)
    await vi.advanceTimersByTimeAsync(REFRESH_MS)
    expect(storm.scan.value).not.toBeNull()
    expect(storm.refreshFailed.value).toBe(true)
    expect(storm.outdated.value).toBe(true)
  })

  it('is out of date again after the layer was off for hours, at once, while the new scan is asked for, and the scan is kept', async () => {
    const { on, storm } = mount()
    await settle()
    on.value = false
    await nextTick()
    vi.setSystemTime(Date.now() + 3 * 3_600_000)
    // the request that the switch asks for does not come
    fetched.mockReturnValue(new Promise(() => {}))
    on.value = true
    await nextTick()
    expect(storm.scan.value).not.toBeNull()
    expect(storm.outdated.value).toBe(true)
  })

  it('is out of date for the tab that comes back after hours, until the scan it asks for at once comes', async () => {
    const { storm } = mount()
    await settle()
    setVisibility('hidden')
    await nextTick()
    vi.setSystemTime(Date.now() + 3 * 3_600_000)
    let release!: (answer: unknown) => void
    fetched.mockReturnValueOnce(new Promise((resolve) => {
      release = resolve
    }))
    setVisibility('visible')
    await nextTick()
    expect(storm.outdated.value).toBe(true)
    release(emptyScan())
    await settle()
    // the new scan is of the time now: not out of date
    expect(fetched).toHaveBeenCalledTimes(2)
    expect(storm.outdated.value).toBe(false)
  })

  it('is not out of date where the scan has no time of its own', async () => {
    fetched.mockResolvedValue({ cells: [] })
    const { storm } = mount()
    await settle()
    vi.setSystemTime(Date.now() + 3 * 3_600_000)
    fetched.mockRejectedValue(new Error('offline'))
    await vi.advanceTimersByTimeAsync(REFRESH_MS)
    expect(storm.outdated.value).toBe(false)
  })
})

describe('what failed before a new request', () => {
  it('is no error while the request that follows a Retry runs: the status is pending, not error', async () => {
    fetched.mockRejectedValueOnce(new Error('offline'))
    const { storm } = mount()
    await settle()
    expect(storm.status.value).toBe('error')
    fetched.mockReturnValueOnce(new Promise(() => {}))
    void storm.retry()
    await nextTick()
    expect(storm.status.value).toBe('pending')
    expect(storm.error.value).toBeNull()
  })

  it('is no error when the layer is switched on again after a failure: it is pending until the answer', async () => {
    fetched.mockRejectedValueOnce(new Error('offline'))
    const { on, storm } = mount()
    await settle()
    expect(storm.status.value).toBe('error')
    on.value = false
    await nextTick()
    fetched.mockReturnValueOnce(new Promise(() => {}))
    on.value = true
    await nextTick()
    expect(storm.status.value).toBe('pending')
    expect(storm.error.value).toBeNull()
  })

  it('is no failed refresh when the layer is switched on again after one: the scan is shown without the note until it fails again', async () => {
    const { on, storm } = mount()
    await settle()
    fetched.mockRejectedValueOnce(new Error('offline'))
    await vi.advanceTimersByTimeAsync(REFRESH_MS)
    expect(storm.refreshFailed.value).toBe(true)
    on.value = false
    await nextTick()
    fetched.mockReturnValueOnce(new Promise(() => {}))
    on.value = true
    await nextTick()
    expect(storm.refreshFailed.value).toBe(false)
  })
})
