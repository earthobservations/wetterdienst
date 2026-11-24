import type { Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import type { Mock } from 'vitest'
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { verificationFile, verificationName, verificationWarning } from '../../server/utils/googleSiteVerification'

// Google Search Console's HTML-file verification (GH-4108): the name is a setting of the instance, never a file of
// `public/`, and the answer is the one line Google's own file holds.

const NAME = 'google54ae9a07758f51bd'
const LINE = `google-site-verification: ${NAME}.html`

describe('the name an operator sets', () => {
  it.each([NAME, `${NAME}.html`, ` ${NAME} `])('reads %j as the name', (value) => {
    expect(verificationName(value)).toBe(NAME)
    expect(verificationWarning(value)).toBeUndefined()
  })

  it.each([undefined, null, '', '  '])('reads %j as not set, without a warning', (value) => {
    expect(verificationName(value)).toBe('')
    expect(verificationWarning(value)).toBeUndefined()
  })

  it.each([
    'google',
    'google.html',
    'googleXYZ',
    'google54AE9A07758F51BD',
    '54ae9a07758f51bd',
    'google54ae9a07758f51bd.txt',
    'google54ae9a07758f51bd.html.html',
    '../google54ae9a07758f51bd',
    '/google54ae9a07758f51bd.html',
    'google54ae9a07758f51bd/../../x',
    'google-site-verification: google54ae9a07758f51bd.html',
  ])('ignores %j, and says so', (value) => {
    expect(verificationName(value)).toBe('')
    expect(verificationWarning(value)).toContain('NUXT_GOOGLE_SITE_VERIFICATION is ignored')
  })

  it('does not repeat the value in the warning', () => {
    expect(verificationWarning('a-secret-of-the-operator')).not.toContain('secret')
  })

  it('answers the one line Google\'s file holds, without a line break after it', () => {
    expect(verificationFile(NAME)).toEqual({ path: `/${NAME}.html`, body: LINE })
  })
})

// the middleware as Nitro runs it, in front of a handler that stands for the shell
const nuxtRequire = createRequire(createRequire(import.meta.url).resolve('nuxt/package.json'))
const h3 = nuxtRequire('h3') as typeof import('h3')

const config: { googleSiteVerification: unknown } = { googleSiteVerification: '' }

describe('the middleware', () => {
  let server: Server
  let app: string
  let shell: Mock<(event: import('h3').H3Event) => string>

  // The globals Nitro provides are stubbed for each test and removed after it, so that no other describe of the
  // file (the warning's stubs `useRuntimeConfig` too) can take them from this one, whatever order the tests run in.
  beforeEach(async () => {
    for (const [name, value] of Object.entries({
      defineEventHandler: h3.defineEventHandler,
      setResponseHeader: h3.setResponseHeader,
      useRuntimeConfig: () => config,
    }))
      vi.stubGlobal(name, value)
    const { default: middleware } = await import('../../server/middleware/google-site-verification')
    shell = vi.fn(() => '<html>the shell</html>')
    const router = h3.createApp()
    router.use(middleware)
    router.use(h3.defineEventHandler(event => shell(event)))
    server = createServer(h3.toNodeListener(router))
    app = await new Promise<string>(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${(server.address() as AddressInfo).port}`)))
  })

  afterEach(async () => {
    config.googleSiteVerification = ''
    vi.unstubAllGlobals()
    await new Promise(resolve => server.close(resolve))
  })

  it('answers /<name>.html with exactly the line Google expects, as HTML', async () => {
    config.googleSiteVerification = NAME
    const response = await fetch(`${app}/${NAME}.html`)

    expect(response.status).toBe(200)
    expect(response.headers.get('content-type')).toBe('text/html; charset=utf-8')
    expect(await response.text()).toBe(LINE)
    expect(shell).not.toHaveBeenCalled()
  })

  it('answers a file and not the shell: cached for an hour, with none of the headers the shell\'s hooks add', async () => {
    config.googleSiteVerification = NAME
    const response = await fetch(`${app}/${NAME}.html`)

    expect(response.headers.get('cache-control')).toBe('public, max-age=3600')
    // seo-head's `render:html` hook adds `Vary: Cookie, Accept-Language` and, for some paths, `X-Robots-Tag`
    expect(response.headers.get('vary')).toBeNull()
    expect(response.headers.get('x-robots-tag')).toBeNull()
    expect(await response.text()).toBe(LINE)
  })

  it('takes the name with the .html Google shows, and a query string', async () => {
    config.googleSiteVerification = `${NAME}.html`
    const response = await fetch(`${app}/${NAME}.html?x=1`)

    expect(response.status).toBe(200)
    expect(await response.text()).toBe(LINE)
  })

  it('answers HEAD with the headers and no body', async () => {
    config.googleSiteVerification = NAME
    const response = await fetch(`${app}/${NAME}.html`, { method: 'HEAD' })

    expect(response.status).toBe(200)
    expect(response.headers.get('content-type')).toBe('text/html; charset=utf-8')
    expect(await response.text()).toBe('')
    expect(shell).not.toHaveBeenCalled()
  })

  it('changes nothing while the setting is empty: the path is the shell\'s', async () => {
    const response = await fetch(`${app}/${NAME}.html`)

    expect(await response.text()).toBe('<html>the shell</html>')
    expect(shell).toHaveBeenCalledOnce()
  })

  it('does not answer for another google<hex>.html: that is the shell\'s, as before', async () => {
    config.googleSiteVerification = NAME
    const response = await fetch(`${app}/google0000000000000000.html`)

    expect(await response.text()).toBe('<html>the shell</html>')
    expect(shell).toHaveBeenCalledOnce()
  })

  it.each([`/${NAME}`, `/${NAME}.htm`, `/sub/${NAME}.html`, `/${NAME}.html/`, `/${NAME.toUpperCase()}.html`, '/'])('does not answer for %s', async (path) => {
    config.googleSiteVerification = NAME
    const response = await fetch(`${app}${path}`)

    expect(await response.text()).toBe('<html>the shell</html>')
  })

  it.each(['not a name', 'google', '../x', 'GOOGLEABC'])('ignores the value %j, and answers nothing for it', async (value) => {
    config.googleSiteVerification = value
    for (const path of ['/google.html', '/googleabc.html', `/${value}.html`, `/${NAME}.html`]) {
      const response = await fetch(`${app}${path}`)
      expect(await response.text(), path).toBe('<html>the shell</html>')
    }
  })

  it('answers no other method than GET and HEAD', async () => {
    config.googleSiteVerification = NAME
    const response = await fetch(`${app}/${NAME}.html`, { method: 'POST' })

    expect(await response.text()).toBe('<html>the shell</html>')
  })
})

describe('the warning at start', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  async function start(value: unknown) {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.stubGlobal('defineNitroPlugin', (plugin: () => void) => plugin())
    vi.stubGlobal('useRuntimeConfig', () => ({ googleSiteVerification: value }))
    await import('../../server/plugins/google-site-verification')
    const messages = warn.mock.calls.map(call => String(call[0]))
    warn.mockRestore()
    return messages
  }

  it('warns once for a value that is no name, and does not throw', async () => {
    const messages = await start('hello')
    expect(messages).toHaveLength(1)
    expect(messages[0]).toContain('NUXT_GOOGLE_SITE_VERIFICATION is ignored')
  })

  it.each(['', NAME, `${NAME}.html`])('is silent for %j', async (value) => {
    expect(await start(value)).toEqual([])
  })
})
