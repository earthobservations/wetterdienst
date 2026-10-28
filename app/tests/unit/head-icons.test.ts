import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// nuxt.config.ts relies on the `defineNuxtConfig` auto-import and imports the tailwind vite plugin: stub both so
// the raw config object can be imported in a plain node environment (as security-headers.test.ts does).
vi.mock('@tailwindcss/vite', () => ({ default: () => ({ name: 'tailwindcss-stub' }) }))

const APP = join(__dirname, '..', '..')

function isFileOfPublic(href: string): boolean {
  return href.startsWith('/') && existsSync(join(APP, 'public', href.slice(1)))
}

describe('the icon of the app (GH-3431)', () => {
  beforeEach(() => {
    vi.stubGlobal('defineNuxtConfig', (config: any) => config)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('links the SVG, the 32 px ICO and the iOS icon, each a file of public/', async () => {
    const config = (await import('../../nuxt.config')).default as any
    const links: { rel: string, href: string }[] = config.app.head.link
    expect(links.map(link => link.rel)).toEqual(['icon', 'icon', 'apple-touch-icon'])
    for (const link of links)
      expect(isFileOfPublic(link.href), link.href).toBe(true)
  })

  it('shows, in the navigation and the top bar of the app and in the widget, and on the page of the API reference, files of public/', () => {
    const sources = ['app/components/AppNav.vue', 'app/layouts/default.vue', 'app/pages/widget.vue', 'server/routes/docs.ts']
    for (const source of sources) {
      const text = readFileSync(join(APP, source), 'utf8')
      const hrefs = [...text.matchAll(/(?:<img src|<link rel="icon"[^>]*?href)="(\/[^"]+)"/g)].map(match => match[1]!)
      expect(hrefs.length, source).toBeGreaterThan(0)
      for (const href of hrefs)
        expect(isFileOfPublic(href), `${source}: ${href}`).toBe(true)
    }
  })

  it('has an ICO that is one, not a PNG under another name', () => {
    const head = readFileSync(join(APP, 'public', 'favicon.ico')).subarray(0, 4)
    expect([...head]).toEqual([0, 0, 1, 0])
  })
})
