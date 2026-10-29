import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { UApp } from '#components'
import AppSearch from '~/components/AppSearch.vue'

// The command palette's workaround for Nuxt UI's listbox markup (GH-3518) watches the palette while it is open. It must
// watch the palette that is open, once, however quickly it is closed and opened, and nothing once it is closed.
interface Watch { target: Element | null, active: boolean }
let watches: Watch[] = []

beforeEach(() => {
  watches = []
  vi.stubGlobal('MutationObserver', class {
    private entry: Watch = { target: null, active: false }
    constructor(_callback: () => void) {
      watches.push(this.entry)
    }

    observe(target: Element) {
      this.entry.target = target
      this.entry.active = true
    }

    disconnect() {
      this.entry.active = false
    }

    takeRecords() {
      return []
    }
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

async function palette() {
  const wrapper = await mountSuspended(defineComponent({
    render: () => h(UApp, null, { default: () => h(AppSearch) }),
  }), { attachTo: document.body })
  return { wrapper, open: useState<boolean>('app-search-open') }
}

// the watches of this component's: on a palette's root (Reka and Vue make observers of their own)
const active = () => watches.filter(entry => entry.active && entry.target?.matches('[data-slot="root"]'))

describe('the palette\'s watch', () => {
  it('watches the palette, once, while it is open, and nothing after it is closed', async () => {
    const { wrapper, open } = await palette()
    open.value = true
    await vi.waitFor(() => expect(active()).toHaveLength(1))
    expect(document.querySelector('[role="dialog"]')?.contains(active()[0]!.target)).toBe(true)

    open.value = false
    await vi.waitFor(() => expect(active()).toHaveLength(0))
    wrapper.unmount()
  })

  it('has one watch, on the open palette, after a close and an open in quick succession', async () => {
    const { wrapper, open } = await palette()
    // opened, drawn, closed and opened again before the first opening's frame has passed: the palette is there again for
    // what the first was waiting for
    open.value = true
    await nextTick()
    await nextTick()
    open.value = false
    await nextTick()
    open.value = true
    await vi.waitFor(() => expect(active()).toHaveLength(1))
    // and it stays one: nothing waiting from the first opening attaches another
    await new Promise(resolve => setTimeout(resolve, 300))

    expect(active()).toHaveLength(1)
    expect(document.querySelector('[role="dialog"]')?.contains(active()[0]!.target)).toBe(true)
    open.value = false
    await vi.waitFor(() => expect(active()).toHaveLength(0))
    wrapper.unmount()
  })

  it('has none for a palette that was closed before it was drawn', async () => {
    const { wrapper, open } = await palette()
    open.value = true
    open.value = false
    await new Promise(resolve => setTimeout(resolve, 200))

    expect(active()).toHaveLength(0)
    wrapper.unmount()
  })

  it('puts the list right in the palette, not in the first dialog of the page, where another is open before it', async () => {
    // the drawer or the rail's popover, open behind the palette: a dialog that comes first in the page, with a root of its own
    const other = document.createElement('div')
    other.setAttribute('role', 'dialog')
    other.innerHTML = '<div data-slot="root"><div data-slot="content" role="listbox"><div data-slot="viewport"></div></div></div>'
    document.body.prepend(other)
    const { wrapper, open } = await palette()
    open.value = true
    await vi.waitFor(() => expect(document.querySelectorAll('[role="dialog"]').length).toBeGreaterThanOrEqual(2))

    // the palette's list is the one given the role of a listbox, with a name; the other dialog is left as it was
    await vi.waitFor(() => {
      const list = document.querySelector('[role="dialog"]:not([data-other]) [data-slot="root"] > [data-slot="input"]')
        ?.closest('[data-slot="root"]')
        ?.querySelector(':scope > [data-slot="content"] > [data-slot="viewport"]')
      expect(list?.getAttribute('role')).toBe('listbox')
      expect(list?.getAttribute('aria-label')).toBeTruthy()
    })
    expect(other.querySelector('[data-slot="content"]')?.getAttribute('role')).toBe('listbox')
    expect(other.querySelector('[data-slot="viewport"]')?.getAttribute('role')).toBeNull()

    open.value = false
    wrapper.unmount()
    other.remove()
  })
})
