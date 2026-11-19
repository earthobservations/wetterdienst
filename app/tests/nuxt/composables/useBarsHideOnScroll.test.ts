import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { BARS_ATTRIBUTE, overlayIsOpen, useBarsHideOnScroll } from '~/composables/useBarsHideOnScroll'
import { PHONE_QUERY } from '~/composables/usePhone'

// The bars of the phone that hide on scroll (GH-4226): the page is scrolled by a test (the offset, the length of the page and the
// window's height are served), and `<html data-bars>` says what the composable decided. The direction logic itself is
// tests/unit/bar-scroll.test.ts; what is held here is what the composable does with it: where it is on, and what stops it.
const Harness = defineComponent({
  setup() {
    useBarsHideOnScroll()
    return () => h('div')
  },
})

let offset = 0
const matchMedia = window.matchMedia
const hidden = () => document.documentElement.getAttribute(BARS_ATTRIBUTE) === 'hidden'

function serveWindow(queries: string[]) {
  window.matchMedia = ((query: string) => ({
    matches: queries.includes(query),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
  })) as unknown as typeof window.matchMedia
}

async function scrollTo(y: number) {
  offset = y
  window.dispatchEvent(new Event('scroll'))
  await nextTick()
}

/** Mounts the harness on a window that answers `queries`; the reader has made their first input unless `untouched` */
async function mountOn(queries: string[], route?: string, { untouched = false } = {}) {
  serveWindow(queries)
  const wrapper = await mountSuspended(Harness, { route })
  if (!untouched)
    window.dispatchEvent(new Event('wheel'))
  return wrapper
}

describe('the bars that hide on scroll', () => {
  beforeEach(() => {
    offset = 0
    vi.spyOn(window, 'scrollY', 'get').mockImplementation(() => offset)
    vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(800)
    vi.spyOn(document.documentElement, 'scrollHeight', 'get').mockReturnValue(5000)
  })
  afterEach(() => {
    vi.restoreAllMocks()
    window.matchMedia = matchMedia
    document.documentElement.removeAttribute(BARS_ATTRIBUTE)
    document.body.innerHTML = ''
  })

  it('hide on a phone when the page is scrolled down, and come back when it is scrolled up', async () => {
    const wrapper = await mountOn([PHONE_QUERY])
    await scrollTo(400)
    expect(hidden()).toBe(true)
    await scrollTo(370)
    expect(hidden()).toBe(false)
    await scrollTo(900)
    expect(hidden()).toBe(true)
    await scrollTo(0)
    expect(hidden()).toBe(false)
    wrapper.unmount()
  })

  it('hide only for the reader\'s own scroll: a page that arrives scrolled, or is moved by a script, keeps them', async () => {
    const wrapper = await mountOn([PHONE_QUERY], undefined, { untouched: true })
    await scrollTo(1200)
    expect(hidden()).toBe(false)
    await scrollTo(1500)
    expect(hidden()).toBe(false)
    // the first touch, key, press or turn of the wheel, and the scroll after it counts
    window.dispatchEvent(new Event('touchstart'))
    await scrollTo(1520)
    expect(hidden()).toBe(true)
    wrapper.unmount()
  })

  it('do not hide on a tablet or a desktop, where the window is not a phone', async () => {
    const wrapper = await mountOn([])
    await scrollTo(900)
    expect(document.documentElement.hasAttribute(BARS_ATTRIBUTE)).toBe(false)
    wrapper.unmount()
  })

  it('do not hide in a window as low as the bars stop being fixed', async () => {
    const wrapper = await mountOn([PHONE_QUERY, '(max-height: 30rem)'])
    await scrollTo(900)
    expect(document.documentElement.hasAttribute(BARS_ATTRIBUTE)).toBe(false)
    wrapper.unmount()
  })

  it('are shown again when the app goes, with the bars away', async () => {
    const wrapper = await mountOn([PHONE_QUERY])
    await scrollTo(900)
    expect(hidden()).toBe(true)
    wrapper.unmount()
    expect(document.documentElement.hasAttribute(BARS_ATTRIBUTE)).toBe(false)
  })

  it('stay while a dialog is open, and the offset that is put back when it closes moves nothing', async () => {
    const wrapper = await mountOn([PHONE_QUERY])
    const dialog = document.createElement('div')
    dialog.setAttribute('role', 'dialog')
    dialog.setAttribute('data-state', 'open')
    document.body.append(dialog)
    await scrollTo(900)
    expect(hidden()).toBe(false)
    // closed: the page's offset is put back at the same point and the bars are not touched by it
    dialog.remove()
    await scrollTo(900)
    expect(hidden()).toBe(false)
    await scrollTo(930)
    expect(hidden()).toBe(true)
    wrapper.unmount()
  })

  it('are told by what is open: a dialog that is open, a trigger that says so, not one that is shut', () => {
    expect(overlayIsOpen(document)).toBe(false)
    const shut = document.createElement('div')
    shut.setAttribute('role', 'dialog')
    shut.setAttribute('data-state', 'closed')
    document.body.append(shut)
    const trigger = document.createElement('button')
    trigger.setAttribute('aria-haspopup', 'dialog')
    trigger.setAttribute('aria-expanded', 'false')
    document.body.append(trigger)
    // an ⓘ or a collapsible says it is expanded and is no popup: it does not hold the bars
    const disclosure = document.createElement('button')
    disclosure.setAttribute('aria-expanded', 'true')
    document.body.append(disclosure)
    expect(overlayIsOpen(document)).toBe(false)
    trigger.setAttribute('aria-expanded', 'true')
    expect(overlayIsOpen(document)).toBe(true)
    trigger.remove()
    const combobox = document.createElement('button')
    combobox.setAttribute('role', 'combobox')
    combobox.setAttribute('aria-expanded', 'true')
    document.body.append(combobox)
    expect(overlayIsOpen(document)).toBe(true)
  })

  it('come back with a focus in either bar, and not with one anywhere else', async () => {
    const wrapper = await mountOn([PHONE_QUERY])
    const bar = document.createElement('nav')
    bar.className = 'app-tabbar'
    const link = document.createElement('a')
    link.href = '#'
    bar.append(link)
    const page = document.createElement('button')
    document.body.append(bar, page)

    await scrollTo(900)
    expect(hidden()).toBe(true)
    page.focus()
    expect(hidden()).toBe(true)
    link.focus()
    expect(hidden()).toBe(false)

    // and the count begins where the page is: a few pixels are no scroll
    await scrollTo(905)
    expect(hidden()).toBe(false)
    await scrollTo(930)
    expect(hidden()).toBe(true)
    wrapper.unmount()
  })

  it('stay on a page that says so', async () => {
    const router = useRouter()
    router.addRoute({ path: '/keeps-bars', component: { render: () => h('div') }, meta: { barsHide: false } })
    const wrapper = await mountOn([PHONE_QUERY], '/keeps-bars')
    await scrollTo(900)
    expect(document.documentElement.hasAttribute(BARS_ATTRIBUTE)).toBe(false)
    wrapper.unmount()
  })
})
