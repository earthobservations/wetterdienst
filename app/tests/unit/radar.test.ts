import { describe, expect, it } from 'vitest'
import { clockSkew } from '../../app/utils/provider-credit'
import { CELLS_WINDOW_MS, cellsShownOn, classLimits, classRange, describeFrame, formatFrameTime, frameKey, frameUrl, indexAfterRefresh, isStale, isUnavailable, isWithinBounds, leafletBounds, newestAge, nextReady, openingIndex, parseLoop, preloadOrder, STALE_AFTER_MS } from '../../app/utils/radar'
import { RADAR_BOUNDS, radarAnswer } from '../helpers/radar-answer'

// The Radar tool's reading of the backend's list of frames (GH-3788): the frames in time order, the bounds a Leaflet image overlay takes,
// the legend, the credit and the stale warning; and the decisions of the player: which frame opens the loop, in which order the frames are
// asked for, how the loop goes on, where it stands after a refresh, and what a time is called in words.

const NOW = Date.parse('2026-11-19T21:30:00Z')
const answer = radarAnswer({ run: '2026-11-19T21:25:00Z' })

describe('parseLoop', () => {
  it('reads the 25 frames of the analysis and the 24 of the forecast, in time order, with their kind and lead', () => {
    const loop = parseLoop(answer)
    expect(loop.frames).toHaveLength(49)
    expect(loop.frames.slice(0, 25).every(frame => frame.kind === 'observation' && frame.leadMinutes === 0)).toBe(true)
    expect(loop.frames.slice(25).map(frame => frame.leadMinutes)).toEqual(Array.from({ length: 24 }, (_, index) => 5 * (index + 1)))
    expect(loop.frames.map(frame => frame.at)).toEqual(loop.frames.map(frame => frame.at).sort((a, b) => a - b))
    expect(loop.frames[0]!.time).toBe('2026-11-19T19:25:00Z')
    expect(loop.frames[24]!.time).toBe('2026-11-19T21:25:00Z')
    // the forecast frames are of the newest run
    expect(new Set(loop.frames.slice(25).map(frame => frame.run))).toEqual(new Set(['2026-11-19T21:25:00Z']))
  })

  it('puts the frames in order where the answer does not, and leaves out what is no frame', () => {
    const shuffled = { ...answer, frames: [answer.frames[3], { time: 'soon', run: 'x', lead_minutes: 0, kind: 'observation' }, answer.frames[1], null, { ...answer.frames[2], kind: 'nowcast' }, { ...answer.frames[0], lead_minutes: 'a' }, answer.frames[0]] }
    expect(parseLoop(shuffled).frames.map(frame => frame.time)).toEqual([answer.frames[0]!.time, answer.frames[1]!.time, answer.frames[3]!.time])
  })

  it('reads the bounds, the legend and the credit of the answer', () => {
    const loop = parseLoop(answer)
    expect(loop.bounds).toEqual(RADAR_BOUNDS)
    expect(loop.run).toBe('2026-11-19T21:25:00Z')
    expect(loop.legend.unit).toBe('mm/h')
    expect(loop.legend.transparentBelow).toBe(0.1)
    expect(loop.legend.classes).toHaveLength(7)
    expect(loop.legend.classes.at(-1)).toEqual({ lower: 25, upper: null, color: '#081d58' })
    expect(loop.credit?.attribution).toBe('Source: Deutscher Wetterdienst')
    expect(loop.credit?.license?.name).toBe('Creative Commons Attribution 4.0 International')
    expect(loop.stale).toBe(false)
  })

  it('reads the radar-stale warning', () => {
    expect(parseLoop(radarAnswer({ run: '2026-11-19T21:25:00Z', warnings: [{ code: 'radar-stale', message: 'old' }] })).stale).toBe(true)
    expect(parseLoop(radarAnswer({ run: '2026-11-19T21:25:00Z', warnings: [{ code: 'other', message: 'x' }] })).stale).toBe(false)
  })

  it('accepts a list with no frame (a loop that DWD has no frames for)', () => {
    expect(parseLoop({ ...answer, frames: [] }).frames).toEqual([])
  })

  it.each([
    ['no object', null],
    ['no list of frames', { ...answer, frames: undefined }],
    ['no bounds', { ...answer, image: {} }],
    ['bounds that are inside out', { ...answer, image: { bounds: { west: 10, east: 5, south: 40, north: 50 } } }],
    ['bounds that are no coordinates', { ...answer, image: { bounds: { west: 1, east: 400, south: 40, north: 50 } } }],
    ['no legend', { ...answer, legend: undefined }],
    ['a legend with no classes', { ...answer, legend: { unit: 'mm/h', classes: [] } }],
    ['a class with a colour that is none', { ...answer, legend: { unit: 'mm/h', classes: [{ lower: 1, upper: 2, color: 'red' }] } }],
  ])('is no loop for %s', (_, bad) => {
    expect(() => parseLoop(bad)).toThrow(TypeError)
  })
})

