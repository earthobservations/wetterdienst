import type { BarScrollState } from '../../app/utils/bar-scroll'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { BAR_HIDE_AFTER, BAR_SCROLL_THRESHOLD, shownBarScroll, stepBarScroll } from '../../app/utils/bar-scroll'

// The direction logic of the bars that hide on a phone (GH-4226): a page walked up and down, the state kept between steps.
const PAGE = 5000
const LONG = 5000 - 800

/** Walks the page through the offsets in turn and answers the state after each */
function walk(offsets: number[], from: BarScrollState = shownBarScroll(), max = LONG) {
  const states: BarScrollState[] = []
  let state = from
  for (const y of offsets) {
    state = stepBarScroll(state, { y, max })
    states.push(state)
  }
  return states
}
const shown = (offsets: number[], from?: BarScrollState) => walk(offsets, from).map(state => state.shown)

describe('the bars at the top of a page', () => {
  it('are shown at the start, with nothing to count from', () => {
    expect(shownBarScroll()).toEqual({ shown: true, anchor: 0 })
  })

  it('are shown at the top, however they were', () => {
    const hidden: BarScrollState = { shown: false, anchor: 900 }
    expect(stepBarScroll(hidden, { y: 0, max: LONG })).toEqual({ shown: true, anchor: 0 })
    // and above it: iOS Safari's rubber band reports a negative offset
    expect(stepBarScroll(hidden, { y: -40, max: LONG })).toEqual({ shown: true, anchor: 0 })
  })

  it('are shown on a page that does not scroll', () => {
    const hidden: BarScrollState = { shown: false, anchor: 300 }
    expect(stepBarScroll(hidden, { y: 0, max: 0 })).toEqual({ shown: true, anchor: 0 })
    expect(stepBarScroll(hidden, { y: 120, max: -200 })).toEqual({ shown: true, anchor: 0 })
  })

  it('hand back the very same state when nothing changed, so that nothing is written', () => {
    const state = shownBarScroll()
    expect(stepBarScroll(state, { y: 0, max: LONG })).toBe(state)
    expect(stepBarScroll(state, { y: 0, max: 0 })).toBe(state)
  })
})

describe('the threshold', () => {
  it('is more than a tremble and less than a flick', () => {
    expect(BAR_SCROLL_THRESHOLD).toBeGreaterThanOrEqual(8)
    expect(BAR_SCROLL_THRESHOLD).toBeLessThanOrEqual(24)
  })

  it('hides the bars after the threshold of travel down, and not before', () => {
    // the bars were shown with the page at `start` (a turn upwards, a focus in a bar)
    const start = BAR_HIDE_AFTER + 100
    const from = shownBarScroll(start)
    expect(shown([start + BAR_SCROLL_THRESHOLD - 1], from)).toEqual([true])
    expect(shown([start + BAR_SCROLL_THRESHOLD], from)).toEqual([false])
  })

  it('shows them again after the threshold of travel up, and not before', () => {
    const hidden: BarScrollState = { shown: false, anchor: 900 }
    expect(shown([900 - BAR_SCROLL_THRESHOLD + 1], hidden)).toEqual([false])
    expect(shown([900 - BAR_SCROLL_THRESHOLD], hidden)).toEqual([true])
  })

  it('takes a tremble for nothing, from either side', () => {
    // bars in view, a finger trembling around 300
    const settled = shownBarScroll(300)
    const trembling = [304, 297, 302, 299, 303, 298]
    expect(shown(trembling, settled).every(Boolean)).toBe(true)
    // bars away, the same
    const away = walk([300, 300 + BAR_SCROLL_THRESHOLD])[1]!
    expect(away.shown).toBe(false)
    const around = away.anchor
    const shakes = [around - 4, around + 3, around - 5, around + 2]
    expect(shown(shakes, away).every(shown => !shown)).toBe(true)
  })

  it('counts the travel from the farthest point, not from the step before', () => {
    // down by 3 px at a time is a scroll down all the same, and up by 3 px at a time is one up
    const down = Array.from({ length: 12 }, (_, step) => BAR_HIDE_AFTER + 60 + step * 3)
    expect(shown(down).at(-1)).toBe(false)
    const hidden = walk(down)[11]!
    const up = Array.from({ length: 8 }, (_, step) => hidden.anchor - (step + 1) * 3)
    const states = shown(up, hidden)
    expect(states.slice(0, 3)).toEqual([false, false, false])
    expect(states.at(-1)).toBe(true)
  })

  it('turns round at once: the way back counts from where the page was farthest', () => {
    // 2000 px down, then a flick of the threshold back up
    expect(shown([2000, 2000 - BAR_SCROLL_THRESHOLD])).toEqual([false, true])
    // down a little further after the turn: the bars hide again by the threshold, not by the whole way
    const states = walk([2000, 1900, 1900 + BAR_SCROLL_THRESHOLD])
    expect(states.map(state => state.shown)).toEqual([false, true, false])
  })
})

describe('the first pixels of a page', () => {
  it('keep the bars: they do not hide before the page has left its top by about a bar', () => {
    expect(BAR_HIDE_AFTER).toBeGreaterThanOrEqual(40)
    expect(shown([10, 30, BAR_HIDE_AFTER])).toEqual([true, true, true])
  })

  it('hide on the way down once past it', () => {
    expect(shown([10, BAR_HIDE_AFTER + 1, BAR_HIDE_AFTER + 40]).at(-1)).toBe(false)
  })

  it('come back on the way to the top, from any height, in one step', () => {
    const away = walk([900, 1200])[1]!
    expect(away.shown).toBe(false)
    expect(stepBarScroll(away, { y: 0, max: LONG }).shown).toBe(true)
  })
})

