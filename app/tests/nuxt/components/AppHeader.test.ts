import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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

const DEFAULT = ['/meteogram', '/explorer', '/stripes', '/radar', '/history', '/map', '/kostra']

describe('the tool tabs of the header', () => {
  it('are in the order of the tools until the reader chooses', async () => {
    expect(tabs(await mountHeader())).toEqual(DEFAULT)
  })

  it('follow the order the reader chose, all seven of them, not only the first four', async () => {
    useTabBar().setOrder(['map', 'history', 'radar', 'forecast', 'stripes', 'explorer', 'kostra'])
    const wrapper = await mountHeader()
    expect(tabs(wrapper)).toEqual(['/map', '/history', '/radar', '/meteogram', '/stripes', '/explorer', '/kostra'])
    expect(wrapper.findAll('nav ul a.nav-tab .nav-label').map(label => label.text())).toEqual(['Map', 'History', 'Radar', 'Forecast', 'Climate stripes', 'Explorer', 'Heavy rainfall'])
  })

  it('follow a change of the order while they are shown, and the reset', async () => {
    const { setOrder, resetOrder } = useTabBar()
    const wrapper = await mountHeader()
    setOrder(['stripes', 'history', 'explorer', 'forecast', 'radar', 'map', 'kostra'])
    await vi.waitFor(() => expect(tabs(wrapper)).toEqual(['/stripes', '/history', '/explorer', '/meteogram', '/radar', '/map', '/kostra']))
    resetOrder()
    await vi.waitFor(() => expect(tabs(wrapper)).toEqual(DEFAULT))
  })

  it('are the default for a stored list that is wrong, no error', async () => {
    useSettings().settings.value.tabBar = ['satellite', 'history'] as string[]
    expect(tabs(await mountHeader())).toEqual(['/history', '/meteogram', '/explorer', '/stripes', '/radar', '/map', '/kostra'])
  })

  it('mark the tool of the page one is on, wherever it stands', async () => {
    useTabBar().setOrder(['history', 'radar', 'forecast', 'stripes', 'explorer'])
    const wrapper = await mountHeader('/radar')
    expect(wrapper.findAll('nav ul a[aria-current="page"]').map(link => link.attributes('href'))).toEqual(['/radar'])
  })
})