describe('the address of a frame and the bounds of the images', () => {
  it('asks for the frame with its run, so that the image is the same for an hour in the browser\'s cache', () => {
    expect(frameUrl({ time: '2026-11-19T21:35:00Z', run: '2026-11-19T21:25:00Z' })).toBe('/api/radar/frame?product=rv&time=2026-11-19T21%3A35%3A00Z&run=2026-11-19T21%3A25%3A00Z')
  })

  it('keys a frame by its run and its time: a forecast frame of another run is another image', () => {
    expect(frameKey({ time: 'b', run: 'a' })).not.toBe(frameKey({ time: 'b', run: 'c' }))
  })

  it('gives Leaflet [[south, west], [north, east]]', () => {
    expect(leafletBounds(RADAR_BOUNDS)).toEqual([[45.6823, 1.4633], [56.2194, 18.7316]])
  })

  it('says whether a place is within the box of the images, the edges included (GH-4287)', () => {
    expect(isWithinBounds({ latitude: 51.34, longitude: 12.37 }, RADAR_BOUNDS)).toBe(true)
    expect(isWithinBounds({ latitude: RADAR_BOUNDS.south, longitude: RADAR_BOUNDS.west }, RADAR_BOUNDS)).toBe(true)
    expect(isWithinBounds({ latitude: RADAR_BOUNDS.north, longitude: RADAR_BOUNDS.east }, RADAR_BOUNDS)).toBe(true)
    // just beyond each edge, and far away (Madrid, Reykjavik, the southern hemisphere)
    expect(isWithinBounds({ latitude: RADAR_BOUNDS.south - 0.01, longitude: 10 }, RADAR_BOUNDS)).toBe(false)
    expect(isWithinBounds({ latitude: RADAR_BOUNDS.north + 0.01, longitude: 10 }, RADAR_BOUNDS)).toBe(false)
    expect(isWithinBounds({ latitude: 50, longitude: RADAR_BOUNDS.west - 0.01 }, RADAR_BOUNDS)).toBe(false)
    expect(isWithinBounds({ latitude: 50, longitude: RADAR_BOUNDS.east + 0.01 }, RADAR_BOUNDS)).toBe(false)
    expect(isWithinBounds({ latitude: 40.4168, longitude: -3.7038 }, RADAR_BOUNDS)).toBe(false)
    expect(isWithinBounds({ latitude: -33.9, longitude: 12.37 }, RADAR_BOUNDS)).toBe(false)
  })
})

describe('the opening frame and the order of loading', () => {
  const frames = parseLoop(answer).frames

  it('opens on the newest frame of the analysis: the sky as it was seen last', () => {
    expect(openingIndex(frames)).toBe(24)
    expect(frames[openingIndex(frames)]!.kind).toBe('observation')
  })

  it('opens on the first frame where there is no analysis, and on 0 for no frames', () => {
    expect(openingIndex(frames.filter(frame => frame.kind === 'forecast'))).toBe(0)
    expect(openingIndex([])).toBe(0)
  })

  it('asks for the opening frame first, then the others in time order, and not for those that are in hand', () => {
    const order = preloadOrder(frames, new Set())
    expect(order[0]).toBe(frames[24])
    expect(order.slice(1)).toEqual(frames.filter((_, index) => index !== 24))
    expect(order).toHaveLength(49)
    const settled = new Set([frameKey(frames[24]!), frameKey(frames[0]!)])
    expect(preloadOrder(frames, settled)).toEqual(frames.filter((_, index) => index !== 24 && index !== 0))
  })
})

