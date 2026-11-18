import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it } from 'vitest'
import MapStormCells from '~/components/MapStormCells.vue'
import { parseScan } from '~/utils/storm-cells'
import { emptyScan, exampleScan, stormCell, stormCellsAnswer } from '../../helpers/storm-cells-answer'

// The text of the map's thunderstorm cells (GH-4208): what a keyboard and a screen reader have of what the map draws. The
// count and the scan it is of, the empty scan that is the usual one, the list of the cells with their severity in words
// and their motion marked as calculated, the credit of the data, and what is told when the scan is old or fails.

const mounted: Array<{ unmount: () => void }> = []
async function mountCells(props: Record<string, unknown>) {
  const wrapper = await mountSuspended(MapStormCells, { props: { status: 'success', refreshFailed: false, scan: null, ...props }, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
afterEach(() => mounted.splice(0).forEach(wrapper => wrapper.unmount()))

const text = (wrapper: Awaited<ReturnType<typeof mountCells>>, testid: string) => wrapper.find(`[data-testid="${testid}"]`).text()

describe('a scan with no cell', () => {
  it('says there are no thunderstorm cells in the latest scan, with the scan\'s time in UTC, and lists none', async () => {
    const wrapper = await mountCells({ scan: parseScan(emptyScan('2026-11-17T22:20:00.000000+00:00')) })
    expect(text(wrapper, 'map-cells-summary')).toBe('No thunderstorm cells in the latest scan')
    expect(text(wrapper, 'map-cells-scan')).toMatch(/^Scan of .*22:20 UTC$/)
    expect(wrapper.find('[data-testid="map-cells-list"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-cells-stale"]').exists()).toBe(false)
  })

  it('says it where the sky is quiet only in a scan that is old: the scan is stale, and an empty one is then no all-clear', async () => {
    const stale = parseScan(stormCellsAnswer([], { warnings: [{ code: 'scan-stale', message: 'old' }] }))
    const wrapper = await mountCells({ scan: stale })
    expect(text(wrapper, 'map-cells-stale')).toContain('more than 20 minutes old')
    expect(text(wrapper, 'map-cells-summary')).toBe('No thunderstorm cells in the latest scan')
  })
})

describe('a scan with cells', () => {
  it('counts them, and lists each by name with its severity in a number and a word, most severe first', async () => {
    const wrapper = await mountCells({ scan: parseScan(exampleScan()) })
    expect(text(wrapper, 'map-cells-summary')).toBe('Thunderstorm cells in the latest scan: 4')
    const items = wrapper.findAll('[data-testid="map-cells-item"]')
    expect(items).toHaveLength(4)
    expect(items.map(item => item.find('.font-semibold').text())).toEqual(['Cell 12', 'Cell 7', 'Cell 3', 'Cell 21'])
    expect(items.map(item => item.find('[data-testid="map-cells-severity"]').text())).toEqual([
      'Severity 3 (extreme)',
      'Severity 2 (severe)',
      'Severity 1 (moderate)',
      'Severity 0 (weak)',
    ])
  })

  it('names the list for a screen reader, and keeps the badge, which is the mark on the map, out of what it reads', async () => {
    const wrapper = await mountCells({ scan: parseScan(exampleScan()) })
    expect(wrapper.find('ul').attributes('aria-label')).toBe('Thunderstorm cells, most severe first')
    expect(wrapper.find('.map-cells-badge').attributes('aria-hidden')).toBe('true')
    // the severity is in the words as well, so the colour of the badge is no cue alone
    expect(wrapper.find('[data-testid="map-cells-item"]').text()).toContain('Severity 3 (extreme)')
  })

  it('tells the motion in words, the direction by the compass, and marks the direction as calculated', async () => {
    const wrapper = await mountCells({ scan: parseScan(exampleScan()) })
    const motions = wrapper.findAll('[data-testid="map-cells-motion"]').map(motion => motion.text())
    expect(motions).toEqual([
      // 95 degrees, 48 km/h and the others, by the point of the compass they are nearest
      'Moves east at 31 km/h (direction calculated)',
      'Moves north-east at 48 km/h (direction calculated)',
      'Moves south-east at 22 km/h (direction calculated)',
      'Moves west at 15 km/h (direction calculated)',
    ])
  })

  it('tells a motion that is partly known, or not at all, and a cell that stands', async () => {
    const scan = parseScan(stormCellsAnswer([
      stormCell({ cell_id: '1', latitude: 50, longitude: 8, severity: 3, speed: 30, direction: null }),
      stormCell({ cell_id: '2', latitude: 50, longitude: 9, severity: 2, speed: null, direction: 180 }),
      stormCell({ cell_id: '3', latitude: 50, longitude: 10, severity: 1, speed: null, direction: null }),
      stormCell({ cell_id: '4', latitude: 50, longitude: 11, severity: 0, speed: 0.3, direction: 90 }),
    ]))
    const wrapper = await mountCells({ scan })
    expect(wrapper.findAll('[data-testid="map-cells-motion"]').map(motion => motion.text())).toEqual([
      'Moves at 30 km/h, direction not known',
      'Moves south, speed not known (direction calculated)',
      'Motion not known',
      'Almost stationary, under 1 km/h',
    ])
  })

  it('tells a cell with no severity so, not as a weak one', async () => {
    const wrapper = await mountCells({ scan: parseScan(stormCellsAnswer([stormCell({ cell_id: '9', latitude: 50, longitude: 8, severity: null })])) })
    expect(text(wrapper, 'map-cells-severity')).toBe('Severity not known')
    expect(wrapper.find('.map-cells-badge').text()).toBe('?')
  })

  it('explains the marks in a legend: the number is the severity, the dashed arrow the direction, calculated', async () => {
    const wrapper = await mountCells({ scan: parseScan(exampleScan()) })
    expect(wrapper.text()).toContain('the number is its severity, from 0 (weak) to 3 (extreme)')
    expect(wrapper.text()).toContain('Dashed arrow: direction of motion, calculated')
  })

  it('credits DWD where the layer is shown: the product, the credit line and the licence of the answer, as a link', async () => {
    const wrapper = await mountCells({ scan: parseScan(exampleScan()) })
    const credit = wrapper.find('[data-testid="map-cells-credit"]')
    expect(credit.text()).toContain('KONRAD3D radar product of the German Weather Service (DWD)')
    expect(credit.text()).toContain('Source: Deutscher Wetterdienst')
    const link = credit.find('a')
    expect(link.text()).toBe('Creative Commons Attribution 4.0 International')
    expect(link.attributes('href')).toBe('https://creativecommons.org/licenses/by/4.0/')
  })

  it('lists the ten most severe of a long scan, and shows the rest on a press that says how many there are and whether the list is open', async () => {
    const scan = parseScan(stormCellsAnswer(Array.from({ length: 25 }, (_, index) => stormCell({ cell_id: String(index + 1), latitude: 50, longitude: 8, severity: index % 4 }))))
    const wrapper = await mountCells({ scan })
    expect(text(wrapper, 'map-cells-summary')).toBe('Thunderstorm cells in the latest scan: 25')
    expect(wrapper.findAll('[data-testid="map-cells-item"]')).toHaveLength(10)
    // the most severe first: the extreme ones are all there
    expect(wrapper.findAll('[data-testid="map-cells-severity"]').every(item => /extreme|severe/.test(item.text()))).toBe(true)
    const more = wrapper.find('[data-testid="map-cells-more"]')
    expect(more.text()).toBe('Show all 25 cells')
    expect(more.attributes('aria-expanded')).toBe('false')
    expect(more.attributes('aria-controls')).toBe('map-cells-list')
    await more.trigger('click')
    expect(wrapper.findAll('[data-testid="map-cells-item"]')).toHaveLength(25)
    expect(wrapper.find('[data-testid="map-cells-more"]').text()).toBe('Show fewer cells')
    expect(wrapper.find('[data-testid="map-cells-more"]').attributes('aria-expanded')).toBe('true')
    await wrapper.find('[data-testid="map-cells-more"]').trigger('click')
    expect(wrapper.findAll('[data-testid="map-cells-item"]')).toHaveLength(10)
  })

  it('has no such press for a short list', async () => {
    const wrapper = await mountCells({ scan: parseScan(exampleScan()) })
    expect(wrapper.find('[data-testid="map-cells-more"]').exists()).toBe(false)
  })

  it('credits DWD for an empty scan as well', async () => {
    const wrapper = await mountCells({ scan: parseScan(emptyScan()) })
    expect(text(wrapper, 'map-cells-credit')).toContain('Source: Deutscher Wetterdienst')
  })
})

describe('while the scan comes, and when it does not', () => {
  it('says that it is loading, with the layer\'s name as the heading', async () => {
    const wrapper = await mountCells({ status: 'pending' })
    expect(text(wrapper, 'map-cells-loading')).toBe('Loading thunderstorm cells …')
    expect(wrapper.find('h2').text()).toBe('Thunderstorm cells')
  })

  it('says that it failed, as an alert, and offers Retry, which raises `retry`', async () => {
    const wrapper = await mountCells({ status: 'error' })
    expect(wrapper.find('[data-testid="map-cells-failed"]').attributes('role')).toBe('alert')
    await wrapper.find('[data-testid="map-cells-retry"]').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('keeps the scan where a refresh failed, and says which scan it is from', async () => {
    const wrapper = await mountCells({ scan: parseScan(exampleScan()), refreshFailed: true })
    expect(text(wrapper, 'map-cells-refresh-failed')).toMatch(/could not be refreshed\. The scan shown is from .*22:15 UTC/)
    expect(wrapper.findAll('[data-testid="map-cells-item"]')).toHaveLength(4)
  })

  it('has one live line, the count, which carries no time: a scan that changes nothing is not announced again', async () => {
    const wrapper = await mountCells({ scan: parseScan(emptyScan('2026-11-17T22:20:00.000000+00:00')) })
    const live = wrapper.findAll('[role="status"]')
    expect(live).toHaveLength(1)
    expect(live[0]!.text()).not.toMatch(/\d\d:\d\d/)
    await wrapper.setProps({ scan: parseScan(emptyScan('2026-11-17T22:25:00.000000+00:00')) })
    expect(wrapper.find('[role="status"]').text()).toBe('No thunderstorm cells in the latest scan')
    expect(text(wrapper, 'map-cells-scan')).toContain('22:25 UTC')
  })
})
