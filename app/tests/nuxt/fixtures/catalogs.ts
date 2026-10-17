import { readFileSync } from 'node:fs'
import process from 'node:process'

// The locales of the app besides English (nuxt.config.ts)
export const OTHER_LANGUAGES = ['de', 'de-hh', 'fr', 'es', 'it', 'nl', 'pl', 'cs', 'da', 'lb']

/**
 * The messages of a catalog, as the file has them: a module that imports the catalog gets it compiled
 * by the i18n module, with the text no longer in it.
 */
export function messagesOf(code: string, section: string): Record<string, string> {
  return JSON.parse(readFileSync(`${process.cwd()}/i18n/locales/${code}.json`, 'utf-8'))[section]
}

/** A message with its named values filled in, as vue-i18n does for `{status}`. */
export function fill(message: string, named: Record<string, string>): string {
  return message.replace(/\{(\w+)\}/g, (_, name) => named[name]!)
}
