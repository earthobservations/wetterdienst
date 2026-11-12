import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import phosphor from '@iconify-json/ph/icons.json'
import simpleIcons from '@iconify-json/simple-icons/icons.json'
import { describe, expect, it } from 'vitest'

// The app's icons are Phosphor (and three brand marks of Simple Icons); Lucide and Heroicons are not in the
// bundle, so a name of theirs, such as one brought in by a merge of code written before, draws nothing and
// raises no error (GH-3518).

const APP = join(__dirname, '..', '..', 'app')

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory())
      return sources(path)
    return /\.(?:vue|ts)$/.test(name) ? [path] : []
  })
}

const NAMES = new Map<string, string>()
for (const file of sources(APP)) {
  for (const match of readFileSync(file, 'utf-8').matchAll(/['"`](i-(?:ph|simple-icons|lucide|heroicons)-[a-z0-9-]+)['"`]/g))
    NAMES.set(match[1]!, file.slice(APP.length + 1))
}

describe('the icon names of the app', () => {
  it('finds the icons it is held to', () => {
    expect(NAMES.size).toBeGreaterThan(50)
  })

  it.each([...NAMES])('%s (%s) is an icon of the bundle', (name) => {
    const [, set, icon] = /^i-(ph|simple-icons|lucide|heroicons)-(.+)$/.exec(name)!
    const known = set === 'ph' ? phosphor.icons : set === 'simple-icons' ? simpleIcons.icons : {}
    expect(Object.keys(known), `${set} is not a set of the bundle, or has no ${icon}`).toContain(icon)
  })
})
