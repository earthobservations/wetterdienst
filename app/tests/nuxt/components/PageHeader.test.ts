import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, onTestFinished } from 'vitest'
import { nextTick } from 'vue'
import { PageHeader } from '#components'
import { PHONE_QUERY } from '~/composables/usePhone'

async function mountHeader() {
  const wrapper = await mountSuspended(PageHeader, {
    props: { title: 'Explorer', lede: 'Look at it', aboutLabel: 'About the explorer' },
    slots: { about: () => 'What this is for' },
  })
  onTestFinished(() => wrapper.unmount())
  return wrapper
}

// The About button and its panel (GH-3518, GH-3872): the panel is the header's own element under the row, and the
// button names it while it is open. Where it stands (right-aligned under the button on a wide window, the full
// width on a phone) is a layout, which tests/e2e/page-about.spec.ts measures.
describe('the About button of the page header', () => {
  it('opens and closes the panel under the header row, and says so', async () => {
    const wrapper = await mountHeader()
    const button = wrapper.find('button[aria-expanded]')
    expect(button.text()).toContain('About the explorer')
    expect(button.attributes('aria-expanded')).toBe('false')
    expect(button.attributes('aria-controls')).toBeUndefined()
    expect(wrapper.find('.page-about').exists()).toBe(false)

    await button.trigger('click')
    const panel = wrapper.find('.page-about')
    expect(panel.text()).toBe('What this is for')
    expect(button.attributes('aria-expanded')).toBe('true')
    expect(button.attributes('aria-controls')).toBe(panel.attributes('id'))
    // the panel is a sibling of the row, not inside it, so it is as wide as the header and can be put at its edge
    expect(panel.element.parentElement?.tagName).toBe('HEADER')

    await button.trigger('click')
    expect(wrapper.find('.page-about').exists()).toBe(false)
    expect(button.attributes('aria-expanded')).toBe('false')
  })

  it('is left out of a print, and keeps the shrinking box of its actions', async () => {
    const wrapper = await mountHeader()
    const actions = wrapper.find('button[aria-expanded]').element.parentElement!
    expect(actions.getAttribute('data-print')).toBe('hide')
    expect(actions.classList).toContain('min-w-0')
    expect(actions.classList).toContain('max-w-full')
    expect(actions.classList).toContain('sm:shrink-0')
  })

  it('has no button when the page has no About slot', async () => {
    const wrapper = await mountSuspended(PageHeader, { props: { title: 'Settings', aboutLabel: 'About' } })
    onTestFinished(() => wrapper.unmount())
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('has no ⓘ on a window that is not a phone', async () => {
    const wrapper = await mountHeader()
    expect(wrapper.find('[data-testid="page-info"]').exists()).toBe(false)
  })
})

// On a phone (the tab bar's breakpoint, GH-4227) the button is a small ⓘ beside the title: it has a name, says whether the panel is
// open and which panel it controls (an element that is always there, hidden, so the reference holds), and Escape closes the panel
// and gives the focus back to it. The window's width is a media query, which the test serves.
describe('the ⓘ of the page header on a phone', () => {
  const matchMedia = window.matchMedia
  beforeEach(() => {
    window.matchMedia = ((query: string) => ({
      matches: query === PHONE_QUERY,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
    })) as unknown as typeof window.matchMedia
  })
  afterEach(() => {
    window.matchMedia = matchMedia
  })

  async function mountPhone() {
    const host = document.createElement('div')
    document.body.append(host)
    const wrapper = await mountSuspended(PageHeader, {
      props: { title: 'Explorer', lede: 'Look at it', aboutLabel: 'About the explorer' },
      slots: { about: () => 'What this is for' },
      attachTo: host,
    })
    onTestFinished(() => {
      wrapper.unmount()
      host.remove()
    })
    return wrapper
  }

  it('is a named button beside the title, with the labelled one of the actions gone', async () => {
    const wrapper = await mountPhone()
    const info = wrapper.get('[data-testid="page-info"]')
    expect(info.attributes('aria-label')).toBe('About the explorer')
    expect(info.text()).toBe('')
    // beside the title, in the one row
    const row = wrapper.get('.page-title-row')
    expect(row.element.contains(info.element)).toBe(true)
    expect(row.get('h1').text()).toBe('Explorer')
    // no second About button
    expect(wrapper.findAll('button[aria-expanded]')).toHaveLength(1)
    expect(wrapper.find('[data-print="hide"] button[aria-expanded]').exists()).toBe(false)
  })

  it('says whether the panel is open and which one it controls, which is there all the time', async () => {
    const wrapper = await mountPhone()
    const info = wrapper.get('[data-testid="page-info"]')
    const id = info.attributes('aria-controls')!
    expect(id).toBeTruthy()
    const panel = wrapper.get(`#${id}`)
    expect(panel.classes()).toContain('page-about')
    expect(info.attributes('aria-expanded')).toBe('false')
    expect(panel.isVisible()).toBe(false)

    await info.trigger('click')
    expect(info.attributes('aria-expanded')).toBe('true')
    expect(panel.isVisible()).toBe(true)
    expect(panel.text()).toBe('What this is for')

    await info.trigger('click')
    expect(info.attributes('aria-expanded')).toBe('false')
    expect(panel.isVisible()).toBe(false)
  })

  it('closes on Escape and gives the focus back to the ⓘ from where it was in the panel', async () => {
    const wrapper = await mountPhone()
    const info = wrapper.get('[data-testid="page-info"]')
    await info.trigger('click')
    const panel = wrapper.get('.page-about').element as HTMLElement
    panel.setAttribute('tabindex', '-1')
    panel.focus()
    expect(document.activeElement).toBe(panel)

    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    document.dispatchEvent(escape)
    await nextTick()
    await nextTick()
    expect(info.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(info.element)
    // the key is answered, so a full screen under it (the map's) does not leave with the same press
    expect(escape.defaultPrevented).toBe(true)
  })

  it('leaves an Escape alone when its panel is not open', async () => {
    await mountPhone()
    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    document.dispatchEvent(escape)
    expect(escape.defaultPrevented).toBe(false)
  })

  it('does not take the focus when it was somewhere else, and ignores other keys and a key already answered', async () => {
    const wrapper = await mountPhone()
    const info = wrapper.get('[data-testid="page-info"]')
    await info.trigger('click')
    const outside = document.createElement('input')
    document.body.append(outside)
    onTestFinished(() => outside.remove())
    outside.focus()

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    expect(info.attributes('aria-expanded')).toBe('true')
    const answered = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    answered.preventDefault()
    document.dispatchEvent(answered)
    expect(info.attributes('aria-expanded')).toBe('true')

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()
    await nextTick()
    expect(info.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(outside)
  })

  it('has no ⓘ when the page has no About slot', async () => {
    const wrapper = await mountSuspended(PageHeader, { props: { title: 'Settings', aboutLabel: 'About' } })
    onTestFinished(() => wrapper.unmount())
    expect(wrapper.find('[data-testid="page-info"]').exists()).toBe(false)
  })

  it('keeps the lede for a screen reader alone on a page that is compact (the map)', async () => {
    const wrapper = await mountSuspended(PageHeader, { props: { title: 'Map', lede: 'The stations', compact: true } })
    onTestFinished(() => wrapper.unmount())
    expect(wrapper.get('.page-lede').classes()).toContain('sr-only')
    expect(wrapper.get('header').attributes('data-compact')).toBeDefined()
  })
})
