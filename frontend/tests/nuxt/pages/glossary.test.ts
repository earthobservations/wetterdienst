import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import { clearNuxtData } from '#app'
import GlossaryPage from '~/pages/glossary.vue'

// the page reads the vocabulary through `useFetch`, which goes via `$fetch` rather than the global
// one, so the endpoint is registered instead of the fetch being stubbed
const entries = [
  {
    name: 'temperature_air_mean_2m',
    unit_type: 'temperature',
    unit: 'degree_celsius',
    unit_symbol: '°C',
    description: 'Temperature of the air two metres above the ground.',
  },
  {
    name: 'sunshine_duration',
    unit_type: 'time',
    unit: 'second',
    unit_symbol: 's',
    description: 'Length of time the sun shone unobstructed.',
  },
]

// registered once: re-registering the same path in a later test does not replace the handler
let served: typeof entries = entries
registerEndpoint('/api/glossary', () => served)

describe('glossary Page', () => {
  it('renders the page', async () => {
    served = entries
    const wrapper = await mountSuspended(GlossaryPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays the glossary heading', async () => {
    served = entries
    const wrapper = await mountSuspended(GlossaryPage)
    expect(wrapper.text()).toContain('Glossary')
  })

  it('shows each parameter with its description and unit', async () => {
    served = entries
    const wrapper = await mountSuspended(GlossaryPage)
    const text = wrapper.text()

    // the description is what the page exists for -- it comes from the backend, per parameter
    expect(text).toContain('Temperature of the air two metres above the ground.')
    expect(text).toContain('Length of time the sun shone unobstructed.')
    expect(text).toContain('°C')
    // the raw id stays visible, since that is what a request has to name
    expect(text).toContain('temperature_air_mean_2m')
  })

  it('reports how much of the vocabulary is shown', async () => {
    served = entries
    const wrapper = await mountSuspended(GlossaryPage)
    expect(wrapper.text()).toContain('2 of 2 parameters')
  })

  it('says so when nothing is returned', async () => {
    // `useFetch` caches by url, so the payload from the mounts above would be reused otherwise
    clearNuxtData()
    served = []
    const wrapper = await mountSuspended(GlossaryPage)
    expect(wrapper.text()).toContain('No parameter matches your search.')
  })

  // last, because it serves a third entry and the `useFetch` cache is shared across these mounts
  it('names the quantity filter in the ui language, not the backend id', async () => {
    // the options were built with `type.replace(/_/g, ' ')`, so every locale read the raw english
    // id -- "energy per area", "wind scale" -- while translations for them already existed
    clearNuxtData()
    served = [...entries, {
      name: 'radiation_global',
      unit_type: 'energy_per_area',
      unit: 'joule_per_square_centimeter',
      unit_symbol: 'J/cm²',
      description: 'Global radiation.',
    }]
    const wrapper = await mountSuspended(GlossaryPage)
    // the options live in a popover that is not rendered until the select opens, so what the select
    // is handed is what gets checked
    const labels = ((wrapper.vm as any).unitTypeItems as { label: string }[]).map(item => item.label)
    expect(labels).toContain('Energy per area')
    expect(labels).not.toContain('energy per area')
    expect(labels).toContain('Temperature')
  })
})
