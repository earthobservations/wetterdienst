import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { panelToggleStyle, SERIES_LABEL, seriesLabelColor, TOGGLE_WASH } from '../../app/utils/chart-theme'

// WCAG 2.x relative luminance and contrast ratio of two #rrggbb colours
function channels(hex: string) {
  return [1, 3, 5].map(i => Number.parseInt(hex.slice(i, i + 2), 16))
}
function luminance(hex: string) {
  const [r, g, b] = channels(hex).map(c => c / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
}
function contrast(a: string, b: string) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi! + 0.05) / (lo! + 0.05)
}

// The colours of the app are tokens of main.css (GH-3518): read from there, so that a change of a shade is held to
// the ratios it has to keep
const css = readFileSync(fileURLToPath(new URL('../../app/assets/css/main.css', import.meta.url)), 'utf-8')
function token(name: string): string {
  const value = new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, 'i').exec(css)?.[1]
  if (!value)
    throw new Error(`--${name} is not a colour of main.css`)
  return value
}
// the `.dark { ... }` block of the file: the night's tokens
const nightStart = css.indexOf('.dark {')
const night = css.slice(nightStart, css.indexOf('}', nightStart))
function darkToken(name: string): string {
  const value = new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, 'i').exec(night)?.[1]
  if (!value)
    throw new Error(`--${name} is not a colour of main.css at night`)
  return value
}
const brand = (shade: number) => token(`color-brand-${shade}`)
const ink = (shade: number) => token(`color-ink-${shade}`)
const WHITE = '#ffffff'

describe('the solid primary button (app.config.ts)', () => {
  // light: a white label on the logo's blue, hovered shade 700, pressed shade 800;
  // dark: a navy label on shade 400, hovered shade 300, pressed shade 200
  it.each([
    ['light, at rest', WHITE, 600],
    ['light, hovered', WHITE, 700],
    ['light, pressed', WHITE, 800],
    ['dark, at rest', 'navy', 400],
    ['dark, hovered', 'navy', 300],
    ['dark, pressed', 'navy', 200],
  ] as const)('has a label that clears 4.5:1 on its fill, %s', (_state, label, shade) => {
    const text = label === 'navy' ? ink(950) : label
    expect(contrast(text, brand(shade))).toBeGreaterThanOrEqual(4.5)
  })

  it('is the logo\'s blue', () => {
    expect(brand(600).toLowerCase()).toBe('#2e6fd1')
    expect(css).toMatch(/--ui-primary:\s*var\(--color-brand-600\)/)
  })
})

describe('text in the colours of the app', () => {
  const PAPER = ink(50)
  it.each([
    ['body text on a card', ink(800), WHITE],
    ['muted text on a card', ink(600), WHITE],
    ['dimmed text on a card', ink(500), WHITE],
    ['dimmed text on the paper', ink(500), PAPER],
    ['dimmed text on a hovered field', ink(500), ink(100)],
    ['primary text on a card', brand(700), WHITE],
    ['primary text on its soft tint', brand(700), brand(100)],
    ['a hovered link on a card', brand(800), WHITE],
    ['muted text at night, on the page', ink(400), ink(950)],
    ['muted text at night, on the accented fill', ink(400), darkToken('ui-bg-accented')],
    ['primary text at night, on a card', brand(400), darkToken('ui-bg')],
  ])('clears 4.5:1: %s', (_what, text, ground) => {
    expect(contrast(text, ground)).toBeGreaterThanOrEqual(4.5)
  })

  // the edge of a field, a checkbox and a switch, and the focus ring: 3:1 (WCAG 1.4.11)
  it.each([
    ['the edge of a field on a card', token('ui-border-accented'), WHITE],
    ['the edge of a field on the paper', token('ui-border-accented'), PAPER],
    ['the focus ring on the paper', token('color-brand-700'), PAPER],
  ])('clears 3:1: %s', (_what, line, ground) => {
    expect(contrast(line, ground)).toBeGreaterThanOrEqual(3)
  })
})

