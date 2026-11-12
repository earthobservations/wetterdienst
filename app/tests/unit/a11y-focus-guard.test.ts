// @vitest-environment happy-dom
import { afterEach, describe, expect, it } from 'vitest'
import { isFocusGuard } from '../e2e/accessibility/focus-guard'

// The keyboard scan does not count Reka's guards as stops. The toast region's proxies are found by where they are
// (Reka UI 2.11.0 gave up their `aria-hidden`), which this holds to the markup `ToastViewport` renders.

function focus(html: string, selector: string) {
  document.body.innerHTML = html
  const node = document.querySelector<HTMLElement>(selector)!
  node.focus()
  return node
}

function REGION(head: string, tail: string) {
  return `
  <button id="before">before</button>
  <div role="region" aria-label="Notifications" tabindex="-1">
    ${head}<ol data-slot="viewport" tabindex="0"></ol>${tail}
  </div>`
}

describe('the keyboard scan\'s focus guards', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('takes both focus proxies of the toast region for guards, with no aria-hidden on them', () => {
    const markup = REGION('<span id="head" tabindex="0" style="position: fixed"></span>', '<span id="tail" tabindex="0" style="position: fixed"></span>')
    expect(focus(markup, '#head')).toBe(document.activeElement)
    expect(isFocusGuard()).toBe(true)
    focus(markup, '#tail')
    expect(isFocusGuard()).toBe(true)
  })

  it('still takes a proxy that has aria-hidden for one', () => {
    focus(REGION('<span id="head" tabindex="0" aria-hidden="true"></span>', ''), '#head')
    expect(isFocusGuard()).toBe(true)
  })

  it('takes Reka\'s focus guard of an open menu for one', () => {
    focus('<span data-reka-focus-guard tabindex="0" id="guard"></span>', '#guard')
    expect(isFocusGuard()).toBe(true)
  })

  it('does not take the list of the toasts, a button in it or a span between the proxies for one', () => {
    const markup = REGION('<span id="head" tabindex="0"></span>', '<span id="tail" tabindex="0"></span>')
      .replace('<ol data-slot="viewport" tabindex="0"></ol>', '<ol data-slot="viewport" tabindex="0"><li><button id="close">x</button></li></ol><span id="middle" tabindex="0"></span>')
    for (const selector of ['#close', 'ol', '#middle', '#before']) {
      focus(markup, selector)
      expect(isFocusGuard(), selector).toBe(false)
    }
  })

  it('does not take a span with tabindex in a region that holds no list of toasts for one', () => {
    focus('<div role="region"><span id="x" tabindex="0"></span><p>text</p></div>', '#x')
    expect(isFocusGuard()).toBe(false)
  })

  it('is false where nothing has the focus', () => {
    document.body.innerHTML = '<p>text</p>'
    expect(isFocusGuard()).toBe(false)
  })
})
