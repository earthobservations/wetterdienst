import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it, onTestFinished } from 'vitest'
import { PageHeader } from '#components'

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
})
