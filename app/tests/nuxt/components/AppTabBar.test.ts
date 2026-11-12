import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AppTabBar from '~/components/AppTabBar.vue'
import { useSettings } from '~/composables/useSettings'
import { useTabBar } from '~/composables/useTabBar'

// The navigation of the narrow layout (GH-3650, GH-3846, GH-3851): five tools and the Menu are six items, more than a
// tab bar holds, so the bar has four tools, which the reader chooses (Forecast, Explorer, Stripes and History until
// they do), and the Menu. The Menu's tab is marked on every page that is reached through its sheet and has no tab:
// a tool that is not in the bar, the reference and the project's pages, the settings. The home page and the legal
// pages mark nothing.

const mounted: Array<{ unmount: () => void }> = []
async function mountBar(route = '/') {
  const wrapper = await mountSuspended(AppTabBar, { route, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  document.body.querySelectorAll('[role="dialog"]').forEach(dialog => dialog.remove())
  // the choice is the settings', which one test leaves to the next
  useSettings().reset()
})

type Bar = Awaited<ReturnType<typeof mountBar>>
const menuButton = (wrapper: Bar) => wrapper.find('button[aria-haspopup="dialog"]')
const tabs = (wrapper: Bar) => wrapper.findAll('li').map(item => item.text())
const current = (wrapper: Bar) => wrapper.findAll('[aria-current="page"]').map(link => link.attributes('href'))
function choose(order: unknown) {
  useSettings().settings.value.tabBar = order as string[]
}

const DEFAULT_BAR = ['Forecast', 'Explorer', 'Climate stripes', 'History', 'Menu']
// History left out of the bar for the map
const WITH_MAP = ['map', 'forecast', 'explorer', 'stripes', 'history']

describe('the tab bar of the narrow layout', () => {
  it('has Forecast, Explorer, Stripes and History and the Menu until the reader chooses', async () => {
    const wrapper = await mountBar()
    expect(tabs(wrapper)).toEqual(DEFAULT_BAR)
    expect(wrapper.findAll('a').map(link => link.attributes('href'))).toEqual(['/meteogram', '/explorer', '/stripes', '/history'])
    expect(wrapper.find('a[href="/map"]').exists()).toBe(false)
  })

  it('has the Menu as a button that opens a dialog, named by its label', async () => {
    const wrapper = await mountBar()
    const button = menuButton(wrapper)
    expect(button.attributes('aria-label')).toBe('Menu')
    expect(button.attributes('aria-expanded')).toBe('false')
  })

  describe('the Menu\'s sheet (GH-3934)', () => {
    async function openSheet(order?: unknown) {
      if (order)
        choose(order)
      const wrapper = await mountBar()
      await menuButton(wrapper).trigger('click')
      await vi.waitFor(() => expect(document.body.querySelector('[role="dialog"]')).not.toBeNull())
      return document.body.querySelector('[role="dialog"]')!
    }
    const links = (sheet: Element) => [...sheet.querySelectorAll('section')[0]!.querySelectorAll('a')]
    const toolItems = (sheet: Element) => [...sheet.querySelectorAll<HTMLElement>('li[data-tool]')]

    it('has all five tools, the Home page and the link to the chooser, with the default choice', async () => {
      const tools = links(await openSheet())
      expect(tools.map(link => link.textContent!.replace(/, (in the bar|only in the Menu)$/, '').trim())).toEqual(['Home', 'Forecast', 'Explorer', 'Climate stripes', 'History', 'Map', 'Arrange tools'])
      expect(tools.map(link => link.getAttribute('href'))).toEqual(['/', '/meteogram', '/explorer', '/stripes', '/history', '/map', '/settings#bar'])
    })

    it('lists the tools in the order the reader chose, the four of the bar first, then the others', async () => {
      const sheet = await openSheet(['history', 'map', 'forecast', 'explorer', 'stripes'])
      expect(toolItems(sheet).map(item => item.dataset.tool)).toEqual(['history', 'map', 'forecast', 'explorer', 'stripes'])
      expect(toolItems(sheet).map(item => item.querySelector('a')!.getAttribute('href'))).toEqual(['/history', '/map', '/meteogram', '/explorer', '/stripes'])
      // the home page leads and the link to the chooser follows the tools
      expect(links(sheet).map(link => link.getAttribute('href')).at(0)).toBe('/')
      expect(links(sheet).map(link => link.getAttribute('href')).at(-1)).toBe('/settings#bar')
    })

    it('follows setOrder while it is open, as the bar does', async () => {
      const { setOrder } = useTabBar()
      const sheet = await openSheet()
      expect(toolItems(sheet).map(item => item.dataset.tool)).toEqual(['forecast', 'explorer', 'stripes', 'history', 'map'])
      setOrder(['map', 'stripes', 'explorer', 'forecast', 'history'])
      await vi.waitFor(() => expect(toolItems(sheet).map(item => item.dataset.tool)).toEqual(['map', 'stripes', 'explorer', 'forecast', 'history']))
    })

    it('marks the four tools of the bar with the bar\'s line, the others with the lighter one, and has no heading or rule between them', async () => {
      const sheet = await openSheet(['stripes', 'map', 'history', 'forecast', 'explorer'])
      const groups = toolItems(sheet).map(item => [item.dataset.tool, item.querySelector('a')!.dataset.group])
      expect(groups).toEqual([['stripes', 'bar'], ['map', 'bar'], ['history', 'bar'], ['forecast', 'bar'], ['explorer', 'menu']])
      for (const item of toolItems(sheet)) {
        const link = item.querySelector('a')!
        expect(item.dataset.group, 'the group is on the link only').toBeUndefined()
        // one line, drawn by CSS from the group, and no information in it for a screen reader
        const marks = link.querySelectorAll('.tool-mark')
        expect(marks).toHaveLength(1)
        expect(marks[0]!.getAttribute('aria-hidden')).toBe('true')
      }
      // the sheet's own headings (its title, tools, reference, project) are all it has: none says where a tool is
      expect([...sheet.querySelectorAll('h2')].map(heading => heading.textContent!.trim())).toEqual(['Menu', 'Tools', 'Reference', 'Project'])
      expect(sheet.querySelectorAll('h3')).toHaveLength(0)
      expect(sheet.querySelectorAll('hr')).toHaveLength(0)
    })

    it('says in visually hidden text which tools are in the bar and which only in the Menu', async () => {
      const sheet = await openSheet(['stripes', 'map', 'history', 'forecast', 'explorer'])
      const hidden = toolItems(sheet).map(item => item.querySelector('.sr-only')!.textContent!.trim())
      expect(hidden).toEqual([', in the bar', ', in the bar', ', in the bar', ', in the bar', ', only in the Menu'])
      // the link's name is the tool, then where it is
      expect(toolItems(sheet).at(0)!.querySelector('a')!.textContent!.replace(/\s+/g, ' ').trim()).toBe('Climate stripes, in the bar')
      // the other links of the sheet say nothing of the kind
      expect(sheet.querySelectorAll('.sr-only')).toHaveLength(5)
    })
  })

  describe('marks, for every kind of page it is on', () => {
    // [route, the link of the bar that is the page, or null where the Menu is, or nothing where the page is no place of the bar]
    const routes: Array<[string, string | null | undefined]> = [
      // the tools of the bar mark their own tab
      ['/meteogram', '/meteogram'],
      ['/meteogram?station=10147&compact=true', '/meteogram'],
      ['/explorer', '/explorer'],
      ['/stripes', '/stripes'],
      ['/history', '/history'],
      // the tool that is not in the bar: the Menu
      ['/map', null],
      ['/map?station=10147&lat=53.45&lon=10.2', null],
      ['/map?layer=measured', null],
      // the reference
      ['/providers', null],
      ['/providers/dwd', null],
      ['/glossary', null],
      ['/api', null],
      // the project
      ['/about', null],
      ['/support', null],
      ['/settings', null],
      ['/settings#bar', null],
      // the home page and the legal pages: nothing
      ['/', undefined],
      ['/impressum', undefined],
      ['/datenschutz', undefined],
      // a page that is none of these
      ['/widget', undefined],
      ['/apiary', undefined],
    ]

    it.each(routes)('%s', async (route, tab) => {
      const wrapper = await mountBar(route)
      expect(menuButton(wrapper).attributes('aria-current'), 'the Menu').toBe(tab === null ? 'true' : undefined)
      expect(current(wrapper), 'the tabs').toEqual(typeof tab === 'string' ? [tab] : [])
    })
  })

  describe('with the choice of the reader', () => {
    it('shows the four tools in the order chosen, and the Menu', async () => {
      choose(['history', 'map', 'forecast', 'explorer', 'stripes'])
      const wrapper = await mountBar()
      expect(tabs(wrapper)).toEqual(['History', 'Map', 'Forecast', 'Explorer', 'Menu'])
      expect(wrapper.findAll('a').map(link => link.attributes('href'))).toEqual(['/history', '/map', '/meteogram', '/explorer'])
    })

    it('marks the tab of a tool that was moved into the bar, and the Menu on the one it left out', async () => {
      choose(WITH_MAP)
      const onMap = await mountBar('/map?layer=measured')
      expect(current(onMap)).toEqual(['/map'])
      expect(menuButton(onMap).attributes('aria-current')).toBeUndefined()
      const onHistory = await mountBar('/history')
      expect(current(onHistory)).toEqual([])
      expect(menuButton(onHistory).attributes('aria-current')).toBe('true')
    })

    it.each(['/providers', '/glossary', '/api', '/about', '/support', '/settings'])('marks the Menu on %s, as the reference and the project are in the sheet whatever the bar holds', async (route) => {
      choose(['stripes', 'map', 'history', 'forecast', 'explorer'])
      const wrapper = await mountBar(route)
      expect(menuButton(wrapper).attributes('aria-current')).toBe('true')
      expect(current(wrapper)).toEqual([])
    })

    it('marks nothing on the home page and the legal pages, whatever the bar holds', async () => {
      choose(WITH_MAP)
      for (const route of ['/', '/impressum', '/datenschutz']) {
        const wrapper = await mountBar(route)
        expect(menuButton(wrapper).attributes('aria-current'), route).toBeUndefined()
        expect(current(wrapper), route).toEqual([])
      }
    })

    it.each([
      ['a list of the tools that is too short', ['map']],
      ['a tool that does not exist', ['radar', 'map', 'forecast', 'explorer', 'stripes']],
      ['a tool twice', ['map', 'map', 'map', 'map']],
      ['no list', 'map'],
      ['nothing', null],
    ])('is a bar of four tools with the Menu for %s, no error', async (_name, stored) => {
      choose(stored)
      const wrapper = await mountBar('/history')
      expect(wrapper.findAll('li')).toHaveLength(5)
      expect(wrapper.findAll('a')).toHaveLength(4)
      expect(tabs(wrapper).at(-1)).toBe('Menu')
      // the tool named stays where it was put, the rest are the default's, and every tool is in the bar or in the Menu
      expect(wrapper.findAll('a').map(link => link.attributes('href'))).not.toContain(undefined)
    })

    it('is the default bar for a list that names nothing it knows', async () => {
      choose(['radar', 'weather'])
      expect(tabs(await mountBar())).toEqual(DEFAULT_BAR)
    })

    it('follows a change of the choice while it is shown, the bar and the mark', async () => {
      const wrapper = await mountBar('/map')
      expect(tabs(wrapper)).toEqual(DEFAULT_BAR)
      expect(menuButton(wrapper).attributes('aria-current')).toBe('true')
      choose(WITH_MAP)
      await vi.waitFor(() => expect(tabs(wrapper)).toEqual(['Map', 'Forecast', 'Explorer', 'Climate stripes', 'Menu']))
      expect(menuButton(wrapper).attributes('aria-current')).toBeUndefined()
      expect(current(wrapper)).toEqual(['/map'])
      useSettings().settings.value.tabBar = ['forecast', 'explorer', 'stripes', 'history', 'map']
      await vi.waitFor(() => expect(tabs(wrapper)).toEqual(DEFAULT_BAR))
      expect(menuButton(wrapper).attributes('aria-current')).toBe('true')
    })
  })

  describe('as one goes from page to page, with no new mount', () => {
    it('follows the route: the tab of a tool, the Menu for the pages of the sheet, nothing for the home page', async () => {
      const wrapper = await mountBar('/')
      const router = useRouter()
      const at = async (path: string) => {
        await router.push(path)
        await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe(path))
        await wrapper.vm.$nextTick()
      }
      const steps: Array<[string, string | null | undefined]> = [
        ['/history', '/history'],
        ['/map', null],
        ['/glossary', null],
        ['/explorer', '/explorer'],
        ['/settings', null],
        ['/', undefined],
        ['/providers/dwd', null],
        ['/datenschutz', undefined],
        ['/about', null],
        ['/meteogram?station=10147', '/meteogram'],
      ]
      for (const [path, tab] of steps) {
        await at(path)
        expect(menuButton(wrapper).attributes('aria-current'), `the Menu at ${path}`).toBe(tab === null ? 'true' : undefined)
        expect(current(wrapper), `the tabs at ${path}`).toEqual(typeof tab === 'string' ? [tab] : [])
      }
    })

    it('follows the route with a chosen bar, a tool that moved into the bar marking its own tab', async () => {
      choose(WITH_MAP)
      const wrapper = await mountBar('/')
      const router = useRouter()
      for (const [path, tab] of [['/map', '/map'], ['/history', null], ['/stripes', '/stripes'], ['/support', null], ['/impressum', undefined]] as const) {
        await router.push(path)
        await vi.waitFor(() => expect(router.currentRoute.value.path).toBe(path))
        await wrapper.vm.$nextTick()
        expect(menuButton(wrapper).attributes('aria-current'), `the Menu at ${path}`).toBe(tab === null ? 'true' : undefined)
        expect(current(wrapper), `the tabs at ${path}`).toEqual(typeof tab === 'string' ? [tab] : [])
      }
    })
  })

  describe('the link to the chooser of the bar', () => {
    async function openSheet(route: string) {
      const wrapper = await mountBar(route)
      await menuButton(wrapper).trigger('click')
      await vi.waitFor(() => expect(document.body.querySelector('[role="dialog"]')).not.toBeNull())
      const link = document.body.querySelector<HTMLAnchorElement>('[role="dialog"] a[href="/settings#bar"]')!
      return { wrapper, link }
    }
    const click = (link: HTMLElement, init: MouseEventInit = {}) => link.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, button: 0, ...init }))

    it('closes the sheet on a plain click', async () => {
      const { wrapper, link } = await openSheet('/history')
      click(link)
      await vi.waitFor(() => expect(menuButton(wrapper).attributes('aria-expanded')).toBe('false'))
    })

    it.each([
      ['Ctrl', { ctrlKey: true }],
      ['Cmd', { metaKey: true }],
      ['Shift', { shiftKey: true }],
      ['Alt', { altKey: true }],
      ['the middle button', { button: 1 }],
    ])('leaves the sheet open on %s-click, which opens the link elsewhere and not here', async (_name, init) => {
      const { wrapper, link } = await openSheet('/history')
      click(link, init)
      await wrapper.vm.$nextTick()
      expect(menuButton(wrapper).attributes('aria-expanded')).toBe('true')
      expect(document.body.querySelector('[role="dialog"]')).not.toBeNull()
    })
  })
})
