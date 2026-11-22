import type { Chip } from './chip'
import { day } from './chips/day'
import { download } from './chips/download'
import { monthrain } from './chips/monthrain'
import { nearby } from './chips/nearby'
import { rain } from './chips/rain'
import { season } from './chips/season'

// The chips of "Ask the weather" (components/AskTheWeather.vue), in the order the home page offers them: the questions
// people bring to a weather service, each one definition (`chip.ts`) answered from data the app fetches and leading into
// the tool that holds that data. The question itself carries no tile, because the four tiles are the tools' marks and
// nothing else (GH-3518): the tile appears on the link that leads into the tool.
//
// A new chip is registered here, and nowhere else in the code: `README.md` next to this file.
export const CHIPS = [rain, season, day, monthrain, nearby, download] as const

export type ChipId = typeof CHIPS[number]['id']

/** The chip a link or a press names, or null: by its id, or by a name it had before (`?ask=summer` is the season chip, which asks about the summer until the link says another) */
export function chipOf(id: unknown): Chip | null {
  return CHIPS.find(chip => chip.id === id || (typeof id === 'string' && (chip.aliases ?? []).includes(id))) ?? null
}

export function isChip(value: unknown): value is ChipId {
  return chipOf(value) !== null
}

/** The id of the chip a link names (an old name of it too), or null: `summer` is `season` */
export function chipIdOf(value: unknown): ChipId | null {
  return (chipOf(value)?.id as ChipId | undefined) ?? null
}
