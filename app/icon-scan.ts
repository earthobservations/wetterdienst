/**
 * Which files @nuxt/icon reads for the names of the icons it bundles with the page (`icon.clientBundle.scan` of
 * nuxt.config.ts, GH-3527). Its default reads components and markdown only, so an icon named in a `.ts` file
 * (the weather icons of `app/utils/weather-kind.ts`, the icons of `app/utils/sections.ts`) is not bundled and is
 * asked of the server at first paint, which is blank when that fails. `tests/unit/icon-scan.test.ts` holds the
 * weather icons to this scan. The default `globExclude` (node_modules, dist, build, coverage, test, tests, dot
 * directories) is kept.
 */
export const ICON_SCAN = {
  globInclude: ['**/*.{vue,ts,jsx,tsx,md,mdc,mdx,yml,yaml}'],
}
