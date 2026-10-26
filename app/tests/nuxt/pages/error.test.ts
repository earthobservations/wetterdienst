import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import ErrorPage from '~/error.vue'

// `app/error.vue` is Nuxt's own error page, except where the page is framed by another origin outside the widget:
// then it is empty. It once rendered a component that Nuxt does not register, which left every 404 a white page.
const framed = vi.hoisted(() => ({ blank: false }))
mockNuxtImport('useFrameBlank', () => () => ref(framed.blank))

const notFound = { statusCode: 404, statusMessage: 'Page not found', message: 'Page not found: /nonexistent', url: '/nonexistent', fatal: false, unhandled: false }

describe('the error page', () => {
  it('shows what Nuxt shows for a 404, where the page is not framed', async () => {
    framed.blank = false
    const wrapper = await mountSuspended(ErrorPage, { props: { error: notFound as never } })

    expect(wrapper.text()).toContain('404')
    expect(wrapper.text()).toContain('Page not found')
  })

  it('shows nothing, not even the path, where the page is framed by another origin outside the widget', async () => {
    framed.blank = true
    const wrapper = await mountSuspended(ErrorPage, { props: { error: notFound as never } })

    expect(wrapper.text()).toBe('')
    expect(wrapper.html()).not.toContain('nonexistent')
  })
})
