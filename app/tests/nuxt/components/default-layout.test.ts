import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { UApp } from '#components'
import DefaultLayout from '~/layouts/default.vue'

// The shell of the pages (GH-3518): its row layout follows the script flag of the sidebar, not a Tailwind breakpoint. Tailwind's
// are in rem, which a browser set to a larger default font size makes wider than the pixels of the flag: between 1024 and
// 1279 px (a 20 px default) the rail was drawn and the page stood below it.
registerEndpoint('/api/version', () => ({ version: '0.178.0' }))

function screen(width: number) {
  vi.stubGlobal('matchMedia', (query: string) => {
    const min = /min-width:\s*(\d+)px/.exec(query)
    return {
      media: query,
      matches: min ? width >= Number(min[1]) : false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    }
  })
}

async function shell() {
  // inside UApp, which the tooltips and the drawer of the shell need, as in app.vue
  const wrapper = await mountSuspended(defineComponent({
    render: () => h(UApp, null, { default: () => h(DefaultLayout, null, { default: () => h('p', 'the page') }) }),
  }))
  return { wrapper, row: wrapper.find('.min-h-screen') }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('the shell', () => {
  it('is a row, with the sidebar beside the page, where the script says the window is large', async () => {
    screen(1100)
    const { wrapper, row } = await shell()

    expect(row.classes()).toContain('flex')
    expect(row.classes()).not.toContain('lg:flex')
    expect(wrapper.find('aside').exists()).toBe(true)
    wrapper.unmount()
  })

  it('is a column with a top bar, and no sidebar, below 1024 px', async () => {
    screen(800)
    const { wrapper, row } = await shell()

    expect(row.classes()).not.toContain('flex')
    expect(wrapper.find('aside').exists()).toBe(false)
    expect(wrapper.find('header').exists()).toBe(true)
    wrapper.unmount()
  })

  it('has a skip link to the page as its first element', async () => {
    screen(1440)
    const { wrapper, row } = await shell()

    expect(row.find('a').attributes('href')).toBe('#main')
    expect(wrapper.find('main#main').exists()).toBe(true)
    wrapper.unmount()
  })
})
