import type { QuestionId } from '~/utils/questions'
import { DateTime } from 'luxon'
import { lastBoxingDay } from '~/utils/answers'
import { withData } from '~/utils/format'

/** The questions as a reader sees them: in the language of the page, about the place chosen */
export function useQuestions() {
  const { t, locale, localeProperties } = useI18n()
  const { place } = usePlace()
  const language = computed(() => withData(localeProperties.value.language ?? locale.value, Intl.DateTimeFormat.supportedLocalesOf))

  /** A day as the language writes it: "26 December", "26. Dezember"; with the year where it is asked for */
  function dayText(day: string, withYear = false): string {
    return new Intl.DateTimeFormat(language.value, { day: 'numeric', month: 'long', year: withYear ? 'numeric' : undefined, timeZone: 'UTC' })
      .format(new Date(`${day}T00:00:00Z`))
  }

  function questionText(id: QuestionId, day: string = lastBoxingDay(DateTime.now())): string {
    switch (id) {
      case 'rain':
        return t('ask.q.rain', { place: place.value.name })
      case 'summer':
        return t('ask.q.summer')
      case 'wind':
        return t('ask.q.wind', { day: dayText(day) })
      case 'download':
        return t('ask.q.download')
    }
  }

  return { questionText, dayText, language }
}
