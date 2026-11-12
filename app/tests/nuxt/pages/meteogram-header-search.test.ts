import type { VueWrapper } from '@vue/test-utils'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import MeteogramPage from '~/pages/meteogram.vue'

// In a file of its own: the page's tests of the other file leave their pages mounted, and every one of them
// answers a change of the URL, which these tests count the requests of.

describe('the meteogram page followed to a station by the search of the header (GH-3518)', () => {
  const stations: Record<string, { station_id: string, name: string, latitude: number, longitude: number }> = {
    '01001': { station_id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 },
    '10381': { station_id: '10381', name: 'BERLIN', latitude: 52.46, longitude: 13.31 },
    '10147': { station_id: '10147', name: 'HAMBURG', latitude: 53.63, longitude: 10.0 },
  }
  let wrapper: VueWrapper | undefined
  const endpoints: Array<() => void> = []
  const stationRequests: string[] = []
  // an answer the lookup of one station waits for, where a test holds it
  let slow: Promise<void> | undefined
  let slowId = '99999'

  beforeEach(() => {
    stationRequests.length = 0
    slow = undefined
    slowId = '99999'
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ values: [] }), { status: 200 }))
    endpoints.push(registerEndpoint('/api/stations', async (event) => {
      const id = String(getQuery(event).stations)
      stationRequests.push(id)
      if (id === slowId && slow)
        await slow
      const station = stations[id]
      return { stations: station ? [station] : [] }
    }))
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    endpoints.splice(0).forEach(dispose => dispose())
  })

  it('shows the station the URL names again after the page chose another one', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    // the reader picks another station in the page, which the page writes to the URL
    vm.selectedStation = stations['10381']
    await vi.waitFor(() => expect(useRoute().query.station).toBe('10381'))
    // and then searches the first one again in the header
    await navigateTo('/meteogram?station=01001')
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
  })

  it('shows a station the reader chose and cleared when the header searches it', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram' })
    const vm = wrapper.vm as any
    vm.selectedStation = stations['10381']
    await vi.waitFor(() => expect(useRoute().query.station).toBe('10381'))
    vm.selectedStation = null
    await vi.waitFor(() => expect(useRoute().query.station).toBeUndefined())
    await navigateTo('/meteogram?station=10381')
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('10381'))
  })

  it('does not carry the run chosen for one station over to the one the search names', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001&issue=2026-10-03T06:00:00' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    expect(vm.selectedIssue).toBe('2026-10-03T06:00:00')
    await navigateTo('/meteogram?station=10381')
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('10381'))
    expect(vm.selectedIssue).toBe('')
    await vi.waitFor(() => expect(useRoute().query.issue).toBeUndefined())
  })

  it('fetches the values once for the station the search names, whatever run the one before had', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001&issue=2026-10-03T06:00:00' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    await new Promise(resolve => setTimeout(resolve, 50))
    const valuesRequests = () => vi.mocked(globalThis.fetch).mock.calls.filter(([url]) => String(url).includes('/api/values?')).length
    const before = valuesRequests()
    await navigateTo('/meteogram?station=10381')
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('10381'))
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(valuesRequests() - before).toBe(1)
  })

  it('fetches for a run chosen while the station the search names is still being looked up', async () => {
    let release: () => void = () => {}
    const answer = new Promise<void>((resolve) => {
      release = resolve
    })
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    await new Promise(resolve => setTimeout(resolve, 50))
    slow = answer
    const valuesRequests = () => vi.mocked(globalThis.fetch).mock.calls.filter(([url]) => String(url).includes('/api/values?')).length
    await navigateTo('/meteogram?station=99999')
    await vi.waitFor(() => expect(stationRequests.filter(id => id === '99999')).toHaveLength(1))
    const before = valuesRequests()
    vm.selectedIssue = '2026-10-03T06:00:00'
    await vi.waitFor(() => expect(valuesRequests()).toBe(before + 1))
    release()
  })

  it('shows the station of the later search where the answer of an earlier one comes last', async () => {
    let release: () => void = () => {}
    const answer = new Promise<void>((resolve) => {
      release = resolve
    })
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    slow = answer
    slowId = '10381'
    await navigateTo('/meteogram?station=10381')
    await vi.waitFor(() => expect(stationRequests.filter(id => id === '10381')).toHaveLength(1))
    await navigateTo('/meteogram?station=10147')
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('10147'))
    release()
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(vm.selectedStation?.station_id).toBe('10147')
    expect(vm.isRestoringFromUrl).toBe(false)
  })

  it('takes the latest run for a link to the station that is shown, without a run', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001&issue=2026-10-03T06:00:00' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    expect(vm.selectedIssue).toBe('2026-10-03T06:00:00')
    await new Promise(resolve => setTimeout(resolve, 50))
    const valuesRequests = () => vi.mocked(globalThis.fetch).mock.calls.filter(([url]) => String(url).includes('/api/values?'))
    const before = valuesRequests().length
    await navigateTo('/meteogram?station=01001')
    await vi.waitFor(() => expect(vm.selectedIssue).toBe(''))
    await new Promise(resolve => setTimeout(resolve, 50))
    // the URL stays without a run, and the latest run is fetched once
    expect(useRoute().query.issue).toBeUndefined()
    const asked = valuesRequests().slice(before)
    expect(asked).toHaveLength(1)
    expect(String(asked[0]![0])).not.toContain('issue=')
  })

  it('takes the latest run for a search back to the shown station after another that was not found', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001&issue=2026-10-03T06:00:00' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    await navigateTo('/meteogram?station=99999')
    await vi.waitFor(() => expect(stationRequests.filter(id => id === '99999')).toHaveLength(1))
    await vi.waitFor(() => expect(vm.isRestoringFromUrl).toBe(false))
    await navigateTo('/meteogram?station=01001')
    await vi.waitFor(() => expect(vm.selectedIssue).toBe(''))
    expect(useRoute().query.issue).toBeUndefined()
  })

  it('shows the station the reader searched last where a lookup of an earlier one is under way', async () => {
    let release: () => void = () => {}
    const answer = new Promise<void>((resolve) => {
      release = resolve
    })
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    slow = answer
    slowId = '10381'
    await navigateTo('/meteogram?station=10381')
    await vi.waitFor(() => expect(stationRequests.filter(id => id === '10381')).toHaveLength(1))
    await navigateTo('/meteogram?station=01001')
    release()
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(vm.selectedStation?.station_id).toBe('01001')
    expect(useRoute().query.station).toBe('01001')
    expect(vm.isRestoringFromUrl).toBe(false)
  })

  it('keeps the station cleared where a lookup of the one the search named is under way', async () => {
    let release: () => void = () => {}
    const answer = new Promise<void>((resolve) => {
      release = resolve
    })
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    slow = answer
    slowId = '10381'
    await navigateTo('/meteogram?station=10381')
    await vi.waitFor(() => expect(stationRequests.filter(id => id === '10381')).toHaveLength(1))
    vm.selectedStation = null
    await vi.waitFor(() => expect(useRoute().query.station).toBeUndefined())
    release()
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(vm.selectedStation).toBeNull()
  })

  it('takes the run of the URL as it is when the lookup is answered, not as it was when it began', async () => {
    let release: () => void = () => {}
    const answer = new Promise<void>((resolve) => {
      release = resolve
    })
    slow = answer
    slowId = '01001'
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001&issue=2026-10-03T06:00:00' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(stationRequests.filter(id => id === '01001')).toHaveLength(1))
    await navigateTo('/meteogram?station=01001')
    release()
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(vm.selectedIssue).toBe('')
    expect(useRoute().query.issue).toBeUndefined()
  })

  it('keeps the station the reader picked where a lookup of the one the search named is under way', async () => {
    let release: () => void = () => {}
    const answer = new Promise<void>((resolve) => {
      release = resolve
    })
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    slow = answer
    slowId = '10381'
    await navigateTo('/meteogram?station=10381')
    await vi.waitFor(() => expect(stationRequests.filter(id => id === '10381')).toHaveLength(1))
    vm.selectedStation = stations['10147']
    await vi.waitFor(() => expect(useRoute().query.station).toBe('10147'))
    release()
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(vm.selectedStation?.station_id).toBe('10147')
  })

  it('asks again for a station that was not found, once the reader has moved the page on to a run', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    await navigateTo('/meteogram?station=99999')
    await vi.waitFor(() => expect(stationRequests.filter(id => id === '99999')).toHaveLength(1))
    // the reader picks a run: the page writes the station it shows to the URL again
    vm.selectedIssue = '2026-10-03T06:00:00'
    await vi.waitFor(() => expect(useRoute().query.station).toBe('01001'))
    await navigateTo('/meteogram?station=99999')
    await vi.waitFor(() => expect(stationRequests.filter(id => id === '99999')).toHaveLength(2))
  })

  it('cancels the lookup of the station the search named where the tab bar goes to the page without a station (GH-3732)', async () => {
    let release: () => void = () => {}
    const answer = new Promise<void>((resolve) => {
      release = resolve
    })
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    slow = answer
    slowId = '10381'
    await navigateTo('/meteogram?station=10381')
    await vi.waitFor(() => expect(stationRequests.filter(id => id === '10381')).toHaveLength(1))
    await navigateTo('/meteogram')
    release()
    await new Promise(resolve => setTimeout(resolve, 100))
    // the station that was shown stays: the answer of the lookup is not applied
    expect(vm.selectedStation?.station_id).toBe('01001')
    expect(vm.isRestoringFromUrl).toBe(false)
    // and the station may be searched again
    slow = undefined
    await navigateTo('/meteogram?station=10381')
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('10381'))
  })
})

