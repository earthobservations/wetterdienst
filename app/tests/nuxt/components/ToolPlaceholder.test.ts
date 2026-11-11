import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import ToolPlaceholder from '~/components/ToolPlaceholder.vue'
import { TOOLS } from '~/utils/sections'
import { messagesOf } from '../fixtures/catalogs'

// The placeholder of a tool before it has a result (GH-3850): one component, the tool's own tile from
// utils/sections.ts, and one sentence that names no direction

// the catalog as written: the nuxt environment hands the imported file over compiled
const placeholders = messagesOf('en', 'toolPlaceholder')

// the tools that have a placeholder are the ones the catalog has a sentence for, so a tool that is given one (the map,
// GH-3650) is held to the same tests with no change here
const WITH_PLACEHOLDER = Object.keys(placeholders)

describe('toolPlaceholder', () => {
  it('has a sentence for tools of utils/sections.ts only, and for the four that show one', () => {
    expect(WITH_PLACEHOLDER.filter(key => !TOOLS.some(tool => tool.key === key))).toEqual([])
    expect(WITH_PLACEHOLDER).toEqual(expect.arrayContaining(['forecast', 'explorer', 'stripes', 'history']))
  })

  it.each(WITH_PLACEHOLDER)('marks %s with the tile and the glyph of utils/sections.ts', async (key) => {
    const section = TOOLS.find(tool => tool.key === key)!
    const wrapper = await mountSuspended(ToolPlaceholder, { props: { tool: key } })
    const root = wrapper.find('[data-testid="tool-placeholder"]')
    expect(root.attributes('data-tool')).toBe(key)
    const tile = root.find('.tile')
    expect(tile.classes(), 'the tool\'s own tile').toContain(`tile-${section.tile}`)
    expect(tile.attributes('aria-hidden'), 'a picture beside a sentence, hidden from assistive technology').toBe('true')
    expect(tile.html(), 'the tool\'s own glyph').toContain(section.icon.replace('i-ph-', ''))
  })

  it('draws the frame of the dashed placeholder, the same for every tool', async () => {
    const frames = await Promise.all(WITH_PLACEHOLDER.map(async (key) => {
      const wrapper = await mountSuspended(ToolPlaceholder, { props: { tool: key } })
      return wrapper.find('[data-testid="tool-placeholder"]').classes().sort().join(' ')
    }))
    expect(new Set(frames).size).toBe(1)
    expect(frames[0]).toContain('border-dashed')
  })

  it.each(WITH_PLACEHOLDER)('says one sentence for %s, in which no direction is named', async (key) => {
    const wrapper = await mountSuspended(ToolPlaceholder, { props: { tool: key } })
    const text = wrapper.text()
    expect(text).toBe(placeholders[key])
    expect(text).not.toMatch(/\b(above|below|left|right)\b/i)
    expect(text, 'both ways in').toMatch(/search/i)
    expect(text, 'both ways in').toMatch(/map/i)
  })

  it('names the point of the explorer, whose interpolation takes one in place of a station', () => {
    expect(placeholders.explorer).toMatch(/\bpoint\b/i)
  })

  it('says nothing of the backend', () => {
    expect(placeholders.history!).not.toMatch(/backend/i)
  })

  it('refuses a key that is no tool', async () => {
    await expect(mountSuspended(ToolPlaceholder, { props: { tool: 'nonsense' } })).rejects.toThrow(/no tool/)
  })
})
