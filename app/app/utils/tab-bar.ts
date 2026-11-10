// The choice of the tools in the tab bar of the narrow layout (GH-3846): one list of all the tools in an order the
// reader can change, of which the first four are the bar and the rest are only in the Menu's sheet (and, in the wide
// layout, the header shows them in the same order, all of them, GH-3936). The line between
// them is fixed after the fourth, so there are always four in the bar, whatever is moved, and no state of the list
// is invalid. Only the order of the keys is stored (`settings.tabBar`); everything else is derived from it, so a
// tool that is added later, one that is removed, or a list that is too short, repeats a key or is not a list at all
// is repaired by `normalizeToolOrder` each time it is read, never an error.

import { TOOLS } from './sections'

/** The tools in the bar; the Menu is the fifth item beside them */
export const BAR_SIZE = 4

/** The tools in the order of the header: the default bar is Forecast, Explorer, Stripes and History, the Map beneath */
export const DEFAULT_TOOL_ORDER: readonly string[] = TOOLS.map(tool => tool.key)

/**
 * The tools in the header of the wide layout (GH-3936): all of them, so no second group and no line there today. The
 * split is the same as the bar's, only with a size of its own (`barKeys(order, HEADER_SIZE)`): a later "more tools"
 * entry sets a smaller size here and the chooser then has the two groups from the same list.
 */
export const HEADER_SIZE = DEFAULT_TOOL_ORDER.length

/**
 * Makes a stored order a valid one: what is not a known tool's key is dropped, a key that comes twice is kept at its
 * first place, and a tool the list does not name (one added since it was saved, or a list that was too short) is put
 * after the others in the default order, i.e. below the line unless the list left the bar short. Anything that is
 * not a list is the default.
 */
export function normalizeToolOrder(raw: unknown, known: readonly string[] = DEFAULT_TOOL_ORDER): string[] {
  const order: string[] = []
  if (Array.isArray(raw)) {
    for (const key of raw) {
      if (typeof key === 'string' && known.includes(key) && !order.includes(key))
        order.push(key)
    }
  }
  for (const key of known) {
    if (!order.includes(key))
      order.push(key)
  }
  return order
}

/** The order with the tool at `from` taken out and put at `to`: both are places in the list, clamped to it */
export function moveTool(order: readonly string[], from: number, to: number): string[] {
  const next = [...order]
  const last = next.length - 1
  if (from < 0 || from > last)
    return next
  const [key] = next.splice(from, 1)
  next.splice(Math.min(Math.max(to, 0), last), 0, key!)
  return next
}

/** The keys of the first `size` tools, in the order of the list: the bar's (`BAR_SIZE`, the default) or the header's (`HEADER_SIZE`) */
export function barKeys(order: readonly string[], size: number = BAR_SIZE): string[] {
  return order.slice(0, size)
}

/** The keys of the tools after the first `size`: the ones that are only in the Menu (or, with a smaller `HEADER_SIZE`, behind "more tools") */
export function menuKeys(order: readonly string[], size: number = BAR_SIZE): string[] {
  return order.slice(size)
}

export function isDefaultOrder(order: readonly string[], known: readonly string[] = DEFAULT_TOOL_ORDER): boolean {
  return order.length === known.length && order.every((key, index) => key === known[index])
}

export type MoveKind = 'reorderedBar' | 'reorderedMenu' | 'enteredBar' | 'leftBar'

/** What a move did, for the words that say it to someone who does not see the list (the keys of the tools, not their names) */
export interface MoveNote {
  kind: MoveKind
  tool: string
  /**
   * The place the words name, from 1: the tool's own in the bar (`reorderedBar`, `enteredBar`) or among the tools that
   * are only in the Menu (`reorderedMenu`), and for `leftBar`, in which the tool is in the Menu, that of the tool it
   * made room for
   */
  position: number
  /** How many places there are where that place is */
  total: number
  /** The tool the move pushed out of the bar (`enteredBar`), or pulled into it (`leftBar`) */
  other?: string
}

/** What moving `tool` from `before` to `after` did, or null where it stayed where it was */
export function describeMove(before: readonly string[], after: readonly string[], tool: string, size: number = BAR_SIZE): MoveNote | null {
  const was = before.indexOf(tool)
  const now = after.indexOf(tool)
  if (was === -1 || now === -1 || was === now)
    return null
  const wasIn = was < size
  const nowIn = now < size
  if (wasIn && nowIn)
    return { kind: 'reorderedBar', tool, position: now + 1, total: size }
  if (!wasIn && !nowIn)
    return { kind: 'reorderedMenu', tool, position: now - size + 1, total: after.length - size }
  if (nowIn) {
    const other = barKeys(before, size).find(key => !barKeys(after, size).includes(key))
    return { kind: 'enteredBar', tool, position: now + 1, total: size, other }
  }
  const other = barKeys(after, size).find(key => !barKeys(before, size).includes(key))
  return { kind: 'leftBar', tool, position: other ? after.indexOf(other) + 1 : 0, total: size, other }
}

/**
 * The place a pointer at `y` is dropping on: the one of the slots (the rows' rectangles top to bottom, which stay
 * where they are, as the same number of rows stand in each part of the list) whose middle is nearest to it
 */
export function slotAt(y: number, slots: readonly { top: number, bottom: number }[]): number {
  let nearest = 0
  let distance = Infinity
  slots.forEach((slot, index) => {
    const gap = Math.abs(y - (slot.top + slot.bottom) / 2)
    if (gap < distance) {
      distance = gap
      nearest = index
    }
  })
  return nearest
}
