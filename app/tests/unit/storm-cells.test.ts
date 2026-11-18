import { describe, expect, it } from 'vitest'
import { COMPASS_POINTS, compassPoint, drawable, hasMotion, LIST_LIMIT, listed, markSvg, outlineOf, parseCell, parseScan, SEVERITIES, SEVERITY_STYLES, styleOf, UNKNOWN_SEVERITY_STYLE } from '../../app/utils/storm-cells'
import { emptyScan, exampleScan, ringAround, stormCell, stormCellsAnswer } from '../helpers/storm-cells-answer'

// The thunderstorm cells of the map (GH-4208): what the answer of `GET /api/storm-cells` is read into, and the decisions of
// the drawing: the style of a severity, whether a cell has a motion to draw, and where the arrow points.

describe('a scan with no cell', () => {
  it('is a scan like any other: the cells are none, and the time it is of is kept', () => {
    const scan = parseScan(emptyScan('2026-11-17T22:20:00.000000+00:00'))
    expect(scan.cells).toEqual([])
    expect(scan.referenceTime).toBe('2026-11-17T22:20:00.000000+00:00')
    expect(scan.stale).toBe(false)
  })

  it('is no scan where the answer has no list of cells, which is a failure and not an empty sky', () => {
    expect(() => parseScan({ reference_time: '2026-11-17T22:20:00+00:00' })).toThrow('no list of thunderstorm cells')
    expect(() => parseScan(null)).toThrow(TypeError)
    expect(() => parseScan('<html></html>')).toThrow(TypeError)
    expect(() => parseScan({ cells: {} })).toThrow(TypeError)
  })

  it('has no time where the answer names none, or one that is none', () => {
    expect(parseScan({ cells: [] }).referenceTime).toBeNull()
    expect(parseScan({ cells: [], reference_time: 'soon' }).referenceTime).toBeNull()
  })
})

describe('reading a scan with cells', () => {
  it('reads each cell: its identifier, severity, centre, speed and calculated direction', () => {
    const scan = parseScan(exampleScan())
    expect(scan.cells).toHaveLength(4)
    const cell = scan.cells.find(entry => entry.id === '7')!
    expect(cell).toMatchObject({ severity: 2, latitude: 50.1, longitude: 8.7, speedKmh: 48, directionDegrees: 62 })
  })

  it('sorts the cells from the most severe, and by identifier within a severity, numbers as numbers', () => {
    const scan = parseScan(stormCellsAnswer([
      stormCell({ cell_id: '10', latitude: 50, longitude: 8, severity: 1 }),
      stormCell({ cell_id: '9', latitude: 50, longitude: 9, severity: 1 }),
      stormCell({ cell_id: '2', latitude: 50, longitude: 10, severity: 3 }),
      stormCell({ cell_id: '4', latitude: 50, longitude: 11, severity: null }),
    ]))
    expect(scan.cells.map(cell => cell.id)).toEqual(['2', '9', '10', '4'])
  })

  it('names a cell by its code, or its place in the list, where it has no identifier', () => {
    expect(parseCell({ code: '2026111722150000000007', severity: 1 }, 0)?.id).toBe('2026111722150000000007')
    expect(parseCell({ severity: 1 }, 4)?.id).toBe('5')
  })

  it('leaves out what is no cell', () => {
    const scan = parseScan({ cells: [null, 'x', 4, [], stormCell({ cell_id: '1', latitude: 50, longitude: 8 })] })
    expect(scan.cells.map(cell => cell.id)).toEqual(['1'])
  })

  it('takes a severity that is an integer of 0 to 3, and no other, for one', () => {
    for (const [given, wanted] of [[0, 0], [3, 3], [4, null], [-1, null], [1.5, null], ['2', null], [null, null], [undefined, null]] as const)
      expect(parseCell({ cell_id: 'a', severity: given }, 0)?.severity).toBe(wanted)
  })

  it('takes a speed and a direction that are numbers in range, and none otherwise', () => {
    expect(parseCell({ cell_speed_kmh: 12.5, direction_degrees: 359.9 }, 0)).toMatchObject({ speedKmh: 12.5, directionDegrees: 359.9 })
    expect(parseCell({ cell_speed_kmh: null, direction_degrees: null }, 0)).toMatchObject({ speedKmh: null, directionDegrees: null })
    expect(parseCell({ cell_speed_kmh: -3, direction_degrees: 400 }, 0)).toMatchObject({ speedKmh: null, directionDegrees: null })
    expect(parseCell({ cell_speed_kmh: '30', direction_degrees: '90' }, 0)).toMatchObject({ speedKmh: null, directionDegrees: null })
    // 360 is north, as 0 is
    expect(parseCell({ direction_degrees: 360 }, 0)?.directionDegrees).toBe(0)
  })
})

