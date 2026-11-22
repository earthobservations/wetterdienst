import type { PaletteGroup } from '../../app/utils/palette'
import type { Hit } from '../../app/utils/search-index'
import { describe, expect, it } from 'vitest'
import { countsByGroup, filterGroups, fold, GROUP_LIMITS, GROUP_ORDER, hitDescription, itemOfHit, limitCounted, limitItems, orderGroups, scoreOf } from '../../app/utils/palette'

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

// The groups of the words of the app (GH-3790)

const hit = (title: string, to: string, extra: Partial<Hit> = {}): Hit => ({ kind: 'measurement', title, context: '', summary: '', to, score: 1, ...extra })

describe('the order of the groups', () => {
  const group = (id: string, ...labels: string[]): PaletteGroup => ({ id, label: id, items: labels.map(label => item(label)) })

  it('puts a point first, then the stations, then the pages, then the words of the app, then the actions', () => {
    const shuffled = [group('language', 'x'), group('glossary', 'x'), group('project', 'x'), group('station-ids', 'x'), group('station-ids-icao', 'x'), group('place', 'x'), group('settings', 'x'), group('tools', 'x'), group('stations-ghcn', 'x'), group('stations-forecast', 'x'), group('stations-measured', 'x'), group('questions', 'x'), group('measurement', 'x'), group('method', 'x'), group('reference', 'x'), group('providers', 'x'), group('theme', 'x')]
    expect(orderGroups(shuffled).map(entry => entry.id)).toEqual([...GROUP_ORDER])
  })

  it('leaves out a group with no items, and puts one that is not named last, keeping the order of those it does not know', () => {
    const ordered = orderGroups([group('other-b', 'x'), group('empty'), group('tools', 'x'), group('other-a', 'x'), group('place', 'x')])
    expect(ordered.map(entry => entry.id)).toEqual(['place', 'tools', 'other-b', 'other-a'])
  })
})

describe('the few results of a group', () => {
  const items = ['a', 'b', 'c', 'd', 'e', 'f'].map(label => item(label))
  const more = (hidden: number) => ({ id: 'more', label: `${hidden} more`, more: true })

  it('shows all of them up to the limit', () => {
    expect(limitItems(items.slice(0, 3), 3, more)).toHaveLength(3)
  })

  it('shows the one that is just over the limit, since "1 more" is no shorter than it', () => {
    expect(limitItems(items.slice(0, 4), 3, more).map(entry => entry.label)).toEqual(['a', 'b', 'c', 'd'])
  })

  it('shows the limit and a last item that says how many are left, and leads to the page that has them', () => {
    const limited = limitItems(items, 3, more)
    expect(limited.map(entry => entry.label)).toEqual(['a', 'b', 'c', '3 more'])
    expect(limited.at(-1)!.more).toBe(true)
  })

  it('cuts at the limit where the group has no page of its own to lead to', () => {
    expect(limitItems(items, 3).map(entry => entry.label)).toEqual(['a', 'b', 'c'])
  })

  it('has a limit for each group of the words of the app and for the stations of each network', () => {
    for (const id of ['stations', 'questions', 'measurement', 'method', 'glossary', 'settings', 'project'])
      expect(GROUP_LIMITS[id], id).toBeGreaterThan(0)
  })
})

describe('the few stations of a network, whose total the server counted', () => {
  // the server gives the best limit + 1 of them, however many there are
  const best = ['a', 'b', 'c', 'd'].map(label => item(label))
  const more = (hidden: number) => ({ id: 'more', label: `${hidden} more`, more: true })

  it('shows all of them where there are no more than the limit and one', () => {
    expect(limitCounted(best.slice(0, 2), 2, 3, more).map(entry => entry.label)).toEqual(['a', 'b'])
    expect(limitCounted(best, 4, 3, more).map(entry => entry.label)).toEqual(['a', 'b', 'c', 'd'])
  })

  it('shows the limit and says how many there are besides, from the total and not from the few it was given', () => {
    const limited = limitCounted(best, 133, 3, more)
    expect(limited.map(entry => entry.label)).toEqual(['a', 'b', 'c', '130 more'])
    expect(limited.at(-1)!.more).toBe(true)
  })

  it('cuts at the limit where there is nowhere to lead to', () => {
    expect(limitCounted(best, 133, 3).map(entry => entry.label)).toEqual(['a', 'b', 'c'])
  })
})

describe('a result of the words of the app', () => {
  it('leads to its page and anchor, with the part of the page and what it says under its name', () => {
    const found = itemOfHit(hit('Wind', '/measurement#wind', { context: 'How it is measured', summary: 'Anemometers measure the speed' }), 'i-ph-ruler')
    expect(found).toMatchObject({ label: 'Wind', description: 'How it is measured · Anemometers measure the speed', to: '/measurement#wind', icon: 'i-ph-ruler' })
    expect(found.external).toBeUndefined()
    expect(found.run).toBeUndefined()
  })

  it('has one line under its name from what it has, none where it has nothing', () => {
    expect(hitDescription({ context: '', summary: 'Only a summary' })).toBe('Only a summary')
    expect(hitDescription({ context: 'Units', summary: '' })).toBe('Units')
    expect(itemOfHit(hit('Bare', '/x'), 'i-ph-ruler').description).toBeUndefined()
  })

  it('is told apart by its target: two parts of one entry are one result', () => {
    expect(itemOfHit(hit('A', '/measurement#a'), 'i').id).toBe('hit-/measurement#a')
  })
})

describe('what the live region says of the groups', () => {
  it('names each group with the number of its results, not counting the option that leads on', () => {
    const groups: PaletteGroup[] = [
      { id: 'glossary', label: 'Glossary', items: [item('a'), item('b'), { id: 'more', label: '5 more', more: true }] },
      { id: 'settings', label: 'Settings', items: [item('c')] },
    ]
    expect(countsByGroup(groups, (name, count) => `${name}: ${count}`)).toBe('Glossary: 2. Settings: 1')
  })
})