describe('nextReady', () => {
  it('goes on to the next frame that is in hand, and round at the end', () => {
    expect(nextReady(0, 5, () => true)).toBe(1)
    expect(nextReady(4, 5, () => true)).toBe(0)
    expect(nextReady(0, 5, index => index === 3)).toBe(3)
    expect(nextReady(3, 5, index => index !== 4 && index !== 0)).toBe(1)
  })

  it('has none where no other frame is in hand, or the loop has one frame', () => {
    expect(nextReady(2, 5, index => index === 2)).toBeNull()
    expect(nextReady(0, 1, () => true)).toBeNull()
    expect(nextReady(0, 0, () => true)).toBeNull()
  })
})

describe('the age of the newest run', () => {
  const frames = parseLoop(answer).frames

  it('is read from the newest frame of the analysis, not from the forecast, which is in the future', () => {
    expect(newestAge(frames, NOW)).toBe(5 * 60_000)
    expect(newestAge(frames.filter(frame => frame.kind === 'forecast'), NOW)).toBeNull()
  })

  it('is stale after 20 minutes and not before', () => {
    expect(STALE_AFTER_MS).toBe(20 * 60_000)
    expect(isStale(frames, NOW)).toBe(false)
    expect(isStale(frames, Date.parse('2026-11-19T21:45:00Z'))).toBe(false)
    expect(isStale(frames, Date.parse('2026-11-19T21:45:01Z'))).toBe(true)
    expect(isStale([], NOW)).toBe(false)
  })
})

describe('indexAfterRefresh', () => {
  const before = parseLoop(radarAnswer({ run: '2026-11-19T21:25:00Z' })).frames
  const after = parseLoop(radarAnswer({ run: '2026-11-19T21:30:00Z' })).frames

  it('keeps the reader at the frame they were at, where it is still in the loop', () => {
    const watching = before[10]!
    expect(after[indexAfterRefresh(after, watching)]!.time).toBe(watching.time)
  })

  it('goes to the nearest frame in time where theirs has left the loop', () => {
    const oldest = { ...before[0]!, time: '2026-11-19T19:00:00Z', at: Date.parse('2026-11-19T19:00:00Z') }
    expect(indexAfterRefresh(after, oldest)).toBe(0)
  })

  it('opens where there was no frame, and on the first where there is none', () => {
    expect(indexAfterRefresh(after, null)).toBe(openingIndex(after))
    expect(indexAfterRefresh([], before[0]!)).toBe(0)
  })
})

describe('the legend in numbers', () => {
  const classes = parseLoop(answer).legend.classes

  it('writes a class as its limits, the last one open, in the language\'s own decimal sign', () => {
    expect(classes.map(entry => classRange(entry, 'en-GB'))).toEqual(['0.1–0.5', '0.5–1', '1–2.5', '2.5–5', '5–10', '10–25', '25+'])
    expect(classes.map(entry => classRange(entry, 'de-DE'))).toEqual(['0,1–0,5', '0,5–1', '1–2,5', '2,5–5', '5–10', '10–25', '25+'])
  })

  it('gives the limits for a sentence', () => {
    expect(classLimits(classes[0]!, 'de-DE')).toEqual({ lower: '0,1', upper: '0,5' })
    expect(classLimits(classes[6]!, 'en-GB')).toEqual({ lower: '25', upper: null })
  })
})

