import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// The accessibility baseline (tests/e2e/accessibility/baseline.json) is the list of violations the app has and does not
// fix itself. Each entry says why, and where the cause is another project's, links the issue there (GH-2559).
interface Entry { rule: string, page: string, state: string, issue?: string | null, reason?: string }
const baseline = JSON.parse(readFileSync(fileURLToPath(new URL('../e2e/accessibility/baseline.json', import.meta.url)), 'utf-8')) as { entries: Entry[] }

describe('the accessibility baseline', () => {
  it.each(baseline.entries.map(entry => [`${entry.rule}: ${entry.page} / ${entry.state}`, entry] as const))('gives a reason for %s', (_name, entry) => {
    expect(typeof entry.reason, 'a `reason`: why the app does not fix it, and whose the cause is').toBe('string')
    // a sentence, not a placeholder
    expect(entry.reason!.length).toBeGreaterThan(60)
  })

  it.each(baseline.entries.map(entry => [`${entry.rule}: ${entry.page} / ${entry.state}`, entry] as const))('has for %s an issue of the project that owns the cause, or null where there is none', (_name, entry) => {
    expect(entry.issue, 'an `issue`: a URL, or null').not.toBeUndefined()
    if (entry.issue !== null)
      expect(entry.issue).toMatch(/^https:\/\/github\.com\/[\w-]+\/[\w.-]+\/(issues|pull)\/\d+$/)
  })

  it('names the project in a reason that links no issue, so that it is known whose it is', () => {
    for (const entry of baseline.entries.filter(entry => entry.issue === null))
      expect(entry.reason, `${entry.rule}: ${entry.page} / ${entry.state}`).toMatch(/Nuxt UI|Reka UI|Reka/)
  })
})
