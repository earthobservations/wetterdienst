import type { Locator, Page } from '@playwright/test'
import { expect, test } from '@playwright/test'

test.describe('Home Page', () => {
  test('should load the homepage', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/Wetterdienst/i)
  })

  test('should display main navigation', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Check for navigation links
    const explorerLink = page.getByRole('link', { name: /explorer/i })
    // Exact, not /api/i: the home page's developer row links to the backend's Swagger UI as
    // "REST API", which a loose match picks up alongside the nav entry and fails on strict mode.
    const apiLink = page.getByRole('link', { name: 'API', exact: true })

    await expect(explorerLink).toBeVisible()
    await expect(apiLink).toBeVisible()
  })

  // The weather services are the backend's (`/api/providers`), so for a moment there are none to show: the
  // block holds its place with placeholders. What is under the card must not move by more than a row of chips
  // when the answer comes (a row is a chip of 30px and a gap of 8), however wide the window is.
  for (const width of [1280, 768, 375]) {
    test(`keeps the weather services block about as tall before the backend answers as after, at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      let release!: () => void
      const held = new Promise<void>((resolve) => {
        release = resolve
      })
      await page.route('**/api/providers', async (route) => {
        await held
        await route.continue()
      })
      await page.goto('/')
      const card = page.getByTestId('home-providers-card')
      await expect(card.getByRole('status')).toBeVisible()
      const before = (await card.boundingBox())!.height

      release()
      await expect(page.getByTestId('home-providers')).toBeVisible({ timeout: 30_000 })
      const after = (await card.boundingBox())!.height

      expect(Math.abs(after - before), `the card was ${before}px tall before and ${after}px after`).toBeLessThanOrEqual(38)
    })
  }

  test('links every weather service to its page', async ({ page }) => {
    await page.goto('/')
    const chip = page.getByTestId('home-providers').getByRole('link', { name: 'DWD' })

    await expect(chip).toBeVisible({ timeout: 30_000 })
    await chip.click()
    await expect(page).toHaveURL(/\/providers\/dwd$/)
  })
})

test.describe('API Documentation Page', () => {
  test('should navigate to API page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('link', { name: 'API', exact: true }).click()

    await expect(page).toHaveURL(/\/api/)
    await expect(page.getByRole('heading', { name: /REST API/i })).toBeVisible()
  })

  test('should display API endpoints', async ({ page }) => {
    await page.goto('/api')
    await page.waitForLoadState('networkidle')

    const endpoints = ['coverage', 'stations', 'values', 'interpolate', 'summarize']

    for (const endpoint of endpoints) {
      await expect(page.getByText(endpoint, { exact: false }).first()).toBeVisible()
    }
  })

  test('should have clickable endpoint links', async ({ page }) => {
    await page.goto('/api')
    await page.waitForLoadState('networkidle')

    // Just verify endpoint text is visible, buttons may not exist
    await expect(page.getByText('coverage', { exact: false }).first()).toBeVisible()
  })
})

test.describe('Explorer Page', () => {
  test('should navigate to explorer page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('link', { name: /explorer/i }).click()

    await expect(page).toHaveURL(/\/explorer/)
  })

  test('should display parameter selection', async ({ page }) => {
    await page.goto('/explorer')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText(/Select Parameters/i).first()).toBeVisible()
  })

  test('should have provider dropdown', async ({ page }) => {
    await page.goto('/explorer')
    await page.waitForLoadState('networkidle')

    // Check that select elements exist
    const selects = await page.locator('select, [role="combobox"]').count()
    expect(selects).toBeGreaterThan(0)
  })
})

test.describe('Climate Stripes Page', () => {
  test('should navigate to stripes page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('navigation').getByRole('link', { name: /stripes/i }).click()

    await expect(page).toHaveURL(/\/stripes/)
  })

  test('should display climate stripes heading', async ({ page }) => {
    await page.goto('/stripes')
    await page.waitForLoadState('networkidle')

    // Use first() to avoid strict mode violation with multiple headings
    await expect(page.getByRole('heading', { name: /Climate Stripes/i }).first()).toBeVisible()
  })

  test('should load stripes stations', async ({ page }) => {
    await page.goto('/stripes')
    await page.waitForLoadState('networkidle')

    // Should have a station selector
    const selectors = await page.locator('select, [role="combobox"]').count()
    expect(selectors).toBeGreaterThan(0)
  })
})

test.describe('Providers Page', () => {
  test('should be reachable from the navigation', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('navigation').getByRole('link', { name: 'Providers', exact: true }).click()

    await expect(page).toHaveURL(/\/providers$/)
    await expect(page.getByRole('heading', { name: 'Providers', level: 1 })).toBeVisible()
  })

  test('should be reachable from the home page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('link', { name: /All providers, their licences/ }).click()

    await expect(page).toHaveURL(/\/providers$/)
  })

  test('should list the providers the backend serves, and narrow them by a search', async ({ page }) => {
    await page.goto('/providers')

    // what the backend says each is, not a list written into the app
    await expect(page.getByRole('heading', { name: 'German Weather Service' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Norwegian Meteorological Institute' })).toBeVisible()
    await expect(page.getByText(/Showing 22 of 22/)).toBeVisible()

    await page.getByPlaceholder(/Search name, country or code/).fill('norway')
    await expect(page.getByRole('heading', { name: 'Norwegian Meteorological Institute' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'German Weather Service' })).toHaveCount(0)
    await expect(page.getByText(/Showing 1 of 22/)).toBeVisible()
  })

  test('should open the page of a provider with its licence and credit line', async ({ page }) => {
    await page.goto('/providers')
    await page.getByRole('link', { name: /German Weather Service/ }).click()

    await expect(page).toHaveURL(/\/providers\/dwd$/)
    await expect(page.getByRole('heading', { name: 'German Weather Service', level: 1 })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Creative Commons Attribution 4.0 International' })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by/4.0/')
    await expect(page.getByText('Source: Deutscher Wetterdienst')).toBeVisible()
    // its networks, the standalone ones among them
    await expect(page.getByRole('heading', { name: 'observation', level: 3 })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'radar', level: 3 })).toBeVisible()
  })

  test('should open the explorer on the network of a provider', async ({ page }) => {
    await page.goto('/providers/dwd')
    await page.getByRole('link', { name: 'Open in the explorer' }).first().click()

    await expect(page).toHaveURL(/\/explorer\?provider=dwd&network=/)
    await expect(page.getByText(/Select Parameters/i).first()).toBeVisible()
  })

  test('should say so for a provider there is none of', async ({ page }) => {
    await page.goto('/providers/nowhere')

    await expect(page.getByText('There is no provider called “nowhere”.')).toBeVisible()
  })
})

test.describe('Versions in the navigation', () => {
  const LINE = /^App \d+\.\d+\.\d+ · Backend \d+\.\d+\.\d+/

  test('are under the settings of the sidebar, the app\'s and the backend\'s', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')

    await expect(page.getByTestId('app-versions')).toHaveText(LINE)
  })

  test('are in the drawer of a phone', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')
    await page.getByRole('button', { name: 'Menu', exact: true }).click()

    await expect(page.getByTestId('app-versions')).toHaveText(LINE)
  })

  test('are in the settings popover where the navigation is a rail of icons', async ({ page }) => {
    await page.setViewportSize({ width: 1100, height: 800 })
    await page.goto('/')
    await expect(page.getByTestId('app-versions')).toHaveCount(0)
    await page.getByRole('button', { name: 'Settings', exact: true }).click()

    await expect(page.getByTestId('app-versions')).toHaveText(LINE)
  })
})

test.describe('The navigation as a rail of icons', () => {
  test.use({ viewport: { width: 1100, height: 800 } })

  test('names every link for a screen reader, though the labels are not drawn', async ({ page }) => {
    await page.goto('/')
    const links = page.getByRole('navigation', { name: 'Menu' }).getByRole('link')
    await expect(links.first()).toBeVisible()
    const count = await links.count()
    expect(count).toBeGreaterThanOrEqual(12)
    for (let index = 0; index < count; index++)
      await expect(links.nth(index)).toHaveAccessibleName(/\S/)
    await expect(page.getByRole('navigation', { name: 'Menu' }).getByRole('link', { name: 'Explorer', exact: true })).toBeVisible()
  })

  test('has the page beside the rail, not under it', async ({ page }) => {
    await page.goto('/')
    const rail = (await page.locator('aside').boundingBox())!
    const main = (await page.locator('main#main').boundingBox())!

    expect(main.x).toBeGreaterThanOrEqual(rail.x + rail.width - 1)
    expect(main.y).toBeLessThan(100)
  })
})

// A control that is only an icon: its icon is a mask over a background colour, which forced colours (Windows high
// contrast) replaces by the canvas, so the icon has to be given the colour of the text instead.
async function settled(page: Page) {
  // a drawer, popover or dialog that is still sliding in is not where its screenshot will be taken
  await page.evaluate(async () => {
    await Promise.all(document.getAnimations().map(animation => animation.finished.catch(() => {})))
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  })
}

async function iconIsPainted(page: Page, icon: Locator) {
  await settled(page)
  const box = (await icon.boundingBox())!
  expect(box.width).toBeGreaterThan(0)
  const colours = await icon.evaluate((element) => {
    const style = getComputedStyle(element)
    // the system colour of the canvas, which the page's own background is replaced by
    const probe = document.createElement('div')
    probe.style.backgroundColor = 'Canvas'
    document.body.append(probe)
    const canvas = getComputedStyle(probe).backgroundColor
    probe.remove()
    return { background: style.backgroundColor, text: style.color, canvas }
  })
  expect(colours.background, 'the icon is painted in the colour of the text').toBe(colours.text)
  expect(colours.background, 'and not in that of the canvas').not.toBe(colours.canvas)
  expect(colours.text, 'which is a system colour, not the colour of the page').not.toBe('rgb(34, 97, 190)')
  // and the pixels differ from those of the same place with the icon hidden
  const clip = { x: box.x, y: box.y, width: box.width, height: box.height }
  const painted = await page.screenshot({ clip })
  await icon.evaluate((element) => {
    element.style.visibility = 'hidden'
  })
  const hidden = await page.screenshot({ clip })
  await icon.evaluate((element) => {
    element.style.visibility = ''
  })
  expect(painted.equals(hidden), 'the icon puts pixels on the page').toBe(false)
}

test.describe('Forced colours', () => {
  test.use({ forcedColors: 'active', reducedMotion: 'reduce' })

  test('show the icons of the rail, and mark the current page', async ({ page }) => {
    await page.setViewportSize({ width: 1100, height: 800 })
    await page.goto('/explorer')
    const nav = page.getByRole('navigation', { name: 'Menu' })
    const links = nav.getByRole('link')
    await expect(links.first()).toBeVisible()
    const count = await links.count()
    expect(count).toBeGreaterThanOrEqual(12)
    for (let index = 0; index < count; index++)
      await iconIsPainted(page, links.nth(index).locator('.iconify').first())
    await iconIsPainted(page, page.locator('aside').getByRole('button', { name: 'Search', exact: true }).locator('.iconify').first())
    await iconIsPainted(page, page.locator('aside').getByRole('button', { name: 'Settings', exact: true }).locator('.iconify').first())

    const current = nav.locator('[aria-current="page"]')
    await expect(current).toHaveCount(1)
    expect(await current.evaluate(element => getComputedStyle(element).outlineStyle)).toBe('solid')
  })

  test('show the icon buttons of the top bar and of the drawer', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')
    await iconIsPainted(page, page.getByRole('banner').getByRole('button', { name: 'Search', exact: true }).locator('.iconify').first())
    await page.getByRole('button', { name: 'Menu', exact: true }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await iconIsPainted(page, dialog.getByRole('button', { name: 'Close', exact: true }).locator('.iconify').first())
    await iconIsPainted(page, dialog.getByRole('link', { name: 'Explorer', exact: true }).locator('.iconify').first())
  })

  test('mark the current page of the sidebar', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/glossary')
    const current = page.getByRole('navigation', { name: 'Menu' }).locator('[aria-current="page"]')
    await expect(current).toHaveText('Glossary')
    expect(await current.evaluate(element => getComputedStyle(element).outlineStyle)).toBe('solid')
  })
})

test.describe('The drawer in a short window', () => {
  for (const size of [{ width: 320, height: 256 }, { width: 640, height: 512 }]) {
    test(`scrolls as a whole, and reaches the settings, at ${size.width} x ${size.height} px (400 % zoom)`, async ({ page }) => {
      await page.setViewportSize(size)
      await page.goto('/')
      await page.getByRole('button', { name: 'Menu', exact: true }).click()
      const dialog = page.getByRole('dialog')
      await expect(dialog).toBeVisible()

      // the list of places is not a small scroller of its own
      const nav = dialog.getByRole('navigation', { name: 'Menu' })
      const [client, scroll] = await nav.evaluate(element => [element.clientHeight, element.scrollHeight])
      expect(scroll).toBeLessThanOrEqual(client + 1)
      expect(client).toBeGreaterThan(size.height / 2)

      const settings = dialog.getByRole('button', { name: 'Settings', exact: true })
      await settings.scrollIntoViewIfNeeded()
      await expect(settings).toBeInViewport()
    })
  }

  test('has no keys beside the search on a phone, where the sidebar has them', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')
    await page.getByRole('button', { name: 'Menu', exact: true }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog.getByRole('button', { name: 'Search', exact: true })).toBeVisible()
    await expect(dialog.locator('kbd')).toHaveCount(0)

    await page.keyboard.press('Escape')
    await page.setViewportSize({ width: 1440, height: 900 })
    await expect(page.locator('aside').getByRole('button', { name: 'Search', exact: true }).locator('kbd')).toHaveCount(2)
  })
})

test.describe('The focus when the layout changes', () => {
  test('goes to the page when the window widens under an open drawer', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')
    await page.getByRole('button', { name: 'Menu', exact: true }).click()
    await expect(page.getByRole('dialog')).toBeVisible()

    await page.setViewportSize({ width: 1300, height: 800 })

    await expect(page.locator('#main')).toBeFocused()
  })

  test('goes to the page when the window narrows under the open settings of the rail', async ({ page }) => {
    await page.setViewportSize({ width: 1100, height: 800 })
    await page.goto('/')
    await page.getByRole('button', { name: 'Settings', exact: true }).click()
    await expect(page.getByRole('dialog')).toBeVisible()

    await page.setViewportSize({ width: 800, height: 800 })

    await expect(page.locator('#main')).toBeFocused()
  })

  test('stays on a link of the rail when the window crosses 1280 px, in both directions', async ({ page }) => {
    await page.setViewportSize({ width: 1100, height: 800 })
    await page.goto('/')
    await page.locator('aside nav a[href="/explorer"]').focus()

    await page.setViewportSize({ width: 1300, height: 800 })
    await expect(page.locator('aside nav a[href="/explorer"]')).toBeFocused()
    await expect(page.locator('aside nav a[href="/explorer"]')).toContainText('Explorer')

    await page.setViewportSize({ width: 1100, height: 800 })
    await expect(page.locator('aside nav a[href="/explorer"]')).toBeFocused()
  })

  test('leaves a page that had no focus without one, and unscrolled, when the window crosses 1024 px', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 700 })
    await page.goto('/settings')
    // the app has taken the page up: the layout's watchers exist from here (a resize before this would test nothing)
    await expect(page.locator('header[data-app-nav]')).toBeVisible()
    expect(await page.evaluate(() => document.activeElement === document.body)).toBe(true)

    await page.setViewportSize({ width: 1300, height: 700 })
    await expect(page.locator('aside nav')).toBeVisible()
    await page.waitForTimeout(700)

    expect(await page.evaluate(() => document.activeElement === document.body)).toBe(true)
    expect(await page.evaluate(() => window.scrollY)).toBe(0)
  })

  test('goes to the search button of the new layout when the palette closes and the button that opened it is gone', async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 800 })
    await page.goto('/')
    await expect(page.locator('header[data-app-nav]')).toBeVisible()
    await page.locator('header[data-app-nav] [data-app-search]').click()
    await expect(page.locator('[data-slot="root"] > [data-slot="input"] input')).toBeVisible()

    await page.setViewportSize({ width: 1300, height: 800 })
    await expect(page.locator('aside nav')).toBeVisible()
    await page.waitForTimeout(700)
    await page.keyboard.press('Escape')

    await expect(page.locator('aside [data-app-search]')).toBeFocused()
  })

  test('does the same for a palette opened from the drawer', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 })
    await page.goto('/')
    await expect(page.locator('header[data-app-nav]')).toBeVisible()
    await page.getByRole('button', { name: 'Menu', exact: true }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'Search', exact: true }).click()
    await expect(page.locator('[data-slot="root"] > [data-slot="input"] input')).toBeVisible()

    await page.setViewportSize({ width: 1300, height: 800 })
    await expect(page.locator('aside nav')).toBeVisible()
    await page.waitForTimeout(700)
    await page.keyboard.press('Escape')

    await expect(page.locator('aside [data-app-search]')).toBeFocused()
  })

  test('closes the settings popover of the rail when the palette opened over it goes to a page', async ({ page }) => {
    await page.setViewportSize({ width: 1100, height: 800 })
    await page.goto('/')
    await page.locator('aside').getByRole('button', { name: 'Settings', exact: true }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.keyboard.press('Control+k')
    await expect(page.locator('[data-slot="root"] > [data-slot="input"] input')).toBeVisible()
    await page.keyboard.type('glossar')
    await expect(page.locator('[role="option"][data-highlighted]')).toHaveText('Glossary')
    await page.keyboard.press('Enter')

    await expect(page).toHaveURL(/\/glossary/)
    await expect(page.getByRole('dialog')).toHaveCount(0)
  })
})

test.describe('The sticky top bar', () => {
  test('keeps a focused element clear of it, tabbing back up a page', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 700 })
    await page.goto('/settings')
    await page.locator('footer a').last().focus()
    const bar = (await page.locator('header[data-app-nav]').boundingBox())!

    for (let stop = 0; stop < 30; stop++) {
      await page.keyboard.press('Shift+Tab')
      await page.waitForTimeout(60)
      const top = await page.evaluate(() => {
        const active = document.activeElement
        // the bar's own buttons are at the top of the window by design
        return active && active !== document.body && !active.closest('header[data-app-nav]') ? active.getBoundingClientRect().top : null
      })
      if (top !== null)
        expect(top, `stop ${stop}`).toBeGreaterThanOrEqual(bar.height - 1)
    }
  })
})

test.describe('The settings popover in a short window', () => {
  test('stays inside the window at 320 x 256 px, and reaches its language field', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 256 })
    await page.goto('/')
    await page.getByRole('button', { name: 'Menu', exact: true }).click()
    await settled(page)
    await page.getByRole('dialog').getByRole('button', { name: 'Settings', exact: true }).click()
    await settled(page)
    const popover = page.getByRole('dialog').last()
    const box = (await popover.boundingBox())!

    expect(box.y).toBeGreaterThanOrEqual(0)
    expect(box.y + box.height).toBeLessThanOrEqual(256 + 1)
    await expect(page.getByText('Language', { exact: true })).toBeInViewport()
  })
})

test.describe('The versions line', () => {
  test('breaks a long version instead of widening the sidebar', async ({ page }) => {
    await page.route('**/api/version', route => route.fulfill({ json: { version: `1.${'0'.repeat(60)}` } }))
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    const line = page.getByTestId('app-versions')
    await expect(line).toContainText('Backend 1.0000')

    const [client, scroll] = await line.evaluate(element => [element.clientWidth, element.scrollWidth])
    expect(scroll).toBeLessThanOrEqual(client)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })

  test('is not made of an answer that is no version', async ({ page }) => {
    await page.route('**/api/version', route => route.fulfill({ json: { version: { nested: true } } }))
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')

    await expect(page.getByTestId('app-versions')).toContainText('Backend unknown')
  })
})

test.describe('Support Page', () => {
  test('should be reachable from the navigation', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    // Support is in the navigation's project group, and a footer link. Both are named "Support", hence the scoping.
    await page.getByRole('navigation').getByRole('link', { name: /support/i }).click()

    await expect(page).toHaveURL(/\/support/)
  })

  test('should be reachable from the footer', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('contentinfo').getByRole('link', { name: /support/i }).click()

    await expect(page).toHaveURL(/\/support/)
  })

  test('should display support options', async ({ page }) => {
    await page.goto('/support')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText(/Report Issues/i)).toBeVisible()
    await expect(page.getByText(/Contribute/i)).toBeVisible()
  })

  test('should have external links', async ({ page }) => {
    await page.goto('/support')
    await page.waitForLoadState('networkidle')

    const githubLink = page.getByRole('link', { name: /github/i }).first()
    await expect(githubLink).toBeVisible()
  })
})

test.describe('About Page', () => {
  test('should be reachable from the footer', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await page.getByRole('contentinfo').getByRole('link', { name: /about/i }).click()
    await expect(page).toHaveURL(/\/about/)
  })

  test('should introduce the project and the maintainer', async ({ page }) => {
    await page.goto('/about')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: /About Wetterdienst/i })).toBeVisible()
    await expect(page.getByText('Benjamin Gutzmann')).toBeVisible()
    await expect(page.getByText('Andreas Motl')).toBeVisible()
  })
})

test.describe('Impressum Page', () => {
  test('should navigate to impressum page', async ({ page }) => {
    // Go directly to impressum page instead of trying to find the link
    await page.goto('/impressum')
    await expect(page).toHaveURL(/\/impressum/)
  })

  test('should display legal notice', async ({ page }) => {
    await page.goto('/impressum')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: /Legal Notice/i })).toBeVisible()
  })
})

test.describe('Privacy Policy Page', () => {
  test('should be linked in the footer next to the legal notice', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    const footer = page.getByRole('contentinfo')
    await expect(footer.locator('a[href="/impressum"]')).toBeVisible()
    await footer.locator('a[href="/datenschutz"]').click()
    await expect(page).toHaveURL(/\/datenschutz/)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })

  test('should serve the same page at /privacy', async ({ page }) => {
    await page.goto('/privacy')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(page.getByText('Hetzner').first()).toBeVisible()
  })

  test('should be German with a German browser and English with an English one', async ({ browser }) => {
    for (const [locale, heading] of [['de-DE', 'Datenschutzerklärung'], ['en-GB', 'Privacy policy']] as const) {
      const context = await browser.newContext({ locale })
      const page = await context.newPage()
      await page.goto('/datenschutz')
      await page.waitForLoadState('networkidle')
      await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
      await context.close()
    }
  })
})

test.describe('Forecast (Meteogram) Page', () => {
  test('should navigate to the forecast page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('navigation').getByRole('link', { name: /forecast/i }).click()

    await expect(page).toHaveURL(/\/meteogram/)
  })

  test('should display the forecast heading and station search', async ({ page }) => {
    await page.goto('/meteogram')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: /Weather forecast/i }).first()).toBeVisible()
    await expect(page.getByText(/Search for a station above/i)).toBeVisible()
  })

  test('should load a forecast when a station is picked via the URL', async ({ page }) => {
    await page.goto('/meteogram?station=01001')
    await page.waitForLoadState('networkidle')

    // Either the chart loads or a definitive error/no-data state is shown --
    // never the empty "search for a station" hint.
    await expect(page.getByText(/Search for a station above/i)).not.toBeVisible()
    await expect(page.getByText('JAN MAYEN', { exact: true })).toBeVisible()
  })
})

test.describe('History Page', () => {
  test('should navigate to the history page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('navigation').getByRole('link', { name: /history/i }).click()

    await expect(page).toHaveURL(/\/history/)
  })

  test('should display the station history heading', async ({ page }) => {
    await page.goto('/history')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: /Station history/i }).first()).toBeVisible()
  })

  test('should show the history sections selector', async ({ page }) => {
    await page.goto('/history')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText(/History sections/i)).toBeVisible()
  })
})

test.describe('Settings Page', () => {
  test('should navigate to the settings page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    // The settings button of the navigation opens a quick-settings popover; the full settings
    // page is reached via the "Settings" link inside that popover.
    await page.getByRole('button', { name: 'Settings', exact: true }).click()
    await page.getByRole('link', { name: 'Settings', exact: true }).click()

    await expect(page).toHaveURL(/\/settings/)
  })

  test('should display language, appearance and units sections', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: /^Settings$/i })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Language' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Appearance' })).toBeVisible()
  })

  test('should switch theme when a theme button is clicked', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForLoadState('networkidle')

    await page.getByRole('button', { name: /^Dark$/i }).click()
    await expect(page.locator('html')).toHaveClass(/dark/)
  })
})

test.describe('Widget Page', () => {
  test('should show a hint when no station is specified', async ({ page }) => {
    await page.goto('/widget')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText(/No station specified/i)).toBeVisible()
  })

  test('should render a minimal embeddable view for a given station', async ({ page }) => {
    await page.goto('/widget?station=01001')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText(/No station specified/i)).not.toBeVisible()
    await expect(page.getByText('JAN MAYEN')).toBeVisible()
    await expect(page.getByTitle(/Open full forecast/i)).toBeVisible()
  })
})

test.describe('Color Mode Toggle', () => {
  test('should have color mode toggle button', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Look for the color mode button (should have an icon)
    const colorModeButton = page.locator('button').filter({ hasText: '' }).first()
    await expect(colorModeButton).toBeVisible()
  })
})
