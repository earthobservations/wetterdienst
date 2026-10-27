import { mountSuspended } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '~/app.vue'

// The tags the page puts in its own head (GH-3497): title, description, canonical link, og and twitter tags, `lang`,
// and `noindex` for the pages that are not for a search. The server writes the same into the shell for a crawler that
// runs no script (tests/unit/seo.test.ts); these are what the script leaves there once it has run.

const SITE = 'https://wetterdienst.eobs.org'

function metaContent(selector: string): string[] {
  return [...document.head.querySelectorAll<HTMLMetaElement>(selector)].map(element => element.content)
}

async function openApp(path: string) {
  const router = useRouter()
  await router.push(path)
  await mountSuspended(App)
  await nextTick()
  await nextTick()
}

async function useLocale(code: string) {
  await useNuxtApp().$i18n.setLocale(code as 'de')
}

describe('the head of the page', () => {
  beforeEach(async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ version: '0.0.0' }), { status: 200 }))
    await useLocale('en')
  })

  it('describes the site on the home page, with the sentence that says what it is as the title', async () => {
    await openApp('/')

    await vi.waitFor(() => expect(document.title).toBe('Wetterdienst – open weather and climate data from national weather services'))
    expect(metaContent('meta[name="description"]')).toEqual([
      'Open weather and climate data from national weather services, in one format: explorer, forecast, climate stripes, REST API and MCP server. Open source and free.',
    ])
    expect(document.head.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(`${SITE}/`)
    expect(document.documentElement.lang).toBe('en')
  })

  it('names a page and describes it, and gives it its own canonical link', async () => {
    await openApp('/glossary')

    expect(document.title).toBe('Glossary - Wetterdienst')
    expect(metaContent('meta[name="description"]')).toEqual([
      'What each weather and climate parameter measures and the unit its values come back in, searchable by name and quantity.',
    ])
    expect(document.head.querySelectorAll('link[rel="canonical"]')).toHaveLength(1)
    expect(document.head.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(`${SITE}/glossary`)
    expect(metaContent('meta[name="robots"]')).toEqual([])
  })

  it('sets the og and twitter tags of the page, once each', async () => {
    await openApp('/about')

    expect(metaContent('meta[property="og:title"]')).toEqual(['About - Wetterdienst'])
    expect(metaContent('meta[property="og:description"]')).toEqual(['About the open-source project Wetterdienst and the people who maintain it.'])
    expect(metaContent('meta[property="og:url"]')).toEqual([`${SITE}/about`])
    expect(metaContent('meta[property="og:type"]')).toEqual(['website'])
    expect(metaContent('meta[property="og:site_name"]')).toEqual(['Wetterdienst'])
    expect(metaContent('meta[property="og:locale"]')).toEqual(['en_GB'])
    expect(metaContent('meta[property="og:image"]')).toEqual([`${SITE}/apple-touch-icon.png`])
    expect(metaContent('meta[name="twitter:card"]')).toEqual(['summary'])
    expect(metaContent('meta[name="twitter:title"]')).toEqual(['About - Wetterdienst'])
    expect(metaContent('meta[name="twitter:description"]')).toEqual(['About the open-source project Wetterdienst and the people who maintain it.'])
    expect(metaContent('meta[name="twitter:image"]')).toEqual([`${SITE}/apple-touch-icon.png`])
  })

  it('is in the language of the visitor', async () => {
    await useLocale('de')
    await openApp('/stripes')

    expect(document.title).toBe('Klimastreifen - Wetterdienst')
    expect(metaContent('meta[name="description"]')).toEqual(['Klimastreifen für Temperatur oder Niederschlag einer DWD-Station.'])
    expect(metaContent('meta[property="og:locale"]')).toEqual(['de_DE'])
    expect(document.documentElement.lang).toBe('de')
  })

  it('asks for the widget and the settings to be left out of the index, and names no canonical link for them', async () => {
    // `/Widget` is the widget to the router as well
    for (const path of ['/widget', '/settings', '/Widget', '/SETTINGS']) {
      await openApp(path)
      expect(metaContent('meta[name="robots"]'), path).toEqual(['noindex'])
      expect(document.head.querySelector('link[rel="canonical"]'), path).toBeNull()
    }
  })

  it('takes the address from the setting, so an instance of its own names itself', async () => {
    const config = useRuntimeConfig().public
    const before = config.siteUrl
    config.siteUrl = 'https://weather.example.org'
    try {
      // the address is read when the app is set up
      await openApp('/api')
      expect(document.head.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe('https://weather.example.org/api')
      expect(metaContent('meta[property="og:url"]')).toEqual(['https://weather.example.org/api'])
    }
    finally {
      config.siteUrl = before
    }
  })

  it('has no canonical link on a path that is no page of the index, and not an empty one', async () => {
    await openApp('/providers/dwd')

    expect(document.head.querySelector('link[rel="canonical"]')).toBeNull()
    expect(metaContent('meta[name="description"]')).toHaveLength(1)
  })
})
