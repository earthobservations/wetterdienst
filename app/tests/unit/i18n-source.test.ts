import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

// What the app's own source says in a language, and what it leaves to `t()` and to `Intl` (GH-2610). The catalogs are
// held by `i18n-parity.test.ts` and `i18n-quality.test.ts`; this one reads the code that uses them, for the three
// ways text escapes a translation that can be found by pattern:
//
// - a colon written after a translated label: French sets a no-break space before it, so it is `common.colon`
// - a date or a time written out of its parts (`${dd}.${mm}.${yyyy}`), which is German order in every language, and
//   `Intl` or `toLocale*String` called with no language, which is the browser's
// - a text, a title or a label of an element written in the template in a language, where `t()` belongs

const APP = join(__dirname, '..', '..')

function sources(directory: string): string[] {
  return readdirSync(join(APP, directory), { recursive: true, withFileTypes: true })
    .filter(entry => entry.isFile() && /\.(?:vue|ts)$/.test(entry.name))
    .map(entry => join(entry.parentPath, entry.name))
}

const files = ['app', 'shared'].flatMap(sources).map(path => ({ name: relative(APP, path), text: readFileSync(path, 'utf8') }))

/** Every line of the sources that matches `pattern`, as `file:line: text`, less those that hold a text of `allowed` (with its reason). */
function found(pattern: RegExp, allowed: Record<string, string> = {}): string[] {
  const texts = Object.keys(allowed)
  return files.flatMap(file => file.text.split('\n').flatMap((line, index) =>
    pattern.test(line) && !texts.some(text => line.includes(text)) ? [`${file.name}:${index + 1}: ${line.trim().slice(0, 120)}`] : []))
}

describe('what the source leaves to the language', () => {
  it('reads the sources', () => {
    expect(files.length).toBeGreaterThan(50)
  })

  it('writes no colon after a translated label: it is `common.colon`, which French sets with a no-break space', () => {
    // `{{ t('x') }}:` in a template, `${t('x')}:` and `${t('x')}</b>:` in a text built in code
    expect(found(/t\('[^']+'\)\s*\}\}\s*:(?:\s|$)|t\('[^']+'\)\}(?:<\/\w+>)?:/)).toEqual([])
  })

  it('writes no date out of its parts: the order and the separators are the language\'s', () => {
    // `${dd}.${mm}.${yyyy}`, `${day}/${month}/${year}`: three parts of a date
    expect(found(/\$\{(?:dd|day|d)\}[./-]\$\{(?:mm|month|m)\}[./-]\$\{(?:yyyy|year|y)\}/)).toEqual([])
    expect(found(/\$\{(?:yyyy|year|y)\}[./-]\$\{(?:mm|month|m)\}[./-]\$\{(?:dd|day|d)\}/)).toEqual([])
  })

  it('asks `Intl` and `toLocale*String` for a language, never the browser\'s', () => {
    // no argument, or `undefined`: the browser's language, which is not the page's
    expect(found(/\.toLocale(?:Date|Time)?String\((?:\s*undefined)?\s*[,)]/)).toEqual([])
    expect(found(/new Intl\.(?:DateTimeFormat|NumberFormat|RelativeTimeFormat|ListFormat|PluralRules|Collator)\((?:\s*undefined)?\s*[,)]/)).toEqual([])
  })

  it('writes no text, title or label of an element in the template: `t()` does', () => {
    // a static attribute with a word in it (`title="Station"`), where the translated one is `:title="t('...')"`
    const allowed: Record<string, string> = {
      'placeholder="parameter_name"': 'the name of a parameter as the API takes it, in no language',
      'alt="Wetterdienst"': 'the name of the project',
    }
    expect(found(/\s(?:title|aria-label|aria-roledescription|aria-description|placeholder|alt|label)="[^"{]*[A-Za-zÄÖÜäöü]{3}/, allowed)).toEqual([])
  })
})
