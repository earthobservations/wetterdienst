// Where the labels of a bar chart's axes go (GH-3893): which of the bars carry a label under the axis, and which
// values are written beside the plot. Pure, so that what is shown at 320 px and at 800 px is held by a test and not
// by a screenshot.

/** The rem of a plot's height (`h-36`), which the value labels are placed in */
export const PLOT_HEIGHT_REM = 9
/** The rem of a value label's line (`text-xs`, 1 rem of leading) */
export const VALUE_LABEL_REM = 1

/** The widths of a digit and of a bold one in an em: a label is estimated as its length times this, a little high */
const EM_PER_CHARACTER = 0.65

/** The width in px of a label of `font` px, from its length: the digits of the years and hours are all alike */
export function estimateLabelWidth(label: string, font: number): number {
  return Math.ceil(label.length * font * EM_PER_CHARACTER)
}

/** The years a label can be on, for years that span more than a generation or less: round decades, or years */
export function yearSteps(positions: number[]): number[] {
  const known = positions.filter(Number.isFinite)
  const span = known.length ? Math.max(...known) - Math.min(...known) : 0
  return span > 20 ? [10, 20, 50, 100] : [1, 2, 5, 10]
}

export interface LabelChoice {
  /** Where each bar is on the axis it is labelled by: its year, or its place in the series */
  positions: number[]
  /** The width in px of each bar's label */
  widths: number[]
  /** The width in px of the plot, which the bars share equally */
  width: number
  /** The steps to try, the smallest first: a bar is a candidate where its position is a multiple of the step */
  steps: number[]
  /** The bars that are asked about: their label is always written, and no other is written over it */
  highlights: number[]
  /** The space in px that two labels keep between them */
  gap?: number
}

/**
 * The bars that carry a label. The regular labels are those at the multiples of the smallest step at which none
 * of them touches the next (by year, so a series with gaps in it is labelled at 1960, 1980, 2000 and not at every
 * n-th bar); a label that would touch one of the highlighted bars' is left out, so that these always win. A label
 * keeps inside the plot, as `labelLeft` places it, so a bar at the edge is not asked to be wider than the plot.
 */
export function chooseLabels(input: LabelChoice): number[] {
  const { positions, widths, width, steps, highlights, gap = 6 } = input
  const count = positions.length
  const marked = new Set(highlights)
  const box = (index: number) => {
    const half = widths[index]! / 2
    const start = Math.min(Math.max(((index + 0.5) / count) * width - half, 0), Math.max(width - widths[index]!, 0))
    return { start, end: start + widths[index]! }
  }
  const touches = (a: number, b: number) => {
    const [first, second] = [box(a), box(b)]
    return first.start < second.end + gap && second.start < first.end + gap
  }

  let regular: number[] = []
  for (const step of steps) {
    const candidates = positions.flatMap((position, index) => !marked.has(index) && Number.isInteger(position) && position % step === 0 ? [index] : [])
    if (candidates.every((index, at) => at === 0 || !touches(candidates[at - 1]!, index))) {
      regular = candidates
      break
    }
  }
  const asked = [...marked].filter(index => index >= 0 && index < count)
  const kept = regular.filter(index => !asked.some(other => touches(index, other)))
  return [...kept, ...asked].sort((a, b) => a - b)
}

/** The `left` of a label centred on its bar, kept inside the plot (CSS: the label's width is a length, the bar a share) */
export function labelLeft(index: number, count: number, width: number): string {
  const centre = ((index + 0.5) / count) * 100
  return `clamp(0px, calc(${centre}% - ${width / 2}px), calc(100% - ${width}px))`
}

export interface ValueLabel {
  kind: 'top' | 'zero' | 'bottom'
  value: number
  /** The top of the label, in rem from the top of the plot: it sits inside the plot's box */
  rem: number
}

/**
 * The values written beside the plot: the highest at its top, the lowest at its bottom (not above or below it,
 * where the year labels are) and, for bars that hang from a line, a 0 at that line. A 0 that would be written over
 * the highest or the lowest label (the line is within a label's height of the edge) is left out, and so is the
 * extreme that is zero itself: the line says it.
 */
export function valueLabels(top: number, bottom: number, diverging: boolean): ValueLabel[] {
  const last = PLOT_HEIGHT_REM - VALUE_LABEL_REM
  if (!diverging)
    return [{ kind: 'top', value: top, rem: 0 }, { kind: 'bottom', value: 0, rem: last }]
  const span = (top - bottom) || 1
  const line = (top / span) * PLOT_HEIGHT_REM
  const zero = Math.min(Math.max(line - VALUE_LABEL_REM / 2, 0), last)
  const labels: ValueLabel[] = []
  if (top > 0)
    labels.push({ kind: 'top', value: top, rem: 0 })
  if (bottom < 0)
    labels.push({ kind: 'bottom', value: bottom, rem: last })
  const clear = (other: ValueLabel) => Math.abs(other.rem - zero) >= VALUE_LABEL_REM
  if (labels.every(clear))
    labels.push({ kind: 'zero', value: 0, rem: zero })
  return labels.sort((a, b) => a.rem - b.rem)
}