describe('a time in the reader\'s zone', () => {
  const at = Date.parse('2026-11-19T21:35:00Z')

  it('is the time of day with the zone\'s name, in the language of the page', () => {
    expect(formatFrameTime(at, 'en-GB', at, 'UTC')).toBe('21:35 UTC')
    expect(formatFrameTime(at, 'de-DE', at, 'Europe/Berlin')).toBe('22:35 MEZ')
    expect(formatFrameTime(Date.parse('2026-07-01T12:00:00Z'), 'de-DE', Date.parse('2026-07-01T12:00:00Z'), 'Europe/Berlin')).toBe('14:00 MESZ')
    expect(formatFrameTime(at, 'en-GB', at, 'America/New_York')).toMatch(/^16:35 (EST|GMT-5)$/)
  })

  it('has the weekday where the frame is on another day than now, which the loop of four hours can cross', () => {
    const midnight = Date.parse('2026-11-19T23:05:00Z')
    expect(formatFrameTime(midnight, 'en-GB', at, 'Europe/Berlin')).toMatch(/^Fri,? 00:05 CET$/)
    // the day is the reader's zone's, not UTC's: 22:35 and 00:05 in Berlin are two days, 21:35 and 23:05 in UTC are one
    expect(formatFrameTime(midnight, 'en-GB', at, 'UTC')).toBe('23:05 UTC')
  })

  it('is told by words, so that observed and forecast are not told apart by colour', () => {
    const t = (key: string, params?: Record<string, unknown>) => `${key}${params ? JSON.stringify(params) : ''}`
    expect(describeFrame(t, { at, kind: 'observation', leadMinutes: 0 }, 'en-GB', at)).toMatchObject({ kind: 'radar.observed', ahead: null, value: expect.stringContaining('radar.valueObserved') })
    const forecast = describeFrame(t, { at, kind: 'forecast', leadMinutes: 35 }, 'en-GB', at)
    expect(forecast.kind).toBe('radar.forecast')
    expect(forecast.ahead).toContain('35')
    expect(forecast.value).toContain('radar.valueForecast')
  })
})

describe('the cells and the frame on the map', () => {
  const frames = parseLoop(answer).frames
  const scan = '2026-11-19T21:20:00.000000+00:00'
  const at = (time: string) => frames.find(frame => frame.time === time)!

  it('shows the cells on an observed frame within 15 minutes of the scan, before it and after it, and not beyond', () => {
    expect(CELLS_WINDOW_MS).toBe(15 * 60_000)
    expect(cellsShownOn(at('2026-11-19T21:20:00Z'), scan)).toBe(true)
    expect(cellsShownOn(at('2026-11-19T21:05:00Z'), scan)).toBe(true)
    expect(cellsShownOn(at('2026-11-19T21:25:00Z'), scan)).toBe(true)
    expect(cellsShownOn(at('2026-11-19T21:00:00Z'), scan)).toBe(false)
    expect(cellsShownOn(at('2026-11-19T19:25:00Z'), scan)).toBe(false)
  })

  it('never shows them on a frame of the forecast, which is of a time that has not been, and not where there is no frame or no scan', () => {
    const forecast = frames.find(frame => frame.kind === 'forecast')!
    expect(cellsShownOn(forecast, '2026-11-19T21:25:00.000000+00:00')).toBe(false)
    expect(cellsShownOn(null, scan)).toBe(false)
    expect(cellsShownOn(at('2026-11-19T21:20:00Z'), null)).toBe(false)
    expect(cellsShownOn(at('2026-11-19T21:20:00Z'), 'soon')).toBe(false)
  })

  it('tells a backend that has no radar (a 404, a 501) from one that failed, which Retry may mend', () => {
    expect(isUnavailable({ statusCode: 501 })).toBe(true)
    expect(isUnavailable({ status: 404 })).toBe(true)
    expect(isUnavailable({ statusCode: 502 })).toBe(false)
    expect(isUnavailable({ statusCode: 503 })).toBe(false)
    expect(isUnavailable(new Error('down'))).toBe(false)
    expect(isUnavailable(null)).toBe(false)
  })
})

describe('the clock of the answer', () => {
  it('reads how far the device\'s clock is from the server\'s from the answer\'s own retrieved_at, so that the age is the server\'s', () => {
    const device = Date.parse('2026-11-19T21:30:00Z')
    expect(clockSkew({ retrieved_at: '2026-11-19T21:40:00.000000+00:00' }, device)).toBe(10 * 60_000)
    expect(clockSkew({ retrieved_at: '2026-11-19T21:25:00Z' }, device)).toBe(-5 * 60_000)
    expect(clockSkew({}, device)).toBe(0)
    expect(clockSkew({ retrieved_at: 'later' }, device)).toBe(0)
    expect(clockSkew(null, device)).toBe(0)
  })

  it('is in the loop and the scan as they are read', () => {
    const loop = parseLoop(radarAnswer({ run: '2026-11-19T21:25:00Z', now: Date.now() - 3_600_000 }))
    // the server said it was an hour ago: the device is an hour ahead of it
    expect(loop.clockSkewMs).toBeLessThan(-3_590_000)
    expect(loop.clockSkewMs).toBeGreaterThan(-3_610_000)
  })
})
