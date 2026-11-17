import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import SegmentedControl from '~/components/SegmentedControl.vue'

// The radio group of the app's switches (GH-4079 gave it a disabled option): one stop of Tab, the arrow keys along it.

const OPTIONS = [
  { value: 'off', label: 'None', disabled: true },
  { value: 'fine', label: 'Fine' },
  { value: 'coarse', label: 'Coarse' },
]

async function mountGroup(modelValue: string, options = OPTIONS) {
  return mountSuspended(SegmentedControl, { props: { modelValue, options, label: 'Grouping' }, attachTo: document.body })
}

describe('segmentedControl with a disabled option', () => {
  it('shows it disabled, and is a group of radios with one stop of Tab on the chosen one', async () => {
    const wrapper = await mountGroup('fine')
    const radios = wrapper.findAll('[role="radio"]')
    expect(radios.map(radio => radio.attributes('disabled') !== undefined)).toEqual([true, false, false])
    expect(radios.map(radio => radio.attributes('tabindex'))).toEqual(['-1', '0', '-1'])
    wrapper.unmount()
  })

  it('has its one stop of Tab on the first option that can be chosen where the value is a disabled one: a disabled button takes no focus', async () => {
    const wrapper = await mountGroup('off')
    expect(wrapper.findAll('[role="radio"]').map(radio => radio.attributes('tabindex'))).toEqual(['-1', '0', '-1'])
    wrapper.unmount()
  })

  it('is walked by the arrow keys past the disabled option, round the ends, and by Home and End', async () => {
    const wrapper = await mountGroup('fine')
    const radios = wrapper.findAll('[role="radio"]')
    await radios[1]!.trigger('keydown', { key: 'ArrowLeft' })
    // the left of Fine is None, which cannot be chosen: round the end to Coarse
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual(['coarse'])
    await radios[2]!.trigger('keydown', { key: 'ArrowRight' })
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual(['fine'])
    await radios[1]!.trigger('keydown', { key: 'Home' })
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual(['fine'])
    await radios[1]!.trigger('keydown', { key: 'End' })
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual(['coarse'])
    wrapper.unmount()
  })

  it('walks all the options as before where none is disabled', async () => {
    const wrapper = await mountGroup('off', OPTIONS.map(option => ({ value: option.value, label: option.label })))
    const radios = wrapper.findAll('[role="radio"]')
    await radios[0]!.trigger('keydown', { key: 'ArrowRight' })
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual(['fine'])
    await radios[0]!.trigger('keydown', { key: 'ArrowLeft' })
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual(['coarse'])
    wrapper.unmount()
  })
})
