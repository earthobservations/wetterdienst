// The questions the home page offers as suggestions (components/AskTheWeather.vue): the ones people bring to a
// weather service, each answered from data the app fetches (utils/answers.ts) and leading into the tool that holds
// that data. `tool` is the tool the answer opens (utils/sections.ts); the question itself carries no tile, because
// the four tiles are the tools' marks and nothing else (GH-3518): the tile appears on the link that leads into the tool.
export const QUESTIONS = [
  { id: 'rain', icon: 'i-ph-cloud-rain', tool: 'forecast' },
  { id: 'summer', icon: 'i-ph-thermometer-hot', tool: 'explorer' },
  { id: 'wind', icon: 'i-ph-wind', tool: 'explorer' },
  { id: 'download', icon: 'i-ph-download-simple', tool: 'explorer' },
] as const

export type QuestionId = typeof QUESTIONS[number]['id']

export function isQuestion(value: unknown): value is QuestionId {
  return QUESTIONS.some(question => question.id === value)
}