describe('the tiles of the tools (GH-3650)', () => {
  // a tile is a mark beside a name that is always written, so it needs 3:1 as a non-text mark (WCAG 1.4.11) against what
  // it lies on, and its glyph 4.5:1 on its fill (the glyph is a picture of the name, and so held to text's ratio)
  const CARD = '#ffffff'
  const PAPER = ink(50)
  const NIGHT_CARD = darkToken('ui-bg')
  const NIGHT_PAGE = ink(950)

  it.each([
    ['by day, on a card', token('color-tile-map'), CARD],
    ['by day, on the paper', token('color-tile-map'), PAPER],
    ['at night, on a card', token('color-tile-map-night'), NIGHT_CARD],
    ['at night, on the page', token('color-tile-map-night'), NIGHT_PAGE],
  ])('has a violet map tile that clears 3:1 against what it lies on, %s', (_where, fill, ground) => {
    expect(contrast(fill, ground)).toBeGreaterThanOrEqual(3)
  })

  it.each([
    ['by day, white', token('color-tile-map'), WHITE],
    ['at night, navy', token('color-tile-map-night'), ink(950)],
  ])('has a glyph on the map tile that clears 4.5:1, %s', (_when, fill, glyph) => {
    expect(contrast(glyph, fill)).toBeGreaterThanOrEqual(4.5)
  })

  it('says in the stylesheet what the test holds: white on the day violet, navy on the night violet', () => {
    expect(css).toMatch(/\.tile-map\s*\{[^}]*--tile-fill:\s*var\(--color-tile-map\)[^}]*--tile-glyph:\s*#ffffff/)
    expect(css).toMatch(/\.dark \.tile-map\s*\{[^}]*--tile-fill:\s*var\(--color-tile-map-night\)[^}]*--tile-glyph:\s*var\(--color-ink-950\)/)
  })

  /** The hue of a colour, in degrees */
  function hue(hex: string) {
    const [r, g, b] = channels(hex).map(c => c! / 255) as [number, number, number]
    const max = Math.max(r, g, b)
    const delta = max - Math.min(r, g, b)
    const sector = max === r ? ((g - b) / delta) % 6 : max === g ? (b - r) / delta + 2 : (r - g) / delta + 4
    return (sector * 60 + 360) % 360
  }

  it('is in the gap of the colour wheel the issue names, between the rain\'s blue and the thermometer\'s coral (hue 250 to 280: violet-600 is 262, the lighter violet of the night 256), by day and at night', () => {
    for (const fill of [token('color-tile-map'), token('color-tile-map-night')]) {
      expect(hue(fill)).toBeGreaterThanOrEqual(250)
      expect(hue(fill)).toBeLessThanOrEqual(280)
    }
  })

  it('is far from the other four tiles in hue, 40 degrees at the least', () => {
    const distance = (a: number, b: number) => Math.min(Math.abs(a - b), 360 - Math.abs(a - b))
    for (const other of ['sun', 'rain', 'wind', 'heat'])
      expect(distance(hue(token('color-tile-map')), hue(token(`color-tile-${other}`))), other).toBeGreaterThanOrEqual(40)
  })
})

describe('the arrow buttons of the phone bar\'s chooser (GH-3846)', () => {
  // their edge is the muted text colour, on the row's raised background (1.4.11: 3:1)
  it('has the muted text colour as its edge', () => {
    expect(/\.bar-move \{[^}]*border: 1px solid var\(--ui-text-muted\)/.test(css)).toBe(true)
  })

  it.each([
    ['light, on the row', ink(600), ink(100)],
    ['light, on the button\'s own fill', ink(600), WHITE],
    ['dark, on the row', ink(400), darkToken('ui-bg-elevated')],
    ['dark, on the button\'s own fill', ink(400), darkToken('ui-bg')],
  ])('clears 3:1 against what it lies on, %s', (_where, edge, ground) => {
    expect(contrast(edge, ground)).toBeGreaterThanOrEqual(3)
  })
})

