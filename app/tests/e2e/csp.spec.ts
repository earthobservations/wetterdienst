import type { AddressInfo } from 'node:net'
import { createServer } from 'node:http'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The Content Security Policy keeps a script the page did not write from running (GH-3112). The page's own inline
// scripts (the import map, the colour mode, the app's data) carry a nonce, the header names that nonce, and
// `'unsafe-inline'` is not in `script-src`: an inline script that has no nonce is refused, and so is an event handler
// attribute (`script-src-attr 'none'`).

/** The sources of one directive of a policy */
function directive(policy: string, name: string): string[] {
  const found = policy.split(';').map(part => part.trim().split(/\s+/)).find(([first]) => first === name)
  return found ? found.slice(1) : []
}

test.describe('the policy the page is sent with', () => {
  test('names the nonce of the page\'s scripts, and has no \'unsafe-inline\' for scripts', async ({ request }) => {
    const response = await request.get('/')
    const scriptSrc = directive(response.headers()['content-security-policy']!, 'script-src')
    const nonces = scriptSrc.filter(source => source.startsWith('\'nonce-'))

    expect(nonces).toHaveLength(1)
    expect(scriptSrc).not.toContain('\'unsafe-inline\'')
    expect(scriptSrc).not.toContain('\'unsafe-eval\'')
    expect(directive(response.headers()['content-security-policy']!, 'script-src-attr')).toEqual(['\'none\''])

    // every script of the page is the one the header names: a script without it would not run
    const nonce = nonces[0]!.slice('\'nonce-'.length, -1)
    const tags = (await response.text()).match(/<script\b[^>]*>/gi) ?? []
    expect(tags.length).toBeGreaterThan(0)
    for (const tag of tags)
      expect(tag).toContain(`nonce="${nonce}"`)
  })

  test('has a nonce of its own for every response', async ({ request }) => {
    const nonceOf = async () => (await request.get('/')).headers()['content-security-policy']!.match(/'nonce-([^']+)'/)?.[1]
    const [first, second] = [await nonceOf(), await nonceOf()]

    expect(first).toBeTruthy()
    expect(second).toBeTruthy()
    expect(first).not.toBe(second)
  })
})

test.describe('who may frame a page', () => {
  test('any origin may frame the widget, in either spelling and with a query', async ({ request }) => {
    for (const path of ['/widget', '/widget/', '/widget?station=10381', '/widget/?station=10381&theme=dark']) {
      const headers = (await request.get(path)).headers()
      expect(directive(headers['content-security-policy']!, 'frame-ancestors'), path).toEqual(['*'])
      expect(headers['x-frame-options'], path).toBeUndefined()
    }
  })

  test('no other page may be framed by another origin, not even by a path that reads as the widget once decoded', async ({ request }) => {
    const paths = ['/', '/meteogram', '/explorer', '/docs', '/widgets', '/widgetx', '/Widget', '/%77idget', '/widge%74', '/%57idget', '/widget//', '/api/version']
    for (const path of paths) {
      const headers = (await request.get(path)).headers()
      expect(headers['x-frame-options'], path).toBe('SAMEORIGIN')
      if (headers['content-security-policy'])
        expect(directive(headers['content-security-policy'], 'frame-ancestors'), path).toEqual(['\'self\''])
    }
  })
})

test.describe('a page framed by another origin', () => {
  // Behind a proxy that rewrites the path before it forwards it, `/%77idget`, `//widget` and `/widget//` arrive at
  // the server as `/widget`, which it frames freely, while the browser keeps the address it was given. The test is
  // that proxy: the frame is answered with the widget's own response, at the address the page was framed at.
  const SPELLINGS = ['/%77idget', '//widget', '/widget//', '/WIDGET', '/Widget/', '/nonexistent']

  test('draws the widget, and nothing at an address that is not the widget\'s however the server answered it', async ({ page, baseURL }) => {
    const origin = new URL(baseURL!).origin
    // a page of another origin (the address of this machine, not its name), which is a server of its own: a browser
    // does not let a page it takes for public frame one on this machine
    const embedder = createServer((_request, response) => {
      response.setHeader('content-type', 'text/html')
      response.end(['/widget?station=10381', ...SPELLINGS].map((path, index) => `<iframe id="f${index}" src="${origin}${path}" width="600" height="400"></iframe>`).join(''))
    })
    await new Promise<void>(resolve => embedder.listen(0, '127.0.0.1', resolve))
    try {
      await page.route(url => url.origin === origin && SPELLINGS.includes(url.pathname), async (route) => {
        await route.fulfill({ response: await route.fetch({ url: `${origin}/widget` }) })
      })
      await page.goto(`http://127.0.0.1:${(embedder.address() as AddressInfo).port}/`)

      const widget = page.frameLocator('#f0')
      await expect(widget.getByRole('img', { name: 'Wetterdienst' })).toBeVisible()
      for (const [index, path] of SPELLINGS.entries()) {
        const frame = page.frameLocator(`#f${index + 1}`)
        await expect(frame.locator('body'), path).toHaveText('', { useInnerText: true })
        await expect(frame.getByRole('img', { name: 'Wetterdienst' }), path).toHaveCount(0)
        await expect(frame.getByText(/not found|404|Seite nicht gefunden/i), path).toHaveCount(0)
      }
    }
    finally {
      await new Promise(resolve => embedder.close(resolve))
    }
  })
})

