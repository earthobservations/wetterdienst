import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it } from 'vitest'
import SettingsPage from '~/pages/settings.vue'

describe('settings Page', () => {
  // useSettings() is backed by a module-level singleton (localStorage-backed),
  // so mutations in one test would otherwise leak into the next.
  afterEach(async () => {
    const wrapper = await mountSuspended(SettingsPage)
    ;(wrapper.vm as any).reset()
  })

  it('renders the page', async () => {
    const wrapper = await mountSuspended(SettingsPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays the settings heading', async () => {
    const wrapper = await mountSuspended(SettingsPage)
    expect(wrapper.text()).toContain('Settings')
  })

  it('displays language, appearance and units sections', async () => {
    const wrapper = await mountSuspended(SettingsPage)
    const text = wrapper.text()

    expect(text).toContain('Language')
    expect(text).toContain('Appearance')
    expect(text).toContain('Units')
  })

  it('shows friendly labels and convert units toggles', async () => {
    const wrapper = await mountSuspended(SettingsPage)
    const text = wrapper.text()

    expect(text).toContain('Plain-language labels')
    expect(text).toContain('Convert units')
  })

  it('hides the unit selectors when convertUnits is disabled', async () => {
    const wrapper = await mountSuspended(SettingsPage)
    const vm = wrapper.vm as any
    vm.settings.convertUnits = false
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('Temperature')
  })

  it('shows the unit selectors when convertUnits is enabled', async () => {
    const wrapper = await mountSuspended(SettingsPage)
    const vm = wrapper.vm as any
    vm.settings.convertUnits = true
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Temperature')
    expect(wrapper.text()).toContain('Wind speed')
  })

  it('resets settings to defaults when reset is called', async () => {
    const wrapper = await mountSuspended(SettingsPage)
    const vm = wrapper.vm as any

    vm.settings.friendlyLabels = false
    await wrapper.vm.$nextTick()
    expect(vm.settings.friendlyLabels).toBe(false)

    vm.reset()
    await wrapper.vm.$nextTick()

    expect(vm.settings.friendlyLabels).toBe(true)
  })

  it('clicking a theme button switches the color mode', async () => {
    const wrapper = await mountSuspended(SettingsPage, { attachTo: document.body })
    const vm = wrapper.vm as any

    const darkButton = wrapper.findAll('button').find(b => b.text() === 'Dark')
    await darkButton!.trigger('click')
    await wrapper.vm.$nextTick()
    expect(vm.colorMode.preference).toBe('dark')

    const lightButton = wrapper.findAll('button').find(b => b.text() === 'Light')
    await lightButton!.trigger('click')
    await wrapper.vm.$nextTick()
    expect(vm.colorMode.preference).toBe('light')
  })

  it('clicking the friendly-labels switch toggles the setting', async () => {
    const wrapper = await mountSuspended(SettingsPage, { attachTo: document.body })
    const vm = wrapper.vm as any
    expect(vm.settings.friendlyLabels).toBe(true)

    const friendlyLabelsSwitch = wrapper.findAllComponents({ name: 'USwitch' })[0]!
    await friendlyLabelsSwitch.find('button[role="switch"]').trigger('click')
    await wrapper.vm.$nextTick()

    expect(vm.settings.friendlyLabels).toBe(false)
  })

  it('clicking Reset restores defaults after clicking Dark and toggling switches', async () => {
    const wrapper = await mountSuspended(SettingsPage, { attachTo: document.body })
    const vm = wrapper.vm as any

    const darkButton = wrapper.findAll('button').find(b => b.text() === 'Dark')
    await darkButton!.trigger('click')
    const friendlyLabelsSwitch = wrapper.findAllComponents({ name: 'USwitch' })[0]!
    await friendlyLabelsSwitch.find('button[role="switch"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(vm.settings.friendlyLabels).toBe(false)

    const resetButton = wrapper.findAll('button').find(b => b.text().includes('Reset to defaults'))
    await resetButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(vm.settings.friendlyLabels).toBe(true)
  })
})