describe('the two lines of the bar\'s tools and the menu-only tools (GH-3934)', () => {
  // a line beside a tool in the Menu's sheet, and the dashed line of the chooser: non-text marks (WCAG 1.4.11), 3:1
  // against what they lie on, light and dark. The words a screen reader gets are the other half, and tested with the sheet.
  const day = css.slice(css.indexOf(':root,'), css.indexOf('.dark {'))
  const shade = (block: string, name: string) => brand(Number(new RegExp(`--${name}:\\s*var\\(--color-brand-(\\d+)\\)`).exec(block)?.[1]))
  const CARD = '#ffffff'
  const HOVERED_LINK = ink(100)
  const NIGHT_CARD = darkToken('ui-bg')
  const NIGHT_HOVERED_LINK = darkToken('ui-bg-elevated')

  it.each([
    ['the bar\'s line by day, on the sheet', shade(day, 'app-mark-bar'), CARD],
    ['the bar\'s line by day, on a hovered link', shade(day, 'app-mark-bar'), HOVERED_LINK],
    ['the menu-only line by day, on the sheet', shade(day, 'app-mark-menu'), CARD],
    ['the menu-only line by day, on a hovered link', shade(day, 'app-mark-menu'), HOVERED_LINK],
    ['the bar\'s line at night, on the sheet', shade(night, 'app-mark-bar'), NIGHT_CARD],
    ['the bar\'s line at night, on a hovered link', shade(night, 'app-mark-bar'), NIGHT_HOVERED_LINK],
    ['the menu-only line at night, on the sheet', shade(night, 'app-mark-menu'), NIGHT_CARD],
    ['the menu-only line at night, on a hovered link', shade(night, 'app-mark-menu'), NIGHT_HOVERED_LINK],
  ])('clears 3:1: %s', (_what, line, ground) => {
    expect(contrast(line, ground)).toBeGreaterThanOrEqual(3)
  })

  it('has two colours that are not one, by day and at night', () => {
    expect(shade(day, 'app-mark-bar')).not.toBe(shade(day, 'app-mark-menu'))
    expect(shade(night, 'app-mark-bar')).not.toBe(shade(night, 'app-mark-menu'))
  })

  it('has the bar\'s line the stronger of the two against the sheet, by day and at night', () => {
    expect(contrast(shade(day, 'app-mark-bar'), CARD)).toBeGreaterThan(contrast(shade(day, 'app-mark-menu'), CARD))
    expect(contrast(shade(night, 'app-mark-bar'), NIGHT_CARD)).toBeGreaterThan(contrast(shade(night, 'app-mark-menu'), NIGHT_CARD))
  })

  it('draws the menu-only line shorter than the bar\'s, so that the groups differ by shape as well (WCAG 1.4.1)', () => {
    const height = (rule: RegExp) => Number(rule.exec(css)?.[1])
    expect(height(/\.tool-mark\s*\{[^}]*height:\s*([\d.]+)rem/)).toBe(1.25)
    expect(height(/\.sheet-tool\[data-group="menu"\] \.tool-mark\s*\{[^}]*height:\s*([\d.]+)rem/)).toBe(0.75)
  })

  it('keeps the two lines apart in forced colours, where a background is replaced: text colour and grey', () => {
    const forced = css.slice(css.indexOf('@media (forced-colors: active)'))
    expect(forced).toMatch(/\.tool-mark\s*\{[^}]*forced-color-adjust:\s*none;[^}]*background:\s*CanvasText/)
    expect(forced).toMatch(/\.sheet-tool\[data-group="menu"\] \.tool-mark\s*\{[^}]*background:\s*GrayText/)
  })

  it('draws the chooser\'s dashed line in the bar\'s colour, so the sheet and the chooser mark the groups alike', () => {
    expect(css).toMatch(/\.bar-line\s*\{[^}]*border-top:\s*2px dashed var\(--app-mark-bar\)/)
    expect(css).toMatch(/\.tool-mark\s*\{[^}]*background:\s*var\(--app-mark-bar\)/)
    expect(css).toMatch(/\.sheet-tool\[data-group="menu"\] \.tool-mark\s*\{[^}]*background:\s*var\(--app-mark-menu\)/)
  })
})

