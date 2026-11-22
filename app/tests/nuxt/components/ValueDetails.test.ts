import type { DetailStation } from '~/utils/value-details'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import ValueDetails from '~/components/ValueDetails.vue'
import { valueDetails } from '~/utils/value-details'

// The value details' table (GH-4296): a row for each station of each parameter, the difference of two stations under them,
// a sum only for what adds up, the words and numbers in the language of the page, and the table readable by a screen reader

const hamburg = { id: '01975', name: 'Hamburg-Fuhlsbüttel' }
const munich = { id: '03379', name: 'München-Stadt' }

const parameters = [
  { dataset: 'climate_summary', name: 'precipitation_amount', unit: 'mm', aggregation: 'sum' as const },
  { dataset: 'climate_summary', name: 'temperature_air_mean_2m', unit: '°C', aggregation: 'mean' as const },
]

function reading(station_id: string, parameter: string, value: number | null) {
  return { station_id, resolution: 'daily', dataset: 'climate_summary', parameter, timestamp: '2025-01-01T00:00:00Z', value }
}

const twoStations = [
  reading('01975', 'precipitation_amount', 10),
  reading('01975', 'precipitation_amount', 12.5),
  reading('03379', 'precipitation_amount', 8),
  reading('03379', 'precipitation_amount', 9.5),
  reading('01975', 'temperature_air_mean_2m', 10),
  reading('03379', 'temperature_air_mean_2m', 12),
]

function build(rows: object[], stations: DetailStation[] = [hamburg, munich], split = true) {
  return valueDetails(rows, { split, stations, parameters })
}

async function mountDetails(details = build(twoStations)) {
  return mountSuspended(ValueDetails, { props: { details }, attachTo: document.body })
}

async function setLocale(locale: string) {
  const harness = await mountSuspended(defineComponent({
    setup: () => ({ setLocale: useI18n().setLocale }),
    render: () => h('div'),
  }))
  await (harness.vm as unknown as { setLocale: (locale: string) => Promise<void> }).setLocale(locale)
  harness.unmount()
}

afterEach(async () => {
  await setLocale('en')
})

const cells = (row: { findAll: (selector: string) => { text: () => string }[] }) => row.findAll('th, td').map(cell => cell.text())

