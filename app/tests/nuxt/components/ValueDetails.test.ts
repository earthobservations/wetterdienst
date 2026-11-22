import type { DetailStation } from '~/utils/value-details'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import ValueDetails from '~/components/ValueDetails.vue'
import { valueDetails } from '~/utils/value-details'

// The value details' table (GH-4296): a row for each station of each parameter, a sum only for what adds up, the words and
// numbers in the language of the page, and the table readable by a screen reader

const hamburg = { id: '01975', name: 'Hamburg-Fuhlsbüttel' }
const munich = { id: '03379', name: 'München-Stadt' }

const parameters = [
  { resolution: 'daily', dataset: 'climate_summary', name: 'precipitation_amount', unit: 'mm', aggregation: 'sum' as const },
  { resolution: 'daily', dataset: 'climate_summary', name: 'temperature_air_mean_2m', unit: '°C', aggregation: 'mean' as const },
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

describe('valueDetails table', () => {
  it('has one row for each station of each parameter, and nothing else', async () => {
    const wrapper = await mountDetails()
    const groups = wrapper.findAll('[data-testid="value-details-group"]')
    expect(groups).toHaveLength(2)
    for (const group of groups)
      expect(group.findAll('tr')).toHaveLength(2)
    expect(groups[0]!.findAll('[data-testid="value-details-station"]').map(cell => cell.text())).toEqual(['Hamburg-Fuhlsbüttel, 01975', 'München-Stadt, 03379'])
    // the stations are not compared: no difference, no order sentence
    expect(wrapper.find('[data-testid="value-details-difference"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="value-details-order"]').exists()).toBe(false)
  })

  it('has the sum of the rain and none for a temperature, with its words for a screen reader', async () => {
    const wrapper = await mountDetails()
    const [rain, temperature] = wrapper.findAll('[data-testid="value-details-group"]')
    expect(rain!.findAll('[data-testid="value-details-row"]').map(row => row.get('[data-testid="value-details-sum"]').text())).toEqual(['22.50', '17.50'])
    const sums = temperature!.findAll('[data-testid="value-details-sum"]')
    expect(sums).toHaveLength(2)
    for (const sum of sums) {
      expect(sum.text()).toContain('no sum for this parameter')
      expect(sum.find('[aria-hidden="true"]').text()).toBe('—')
    }
  })

  it('says why there is no sum where the windows overlap, and says so below the table', async () => {
    const six = [{ resolution: 'hourly', dataset: 'data', name: 'precipitation_amount_last_6h', unit: 'mm', aggregation: 'sum' as const }]
    const rows = [{ station_id: '01975', dataset: 'data', parameter: 'precipitation_amount_last_6h', value: 1 }, { station_id: '01975', dataset: 'data', parameter: 'precipitation_amount_last_6h', value: 2 }]
    const wrapper = await mountDetails(valueDetails(rows, { split: true, stations: [hamburg], parameters: six }))
    const sum = wrapper.get('[data-testid="value-details-sum"]')
    expect(sum.text()).toContain('no sum: the windows of this parameter overlap')
    expect(sum.find('[aria-hidden="true"]').text()).toBe('—')
    expect(wrapper.get('[data-testid="value-details-sum-note"]').text()).toContain('windows overlap')
  })

  it('says the sums are for what adds up, below the table, where one is missing', async () => {
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

  it('has no station column for a point, one row for each parameter', async () => {
    const wrapper = await mountDetails(build(twoStations, [], false))
    expect(wrapper.findAll('thead th').map(th => th.text())).toEqual(['Dataset', 'Parameter', 'Unit', 'Count', 'Min', 'Max', 'Mean', 'Sum'])
    expect(wrapper.findAll('[data-testid="value-details-row"]')).toHaveLength(2)
  })

  it('has one station\'s rows with its name and id', async () => {
    const wrapper = await mountDetails(build(twoStations.filter(row => row.station_id === '01975'), [hamburg]))
    expect(wrapper.findAll('[data-testid="value-details-station"]').map(cell => cell.text())).toEqual(['Hamburg-Fuhlsbüttel, 01975', 'Hamburg-Fuhlsbüttel, 01975'])
  })

  it('names a station by its id where it has no name, and shows a missing value as a dash with its words', async () => {
    const wrapper = await mountDetails(build([reading('01975', 'precipitation_amount', 1), reading('03379', 'precipitation_amount', null)], [hamburg, { id: '03379', name: null }]))
    const rows = wrapper.findAll('[data-testid="value-details-row"]')
    expect(rows[1]!.get('[data-testid="value-details-station"]').text()).toBe('03379')
    expect(rows[1]!.text()).toContain('no value')
    expect(rows[1]!.get('[data-testid="value-details-sum"]').text()).toContain('no value')
  })

  describe('as a table a screen reader reads', () => {
    it('is a box that takes the focus, named once by its caption, with headers with their scope and a station as the header of its row', async () => {
      const wrapper = await mountDetails()
      const box = wrapper.get('[data-testid="value-details-scroll"]')
      expect(box.attributes('tabindex')).toBe('0')
      // the caption names the table; a second name on the box would be read twice
      expect(box.attributes('aria-label')).toBeUndefined()
      expect(box.attributes('role')).toBeUndefined()
      expect(wrapper.get('caption').text()).toBe('Values Details')
      expect(wrapper.findAll('thead th').every(th => th.attributes('scope') === 'col')).toBe(true)
      const group = wrapper.get('[data-testid="value-details-group"]')
      // the parameter heads its rows, each station its own
      expect(group.findAll('th').map(th => [th.attributes('scope'), th.attributes('rowspan') ?? null])).toEqual([['rowgroup', '2'], ['row', null], ['row', null]])
      expect(group.findAll('td').slice(0, 2).map(td => td.attributes('rowspan'))).toEqual(['2', '2'])
    })

    it('keeps a station\'s name and id apart for a screen reader, which reads the comma', async () => {
      const wrapper = await mountDetails()
      const cell = wrapper.get('[data-testid="value-details-station"]')
      const comma = cell.get('.sr-only')
      expect(comma.text()).toBe(',')
      // the id follows its name in the order of the page, not only below it on screen
      expect(cell.text()).toBe('Hamburg-Fuhlsbüttel, 01975')
    })

    it('has the parameter as the header of its row where there is one row for it', async () => {
      const wrapper = await mountDetails(build(twoStations, [], false))
      expect(wrapper.get('[data-testid="value-details-group"] th').attributes('scope')).toBe('row')
    })
  })
})

// what each locale's glossary says of the ids below, spelled out rather than read from the glossary the page is held to
const urban = [
  { resolution: '10_minutes', dataset: 'urban_wind', name: 'wind_direction_mean_last_10min', unit: '°', aggregation: 'mean' as const },
  { resolution: '10_minutes', dataset: 'urban_wind', name: 'wind_speed_mean_last_10min', unit: 'm/s', aggregation: 'mean' as const },
]
const urbanRows = ['wind_direction_mean_last_10min', 'wind_speed_mean_last_10min'].map(parameter => ({ station_id: '01048', resolution: '10_minutes', dataset: 'urban_wind', parameter, timestamp: '2020-01-01T00:00:00Z', value: 2.5 }))
const NAMES = {
  en: { dataset: 'Urban wind', direction: 'Mean wind direction (last 10 min)', speed: 'Mean wind speed (last 10 min)', noSum: 'no sum for this parameter', decimal: '2.50' },
  de: { dataset: 'Stadtklima: Wind', direction: 'Mittlere Windrichtung (letzte 10 min)', speed: 'Mittlere Windgeschwindigkeit (letzte 10 min)', noSum: 'keine Summe für diesen Parameter', decimal: '2,50' },
  fr: { dataset: 'Vent urbain', direction: 'Direction moyenne du vent (10 dernières min)', speed: 'Vitesse moyenne du vent (10 dernières min)', noSum: 'pas de somme pour ce paramètre', decimal: '2,50' },
  pl: { dataset: 'Wiatr miejski', direction: 'Średni kierunek wiatru (ostatnie 10 min)', speed: 'Średnia prędkość wiatru (ostatnie 10 min)', noSum: 'brak sumy dla tego parametru', decimal: '2,50' },
}

describe('valueDetails table in the language of the page', () => {
  it.each(Object.keys(NAMES) as (keyof typeof NAMES)[])('names the dataset and the parameters by the glossary\'s labels, and not by their ids, in %s', async (locale) => {
    await setLocale(locale)
    const n = NAMES[locale]
    const wrapper = await mountDetails(valueDetails(urbanRows, { split: true, stations: [{ id: '01048', name: null }], parameters: urban }))
    const groups = wrapper.findAll('[data-testid="value-details-group"]')
    // the parameter heads its group of rows, and the dataset is the cell before it (and, on a phone, a line under it)
    expect(groups.map(group => group.findAll('th')[0]!.text())).toEqual([`${n.direction} ${n.dataset}`, `${n.speed} ${n.dataset}`])
    expect(groups.map(group => group.findAll('td')[0]!.text())).toEqual([n.dataset, n.dataset])
    // the raw ids and their prettified forms are nowhere
    const text = wrapper.text()
    for (const id of ['wind_direction_mean_last_10min', 'wind_speed_mean_last_10min', 'urban_wind', 'Wind Direction Mean Last 10min', 'Urban Wind'])
      expect(text, id).not.toContain(id)
  })

  it('shows the raw ids where plain-language labels are off', async () => {
    const wrapper = await mountDetails(valueDetails(urbanRows, { split: true, stations: [{ id: '01048', name: null }], parameters: urban }))
    const { settings } = useSettings()
    settings.value = { ...settings.value, friendlyLabels: false }
    try {
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).toContain('wind_direction_mean_last_10min')
      expect(wrapper.text()).toContain('urban_wind')
    }
    finally {
      settings.value = { ...settings.value, friendlyLabels: true }
    }
  })

  it.each(Object.keys(NAMES) as (keyof typeof NAMES)[])('writes the numbers with the decimal separator and the missing sum in words of %s', async (locale) => {
    await setLocale(locale)
    const n = NAMES[locale]
    const wrapper = await mountDetails(valueDetails(urbanRows, { split: true, stations: [{ id: '01048', name: null }], parameters: urban }))
    const row = wrapper.get('[data-testid="value-details-row"]')
    // `toFixed` writes a point in every language: "2.50" where German, French and Polish read "2,50"
    expect(row.findAll('td').map(cell => cell.text())).toContain(n.decimal)
    expect(row.get('[data-testid="value-details-sum"]').text()).toContain(n.noSum)
  })

  it.each([
    ['de', { unit: 'Einheit', overlap: 'keine Summe: die Zeitfenster dieses Parameters überlappen sich' }],
    ['fr', { unit: 'Unité', overlap: 'pas de somme : les fenêtres de ce paramètre se chevauchent' }],
    ['pl', { unit: 'Jednostka', overlap: 'brak sumy: okna tego parametru nakładają się' }],
  ])('has the unit column and the reason of overlapping windows in %s', async (locale, words) => {
    await setLocale(locale)
    const six = [{ resolution: 'hourly', dataset: 'data', name: 'precipitation_amount_last_6h', unit: 'mm', aggregation: 'sum' as const }]
    const rows = [{ station_id: '01975', dataset: 'data', parameter: 'precipitation_amount_last_6h', value: 1 }]
    const wrapper = await mountDetails(valueDetails(rows, { split: true, stations: [hamburg], parameters: six }))
    expect(wrapper.findAll('thead th').map(th => th.text())).toContain(words.unit)
    expect(wrapper.get('[data-testid="value-details-sum"]').text()).toContain(words.overlap)
  })
})
