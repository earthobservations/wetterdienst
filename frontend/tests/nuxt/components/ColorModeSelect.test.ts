import { ColorModeSelect } from '#components'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, it, expect } from 'vitest'

describe('ColorModeSelect Component', () => {
  it('renders the component', async () => {
    const wrapper = await mountSuspended(ColorModeSelect)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays a button', async () => {
    const wrapper = await mountSuspended(ColorModeSelect)
    
    const button = wrapper.find('button')
    expect(button.exists()).toBe(true)
  })

  it('button has the correct styling', async () => {
    const wrapper = await mountSuspended(ColorModeSelect)
    
    const button = wrapper.find('button')
    expect(button.classes()).toContain('rounded-md')
  })

  it('renders an icon element', async () => {
    const wrapper = await mountSuspended(ColorModeSelect)
    
    // Check for icon span element
    const icon = wrapper.find('.iconify')
    expect(icon.exists()).toBe(true)
  })
})
