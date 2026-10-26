import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import ErrorPage from '~/error.vue'

// `app/error.vue` draws a 404 itself, in the app's language and without a script of its own: Nuxt's page for it
// injects an inline script for its back button, which the Content Security Policy (a nonce per response, no
// `'unsafe-inline'` for scripts) refuses, so the button never appeared (GH-3453). Every other error is Nuxt's own
// page, as before. Where the page is framed by another origin outside the widget it is empty. It once rendered a
// component that Nuxt does not register, which left every 404 a white page.
const framed = vi.hoisted(() => ({ blank: false }))
mockNuxtImport('useFrameBlank', () => () => ref(framed.blank))

const notFound = { statusCode: 404, statusMessage: 'Page not found', message: 'Page not found: /nonexistent', url: '/nonexistent', fatal: false, unhandled: false }
const serverError = { statusCode: 500, statusMessage: 'Internal server error', message: 'Something broke', url: '/', fatal: true, unhandled: true }

afterEach(() => {
  framed.blank = false
  window.history.replaceState(null, '')
})

describe('the error page', () => {
  it('draws a 404 in the app\'s language, with a link home that needs no script', async () => {
    const wrapper = await mountSuspended(ErrorPage, { props: { error: notFound as never } })

    expect(wrapper.text()).toContain('404')
    expect(wrapper.text()).toContain('Page not found')
    expect(wrapper.text()).toContain('There is no page at this address')
    const home = wrapper.find('a')
    expect(home.attributes('href')).toBe('/')
    expect(home.text()).toBe('Go to the home page')
    // it does not print the path it was asked for
    expect(wrapper.html()).not.toContain('nonexistent')
  })

  it('draws a 404 in German where the app is', async () => {
    const SetLocale = defineComponent({
      setup() {
        const { setLocale } = useI18n()
        return { setLocale }
      },
      render: () => h('div'),
    })
    const harness = await mountSuspended(SetLocale)
    await (harness.vm as any).setLocale('de')
    await nextTick()
    try {
      const wrapper = await mountSuspended(ErrorPage, { props: { error: notFound as never } })

      expect(wrapper.text()).toContain('Seite nicht gefunden')
      expect(wrapper.find('a').text()).toBe('Zur Startseite')
    }
    finally {
      await (harness.vm as any).setLocale('en')
    }
  })

  it('injects no script into the page: the Content Security Policy would refuse it', async () => {
    await mountSuspended(ErrorPage, { props: { error: notFound as never } })

    const inline = [...document.head.querySelectorAll('script')].filter(script => script.textContent?.includes('history'))
    expect(inline).toEqual([])
    expect(document.querySelector('[data-back-previous]')).toBeNull()
  })

  it('has no back button where there is no page of the app to go back to', async () => {
    const wrapper = await mountSuspended(ErrorPage, { props: { error: notFound as never } })

    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('has a back button where the router knows the page before, which goes back', async () => {
    window.history.replaceState({ back: '/about' }, '')
    const back = vi.spyOn(useRouter(), 'back').mockImplementation(() => {})
    const wrapper = await mountSuspended(ErrorPage, { props: { error: notFound as never } })

    const buttons = wrapper.findAll('button')
    expect(buttons).toHaveLength(1)
    expect(buttons[0]!.text()).toBe('Go back')
    await buttons[0]!.trigger('click')
    expect(back).toHaveBeenCalledOnce()
  })

  it('leaves every other error to Nuxt\'s own page', async () => {
    const wrapper = await mountSuspended(ErrorPage, { props: { error: serverError as never } })

    expect(wrapper.text()).toContain('500')
    expect(wrapper.text()).toContain('Internal server error')
    expect(wrapper.text()).not.toContain('There is no page at this address')
  })

  it('shows nothing, not even the path, where the page is framed by another origin outside the widget', async () => {
    framed.blank = true
    const wrapper = await mountSuspended(ErrorPage, { props: { error: notFound as never } })

    expect(wrapper.text()).toBe('')
    expect(wrapper.html()).not.toContain('nonexistent')
  })
})