describe('the outline of a cell', () => {
  it('turns a polygon of GeoJSON (longitude, latitude) into rings of Leaflet (latitude, longitude)', () => {
    const outline = outlineOf({ type: 'Polygon', coordinates: [ringAround(50, 8, 0.1)] })
    expect(outline).toHaveLength(1)
    expect(outline[0]).toHaveLength(1)
    const ring = outline[0]![0]!
    expect(ring).toHaveLength(5)
    // latitude first
    expect(ring[0]![0]).toBeCloseTo(49.9, 4)
    expect(ring[0]![1]).toBeLessThan(8)
  })

  it('draws every surface of a cell in several parts, and keeps the holes of a surface with it', () => {
    const outline = outlineOf({
      type: 'MultiPolygon',
      coordinates: [
        [ringAround(50, 8, 0.1)],
        [ringAround(50.5, 8.5, 0.2), ringAround(50.5, 8.5, 0.05)],
      ],
    })
    expect(outline).toHaveLength(2)
    expect(outline[0]).toHaveLength(1)
    expect(outline[1]).toHaveLength(2)
  })

  it('draws no outline for a point, a geometry of no kind, rings of fewer than three points or points that are no places', () => {
    expect(outlineOf({ type: 'Point', coordinates: [8, 50] })).toEqual([])
    expect(outlineOf(null)).toEqual([])
    expect(outlineOf({ type: 'Polygon' })).toEqual([])
    expect(outlineOf({ type: 'Polygon', coordinates: [[[8, 50], [8.1, 50]]] })).toEqual([])
    expect(outlineOf({ type: 'Polygon', coordinates: [[[8, 50], [8.1, 50], [8, 99]]] })).toEqual([])
    expect(outlineOf({ type: 'Polygon', coordinates: [[[8, 50], ['x', 50], [8, 'y'], [8.2, 50.2]]] })).toEqual([])
  })

  it('is no outline of a cell asked for as a centre, which has a point for a geometry', () => {
    const cell = parseCell({ ...stormCell({ cell_id: '1', latitude: 50, longitude: 8 }), geometry: { type: 'Point', coordinates: [8, 50] } }, 0)!
    expect(cell.outline).toEqual([])
    expect(drawable([cell])).toEqual([cell])
  })

  it('leaves a ring with no edge out with its holes', () => {
    expect(outlineOf({ type: 'Polygon', coordinates: [[], ringAround(50, 8, 0.1)] })).toEqual([])
  })
})

describe('which cells are drawn', () => {
  it('draws a cell that has an outline or a centre, and lists one that has neither without drawing it', () => {
    const cells = parseScan(stormCellsAnswer([
      stormCell({ cell_id: 'a', latitude: 50, longitude: 8 }),
      { ...stormCell({ cell_id: 'b', latitude: 50, longitude: 8 }), geometry: null },
      { ...stormCell({ cell_id: 'c', latitude: 50, longitude: 8 }), geometry: null, centroid_latitude: null, centroid_longitude: null },
    ])).cells
    expect(cells).toHaveLength(3)
    expect(drawable(cells).map(cell => cell.id)).toEqual(['a', 'b'])
  })
})

describe('how many cells the list shows', () => {
  const many = (count: number) => parseScan(stormCellsAnswer(Array.from({ length: count }, (_, index) => stormCell({ cell_id: String(index + 1), latitude: 50, longitude: 8, severity: index % 4 })))).cells

  it('shows all of a short list, and the ten most severe of a long one until asked for all', () => {
    expect(LIST_LIMIT).toBe(10)
    expect(listed(many(10), false)).toHaveLength(10)
    expect(listed(many(11), false)).toHaveLength(10)
    expect(listed(many(120), true)).toHaveLength(120)
    // the scan is sorted from the most severe, so the first ten are those
    const cells = many(40)
    expect(listed(cells, false).every(cell => cell.severity === 3 || cell.severity === 2)).toBe(true)
    expect(listed(cells, false)).toEqual(cells.slice(0, 10))
  })
})

