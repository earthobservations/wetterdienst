import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import TabBarChooser from '~/components/TabBarChooser.vue'
import { useSettings } from '~/composables/useSettings'

// The chooser of the four tools in the phone's tab bar (GH-3846): the list with its line, the preview of the bar, the
// arrow buttons that do what dragging does (WCAG 2.5.7), the status that says what moved, and the drag by the
// handle with the pointer events a mouse, a finger and a pen send.

const mounted: Array<{ unmount: () => void }> = []
async function mountChooser() {
  const wrapper = await mountSuspended(TabBarChooser, { attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
type Chooser = Awaited<ReturnType<typeof mountChooser>>

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  useSettings().reset()
  vi.restoreAllMocks()
})

const stored = () => useSettings().settings.value.tabBar
const rows = (wrapper: Chooser, group: 'bar' | 'menu') => wrapper.findAll(`[data-testid="bar-group-${group}"] li`).map(row => row.attributes('data-tool'))
const names = (wrapper: Chooser, group: 'bar' | 'menu') => wrapper.findAll(`[data-testid="bar-group-${group}"] li`).map(row => row.find('span.font-semibold').text())
const previewNames = (wrapper: Chooser) => wrapper.findAll('[data-testid="bar-preview"] [data-preview-tool]').map(item => item.text())
const button = (wrapper: Chooser, tool: string, dir: 'up' | 'down') => wrapper.find(`li[data-tool="${tool}"] button[data-dir="${dir}"]`)
const focusOn = (target: { element: Element }) => (target.element as HTMLElement).focus()
const status = (wrapper: Chooser) => wrapper.find('[data-testid="bar-status"]').text()

describe('the chooser of the tools in the phone bar', () => {
  it('lists the four tools of the bar above the line and the others below it, in the order of the bar', async () => {
    const wrapper = await mountChooser()
    expect(rows(wrapper, 'bar')).toEqual(['forecast', 'explorer', 'stripes', 'history'])
    expect(rows(wrapper, 'menu')).toEqual(['map'])
    expect(names(wrapper, 'bar')).toEqual(['Forecast', 'Explorer', 'Climate stripes', 'History'])
    // each list is named by the heading over it
    const headings = wrapper.findAll('h3').map(heading => heading.text())
    expect(headings).toEqual(['In the bar', 'Only in the Menu'])
    for (const list of wrapper.findAll('ol'))
      expect(wrapper.find(`#${list.attributes('aria-labelledby')}`).exists()).toBe(true)
  })

  it('shows the bar as it would be drawn: the four tools and the Menu, and says what is only in the Menu', async () => {
    const wrapper = await mountChooser()
    expect(previewNames(wrapper)).toEqual(['Forecast', 'Explorer', 'Climate stripes', 'History'])
    const preview = wrapper.find('[data-testid="bar-preview"]')
    expect(preview.text()).toContain('Menu')
    // a picture with a name that lists what it shows
    expect(preview.attributes('role')).toBe('img')
    expect(preview.attributes('aria-label')).toBe('Preview of the bar: Forecast, Explorer, Climate stripes, History, Menu')
    expect(wrapper.find('[data-testid="bar-preview-menu"]').text()).toBe('Only in the Menu: Map')
  })

  it('has a handle that is no stop of the keyboard and is not read out, and two buttons on a row that are (their size is set in main.css, measured in the e2e spec)', async () => {
    const wrapper = await mountChooser()
    for (const handle of wrapper.findAll('[data-testid="bar-handle"]')) {
      expect(handle.attributes('aria-hidden')).toBe('true')
      expect(handle.attributes('tabindex')).toBeUndefined()
    }
    expect(wrapper.findAll('li button')).toHaveLength(10)
    expect(button(wrapper, 'stripes', 'up').attributes('aria-label')).toBe('Move Climate stripes up')
    expect(button(wrapper, 'stripes', 'down').attributes('aria-label')).toBe('Move Climate stripes down')
  })

  describe('by the buttons, which are the way without dragging', () => {
    it('moves a tool up inside the bar, and says where it is now', async () => {
      const wrapper = await mountChooser()
      await button(wrapper, 'stripes', 'up').trigger('click')
      expect(stored()).toEqual(['forecast', 'stripes', 'explorer', 'history', 'map'])
      expect(rows(wrapper, 'bar')).toEqual(['forecast', 'stripes', 'explorer', 'history'])
      expect(status(wrapper)).toBe('Climate stripes moved to place 2 of 4 in the bar.')
      expect(previewNames(wrapper)).toEqual(['Forecast', 'Climate stripes', 'Explorer', 'History'])
    })

    it('moves a tool into the bar over the line, which pushes the fourth out, and says both', async () => {
      const wrapper = await mountChooser()
      await button(wrapper, 'map', 'up').trigger('click')
      expect(stored()).toEqual(['forecast', 'explorer', 'stripes', 'map', 'history'])
      expect(rows(wrapper, 'bar')).toEqual(['forecast', 'explorer', 'stripes', 'map'])
      expect(rows(wrapper, 'menu')).toEqual(['history'])
      expect(status(wrapper)).toBe('Map is now in the bar, at place 4 of 4. History is now only in the Menu.')
      expect(wrapper.find('[data-testid="bar-preview-menu"]').text()).toBe('Only in the Menu: History')
    })

    it('moves a tool out of the bar over the line, which pulls the one below it in, and says both', async () => {
      const wrapper = await mountChooser()
      await button(wrapper, 'history', 'down').trigger('click')
      expect(stored()).toEqual(['forecast', 'explorer', 'stripes', 'map', 'history'])
      expect(status(wrapper)).toBe('History is now only in the Menu. Map is now in the bar, at place 4 of 4.')
    })

    it('always has four tools in the bar, whichever way the tools are moved', async () => {
      const wrapper = await mountChooser()
      const presses: Array<[string, 'up' | 'down']> = [['map', 'up'], ['map', 'up'], ['forecast', 'down'], ['history', 'down'], ['explorer', 'down'], ['stripes', 'up'], ['map', 'down']]
      for (const [tool, dir] of presses) {
        await button(wrapper, tool, dir).trigger('click')
        expect(rows(wrapper, 'bar'), `${tool} ${dir}`).toHaveLength(4)
        expect([...rows(wrapper, 'bar'), ...rows(wrapper, 'menu')].sort()).toEqual(['explorer', 'forecast', 'history', 'map', 'stripes'])
        expect(previewNames(wrapper)).toHaveLength(4)
      }
    })

    it('keeps the focus on the button that was pressed, also where the row is built again on the other side of the line', async () => {
      const wrapper = await mountChooser()
      focusOn(button(wrapper, 'map', 'up'))
      await button(wrapper, 'map', 'up').trigger('click')
      await vi.waitFor(() => expect(document.activeElement).toBe(button(wrapper, 'map', 'up').element))
      await button(wrapper, 'map', 'up').trigger('click')
      await vi.waitFor(() => expect(document.activeElement).toBe(button(wrapper, 'map', 'up').element))
      expect(stored().indexOf('map')).toBe(2)
      // and the other way, back across the line
      focusOn(button(wrapper, 'map', 'down'))
      await button(wrapper, 'map', 'down').trigger('click')
      await button(wrapper, 'map', 'down').trigger('click')
      await vi.waitFor(() => expect(document.activeElement).toBe(button(wrapper, 'map', 'down').element))
      expect(rows(wrapper, 'menu')).toEqual(['map'])
    })

    it('does nothing at the ends of the list, where the button stays a stop and says it is unavailable', async () => {
      const wrapper = await mountChooser()
      const first = button(wrapper, 'forecast', 'up')
      const last = button(wrapper, 'map', 'down')
      expect(first.attributes('aria-disabled')).toBe('true')
      expect(last.attributes('aria-disabled')).toBe('true')
      expect(first.attributes('disabled')).toBeUndefined()
      expect(button(wrapper, 'explorer', 'up').attributes('aria-disabled')).toBeUndefined()
      await first.trigger('click')
      await last.trigger('click')
      expect(stored()).toEqual(['forecast', 'explorer', 'stripes', 'history', 'map'])
      expect(status(wrapper)).toBe('')
    })

    it('has the status in the page from the start, polite, so that the first move is read out', async () => {
      const wrapper = await mountChooser()
      const live = wrapper.find('[data-testid="bar-status"]')
      expect(live.attributes('role')).toBe('status')
      expect(live.attributes('aria-live')).toBe('polite')
      expect(live.text()).toBe('')
    })
  })

  describe('reset', () => {
    it('puts the default back and says what the bar is', async () => {
      const wrapper = await mountChooser()
      await button(wrapper, 'map', 'up').trigger('click')
      await button(wrapper, 'map', 'up').trigger('click')
      expect(stored()).not.toEqual(['forecast', 'explorer', 'stripes', 'history', 'map'])
      await wrapper.find('[data-testid="bar-reset"]').trigger('click')
      expect(stored()).toEqual(['forecast', 'explorer', 'stripes', 'history', 'map'])
      expect(rows(wrapper, 'bar')).toEqual(['forecast', 'explorer', 'stripes', 'history'])
      expect(status(wrapper)).toBe('The bar is back to its default: Forecast, Explorer, Climate stripes, History.')
    })
  })

  describe('a choice that is stored wrong', () => {
    it.each([
      ['a tool that does not exist', ['radar', 'map', 'forecast', 'explorer', 'stripes'], ['map', 'forecast', 'explorer', 'stripes']],
      ['too few tools', ['history'], ['history', 'forecast', 'explorer', 'stripes']],
      ['no list', 'garbage', ['forecast', 'explorer', 'stripes', 'history']],
      ['a tool twice', ['map', 'map', 'map'], ['map', 'forecast', 'explorer', 'stripes']],
    ])('is shown as a list of four and one below the line for %s, and the first move saves a valid list', async (_name, bad, bar) => {
      useSettings().settings.value.tabBar = bad as string[]
      const wrapper = await mountChooser()
      expect(rows(wrapper, 'bar')).toEqual(bar)
      expect(rows(wrapper, 'menu')).toHaveLength(1)
      await button(wrapper, bar[1]!, 'up').trigger('click')
      expect([...stored()].sort()).toEqual(['explorer', 'forecast', 'history', 'map', 'stripes'])
    })
  })

  describe('by the handle, with a pointer', () => {
    // a test environment has no layout: the rows are given the rectangles of five rows of 56 px with 8 px between
    // them, and a line of 24 px before the fifth, as the page has
    function layOut(wrapper: Chooser) {
      wrapper.findAll('li[data-row]').forEach((row, index) => {
        const top = index * 64 + (index >= 4 ? 24 : 0)
        vi.spyOn(row.element, 'getBoundingClientRect').mockReturnValue({ top, bottom: top + 56, left: 0, right: 300, width: 300, height: 56, x: 0, y: top, toJSON: () => ({}) })
      })
    }
    const handle = (wrapper: Chooser, tool: string) => wrapper.find(`li[data-tool="${tool}"] [data-testid="bar-handle"]`)
    const pointer = (pointerId: number, clientY: number, extra: Record<string, unknown> = {}) => ({ pointerId, clientY, button: 0, pointerType: 'touch', ...extra })
    /** The vertical middle of the slot `index` */
    const middle = (index: number) => index * 64 + (index >= 4 ? 24 : 0) + 28

    beforeEach(() => {
      // a pointer capture is a browser's: here it is only asked for
      HTMLElement.prototype.setPointerCapture = vi.fn()
    })

    it('moves a tool into the bar with the preview following while it is dragged, and makes the move on the drop only', async () => {
      const wrapper = await mountChooser()
      layOut(wrapper)
      await handle(wrapper, 'map').trigger('pointerdown', pointer(1, middle(4)))
      await handle(wrapper, 'map').trigger('pointermove', pointer(1, middle(1)))
      // the list stays as it is, the row it lands on is marked, and the preview is the bar after a drop
      expect(rows(wrapper, 'bar')).toEqual(['forecast', 'explorer', 'stripes', 'history'])
      expect(wrapper.find('li[data-tool="explorer"]').attributes('data-drop')).toBe('before')
      expect(wrapper.find('li[data-tool="map"]').attributes('data-dragging')).toBeDefined()
      expect(previewNames(wrapper)).toEqual(['Forecast', 'Map', 'Explorer', 'Climate stripes'])
      expect(wrapper.find('[data-testid="bar-preview-menu"]').text()).toBe('Only in the Menu: History')
      expect(stored()).toEqual(['forecast', 'explorer', 'stripes', 'history', 'map'])
      await handle(wrapper, 'map').trigger('pointerup', pointer(1, middle(1)))
      expect(stored()).toEqual(['forecast', 'map', 'explorer', 'stripes', 'history'])
      expect(rows(wrapper, 'bar')).toEqual(['forecast', 'map', 'explorer', 'stripes'])
      expect(rows(wrapper, 'menu')).toEqual(['history'])
      expect(status(wrapper)).toBe('Map is now in the bar, at place 2 of 4. History is now only in the Menu.')
      expect(wrapper.find('[data-dragging]').exists()).toBe(false)
      expect(wrapper.find('[data-drop]').exists()).toBe(false)
    })

    it('moves a tool out of the bar below the line, which pulls the first below it in', async () => {
      const wrapper = await mountChooser()
      layOut(wrapper)
      await handle(wrapper, 'forecast').trigger('pointerdown', pointer(2, middle(0)))
      await handle(wrapper, 'forecast').trigger('pointermove', pointer(2, middle(4) + 20))
      expect(previewNames(wrapper)).toEqual(['Explorer', 'Climate stripes', 'History', 'Map'])
      expect(wrapper.find('li[data-tool="map"]').attributes('data-drop')).toBe('after')
      await handle(wrapper, 'forecast').trigger('pointerup', pointer(2, middle(4) + 20))
      expect(stored()).toEqual(['explorer', 'stripes', 'history', 'map', 'forecast'])
      expect(status(wrapper)).toBe('Forecast is now only in the Menu. Map is now in the bar, at place 4 of 4.')
    })

    it('reorders inside the bar, down as well as up', async () => {
      const wrapper = await mountChooser()
      layOut(wrapper)
      await handle(wrapper, 'history').trigger('pointerdown', pointer(3, middle(3)))
      await handle(wrapper, 'history').trigger('pointermove', pointer(3, middle(0)))
      await handle(wrapper, 'history').trigger('pointerup', pointer(3, middle(0)))
      expect(stored()).toEqual(['history', 'forecast', 'explorer', 'stripes', 'map'])
      expect(status(wrapper)).toBe('History moved to place 1 of 4 in the bar.')
    })

    it('makes no move for a drop on the place it started from, and says nothing', async () => {
      const wrapper = await mountChooser()
      layOut(wrapper)
      await handle(wrapper, 'stripes').trigger('pointerdown', pointer(4, middle(2)))
      await handle(wrapper, 'stripes').trigger('pointermove', pointer(4, middle(2) + 10))
      expect(wrapper.find('[data-drop]').exists()).toBe(false)
      await handle(wrapper, 'stripes').trigger('pointerup', pointer(4, middle(2) + 10))
      expect(stored()).toEqual(['forecast', 'explorer', 'stripes', 'history', 'map'])
      expect(status(wrapper)).toBe('')
    })

    it('leaves the list as it was when the pointer is cancelled, as a finger is when the browser takes the gesture', async () => {
      const wrapper = await mountChooser()
      layOut(wrapper)
      await handle(wrapper, 'map').trigger('pointerdown', pointer(5, middle(4)))
      await handle(wrapper, 'map').trigger('pointermove', pointer(5, middle(0)))
      expect(previewNames(wrapper)[0]).toBe('Map')
      await handle(wrapper, 'map').trigger('pointercancel', pointer(5, middle(0)))
      expect(stored()).toEqual(['forecast', 'explorer', 'stripes', 'history', 'map'])
      expect(previewNames(wrapper)).toEqual(['Forecast', 'Explorer', 'Climate stripes', 'History'])
      expect(wrapper.find('[data-dragging]').exists()).toBe(false)
    })

    it('leaves the list as it was on Escape, and the pointer that is released after it does nothing', async () => {
      const wrapper = await mountChooser()
      layOut(wrapper)
      await handle(wrapper, 'map').trigger('pointerdown', pointer(6, middle(4)))
      await handle(wrapper, 'map').trigger('pointermove', pointer(6, middle(0)))
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }))
      await wrapper.vm.$nextTick()
      expect(wrapper.find('[data-dragging]').exists()).toBe(false)
      expect(previewNames(wrapper)).toEqual(['Forecast', 'Explorer', 'Climate stripes', 'History'])
      await handle(wrapper, 'map').trigger('pointerup', pointer(6, middle(0)))
      expect(stored()).toEqual(['forecast', 'explorer', 'stripes', 'history', 'map'])
    })

    it('does not start with another button than the main one of a mouse, and ignores a second pointer while one drags', async () => {
      const wrapper = await mountChooser()
      layOut(wrapper)
      await handle(wrapper, 'map').trigger('pointerdown', pointer(7, middle(4), { pointerType: 'mouse', button: 2 }))
      expect(wrapper.find('[data-dragging]').exists()).toBe(false)
      await handle(wrapper, 'map').trigger('pointerdown', pointer(8, middle(4)))
      await handle(wrapper, 'history').trigger('pointerdown', pointer(9, middle(3)))
      expect(wrapper.findAll('[data-dragging]')).toHaveLength(1)
      // a move or a release of the other pointer is not the drag's
      await handle(wrapper, 'map').trigger('pointermove', pointer(9, middle(0)))
      expect(wrapper.find('[data-drop]').exists()).toBe(false)
      await handle(wrapper, 'map').trigger('pointerup', pointer(9, middle(0)))
      expect(stored()).toEqual(['forecast', 'explorer', 'stripes', 'history', 'map'])
      await handle(wrapper, 'map').trigger('pointerup', pointer(8, middle(0)))
      expect(stored()).toEqual(['map', 'forecast', 'explorer', 'stripes', 'history'])
    })

    it('holds the pointer on the handle for the drag, so that it keeps moving wherever the pointer goes', async () => {
      const wrapper = await mountChooser()
      layOut(wrapper)
      await handle(wrapper, 'map').trigger('pointerdown', pointer(10, middle(4)))
      expect(HTMLElement.prototype.setPointerCapture).toHaveBeenCalledWith(10)
      await handle(wrapper, 'map').trigger('pointerup', pointer(10, middle(4)))
    })
  })
})
