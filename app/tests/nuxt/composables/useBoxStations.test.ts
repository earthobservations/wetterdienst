import type { MapBox } from '~/utils/map-tool'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import { BOX_DEBOUNCE_MS, useBoxStations } from '~/composables/useBoxStations'
import { BOX_MAX_AREA, BOX_PAD, padBox } from '~/utils/map-tool'

// The stations of a layer that is too large to be loaded whole, asked for by the part of the map in view (GH-4078): one request for a
// drag or a run of zooms (debounce), none for a move inside what is loaded, the one on its way cancelled where the map has moved
// past it, and none at all where the view holds most of the world.

function station(station_id: string, latitude = 50, longitude = 10) {
  return { station_id, name: station_id, region: null, latitude, longitude, elevation: null, start_timestamp: null, end_timestamp: null }
}

const view = (left: number, bottom: number, size = 4): MapBox => ({ left, bottom, right: left + size, top: bottom + size })

/** What the loader was asked: the box and the signal of each request, and the answer each is held to until the test gives it */
interface Ask {
  box: MapBox
  signal: AbortSignal
  answer: (stations: ReturnType<typeof station>[]) => void
  fail: (reason: unknown) => void
}

function setup(options: { delay?: number, maxArea?: number } = {}) {
  const asks: Ask[] = []
  const scope = effectScope()
  const list = scope.run(() => useBoxStations({
    ...options,
    load: (box, signal) => new Promise((resolve, reject) => {
      asks.push({ box, signal, answer: resolve as Ask['answer'], fail: reject })
      signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    }),
  }))!
  return { list, asks, scope }
}

beforeEach(() => {
  vi.useFakeTimers()
})
afterEach(() => {
  vi.useRealTimers()
})

