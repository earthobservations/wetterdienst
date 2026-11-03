import type { Page } from '@playwright/test'
import type { Backend } from './mock-backend'
import type { ScanResult, Where } from './scan'
import AxeBuilder from '@axe-core/playwright'
import { addViolations, record, settle } from './scan'

// What axe cannot see from a page at rest: the colours of an element that is hovered or focused
// (1.4.3, GH-2991), and what keyboard use does -- whether a focused element shows that it is (2.4.7),
// is not hidden behind something (2.4.11) and whether Tab ever leaves the page (2.1.2). The scan walks
// the tab order of the page as it stands and hovers what can be hovered.

/** What a pointer can act on, and what the app gives a hover style to without making it interactive */
const HOVERABLE = 'a[href], button:not([disabled]), [role="tab"], [role="option"], [role="menuitem"], summary, label, [class*="hover:"]'

/** The element being looked at is marked, so that axe, which takes selectors, can be pointed at it */
const PROBE = 'data-a11y-probe'

/** Rules whose ids are the app's own, where axe has none: the WCAG criterion each one tests */
export const CUSTOM_RULES = {
  'focus-not-visible': 'A focused element shows no focus indicator (WCAG 2.4.7)',
  'focus-indicator-contrast': 'The focus indicator has less than 3:1 against the colour behind it (WCAG 1.4.11)',
  'focus-obscured': 'A focused element is entirely hidden behind other content (WCAG 2.4.11)',
  'focus-lost': 'Tab moves the focus out of the page into nowhere before the order has come round (WCAG 2.1.2)',
} as const

type Found = ScanResult['found']

function add(found: Found, rule: keyof typeof CUSTOM_RULES, impact: string, target: string) {
  const before = found[rule]
  found[rule] = {
    impact: before?.impact ?? impact,
    nodes: (before?.nodes ?? 0) + 1,
    help: CUSTOM_RULES[rule],
    targets: [...(before?.targets ?? []), target].slice(0, 5),
  }
}

/** Wait for the transitions a hover or a focus starts: until they have ended the colour is half way */
async function transitionsDone(page: Page) {
  await page.waitForFunction(() => document.getAnimations().every(animation =>
    animation.playState !== 'running' || animation.effect?.getComputedTiming().iterations === Infinity,
  ), undefined, { timeout: 3000 }).catch(() => {})
}

/** Run axe's colour contrast rule on the element that carries the probe mark, as it looks now */
async function contrastOfProbe(page: Page, found: Found, context: string): Promise<string> {
  try {
    const axe = await new AxeBuilder({ page })
      .include(`[${PROBE}]`)
      .withRules(['color-contrast'])
      .analyze()
    addViolations(found, axe.violations, context)
    return axe.testEngine.version
  }
  catch (error) {
    // an option of a virtualised list that was drawn anew while the scan settled, or a menu that closed
    // under it: the element is gone and so is the state in which it was looked at
    if (error instanceof Error && error.message.includes('No elements found for include'))
      return ''
    throw error
  }
}

/** Hover every element a pointer can act on, one by one, and check the contrast of what it shows then */
export async function scanHover(page: Page, backend: Backend, where: Where, _options: { keepFocus?: boolean } = {}): Promise<ScanResult> {
  await settle(page, backend)
  const found: Found = {}
  const candidates = page.locator(HOVERABLE)
  const count = await candidates.count()
  let engine = ''
  // elements with the same classes under a parent with the same classes look the same hovered (a row of
  // chips, a list of options): the first of each is enough, and a page of hundreds takes minutes otherwise
  const looked = new Set<string>()
  for (let index = 0; index < count; index++) {
    const element = candidates.nth(index)
    if (!(await element.isVisible()))
      continue
    const signature = await element.evaluate(node => `${node.tagName}|${node.className}|${node.parentElement?.className}|${node.getAttribute('role')}`)
    if (looked.has(signature))
      continue
    looked.add(signature)
    // a hover style on something the pointer cannot reach (under an overlay, off screen) is no state
    try {
      await element.scrollIntoViewIfNeeded({ timeout: 2000 })
      await element.hover({ timeout: 2000 })
    }
    catch {
      continue
    }
    const name = await element.evaluate((node, probe) => {
      node.setAttribute(probe, '')
      const text = (node.getAttribute('aria-label') ?? node.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 40)
      return `${node.tagName.toLowerCase()}${node.id ? `#${node.id}` : ''} "${text}"`
    }, PROBE)
    try {
      // the transition a hover starts has to end before the colour is the one that is read
      await transitionsDone(page)
      engine = (await contrastOfProbe(page, found, `hover: ${name} `)) || engine
    }
    finally {
      await element.evaluate((node, probe) => node.removeAttribute(probe), PROBE).catch(() => {})
    }
  }
  await page.mouse.move(0, 0)
  return record(where, engine, found)
}

