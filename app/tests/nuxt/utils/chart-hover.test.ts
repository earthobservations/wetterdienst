import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { HOVER_DISMISSED, installChartHoverDismiss } from '~/utils/chart-hover'

// Escape dismisses the hover label of a Plotly chart under the pointer (WCAG 1.4.13). The label is hidden
// by main.css where the mark is set, which this holds to being set and taken away; the real browser
// (tests/e2e/accessibility.spec.ts, `hover label of the charts`) holds the label to being gone.
describe('dismissing the hover label of a chart by Escape', () => {
  let stop: (() => void) | undefined
  let chart: HTMLElement
  let other: HTMLElement
  let inner: SVGElement

  beforeEach(() => {
    chart = document.body.appendChild(document.createElement('div'))
    chart.className = 'js-plotly-plot'
    inner = chart.appendChild(document.createElementNS('http://www.w3.org/2000/svg', 'rect'))
    other = document.body.appendChild(document.createElement('div'))
    other.className = 'js-plotly-plot'
    stop = installChartHoverDismiss(document)
  })

  afterEach(() => {
    stop?.()
    stop = undefined
    document.body.innerHTML = ''
  })

  const move = (target: Element, x: number, y: number) =>
    target.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, clientX: x, clientY: y }))
  const escape = (key = 'Escape') => document.body.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))
  const dismissed = (el: Element) => el.hasAttribute(HOVER_DISMISSED)

  it('marks the chart under the pointer on Escape, whatever the focus is on', () => {
    move(inner, 10, 10)
    escape()
    expect(dismissed(chart)).toBe(true)
    expect(dismissed(other)).toBe(false)
  })

  it('leaves the mark where the pointer rests, and takes it away when the pointer moves', () => {
    move(inner, 10, 10)
    escape()
    // the same position again, as a browser sends after a layout: not a move
    move(inner, 10, 10)
    expect(dismissed(chart)).toBe(true)
    move(inner, 11, 10)
    expect(dismissed(chart)).toBe(false)
  })

  it('takes the mark away when the pointer goes to another chart or off the charts', () => {
    move(inner, 10, 10)
    escape()
    move(other, 10, 10)
    expect(dismissed(chart)).toBe(false)

    move(inner, 10, 10)
    escape()
    move(document.body, 10, 10)
    expect(dismissed(chart)).toBe(false)
  })

  it('takes the mark away when the pointer leaves the window', () => {
    move(inner, 10, 10)
    escape()
    document.documentElement.dispatchEvent(new PointerEvent('pointerleave'))
    expect(dismissed(chart)).toBe(false)
    // and a key pressed with no pointer on a chart marks none
    escape()
    expect(dismissed(chart)).toBe(false)
  })

  it('marks nothing on another key, or with the pointer off the charts', () => {
    move(inner, 10, 10)
    escape('Enter')
    expect(dismissed(chart)).toBe(false)
    move(document.body, 10, 10)
    escape()
    expect(dismissed(chart)).toBe(false)
  })

  it('does not stop Escape, which still closes a dialog or a menu', () => {
    move(inner, 10, 10)
    let seen: KeyboardEvent | undefined
    document.addEventListener('keydown', (event) => {
      seen = event
    }, { once: true })
    escape()
    expect(seen?.defaultPrevented).toBe(false)
  })

  it('stops listening, and takes the mark away, when it is stopped', () => {
    // a document of its own, as the page's has the app's own listener on it
    const doc = document.implementation.createHTMLDocument()
    const plot = doc.body.appendChild(doc.createElement('div'))
    plot.className = 'js-plotly-plot'
    const off = installChartHoverDismiss(doc)
    plot.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, clientX: 1, clientY: 1 }))
    doc.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(dismissed(plot)).toBe(true)
    off()
    expect(dismissed(plot)).toBe(false)
    plot.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, clientX: 1, clientY: 1 }))
    doc.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(dismissed(plot)).toBe(false)
  })
})