describe('valueDetails table', () => {
  it('has one row for each station of each parameter, and the difference of two under them', async () => {
    const wrapper = await mountDetails()
    const groups = wrapper.findAll('[data-testid="value-details-group"]')
    expect(groups).toHaveLength(2)
    for (const group of groups)
      expect(group.findAll('tr')).toHaveLength(3)
    const [rain] = groups
    expect(rain!.findAll('[data-testid="value-details-station"]').map(cell => cell.text())).toEqual(['1.Hamburg-Fuhlsbüttel01975', '2.München-Stadt03379'])
    expect(rain!.find('[data-testid="value-details-difference"]').exists()).toBe(true)
  })

  it('says which station is the first and which the second, and what the difference is', async () => {
    const wrapper = await mountDetails()
    const order = wrapper.get('[data-testid="value-details-order"]').text()
    expect(order).toContain('first Hamburg-Fuhlsbüttel (01975)')
    expect(order).toContain('second München-Stadt (03379)')
    expect(order).toContain('second station less the first')
  })

  it('writes the difference of a sum with its sign and as a share of the first, and has no sum for a temperature', async () => {
    const wrapper = await mountDetails()
    const [rain, temperature] = wrapper.findAll('[data-testid="value-details-group"]')
    // 22.5 mm first, 17.5 mm second
    expect(rain!.get('[data-testid="value-details-difference"] [data-testid="value-details-sum"]').text()).toMatch(/^[-−]5\.00\s*\([-−]22\.2%\)$/)
    expect(rain!.findAll('[data-testid="value-details-row"]').map(row => row.get('[data-testid="value-details-sum"]').text())).toEqual(['22.50', '17.50'])
    const sums = temperature!.findAll('[data-testid="value-details-sum"]')
    expect(sums).toHaveLength(3)
    for (const sum of sums) {
      expect(sum.text()).toContain('no sum for this parameter')
      expect(sum.find('[aria-hidden="true"]').text()).toBe('—')
    }
    // the mean's difference is a rise, signed
    expect(cells(temperature!.get('[data-testid="value-details-difference"]'))).toEqual(['Difference (2 − 1)', '', '+2.00', '+2.00', '+2.00', expect.stringContaining('no sum')])
  })

  it('says the sums are for what adds up, below the table', async () => {
    const wrapper = await mountDetails()
    expect(wrapper.get('[data-testid="value-details-sum-note"]').text()).toContain('only for parameters that are amounts per interval')
    const onlyRain = await mountDetails(build(twoStations.slice(0, 4)))
    expect(onlyRain.find('[data-testid="value-details-sum-note"]').exists()).toBe(false)
  })

  it('has the unit of each parameter in a column of its own', async () => {
    const wrapper = await mountDetails()
    expect(wrapper.findAll('thead th').map(th => th.text())).toEqual(['Dataset', 'Parameter', 'Unit', 'Station', 'Count', 'Min', 'Max', 'Mean', 'Sum'])
    const groups = wrapper.findAll('[data-testid="value-details-group"]')
    expect(groups.map(group => group.findAll('td')[1]!.text())).toEqual(['mm', '°C'])
  })

  it('has no unit column where the answer names no unit', async () => {
    const wrapper = await mountDetails(valueDetails(twoStations, { split: true, stations: [hamburg, munich], parameters: [] }))
    expect(wrapper.findAll('thead th').map(th => th.text())).not.toContain('Unit')
  })

  it('has no station column and no difference for a point, one row for each parameter', async () => {
    const wrapper = await mountDetails(build(twoStations, [], false))
    expect(wrapper.findAll('thead th').map(th => th.text())).toEqual(['Dataset', 'Parameter', 'Unit', 'Count', 'Min', 'Max', 'Mean', 'Sum'])
    expect(wrapper.findAll('[data-testid="value-details-row"]')).toHaveLength(2)
    expect(wrapper.find('[data-testid="value-details-difference"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="value-details-order"]').exists()).toBe(false)
  })

  it('has one station\'s rows with its name and id and no order or difference', async () => {
    const wrapper = await mountDetails(build(twoStations.filter(row => row.station_id === '01975'), [hamburg]))
    expect(wrapper.findAll('[data-testid="value-details-station"]').map(cell => cell.text())).toEqual(['Hamburg-Fuhlsbüttel01975', 'Hamburg-Fuhlsbüttel01975'])
    expect(wrapper.find('[data-testid="value-details-order"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="value-details-difference"]').exists()).toBe(false)
  })

  it('names a station by its id where it has no name, and shows a missing value as a dash with its words', async () => {
    const wrapper = await mountDetails(build([reading('01975', 'precipitation_amount', 1), reading('03379', 'precipitation_amount', null)], [hamburg, { id: '03379', name: null }]))
    const rows = wrapper.findAll('[data-testid="value-details-row"]')
    expect(rows[1]!.get('[data-testid="value-details-station"]').text()).toContain('2.03379')
    expect(rows[1]!.text()).toContain('no value')
    expect(cells(wrapper.get('[data-testid="value-details-difference"]'))).toEqual(['Difference (2 − 1)', '', expect.stringContaining('no value'), expect.stringContaining('no value'), expect.stringContaining('no value'), expect.stringContaining('no value')])
  })

  describe('as a table a screen reader reads', () => {
    it('is a named region that takes the focus, with a caption, headers with their scope and a station as the header of its row', async () => {
      const wrapper = await mountDetails()
      const region = wrapper.get('[role="region"]')
      expect(region.attributes('tabindex')).toBe('0')
      expect(region.attributes('aria-label')).toBe('Values Details')
      expect(wrapper.get('caption').text()).toBe('Values Details')
      expect(wrapper.findAll('thead th').every(th => th.attributes('scope') === 'col')).toBe(true)
      const group = wrapper.get('[data-testid="value-details-group"]')
      // the parameter heads its rows, the station its own, as the difference does
      expect(group.findAll('th').map(th => [th.attributes('scope'), th.attributes('rowspan') ?? null])).toEqual([['rowgroup', '3'], ['row', null], ['row', null], ['row', null]])
      expect(group.findAll('td').slice(0, 2).map(td => td.attributes('rowspan'))).toEqual(['3', '3'])
    })

    it('has the parameter as the header of its row where there is one row for it', async () => {
      const wrapper = await mountDetails(build(twoStations, [], false))
      expect(wrapper.get('[data-testid="value-details-group"] th').attributes('scope')).toBe('row')
    })

    it('says the difference by its sign in the text, not by colour: no colour class of a rise or a fall', async () => {
      const wrapper = await mountDetails()
      const row = wrapper.get('[data-testid="value-details-difference"]')
      expect(row.html()).not.toMatch(/text-(red|green|blue|emerald|rose|sky)-/)
      expect(row.text()).toMatch(/[+−-]/)
    })
  })
})

describe('valueDetails table in the language of the page', () => {
  it.each([
    ['de', { first: 'erste Hamburg-Fuhlsbüttel (01975)', difference: 'Differenz (2 − 1)', unit: 'Einheit', noSum: 'keine Summe' }],
    ['fr', { first: 'première Hamburg-Fuhlsbüttel (01975)', difference: 'Différence (2 − 1)', unit: 'Unité', noSum: 'pas de somme' }],
    ['pl', { first: 'pierwsza Hamburg-Fuhlsbüttel (01975)', difference: 'Różnica (2 − 1)', unit: 'Jednostka', noSum: 'brak sumy' }],
  ])('names the stations, the difference and the missing sum in %s', async (locale, words) => {
    await setLocale(locale)
    const wrapper = await mountDetails()
    expect(wrapper.get('[data-testid="value-details-order"]').text()).toContain(words.first)
    expect(wrapper.get('[data-testid="value-details-difference"] th').text()).toBe(words.difference)
    expect(wrapper.findAll('thead th').map(th => th.text())).toContain(words.unit)
    expect(wrapper.text()).toContain(words.noSum)
  })

  it.each([
    // the percent sign is spaced as the language spaces it: "-22,2 %" in German and French, "-22,2%" in Polish
    ['de', ['22,50', '17,50'], /^[-−]5,00\s*\([-−]22,2\s?%\)$/],
    ['fr', ['22,50', '17,50'], /^[-−]5,00\s*\([-−]22,2\s?%\)$/],
    ['pl', ['22,50', '17,50'], /^[-−]5,00\s*\([-−]22,2\s?%\)$/],
  ])('writes the numbers with the decimal separator of %s, the share with its percent sign', async (locale, sums, difference) => {
    await setLocale(locale)
    const wrapper = await mountDetails()
    const rain = wrapper.get('[data-testid="value-details-group"]')
    expect(rain.findAll('[data-testid="value-details-row"]').map(row => row.get('[data-testid="value-details-sum"]').text())).toEqual(sums)
    expect(rain.get('[data-testid="value-details-difference"] [data-testid="value-details-sum"]').text().replace(/[\xA0\u202F]/g, ' ')).toMatch(difference)
  })
})
