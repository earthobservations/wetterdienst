import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData } from '#app'
import ProviderCredit from '~/components/ProviderCredit.vue'
import { providersAnswer } from '../fixtures/providers'

// The provider's credit line, and under it the processing note (GH-3799, GH-4255): the one block every place that shows provider data uses.

const mounted: Array<{ unmount: () => void }> = []
async function mountCredit(props: Record<string, unknown>) {
  const wrapper = await mountSuspended(ProviderCredit, { props, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
const NOTE = 'Processed by wetterdienst: the provider\'s data was reshaped into a uniform table, and its units converted where they differ.'
const line = (wrapper: Awaited<ReturnType<typeof mountCredit>>) => wrapper.find('[data-testid="provider-credit-line"]')

beforeEach(() => {
  clearNuxtData('providers')
  registerEndpoint('/api/providers', () => providersAnswer())
})
afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
})

describe('providerCredit', () => {
  it('says the credit line of the provider and its licence as a link, from the list of providers, and the note directly under it', async () => {
    const wrapper = await mountCredit({ provider: 'dwd' })
    await vi.waitFor(() => expect(line(wrapper).exists()).toBe(true))
    expect(line(wrapper).text()).toBe('Source: Deutscher Wetterdienst, Creative Commons Attribution 4.0 International')
    const link = line(wrapper).find('a')
    expect(link.attributes('href')).toBe('https://creativecommons.org/licenses/by/4.0/')
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toContain('noopener')
    const note = wrapper.find('[data-testid="processing-note"]')
    expect(note.text()).toBe(NOTE)
    expect(note.element.previousElementSibling).toBe(line(wrapper).element)
  })

  it('adds the sentence of an estimate to the note for values that were calculated', async () => {
    const wrapper = await mountCredit({ provider: 'dwd', derived: true })
    expect(wrapper.find('[data-testid="processing-note"]').text()).toBe(`${NOTE} The values were selected or calculated from the provider's readings.`)
  })

  it('says the note alone for a provider that states neither a credit line nor a licence, and the fallback line where one is given', async () => {
    const alone = await mountCredit({ provider: 'aemet' })
    await vi.waitFor(() => expect(alone.find('[data-testid="processing-note"]').exists()).toBe(true))
    expect(line(alone).exists()).toBe(false)
    const withFallback = await mountCredit({ provider: 'aemet', fallback: 'Source: AEMET' })
    expect(line(withFallback).text()).toBe('Source: AEMET')
  })

  it('takes the terms of an answer instead of the list\'s, and does not make a link of an address that is not http(s)', async () => {
    const wrapper = await mountCredit({ provider: 'dwd', terms: { attribution: 'Source: NOAA', license: { name: 'CC0', url: 'javascript:alert(1)' } } })
    expect(line(wrapper).text()).toBe('Source: NOAA, CC0')
    expect(line(wrapper).find('a').exists()).toBe(false)
  })

  it('says only the licence where there is no credit line, without a separator', async () => {
    const wrapper = await mountCredit({ terms: { attribution: null, license: { name: 'CC0', url: 'https://example.org/cc0' } } })
    expect(line(wrapper).text()).toBe('CC0')
    expect(line(wrapper).find('a').attributes('href')).toBe('https://example.org/cc0')
  })

  it('is smaller where it is compact, for the widget, and keeps the class it is given', async () => {
    const wrapper = await mountCredit({ provider: 'dwd', compact: true, class: 'px-1' })
    await vi.waitFor(() => expect(line(wrapper).exists()).toBe(true))
    expect(line(wrapper).classes()).toContain('text-xs')
    expect(wrapper.find('[data-testid="processing-note"]').classes()).toContain('text-[11px]')
    expect(wrapper.classes()).toContain('px-1')
    const normal = await mountCredit({ provider: 'dwd' })
    await vi.waitFor(() => expect(line(normal).exists()).toBe(true))
    expect(line(normal).classes()).toContain('text-sm')
  })
})
