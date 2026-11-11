import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

// What the app's own source says in a language, and what it leaves to `t()` and to `Intl` (GH-2610). The catalogs are
// held by `i18n-parity.test.ts` and `i18n-quality.test.ts`; this one reads the code that uses them, for four ways
// text escapes a translation that can be found by pattern:
//
// - a colon written after a translated label: French sets a no-break space before it, so it is `common.colon`
// - a date or a time written out of its parts (`${dd}.${mm}.${yyyy}`), which is German order in every language
// - `Intl` or `toLocale*String` called with no language, which is the browser's
// - a static attribute of an element (`title`, `aria-label`, `placeholder`, ...) with a word in it, where `t()` belongs
//
// Text between the tags of an element is not checked.

const APP = join(__dirname, '..', '..')

/** `{{ t('x') }}:` and `{{ t('x', { n }) }}:` in a template, `${t('x')}:` and `${t('x')}</b>:` in a text built in code */
const COLON_AFTER_LABEL = /t\('[^']+'(?:,[^)]*)?\)\s*\}\}\s*:|t\('[^']+'(?:,[^)]*)?\)\}(?:<\/\w+>)?:/

/** Three parts of a date, in either order: `${dd}.${mm}.${yyyy}`, `${year}-${month}-${day}` */
const DATE_DMY = /\$\{(?:dd|day|d)\}[./-]\$\{(?:mm|month|m)\}[./-]\$\{(?:yyyy|year|y)\}/
const DATE_YMD = /\$\{(?:yyyy|year|y)\}[./-]\$\{(?:mm|month|m)\}[./-]\$\{(?:dd|day|d)\}/

/**
 * No argument, or `undefined`: the browser's language, which is not the page's. A luxon DateTime that was given its
 * language by `.setLocale(...)` writes in it with no argument, so that chain is not one.
 */
const TO_LOCALE_STRING = /(?<!\.setLocale\([^()]*\))\.toLocale(?:Date|Time)?String\((?:\s*undefined)?\s*[,)]/
const INTL_NO_LANGUAGE = /new Intl\.(?:DateTimeFormat|NumberFormat|RelativeTimeFormat|ListFormat|PluralRules|Collator)\((?:\s*undefined)?\s*[,)]/

/** A static attribute with a word in it (`title="Station"`), where the translated one is `:title="t('...')"` */
const STATIC_ATTRIBUTE = /\s(?:title|aria-label|aria-roledescription|aria-description|placeholder|alt|label)="[^"{]*[A-Za-zÄÖÜäöü]{3}/

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
    expect(found(COLON_AFTER_LABEL)).toEqual([])
  })

  it('writes no date out of its parts: the order and the separators are the language\'s', () => {
    expect(found(DATE_DMY)).toEqual([])
    expect(found(DATE_YMD)).toEqual([])
  })

  it('asks `Intl` and `toLocale*String` for a language, never the browser\'s', () => {
    expect(found(TO_LOCALE_STRING)).toEqual([])
    expect(found(INTL_NO_LANGUAGE)).toEqual([])
  })

  it('writes no static attribute with a word in it: `t()` does', () => {
    const allowed: Record<string, string> = {
      'placeholder="parameter_name"': 'the name of a parameter as the API takes it, in no language',
      'alt="Wetterdienst"': 'the name of the project',
    }
    expect(found(STATIC_ATTRIBUTE, allowed)).toEqual([])
  })
})

describe('the patterns', () => {
  // `§{` stands for the `${` of a template literal, which a string of this file may not hold
  const code = (line: string) => line.replaceAll('§{', '$' + '{')

  it.each([
    '{{ t(\'x\') }}: {{ y }}',
    '{{ t(\'x\') }}:</label>',
    '<span>{{ t(\'x\') }}:</span>',
    '<strong>{{ t(\'x\') }}:</strong>',
    '{{ t(\'x\') }}:<br>',
    '{{ t(\'x\', { n: 2 }) }}:',
    '`<b>§{t(\'x\')}</b>: §{y}`',
    '`§{t(\'x\')}: §{y}`',
  ])('finds a colon after a label in %s', (line) => {
    expect(COLON_AFTER_LABEL.test(code(line))).toBe(true)
  })

  it.each([
    '{{ t(\'x\') }}{{ t(\'common.colon\') }} {{ y }}',
    '`§{t(\'x\')}§{t(\'common.colon\')} §{y}`',
    '<span :class="a ? \'b\' : \'c\'">{{ t(\'x\') }}</span>',
  ])('leaves %s alone', (line) => {
    expect(COLON_AFTER_LABEL.test(code(line))).toBe(false)
  })

  it('flags a date or time string with no language, and leaves a luxon DateTime that was given one', () => {
    expect(TO_LOCALE_STRING.test('date.toLocaleString()')).toBe(true)
    expect(TO_LOCALE_STRING.test('date.toLocaleDateString(undefined, options)')).toBe(true)
    expect(TO_LOCALE_STRING.test('number.toLocaleString(locale)')).toBe(false)
    expect(TO_LOCALE_STRING.test('DateTime.fromMillis(ms).setLocale(language.value).toLocaleString()')).toBe(false)
    expect(TO_LOCALE_STRING.test('DateTime.fromMillis(ms).setLocale(language.value).toLocaleString(DateTime.DATETIME_SHORT)')).toBe(false)
  })
})
