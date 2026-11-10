import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
// @ts-expect-error a script of plain JavaScript, with no declarations
import { URLS } from '../e2e/accessibility/lighthouse.mjs'

// `pnpm lighthouse` (tests/e2e/accessibility/lighthouse.mjs) scores every page the accessibility spec scans at first paint
describe('the pages Lighthouse is run on', () => {
  const spec = readFileSync(fileURLToPath(new URL('../e2e/accessibility.spec.ts', import.meta.url)), 'utf-8')
  const pages = spec.slice(spec.indexOf('const PAGES: Target[] = ['), spec.indexOf('interface State'))

  it('are every page of the spec\'s first paint', () => {
    const paths = [...pages.matchAll(/path: '([^']+)'/g)].map(match => match[1]!)
    expect(paths.length).toBeGreaterThanOrEqual(16)
    expect((URLS as string[]).filter(url => !url.includes('?'))).toEqual(expect.arrayContaining(paths))
  })

  it('are 17: those and the explorer with a station chosen', () => {
    expect(URLS).toHaveLength(17)
    expect((URLS as string[]).filter(url => url.includes('stations=00011'))).toHaveLength(1)
  })
})
