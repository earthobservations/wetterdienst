import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import ProviderMark from '~/components/ProviderMark.vue'

// The country of a provider, as the code the backend gives (GH-3518): never stray letters.
async function mark(country: string | null) {
  return mountSuspended(ProviderMark, { props: { country } })
}

describe('providerMark', () => {
  it.each(['DE', 'GB', 'US'])('writes the code %s', async (code) => {
    const wrapper = await mark(code)

    expect(wrapper.text()).toBe(code)
    expect(wrapper.attributes('aria-hidden')).toBe('true')
  })

  it('draws a globe, and no letters, for a provider of several countries', async () => {
    const wrapper = await mark(null)

    expect(wrapper.text()).toBe('')
    expect(wrapper.find('[class*="globe-hemisphere-west"]').exists()).toBe(true)
  })

  it.each(['', 'de', 'DEU', 'D1', ' D'])('draws nothing for %j, which is no code', async (code) => {
    const wrapper = await mark(code)

    expect(wrapper.text()).toBe('')
    expect(wrapper.find('span').exists()).toBe(false)
  })
})
