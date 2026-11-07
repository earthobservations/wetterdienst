import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AppTabBar from '~/components/AppTabBar.vue'

// The navigation of the narrow layout (GH-3650): five tools and the Menu are six items, more than a tab bar holds, so
// the bar has the four tools it had before the map and the Menu, and the map is in the Menu's sheet, where the tab of a
// page on the map is marked.

const mounted: Array<{ unmount: () => void }> = []
async function mountBar(route = '/') {
  const wrapper = await mountSuspended(AppTabBar, { route, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  document.body.querySelectorAll('[role="dialog"]').forEach(dialog => dialog.remove())
})

const menuButton = (wrapper: Awaited<ReturnType<typeof mountBar>>) => wrapper.find('button[aria-haspopup="dialog"]')

describe('the tab bar of the narrow layout', () => {
  it('has the four tools it had before the map and the Menu, History a tab and the map none', async () => {
    const wrapper = await mountBar()
    const items = wrapper.findAll('li').map(item => item.text())
    expect(items).toEqual(['Forecast', 'Explorer', 'Climate stripes', 'History', 'Menu'])
    expect(wrapper.findAll('a').map(link => link.attributes('href'))).toEqual(['/meteogram', '/explorer', '/stripes', '/history'])
    expect(wrapper.find('a[href="/map"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Map')
  })

  it('has the Menu as a button that opens a dialog, named by its label', async () => {
    const wrapper = await mountBar()
    const button = menuButton(wrapper)
    expect(button.attributes('aria-label')).toBe('Menu')
    expect(button.attributes('aria-expanded')).toBe('false')
  })

  it('has the map in the Menu\'s sheet, with the other four tools in the order of the header', async () => {
    const wrapper = await mountBar()
    await menuButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(document.body.querySelector('[role="dialog"]')).not.toBeNull())
    const sheet = document.body.querySelector('[role="dialog"]')!
    const tools = [...sheet.querySelectorAll('section')[0]!.querySelectorAll('a')]
    expect(tools.map(link => link.textContent!.trim())).toEqual(['Home', 'Forecast', 'Explorer', 'Climate stripes', 'History', 'Map'])
    expect(tools.map(link => link.getAttribute('href'))).toEqual(['/', '/meteogram', '/explorer', '/stripes', '/history', '/map'])
    expect(menuButton(wrapper).attributes('aria-expanded')).toBe('true')
  })

  it('marks the tab of the page one is on, History among them, and not the Menu', async () => {
    const onHistory = await mountBar('/history')
    expect(onHistory.find('a[href="/history"]').attributes('aria-current')).toBe('page')
    expect(menuButton(onHistory).attributes('aria-current')).toBeUndefined()
    expect(onHistory.findAll('[aria-current="page"]')).toHaveLength(1)
  })

  it('marks the Menu as the page one is on while the page is the map, which has no tab, with a query as well', async () => {
    for (const route of ['/map', '/map?station=10147&lat=53.45&lon=10.2', '/map?layer=measured']) {
      const wrapper = await mountBar(route)
      expect(menuButton(wrapper).attributes('aria-current'), route).toBe('true')
      // no link of the bar is the page
      expect(wrapper.findAll('[aria-current="page"]'), route).toHaveLength(0)
    }
  })

  it('does not mark the Menu on a page that has a tab, or on none', async () => {
    for (const route of ['/explorer', '/history', '/providers', '/']) {
      const wrapper = await mountBar(route)
      expect(menuButton(wrapper).attributes('aria-current'), route).toBeUndefined()
    }
  })
})
