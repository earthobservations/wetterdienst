import type { Chip } from './chip'
import { download } from './chips/download'
import { rain } from './chips/rain'
import { summer } from './chips/summer'
import { wind } from './chips/wind'

// The chips of "Ask the weather" (components/AskTheWeather.vue), in the order the home page offers them: the questions
// people bring to a weather service, each one definition (`chip.ts`) answered from data the app fetches and leading into
// the tool that holds that data. The question itself carries no tile, because the four tiles are the tools' marks and
// nothing else (GH-3518): the tile appears on the link that leads into the tool.
//
// A new chip is registered here, and nowhere else in the code: `README.md` next to this file.
export const CHIPS = [rain, summer, wind, download] as const

export type ChipId = typeof CHIPS[number]['id']

/** The chip a link or a press names, or null */
export function chipOf(id: unknown): Chip | null {
  return CHIPS.find(chip => chip.id === id) ?? null
}

export function isChip(value: unknown): value is ChipId {
  return chipOf(value) !== null
}
