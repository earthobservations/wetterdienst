/**
 * The facets of the Explorer saved as one image (GH-4096): each chart's SVG, drawn on its own in the light theme, as a
 * nested `<svg>` of one sheet, one under the other in the order the page shows them, as wide as the widest. The file's
 * size is the sum of the charts' sizes as they are shown, which is what it has always been.
 */

export interface SvgPart {
  svg: string
  width: number
  height: number
}

const ROOT = /^\s*(?:<\?xml[^>]*\?>\s*)?<svg\b([^>]*)>/

/** The root element's attributes without `names`, which the nesting sets again */
function withoutAttributes(attributes: string, names: string[]): string {
  return names.reduce((rest, name) => rest.replace(new RegExp(`\\s${name}="[^"]*"`, 'g'), ''), attributes)
}

/** `parts` as one SVG: the sheet is as wide as the widest and as high as all of them together, which are drawn from its top to its foot */
export function stackSvgs(parts: readonly SvgPart[]): SvgPart {
  const width = Math.max(0, ...parts.map(part => part.width))
  const height = parts.reduce((sum, part) => sum + part.height, 0)
  let top = 0
  const nested = parts.map((part) => {
    const root = ROOT.exec(part.svg)
    if (!root)
      throw new Error('The chart is not an SVG')
    const attributes = withoutAttributes(root[1]!, ['width', 'height', 'x', 'y', 'viewBox'])
    const opened = `<svg${attributes} x="0" y="${top}" width="${part.width}" height="${part.height}" viewBox="0 0 ${part.width} ${part.height}">`
    top += part.height
    return `${opened}${part.svg.slice(root[0].length)}`
  })
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${nested.join('')}</svg>`
  return { svg, width, height }
}
