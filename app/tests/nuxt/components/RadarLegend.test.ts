import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it } from 'vitest'
import RadarLegend from '~/components/RadarLegend.vue'
import { parseLoop } from '~/utils/radar'
import { radarAnswer } from '../../helpers/radar-answer'

// The legend of the radar's colours (GH-3788): the rates in mm/h as numbers beside the swatches, from the classes of the answer, in the
// language of the page, so that the colours are never the only way to read them.

const LEGEND = parseLoop(radarAnswer()).legend

const mounted: Array<{ unmount: () => void }> = []
async function mountLegend() {
  const wrapper = await mountSuspended(RadarLegend, { props: { legend: LEGEND }, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
afterEach(() => mounted.splice(0).forEach(wrapper => wrapper.unmount()))

describe('the legend', () => {
  it('is a section named by its heading, which says the unit', async () => {
    const wrapper = await mountLegend()
    const section = wrapper.find('[data-testid="radar-legend"]')
    expect(section.element.tagName).toBe('SECTION')
    expect(wrapper.find(`#${section.attributes('aria-labelledby')}`).text()).toBe('Precipitation rate in mm/h')
  })

  it('has a class for each of the answer\'s seven, lightest first, with its colour and its numbers', async () => {
    const wrapper = await mountLegend()
    const items = wrapper.findAll('[data-testid="radar-legend-class"]')
    expect(items).toHaveLength(7)
    expect(items.map(item => item.find('[aria-hidden="true"]:not(.radar-legend-swatch)').text())).toEqual(['0.1–0.5', '0.5–1', '1–2.5', '2.5–5', '5–10', '10–25', '25+'])
    // the swatches are the answer's colours
    expect(items.map(item => (item.find('.radar-legend-swatch').element as HTMLElement).style.background)).toEqual(LEGEND.classes.map(entry => entry.color))
  })

  it('says each class as a sentence for a screen reader, and keeps the swatch out of what it reads', async () => {
    const wrapper = await mountLegend()
    const items = wrapper.findAll('[data-testid="radar-legend-class"]')
    expect(items.map(item => item.find('.sr-only').text())).toEqual([
      '0.1 to under 0.5 mm/h',
      '0.5 to under 1 mm/h',
      '1 to under 2.5 mm/h',
      '2.5 to under 5 mm/h',
      '5 to under 10 mm/h',
      '10 to under 25 mm/h',
      '25 mm/h and more',
    ])
    for (const item of items)
      expect(item.find('.radar-legend-swatch').attributes('aria-hidden')).toBe('true')
  })

  it('says what no colour is: under the first class, or no data', async () => {
    const wrapper = await mountLegend()
    expect(wrapper.find('[data-testid="radar-legend-none"]').text()).toBe('No colour: under 0.1 mm/h, or no data')
  })
})
