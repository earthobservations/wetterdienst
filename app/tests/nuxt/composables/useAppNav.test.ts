import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'

// The places of the navigation (GH-3518): the order is the owner's, and the sidebar, the drawer and the command palette all
// read it from here.
async function groups() {
  const Probe = defineComponent({
    setup: () => useAppNav(),
    render: () => h('div'),
  })
  const wrapper = await mountSuspended(Probe)
  const found = (wrapper.vm as unknown as { groups: Array<{ key: string, items: Array<{ to?: string }> }> }).groups
  wrapper.unmount()
  return Object.fromEntries(found.map(group => [group.key, group.items.map(item => item.to)]))
}

describe('useAppNav', () => {
  it('ends the data group with the API', async () => {
    const { data } = await groups()

    expect(data).toEqual(['/explorer', '/meteogram', '/stripes', '/history', '/api'])
  })

  it('starts the reference group with the providers', async () => {
    const { reference } = await groups()

    expect(reference![0]).toBe('/providers')
    expect(reference).toEqual(['/providers', '/glossary', 'https://wetterdienst.readthedocs.io/'])
  })

  it('lists every place once', async () => {
    const all = Object.values(await groups()).flat()

    expect(new Set(all).size).toBe(all.length)
  })
})
