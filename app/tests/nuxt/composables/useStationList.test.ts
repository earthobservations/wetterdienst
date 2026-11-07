import { describe, expect, it } from 'vitest'
import { ref } from 'vue'
import { useStationList } from '~/composables/useStationList'

// The list of stations a layer of the map is made of (GH-3650): asked for once for its key, and never another key's.

function station(station_id: string, latitude: number | null = 50) {
  return { station_id, name: station_id, region: null, latitude, longitude: latitude === null ? null : 10, elevation: null }
}

/** An answer a test holds back until it releases it */
function gate<T>() {
  let release!: (value: T) => void
  let fail!: (reason: unknown) => void
  const promise = new Promise<T>((resolve, reject) => {
    release = resolve
    fail = reject
  })
  return { promise, release, fail }
}

describe('a list of stations', () => {
  it('is asked for once, keeps the stations that have a position, and is not asked for again for the same key', async () => {
    let asks = 0
    const list = useStationList(() => 'a', async () => {
      asks++
      return [station('1'), station('2', null)]
    })
    expect(list.status.value).toBe('idle')
    await list.ensure()
    expect(list.status.value).toBe('success')
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['1'])
    await list.ensure()
    expect(asks).toBe(1)
  })

  it('is asked for again after a failure, and again on request', async () => {
    let asks = 0
    const list = useStationList(() => 'a', async () => {
      asks++
      if (asks === 1)
        throw new Error('down')
      return [station('1')]
    })
    await list.ensure()
    expect(list.status.value).toBe('error')
    expect((list.error.value as Error).message).toBe('down')
    await list.ensure()
    expect(list.status.value).toBe('success')
    expect(list.error.value).toBeNull()
    await list.ensure(true)
    expect(asks).toBe(3)
  })

  it('reads as nothing where its key has moved on, until the new list is asked for: the stations of the old list are never the new one\'s', async () => {
    const key = ref('a')
    const list = useStationList(() => key.value, async () => [station(key.value)])
    await list.ensure()
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['a'])
    key.value = 'b'
    expect(list.stations.value).toEqual([])
    expect(list.status.value).toBe('idle')
    await list.ensure()
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['b'])
    // and back to a key it had: the list of the other key is not served either
    key.value = 'a'
    expect(list.stations.value).toEqual([])
  })

  it('drops an answer that comes after its key has moved on, whichever answer is last', async () => {
    const key = ref('a')
    const answers: Record<string, ReturnType<typeof gate<ReturnType<typeof station>[]>>> = { a: gate(), b: gate() }
    const list = useStationList(() => key.value, () => answers[key.value]!.promise)
    const first = list.ensure()
    key.value = 'b'
    const second = list.ensure()
    // the newer key answers first, the older one late
    answers.b!.release([station('from-b')])
    await second
    answers.a!.release([station('from-a')])
    await first
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['from-b'])
    expect(list.status.value).toBe('success')
  })

  it('drops a failure that comes after its key has moved on: it is not the failure of the list shown', async () => {
    const key = ref('a')
    const answers: Record<string, ReturnType<typeof gate<ReturnType<typeof station>[]>>> = { a: gate(), b: gate() }
    const list = useStationList(() => key.value, () => answers[key.value]!.promise)
    const first = list.ensure()
    key.value = 'b'
    const second = list.ensure()
    answers.b!.release([station('from-b')])
    await second
    answers.a!.fail(new Error('late'))
    await first
    expect(list.status.value).toBe('success')
    expect(list.error.value).toBeNull()
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['from-b'])
  })

  it('does not let an answer that was asked for first replace the list asked for by a forced second ask of the same key', async () => {
    const answers = [gate<ReturnType<typeof station>[]>(), gate<ReturnType<typeof station>[]>()]
    let asks = 0
    const list = useStationList(() => 'a', () => answers[asks++]!.promise)
    const first = list.ensure()
    const second = list.ensure(true)
    answers[1]!.release([station('new')])
    await second
    answers[0]!.release([station('old')])
    await first
    expect(list.stations.value.map(entry => entry.station_id)).toEqual(['new'])
  })
})
