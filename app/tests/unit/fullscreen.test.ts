import { describe, expect, it, vi } from 'vitest'
import {
  exitNativeFullscreen,
  fullscreenElementOf,
  requestNativeFullscreen,
  supportsNativeFullscreen,
} from '../../app/utils/fullscreen'

// The Fullscreen API as a document and an element serve it (GH-4227): present, prefixed, absent, and switched off by the page's
// policy (`document.fullscreenEnabled` false), which is what iPhone Safari answers for an element.

describe('supportsNativeFullscreen', () => {
  const element = { requestFullscreen: vi.fn() }

  it('is true where the document allows it and the element has the call', () => {
    expect(supportsNativeFullscreen({ fullscreenEnabled: true }, element)).toBe(true)
  })

  it('is false where the page may not (a policy, a frame without allowfullscreen) or the browser has none (iPhone Safari)', () => {
    expect(supportsNativeFullscreen({ fullscreenEnabled: false }, element)).toBe(false)
    expect(supportsNativeFullscreen({}, element)).toBe(false)
    expect(supportsNativeFullscreen({ fullscreenEnabled: true }, {})).toBe(false)
  })

  it('takes WebKit\'s prefixed members where the standard ones are not there', () => {
    expect(supportsNativeFullscreen({ webkitFullscreenEnabled: true }, { webkitRequestFullscreen: vi.fn() })).toBe(true)
    expect(supportsNativeFullscreen({ webkitFullscreenEnabled: false }, { webkitRequestFullscreen: vi.fn() })).toBe(false)
  })
})

describe('the element that is full screen', () => {
  it('is the standard one, else the prefixed one, else none', () => {
    const element = {} as Element
    expect(fullscreenElementOf({ fullscreenElement: element })).toBe(element)
    expect(fullscreenElementOf({ webkitFullscreenElement: element })).toBe(element)
    expect(fullscreenElementOf({})).toBeNull()
    expect(fullscreenElementOf({ fullscreenElement: null })).toBeNull()
  })
})

describe('asking for and leaving full screen', () => {
  it('asks the element with the browser\'s own toolbars hidden, and waits for the answer', async () => {
    const requestFullscreen = vi.fn().mockResolvedValue(undefined)
    await requestNativeFullscreen({ requestFullscreen })
    expect(requestFullscreen).toHaveBeenCalledWith({ navigationUI: 'hide' })
  })

  it('passes on a refusal, which is how the app learns to cover the page itself', async () => {
    const requestFullscreen = vi.fn().mockRejectedValue(new TypeError('Permissions check failed'))
    await expect(requestNativeFullscreen({ requestFullscreen })).rejects.toThrow('Permissions check failed')
  })

  it('uses the prefixed call where it is the only one, which answers nothing', async () => {
    const webkitRequestFullscreen = vi.fn()
    await requestNativeFullscreen({ webkitRequestFullscreen })
    expect(webkitRequestFullscreen).toHaveBeenCalledOnce()
  })

  it('leaves by the standard call or the prefixed one', async () => {
    const exitFullscreen = vi.fn().mockResolvedValue(undefined)
    await exitNativeFullscreen({ exitFullscreen })
    expect(exitFullscreen).toHaveBeenCalledOnce()
    const webkitExitFullscreen = vi.fn()
    await exitNativeFullscreen({ webkitExitFullscreen })
    expect(webkitExitFullscreen).toHaveBeenCalledOnce()
    await expect(exitNativeFullscreen({})).resolves.toBeUndefined()
  })
})
