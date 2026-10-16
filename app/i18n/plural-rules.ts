// Which plural form of a message a count takes (GH-2968). vue-i18n splits a message at `|` into its
// forms and asks the rule of the active language which one a count wants. Its own rule knows two
// forms and takes the first for 1 only, which is wrong for Polish and Czech (one, few, other: three
// forms) and for French (0 is singular). Every language has a rule here, rather than falling back on
// the default, so that `tests/unit/plural-rules.test.ts` can hold each of them to the CLDR plural
// categories of its language.
//
// A message is written as `one | other` for the languages with two forms, and as `one | few | other`
// for pl and cs. A rule never answers a form the message does not have, whatever the message it is
// asked about. vue-i18n takes the count from the named `{count}`, not from the argument that follows.

type PluralRule = (choice: number, choicesLength: number) => number

/** The first form for 1, the second for every other count, 0 included: de, en, es, it, nl, da, lb, de-hh. */
const oneOther: PluralRule = (choice, length) => Math.min(choice === 1 ? 0 : 1, length - 1)

/** The first form for 0 and 1, the second for the rest: French has "0 valeur". */
const zeroOneOther: PluralRule = (choice, length) => Math.min(choice === 0 || choice === 1 ? 0 : 1, length - 1)

/** One (1), few (2 to 4), other (everything else, 0 included): Czech. */
const oneFewOther: PluralRule = (choice, length) =>
  Math.min(choice === 1 ? 0 : choice >= 2 && choice <= 4 ? 1 : 2, length - 1)

/** One (1), few (2 to 4 but not 12 to 14, as in 22 to 24, 32 to 34, ...), other (the rest): Polish. */
const polish: PluralRule = (choice, length) => {
  const tens = choice % 100
  const ones = choice % 10
  const few = ones >= 2 && ones <= 4 && !(tens >= 12 && tens <= 14)
  return Math.min(choice === 1 ? 0 : few ? 1 : 2, length - 1)
}

export const pluralRules: Record<string, PluralRule> = {
  'cs': oneFewOther,
  'da': oneOther,
  'de': oneOther,
  'de-hh': oneOther,
  'en': oneOther,
  'es': oneOther,
  'fr': zeroOneOther,
  'it': oneOther,
  'lb': oneOther,
  'nl': oneOther,
  'pl': polish,
}

/** The number of forms a language writes a plural message in. */
export const pluralForms: Record<string, number> = Object.fromEntries(
  Object.keys(pluralRules).map(locale => [locale, ['cs', 'pl'].includes(locale) ? 3 : 2]),
)
