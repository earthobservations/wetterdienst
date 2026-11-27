/**
 * How many of the header's tool tabs fit in the room the row has (GH-4500): the tabs that do not fit go, from the end, into the "More"
 * menu at the end of the list. The widths are measured in the browser (`AppHeader.vue`: the tabs' own widths in every language, at every
 * step of the header's width), so no language and no width is guessed here; this is the arithmetic on them.
 *
 * The row is the list of tabs (`gap` apart, and the "More" button after the last one where some go into it), then the rest of the row
 * (`fixed`: the line, the reference's button and the gaps between them and the list).
 */
export interface TabFit {
  /** The natural width of each tab, in the order of the header */
  widths: readonly number[]
  /** The space between two tabs of the list */
  gap: number
  /** The width of everything in the row but the list of tabs */
  fixed: number
  /** The width of the "More" button */
  more: number
  /** The width the row has */
  available: number
}

/** The width of the row with the first `count` tabs in it, and the "More" button after them where `withMore` */
export function rowWidth(input: Pick<TabFit, 'widths' | 'gap' | 'fixed' | 'more'>, count: number, withMore: boolean): number {
  const tabs = input.widths.slice(0, count).reduce((sum, width) => sum + width, 0)
  const items = count + (withMore ? 1 : 0)
  return tabs + (withMore ? input.more : 0) + Math.max(0, items - 1) * input.gap + input.fixed
}

/**
 * The number of tabs shown: all of them where they fit with no "More" button, else the most that fit with one (none, if only the button
 * does). A tab that is one pixel too wide does not fit: the row would then scroll or wrap.
 */
export function visibleTabCount(input: TabFit): number {
  const all = input.widths.length
  // half a pixel of the browser's rounding is not a tab too many
  const room = input.available + 0.5
  if (rowWidth(input, all, false) <= room)
    return all
  for (let count = all - 1; count > 0; count--) {
    if (rowWidth(input, count, true) <= room)
      return count
  }
  return 0
}
