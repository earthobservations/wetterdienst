import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { OPERATOR } from '../../app/utils/operator'
import { privacy as de } from '../../i18n/privacy/de'
import { privacy as en } from '../../i18n/privacy/en'

// The privacy policy is written twice, in German (binding) and in English, outside the eleven interface
// catalogs (i18n/privacy/). These hold the two to each other, and the text to what it must not do.

const texts = { de, en }

// nuxt.config.ts relies on the `defineNuxtConfig` auto-import and imports the tailwind vite plugin: stub both
// so the raw config object can be imported in a plain node environment (as security-headers.test.ts does)
vi.mock('@tailwindcss/vite', () => ({ default: () => ({ name: 'tailwindcss-stub' }) }))

function allText(policy: typeof de): string {
  return JSON.stringify(policy)
}

describe('privacy policy texts', () => {
  it('have the same sections in the same order, each with the same parts', () => {
    expect(en.sections.map(s => s.id)).toEqual(de.sections.map(s => s.id))
    for (const [index, section] of de.sections.entries()) {
      const other = en.sections[index]!
      expect(other.icon, section.id).toBe(section.icon)
      expect(other.paragraphs.length, `${section.id} paragraphs`).toBe(section.paragraphs.length)
      expect(other.items?.length, `${section.id} items`).toBe(section.items?.length)
      expect(other.link, `${section.id} link`).toEqual(section.link)
    }
  })

  it('say in the translation, and only there, that the German one binds', () => {
    expect(de.binding).toBeUndefined()
    expect(en.binding).toContain('legally binding')
  })

  it.each(Object.keys(texts))('have no empty string in %s', (code) => {
    const policy = texts[code as keyof typeof texts]
    const strings = [
      policy.title,
      policy.updated,
      policy.intro,
      ...Object.values(policy.controller),
      ...policy.sections.flatMap(s => [s.title, ...s.paragraphs, ...(s.items ?? [])]),
    ]
    expect(strings.filter(s => !s.trim())).toEqual([])
  })

  it.each(Object.keys(texts))('do not repeat the operator\'s address in %s: the page reads it from one place', (code) => {
    const text = allText(texts[code as keyof typeof texts])
    for (const value of [OPERATOR.street, OPERATOR.city, OPERATOR.email, OPERATOR.name])
      expect(text).not.toContain(value)
  })

  it.each(Object.keys(texts))('name every third party that the map and the About page load images from in %s', (code) => {
    const text = allText(texts[code as keyof typeof texts])
    for (const host of ['tile.openstreetmap.org', 'avatars.githubusercontent.com'])
      expect(text, host).toContain(host)
  })

  it.each(Object.keys(texts))('name the cookie and the localStorage keys the app writes in %s', (code) => {
    const text = allText(texts[code as keyof typeof texts])
    for (const key of ['wd_lang', 'wd_settings', 'meteogram.view', 'wd-place', 'nuxt-color-mode'])
      expect(text, key).toContain(key)
  })

  it.each(Object.keys(texts))('state no retention period in days in %s: none is configured, only the cookie has a lifetime', (code) => {
    expect(allText(texts[code as keyof typeof texts])).not.toMatch(/\b(?!365\b)\d+\s*(days|Tage)\b/)
  })

  describe('and the hosts the Content Security Policy allows', () => {
    beforeEach(() => {
      vi.stubGlobal('defineNuxtConfig', (config: any) => config)
    })

    afterEach(() => {
      vi.unstubAllGlobals()
      vi.resetModules()
    })

    /** The hosts a policy's sources name: `https://host` and `https://*.host`, without scheme and wildcard */
    function cspHosts(policy: Record<string, string[]>): string[] {
      return [...new Set(Object.values(policy).flat().flatMap((source) => {
        const match = /^https:\/\/(?:\*\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)$/i.exec(source)
        return match ? [match[1]!] : []
      }))].sort()
    }

    /** The hosts the items of the third-parties section write */
    function namedHosts(policy: typeof de): string[] {
      const items = policy.sections.find(section => section.id === 'third-parties')!.items ?? []
      return [...new Set(items.flatMap(item => item.match(/\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b/gi) ?? []))].sort()
    }

    it.each(Object.keys(texts))('are exactly the hosts the third-parties section of %s names, none more, none fewer', async (code) => {
      vi.resetModules()
      const config = (await import('../../nuxt.config')).default as any
      const allowed = cspHosts(config.security.headers.contentSecurityPolicy)

      expect(allowed.length).toBeGreaterThan(0)
      // the text names the host as the policy writes it (a `*.tile.openstreetmap.org` is written `tile.openstreetmap.org`)
      expect(namedHosts(texts[code as keyof typeof texts])).toEqual(allowed)
    })
  })
})
