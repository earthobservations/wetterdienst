import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { useRadarFrames } from '~/composables/useRadarFrames'
import { RADAR_REFRESH_MS } from '~/utils/radar'
import { radarAnswer } from '../../helpers/radar-answer'

// The refresh of the radar's list of frames (GH-3788): asked for at once and again every 5 minutes (DWD writes a run that often), a list
// that fails to refresh is kept, one that never came is an error that Retry asks again, and a loop that ends at an old run is stale.
// The timer, the tab and the kept answer are `usePolledAnswer`'s, which the thunderstorm cells share (`useStormCells.test.ts`).

const fetched = vi.fn()
const scopes: Array<ReturnType<typeof effectScope>> = []
const NOW = new Date('2026-11-19T21:30:00Z')

function mount(initial = true) {
  const on = ref(initial)
  const scope = effectScope()
  scopes.push(scope)
  const radar = scope.run(() => useRadarFrames(() => on.value, { load: () => fetched() }))!
  return { on, radar }
}

async function settle() {
  await vi.advanceTimersByTimeAsync(0)
  await nextTick()
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'], now: NOW })
  fetched.mockReset()
  fetched.mockResolvedValue(radarAnswer({ run: '2026-11-19T21:25:00Z' }))
})

afterEach(() => {
  scopes.splice(0).forEach(scope => scope.stop())
  vi.useRealTimers()
})

describe('the radar\'s list of frames', () => {
  it('is asked for at once and read into a loop, with the frames in time order', async () => {
    const { radar } = mount()
    await settle()
    expect(fetched).toHaveBeenCalledTimes(1)
    expect(radar.status.value).toBe('success')
    expect(radar.loop.value?.frames).toHaveLength(49)
    expect(radar.stale.value).toBe(false)
  })

  it('is asked for again every 5 minutes, and the loop is the new one', async () => {
    const { radar } = mount()
    await settle()
    fetched.mockResolvedValue(radarAnswer({ run: '2026-11-19T21:30:00Z' }))
    await vi.advanceTimersByTimeAsync(RADAR_REFRESH_MS)
    expect(fetched).toHaveBeenCalledTimes(2)
    expect(radar.loop.value?.run).toBe('2026-11-19T21:30:00Z')
  })

  it('is not asked for while the page is not active', async () => {
    const { radar } = mount(false)
    await vi.advanceTimersByTimeAsync(RADAR_REFRESH_MS * 3)
    expect(fetched).not.toHaveBeenCalled()
    expect(radar.status.value).toBe('idle')
  })

  it('keeps the loop it has where a refresh fails, and says so', async () => {
    const { radar } = mount()
    await settle()
    fetched.mockRejectedValue(new Error('down'))
    await vi.advanceTimersByTimeAsync(RADAR_REFRESH_MS)
    expect(radar.refreshFailed.value).toBe(true)
    expect(radar.loop.value?.frames).toHaveLength(49)
    expect(radar.status.value).toBe('success')
  })

  it('is an error where the first list never came, and Retry asks again', async () => {
    fetched.mockRejectedValue(new Error('down'))
    const { radar } = mount()
    await settle()
    expect(radar.status.value).toBe('error')
    fetched.mockResolvedValue(radarAnswer({ run: '2026-11-19T21:25:00Z' }))
    await radar.retry()
    expect(radar.status.value).toBe('success')
  })

  it('is an error for an answer that is no loop', async () => {
    fetched.mockResolvedValue({ frames: 'none' })
    const { radar } = mount()
    await settle()
    expect(radar.status.value).toBe('error')
  })

  it('is stale where the backend says so (radar-stale), whatever the age of the newest run', async () => {
    fetched.mockResolvedValue(radarAnswer({ run: '2026-11-19T21:25:00Z', warnings: [{ code: 'radar-stale', message: 'old' }] }))
    const { radar } = mount()
    await settle()
    expect(radar.stale.value).toBe(true)
  })

  it('reads the age of the newest run when the list is read', async () => {
    // the run is 25 minutes old when the answer comes
    fetched.mockResolvedValue(radarAnswer({ run: '2026-11-19T21:05:00Z' }))
    const { radar } = mount()
    await settle()
    expect(radar.stale.value).toBe(true)
    // and a warning of the backend is stale at any age
    fetched.mockResolvedValue(radarAnswer({ run: '2026-11-19T21:30:00Z', warnings: [{ code: 'radar-stale', message: 'old' }] }))
    await radar.retry()
    expect(radar.stale.value).toBe(true)
  })
})