// The requests of the page for the values and the runs, which the page asks one of for a change, and of which the
// answer of the latest is the one it shows (GH-3732)
describe('the meteogram page\'s requests for the values and the runs', () => {
  const stations: Record<string, { station_id: string, name: string, latitude: number, longitude: number }> = {
    '01001': { station_id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 },
    '10381': { station_id: '10381', name: 'BERLIN', latitude: 52.46, longitude: 13.31 },
  }
  const RUN_J = '2026-10-03T06:00:00'
  const RUN_K = '2026-10-03T12:00:00'
  let wrapper: VueWrapper | undefined
  const endpoints: Array<() => void> = []
  // the answers of the values request a test holds, by the run it asked for ('' = the latest), and the requests made
  let held: Record<string, Promise<void>> = {}
  let heldIssues: Record<string, Promise<void>> = {}
  const answers: Record<string, string[]> = {}
  // the stations the runs were asked for
  const issueRequests: string[] = []

  const valuesRequests = () => vi.mocked(globalThis.fetch).mock.calls.map(([url]) => new URL(String(url), 'http://localhost')).filter(url => url.pathname === '/api/values')
  // a value of the run it was asked for, so that the answer on show says which request it came from
  const valueOf = (run: string) => [{ station_id: '01001', parameter: 'temperature_air_2m', timestamp: '2026-10-03T12:00:00+00:00', value: 1, run }]

  beforeEach(() => {
    held = {}
    heldIssues = {}
    issueRequests.length = 0
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://localhost')
      const run = url.searchParams.get('issue') ?? ''
      await held[`${url.searchParams.get('stations')}|${run}`]
      return new Response(JSON.stringify({ values: valueOf(run) }), { status: 200 })
    })
    endpoints.push(registerEndpoint('/api/stations', (event) => {
      const station = stations[String(getQuery(event).stations)]
      return { stations: station ? [station] : [] }
    }))
    endpoints.push(registerEndpoint('/api/issues', async (event) => {
      const id = String(getQuery(event).station)
      issueRequests.push(id)
      await heldIssues[id]
      return { issues: answers[id] ?? [] }
    }))
    answers['01001'] = [RUN_J, RUN_K]
    answers['10381'] = ['2026-10-04T00:00:00']
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    endpoints.splice(0).forEach(dispose => dispose())
  })

  async function showStation(route: string) {
    wrapper = await mountSuspended(MeteogramPage, { route })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    await vi.waitFor(() => expect(vm.pending).toBe(false))
    await new Promise(resolve => setTimeout(resolve, 50))
    return vm
  }

  it('asks for the values once where another station is picked while a run is set', async () => {
    const vm = await showStation(`/meteogram?station=01001&issue=${RUN_J}`)
    expect(vm.selectedIssue).toBe(RUN_J)
    const before = valuesRequests().length
    vm.selectedStation = stations['10381']
    await vi.waitFor(() => expect(valuesRequests().length).toBeGreaterThan(before))
    await new Promise(resolve => setTimeout(resolve, 100))
    const asked = valuesRequests().slice(before)
    // once, and for the latest run of the new station
    expect(asked).toHaveLength(1)
    expect(asked[0]!.searchParams.get('stations')).toBe('10381')
    expect(asked[0]!.searchParams.has('issue')).toBe(false)
    expect(vm.selectedIssue).toBe('')
  })

  it('asks for the values once where a run is picked', async () => {
    const vm = await showStation('/meteogram?station=01001')
    const before = valuesRequests().length
    vm.selectedIssue = RUN_K
    await vi.waitFor(() => expect(valuesRequests().length).toBeGreaterThan(before))
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(valuesRequests().slice(before).map(url => url.searchParams.get('issue'))).toEqual([RUN_K])
  })

  it('shows the values of the run picked last where the answer of an earlier pick comes after it', async () => {
    const vm = await showStation('/meteogram?station=01001')
    let releaseJ: () => void = () => {}
    held[`01001|${RUN_J}`] = new Promise<void>((resolve) => {
      releaseJ = resolve
    })
    const before = valuesRequests().length
    vm.selectedIssue = RUN_J
    await vi.waitFor(() => expect(valuesRequests().length).toBe(before + 1))
    vm.selectedIssue = RUN_K
    await vi.waitFor(() => expect(vm.values.map((value: { run: string }) => value.run)).toEqual([RUN_K]))
    expect(vm.pending).toBe(false)
    releaseJ()
    await new Promise(resolve => setTimeout(resolve, 100))
    // J's answer is no longer wanted: the chart shows K's values, as the run selector does
    expect(vm.values.map((value: { run: string }) => value.run)).toEqual([RUN_K])
    expect(vm.selectedIssue).toBe(RUN_K)
    expect(vm.pending).toBe(false)
  })

  it('keeps the page waiting while the latest request is, where an earlier one is answered', async () => {
    const vm = await showStation('/meteogram?station=01001')
    let releaseJ: () => void = () => {}
    let releaseK: () => void = () => {}
    held[`01001|${RUN_J}`] = new Promise<void>((resolve) => {
      releaseJ = resolve
    })
    held[`01001|${RUN_K}`] = new Promise<void>((resolve) => {
      releaseK = resolve
    })
    const before = valuesRequests().length
    vm.selectedIssue = RUN_J
    await vi.waitFor(() => expect(valuesRequests().length).toBe(before + 1))
    vm.selectedIssue = RUN_K
    await vi.waitFor(() => expect(valuesRequests().length).toBe(before + 2))
    releaseJ()
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(vm.pending).toBe(true)
    expect(vm.values).toEqual([])
    releaseK()
    await vi.waitFor(() => expect(vm.values.map((value: { run: string }) => value.run)).toEqual([RUN_K]))
    expect(vm.pending).toBe(false)
  })

  it('shows the runs of the station picked last where the answer for an earlier one comes after it', async () => {
    const vm = await showStation('/meteogram?station=01001')
    let releaseJanMayen: () => void = () => {}
    heldIssues['01001'] = new Promise<void>((resolve) => {
      releaseJanMayen = resolve
    })
    // the runs of the station that is shown are asked for again and held, another station is picked after it
    issueRequests.length = 0
    vm.selectedStation = { ...stations['01001'] }
    await vi.waitFor(() => expect(issueRequests).toEqual(['01001']))
    vm.selectedStation = stations['10381']
    await vi.waitFor(() => expect(vm.availableIssues).toEqual(['2026-10-04T00:00:00']))
    releaseJanMayen()
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(vm.availableIssues).toEqual(['2026-10-04T00:00:00'])
  })
})
