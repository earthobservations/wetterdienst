import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

// What the app's own source says in a language, and what it leaves to `t()` and to `Intl` (GH-2610). The catalogs are
// held by `i18n-parity.test.ts` and `i18n-quality.test.ts`; this one reads the code that uses them, for six ways
// text escapes a translation that can be found by pattern:
//
// - a colon written after a translated label: French sets a no-break space before it, so it is `common.colon`
// - a date or a time written out of its parts (`${dd}.${mm}.${yyyy}`), which is German order in every language
// - a time of day written out of its parts (`HH:mm`), which is German's colon in every language (Danish writes `04.00`)
// - `Intl` or `toLocale*String` called with no language, which is the browser's
// - `Intl` or `toLocale*String` called with the app's bare locale code (`lb`, `de-hh`), which a browser may have no
//   data for (Chrome has none for Luxembourgish and writes the system's language): `useFormatLanguage()` or `withData`
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

/**
 * The app's locale code (`locale`, `locale.value`), a language tag read from the locale's properties (`language`,
 * `language.value`, `localeProperties.value.language`) or a variable of the page by either name, as the language of
 * `Intl`, of `toLocale*String` or of a luxon DateTime: none of them is a language the browser has data for (Chrome has
 * none for `lb`). What is handed over is `useFormatLanguage()`'s answer, named `formatLanguage`, or `withData(...)`;
 * the helpers of `utils/format.ts` take a code or a tag and map it themselves.
 */
const UNMAPPED = String.raw`(?:locale|language)(?:\.value)?|localeProperties(?:\.value)?\.language`
const INTL_BARE_LOCALE = new RegExp(String.raw`new Intl\.\w+\(\s*(?:${UNMAPPED})\s*[,)]`)
const TO_LOCALE_BARE = new RegExp(String.raw`\.toLocale(?:Date|Time)?String\(\s*(?:${UNMAPPED})\s*[,)]`)
const SET_LOCALE_BARE = new RegExp(String.raw`\.setLocale\(\s*(?:${UNMAPPED})\s*\)`)
const BARE_LOCALE_PATTERNS = [INTL_BARE_LOCALE, TO_LOCALE_BARE, SET_LOCALE_BARE]

/**
 * The hour and the minute of a time written out: `${hh}:${mm}`, `toFormat('HH:mm')` or the 12-hour `'hh:mm a'`,
 * `${d.getUTCHours()}:${d.getUTCMinutes()}`, `toISO().slice(11, 16)`
 */
