// @vitest-environment happy-dom
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { shouldCancelDialogTouch } from '../../app/utils/dialog-touch'

vi.mock('@tailwindcss/vite', () => ({ default: () => ({ name: 'tailwindcss-stub' }) }))

// Which finger moves inside an open dialog are cancelled (GH-3761). happy-dom has no layout, so the boxes are served
// their scroll metrics; the guard reads them and the box's `overflow`.

function box(element: Element, metrics: { top?: number, height: number, content: number, overflow?: string }) {
  const el = element as HTMLElement
  el.style.overflowY = metrics.overflow ?? 'auto'
  Object.defineProperties(el, {
    scrollTop: { value: metrics.top ?? 0, configurable: true },
    clientHeight: { value: metrics.height, configurable: true },
    scrollHeight: { value: metrics.content, configurable: true },
  })
  return el
}

function dialog(list: { top?: number, content?: number } = {}) {
  document.body.innerHTML = `
    <main id="page"><p id="behind">behind</p></main>
    <div role="dialog" id="dialog">
      <div id="field"><input id="input"></div>
      <div id="list"><div id="option">option</div></div>
      <p id="status">status</p>
    </div>`
  box(document.getElementById('dialog')!, { height: 576, content: 576, overflow: 'hidden' })
  box(document.getElementById('list')!, { top: list.top, height: 480, content: list.content ?? 1895 })
  return (id: string) => document.getElementById(id)!
}

// the finger moves down (dy > 0) to bring up what is above, or up (dy < 0) to bring up what is below
const DOWN = 12
const UP = -12

describe('a one-finger move in an open dialog (GH-3761)', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('is let through where the list can still scroll the way the finger goes', () => {
    const at = dialog({ top: 0 })
    // at its top, it scrolls down (the finger goes up) ...
    expect(shouldCancelDialogTouch(at('option'), 0, UP)).toBe(false)
    // ... and in the middle both ways
    const middle = dialog({ top: 400 })
    expect(shouldCancelDialogTouch(middle('option'), 0, UP)).toBe(false)
    expect(shouldCancelDialogTouch(middle('option'), 0, DOWN)).toBe(false)
  })

  it('is cancelled where the list is at its top and the finger pulls further up, the state right after opening', () => {
    const at = dialog({ top: 0 })
    expect(shouldCancelDialogTouch(at('option'), 0, DOWN)).toBe(true)
    expect(shouldCancelDialogTouch(at('list'), 0, DOWN)).toBe(true)
  })

  it('is cancelled where the list is at its end and the finger pushes further on', () => {
    // 1895 - 480 = 1415: scrolled to the end
    const at = dialog({ top: 1415 })
    expect(shouldCancelDialogTouch(at('option'), 0, UP)).toBe(true)
    expect(shouldCancelDialogTouch(at('option'), 0, DOWN)).toBe(false)
  })

  it('is cancelled on a list that does not overflow, and on the parts that do not scroll', () => {
    const short = dialog({ content: 480 })
    expect(shouldCancelDialogTouch(short('option'), 0, UP)).toBe(true)
    expect(shouldCancelDialogTouch(short('option'), 0, DOWN)).toBe(true)
    const at = dialog({ top: 400 })
    for (const id of ['input', 'field', 'status', 'dialog']) {
      expect(shouldCancelDialogTouch(at(id), 0, UP), id).toBe(true)
      expect(shouldCancelDialogTouch(at(id), 0, DOWN), id).toBe(true)
    }
  })

  it('is cancelled on a list that overflows but may not scroll (overflow hidden)', () => {
    const at = dialog({ top: 400 })
    box(at('list'), { top: 400, height: 480, content: 1895, overflow: 'hidden' })
    expect(shouldCancelDialogTouch(at('option'), 0, UP)).toBe(true)
  })

  it('is not this guard\'s outside a dialog, or for a move that did not move', () => {
    const at = dialog({ top: 0 })
    expect(shouldCancelDialogTouch(at('behind'), 0, UP)).toBe(false)
    expect(shouldCancelDialogTouch(at('option'), 0, 0)).toBe(false)
    expect(shouldCancelDialogTouch(null, 0, UP)).toBe(false)
    expect(shouldCancelDialogTouch(document, 0, UP)).toBe(false)
  })

  it('follows the dominant axis: a sideways move on a list that scrolls only up and down is cancelled', () => {
    const at = dialog({ top: 400 })
    expect(shouldCancelDialogTouch(at('option'), 30, 5)).toBe(true)
  })
})

describe('the viewport of the page (GH-3761)', () => {
  beforeEach(() => {
    vi.stubGlobal('defineNuxtConfig', (config: any) => config)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('covers the window, so that the safe-area insets are reported and the tab bar can stand on the window\'s foot', async () => {
    const config = (await import('../../nuxt.config')).default as any
    expect(config.app.head.viewport).toContain('viewport-fit=cover')
    expect(config.app.head.viewport).toContain('width=device-width')
    // and the header, which now has the status bar's room at its top, and the sides read them too
    const css = readFileSync(join(__dirname, '..', '..', 'app', 'assets', 'css', 'main.css'), 'utf8')
    for (const side of ['top', 'left', 'right', 'bottom'])
      expect(css).toContain(`env(safe-area-inset-${side}`)
  })
})
