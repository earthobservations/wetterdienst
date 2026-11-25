import { describe, expect, it } from 'vitest'
import { TOOLS } from '../../app/utils/sections'
import { BAR_SIZE, barKeys, DEFAULT_TOOL_ORDER, describeMove, HEADER_SIZE, isDefaultOrder, menuKeys, moveTool, normalizeToolOrder, slotAt } from '../../app/utils/tab-bar'

// The choice of the tools in the phone's tab bar (GH-3846): a list of all the tools of which the first four are the
// bar. Whatever is stored or moved, the list is valid: all the tools once each, four above the line (GH-3788: the Map is the sixth tool,
// so two are below it by default).

const DEFAULT = ['forecast', 'explorer', 'stripes', 'radar', 'history', 'map']

describe('the default', () => {
  it('is the tools in the order of the header: the four there were before the map, the map and the radar below the line', () => {
    expect(DEFAULT_TOOL_ORDER).toEqual(DEFAULT)
    expect(DEFAULT_TOOL_ORDER).toEqual(TOOLS.map(tool => tool.key))
    expect(barKeys(DEFAULT_TOOL_ORDER)).toEqual(['forecast', 'explorer', 'stripes', 'radar'])
    expect(menuKeys(DEFAULT_TOOL_ORDER)).toEqual(['history', 'map'])
    expect(BAR_SIZE).toBe(4)
    expect(isDefaultOrder(DEFAULT)).toBe(true)
    expect(isDefaultOrder(['history', ...DEFAULT.slice(0, 4), 'map'])).toBe(false)
  })
})

describe('normalizeToolOrder', () => {
  it('keeps a valid order as it is', () => {
    expect(normalizeToolOrder(['map', 'history', 'radar', 'explorer', 'forecast', 'stripes'])).toEqual(['map', 'history', 'radar', 'explorer', 'forecast', 'stripes'])
  })

  it.each([undefined, null, 'forecast', 42, {}, { 0: 'history' }, true])('is the default for what is no list: %j', (raw) => {
    expect(normalizeToolOrder(raw)).toEqual(DEFAULT)
  })

  it('is the default for an empty list', () => {
    expect(normalizeToolOrder([])).toEqual(DEFAULT)
  })

  it('ignores a key that names no tool (one that was removed, or never was), and anything that is no key', () => {
    expect(normalizeToolOrder(['history', 'satellite', 'forecast', 7, null, {}, 'explorer', 'stripes', 'radar']))
      .toEqual(['history', 'forecast', 'explorer', 'stripes', 'radar', 'map'])
    expect(normalizeToolOrder(['satellite', 'weather'])).toEqual(DEFAULT)
  })

  it('keeps a key that comes twice at its first place', () => {
    expect(normalizeToolOrder(['history', 'history', 'stripes', 'history', 'forecast', 'stripes'])).toEqual(['history', 'stripes', 'forecast', 'explorer', 'radar', 'map'])
  })

  it('fills a list with too few tools from the default, after the ones it names', () => {
    expect(normalizeToolOrder(['history'])).toEqual(['history', 'forecast', 'explorer', 'stripes', 'radar', 'map'])
    expect(normalizeToolOrder(['radar', 'stripes'])).toEqual(['radar', 'stripes', 'forecast', 'explorer', 'history', 'map'])
    // the bar of a list that named only the four: the others are below the line, where a tool added later goes
    expect(normalizeToolOrder(['stripes', 'radar', 'explorer', 'forecast'])).toEqual(['stripes', 'radar', 'explorer', 'forecast', 'history', 'map'])
    // a list saved before the radar existed (GH-3788) keeps its choice, and the radar is below the line
    expect(normalizeToolOrder(['history', 'radar', 'explorer', 'forecast', 'stripes'])).toEqual(['history', 'radar', 'explorer', 'forecast', 'stripes', 'map'])
  })

  it('always answers every tool once, so that four are above the line', () => {
    for (const raw of [[], ['history'], ['x', 'history', 'history'], [...DEFAULT].reverse(), DEFAULT, [...DEFAULT, ...DEFAULT], 'nope']) {
      const order = normalizeToolOrder(raw)
      expect([...order].sort()).toEqual([...DEFAULT].sort())
      expect(barKeys(order)).toHaveLength(BAR_SIZE)
    }
  })

  it('puts a tool added later below the line and changes nobody\'s choice', () => {
    const known = [...DEFAULT, 'satellite']
    const saved = ['history', 'radar', 'explorer', 'forecast', 'stripes', 'map']
    const order = normalizeToolOrder(saved, known)
    expect(order).toEqual([...saved, 'satellite'])
    expect(barKeys(order)).toEqual(['history', 'radar', 'explorer', 'forecast'])
    expect(menuKeys(order)).toEqual(['stripes', 'map', 'satellite'])
  })

  it('keeps the bar of a choice saved before the Radar was the default (GH-3788): its four stay, and the Radar is below the line', () => {
    const saved = ['forecast', 'explorer', 'stripes', 'history', 'map']
    const order = normalizeToolOrder(saved)
    expect(order).toEqual([...saved, 'radar'])
    expect(barKeys(order)).toEqual(['forecast', 'explorer', 'stripes', 'history'])
    expect(menuKeys(order)).toEqual(['map', 'radar'])
  })

  it('leaves what is given alone', () => {
    const saved = ['history']
    normalizeToolOrder(saved)
    expect(saved).toEqual(['history'])
  })
})

