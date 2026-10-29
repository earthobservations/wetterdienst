import type { PaletteGroup } from '../../app/utils/palette'
import { describe, expect, it } from 'vitest'
import { filterGroups, fold, scoreOf } from '../../app/utils/palette'

// What the search finds (GH-3518, AppCommandPalette.vue)

const item = (label: string, description?: string, keywords?: string) => ({ id: label, label, description, keywords })

describe('the matching of the search', () => {
  it('ignores case and accents', () => {
    expect(fold('München Čeština')).toBe('munchen cestina')
    expect(scoreOf(item('Čeština'), 'cest')).not.toBeNull()
    expect(scoreOf(item('Klimastreifen'), 'KLIMA')).not.toBeNull()
  })

  it('finds by the description and the keywords, and wants every word', () => {
    expect(scoreOf(item('Glossary', 'What each parameter measures'), 'parameter')).not.toBeNull()
    expect(scoreOf(item('DWD', 'German Weather Service', 'dwd germany'), 'germany')).not.toBeNull()
    expect(scoreOf(item('Glossary', 'What each parameter measures'), 'parameter unit')).toBeNull()
  })

  it('puts a name that starts with the text before one that holds it, and that before a description', () => {
    const start = scoreOf(item('Forecast'), 'fore')!
    const word = scoreOf(item('Weather forecast'), 'fore')!
    const inside = scoreOf(item('Beforehand'), 'fore')!
    const described = scoreOf(item('Stripes', 'Your region as a forecast'), 'fore')!
    expect(start).toBeGreaterThan(word)
    expect(word).toBeGreaterThan(inside)
    expect(inside).toBeGreaterThan(described)
  })

  it('keeps every item for no text, and drops the groups that have none left', () => {
    const groups: PaletteGroup[] = [
      { id: 'a', label: 'A', items: [item('Forecast'), item('Explorer')] },
      { id: 'b', label: 'B', items: [item('Glossary')] },
    ]
    expect(filterGroups(groups, '  ')).toEqual(groups)
    const found = filterGroups(groups, 'gloss')
    expect(found.map(group => group.id)).toEqual(['b'])
  })

  it('orders the items of a group by how well they match, and keeps their order where they match alike', () => {
    const groups: PaletteGroup[] = [{ id: 'a', label: 'A', items: [item('Weather forecast'), item('Forecast'), item('Forest')] }]
    expect(filterGroups(groups, 'fore')[0]!.items.map(entry => entry.label)).toEqual(['Forecast', 'Forest', 'Weather forecast'])
  })
})
