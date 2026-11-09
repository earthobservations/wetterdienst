import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { EXTERNAL, inSection, MAP_TOOL, PROJECT, REFERENCE, sectionOf, SECTIONS, TOOLS } from '../../app/utils/sections'
import { barKeys, DEFAULT_TOOL_ORDER, menuKeys } from '../../app/utils/tab-bar'

// The places of the app as the navigation shows them (GH-3518): one list for the header, the tab bar, the menu sheet,
// the search, the footer and the head of each page.

const APP = join(__dirname, '..', '..')
const en = JSON.parse(readFileSync(join(APP, 'i18n', 'locales', 'en.json'), 'utf8'))
const message = (key: string) => key.split('.').reduce<any>((node, part) => node?.[part], en)

describe('the sections', () => {
  it('are the five tools, each with a tile of its own', () => {
    expect(TOOLS.map(tool => tool.to)).toEqual(['/meteogram', '/explorer', '/stripes', '/history', '/map'])
    expect(new Set(TOOLS.map(tool => tool.tile)).size).toBe(5)
    // the map's is the fifth, violet one (GH-3650)
    expect(MAP_TOOL).toBe(TOOLS[4])
    expect(MAP_TOOL.tile).toBe('map')
  })

  it('are in the tab bar of the narrow layout as the reader chose, with the four it had before the map as the default', () => {
    // five tools and the Menu are six items, more than a tab bar holds (GH-3650); which four is a choice (GH-3846)
    expect(barKeys(DEFAULT_TOOL_ORDER)).toEqual(['forecast', 'explorer', 'stripes', 'history'])
    expect(menuKeys(DEFAULT_TOOL_ORDER)).toEqual(['map'])
    // every tool is one or the other, so that none is lost from the narrow layout
    expect([...barKeys(DEFAULT_TOOL_ORDER), ...menuKeys(DEFAULT_TOOL_ORDER)].sort()).toEqual(TOOLS.map(tool => tool.key).sort())
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