test.describe('the error page', () => {
  test('is the app\'s own for an unknown address, where the page is not framed, and breaks no part of the policy (GH-3453)', async ({ page }) => {
    // Nuxt's page for a 404 injects an inline script for its back button, which the policy refuses
    await page.addInitScript(() => {
      document.addEventListener('securitypolicyviolation', (event) => {
        const w = window as unknown as { __csp?: string[] }
        ;(w.__csp ??= []).push(`${event.violatedDirective}: ${event.sample}`)
      })
    })
    await page.goto('/nonexistent')

    await expect(page.getByText('404').first()).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Go to the home page' })).toHaveAttribute('href', '/')
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    expect(await page.evaluate(() => (window as unknown as { __csp?: string[] }).__csp ?? [])).toEqual([])
  })
})

test.describe('a page held to its policy', () => {
  test('runs its own scripts and does not run an inline script that is injected', async ({ page, baseURL }) => {
    const violations: string[] = []
    await page.addInitScript(() => {
      document.addEventListener('securitypolicyviolation', (event) => {
        const w = window as unknown as { __csp?: string[] }
        ;(w.__csp ??= []).push(`${event.violatedDirective}: ${event.sample}`)
      })
    })
    await mockBackend(page, baseURL!)
    await page.goto('/')
    // the app has started: its own inline scripts (and the module scripts) ran under the policy
    await expect(page.getByRole('link', { name: 'Explorer' }).first()).toBeVisible()
    violations.push(...await page.evaluate(() => (window as unknown as { __csp?: string[] }).__csp ?? []))
    expect(violations).toEqual([])

    // what an injection into the page would do: an inline script element, and one that is written as markup
    // (innerHTML runs no script, so the element is made and its text set), and an event handler attribute
    await page.evaluate(() => {
      const script = document.createElement('script')
      script.textContent = 'window.__injected_script = true'
      document.head.append(script)
      const holder = document.createElement('div')
      holder.innerHTML = '<img src="data:," onerror="window.__injected_handler = true">'
      document.body.append(holder)
    })
    await page.waitForFunction(() => ((window as unknown as { __csp?: string[] }).__csp?.length ?? 0) > 0)
    // the handler's image fails asynchronously: give the event a turn before looking at the result
    await page.waitForTimeout(500)

    const ran = await page.evaluate(() => {
      const w = window as unknown as Record<string, unknown>
      return { script: w.__injected_script === true, handler: w.__injected_handler === true }
    })
    expect(ran).toEqual({ script: false, handler: false })
    const refused = await page.evaluate(() => (window as unknown as { __csp?: string[] }).__csp ?? [])
    // each was refused by the policy, not merely failing: one violation for the element, one for the attribute
    expect(refused.filter(v => v.startsWith('script-src')).length).toBeGreaterThanOrEqual(2)
  })
})

test.describe('the station map', () => {
  test('draws its marker images, the selected one too, from the app: no request to Cloudflare or GitHub, no image the policy refuses (GH-3420)', async ({ page, baseURL }) => {
    const requested: string[] = []
    page.on('request', request => requested.push(request.url()))
    await page.addInitScript(() => {
      document.addEventListener('securitypolicyviolation', (event) => {
        const w = window as unknown as { __csp?: string[] }
        ;(w.__csp ??= []).push(`${event.violatedDirective}: ${event.blockedURI}`)
      })
    })
    await mockBackend(page, baseURL!)
    await page.goto('/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m,temperature_air_mean_2m&mode=station')
    await page.getByRole('button', { name: 'Choose on the map' }).click()

    const origin = new URL(baseURL!).origin
    const drawn = async (selector: string) => {
      const images = page.locator(selector)
      await expect(images.first()).toBeVisible()
      // each image decoded: it is drawn, not a broken one that the policy or the network refused
      await expect.poll(() => images.evaluateAll(list => list.every(image => (image as HTMLImageElement).complete && (image as HTMLImageElement).naturalWidth > 0))).toBe(true)
      const sources = await images.evaluateAll(list => list.map(image => (image as HTMLImageElement).currentSrc))
      for (const source of sources)
        expect(source.startsWith('data:') || source.startsWith(`${origin}/`), source).toBe(true)
    }

    await drawn('img.leaflet-marker-icon:not(.wd-marker-selected)')
    await drawn('img.leaflet-marker-shadow')
    // a marker is picked: a click on it is intercepted by an overlapping button, so the event is sent to it
    await page.locator('img.leaflet-marker-icon').first().dispatchEvent('click')
    await drawn('img.leaflet-marker-icon.wd-marker-selected')

    const external = requested.filter(url => /cdnjs\.cloudflare\.com|raw\.githubusercontent\.com|unpkg\.com/.test(url))
    expect(external).toEqual([])
    expect(await page.evaluate(() => (window as unknown as { __csp?: string[] }).__csp ?? [])).toEqual([])
  })
})
