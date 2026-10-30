import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { EXTERNAL, inSection, PROJECT, REFERENCE, sectionOf, SECTIONS, TOOLS } from '../../app/utils/sections'

// The places of the app as the navigation shows them (GH-3518): one list for the header, the tab bar, the menu sheet,
// the search, the footer and the head of each page.

const APP = join(__dirname, '..', '..')
const en = JSON.parse(readFileSync(join(APP, 'i18n', 'locales', 'en.json'), 'utf8'))
const message = (key: string) => key.split('.').reduce<any>((node, part) => node?.[part], en)

describe('the sections', () => {
  it('are the four tools, each with a tile of the logo of its own', () => {
    expect(TOOLS.map(tool => tool.to)).toEqual(['/meteogram', '/explorer', '/stripes', '/history'])
    expect(new Set(TOOLS.map(tool => tool.tile)).size).toBe(4)
  })

  it('are each a page of the app', () => {
    for (const section of SECTIONS) {
      const page = section.to === '/providers' ? 'providers/index' : section.to.slice(1)
      expect(readFileSync(join(APP, 'app', 'pages', `${page}.vue`), 'utf8').length, section.to).toBeGreaterThan(0)
    }
  })

  it('name themselves and say what they are for in the catalog', () => {
    for (const section of [...SECTIONS, ...EXTERNAL]) {
      expect(typeof message(section.label), section.label).toBe('string')
      if ('description' in section && section.description)
        expect(typeof message(section.description), section.description).toBe('string')
    }
    for (const group of ['tools', 'reference', 'project'])
      expect(typeof message(`shell.${group}`)).toBe('string')
  })

  it('are told by their path, a page below one included', () => {
    expect(sectionOf('/providers/dwd')).toBe(REFERENCE[0])
    expect(sectionOf('/meteogram')).toBe(TOOLS[0])
    expect(sectionOf('/settings')).toBe(PROJECT.find(section => section.key === 'settings'))
    expect(sectionOf('/')).toBeUndefined()
    expect(sectionOf('/impressum')).toBeUndefined()
    // a path that only starts with the same letters is not the section
    expect(inSection({ to: '/api' }, '/apiary')).toBe(false)
  })

  it('send to an outside place only over https', () => {
    for (const link of EXTERNAL)
      expect(link.to).toMatch(/^https:\/\//)
  })
})
