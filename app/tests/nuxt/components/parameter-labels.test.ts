import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { clearNuxtData } from '#app'
import { ParameterSelection } from '#components'
import GlossaryPage from '~/pages/glossary.vue'

// Where the app names a parameter, a resolution or a dataset outside the data viewer, drawn in
// locales other than English with an id that has no short word for it. The label the app showed
// where one went round the glossary was the id prettified -- "Wind Direction Mean Last 10min" (GH-2865)
// -- which reads as English in every language. The viewer's own places are in
// components/DataViewer.test.ts, the lookup itself in composables/composables.test.ts.

const ids = { resolution: '10_minutes', dataset: 'urban_wind', parameter: 'wind_direction_mean_last_10min' }

// what each locale's glossary says of the ids above, spelled out rather than read from the
// glossary the page is held to
const names = {
  de: { resolution: 'Alle 10 Minuten', dataset: 'Stadtklima: Wind', parameter: 'Mittlere Windrichtung (letzte 10 min)' },
  fr: { resolution: 'Toutes les 10 minutes', dataset: 'Vent urbain', parameter: 'Direction moyenne du vent (10 dernières min)' },
  pl: { resolution: 'Co 10 minut', dataset: 'Wiatr miejski', parameter: 'Średni kierunek wiatru (ostatnie 10 min)' },
}
const locales = Object.keys(names) as (keyof typeof names)[]

// the id as the fallback writes it, and as the backend does: none may reach the page
const fallbacks = ['Wind Direction Mean Last 10min', 'Urban Wind', '10 Minutes', ids.parameter, ids.dataset, ids.resolution]

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

describe('parameterSelection names ids in the active locale', () => {
  const mounted: { unmount: () => void }[] = []

  beforeEach(() => {
    clearNuxtData()
  })

  afterEach(() => {
    for (const wrapper of mounted.splice(0))
      wrapper.unmount()
  })

  async function mountSelection() {
    const open = { name_short: 'DWD', country: 'Germany', kind: 'observation', url: 'https://opendata.dwd.de/', auth: false, configured: true, date_required: false }
    registerEndpoint('/api/coverage', (event) => {
      if (!getQuery(event).provider)
        return { dwd: { observation: open } }
      return {
        [ids.resolution]: {
          description: null,
          datasets: {
            [ids.dataset]: {
              description: null,
              parameters: [{ name: ids.parameter, name_original: 'dd', unit_type: 'angle', unit: 'degree', description: null }],
            },
          },
        },
      }
    })
    const wrapper = await mountSuspended(ParameterSelection, {
      props: { modelValue: { provider: 'dwd', network: 'observation', resolution: ids.resolution, dataset: ids.dataset, parameters: [ids.parameter] } },
    })
    mounted.push(wrapper)
    await vi.waitFor(() => expect((wrapper.vm as any).isInitializing).toBe(false), { timeout: 5000 })
    return wrapper
  }

  it.each(locales)('labels the resolution, dataset and parameter choices in %s', async (locale) => {
    await setLocale(locale)
    const wrapper = await mountSelection()
    const vm = wrapper.vm as any
    const n = names[locale]
    expect(vm.resolutionItems).toEqual([{ label: n.resolution, value: ids.resolution }])
    expect(vm.datasetItems).toEqual([{ label: n.dataset, value: ids.dataset }])
    expect(vm.paramItems.map((item: { label: string, value: string }) => [item.label, item.value])).toEqual([[n.parameter, ids.parameter]])
    // what the selects show of the choice made, which is the same label
    await vi.waitFor(() => expect(wrapper.text()).toContain(n.dataset))
    expect(wrapper.text()).toContain(n.resolution)
    expect(wrapper.text()).toContain(n.parameter)
    expect(fallbacks.filter(id => wrapper.text().includes(id))).toEqual([])
  })
})

describe('glossary page names ids in the active locale', () => {
  const entries = [{
    name: ids.parameter,
    unit_type: 'angle',
    unit: 'degree',
    unit_symbol: '°',
    description: 'Mean direction the wind blows from over the last 10 minutes.',
  }]
  registerEndpoint('/api/glossary', () => entries)

  it.each(locales)('labels the parameter in %s', async (locale) => {
    await setLocale(locale)
    const wrapper = await mountSuspended(GlossaryPage)
    await vi.waitFor(() => expect((wrapper.vm as any).pending).toBe(false), { timeout: 5000 })
    // the label is the entry's heading; the id stays beside it, for whoever needs the API's name
    expect(wrapper.text()).toContain(names[locale].parameter)
    expect(wrapper.text()).not.toContain('Wind Direction Mean Last 10min')
  })
})