/** What the page says about the element that has the focus */
interface Focused {
  /** Nothing in the page has the focus: the browser has it, or the body */
  none: boolean
  /**
   * Reka's focus guard: an invisible stop at either end of an open menu, or the focus proxy at either end of
   * the toast region, which hands the focus on or which the next Tab leaves
   */
  guard?: boolean
  /** A short description for a message */
  name: string
  indicator: boolean
  /** The best contrast ratio of the focus indicator with what is behind it; undefined where it is the highlight of an option */
  indicatorRatio?: number
  /** Whether every point sampled on the element lands on something that is not the element */
  obscured: boolean
  /** The element is the same one as `previous` was, for the end of the tab order */
  key: string
}

async function describeFocus(page: Page): Promise<Focused> {
  return page.evaluate((probe) => {
    document.querySelectorAll(`[${probe}]`).forEach(node => node.removeAttribute(probe))
    const node = document.activeElement as HTMLElement | null
    if (!node || node === document.body || node === document.documentElement)
      return { none: true, name: '', indicator: true, obscured: false, key: '' }
    // the toast region's proxies (`ToastViewport`'s `FocusProxy`) are a span, `aria-hidden`, a pixel clipped to
    // nothing at the window's corner, first and last in the region beside the list of the toasts: they send the
    // focus into the toasts or out of them in the order of the page, and the next Tab leaves them. They are not
    // content that could be covered (Firefox's walk ended on one, at -2,-2, as `focus-obscured`).
    const region = node.parentElement
    const toastProxy = node.tagName === 'SPAN' && node.getAttribute('aria-hidden') === 'true'
      && region?.getAttribute('role') === 'region' && region.querySelector(':scope > ol[data-slot="viewport"]') != null
      && (node === region.firstElementChild || node === region.lastElementChild)
    if (node.hasAttribute('data-reka-focus-guard') || toastProxy)
      return { none: false, guard: true, name: '', indicator: true, obscured: false, key: '' }
    node.setAttribute(probe, '')
    const text = (node.getAttribute('aria-label') ?? node.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 40)
    const classes = [...node.classList].slice(0, 3).join('.')
    const name = `${node.tagName.toLowerCase()}${node.id ? `#${node.id}` : classes ? `.${classes}` : ''} "${text}"`

    // the ring of Tailwind's `focus-visible:ring` is a box-shadow, Nuxt UI's navigation links draw it on a
    // pseudo-element, and Reka's menu items and options show the focus as a highlighted background
    const indicates = (style: CSSStyleDeclaration) =>
      (style.outlineStyle !== 'none' && Number.parseFloat(style.outlineWidth) > 0)
      || (style.boxShadow !== 'none' && style.boxShadow !== '')
    const highlighted = node.hasAttribute('data-highlighted') || node.getAttribute('aria-selected') === 'true'
    const styles = [undefined, '::before', '::after'].map(pseudo => getComputedStyle(node, pseudo))
    const indicator = highlighted || styles.some(indicates)

    // the colours the indicator is drawn in: an outline, and the rings (a shadow with no blur and a spread)
    const rgba = (css: string) => {
      const canvas = document.createElement('canvas')
      canvas.width = canvas.height = 1
      const context = canvas.getContext('2d', { willReadFrequently: true })!
      context.fillStyle = css
      context.fillRect(0, 0, 1, 1)
      const [r, g, b, a] = context.getImageData(0, 0, 1, 1).data as unknown as number[]
      return [r!, g!, b!, a! / 255] as const
    }
    const over = (top: readonly number[], bottom: readonly number[]) => [0, 1, 2].map(i => top[i]! * top[3]! + bottom[i]! * (1 - top[3]!))
    // what is behind the indicator: an outline or a ring around the element lies on what is behind the element,
    // an inset one on the element's own background; the first opaque background up the tree, with the
    // translucent ones over it
    const backdrop = (start: Element | null) => {
      const layers: Array<readonly number[]> = []
      for (let current = start; current; current = current.parentElement) {
        const layer = rgba(getComputedStyle(current).backgroundColor)
        if (layer[3]! > 0)
          layers.push(layer)
        if (layer[3]! >= 0.99)
          break
      }
      let behind: number[] = [255, 255, 255]
      for (const layer of layers.reverse())
        behind = over(layer, [...behind, 1])
      return behind
    }
    const outside = backdrop(node.parentElement)
    const inside = backdrop(node)
    const luminance = (c: readonly number[]) => {
      const [r, g, b] = c.map(v => v / 255).map(v => v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
      return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
    }
    const ratio = (c: readonly number[], behind: readonly number[]) => {
      const [hi, lo] = [luminance(c), luminance(behind)].sort((x, y) => y - x)
      return (hi! + 0.05) / (lo! + 0.05)
    }
    const COLOUR = /(?:rgba?|color|oklab|oklch|lab|lch|hsla?)\([^)]*\)|#[\da-f]{3,8}/gi
    // each colour the indicator is drawn in, with what it lies on: an outline, and the rings (a shadow with no blur and a spread)
    const drawn: Array<{ colour: readonly number[], behind: readonly number[] }> = []
    for (const style of styles) {
      if (style.outlineStyle !== 'none' && Number.parseFloat(style.outlineWidth) > 0)
        drawn.push({ colour: rgba(style.outlineColor), behind: Number.parseFloat(style.outlineOffset) < 0 ? inside : outside })
      for (const shadow of style.boxShadow === 'none' ? [] : style.boxShadow.split(/,(?![^(]*\))/)) {
        const [colour] = shadow.match(COLOUR) ?? []
        const lengths = shadow.replace(COLOUR, '').match(/-?[\d.]+px/g)?.map(Number.parseFloat) ?? []
        // x, y, blur, spread: a ring is a shadow without blur that spreads
        if (colour && lengths[2] === 0 && (lengths[3] ?? 0) > 0)
          drawn.push({ colour: rgba(colour), behind: /\binset\b/.test(shadow) ? inside : outside })
      }
    }
    const ratios = drawn.filter(({ colour }) => colour[3]! > 0.01).map(({ colour, behind }) => ratio(over(colour, [...behind, 1]), behind))
    const indicatorRatio = highlighted || ratios.length === 0 ? undefined : Math.max(...ratios)

    // the sticky header can hide what the browser scrolled just under it, and a map clips a marker that is
    // outside its view: sample the middle and four points of the part of the element that is in the window
    const box = node.getBoundingClientRect()
    const left = Math.max(box.left, 0)
    const top = Math.max(box.top, 0)
    const width = Math.min(box.right, window.innerWidth) - left
    const height = Math.min(box.bottom, window.innerHeight) - top
    const points = [[0.5, 0.5], [0.25, 0.25], [0.75, 0.25], [0.25, 0.75], [0.75, 0.75]]
      .map(([x, y]) => [left + width * x!, top + height * y!] as const)
    const hits = points.map(([x, y]) => {
      const above = document.elementFromPoint(x, y)
      return above != null && (above === node || node.contains(above) || above.contains(node))
    })
    // a box with no area in the window is off screen altogether
    const obscured = box.width > 0 && box.height > 0 && (width <= 0 || height <= 0 || !hits.some(Boolean))
    const cover = document.elementFromPoint(points[0]![0], points[0]![1])
    const map = node.closest('.leaflet-container')?.getBoundingClientRect()
    const where = obscured
      ? ` at ${Math.round(box.left)},${Math.round(box.top)} of a ${window.innerWidth}x${window.innerHeight} window${map ? `, in a map at ${Math.round(map.left)},${Math.round(map.top)} to ${Math.round(map.right)},${Math.round(map.bottom)}` : ''}, under ${cover?.tagName.toLowerCase()}.${cover?.className?.toString().slice(0, 30)}`
      : ''

    const path: string[] = []
    for (let current: Element | null = node; current && current !== document.body; current = current.parentElement)
      path.push(`${current.tagName}:${[...current.parentElement?.children ?? []].indexOf(current)}`)
    return { none: false, name: name + where, indicator, indicatorRatio, obscured, key: path.join('/') }
  }, PROBE)
}

