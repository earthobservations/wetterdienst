import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { UApp } from '#components'
import SettingsMenu from '~/components/SettingsMenu.vue'

// The theme buttons of the header's settings popover are toggle buttons: the chosen one is told by `aria-pressed`,
// not by its fill alone, in a group named Appearance (4.1.2, GH-3989; the same as the page of the settings, GH-3969).

const mounted: Array<{ unmount: () => void }> = []
afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  document.body.innerHTML = ''
})

describe('the theme buttons of the settings menu', () => {
  it('say which theme is chosen, in a group named Appearance, and move it with a click', async () => {
    const wrapper = await mountSuspended({ setup: () => () => h(UApp, null, { default: () => h(SettingsMenu) }) }, { attachTo: document.body })
    mounted.push(wrapper)
    await wrapper.find('button[aria-label="Settings"]').trigger('click')

    // the popover's content is teleported to the body
    const group = () => document.body.querySelector('[role="group"][aria-label="Appearance"]')
    await vi.waitFor(() => expect(group()).not.toBeNull())
    const pressed = () => [...group()!.querySelectorAll('button')].map(b => b.getAttribute('aria-pressed'))
    const buttons = () => [...group()!.querySelectorAll('button')] as HTMLButtonElement[]
    expect(buttons()).toHaveLength(3)
    expect(pressed().filter(v => v === 'true')).toHaveLength(1)

    const next = buttons().find(b => b.getAttribute('aria-pressed') === 'false')!
    next.click()
    await vi.waitFor(() => expect(buttons().find(b => b.getAttribute('aria-pressed') === 'true')).toBe(next))
    expect(pressed().filter(v => v === 'true')).toHaveLength(1)
  })
})
