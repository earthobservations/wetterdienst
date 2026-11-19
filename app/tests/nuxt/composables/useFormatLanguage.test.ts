import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { useFormatLanguage } from '~/composables/useFormatLanguage'

// The language `Intl` and `toLocale*String` are handed: the locale's tag, not the app's code (GH-4007). A bare `lb` or
// `de-hh` is no language a browser has data for, and Chrome then writes the system's.
async function harness() {
  return mountSuspended(defineComponent({
    setup: () => ({ language: useFormatLanguage(), setLocale: useI18n().setLocale }),
    render: () => h('div'),
  }))
}

let wrapper: Awaited<ReturnType<typeof harness>> | undefined

async function languageOf(code: string) {
  wrapper = await harness()
  await (wrapper.vm as any).setLocale(code)
  return (wrapper.vm as any).language as string
}

afterEach(async () => {
  vi.restoreAllMocks()
  await (wrapper?.vm as any)?.setLocale('en')
  wrapper?.unmount()
  wrapper = undefined
})

describe('the language for Intl', () => {
  it.each([
    ['en', 'en-GB'],
    ['de', 'de-DE'],
    ['de-hh', 'de-DE'],
    ['da', 'da-DK'],
    ['lb', 'lb-LU'],
  ])('is the tag of %s: %s', async (code, tag) => {
    expect(await languageOf(code)).toBe(tag)
  })

  it('is German for Luxembourgish where the browser has no data for it', async () => {
    const supported = Intl.DateTimeFormat.supportedLocalesOf.bind(Intl.DateTimeFormat)
    vi.spyOn(Intl.DateTimeFormat, 'supportedLocalesOf').mockImplementation((languages, options) =>
      supported(languages, options).filter(tag => !String(tag).startsWith('lb')))
    expect(await languageOf('lb')).toBe('de-LU')
  })

  it('follows the locale as it changes', async () => {
    wrapper = await harness()
    await (wrapper.vm as any).setLocale('da')
    expect((wrapper.vm as any).language).toBe('da-DK')
    await (wrapper.vm as any).setLocale('de-hh')
    expect((wrapper.vm as any).language).toBe('de-DE')
  })
})
