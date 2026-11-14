/**
 * Saving a chart that ECharts drew as SVG (GH-4068): the SVG text as a file, or rasterised to a PNG or a JPEG of the
 * size and pixel ratio asked for. The browser draws the SVG into a canvas, so no canvas renderer is shipped for it.
 */

export type ImageFormat = 'png' | 'jpeg' | 'svg'

const MIME: Record<ImageFormat, string> = { png: 'image/png', jpeg: 'image/jpeg', svg: 'image/svg+xml' }

/** The size of the file a drawing of `width` by `height` px at `scale` makes: Plotly's way, which the stripes have always saved by */
export function imageSize(width: number, height: number, scale: number): { width: number, height: number } {
  return { width: Math.round(width * scale), height: Math.round(height * scale) }
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('The chart image could not be read back'))
    image.src = url
  })
}

/**
 * The file of `svg`, which is `width` by `height` px: the SVG itself for `svg`, otherwise a raster image `scale` times as
 * large, on `background` (a JPEG has no transparency, and a saved chart is the page's paper, not a hole in it)
 */
export async function svgToBlob(svg: string, options: { format: ImageFormat, width: number, height: number, scale: number, background: string }): Promise<Blob> {
  const { format, width, height, scale, background } = options
  const vector = new Blob([svg], { type: `${MIME.svg};charset=utf-8` })
  if (format === 'svg')
    return vector
  const url = URL.createObjectURL(vector)
  try {
    const image = await loadImage(url)
    const size = imageSize(width, height, scale)
    const canvas = document.createElement('canvas')
    canvas.width = size.width
    canvas.height = size.height
    const context = canvas.getContext('2d')
    if (!context)
      throw new Error('No canvas to draw the chart image on')
    context.fillStyle = background
    context.fillRect(0, 0, size.width, size.height)
    context.drawImage(image, 0, 0, size.width, size.height)
    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('The chart image could not be made')), MIME[format], 0.95)
    })
  }
  finally {
    URL.revokeObjectURL(url)
  }
}

/** Hands `blob` to the browser as a download named `filename` */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  link.remove()
  // the download has started by the time the task ends
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
