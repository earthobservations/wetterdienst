// The axis titles of the meteogram (GH-3558): a title is written along its panel, which a long one of 12 px does not fit.

/** What a character of an axis title is wide, in ems: Inter's average over Latin text, the capitals and digits more */
const TITLE_CHAR_EM = 0.62

/**
 * An axis title written along its panel, which is `panelPx` tall: on one line where it fits, and on two (cut at the
 * space nearest its middle, with a `<br>` that the chart turns into a line break) where it does not, which a German "Niederschlag mm"
 * of 12 px in a panel of 88 px does not. A title of one word stays on one line.
 */
export function fitAxisTitle(text: string, panelPx: number, fontPx: number): { text: string, lines: 1 | 2 } {
  const width = (value: string) => value.length * TITLE_CHAR_EM * fontPx
  if (width(text) <= panelPx)
    return { text, lines: 1 }
  const spaces = [...text.matchAll(/ /g)].map(match => match.index)
  const middle = text.length / 2
  const at = spaces.sort((a, b) => Math.abs(a - middle) - Math.abs(b - middle))[0]
  if (at === undefined)
    return { text, lines: 1 }
  return { text: `${text.slice(0, at)}<br>${text.slice(at + 1)}`, lines: 2 }
}
