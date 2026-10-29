import type { TileTone } from '~/components/AskTile.vue'

// The questions the home page opens on: the ones people bring to a weather service, each answered from data the
// app fetches (utils/answers.ts) and leading into the tool that holds that data. Shared with the command palette.
export const QUESTIONS = [
  { id: 'rain', icon: 'i-lucide-cloud-rain', tone: 'rain' },
  { id: 'summer', icon: 'i-lucide-thermometer-sun', tone: 'warmth' },
  { id: 'wind', icon: 'i-lucide-wind', tone: 'wind' },
  { id: 'download', icon: 'i-lucide-download', tone: 'sun' },
] as const satisfies ReadonlyArray<{ id: string, icon: string, tone: TileTone }>

export type QuestionId = typeof QUESTIONS[number]['id']

export function isQuestion(value: unknown): value is QuestionId {
  return QUESTIONS.some(question => question.id === value)
}
