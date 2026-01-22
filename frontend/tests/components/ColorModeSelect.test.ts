import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import ColorModeSelect from '~/components/ColorModeSelect.vue'

describe('colorModeSelect', () => {
  it('should render the component', async () => {
    const component = await mountSuspended(ColorModeSelect)
    expect(component.html()).toBeTruthy()
  })
})
