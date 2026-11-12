import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { UApp } from '#components'
import AppHeader from '~/components/AppHeader.vue'
import { useSettings } from '~/composables/useSettings'
import { useTabBar } from '~/composables/useTabBar'

// The header of the wide layout carries the tools as tabs (GH-3518) in the order the reader chose in the settings
// (GH-3936), the same list as the phone's bar and Menu; every other place that lists the tools keeps its own order.
// CSS shows the tabs from 64 rem, so they are in the markup at every width and this reads them from it.

const mounted: Array<{ unmount: () => void }> = []
async function mountHeader(route = '/') {
  // the header's tooltip and menus need the providers app.vue's <UApp> supplies
  const wrapper = await mountSuspended({ setup: () => () => h(UApp, null, { default: () => h(AppHeader) }) }, { route, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  useSettings().reset()
})

type Header = Awaited<ReturnType<typeof mountHeader>>
const tabs = (wrapper: Header) => wrapper.findAll('nav ul a.nav-tab').map(link => link.attributes('href'))

const DEFAULT = ['/meteogram', '/explorer', '/stripes', '/history', '/map']

describe('the tool tabs of the header', () => {
  it('are in the order of the tools until the reader chooses', async () => {
    expect(tabs(await mountHeader())).toEqual(DEFAULT)
  })

  it('follow the order the reader chose, all five of them, not only the first four', async () => {
    useTabBar().setOrder(['map', 'history', 'forecast', 'stripes', 'explorer'])
    const wrapper = await mountHeader()
    expect(tabs(wrapper)).toEqual(['/map', '/history', '/meteogram', '/stripes', '/explorer'])
    expect(wrapper.findAll('nav ul a.nav-tab .nav-label').map(label => label.text())).toEqual(['Map', 'History', 'Forecast', 'Climate stripes', 'Explorer'])
  })

  it('follow a change of the order while they are shown, and the reset', async () => {
    const { setOrder, resetOrder } = useTabBar()
    const wrapper = await mountHeader()
    setOrder(['stripes', 'map', 'explorer', 'forecast', 'history'])
    await vi.waitFor(() => expect(tabs(wrapper)).toEqual(['/stripes', '/map', '/explorer', '/meteogram', '/history']))
    resetOrder()
    await vi.waitFor(() => expect(tabs(wrapper)).toEqual(DEFAULT))
  })

  it('are the default for a stored list that is wrong, no error', async () => {
    useSettings().settings.value.tabBar = ['radar', 'map'] as string[]
    expect(tabs(await mountHeader())).toEqual(['/map', '/meteogram', '/explorer', '/stripes', '/history'])
  })

  it('mark the tool of the page one is on, wherever it stands', async () => {
    useTabBar().setOrder(['map', 'history', 'forecast', 'stripes', 'explorer'])
    const wrapper = await mountHeader('/history')
    expect(wrapper.findAll('nav ul a[aria-current="page"]').map(link => link.attributes('href'))).toEqual(['/history'])
  })
})
