import { Settings } from 'luxon'

// Chrome ships no data for Luxembourgish: `new Intl.DateTimeFormat('lb')` answers in the system's language (here
// `en-US`: collator `en-US`, numbers "1,234.5", dates "10/15/2026") and `supportedLocalesOf(['lb'])` is empty. Node
// ships the data, so a test that only filters `supportedLocalesOf` still gets Luxembourgish, which is German's
// order and separators, from a call that passes the bare code: the same text as the stand-in's, and no failure.
//
// This stands in for Chrome: the constructors of `Intl.DateTimeFormat`, `NumberFormat` and `Collator` write `en-US`
// for any `lb` language, as Chrome does, and say so in `passed`, the languages they were handed. A test then asserts
// on text that differs (German's against English's), or that no `lb` was passed.

const NO_DATA = /^lb(?:-|$)/i
const CONSTRUCTORS = ['DateTimeFormat', 'NumberFormat', 'Collator'] as const

export interface ChromeWithoutLuxembourgish {
  /** Every language the three constructors were handed, as the caller wrote it */
  passed: string[]
  /** Puts Node's constructors back; the test's `afterEach` calls it */
  restore: () => void
}

const written = (language: unknown): string[] => [language].flat().filter((entry): entry is string => typeof entry === 'string')

export function chromeWithoutLuxembourgish(): ChromeWithoutLuxembourgish {
  const passed: string[] = []
  const originals = Object.fromEntries(CONSTRUCTORS.map(name => [name, Intl[name]]))

  for (const name of CONSTRUCTORS) {
    const original = Intl[name] as any
    const stand = (language: unknown) => written(language).some(entry => NO_DATA.test(entry)) ? 'en-US' : language
    const construct = (target: any, args: unknown[], newTarget?: any): object => {
      passed.push(...written(args[0]))
      return Reflect.construct(target, [stand(args[0]), ...args.slice(1)], newTarget ?? target)
    }
    const chrome = new Proxy(original, {
      construct,
      apply: (target, _this, args) => construct(target, args),
      get: (target, key, receiver) => key === 'supportedLocalesOf'
        ? (languages: string | string[], options?: object) => target.supportedLocalesOf(written(languages).filter(entry => !NO_DATA.test(entry)), options)
        : Reflect.get(target, key, receiver),
    })
    Object.defineProperty(Intl, name, { value: chrome, configurable: true, writable: true })
  }
  // luxon keeps the formatters it made by language: one made while this stood in must not outlive it, nor one made before it stand in for it
  Settings.resetCaches()

  return {
    passed,
    restore: () => {
      for (const name of CONSTRUCTORS)
        Object.defineProperty(Intl, name, { value: originals[name], configurable: true, writable: true })
      Settings.resetCaches()
    },
  }
}