describe('the Forecast\'s icons, panel toggles and the Tailwind colours of the markup (GH-3642)', () => {
  // `a` over `ground` at the share `alpha`, as the browser blends it
  function over(a: string, ground: string, alpha: number) {
    const [fg, bg] = [channels(a), channels(ground)]
    return `#${fg.map((c, i) => Math.round(c! * alpha + bg[i]! * (1 - alpha)).toString(16).padStart(2, '0')).join('')}`
  }
  const CARD = darkToken('ui-bg')
  const PAPER = ink(50)
  // the toolbar of the Forecast: `bg-gray-50/70` by day and `dark:bg-gray-800/40` at night, on a card (the page's paper
  // by day is the lighter of the two grounds a card has, and the toolbar is a wash of it, so both are held)
  const TOOLBARS = {
    'light, on a card': over(ink(50), WHITE, 0.7),
    'light, on the paper': over(ink(50), PAPER, 0.7),
    'dark, on a card': over(ink(800), CARD, 0.4),
  } as const
  const series = Object.keys(SERIES_LABEL) as (keyof typeof SERIES_LABEL)[]

  describe.each(series)('the icon of %s', (name) => {
    it.each([
      ['by day, on a card', false, WHITE],
      ['by day, on the paper', false, PAPER],
      ['by day, on the toolbar', false, TOOLBARS['light, on a card']],
      ['at night, on a card', true, CARD],
      ['at night, on the toolbar', true, TOOLBARS['dark, on a card']],
    ] as const)('clears 4.5:1 as the summary\'s icon, %s', (_where, dark, ground) => {
      expect(contrast(seriesLabelColor(name, dark), ground)).toBeGreaterThanOrEqual(4.5)
    })

    // a toggle that is on is a mark that carries a state (1.4.11: 3:1) on its own wash of the label colour; the wash
    // is the share of the colour itself that the style names, over each toolbar
    it.each(Object.entries(TOOLBARS))('clears 3:1 as the icon of a toggle that is on, %s', (where, toolbar) => {
      const color = seriesLabelColor(name, where.startsWith('dark'))
      expect(contrast(color, over(color, toolbar, TOGGLE_WASH))).toBeGreaterThanOrEqual(3)
    })
  })

  it('has the toggle that is on use the label colour and the share the test holds', () => {
    const style = panelToggleStyle('#0e7490')
    expect(style.color).toBe('#0e7490')
    expect(style.backgroundColor).toBe(`color-mix(in srgb, #0e7490 ${TOGGLE_WASH * 100}%, transparent)`)
  })

  // Tailwind's palette, as the browser draws it: oklch() in `tailwindcss/theme.css`, here as #rrggbb
  const theme = readFileSync(fileURLToPath(new URL('../../node_modules/tailwindcss/theme.css', import.meta.url)), 'utf-8')
  // `oklch(55.6% 0 none)`: Tailwind writes a hue of `none` for its greys (neutral, zinc-50), which is a hue of 0
  function oklchToHex(value: string) {
    const parts = /oklch\(\s*([\d.]+)%\s+([\d.]+)\s+([\d.]+|none)\s*\)/.exec(value)
    if (!parts)
      throw new Error(`not an oklch() colour of Tailwind's palette: ${JSON.stringify(value)}`)
    const [lightness, chroma, hueDegrees] = [Number(parts[1]), Number(parts[2]), parts[3] === 'none' ? 0 : Number(parts[3])]
    const [L, a, b] = [lightness / 100, chroma * Math.cos(hueDegrees * Math.PI / 180), chroma * Math.sin(hueDegrees * Math.PI / 180)]
    const [l, m, s] = [L + 0.3963377774 * a + 0.2158037573 * b, L - 0.1055613458 * a - 0.0638541728 * b, L - 0.0894841775 * a - 1.291485548 * b].map(v => v ** 3) as [number, number, number]
    const linear = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s]
    return `#${linear.map((c) => {
      const encoded = c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055
      return Math.round(Math.min(1, Math.max(0, encoded)) * 255).toString(16).padStart(2, '0')
    }).join('')}`
  }
  // `gray` is the app's `ink` and `primary` its `brand` (`app.config.ts`: `colors: { primary: 'brand' }`), both of main.css.
  // Their shades are the same by day and at night: `.dark` changes which shade is `--ui-primary` (what `text-primary`
  // and the fill of a button say), never a `--color-brand-*` or `--color-ink-*`, which a test below holds
  function shade(hue: string, step: string) {
    // a step that is not in the scale (`text-primary-150`) is no colour, which the scan reports, and no crash
    const own = (scale: 'brand' | 'ink') => new RegExp(`--color-${scale}-${step}:\\s*(#[0-9a-f]{6})`, 'i').exec(css)?.[1]
    if (hue === 'gray')
      return own('ink')
    if (hue === 'primary' || hue === 'brand')
      return own('brand')
    const value = new RegExp(`--color-${hue}-${step}:\\s*(oklch\\([^)]*\\))`).exec(theme)?.[1]
    return value ? oklchToHex(value) : undefined
  }

  it('reads Tailwind\'s palette as the browser draws it (red-600 is 4.77:1 on white)', () => {
    expect(contrast(shade('red', '600')!, WHITE)).toBeCloseTo(4.77, 1)
  })

  it('reads the greys, which Tailwind writes with a hue of none (neutral-500 is 4.74:1 on white)', () => {
    expect(shade('neutral', '500')).toBeDefined()
    expect(contrast(shade('neutral', '500')!, WHITE)).toBeCloseTo(4.74, 2)
    // every colour of the palette converts, so that no class can crash the collection below
    const all = [...theme.matchAll(/--color-([a-z]+-\d+):\s*(oklch\([^)]*\))/g)]
    expect(all.length).toBeGreaterThan(200)
    for (const [, name, value] of all)
      expect(oklchToHex(value!), name).toMatch(/^#[0-9a-f]{6}$/)
  })

  it('names a colour it cannot read, where it would otherwise fail on a missing match', () => {
    expect(() => oklchToHex('color-mix(in oklab, red, blue)')).toThrow(/not an oklch\(\) colour/)
  })

  // Every `text-<colour>-<step>` class of the markup (GH-3642), 4.5:1 (1.4.3; the same classes colour icons, which need 3:1,
  // but an icon in a text colour is read as text, and a colour that is not enough as a mark is not enough as text either):
  // - a class with `dark:` is painted on the dark card;
  // - a class without it on white, and, where its class string has no `dark:` partner of the same variants (`hover:` and
  //   so on), on the dark card too, as it is painted there as well.
  // Tailwind's palette, `gray` (the app's `ink`) and `primary` and `brand` (the app's `brand` scale) are read; the last
  // two through main.css (GH-3952). There is no class of them that is exempt: an icon in the primary colour is held to 4.5:1
  // like text, since darkening it from shade 500 (3.47:1 on white) to 600 (4.87:1) costs the look nothing, and an
  // exemption for the icons that need only 3:1 (1.4.11) would be a list to keep for no gain.
  // A class this test cannot read (an opacity, `text-[#hex]`) fails, so that none is skipped without a word.
  const sources = (readdirSync(fileURLToPath(new URL('../../app', import.meta.url)), { recursive: true }) as string[])
    .filter(file => /\.(?:vue|ts)$/.test(file))
    .map(file => [file, readFileSync(fileURLToPath(new URL(`../../app/${file}`, import.meta.url)), 'utf-8')] as const)
  interface Use { file: string, name: string, ground: 'white' | 'card', color: string }
  /** The uses of a colour, and what the scan could not read: one entry for each class of each string of the sources */
  function collect(files: readonly (readonly [string, string])[]) {
    const uses: Use[] = []
    const unreadable: string[] = []
    for (const [file, text] of files) {
      // between two quotes lies a class string, or code that has no such class: a partner in another literal is no partner
      for (const segment of text.split(/["'`]/)) {
        if (!segment.includes('text-'))
          continue
        const found = [...segment.matchAll(/(?<![\w-])((?:[a-z0-9-]+:)*)text-([a-z]+)-(\d{2,3})(\/[\w.%[\]]+)?(?![\w-])/g)]
        for (const [, variants, hue, step, opacity] of found) {
          if (opacity)
            unreadable.push(`${file}: ${variants}text-${hue}-${step}${opacity}`)
          else if (shade(hue!, step!) === undefined)
            unreadable.push(`${file}: ${variants}text-${hue}-${step} (not in the palette)`)
        }
        for (const [, variants, value] of segment.matchAll(/(?<![\w-])((?:[a-z0-9-]+:)*)text-\[((?:#|rgb|hsl|oklch|color:)[^\]]*)\]/g))
          unreadable.push(`${file}: ${variants}text-[${value}]`)
        // a partner is any `dark:` text colour of the same variants, `dark:text-white` among them
        const partners = new Set([...segment.matchAll(/(?<![\w-])((?:[a-z0-9-]+:)*)text-(?:white|black|[a-z]+-\d{2,3})(?![\w-])/g)]
          .filter(([, variants]) => variants!.split(':').includes('dark'))
          .map(([, variants]) => variants!.split(':').filter(variant => variant && variant !== 'dark').join(':')))
        for (const [, variants, hue, step, opacity] of found) {
          const color = opacity ? undefined : shade(hue!, step!)
          if (!color)
            continue
          const dark = variants!.split(':').includes('dark')
          const name = `${variants}text-${hue}-${step}`
          if (dark) {
            uses.push({ file, name, ground: 'card', color })
          }
          else {
            uses.push({ file, name, ground: 'white', color })
            if (!partners.has(variants!.replace(/:$/, '')))
              uses.push({ file, name: `${name} (no dark: partner, painted at night too)`, ground: 'card', color })
          }
        }
      }
    }
    return { uses, unreadable }
  }
  const { uses, unreadable } = collect(sources)
  const below = (list: readonly Use[]) => [...new Set(list
    .map(use => ({ ...use, ratio: contrast(use.color, use.ground === 'card' ? CARD : WHITE) }))
    .filter(use => use.ratio < 4.5)
    .map(use => `${use.file}: ${use.name} ${use.ratio.toFixed(2)}:1 on ${use.ground}`))]

  it('finds the Tailwind text colours of the markup', () => {
    expect(uses.length).toBeGreaterThan(100)
    expect(uses.some(use => use.file.endsWith('Meteogram.vue'))).toBe(true)
    expect(uses.some(use => use.name.startsWith('dark:text-'))).toBe(true)
  })

  it('reads every text colour class of the markup, the app\'s own primary scale included', () => {
    expect(unreadable).toEqual([])
  })

  describe('the primary scale (GH-3952)', () => {
    it('is the brand scale of main.css, which `.dark` does not redefine, so that a class means the same shade at night', () => {
      expect(readFileSync(fileURLToPath(new URL('../../app/app.config.ts', import.meta.url)), 'utf-8')).toMatch(/primary:\s*'brand'/)
      // defined once each (the 22 shades of the two scales), none of them in the `.dark` block
      expect(css.match(/^\s*--color-(?:brand|ink)-\d+\s*:/gm)).toHaveLength(22)
      expect(night).not.toMatch(/--color-(?:brand|ink)-\d+\s*:/)
      expect(shade('primary', '600')).toBe(brand(600))
      expect(shade('brand', '700')).toBe(brand(700))
    })

    it('is used, for icons and for links, at the shades the test reads', () => {
      const primary = uses.filter(use => /text-(?:primary|brand)-/.test(use.name))
      expect(primary.length).toBeGreaterThan(80)
      // an icon in the primary colour: shade 600 by day (4.87:1 on white) and 500 at night (4.53:1 on a card)
      expect(primary.some(use => use.name === 'text-primary-600' && use.ground === 'white')).toBe(true)
      expect(primary.some(use => use.name === 'dark:text-primary-500' && use.ground === 'card')).toBe(true)
      // a link: 700 by day
      expect(primary.some(use => use.name === 'text-primary-700')).toBe(true)
    })

    it('has no icon in shade 500 by day, which is 3.47:1 on white', () => {
      expect(uses.filter(use => /^(?:[a-z0-9-]+:)*text-(?:primary|brand)-500$/.test(use.name) && !use.name.startsWith('dark:') && use.ground === 'white')).toEqual([])
    })

    // the icons are painted on a card, but a move onto the page's paper, a tinted or a night's wash must still read:
    // shade 600 by day on `bg-gray-50` (the paper, ink-50) and `bg-primary-50`, shade 500 at night on the page canvas and
    // on `bg-gray-800/50` over it
    it.each([
      ['600 by day, on the page paper (ink-50)', brand(600), PAPER],
      ['600 by day, on bg-gray-50', brand(600), ink(50)],
      ['600 by day, on bg-primary-50', brand(600), brand(50)],
      ['500 at night, on the page canvas (ink-950)', brand(500), ink(950)],
      ['500 at night, on bg-gray-800/50 over the canvas', brand(500), over(ink(800), ink(950), 0.5)],
    ])('clears 4.5:1 for the icon in %s', (_where, color, ground) => {
      expect(contrast(color, ground)).toBeGreaterThanOrEqual(4.5)
    })

    it('reports a shade that is not in the scale, where it would otherwise throw', () => {
      const found = collect([['x.vue', '<i class="text-primary-150 text-gray-150 text-brand-975 dark:text-primary-600">']])
      expect(found.unreadable).toEqual([
        'x.vue: text-primary-150 (not in the palette)',
        'x.vue: text-gray-150 (not in the palette)',
        'x.vue: text-brand-975 (not in the palette)',
      ])
    })

    it('holds a primary class that is too light, by day and at night', () => {
      const scan = (markup: string) => collect([['x.vue', markup]])
      expect(below(scan('<i class="text-primary-500 dark:text-primary-500">').uses)).toEqual(['x.vue: text-primary-500 3.47:1 on white'])
      expect(below(scan('<i class="text-primary-600 dark:text-primary-600">').uses)).toEqual(['x.vue: dark:text-primary-600 3.22:1 on card'])
      expect(below(scan('<i class="text-primary-600">').uses)).toEqual(['x.vue: text-primary-600 (no dark: partner, painted at night too) 3.22:1 on card'])
      expect(below(scan('<i class="text-primary-600 dark:text-primary-500">').uses)).toEqual([])
    })
  })

  it('has no text colour of the markup under 4.5:1 where it is painted, by day on white and at night on the dark card', () => {
    expect(below(uses)).toEqual([])
  })

  // the scan itself, on text of its own: what it flags and what it lets through
  describe('the scan of the classes', () => {
    const scan = (markup: string) => collect([['x.vue', markup]])
    it('reads a grey that Tailwind writes with a hue of none', () => {
      expect(below(scan('<p class="text-neutral-500 dark:text-neutral-300">').uses)).toEqual([])
      expect(below(scan('<p class="text-neutral-400 dark:text-neutral-300">').uses)).toHaveLength(1)
    })
    it('takes dark:text-white as a partner', () => {
      expect(below(scan('<p class="text-gray-900 dark:text-white">').uses)).toEqual([])
    })
    it('holds a class with no dark: partner to the dark card as well, and one with a partner to its own ground', () => {
      expect(below(scan('<p class="text-red-600">').uses)).toEqual(['x.vue: text-red-600 (no dark: partner, painted at night too) 3.29:1 on card'])
      expect(below(scan('<p class="text-red-600 dark:text-red-400">').uses)).toEqual([])
      expect(below(scan('<p class="hover:text-red-600 dark:hover:text-red-400">').uses)).toEqual([])
    })
    it('does not take a partner from another string', () => {
      expect(below(scan(`<p :class="a ? 'text-red-600 dark:text-red-400' : 'text-red-600'">`).uses)).toEqual(['x.vue: text-red-600 (no dark: partner, painted at night too) 3.29:1 on card'])
    })
    it('fails on a class it cannot read', () => {
      expect(scan('<p class="text-red-600/70 dark:text-red-400">').unreadable).toEqual(['x.vue: text-red-600/70'])
      expect(scan('<p class="text-[#ff0000]">').unreadable).toEqual(['x.vue: text-[#ff0000]'])
      expect(scan('<p class="text-[10px] text-xs">').unreadable).toEqual([])
    })
  })

  // the card of today (Meteogram.vue) has `border-blue-600 dark:border-blue-400`, which `tests/nuxt/components/Meteogram.test.ts`
  // holds it to in the rendered card: those are 3:1 and more by day and at night (1.4.11)
  it('has blue-600 an edge of 3:1 on white and blue-400 on the dark card (the card of today)', () => {
    expect(contrast(shade('blue', '600')!, WHITE)).toBeGreaterThanOrEqual(3)
    expect(contrast(shade('blue', '400')!, CARD)).toBeGreaterThanOrEqual(3)
  })
})

describe('the weather icons of the forecast (GH-3527)', () => {
  // an icon is a meaningful graphic beside words that name it: 3:1 against what it lies on (WCAG 1.4.11). It is drawn
  // in `text-toned` (ink-700 by day, ink-300 at night) on the rows of the map's panel (the card), and on the day cards
  // (the paper tint, the tint of today's card, and at night the page and the card)
  it('is in the colours the stylesheet gives `text-toned`, which the ratios below are those of', () => {
    expect(css).toMatch(/--ui-text-toned:\s*var\(--color-ink-700\)/)
    expect(css).toMatch(/--ui-text-toned:\s*var\(--color-ink-300\)/)
  })

  it.each([
    ['by day, on a card', ink(700), WHITE],
    ['by day, on the paper', ink(700), ink(50)],
    ['by day, on the tint of a day card', ink(700), ink(100)],
    ['at night, on a card', ink(300), darkToken('ui-bg')],
    ['at night, on the page', ink(300), ink(950)],
    ['at night, on the accented fill', ink(300), darkToken('ui-bg-accented')],
  ])('clears 3:1: %s', (_where, icon, ground) => {
    expect(contrast(icon, ground)).toBeGreaterThanOrEqual(3)
  })
})
