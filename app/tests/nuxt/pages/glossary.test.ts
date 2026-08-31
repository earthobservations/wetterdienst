import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { describe, expect, it, vi } from 'vitest'
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

// The page no longer awaits `/api/glossary` in setup -- awaiting suspended the whole route and
// made its own loading state unreachable -- so mountSuspended() returns while the request is still
// out. Every assertion here is about what the answer renders, so wait for it.
async function mountGlossary() {
  const wrapper = await mountSuspended(GlossaryPage)
  await vi.waitFor(() => expect((wrapper.vm as any).pending).toBe(false), { timeout: 5000 })
  return wrapper
}

describe('glossary Page', () => {
  it('renders the page', async () => {
    served = entries
    const wrapper = await mountGlossary()
    expect(wrapper.exists()).toBe(true)
  })

  it('displays the glossary heading', async () => {
    served = entries
    const wrapper = await mountGlossary()
    expect(wrapper.text()).toContain('Glossary')
  })

  it('shows each parameter with its description and unit', async () => {
    served = entries
    const wrapper = await mountGlossary()
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
    const wrapper = await mountGlossary()
    expect(wrapper.text()).toContain('2 of 2 parameters')
  })

  it('says so when nothing is returned', async () => {
    // `useFetch` caches by url, so the payload from the mounts above would be reused otherwise
    clearNuxtData()
    served = []
    const wrapper = await mountGlossary()
    expect(wrapper.text()).toContain('No parameter matches your search.')
  })

  it('lists parameters by their label, not by the raw id the api orders them by', async () => {
    clearNuxtData()
    // served in id order, which is the opposite of the label order: sunshine_duration labels as
    // "Sunshine duration" and temperature_air_mean_2m as "Mean air temperature (2 m)". Without the
    // sort the page would hand them back in the order received, so this fails.
    served = [...entries].reverse()
    expect(served.map(entry => entry.name)).toEqual(['sunshine_duration', 'temperature_air_mean_2m'])

    const wrapper = await mountGlossary()
    const shown = (wrapper.vm as any).entries.map((entry: { name: string }) => entry.name)
    expect(shown).toEqual(['temperature_air_mean_2m', 'sunshine_duration'])
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
    const wrapper = await mountGlossary()
    // the options live in a popover that is not rendered until the select opens, so what the select
    // is handed is what gets checked
    const labels = ((wrapper.vm as any).unitTypeItems as { label: string }[]).map(item => item.label)
    expect(labels).toContain('Energy per area')
    expect(labels).not.toContain('energy per area')
    expect(labels).toContain('Temperature')
  })
})
