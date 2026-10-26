import { describe, expect, it } from 'vitest'
import { frameGuard, isFramedByAnotherOrigin, isWidgetPath } from '../../app/utils/frame-guard'

// The page's own answer to being framed by another origin: behind a proxy that rewrites the path, the server
// cannot tell the widget from another page, so the page does (app/utils/frame-guard.ts).

type Kind = 'own' | 'other'

/** A window of an origin: the address of one of this origin can be read, that of another origin throws */
function make(kind: Kind, parent?: Window): Window {
  const win = {} as Window
  Object.defineProperty(win, 'parent', { get: () => parent ?? win })
  Object.defineProperty(win, 'location', {
    get: () => {
      if (kind === 'other')
        throw new DOMException('Blocked a frame from accessing a cross-origin frame.', 'SecurityError')
      return { href: 'https://app.example/' }
    },
  })
  return win
}

/** The window of the page with the given ancestors, from its parent up to the top window, which is the last */
function windowIn(...ancestors: Kind[]): Window {
  let above: Window | undefined
  for (const kind of [...ancestors].reverse())
    above = make(kind, above)
  return make('own', above)
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
    expect(isFramedByAnotherOrigin(windowIn())).toBe(false)
  })

  it('is false in frames of the app\'s own origin, all the way up, which is the app itself', () => {
    expect(isFramedByAnotherOrigin(windowIn('own'))).toBe(false)
    expect(isFramedByAnotherOrigin(windowIn('own', 'own', 'own'))).toBe(false)
  })

  it('is true where the parent is another origin\'s, and its location cannot be read', () => {
    expect(isFramedByAnotherOrigin(windowIn('other'))).toBe(true)
  })

  it('is true where a frame of another origin sits between the app and a top window of its own origin', () => {
    expect(isFramedByAnotherOrigin(windowIn('other', 'own'))).toBe(true)
    expect(isFramedByAnotherOrigin(windowIn('own', 'other', 'own'))).toBe(true)
  })

  it('is true where asking for an ancestor throws for another reason: a window that cannot tell is framed', () => {
    const win = {} as Window
    Object.defineProperty(win, 'parent', {
      get: () => {
        throw new Error('no parent')
      },
    })
    expect(isFramedByAnotherOrigin(win)).toBe(true)
  })

  it('is true for a window too deep in frames to ask all the way up', () => {
    expect(isFramedByAnotherOrigin(windowIn(...Array.from({ length: 40 }, () => 'own' as const)))).toBe(true)
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
