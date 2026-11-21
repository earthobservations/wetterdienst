import type { Chip, ChipEnv, Choices, Say } from '~/utils/ask/chip'
import { DateTime } from 'luxon'
import { formatNumber } from '~/utils/format'
import { unitText } from '~/utils/units'

/**
 * What the chips of "Ask the weather" may use of the page (`ChipEnv`): the language, the place and the formats. The
 * questions as a reader sees them, in the language of the page, about the place chosen.
 */
export function useQuestions() {
  const { t } = useI18n()
  const { place } = usePlace()
  const formatLanguage = useFormatLanguage()

  /** A day as the language writes it: "26 December", "26. Dezember"; with the year where it is asked for */
  function dayText(day: string, withYear = false): string {
    return new Intl.DateTimeFormat(formatLanguage.value, { day: 'numeric', month: 'long', year: withYear ? 'numeric' : undefined, timeZone: 'UTC' })
      .format(new Date(`${day}T00:00:00Z`))
  }

  const env: ChipEnv = {
    t: t as Say,
    // read at each use, so that a computed that uses it follows the place
    get place() {
      return place.value
    },
    number: (value, digits = 1) => formatNumber(value, formatLanguage.value, digits),
    percent: value => new Intl.NumberFormat(formatLanguage.value, { style: 'percent', maximumFractionDigits: 0 }).format(value),
    unitText,
    dayText,
    now: () => DateTime.now(),
  }

  /** The question of a chip, as its button and its heading say it, with the values of its choices */
  function questionText(chip: Chip, choices: Choices): string {
    return chip.question(env, choices)
  }

  return { env, questionText, dayText }
}
