import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

// The styles of a component are global in this app (`<style>` with no `scoped`), so a class that two files define is one rule on both: the page's
// `.kostra-stage` (the map's box, with negative margins) once took the chart's own box of the same name (GH-4500). A class a file of the
// Heavy-rainfall tool defines is defined by that file alone, and by none of the others of the app.

const APP = join(__dirname, '..', '..', 'app')

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    return entry.isDirectory() ? files(path) : /\.(?:vue|css)$/.test(entry.name) ? [path] : []
  })
}

/** The classes a file defines in a selector: the style blocks of a component, the whole of a stylesheet */
function classesDefinedIn(path: string): Set<string> {
  const source = readFileSync(path, 'utf8')
  const css = path.endsWith('.css') ? source : [...source.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(match => match[1]).join('\n')
  // what is before a `{` is a selector (a declaration has no `{`); comments are not
  const selectors = [...css.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{/g)].map(match => match[1]!)
  return new Set(selectors.flatMap(selector => [...selector.matchAll(/\.(-?[_a-z][\w-]*)/gi)].map(match => match[1]!)))
}

const ALL = files(APP)
const KOSTRA_FILES = ALL.filter(path => /(?:Kostra\w*\.vue|pages\/kostra\.vue)$/.test(path))
const DEFINED = new Map(ALL.map(path => [path, classesDefinedIn(path)]))

describe('the classes of the heavy-rainfall tool', () => {
  it('are read from the page and its two components', () => {
    expect(KOSTRA_FILES.map(path => relative(APP, path)).sort()).toEqual(['components/KostraChart.vue', 'components/KostraTable.vue', 'pages/kostra.vue'])
    for (const path of KOSTRA_FILES)
      expect(DEFINED.get(path)!.size, relative(APP, path)).toBeGreaterThan(3)
  })

  it('are each defined by one file of the app alone', () => {
    const shared: string[] = []
    for (const path of KOSTRA_FILES) {
      for (const name of DEFINED.get(path)!) {
        const others = ALL.filter(other => other !== path && DEFINED.get(other)!.has(name))
        if (others.length)
          shared.push(`.${name}: ${relative(APP, path)} and ${others.map(other => relative(APP, other)).join(', ')}`)
      }
    }
    expect(shared).toEqual([])
  })

  it('are all named for the tool, so that no rule of another part of the app is the same by chance', () => {
    const outside: string[] = []
    for (const path of KOSTRA_FILES) {
      for (const name of DEFINED.get(path)!) {
        // the library's and the browser's own classes a rule reaches into, and the app's shared ones (`sr-only`, `app-chart`) are not defined here
        if (!name.startsWith('kostra-'))
          outside.push(`${relative(APP, path)}: .${name}`)
      }
    }
    expect(outside).toEqual([])
  })
})
