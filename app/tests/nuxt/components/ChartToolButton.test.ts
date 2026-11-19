import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it, onTestFinished } from 'vitest'
import ChartToolButton from '~/components/ChartToolButton.vue'

// A button of a chart's toolbar that is off at the edge of what it does stays a button with the focus (WCAG 2.4.3, GH-4101): `aria-disabled`, not
// `disabled`, which drops the focus of a button that turns off while it is pressed. It looks as the disabled button does, and does nothing.

async function mountButton(unavailable: boolean) {
  const wrapper = await mountSuspended(ChartToolButton, {
    props: { unavailable },
    attrs: { 'icon': 'i-ph-arrow-counter-clockwise', 'aria-label': 'Reset zoom', 'title': 'Reset zoom' },
    attachTo: document.body,
  })
  onTestFinished(() => wrapper.unmount())
  return wrapper
}

describe('the chart toolbar button', () => {
  it('is a plain button that says nothing of being off while it can be used, and clicks', async () => {
    const wrapper = await mountButton(false)
    const button = wrapper.find('button')
    expect(button.attributes('aria-disabled')).toBeUndefined()
    expect(button.attributes('disabled')).toBeUndefined()
    await button.trigger('click')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })

  it('is aria-disabled and not disabled when off, keeps the focus, and does nothing when it is pressed', async () => {
    const wrapper = await mountButton(true)
    const button = wrapper.find('button')
    expect(button.attributes('aria-disabled')).toBe('true')
    expect(button.attributes('disabled')).toBeUndefined()
    expect(button.element.tabIndex).toBe(0)
    button.element.focus()
    await button.trigger('click')
    expect(wrapper.emitted('click')).toBeUndefined()
    expect(document.activeElement).toBe(button.element)
  })

  it('passes its icon, name and title to the button, and a button that turns off while it has the focus keeps it', async () => {
    const wrapper = await mountButton(false)
    const button = wrapper.find('button')
    expect(button.attributes('aria-label')).toBe('Reset zoom')
    expect(button.attributes('title')).toBe('Reset zoom')
    button.element.focus()
    await wrapper.setProps({ unavailable: true })
    expect(wrapper.find('button').attributes('aria-disabled')).toBe('true')
    expect(document.activeElement).toBe(wrapper.find('button').element)
  })

  it('looks as the disabled outline button does: every disabled: class of Nuxt UI has its aria-disabled: twin', async () => {
    const wrapper = await mountButton(true)
    const classes = wrapper.find('button').classes()
    const twinned = classes.filter(name => /(?:^|:)disabled:/.test(name))
    expect(twinned.length).toBeGreaterThan(0)
    for (const name of twinned)
      expect(classes, name).toContain(name.replace('disabled:', 'aria-disabled:'))
    expect(classes).toContain('aria-disabled:opacity-75')
    expect(classes).toContain('aria-disabled:cursor-not-allowed')
    // the focus ring is not taken away
    expect(classes).toContain('focus-visible:outline-3')
    expect(classes).toContain('focus-visible:ring-inverted')
  })
})