describe('the warning and the credit of an answer', () => {
  it('tells a scan that the backend warned is stale', () => {
    const scan = parseScan(stormCellsAnswer([], { warnings: [{ code: 'scan-stale', message: 'The newest scan is old' }] }))
    expect(scan.stale).toBe(true)
    // another warning is none of that
    expect(parseScan(stormCellsAnswer([], { warnings: [{ code: 'no-storm-cells-for-place', message: 'x' }] })).stale).toBe(false)
  })

  it('reads the credit and the licence the provider states, from the answer', () => {
    expect(parseScan(emptyScan()).credit).toEqual({
      attribution: 'Source: Deutscher Wetterdienst',
      copyright: '© Deutscher Wetterdienst (DWD), KONRAD3D convective cells',
      license: { name: 'Creative Commons Attribution 4.0 International', spdx: 'CC-BY-4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
    })
  })

  it('has no credit where the answer carries no provider, and no licence where it states none', () => {
    expect(parseScan({ cells: [] }).credit).toBeNull()
    expect(parseScan({ cells: [], metadata: { provider: { attribution: 'Source: x', license: null } } }).credit).toEqual({ attribution: 'Source: x', copyright: null, license: null })
  })
})

describe('how a severity is drawn', () => {
  it('is a style for each of the four severities and one for none', () => {
    for (const severity of SEVERITIES)
      expect(styleOf(severity)).toBe(SEVERITY_STYLES[severity])
    expect(styleOf(null)).toBe(UNKNOWN_SEVERITY_STYLE)
  })

  it('does not tell the severity by colour alone: the number is written, the edge grows with it and the weakest is dashed', () => {
    const styles = SEVERITIES.map(severity => SEVERITY_STYLES[severity])
    expect(styles.map(style => style.text)).toEqual(['0', '1', '2', '3'])
    const weights = styles.map(style => style.weight)
    expect(weights).toEqual([...weights].sort((a, b) => a - b))
    expect(new Set(weights).size).toBe(4)
    expect(styles[0]!.dashArray).not.toBeNull()
    expect(styles.slice(1).every(style => style.dashArray === null)).toBe(true)
    // and the fill is the stronger the more severe
    const fills = styles.map(style => style.fillOpacity)
    expect(fills).toEqual([...fills].sort((a, b) => a - b))
    expect(UNKNOWN_SEVERITY_STYLE.text).toBe('?')
  })

  it('has colours that carry the white number of the mark (4.5:1) and show against the map (3:1)', () => {
    const luminance = (hex: string) => {
      const channel = (offset: number) => {
        const value = Number.parseInt(hex.slice(offset, offset + 2), 16) / 255
        return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
      }
      return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5)
    }
    const ratio = (a: string, b: string) => {
      const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
      return (high + 0.05) / (low + 0.05)
    }
    // the tone the tiles are seen through (StationMap.vue) is the lightest the outline lies on
    for (const style of [...SEVERITIES.map(severity => SEVERITY_STYLES[severity]), UNKNOWN_SEVERITY_STYLE]) {
      expect(ratio(style.color, '#ffffff'), `${style.color} under the white number`).toBeGreaterThanOrEqual(4.5)
      expect(ratio(style.color, '#e8ecf2'), `${style.color} on the map`).toBeGreaterThanOrEqual(3)
    }
  })
})

describe('the motion of a cell', () => {
  it('is drawn where it has a direction and moves, or its speed is not known', () => {
    expect(hasMotion({ speedKmh: 30, directionDegrees: 90 })).toBe(true)
    expect(hasMotion({ speedKmh: null, directionDegrees: 90 })).toBe(true)
    expect(hasMotion({ speedKmh: 1, directionDegrees: 0 })).toBe(true)
  })

  it('is not drawn where there is no direction, or the cell stands', () => {
    expect(hasMotion({ speedKmh: 30, directionDegrees: null })).toBe(false)
    expect(hasMotion({ speedKmh: 0.4, directionDegrees: 90 })).toBe(false)
    expect(hasMotion({ speedKmh: null, directionDegrees: null })).toBe(false)
  })

  it('is told by the nearest point of the compass, north at both ends', () => {
    expect(COMPASS_POINTS).toHaveLength(8)
    const cases: Array<[number, string]> = [[0, 'n'], [22, 'n'], [23, 'ne'], [45, 'ne'], [90, 'e'], [135, 'se'], [180, 's'], [225, 'sw'], [270, 'w'], [315, 'nw'], [337, 'nw'], [338, 'n'], [360, 'n'], [-45, 'nw']]
    for (const [degrees, point] of cases)
      expect(compassPoint(degrees), `${degrees} degrees`).toBe(point)
  })
})

describe('the mark at the centre of a cell', () => {
  it('writes the severity on a disc of its colour, hidden from assistive technology', () => {
    const svg = markSvg({ severity: 3, speedKmh: null, directionDegrees: null })
    expect(svg).toContain('aria-hidden="true"')
    expect(svg).toContain(SEVERITY_STYLES[3].color)
    expect(svg).toMatch(/>3<\/text>/)
  })

  it('has an arrow turned by the direction where the cell moves, dashed to say that it is calculated', () => {
    const svg = markSvg({ severity: 1, speedKmh: 30, directionDegrees: 62 })
    expect(svg).toContain('rotate(62 32 32)')
    expect(svg).toContain('stroke-dasharray')
  })

  it('has no arrow for a cell with no motion', () => {
    expect(markSvg({ severity: 1, speedKmh: 30, directionDegrees: null })).not.toContain('rotate(')
    expect(markSvg({ severity: 1, speedKmh: 0, directionDegrees: 90 })).not.toContain('rotate(')
    expect(markSvg({ severity: null, speedKmh: null, directionDegrees: null })).toMatch(/>\?<\/text>/)
  })
})