// The tabs that do not fit go into the "More" menu (GH-4500). The test's document has no layout, so the widths are given: a tab is 100 px, the
// rest of the row (the line and the reference) 150 px, the "More" button 60 px, with no gap, and the room is what a test sets.
describe('the tabs that do not fit', () => {
  const original = HTMLElement.prototype.getBoundingClientRect
  let room = 10_000
  function stubWidths() {
    HTMLElement.prototype.getBoundingClientRect = function (this: HTMLElement) {
      const measure = this.dataset?.measure
      const width = this.matches?.('nav.app-nav')
        ? room
        : measure === 'tab' ? 100 : measure === 'list' ? 700 : measure === 'row' ? 850 : measure === 'more' ? 60 : 0
      return { width, height: 0, top: 0, left: 0, right: width, bottom: 0, x: 0, y: 0, toJSON: () => ({}) } as DOMRect
    }
  }
  afterEach(() => {
    HTMLElement.prototype.getBoundingClientRect = original
    room = 10_000
  })

  const more = (wrapper: Header) => wrapper.find('[data-testid="nav-more-button"]')
  const inMore = async (wrapper: Header) => {
    await more(wrapper).trigger('click')
    return wrapper.findAll('[data-testid="nav-more-panel"] li').map(item => item.attributes('data-tool'))
  }

  it('are all in the row, with no More button, where the room holds them', async () => {
    stubWidths()
    room = 850
    const wrapper = await mountHeader()
    expect(tabs(wrapper)).toEqual(DEFAULT)
    expect(more(wrapper).exists()).toBe(false)
  })

  it('go from the end into the More menu, which is after the last tab that stays, and each is a link in it', async () => {
    stubWidths()
    // seven tabs miss by a pixel: five are left with the button, which is 60 px for the two tabs that go
    room = 849
    const wrapper = await mountHeader()
    expect(tabs(wrapper)).toEqual(DEFAULT.slice(0, 6))
    expect(more(wrapper).exists()).toBe(true)
    room = 800
    const narrower = await mountHeader()
    expect(tabs(narrower)).toEqual(DEFAULT.slice(0, 5))
    expect(await inMore(narrower)).toEqual(['map', 'kostra'])
    expect(narrower.findAll('[data-testid="nav-more-panel"] a').map(link => link.attributes('href'))).toEqual(['/map', '/kostra'])
  })

  it('keep every tool one click away, whatever the room: the tabs and the menu are the seven, in the order the reader chose', async () => {
    stubWidths()
    useTabBar().setOrder(['kostra', 'history', 'map', 'forecast', 'explorer', 'stripes', 'radar'])
    for (const width of [850, 700, 600, 400, 200, 0]) {
      room = width
      const wrapper = await mountHeader()
      const kept = tabs(wrapper)
      const menu = more(wrapper).exists() ? await inMore(wrapper) : []
      expect(kept.length + menu.length, `${width} px`).toBe(7)
      expect([...kept, ...menu.map(key => `/${key === 'forecast' ? 'meteogram' : key}`)], `${width} px`).toEqual(['/kostra', '/history', '/map', '/meteogram', '/explorer', '/stripes', '/radar'])
      wrapper.unmount()
      mounted.pop()
    }
  })

  it('mark the More button as the tab of the page is marked where the page is a tool that is in it, and only then', async () => {
    stubWidths()
    room = 800
    const inside = await mountHeader('/kostra')
    expect(more(inside).attributes('data-current')).toBeDefined()
    // the tabs that are in the row are not marked: the page is not theirs
    expect(inside.findAll('nav ul a[aria-current="page"]')).toHaveLength(0)
    const outside = await mountHeader('/radar')
    expect(more(outside).attributes('data-current')).toBeUndefined()
    expect(outside.findAll('nav ul a[aria-current="page"]').map(link => link.attributes('href'))).toEqual(['/radar'])
  })

  it('marks the tool of the page in the menu too, with the same marking as the tabs\' links', async () => {
    stubWidths()
    room = 800
    const wrapper = await mountHeader('/kostra')
    await more(wrapper).trigger('click')
    expect(wrapper.find('[data-testid="nav-more-panel"] a[href="/kostra"]').attributes('aria-current')).toBe('page')
    expect(wrapper.find('[data-testid="nav-more-panel"] a[href="/map"]').attributes('aria-current')).toBeUndefined()
  })

  // the focus is not lost where a resize makes every tab fit while the More menu is open (GH-4500): it goes to the tab that takes the place. The test's
  // document has no resize observer, so one is given that a test can tell the window has been resized.
  describe('and the focus', () => {
    const resizes: Array<() => void> = []
    const resize = (width: number) => {
      room = width
      resizes.forEach(call => call())
    }
    beforeEach(() => {
      resizes.length = 0
      vi.stubGlobal('ResizeObserver', class {
        constructor(callback: () => void) {
          resizes.push(callback)
        }

        observe() {}
        unobserve() {}
        disconnect() {}
      })
    })
    afterEach(() => {
      vi.unstubAllGlobals()
    })

    it('goes to the tab that takes the place of the More button, where every tab fits after a resize', async () => {
      stubWidths()
      room = 800
      const wrapper = await mountHeader()
      ;(more(wrapper).element as HTMLElement).focus()
      expect(document.activeElement).toBe(more(wrapper).element)
      resize(10_000)
      await vi.waitFor(() => expect(more(wrapper).exists()).toBe(false))
      // the first tool that was in the menu is the one the button gave its place to
      await vi.waitFor(() => expect((document.activeElement as HTMLElement | null)?.getAttribute('href')).toBe('/map'))
      expect(wrapper.find('nav ul').element.contains(document.activeElement)).toBe(true)
    })

    it('goes to the tab of the item it was on, where that tool now fits', async () => {
      stubWidths()
      room = 800
      const wrapper = await mountHeader()
      await more(wrapper).trigger('click')
      ;(wrapper.find('[data-testid="nav-more-panel"] a[href="/kostra"]').element as HTMLElement).focus()
      // six tabs and the button: the map is a tab now, the heavy rainfall is still in the menu
      resize(820)
      await vi.waitFor(() => expect(wrapper.findAll('nav ul a.nav-tab')).toHaveLength(6))
      // the item the focus was on is still in the menu: nothing is moved
      expect(more(wrapper).exists()).toBe(true)
      resize(10_000)
      await vi.waitFor(() => expect(more(wrapper).exists()).toBe(false))
      await vi.waitFor(() => expect((document.activeElement as HTMLElement | null)?.getAttribute('href')).toBe('/kostra'))
    })

    it('leaves the focus on the More button where some tabs are still in the menu', async () => {
      stubWidths()
      room = 800
      const wrapper = await mountHeader()
      ;(more(wrapper).element as HTMLElement).focus()
      resize(820)
      await vi.waitFor(() => expect(wrapper.findAll('nav ul a.nav-tab')).toHaveLength(6))
      expect(more(wrapper).exists()).toBe(true)
      expect(document.activeElement).toBe(more(wrapper).element)
    })
  })
})