describe('moveTool', () => {
  it('moves a tool inside the bar', () => {
    expect(moveTool(DEFAULT, 0, 2)).toEqual(['explorer', 'stripes', 'forecast', 'radar', 'history', 'map'])
    expect(moveTool(DEFAULT, 3, 0)).toEqual(['radar', 'forecast', 'explorer', 'stripes', 'history', 'map'])
  })

  it('moves one in across the line, which pushes the fourth out: four stay in the bar', () => {
    const next = moveTool(DEFAULT, 4, 0)
    expect(next).toEqual(['history', 'forecast', 'explorer', 'stripes', 'radar', 'map'])
    expect(barKeys(next)).toEqual(['history', 'forecast', 'explorer', 'stripes'])
    expect(menuKeys(next)).toEqual(['radar', 'map'])
    // the same by one step, which is what a button does
    expect(moveTool(DEFAULT, 4, 3)).toEqual(['forecast', 'explorer', 'stripes', 'history', 'radar', 'map'])
  })

  it('moves one out across the line, which pulls the first one below it in', () => {
    const next = moveTool(DEFAULT, 1, 4)
    expect(next).toEqual(['forecast', 'stripes', 'radar', 'history', 'explorer', 'map'])
    expect(barKeys(next)).toEqual(['forecast', 'stripes', 'radar', 'history'])
    expect(moveTool(DEFAULT, 3, 4)).toEqual(['forecast', 'explorer', 'stripes', 'history', 'radar', 'map'])
  })

  it('is no move to the place a tool is at, and clamps to the list', () => {
    expect(moveTool(DEFAULT, 2, 2)).toEqual(DEFAULT)
    expect(moveTool(DEFAULT, 0, 99)).toEqual(['explorer', 'stripes', 'radar', 'history', 'map', 'forecast'])
    expect(moveTool(DEFAULT, 4, -3)).toEqual(['history', 'forecast', 'explorer', 'stripes', 'radar', 'map'])
    expect(moveTool(DEFAULT, 9, 0)).toEqual(DEFAULT)
    expect(moveTool(DEFAULT, -1, 0)).toEqual(DEFAULT)
  })

  it('leaves the order it is given alone, and keeps every tool', () => {
    const before = [...DEFAULT]
    const next = moveTool(before, 4, 0)
    expect(before).toEqual(DEFAULT)
    expect(next).not.toBe(before)
    expect([...next].sort()).toEqual([...DEFAULT].sort())
  })
})

