import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AppTabBar from '~/components/AppTabBar.vue'

// The navigation of the narrow layout (GH-3650): five tools and the Menu are six items, more than a tab bar holds, so
// the bar has four tools and the Menu, and the station history, the tool asked for least, is in the Menu's sheet,
// where the tab of a page on the history is marked.

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
  it('has four tools and the Menu, and not the station history', async () => {
    const wrapper = await mountBar()
    const items = wrapper.findAll('li').map(item => item.text())
    expect(items).toEqual(['Forecast', 'Explorer', 'Climate stripes', 'Map', 'Menu'])
    expect(wrapper.findAll('a').map(link => link.attributes('href'))).toEqual(['/meteogram', '/explorer', '/stripes', '/map'])
    expect(wrapper.text()).not.toContain('History')
  })

  it('has the Menu as a button that opens a dialog, named by its label', async () => {
    const wrapper = await mountBar()
    const button = menuButton(wrapper)
    expect(button.attributes('aria-label')).toBe('Menu')
    expect(button.attributes('aria-expanded')).toBe('false')
  })

  it('has the station history in the Menu\'s sheet, with the other four tools in the order of the header', async () => {
    const wrapper = await mountBar()
    await menuButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(document.body.querySelector('[role="dialog"]')).not.toBeNull())
    const sheet = document.body.querySelector('[role="dialog"]')!
    const tools = [...sheet.querySelectorAll('section')[0]!.querySelectorAll('a')]
    expect(tools.map(link => link.textContent!.trim())).toEqual(['Home', 'Forecast', 'Explorer', 'Climate stripes', 'History', 'Map'])
    expect(tools.map(link => link.getAttribute('href'))).toEqual(['/', '/meteogram', '/explorer', '/stripes', '/history', '/map'])
    expect(menuButton(wrapper).attributes('aria-expanded')).toBe('true')
  })

  it('marks the tab of the page one is on, and the Menu where the page is the station history', async () => {
    const onMap = await mountBar('/map')
    expect(onMap.find('a[href="/map"]').attributes('aria-current')).toBe('page')
    expect(menuButton(onMap).attributes('data-current')).toBeUndefined()
    expect(onMap.findAll('[aria-current="page"]')).toHaveLength(1)
  })

  it('marks the Menu as the page one is on while the page is the station history, which has no tab', async () => {
    const wrapper = await mountBar('/history')
    expect(menuButton(wrapper).attributes('data-current')).toBeDefined()
    // no link of the bar is the page
    expect(wrapper.findAll('[aria-current="page"]')).toHaveLength(0)
  })

  it('does not mark the Menu on a page that has a tab, or on none', async () => {
    for (const route of ['/explorer', '/providers', '/']) {
      const wrapper = await mountBar(route)
      expect(menuButton(wrapper).attributes('data-current'), route).toBeUndefined()
    }
  })
})
