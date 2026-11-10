import { fileURLToPath } from 'node:url'
import { IconUsageScanner } from '@nuxt/icon/utils'
import { describe, expect, it } from 'vitest'
import { WEATHER_ICONS } from '../../app/utils/weather-kind'
import { ICON_SCAN } from '../../icon-scan'

// The icons a page draws with its first paint are those @nuxt/icon finds in the app's files when it builds
// (`clientBundle.scan`); the others are asked of the server, and are blank where that fails (GH-3527).

describe('the icon scan of the build (icon-scan.ts, read by nuxt.config.ts)', () => {
  it('finds every weather icon, which are named in a .ts file', async () => {
    const found = await new IconUsageScanner(ICON_SCAN).scanFiles([fileURLToPath(new URL('../..', import.meta.url))])
    for (const icon of Object.values(WEATHER_ICONS))
      expect(found, icon).toContain(icon.replace(/^i-ph-/, 'ph:'))
  })

  it('keeps the default exclusion: the tests and node_modules are not read', () => {
    const scanner = new IconUsageScanner(ICON_SCAN)
    expect(scanner.globExclude).toEqual(expect.arrayContaining(['node_modules', 'tests', 'test', 'dist', 'build', '.*']))
    expect(scanner.globInclude).toContain('**/*.{vue,ts,jsx,tsx,md,mdc,mdx,yml,yaml}')
  })
})
