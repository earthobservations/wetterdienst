import { Buffer } from 'node:buffer'
import { inflateSync } from 'node:zlib'

// The text of a PDF with the size it is printed at, read from what Chromium's `page.pdf` writes (Skia/PDF): the page
// content streams are Flate-compressed, text is `BT /F<font object> <size> Tf <matrix> Tm <hex> Tj ... ET`, and the
// fonts are Type 3 or TrueType subsets whose `ToUnicode` map says what each code is. That is all this reads (no
// object streams, no encryption, no forms: Skia draws text on the page itself), which keeps the test free of a PDF
// library. A PDF that is not of this shape finds no text, which `chart-print.spec.ts` fails on: it asks for every
// string of the chart in the PDF.

export interface PdfRun {
  text: string
  /** The size in points, the font size times every scale of the text matrix and the current transformation */
  size: number
  /** 1-based number of the page */
  page: number
  /** The position of the run's origin on the page in points, from the bottom left corner */
  x: number
  y: number
}

type Matrix = [number, number, number, number, number, number]
const IDENTITY: Matrix = [1, 0, 0, 1, 0, 0]

/** `a` then `b` (the PDF order: the point goes through `a` first) */
function multiply(a: Matrix, b: Matrix): Matrix {
  return [
    a[0] * b[0] + a[1] * b[2],
    a[0] * b[1] + a[1] * b[3],
    a[2] * b[0] + a[3] * b[2],
    a[2] * b[1] + a[3] * b[3],
    a[4] * b[0] + a[5] * b[2] + b[4],
    a[4] * b[1] + a[5] * b[3] + b[5],
  ]
}

interface PdfObject {
  dict: string
  stream: Buffer | null
}

function readObjects(pdf: Buffer): Map<number, PdfObject> {
  const text = pdf.toString('latin1')
  const objects = new Map<number, PdfObject>()
  const header = /(\d+) 0 obj\r?\n/g
  for (let match = header.exec(text); match; match = header.exec(text)) {
    const start = match.index + match[0].length
    const streamAt = text.indexOf('stream', start)
    const endAt = text.indexOf('endobj', start)
    if (streamAt !== -1 && streamAt < endAt && /^stream\r?\n/.test(text.slice(streamAt, streamAt + 8))) {
      const dict = text.slice(start, streamAt)
      const dataStart = streamAt + (text[streamAt + 6] === '\r' ? 8 : 7)
      const dataEnd = text.indexOf('endstream', dataStart)
      let data: Buffer = pdf.subarray(dataStart, dataEnd)
      if (/\/FlateDecode/.test(dict))
        data = inflateSync(data)
      objects.set(Number(match[1]), { dict, stream: data })
      header.lastIndex = dataEnd
    }
    else {
      objects.set(Number(match[1]), { dict: text.slice(start, endAt), stream: null })
      header.lastIndex = endAt
    }
  }
  return objects
}

/** The code -> text map of a font's `ToUnicode`, and how many bytes a code is */
function readToUnicode(cmap: string): { bytes: number, map: Map<number, string> } {
  const map = new Map<number, string>()
  const utf16 = (hex: string) => Buffer.from(hex, 'hex').swap16().toString('utf16le')
  const space = /begincodespacerange\s*<([\da-f]+)>/i.exec(cmap)
  for (const block of cmap.matchAll(/beginbfchar([\s\S]*?)endbfchar/g)) {
    for (const [, code, to] of block[1]!.matchAll(/<([\da-f]+)>\s*<([\da-f]+)>/gi))
      map.set(Number.parseInt(code!, 16), utf16(to!))
  }
  for (const block of cmap.matchAll(/beginbfrange([\s\S]*?)endbfrange/g)) {
    for (const [, from, to, first] of block[1]!.matchAll(/<([\da-f]+)>\s*<([\da-f]+)>\s*<([\da-f]+)>/gi)) {
      for (let code = Number.parseInt(from!, 16); code <= Number.parseInt(to!, 16); code++)
        map.set(code, String.fromCodePoint(Number.parseInt(first!, 16) + code - Number.parseInt(from!, 16)))
    }
  }
  return { bytes: (space?.[1]?.length ?? 2) / 2, map }
}