const TIME_PARTS = /\$\{(?:hh|hour|hours|h)\}[:.]\$\{(?:mm|minute|minutes|min|m)\}/
const TIME_FORMAT = /\.toFormat\(\s*['"`][^'"`]*[Hh][:.]mm?/
const TIME_FROM_DATE = /\$\{[^}]*Hours\(\)[^}]*\}[:.]\$\{[^}]*Minutes\(\)/
const TIME_FROM_ISO = /toISO(?:String)?\([^)]*\)\??\.(?:slice|substring|substr)\(\s*11\s*,/
const TIME_PATTERNS = [TIME_PARTS, TIME_FORMAT, TIME_FROM_DATE, TIME_FROM_ISO]

/** A static attribute with a word in it (`title="Station"`), where the translated one is `:title="t('...')"` */
const STATIC_ATTRIBUTE = /\s(?:title|aria-label|aria-roledescription|aria-description|placeholder|alt|label)="[^"{]*[A-Za-zÄÖÜäöü]{3}/

function sources(directory: string): string[] {
  return readdirSync(join(APP, directory), { recursive: true, withFileTypes: true })
    .filter(entry => entry.isFile() && /\.(?:vue|ts)$/.test(entry.name))
    .map(entry => join(entry.parentPath, entry.name))
}

// `§{` stands for the `${` of a template literal, which a string of this file may not hold
const code = (line: string) => line.replaceAll('§{', '$' + '{')

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

  it('gives `Intl` and `toLocale*String` a language the browser has data for, never the app\'s bare locale code', () => {
    for (const pattern of BARE_LOCALE_PATTERNS)
      expect(found(pattern)).toEqual([])
  })

  it('gives every number field the language tag: Nuxt UI hands it the bare locale code, which Chrome may have no data for', () => {
    // each `<UInputNumber ... />` up to its closing `/>`, which no attribute holds
    const missing = files.flatMap(file => [...file.text.matchAll(/<UInputNumber\b[\s\S]*?\/>/g)]
      .filter(([tag]) => !/\s:locale="formatLanguage"/.test(tag))
      .map(([tag]) => `${file.name}:${file.text.slice(0, file.text.indexOf(tag)).split('\n').length}: ${tag.split('\n')[1]?.trim()}`))
    expect(missing).toEqual([])
  })

  it('writes no time of day out of its parts: the separator is the language\'s', () => {
    // the offset to UTC ("UTC+01:00") is ISO 8601 notation, with a colon in every language
    const allowed: Record<string, string> = { [code('(UTC§{sign}§{h}:§{m})')]: 'a UTC offset, ISO 8601 notation' }
    for (const pattern of TIME_PATTERNS)
      expect(found(pattern, allowed)).toEqual([])
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

  it.each([
    'new Intl.NumberFormat(locale.value, { style: \'percent\' })',
    'new Intl.Collator(locale)',
    'new Intl.DateTimeFormat(locale.value)',
    'new Intl.Collator(language.value, { numeric: true })',
    'new Intl.NumberFormat(localeProperties.value.language)',
    'count.toLocaleString(language)',
    'DateTime.now().setLocale(language.value)',
    'DateTime.now().setLocale(localeProperties.value.language)',
    'count.toLocaleString(locale.value)',
    'count.toLocaleString(locale, options)',
    'date.toLocaleDateString(locale)',
    'DateTime.now().setLocale(locale.value)',
  ])('finds the bare locale code in %s', (line) => {
    expect(BARE_LOCALE_PATTERNS.some(pattern => pattern.test(line))).toBe(true)
  })

  it.each([
    'new Intl.Collator(formatLanguage.value, { numeric: true })',
    'new Intl.NumberFormat(withData(locale, Intl.NumberFormat.supportedLocalesOf), options)',
    'count.toLocaleString(formatLanguage.value)',
    'DateTime.now().setLocale(formatLanguage.value)',
    'const { t, locale, setLocale } = useI18n()',
    'void setLocale(language.value as typeof locale.value)',
  ])('leaves %s alone (bare locale code)', (line) => {
    expect(BARE_LOCALE_PATTERNS.some(pattern => pattern.test(line))).toBe(false)
  })

  it.each([
    'localDt.toFormat(\'HH:mm\')',
    'localDt.toFormat("H:mm")',
    'localDt.toFormat(\'HH.mm\')',
    '`§{hh}:§{mm}`',
    '`§{hour}.§{minute}`',
    'localDt.toFormat(\'hh:mm a\')',
    'DateTime.fromMillis(t).toISO().slice(11, 16)',
    'new Date(t).toISOString().substring(11, 16)',
    '`§{String(d.getUTCHours()).padStart(2, \'0\')}:§{String(d.getUTCMinutes()).padStart(2, \'0\')}`',
  ])('finds a time written out of its parts in %s', (line) => {
    expect(TIME_PATTERNS.some(pattern => pattern.test(code(line)))).toBe(true)
  })

  it.each([
    'label: hour.toFormat(\'HH\')',
    'label: DateTime.fromISO(key).toFormat(\'d\')',
    'formatHour(t, language.value, stationTZ)',
    'date.toFormat(\'ccc\')',
  ])('leaves %s alone (time of day)', (line) => {
    expect(TIME_PATTERNS.some(pattern => pattern.test(code(line)))).toBe(false)
  })
})
