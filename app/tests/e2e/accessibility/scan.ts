import type { Page } from '@playwright/test'
import type { Backend } from './mock-backend'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import AxeBuilder from '@axe-core/playwright'

// The standard the app aims at (WCAG 2.2 level AA) as axe's tags: every rule that tests a success
// criterion of A or AA in 2.0, 2.1 or 2.2. axe's "best-practice" rules are not part of it.
export const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

export type Mode = 'light' | 'dark'
export type Locale = 'en' | 'de'

/** The way a page is scanned: the colour scheme and the language it is shown in */
export interface Variant { mode: Mode, locale: Locale }

export const variantKey = (variant: Variant) => `${variant.mode}/${variant.locale}`

/** One rule broken on one page in one state, in the variants it is broken in */
export interface BaselineEntry {
  rule: string
  page: string
  state: string
  /** The most severe impact axe gave one of the elements */
  impact: string
  variants: string[]
}

export interface Baseline {
  standard: string
  axe: string
  entries: BaselineEntry[]
}

/** What one scan found, written for `report.mjs`, which sums the scans up */
export interface ScanResult {
  page: string
  state: string
  variant: string
  /** The version of axe-core that scanned */
  engine: string
  /** Rules broken, by rule id */
  found: Record<string, { impact: string, nodes: number, help: string, targets: string[] }>
}

export const BASELINE_PATH = fileURLToPath(new URL('./baseline.json', import.meta.url))
export const RESULTS_DIR = fileURLToPath(new URL('../../../test-results/accessibility/', import.meta.url))

/** Set to take what the scans find as it is, for `report.mjs --write-baseline`, instead of holding it to the baseline */
export const RECORDING = process.env.A11Y_RECORD === '1'

export function readBaseline(): Baseline {
  return JSON.parse(readFileSync(BASELINE_PATH, 'utf-8')) as Baseline
}

const IMPACTS = ['minor', 'moderate', 'serious', 'critical']
const worse = (a: string, b: string) => IMPACTS.indexOf(a) >= IMPACTS.indexOf(b) ? a : b

/** Wait until nothing is moving: a menu fading in has half its final colours, which axe reads */
async function settle(page: Page, backend: Backend) {
  // not `networkidle`: a request that is refused (a tile, another host's image) is asked again
  await backend.idle()
  await page.waitForFunction(() => document.getAnimations().every(animation =>
    // a spinner never ends and is no reason to wait; nor is a toast's progress bar, which moves
    // for as long as the toast is shown and would have the scan wait until it is gone
    animation.playState !== 'running'
    || animation.effect?.getComputedTiming().iterations === Infinity
    || (animation.effect as KeyframeEffect | null)?.target?.closest('[data-slot="progress"]') != null,
  ))
}

/** Scan `page` as it is and return the rules it breaks, by rule id */
export async function scan(page: Page, backend: Backend, where: { page: string, state: string, variant: Variant }): Promise<ScanResult> {
  await settle(page, backend)
  const axe = await new AxeBuilder({ page })
    .withTags(WCAG_TAGS)
    .analyze()

  const found: ScanResult['found'] = {}
  for (const violation of axe.violations) {
    found[violation.id] = {
      impact: violation.nodes.reduce<string>((impact, node) => worse(impact, node.impact ?? 'minor'), violation.impact ?? 'minor'),
      nodes: violation.nodes.length,
      help: violation.help,
      targets: violation.nodes.slice(0, 5).map(node => node.target.join(' ')),
    }
  }
  const result: ScanResult = { ...where, variant: variantKey(where.variant), engine: axe.testEngine.version, found }

  mkdirSync(RESULTS_DIR, { recursive: true })
  const file = `${where.page}__${where.state}__${result.variant.replace('/', '-')}.json`
  writeFileSync(join(RESULTS_DIR, file), `${JSON.stringify(result, null, 2)}\n`)
  return result
}

/**
 * What the scan found that the baseline does not know, and what the baseline knows that the scan
 * did not find. Both are failures: the first is a regression, the second a fixed violation whose
 * entry has to go, so that the baseline only ever shrinks.
 */
export function compareToBaseline(result: ScanResult, baseline: Baseline) {
  const known = new Set(
    baseline.entries
      .filter(entry => entry.page === result.page && entry.state === result.state && entry.variants.includes(result.variant))
      .map(entry => entry.rule),
  )
  const found = Object.keys(result.found)
  return {
    fresh: found.filter(rule => !known.has(rule)).sort(),
    stale: [...known].filter(rule => !found.includes(rule)).sort(),
  }
}
