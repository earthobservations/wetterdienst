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
    const tags = (await response.text()).match(/<script\b[^>]*>/g) ?? []
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
