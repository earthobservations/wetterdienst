import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  failureOfCode,
  forgetRememberedPosition,
  LOCATION_STORAGE_KEY,
  readRememberedPosition,
  roundCoordinate,
  roundPosition,
  writeRememberedPosition,
} from '../../app/utils/geolocation'

// The reader's own position (GH-3651): rounded to two decimals of a degree (about 1 km) before anything leaves the
// browser, the browser's error codes as the failures the page tells, and the one place it may be kept (`wd-location`).

function stubStorage(initial: Record<string, string> = {}) {
  const items = new Map(Object.entries(initial))
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, String(value)),
    removeItem: (key: string) => void items.delete(key),
  })
  return items
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('the rounding of a position', () => {
  it('is to two decimals of a degree, about 1 km', () => {
    expect(roundCoordinate(53.55123)).toBe(53.55)
    expect(roundCoordinate(9.99449)).toBe(9.99)
    expect(roundCoordinate(9.99501)).toBe(10)
    expect(roundCoordinate(-33.8688)).toBe(-33.87)
    expect(roundPosition({ latitude: 52.520008, longitude: 13.404954 })).toEqual({ latitude: 52.52, longitude: 13.4 })
  })

  it('leaves no negative zero, which would be written as -0 in a request', () => {
    expect(Object.is(roundCoordinate(-0.001), 0)).toBe(true)
    expect(String(roundCoordinate(-0.004))).toBe('0')
  })
})

describe('the failure of the browser\'s error code', () => {
  it.each([
    [1, 'denied'],
    [2, 'unavailable'],
    [3, 'timeout'],
    [0, 'unavailable'],
    [99, 'unavailable'],
  ])('%i is %s', (code, failure) => {
    expect(failureOfCode(code)).toBe(failure)
  })
})

describe('the position remembered in the browser', () => {
  it('is written rounded, and read back', () => {
    const items = stubStorage()
    writeRememberedPosition({ latitude: 52.520008, longitude: 13.404954 })
    expect(JSON.parse(items.get(LOCATION_STORAGE_KEY)!)).toEqual({ latitude: 52.52, longitude: 13.4 })
    expect(readRememberedPosition()).toEqual({ latitude: 52.52, longitude: 13.4 })
  })

  it('is forgotten', () => {
    const items = stubStorage({ [LOCATION_STORAGE_KEY]: '{"latitude":1,"longitude":2}' })
    forgetRememberedPosition()
    expect(items.has(LOCATION_STORAGE_KEY)).toBe(false)
    expect(readRememberedPosition()).toBeNull()
  })

  it.each([
    ['nothing', undefined],
    ['text that is no JSON', 'not json'],
    ['JSON that is no position', '[1,2]'],
    ['text coordinates', '{"latitude":"52","longitude":"13"}'],
    ['a latitude beyond the poles', '{"latitude":91,"longitude":13}'],
    ['a longitude beyond the date line', '{"latitude":52,"longitude":181}'],
  ])('is none where the storage holds %s', (_name, stored) => {
    stubStorage(stored === undefined ? {} : { [LOCATION_STORAGE_KEY]: stored })
    expect(readRememberedPosition()).toBeNull()
  })

  it('is rounded again where the storage holds a finer one: nothing finer than 1 km is ever used', () => {
    stubStorage({ [LOCATION_STORAGE_KEY]: '{"latitude":52.520008,"longitude":13.404954}' })
    expect(readRememberedPosition()).toEqual({ latitude: 52.52, longitude: 13.4 })
  })

  it('is no failure where the storage refuses: a browser that blocks it', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new DOMException('blocked', 'SecurityError')
      },
      setItem: () => {
        throw new DOMException('full', 'QuotaExceededError')
      },
      removeItem: () => {
        throw new DOMException('blocked', 'SecurityError')
      },
    })
    expect(readRememberedPosition()).toBeNull()
    expect(() => writeRememberedPosition({ latitude: 1, longitude: 2 })).not.toThrow()
    expect(() => forgetRememberedPosition()).not.toThrow()
  })
})