describe('the stations of the view', () => {
  it('asks for the first view at once, `pad` larger on every side, and shows what comes', async () => {
    const { list, asks } = setup()
    list.show(view(8, 50))
    expect(asks).toHaveLength(1)
    expect(asks[0]!.box).toEqual(padBox(view(8, 50), BOX_PAD))
    expect(list.status.value).toBe('pending')
    asks[0]!.answer([station('A'), { ...station('B'), latitude: null as unknown as number }])
    await vi.advanceTimersByTimeAsync(0)
    expect(list.status.value).toBe('success')
    // the stations that have no position are not kept
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['A'])
    expect(list.refreshing.value).toBe(false)
  })

  it('asks for nothing while the view stays inside the box loaded, or inside the one on its way', async () => {
    const { list, asks } = setup()
    list.show(view(8, 50))
    // inside the request on its way
    list.show(view(8.2, 50.2, 3.5))
    expect(asks).toHaveLength(1)
    asks[0]!.answer([station('A')])
    await vi.advanceTimersByTimeAsync(0)
    // inside what is loaded: a small move, and a zoom in
    list.show(view(8.4, 50.1))
    list.show(view(9, 51, 2))
    await vi.advanceTimersByTimeAsync(BOX_DEBOUNCE_MS * 3)
    expect(asks).toHaveLength(1)
    expect(list.status.value).toBe('success')
  })

  it('asks once for a run of moves, after the map has rested, and keeps the stations shown meanwhile', async () => {
    const { list, asks } = setup()
    list.show(view(8, 50))
    asks[0]!.answer([station('A')])
    await vi.advanceTimersByTimeAsync(0)

    list.show(view(20, 50))
    list.show(view(21, 50))
    list.show(view(22, 50))
    // pending for the box of the view, the stations of the old one stay
    expect(list.status.value).toBe('success')
    expect(list.refreshing.value).toBe(true)
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['A'])
    await vi.advanceTimersByTimeAsync(BOX_DEBOUNCE_MS - 1)
    expect(asks).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(asks).toHaveLength(2)
    expect(asks[1]!.box).toEqual(padBox(view(22, 50), BOX_PAD))
    asks[1]!.answer([station('B', 52, 24)])
    await vi.advanceTimersByTimeAsync(0)
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['B'])
    expect(list.refreshing.value).toBe(false)
  })

  it('cancels the request on its way when the map has moved past it, and drops its answer', async () => {
    const { list, asks } = setup()
    list.show(view(8, 50))
    asks[0]!.answer([station('A')])
    await vi.advanceTimersByTimeAsync(0)

    list.show(view(20, 50))
    await vi.advanceTimersByTimeAsync(BOX_DEBOUNCE_MS)
    expect(asks).toHaveLength(2)
    expect(asks[1]!.signal.aborted).toBe(false)

    // moved on before it answered
    list.show(view(40, 50))
    expect(asks[1]!.signal.aborted).toBe(true)
    // an answer that still comes is not the one wanted
    asks[1]!.answer([station('LATE')])
    await vi.advanceTimersByTimeAsync(0)
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['A'])
    await vi.advanceTimersByTimeAsync(BOX_DEBOUNCE_MS)
    expect(asks).toHaveLength(3)
    asks[2]!.answer([station('C')])
    await vi.advanceTimersByTimeAsync(0)
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['C'])
    expect(list.status.value).toBe('success')
  })

  it('cancels a request that has not been made yet when the map is back inside what is loaded', async () => {
    const { list, asks } = setup()
    list.show(view(8, 50))
    asks[0]!.answer([station('A')])
    await vi.advanceTimersByTimeAsync(0)
    list.show(view(30, 50))
    list.show(view(8.3, 50.3))
    await vi.advanceTimersByTimeAsync(BOX_DEBOUNCE_MS * 2)
    expect(asks).toHaveLength(1)
    expect(list.refreshing.value).toBe(false)
  })

  it('asks for nothing, and shows none, where the view holds more than BOX_MAX_AREA, and asks again once it is smaller', async () => {
    const { list, asks } = setup()
    list.show(view(8, 50))
    asks[0]!.answer([station('A')])
    await vi.advanceTimersByTimeAsync(0)

    const world: MapBox = { left: -180, bottom: -60, right: 180, top: 80 }
    list.show(world)
    expect(list.tooWide.value).toBe(true)
    expect(list.stations.value).toEqual([])
    expect(list.status.value).toBe('idle')
    await vi.advanceTimersByTimeAsync(BOX_DEBOUNCE_MS * 2)
    expect(asks).toHaveLength(1)

    // just under the limit is asked for, just over is not
    const side = Math.sqrt(BOX_MAX_AREA)
    list.show(view(0, 0, side + 0.5))
    expect(list.tooWide.value).toBe(true)
    list.show(view(0, 0, side - 0.5))
    expect(list.tooWide.value).toBe(false)
    expect(asks).toHaveLength(2)
  })

  it('cancels the request on its way when the view becomes too wide', async () => {
    const { list, asks } = setup()
    list.show(view(8, 50))
    list.show({ left: -180, bottom: -60, right: 180, top: 80 })
    expect(asks[0]!.signal.aborted).toBe(true)
    asks[0]!.answer([station('LATE')])
    await vi.advanceTimersByTimeAsync(0)
    expect(list.stations.value).toEqual([])
    expect(list.status.value).toBe('idle')
  })

  it('tells a failure, keeps the stations shown, and asks for the view again on retry', async () => {
    const { list, asks } = setup()
    list.show(view(8, 50))
    asks[0]!.answer([station('A')])
    await vi.advanceTimersByTimeAsync(0)
    list.show(view(30, 50))
    await vi.advanceTimersByTimeAsync(BOX_DEBOUNCE_MS)
    asks[1]!.fail(new Error('down'))
    await vi.advanceTimersByTimeAsync(0)
    expect(list.status.value).toBe('error')
    expect((list.error.value as Error).message).toBe('down')
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['A'])

    list.retry()
    expect(asks).toHaveLength(3)
    asks[2]!.answer([station('B')])
    await vi.advanceTimersByTimeAsync(0)
    expect(list.status.value).toBe('success')
    expect(list.error.value).toBeNull()
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['B'])
  })

  it('keeps the station pinned, the same object, whatever box is loaded', async () => {
    const { list, asks } = setup()
    list.show(view(8, 50))
    const first = station('A', 51, 9)
    asks[0]!.answer([first])
    await vi.advanceTimersByTimeAsync(0)
    const pinned = list.stations.value[0]!
    list.pin(pinned)

    // another box: the station is not in it, and stays; where it is, it is the pinned object and not the box's new copy of it
    list.show(view(30, 50))
    await vi.advanceTimersByTimeAsync(BOX_DEBOUNCE_MS)
    asks[1]!.answer([station('B', 51, 31)])
    await vi.advanceTimersByTimeAsync(0)
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['B', 'A'])
    list.show(view(8, 50))
    await vi.advanceTimersByTimeAsync(BOX_DEBOUNCE_MS)
    asks[2]!.answer([station('A', 51, 9), station('C', 52, 10)])
    await vi.advanceTimersByTimeAsync(0)
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['A', 'C'])
    expect(list.stations.value[0]).toBe(pinned)

    list.pin(null)
    expect(list.stations.value[0]).not.toBe(pinned)
  })

  it('stops asking, and cancels what is on its way, when the layer is left', async () => {
    const { list, asks } = setup()
    list.show(view(8, 50))
    list.stop()
    expect(asks[0]!.signal.aborted).toBe(true)
    expect(list.status.value).toBe('idle')
    // the box left is asked for again where the layer is shown again
    list.show(view(8, 50))
    expect(asks).toHaveLength(2)
  })

  it('cancels its request with the scope it is in', async () => {
    const { list, asks, scope } = setup()
    list.show(view(8, 50))
    scope.stop()
    expect(asks[0]!.signal.aborted).toBe(true)
  })
})
