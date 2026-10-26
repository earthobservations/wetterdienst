import { describe, expect, it } from 'vitest'
import { allowsNavigation, frameGuard, isFramedByAnotherOrigin, WIDGET_ROUTE } from '../../app/utils/frame-guard'

// The page's own answer to being framed by another origin: behind a proxy that rewrites the path, the server
// cannot tell the widget from another page, so the page does (app/utils/frame-guard.ts).

/** A window whose `top` is `top`, or is another origin's: reading its location throws */
function windowIn(top: 'self' | 'same-origin' | 'other-origin' | 'throws'): Pick<Window, 'self' | 'top'> {
  const me = {} as Window
  const win = { self: me, top: me } as Pick<Window, 'self' | 'top'>
  if (top === 'same-origin') {
    win.top = { location: { href: 'https://app.example/' } } as unknown as Window
  }
  else if (top === 'other-origin') {
    win.top = new Proxy({}, { get() {
      throw new DOMException('Blocked a frame from accessing a cross-origin frame.', 'SecurityError')
    } }) as unknown as Window
  }
  else if (top === 'throws') {
    Object.defineProperty(win, 'top', { get() {
      throw new Error('no top')
    } })
  }
  return win
}

describe('isFramedByAnotherOrigin', () => {
  it('is false for a window that is its own top', () => {
    expect(isFramedByAnotherOrigin(windowIn('self'))).toBe(false)
  })

  it('is false in a frame of the app\'s own origin, which is the app itself', () => {
    expect(isFramedByAnotherOrigin(windowIn('same-origin'))).toBe(false)
  })

  it('is true where the top window is another origin\'s, and its location cannot be read', () => {
    expect(isFramedByAnotherOrigin(windowIn('other-origin'))).toBe(true)
  })

  it('is true where asking for the top window throws: a window that cannot tell is framed', () => {
    expect(isFramedByAnotherOrigin(windowIn('throws'))).toBe(true)
  })
})

describe('frameGuard', () => {
  it('draws the widget where it is framed', () => {
    expect(frameGuard(true, WIDGET_ROUTE)).toEqual({ blank: false })
  })

  it.each(['index', 'explorer', 'meteogram', 'providers-provider', undefined, null])('draws nothing at %s where it is framed', (route) => {
    expect(frameGuard(true, route)).toEqual({ blank: true })
  })

  it.each([WIDGET_ROUTE, 'index', 'explorer', undefined])('draws everything at %s where it is not framed', (route) => {
    expect(frameGuard(false, route)).toEqual({ blank: false })
  })
})

describe('allowsNavigation', () => {
  it('stops a navigation away from the widget where it is framed', () => {
    expect(allowsNavigation(true, 'index', false)).toBe(false)
    expect(allowsNavigation(true, 'explorer', false)).toBe(false)
    expect(allowsNavigation(true, undefined, false)).toBe(false)
  })

  it('lets a framed page stay on or return to the widget, and load', () => {
    expect(allowsNavigation(true, WIDGET_ROUTE, false)).toBe(true)
    expect(allowsNavigation(true, 'index', true)).toBe(true)
  })

  it('stops nothing where the page is not framed', () => {
    for (const to of ['index', 'explorer', WIDGET_ROUTE, undefined])
      expect(allowsNavigation(false, to, false)).toBe(true)
  })
})