/**
 * Walk the page by keyboard, Tab by Tab, from its top to where the order comes round, and check what
 * each stop shows: a focus indicator, content that is not hidden, readable colours. A page where the
 * focus drops into nowhere before it has come round is a trap for the keyboard.
 */
export async function scanKeyboard(page: Page, backend: Backend, where: Where, options: { limit?: number, keepFocus?: boolean } = {}): Promise<ScanResult> {
  await settle(page, backend)
  const limit = options.limit ?? 120
  const found: Found = {}
  // from the top of the page, as a visitor who has just arrived; an open menu or dialog already holds the
  // focus, and the walk starts there, as blurring it would close it or send the focus into the page behind
  if (!options.keepFocus) {
    await page.evaluate(() => {
      (document.activeElement as HTMLElement | null)?.blur()
      window.scrollTo(0, 0)
    })
  }
  const seen = new Set<string>()
  let guards = 0
  let engine = ''
  if (options.keepFocus) {
    await transitionsDone(page)
    const start = await describeFocus(page)
    if (!start.none && !start.guard) {
      seen.add(start.key)
      // whether it shows a ring is not asked of it: the state was reached by pointer, and a pointer does not
      // make the focus it sets visible, as a key would
      if (start.obscured)
        add(found, 'focus-obscured', 'serious', start.name)
      engine = (await contrastOfProbe(page, found, `focus: ${start.name} `)) || engine
    }
  }
  for (let step = 0; step < limit; step++) {
    await page.keyboard.press('Tab')
    // the ring fades in: what is measured is what it ends as
    await transitionsDone(page)
    let focused = await describeFocus(page)
    if (focused.obscured) {
      // a map moving its markers, a menu opening under the focus: only what stays hidden is hidden
      await page.waitForTimeout(500)
      await transitionsDone(page)
      focused = await describeFocus(page)
    }
    if (focused.guard) {
      // a guard hands the focus on at once; one that keeps it through three Tabs has nothing after it
      if (++guards > 3)
        break
      continue
    }
    guards = 0
    if (focused.none) {
      // the end of the order, or the browser's own chrome taking the focus
      if (seen.size === 0)
        add(found, 'focus-lost', 'serious', 'the first Tab leaves the page')
      break
    }
    if (seen.has(focused.key))
      break // round again: a menu or a dialog that keeps the focus in itself, as it should
    seen.add(focused.key)
    if (!focused.indicator)
      add(found, 'focus-not-visible', 'serious', focused.name)
    else if (focused.indicatorRatio !== undefined && focused.indicatorRatio < 3)
      add(found, 'focus-indicator-contrast', 'serious', `${focused.name} ${focused.indicatorRatio.toFixed(1)}:1`)
    if (focused.obscured)
      add(found, 'focus-obscured', 'serious', focused.name)
    engine = (await contrastOfProbe(page, found, `focus: ${focused.name} `)) || engine
  }
  return record(where, engine, found)
}
