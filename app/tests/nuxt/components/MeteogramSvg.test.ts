import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it } from 'vitest'
import MeteogramSvg from '~/components/MeteogramSvg.vue'
import { demoForecast } from '~/utils/meteogram-demo'

// ten days of hourly stamps from a fixed hour; Berlin, with the coordinates the day bands need
const START = Date.UTC(2026, 9, 21, 0)
const values = demoForecast(START, 240)
const props = { values, stationName: 'Berlin', stationCoords: { latitude: 52.47, longitude: 13.4 } }

// happy-dom measures nothing: the component draws at its fallback width, 800 px, whose plot is 738 px wide from x = 52
const PLOT_LEFT = 52
const PLOT_WIDTH = 738

let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
async function show(extra: Record<string, unknown> = {}) {
  wrapper = await mountSuspended(MeteogramSvg, { props: { ...props, ...extra }, attachTo: document.body })
  return wrapper
}
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
})

const figure = () => document.body.querySelector<HTMLElement>('[role="figure"]')!
const svg = () => document.body.querySelector<SVGSVGElement>('svg.mg-svg')!
const tooltip = () => document.body.querySelector<HTMLElement>('[data-testid="mg-tooltip"]')
const live = () => document.body.querySelector('[aria-live="polite"]')!.textContent!.trim()
const button = (label: string) => document.body.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`)!

/** A pointer move over the plot at `fraction` of its width, as the browser sends it */
function pointerMove(fraction: number, y = 200) {
  const event = new MouseEvent('pointermove', { bubbles: true, clientX: PLOT_LEFT + PLOT_WIDTH * fraction, clientY: y })
  svg().dispatchEvent(event)
}
function key(target: Element | Document, k: string, init: KeyboardEventInit = {}) {
  return target.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...init }))
}
const settle = () => new Promise(resolve => setTimeout(resolve, 0))

describe('meteogramSvg drawing', () => {
  it('draws every panel with its series, and no canvas and no Plotly', async () => {
    await show()
    expect(document.body.querySelectorAll('canvas').length).toBe(0)
    expect(document.body.querySelector('.js-plotly-plot')).toBeNull()
    for (const cls of ['mg-s-temp', 'mg-s-wind', 'mg-s-pressure', 'mg-s-cloud', 'mg-s-dew', 'mg-s-max', 'mg-s-min']) {
      const path = document.body.querySelector(`path.${cls}`)
      expect(path, cls).not.toBeNull()
      expect(path!.getAttribute('d')).toMatch(/^M/)
    }
    expect(document.body.querySelectorAll('rect.mg-bar').length).toBeGreaterThan(0)
  })

  it('draws the wind barbs in the SVG of the chart, in the wind panel\'s coordinates', async () => {
    await show()
    const barbs = [...document.body.querySelectorAll('g.mg-barb')]
    expect(barbs.length).toBeGreaterThan(10)
    // each is placed by a translate in the same group as the line it sits on
    expect(barbs.every(b => b.getAttribute('transform')!.startsWith('translate('))).toBe(true)
    expect(barbs[0]!.closest('g[clip-path]')).not.toBeNull()
    expect(barbs.some(b => b.querySelector('path')?.getAttribute('d')?.startsWith('M0,0L'))).toBe(true)
  })

  it('draws day bands from sunrise to sunset and the weather symbols along the top', async () => {
    await show()
    const bands = document.body.querySelectorAll('rect.mg-day')
    // ten days, give or take the edges
    expect(bands.length).toBeGreaterThanOrEqual(10)
    expect(Number(bands[1]!.getAttribute('width'))).toBeGreaterThan(20)
    expect(document.body.querySelector('.mg-axis-top')!.textContent).toMatch(/[☀☁⛅🌧]/u)
  })

  it('leaves out a panel that is switched off, and keeps one on', async () => {
    await show()
    expect(document.body.querySelector('path.mg-s-pressure')).not.toBeNull()
    button('Pressure').click()
    await settle()
    expect(document.body.querySelector('path.mg-s-pressure')).toBeNull()
    expect(button('Pressure').getAttribute('aria-pressed')).toBe('false')
  })

  it('says it has no data without values', async () => {
    await show({ values: [] })
    expect(document.body.querySelector('svg.mg-svg')).toBeNull()
    expect(document.body.textContent).toContain('No data available')
  })
})

describe('meteogramSvg keyboard', () => {
  it('is one tab stop, a figure named and described, with its keys listed', async () => {
    await show()
    expect(figure().tabIndex).toBe(0)
    expect(figure().getAttribute('aria-label')).toBe('Forecast chart for Berlin')
    const described = figure().getAttribute('aria-describedby')!.split(' ')
    expect(described.length).toBe(2)
    for (const id of described)
      expect(document.getElementById(id)!.textContent!.trim().length).toBeGreaterThan(10)
    expect(figure().getAttribute('aria-keyshortcuts')).toContain('ArrowRight')
    // the picture is hidden from assistive technology: the readout and the table carry the values
    expect(svg().getAttribute('aria-hidden')).toBe('true')
  })

  it('steps the crosshair with the arrow keys and says what it is at', async () => {
    await show()
    figure().focus()
    key(figure(), 'ArrowRight')
    await settle()
    const first = tooltip()!.querySelector('.font-semibold')!.textContent!.trim()
    expect(first).toMatch(/\d\d:\d\d$/)
    expect(live()).toContain(first)
    expect(live()).toMatch(/Temperature|Mean Temp/)

    key(figure(), 'ArrowRight')
    await settle()
    const second = tooltip()!.querySelector('.font-semibold')!.textContent!.trim()
    expect(second).not.toBe(first)
    // one hour on
    expect(Number.parseInt(second.slice(-5, -3)) % 24).toBe((Number.parseInt(first.slice(-5, -3)) + 1) % 24)

    key(figure(), 'ArrowLeft')
    await settle()
    expect(tooltip()!.querySelector('.font-semibold')!.textContent!.trim()).toBe(first)
  })

  it('jumps with Shift, the page keys, Home and End, and follows the crosshair out of a zoomed window', async () => {
    await show()
    const vm = wrapper!.vm as any
    figure().focus()
    key(figure(), 'End')
    await settle()
    expect(vm.activeIdx).toBe(239)
    key(figure(), 'Home')
    await settle()
    expect(vm.activeIdx).toBe(0)
    key(figure(), 'PageDown')
    await settle()
    expect(vm.activeIdx).toBe(24)

    // zoomed to a window of the first hours, a step beyond its end moves the window
    button('Zoom in').click()
    await new Promise(resolve => setTimeout(resolve, 300))
    const [from] = vm.target
    key(figure(), 'Home')
    key(figure(), 'End')
    await settle()
    expect(vm.target[1]).toBe(START + 239 * 3_600_000)
    expect(vm.target[0]).toBeGreaterThan(from)
  })

  it('zooms with + and - and resets with 0 and the button', async () => {
    await show()
    const vm = wrapper!.vm as any
    const full = vm.target[1] - vm.target[0]
    figure().focus()
    key(figure(), '+')
    await settle()
    expect(vm.target[1] - vm.target[0]).toBe(full / 2)
    key(figure(), '-')
    await settle()
    expect(vm.target[1] - vm.target[0]).toBe(full)
    key(figure(), '+')
    key(figure(), '0')
    await settle()
    expect(vm.target[1] - vm.target[0]).toBe(full)
    key(figure(), '+')
    button('Reset zoom').click()
    await settle()
    expect(vm.target[1] - vm.target[0]).toBe(full)
  })

  it('has the zoom as buttons with names, and the way back disabled until it is zoomed', async () => {
    await show()
    expect(button('Zoom in').disabled).toBe(false)
    expect(button('Zoom out').disabled).toBe(true)
    button('Zoom in').click()
    await settle()
    expect(button('Zoom out').disabled).toBe(false)
  })
})

describe('meteogramSvg readout (WCAG 2.2 1.4.13)', () => {
  it('shows on hover, an ordinary element in the page with text a reader can select', async () => {
    await show()
    expect(tooltip()).toBeNull()
    pointerMove(0.5)
    await settle()
    const tip = tooltip()!
    expect(tip).not.toBeNull()
    // not a canvas or SVG text: a div with a definition list of the values
    expect(tip.tagName).toBe('DIV')
    expect(tip.querySelectorAll('dt').length).toBeGreaterThan(5)
    expect(tip.textContent).toMatch(/\d\d:\d\d/)
    expect(tip.closest('svg')).toBeNull()
  })

  it('is hoverable: it stays while the pointer is on the chart frame, whichever part, and goes when the pointer leaves it', async () => {
    await show()
    pointerMove(0.5)
    await settle()
    // the pointer leaves the plot for the readout: only the frame, which holds both, takes it away
    svg().dispatchEvent(new MouseEvent('pointerleave', { bubbles: false }))
    tooltip()!.dispatchEvent(new MouseEvent('pointermove', { bubbles: true }))
    await settle()
    expect(tooltip()).not.toBeNull()
    expect(tooltip()!.parentElement).toBe(document.body.querySelector('.mg-frame'))

    document.body.querySelector('.mg-frame')!.dispatchEvent(new MouseEvent('pointerleave', { bubbles: false }))
    await settle()
    expect(tooltip()).toBeNull()
  })

  it('is persistent: it does not go by itself while the pointer rests', async () => {
    await show()
    pointerMove(0.3)
    await new Promise(resolve => setTimeout(resolve, 400))
    expect(tooltip()).not.toBeNull()
  })

  it('is dismissed by Escape with the pointer where it is, until the pointer moves; Escape is not consumed', async () => {
    await show()
    pointerMove(0.5)
    await settle()
    expect(tooltip()).not.toBeNull()
    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    document.dispatchEvent(escape)
    await settle()
    expect(tooltip()).toBeNull()
    // so that a dialog around the chart still closes on it
    expect(escape.defaultPrevented).toBe(false)

    // a pointer that rests (the same position again) does not bring it back
    pointerMove(0.5)
    await settle()
    expect(tooltip()).toBeNull()
    // one that moves on does
    pointerMove(0.6)
    await settle()
    expect(tooltip()).not.toBeNull()
  })

  it('is dismissed by Escape with the keyboard focus on the chart, and by its own button', async () => {
    await show()
    figure().focus()
    key(figure(), 'ArrowRight')
    await settle()
    expect(tooltip()).not.toBeNull()
    key(figure(), 'Escape')
    await settle()
    expect(tooltip()).toBeNull()
    // the next step shows it again
    key(figure(), 'ArrowRight')
    await settle()
    expect(tooltip()).not.toBeNull()

    const close = tooltip()!.querySelector<HTMLButtonElement>('button')!
    expect(close.getAttribute('aria-label')).toBe('Close')
    close.click()
    await settle()
    expect(tooltip()).toBeNull()
  })

  it('names the weather of the hour in words, with the symbol hidden from assistive technology', async () => {
    await show()
    figure().focus()
    key(figure(), 'ArrowRight')
    await settle()
    const tip = tooltip()!
    const symbol = tip.querySelector('[aria-hidden="true"]')
    expect(symbol).not.toBeNull()
    expect(tip.textContent).toMatch(/Sunny|Partly cloudy|Cloudy|Rain/)
    expect(live()).toMatch(/Sunny|Partly cloudy|Cloudy|Rain/)
  })

  it('keeps a touch readout when the finger lifts, and closes it by a tap outside', async () => {
    await show()
    const down = new MouseEvent('pointerdown', { bubbles: true, clientX: PLOT_LEFT + PLOT_WIDTH * 0.5, clientY: 200 })
    Object.defineProperty(down, 'pointerType', { value: 'touch' })
    svg().dispatchEvent(down)
    await settle()
    expect(tooltip()).not.toBeNull()
    const leave = new MouseEvent('pointerleave', { bubbles: false })
    Object.defineProperty(leave, 'pointerType', { value: 'touch' })
    document.body.querySelector('.mg-frame')!.dispatchEvent(leave)
    await settle()
    expect(tooltip()).not.toBeNull()

    const outside = new MouseEvent('pointerdown', { bubbles: true })
    Object.defineProperty(outside, 'pointerType', { value: 'touch' })
    document.body.dispatchEvent(outside)
    await settle()
    expect(tooltip()).toBeNull()
  })
})

describe('meteogramSvg text alternative', () => {
  it('has the values as a table with the weather in words, opened by "Show as table"', async () => {
    await show()
    expect(document.body.querySelector('table')).toBeNull()
    const trigger = [...document.body.querySelectorAll('button')].find(b => b.textContent?.trim() === 'Show as table')!
    trigger.click()
    await settle()
    await new Promise(resolve => setTimeout(resolve, 50))
    const table = document.body.querySelector('table')!
    expect(table).not.toBeNull()
    const headers = [...table.querySelectorAll('thead th')].map(th => th.textContent!.trim())
    expect(headers[0]).toBe('Time (Europe/Berlin)')
    expect(headers).toContain('Weather')
    expect(table.querySelectorAll('tbody tr').length).toBe(240)
    expect(table.querySelector('tbody tr')!.textContent).toMatch(/Sunny|Partly cloudy|Cloudy|Rain/)
  })
})