describe('the ends of the page', () => {
  it('read a position past the foot as the foot: the bounce back is no scroll up', () => {
    const atFoot = walk([LONG - 100, LONG])[1]!
    expect(atFoot.shown).toBe(false)
    // iOS Safari reports the rubber band: beyond the end, then back to it
    const bounce = shown([LONG + 30, LONG + 60, LONG + 20, LONG + 5, LONG], atFoot)
    expect(bounce).toEqual([false, false, false, false, false])
  })

  it('still show the bars for a real turn at the foot', () => {
    const atFoot = walk([LONG - 100, LONG])[1]!
    expect(shown([LONG - BAR_SCROLL_THRESHOLD], atFoot)).toEqual([true])
  })

  it('read the rubber band above the top as the top', () => {
    expect(shown([800, 1000, -30, -60, -5, 0]).slice(2)).toEqual([true, true, true, true])
  })

  it('know the page is the same page whatever its length', () => {
    expect(PAGE).toBeGreaterThan(LONG)
    expect(walk([2000, 2000 + 50], shownBarScroll(), 10_000).at(-1)!.shown).toBe(false)
  })
})

describe('reduced motion and the safe areas, in the stylesheet', () => {
  const css = readFileSync(fileURLToPath(new URL('../../app/assets/css/main.css', import.meta.url)), 'utf-8')

  /** The body of the first rule whose selector line is `selector`, inside the whole of `css` or of `within` */
  function ruleOf(selector: string, within = css) {
    const start = within.indexOf(`${selector} {`)
    expect(start, `${selector} has a rule`).toBeGreaterThan(-1)
    return within.slice(start, within.indexOf('}', start))
  }

  it('animates the bars only for a reader who has not asked for no motion', () => {
    const start = css.indexOf('@media (prefers-reduced-motion: reduce) {\n  .app-header,')
    expect(start).toBeGreaterThan(-1)
    const block = css.slice(start, css.indexOf('\n}\n', start) + 3)
    // every element that moves with the bars has no transition, in either state: they are there or they are not
    for (const selector of ['.app-header', '.app-tabbar', '.bar-sticky', '.app-toast-viewport', ':root[data-bars="hidden"]'])
      expect(block).toContain(selector)
    expect(block).toMatch(/transition:\s*none/)
    // and it is the last word: nothing after it gives one of them a transition again
    expect(css.slice(start + block.length)).not.toMatch(/\.(app-header|app-tabbar|bar-sticky|app-toast-viewport)[^{}]*\{[^}]*\btransition:\s*(?!none)/)
  })

  it('slides both bars by transforms the compositor runs, and only below 40 rem in a window that is not low', () => {
    // no registered, inherited number on the root: every element of the page restyled on every frame of the slide
    expect(css).not.toContain('@property --bars-shown')
    expect(css).not.toMatch(/:root\s*\{[^}]*transition:/)
    const phone = css.slice(css.indexOf('@media (width < 40rem) and (min-height: 30.01rem) {'))
    // set on the four elements that read it, not on the root
    expect(phone).toMatch(/:root\[data-bars="hidden"\] :is\(\.app-header, \.app-tabbar, \.bar-sticky, \.app-toast-viewport\) \{\s*--bars-shown: 0;/)
    const header = ruleOf('.app-header', phone)
    expect(header).toContain('transform: translateY(calc(var(--header-height) * (var(--bars-shown, 1) - 1)))')
    // the tab bar goes by its own height, the home indicator's room included
    const tabbar = ruleOf('.app-tabbar', phone)
    expect(tabbar).toContain('transform: translateY(calc(var(--tabbar-height) * (1 - var(--bars-shown, 1))))')
    // no layout: neither bar changes height, top or bottom with it
    expect(`${header}${tabbar}`).not.toMatch(/\b(height|top|bottom|margin[a-z-]*)\s*:/)
    // each transitions the property that moves it (the bars' transform, the preview's top, the toasts' bottom), by one time
    expect(phone).toMatch(/:is\(\.app-header, \.app-tabbar, \.bar-sticky, \.app-toast-viewport\) \{\s*transition:\s*transform 200ms ease-out,\s*top 200ms ease-out,\s*bottom 200ms ease-out;/)
  })

  it('keeps the home indicator under the tab bar, which is what the slide is measured by', () => {
    expect(css).toMatch(/--tabbar-height:\s*calc\(4\.25rem \+ var\(--safe-bottom\)\)/)
    expect(ruleOf('.app-tabbar')).toContain('padding: 0 var(--safe-right) var(--safe-bottom) var(--safe-left)')
  })

  it('has what sticks under the top bar follow it', () => {
    expect(ruleOf('.bar-sticky')).toContain('top: calc(var(--header-height) * var(--bars-shown, 1))')
  })

  it('makes the top bar 44 px of content on a phone, after the low window sets its own', () => {
    const slim = css.indexOf('--header-bar: calc(2.75rem + 1px)')
    const low = css.indexOf('--header-bar: 3.5rem')
    expect(slim).toBeGreaterThan(low)
    expect(low).toBeGreaterThan(-1)
  })
})