describe('describeMove', () => {
  it('says nothing for a tool that stays where it is', () => {
    expect(describeMove(DEFAULT, DEFAULT, 'stripes')).toBeNull()
    expect(describeMove(DEFAULT, DEFAULT, 'unknown')).toBeNull()
  })

  it('names the new place of a tool moved inside the bar', () => {
    expect(describeMove(DEFAULT, moveTool(DEFAULT, 0, 2), 'forecast')).toEqual({ kind: 'reorderedBar', tool: 'forecast', position: 3, total: 4 })
  })

  it('names the tool a move into the bar pushed out', () => {
    expect(describeMove(DEFAULT, moveTool(DEFAULT, 4, 1), 'history')).toEqual({ kind: 'enteredBar', tool: 'history', position: 2, total: 4, other: 'radar' })
  })

  it('names the tool a move out of the bar pulled in, and its place', () => {
    expect(describeMove(DEFAULT, moveTool(DEFAULT, 0, 4), 'forecast')).toEqual({ kind: 'leftBar', tool: 'forecast', position: 4, total: 4, other: 'history' })
    expect(describeMove(DEFAULT, moveTool(DEFAULT, 3, 4), 'radar')).toEqual({ kind: 'leftBar', tool: 'radar', position: 4, total: 4, other: 'history' })
  })

  it('names the place of a tool moved among those that are only in the Menu', () => {
    expect(describeMove(DEFAULT, moveTool(DEFAULT, 5, 4), 'map', 4)).toEqual({ kind: 'reorderedMenu', tool: 'map', position: 1, total: 2 })
  })
})

describe('slotAt', () => {
  // five rows of 56 px with 8 px between them, and a line between the fourth and the fifth
  const slots = [0, 1, 2, 3, 4].map(index => ({ top: index * 64 + (index === 4 ? 24 : 0), bottom: index * 64 + 56 + (index === 4 ? 24 : 0) }))

  it('is the slot whose middle is nearest', () => {
    expect(slotAt(10, slots)).toBe(0)
    expect(slotAt(28, slots)).toBe(0)
    expect(slotAt(70, slots)).toBe(1)
    expect(slotAt(200, slots)).toBe(3)
    expect(slotAt(300, slots)).toBe(4)
  })

  it('is the first or the last above and below the list', () => {
    expect(slotAt(-500, slots)).toBe(0)
    expect(slotAt(5000, slots)).toBe(4)
  })

  it('changes at the middle between two slots, not at the edge of one', () => {
    // the middles of the fourth and fifth row are 220 and 308: the change is at 264, over the line between them
    expect(slotAt(263, slots)).toBe(3)
    expect(slotAt(265, slots)).toBe(4)
  })
})

describe('the split with a size of its own (GH-3936)', () => {
  const order = ['stripes', 'history', 'radar', 'forecast', 'explorer', 'map']

  it('has the header show all the tools today, so there is no second group', () => {
    expect(HEADER_SIZE).toBe(DEFAULT_TOOL_ORDER.length)
    expect(barKeys(order, HEADER_SIZE)).toEqual(order)
    expect(menuKeys(order, HEADER_SIZE)).toEqual([])
  })

  it('splits the same list wherever the size is, the first `size` and the rest, with nothing lost or twice', () => {
    for (const size of [0, 1, 2, 3, 4, 5, 6, 9]) {
      expect(barKeys(order, size)).toHaveLength(Math.min(size, order.length))
      expect([...barKeys(order, size), ...menuKeys(order, size)]).toEqual(order)
    }
  })

  it('has a smaller size for the header put a second group below it (a later "more tools"), from the one list', () => {
    expect(barKeys(order, 3)).toEqual(['stripes', 'history', 'radar'])
    expect(menuKeys(order, 3)).toEqual(['forecast', 'explorer', 'map'])
  })

  it('has the bar\'s size by default, as before', () => {
    expect(barKeys(order)).toEqual(barKeys(order, BAR_SIZE))
    expect(menuKeys(order)).toEqual(menuKeys(order, BAR_SIZE))
  })

  it('describes a move by the size of the layout: with all the tools in the header, a move never leaves it', () => {
    expect(describeMove(DEFAULT, moveTool(DEFAULT, 4, 0), 'history', HEADER_SIZE)).toEqual({ kind: 'reorderedBar', tool: 'history', position: 1, total: 6 })
    expect(describeMove(DEFAULT, moveTool(DEFAULT, 4, 0), 'history')).toEqual({ kind: 'enteredBar', tool: 'history', position: 1, total: 4, other: 'radar' })
  })
})