/** Every run of text in the PDF (the glyphs of one `BT ... ET`, which Skia writes for one line of one style) */
export function pdfTextRuns(pdf: Buffer): PdfRun[] {
  const objects = readObjects(pdf)
  const fonts = new Map<string, { bytes: number, map: Map<number, string> }>()
  const font = (name: string) => {
    let found = fonts.get(name)
    if (!found) {
      const object = objects.get(Number(name.slice(1)))
      const toUnicode = /\/ToUnicode (\d+) 0 R/.exec(object?.dict ?? '')?.[1]
      const cmap = toUnicode ? objects.get(Number(toUnicode))?.stream?.toString('latin1') : undefined
      found = cmap ? readToUnicode(cmap) : { bytes: 1, map: new Map() }
      fonts.set(name, found)
    }
    return found
  }

  const pages = [...objects.entries()].filter(([, object]) => /\/Type \/Page\b/.test(object.dict) && !/\/Type \/Pages\b/.test(object.dict))
  const runs: PdfRun[] = []
  pages.forEach(([, object], index) => {
    const contents = [...(/\/Contents (?:\[([^\]]*)\]|(\d+) 0 R)/.exec(object.dict)?.slice(1, 3).join(' ') ?? '').matchAll(/(\d+) 0 R|(\d+)/g)]
    for (const ref of contents) {
      const stream = objects.get(Number(ref[1] ?? ref[2]))?.stream
      if (stream)
        runs.push(...contentRuns(stream.toString('latin1'), font, index + 1))
    }
  })
  return runs
}

function contentRuns(content: string, font: (name: string) => { bytes: number, map: Map<number, string> }, page: number): PdfRun[] {
  const runs: PdfRun[] = []
  const stack: Matrix[] = []
  let ctm = IDENTITY
  let tm = IDENTITY
  let current: { name: string, size: number } | null = null
  let text: { value: string, size: number, x: number, y: number } | null = null
  const operands: string[] = []
  const numbers = () => operands.slice(-6).map(Number) as Matrix

  const show = (hex: string) => {
    if (!text || !current)
      return
    const { bytes, map } = font(current.name)
    for (let at = 0; at < hex.length; at += bytes * 2)
      text.value += map.get(Number.parseInt(hex.slice(at, at + bytes * 2), 16)) ?? '�'
  }
  const start = () => {
    const matrix = multiply(tm, ctm)
    // the size is the font size times the length of the matrix's unit vector across the line (its determinant's root)
    text = {
      value: '',
      size: (current?.size ?? 0) * Math.sqrt(Math.abs(matrix[0] * matrix[3] - matrix[1] * matrix[2])),
      x: matrix[4],
      y: matrix[5],
    }
  }

  // tokens: names, numbers, hex strings, literal strings, arrays and operators
  const tokens = content.matchAll(/<[\da-f\s]*>|\((?:\\.|[^\\)])*\)|\/[^\s/<>[\]()]+|\[|\]|[^\s/<>[\]()]+/gi)
  for (const [token] of tokens) {
    if (/^[-+.\d]/.test(token) || token.startsWith('/') || token.startsWith('<') || token.startsWith('(') || token === '[' || token === ']') {
      operands.push(token)
      continue
    }
    switch (token) {
      case 'q':
        stack.push(ctm)
        break
      case 'Q':
        ctm = stack.pop() ?? ctm
        break
      case 'cm':
        ctm = multiply(numbers(), ctm)
        break
      case 'BT':
        tm = IDENTITY
        text = null
        break
      case 'Tf':
        current = { name: operands.at(-2)!.slice(1), size: Number(operands.at(-1)) }
        break
      case 'Tm':
        tm = numbers()
        start()
        break
      case 'Td': {
        const [tx, ty] = operands.slice(-2).map(Number) as [number, number]
        tm = multiply([1, 0, 0, 1, tx, ty], tm)
        break
      }
      case 'Tj': {
        if (!text)
          start()
        const string = operands.at(-1)!
        if (string.startsWith('<'))
          show(string.slice(1, -1).replace(/\s/g, ''))
        break
      }
      case 'TJ':
        if (!text)
          start()
        for (const part of operands) {
          if (part.startsWith('<'))
            show(part.slice(1, -1).replace(/\s/g, ''))
        }
        break
      case 'ET':
        if (text && (text as { value: string }).value) {
          const done: { value: string, size: number, x: number, y: number } = text
          runs.push({ text: done.value, size: done.size, page, x: done.x, y: done.y })
        }
        text = null
        break
    }
    operands.length = 0
  }
  return runs
}
