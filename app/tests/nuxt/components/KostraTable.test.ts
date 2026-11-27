import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useNuxtApp } from '#imports'
import KostraTable from '~/components/KostraTable.vue'
import { KOSTRA_DURATIONS, parseKostra } from '~/utils/kostra'
import { depthOf, kostraAnswer } from '../../helpers/kostra-answer'

// The table of the Heavy-rainfall tool (GH-4500): 22 durations down, 9 return periods across, the depth or the intensity in each cell
// and DWD's uncertainty under it.

const table = parseKostra(kostraAnswer())!
const mounted: Array<{ unmount: () => void }> = []

async function mountTable(props: Record<string, unknown> = {}) {
  const wrapper = await mountSuspended(KostraTable, { props: { table, quantity: 'depth', ...props }, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
const rowOf = (wrapper: Awaited<ReturnType<typeof mountTable>>, minutes: number) => wrapper.find(`tr[data-minutes="${minutes}"]`)
const cellOf = (wrapper: Awaited<ReturnType<typeof mountTable>>, minutes: number, years: number) => rowOf(wrapper, minutes).find(`td[data-years="${years}"]`)

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
})

describe('the table', () => {
  it('has a row for each of the 22 durations, labelled in min, h and d, and a column for each of the 9 return periods', async () => {
    const wrapper = await mountTable()
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(22)
    expect(rows.map(row => row.find('th').text())).toEqual(['5 min', '10 min', '15 min', '20 min', '30 min', '45 min', '1 h', '90 min', '2 h', '3 h', '4 h', '6 h', '9 h', '12 h', '18 h', '1 d', '2 d', '3 d', '4 d', '5 d', '6 d', '7 d'])
    expect(rows.every(row => row.findAll('td').length === 9)).toBe(true)
    expect(wrapper.findAll('thead th[data-years]').map(head => head.attributes('data-years'))).toEqual(['1', '2', '3', '5', '10', '20', '30', '50', '100'])
  })

  it('shows the depth of each cell in mm, to a tenth, and DWD\'s uncertainty under it', async () => {
    const wrapper = await mountTable()
    const cell = cellOf(wrapper, 60, 100)
    expect(cell.find('.kostra-value').text()).toBe(depthOf(60, 100).toFixed(1))
    expect(cell.find('.kostra-uncertainty').text()).toContain('±12 %')
    // the first value of the table, in the corner
    expect(cellOf(wrapper, 5, 1).find('.kostra-value').text()).toBe(depthOf(5, 1).toFixed(1))
    expect(wrapper.find('.kostra-corner-unit').text()).toBe('mm')
  })

  it('shows the intensity in l/(s·ha) when that is the quantity, with the same uncertainty', async () => {
    const wrapper = await mountTable({ quantity: 'intensity' })
    const entry = table.rows[KOSTRA_DURATIONS.indexOf(60)]![8]!
    const cell = cellOf(wrapper, 60, 100)
    expect(cell.find('.kostra-value').text()).toBe(entry.intensity!.toFixed(1))
    expect(cell.find('.kostra-value').text()).not.toBe(entry.depthMm!.toFixed(1))
    expect(cell.find('.kostra-uncertainty').text()).toContain('±12 %')
    expect(wrapper.find('.kostra-corner-unit').text()).toBe('l/(s·ha)')
    expect(wrapper.find('caption').text()).toContain('Intensity in l/(s·ha)')
  })

  it('changes its numbers when the quantity changes, not its rows', async () => {
    const wrapper = await mountTable()
    const before = wrapper.find('tbody').text()
    await wrapper.setProps({ quantity: 'intensity' })
    expect(wrapper.find('tbody').text()).not.toBe(before)
    expect(wrapper.findAll('tbody tr')).toHaveLength(22)
  })

  it('says no value where DWD gives none, in words for a screen reader, and shows no uncertainty there', async () => {
    const gappy = parseKostra(kostraAnswer({ missing: [[60, 100]] }))!
    const wrapper = await mountTable({ table: gappy })
    const cell = cellOf(wrapper, 60, 100)
    expect(cell.find('.kostra-none').exists()).toBe(true)
    expect(cell.find('.kostra-none [aria-hidden="true"]').text()).toBe('–')
    expect(cell.find('.sr-only').text()).toBe('no value')
    expect(cell.find('.kostra-uncertainty').exists()).toBe(false)
    expect(cellOf(wrapper, 60, 50).find('.kostra-value').exists()).toBe(true)
  })

  it('is a table a screen reader can read: a caption, column headings with their years, row headings with their durations', async () => {
    const wrapper = await mountTable()
    expect(wrapper.find('caption').text()).toBe('Depth in mm: 22 durations of a rain by 9 return periods')
    const heading = wrapper.find('thead th[data-years="100"]')
    expect(heading.attributes('scope')).toBe('col')
    expect(heading.find('.sr-only').text()).toBe('100 years')
    expect(wrapper.find('thead th[data-years="1"] .sr-only').text()).toBe('1 year')
    expect(wrapper.find('tbody tr th').attributes('scope')).toBe('row')
    // the uncertainty is named for a screen reader before its number
    expect(cellOf(wrapper, 5, 1).find('.kostra-uncertainty .sr-only').text()).toBe('uncertainty')
  })

  it('scrolls sideways in a box of its own that the keyboard can reach, and is named', async () => {
    const wrapper = await mountTable()
    const box = wrapper.find('[data-testid="kostra-table-scroll"]')
    expect(box.attributes('tabindex')).toBe('0')
    expect(box.attributes('role')).toBe('region')
    expect(box.attributes('aria-label')).toBe('Design rainfall table; scrolls sideways')
    // the durations stay at the edge while it scrolls
    expect(wrapper.find('tbody th').classes()).toContain('kostra-duration')
  })

  it('writes the numbers in the language of the page: a decimal comma in German', async () => {
    const wrapper = await mountTable()
    const { $i18n } = useNuxtApp()
    await $i18n.setLocale('de')
    try {
      await vi.waitFor(() => expect(cellOf(wrapper, 60, 100).find('.kostra-value').text()).toBe(depthOf(60, 100).toFixed(1).replace('.', ',')))
      expect(wrapper.find('tbody tr th').text()).toBe('5 min')
      expect(wrapper.find('caption').text()).toContain('Regenhöhe in mm')
    }
    finally {
      await $i18n.setLocale('en')
    }
  })
})
