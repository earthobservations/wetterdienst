import { Buffer } from 'node:buffer'
import { crc32, deflateSync } from 'node:zlib'
import { RADAR_CLASSES } from './radar-answer'

/**
 * A frame of the radar as an image, for the mock backend of the e2e specs and the design previews (GH-3788): a few cells of rain on a
 * wider light shower, drawn in the classes of the legend, transparent where it is dry, and drifting east with the minutes (so that a loop
 * of the frames is seen to move). No dependency: a PNG is a signature and three chunks, and Node has the zlib and the CRC.
 */

const WIDTH = 240
const HEIGHT = 234

function chunk(type: string, data: Buffer): Buffer {
  const length = Buffer.alloc(4)
  length.writeUInt32BE(data.length)
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data])
  const sum = Buffer.alloc(4)
  sum.writeUInt32BE(crc32(body))
  return Buffer.concat([length, body, sum])
}

/** The rate in mm/h at a pixel of a loop at `minutes` after its start: gaussian cells that move 0.12 px a minute */
function rateAt(x: number, y: number, minutes: number): number {
  const cells: Array<[number, number, number, number, number]> = [
    // centre x, centre y, radius x, radius y, peak
    [70 + minutes * 0.12, 90, 38, 24, 14],
    [130 + minutes * 0.12, 70, 26, 34, 32],
    [150 + minutes * 0.12, 150, 46, 22, 6],
    [60 + minutes * 0.12, 170, 30, 20, 3],
  ]
  let rate = 0
  for (const [cx, cy, rx, ry, peak] of cells)
    rate += peak * Math.exp(-(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2))
  return rate
}

function rgbOf(hex: string): [number, number, number] {
  return [1, 3, 5].map(at => Number.parseInt(hex.slice(at, at + 2), 16)) as [number, number, number]
}

/** The image of the frame `minutes` after the start of the loop */
export function radarPng(minutes: number): Buffer {
  const raw = Buffer.alloc((WIDTH * 4 + 1) * HEIGHT)
  for (let y = 0; y < HEIGHT; y++) {
    const row = y * (WIDTH * 4 + 1)
    raw[row] = 0
    for (let x = 0; x < WIDTH; x++) {
      const rate = rateAt(x, y, minutes)
      const entry = [...RADAR_CLASSES].reverse().find(item => rate >= item.lower)
      const at = row + 1 + x * 4
      if (!entry)
        continue
      const [red, green, blue] = rgbOf(entry.color)
      raw[at] = red
      raw[at + 1] = green
      raw[at + 2] = blue
      raw[at + 3] = 255
    }
  }
  const header = Buffer.alloc(13)
  header.writeUInt32BE(WIDTH, 0)
  header.writeUInt32BE(HEIGHT, 4)
  header[8] = 8
  // colour type 6: RGBA
  header[9] = 6
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]), chunk('IHDR', header), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))])
}
