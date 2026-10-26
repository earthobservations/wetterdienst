import { describe, expect, it } from 'vitest'
import { allowsNavigation, frameGuard, guardNavigation, isFramedByAnotherOrigin, isWidgetPath } from '../../app/utils/frame-guard'

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

describe('isWidgetPath', () => {
  it.each(['/widget', '/widget/'])('takes %s for the widget', (path) => {
    expect(isWidgetPath(path)).toBe(true)
  })

  // the router matches these to the widget, case-insensitively; the server does not frame them freely, so neither
  // does the page draw them
  it.each(['/Widget', '/WIDGET', '/Widget/', '/widget//', '//widget', '/%77idget', '/widgetx', '/widget/x', '/', '', undefined])('does not take %s for the widget', (path) => {
    expect(isWidgetPath(path)).toBe(false)
  })
})

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
  it.each(['/widget', '/widget/'])('draws the widget at %s where it is framed', (path) => {
    expect(frameGuard(true, path)).toEqual({ blank: false })
  })

  it.each(['/', '/explorer', '/meteogram', '/providers/dwd', '/Widget', '/WIDGET', '/Widget/', '/widgetx', undefined])('draws nothing at %s where it is framed', (path) => {
    expect(frameGuard(true, path)).toEqual({ blank: true })
  })

  it.each(['/widget', '/', '/explorer', '/Widget', undefined])('draws everything at %s where it is not framed', (path) => {
    expect(frameGuard(false, path)).toEqual({ blank: false })
  })
})

describe('allowsNavigation', () => {
  it('stops a navigation away from the widget where it is framed', () => {
    for (const to of ['/', '/explorer', '/Widget', '/widgetx', undefined])
      expect(allowsNavigation(true, to), String(to)).toBe(false)
  })

  it('lets a framed page stay on or return to the widget', () => {
    expect(allowsNavigation(true, '/widget')).toBe(true)
    expect(allowsNavigation(true, '/widget/')).toBe(true)
  })

  it('stops nothing where the page is not framed', () => {
    for (const to of ['/', '/explorer', '/widget', undefined])
      expect(allowsNavigation(false, to)).toBe(true)
  })
})

describe('guardNavigation', () => {
  /** A router that keeps the guards it is given, and runs them */
  function routerWith() {
    const guards: ((to: { path: string }) => false | undefined)[] = []
    return {
      router: { beforeEach: (guard: (to: { path: string }) => false | undefined) => void guards.push(guard) },
      navigate: (path: string) => guards.every(guard => guard({ path }) !== false),
      guards,
    }
  }

  it('puts a guard on the router of a framed page that stops every navigation but one to the widget', () => {
    const { router, navigate, guards } = routerWith()
    guardNavigation(router, true)

    expect(guards).toHaveLength(1)
    expect(navigate('/widget')).toBe(true)
    expect(navigate('/widget/')).toBe(true)
    expect(navigate('/explorer')).toBe(false)
    expect(navigate('/Widget')).toBe(false)
    expect(navigate('/')).toBe(false)
  })

  it('leaves the router of a page that is not framed alone', () => {
    const { router, guards, navigate } = routerWith()
    guardNavigation(router, false)

    expect(guards).toHaveLength(0)
    expect(navigate('/explorer')).toBe(true)
  })
})
