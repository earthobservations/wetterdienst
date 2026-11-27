/**
 * The states and pollen regions of DWD's forecast in the reader's language (GH-4508). DWD writes them in German; the tables of each
 * language are in `i18n/pollen-names.ts` (what is translated and what is not is written there). This file is how a name is read
 * from them, and it only changes what is shown: matching, the storage and the requests keep DWD's ids and German names
 * (`utils/uv-pollen.ts`), and a name that no table has (a locale without one, a state or a region DWD adds) is DWD's own, as it was.
 */
import type { PollenNames } from '../../i18n/pollen-names'
import { POLLEN_NAMES } from '../../i18n/pollen-names'

/** `{name}` in a template: a word of the language's table, or a state of it by its German name */
const SLOT = /\{([^{}]+)\}/g

function upperFirst(text: string, locale: string): string {
  const first = text.charAt(0)
  return first ? first.toLocaleUpperCase(locale) + text.slice(1) : text
}

/** The table of a locale, or none: a locale that has none (German, Low German, Luxembourgish) shows DWD's names */
function tableOf(locale: string): PollenNames | undefined {
  return Object.hasOwn(POLLEN_NAMES, locale) ? POLLEN_NAMES[locale] : undefined
}

/** Whether a language has names of its own for the states and regions: where it has none, the panel shows DWD's, and its name is no second one to show */
export function hasPollenNames(locale: string): boolean {
  return tableOf(locale) !== undefined
}

/**
 * The name of a state in a language: `Sachsen` is `Saxony`, `Saxe`, `Sassonia` ... Its German name (as the `region` column of DWD's stations
 * writes it) where the language has no table or the state is none of the sixteen.
 */
export function stateName(state: string, locale: string): string {
  const table = tableOf(locale)
  const key = state.trim()
  return table && Object.hasOwn(table.states, key) ? table.states[key as keyof PollenNames['states']] : state
}

/**
 * The name of a part-region in a language, from the name DWD writes for the part (`Tiefland Sachsen`, `Östl. Niedersachsen`, the
 * region's own where it has no part): the generic words are the language's, the place names DWD's. DWD's own name where the language has
 * no table, or the region is none of the 27 (a region DWD adds), so that the chip is never empty.
 */
export function regionName(label: string, locale: string): string {
  const table = tableOf(locale)
  const key = label.trim()
  if (!table || !Object.hasOwn(table.regions, key))
    return label
  const template = table.regions[key as keyof PollenNames['regions']]
  const name = template.replace(SLOT, (slot, name: string) => {
    if (Object.hasOwn(table.words, name))
      return table.words[name as keyof PollenNames['words']]
    if (Object.hasOwn(table.states, name))
      return table.states[name as keyof PollenNames['states']]
    // a slot no table fills is a mistake of the table, which `tests/unit/pollen-names.test.ts` finds; the chip shows DWD's name
    return slot
  })
  return /[{}]/.test(name) ? label : upperFirst(name, locale)
}
