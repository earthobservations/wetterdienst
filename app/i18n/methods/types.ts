import type { WorkId } from '../../app/utils/ask/works'

/** The words of one rule of a chip's method (`Rule` in `utils/ask/chip.ts`) */
export interface RuleText {
  /** What the chip does, with its numbers (`{from}` is the rule's `values.from`): how the source is applied */
  text: string
  /** What the cited work says that the rule uses, in plain words; where the rule cites none, absent */
  says?: string
  /** Why wetterdienst chose it, for a rule that is its own; absent for one that has a source */
  reason?: string
}

/** The words of one chip's method: the inline disclosure under its answer and its section on the page of the methods */
export interface ChipMethod {
  /** The name of the method as its section is headed */
  title: string
  /** One sentence under the title that says what the chip answers and from what */
  summary: string
  /** What the data is, in plain words (the provider's own dataset, the parameters, the stretch of time) */
  data: string
  /** The steps of the method, by id (`ChipExplanation.steps`) */
  steps: Record<string, string>
  /** The formulas, by id (`ChipExplanation.formulas`); symbols and words, not a picture */
  formulas: Record<string, string>
  /** The rules, by id (`Rule.id`) */
  rules: Record<string, RuleText>
  /** The limits of the answer, by id (`ChipExplanation.limits`) */
  limits: Record<string, string>
  /** The lines of "the numbers used" of an answer, by id (`NumberLine.id`), with `{name}` for the answer's own numbers */
  numbers: Record<string, string>
  /**
   * The words of a choice, in the language of the texts, for a line whose parameter holds the choice's id: `terms.season.winter` is
   * what `{season}` says where the answer is about the winter. Absent for a chip with no such words.
   */
  terms?: Record<string, Record<string, string>>
}

/** What a work is, who issues it and why it counts, in plain words; the formal citation is in `works.ts` and stays in the work's own language */
export interface WorkText {
  plain: string
}

/** The texts of the methods in one language: a method for each chip of the registry, and an entry for each work */
export interface MethodTexts {
  chips: Record<string, ChipMethod>
  works: Record<WorkId, WorkText>
}
