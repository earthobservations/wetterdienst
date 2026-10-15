// Sums up what the accessibility scans found (written by `scan.ts` to test-results/accessibility/).
//
//   node tests/e2e/accessibility/report.mjs                   markdown for the job summary, on stdout
//   node tests/e2e/accessibility/report.mjs --write-baseline  takes the scans as the new baseline
//
// The second form is `pnpm test:a11y:baseline`, which runs the scans first without holding them to
// the baseline. It writes what the scans found and nothing else: a baseline is the record of the app
// as it is, so it is regenerated, not edited, and it shrinks as violations are fixed.

import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const BASELINE = fileURLToPath(new URL('./baseline.json', import.meta.url))
const RESULTS = fileURLToPath(new URL('../../../test-results/accessibility/', import.meta.url))
const IMPACTS = ['minor', 'moderate', 'serious', 'critical']

/** @typedef {{ rule: string, page: string, state: string, impact: string, variants: string[] }} Entry */
/** @typedef {{ page: string, state: string, variant: string, found: Record<string, { impact: string, nodes: number, help: string }> }} Result */

/** @returns {Result[]} the scans of the last run */
function readResults() {
  if (!existsSync(RESULTS))
    return []
  return readdirSync(RESULTS)
    .filter(name => name.endsWith('.json'))
    .sort()
    .map(name => JSON.parse(readFileSync(join(RESULTS, name), 'utf-8')))
}

/**
 * One entry per rule, page and state, with the variants it is broken in.
 * @param {Result[]} results
 * @returns {Entry[]} the entries, in the order the baseline lists them
 */
function entriesOf(results) {
  /** @type {Map<string, Entry>} */
  const entries = new Map()
  for (const result of results) {
    for (const [rule, found] of Object.entries(result.found)) {
      const key = `${result.page}\0${result.state}\0${rule}`
      const entry = entries.get(key) ?? { rule, page: result.page, state: result.state, impact: found.impact, variants: [] }
      if (IMPACTS.indexOf(found.impact) > IMPACTS.indexOf(entry.impact))
        entry.impact = found.impact
      entry.variants.push(result.variant)
      entries.set(key, entry)
    }
  }
  return [...entries.values()]
    .map(entry => ({ ...entry, variants: entry.variants.sort() }))
    .sort((a, b) => a.rule.localeCompare(b.rule) || a.page.localeCompare(b.page) || a.state.localeCompare(b.state))
}

/** @param {Entry[]} entries */
function byRule(entries) {
  /** @type {Map<string, { impact: string, entries: number, pages: Set<string> }>} */
  const rules = new Map()
  for (const entry of entries) {
    const rule = rules.get(entry.rule) ?? { impact: entry.impact, entries: 0, pages: new Set() }
    rule.entries++
    rule.pages.add(entry.page)
    if (IMPACTS.indexOf(entry.impact) > IMPACTS.indexOf(rule.impact))
      rule.impact = entry.impact
    rules.set(entry.rule, rule)
  }
  return [...rules.entries()].sort((a, b) => b[1].entries - a[1].entries || a[0].localeCompare(b[0]))
}

/**
 * The baseline as a file: an entry to a line, so that a diff of it reads as the violations that came or went.
 * @param {{ standard: string, axe: string }} head the baseline's own fields
 * @param {Entry[]} entries the entries to write
 * @returns {string} the file's text
 */
function serialize(head, entries) {
  const rows = entries.map(entry => `    { "rule": ${JSON.stringify(entry.rule)}, "page": ${JSON.stringify(entry.page)}, "state": ${JSON.stringify(entry.state)}, "impact": ${JSON.stringify(entry.impact)}, "variants": [${entry.variants.map(variant => JSON.stringify(variant)).join(', ')}] }`)
  return [
    '{',
    `  "standard": ${JSON.stringify(head.standard)},`,
    `  "axe": ${JSON.stringify(head.axe)},`,
    rows.length ? `  "entries": [\n${rows.join(',\n')}\n  ]` : '  "entries": []',
    '}',
    '',
  ].join('\n')
}

const baseline = JSON.parse(readFileSync(BASELINE, 'utf-8'))

if (process.argv.includes('--write-baseline')) {
  const results = readResults()
  if (!results.length) {
    console.error('No scan results in test-results/accessibility/: run the scans first (pnpm test:a11y:baseline).')
    process.exit(1)
  }
  const entries = entriesOf(results)
  writeFileSync(BASELINE, serialize({ ...baseline, axe: results[0].engine ?? baseline.axe }, entries))
  console.warn(`Wrote ${entries.length} baseline entries from ${results.length} scans to ${BASELINE}.`)
  process.exit(0)
}

// the job summary: what is known, and what this run found against it
const results = readResults()
const known = baseline.entries
// by scan (page, state, variant) and rule: the unit the spec holds the baseline to
const knownKeys = new Set(known.flatMap(entry => entry.variants.map(variant => `${entry.page}\0${entry.state}\0${variant}\0${entry.rule}`)))
const foundKeys = new Set(results.flatMap(result => Object.keys(result.found).map(rule => `${result.page}\0${result.state}\0${result.variant}\0${rule}`)))
// a scan that did not run (its test failed first) says nothing of what it would have found
const ran = new Set(results.map(result => `${result.page}\0${result.state}\0${result.variant}`))
const scans = results.length
const pages = new Set(results.map(result => result.page)).size
const serious = known.filter(entry => ['serious', 'critical'].includes(entry.impact)).length

const lines = [
  `### Accessibility baseline (axe, ${baseline.standard})`,
  '',
  `**${known.length}** known violations (a rule broken on a page in a state) in the baseline, of which ${serious} serious or critical, across ${new Set(known.map(entry => entry.rule)).size} rules and ${new Set(known.map(entry => entry.page)).size} pages.`,
  '',
]
if (scans) {
  const fresh = [...foundKeys].filter(key => !knownKeys.has(key)).length
  const fixed = [...knownKeys].filter(key => ran.has(key.slice(0, key.lastIndexOf('\0'))) && !foundKeys.has(key)).length
  lines.push(
    `This run: ${scans} scans of ${pages} pages found ${foundKeys.size} violations (a rule broken in a scan); ${fresh} not in the baseline, ${fixed} in the baseline and no longer found.`,
    '',
  )
}
else {
  lines.push('This run wrote no scan results.', '')
}
if (known.length) {
  lines.push('| Rule | Impact | In the baseline | Pages |', '| --- | --- | ---: | ---: |')
  for (const [rule, summary] of byRule(known))
    lines.push(`| \`${rule}\` | ${summary.impact} | ${summary.entries} | ${summary.pages.size} |`)
  lines.push('')
}
process.stdout.write(`${lines.join('\n')}\n`)
