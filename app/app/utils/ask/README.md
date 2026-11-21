# Adding a chip to "Ask the weather"

A chip is a question of the home page ("Will it rain in Kiel tomorrow?") with its answer. It is **one definition
object**: `components/AskTheWeather.vue` and `components/AnswerPanel.vue` render whatever `registry.ts` holds and have no
code of their own for any chip (GH-3764).

Adding a chip is three things:

1. one file, `chips/<id>.ts`, that calls `defineChip({...})`;
2. its translations, in all eleven locales (`i18n/locales/*.json`);
3. one line in `registry.ts`: `CHIPS = [rain, summer, wind, download, <yours>]`. The order is the order of the buttons.

`tests/unit/ask-chips.test.ts` then holds the new chip to the rest: it must be in the registry, lead into a tool of
the app, and have every key it uses in all eleven locales. Add the test of your answer function to
`tests/unit/answers.test.ts` (or a file of its own), and the chip to the page test
`tests/nuxt/components/AskTheWeather.test.ts`.

## What a definition holds

Copy `chips/summer.ts` (no choices) or `chips/wind.ts` (a choice) and change it. The types, with a comment on every
field, are in `chip.ts`.

| Field | What it is |
| --- | --- |
| `id` | The name in the link (`?ask=<id>`) and in the test id of the button (`question-<id>`). |
| `icon`, `tool` | The icon of the button, and the tool (a key of `TOOLS`, `utils/sections.ts`) the answer leads into. The button itself carries no tile: the tile is on the link into the tool. |
| `quantity` | The quantity whose unit the settings choose (`precipitation`, `temperature`, `speed`, ...). The panel asks again when the reader changes that unit. |
| `choices` | What the reader can choose about the question, with the name each has in the link. Today a day (`kind: 'date'`, `&day=`). The panel draws a labelled control for each; a choice of another kind adds its kind to `chip.ts` and its control to the panel. |
| `question`, `from` | The question as the button and the heading say it (a function of the page's environment and the choices), and the key of the line above the heading that says where the answer comes from. |
| `scale` | The verdicts the answer says, each with the key of its sentence. Empty where the answer is a sentence of its own (the download chip). |
| `load` | **What it fetches**: provider, network, parameters and window, through the `api` it is handed (`values`, `stations`, `providers`, `coverage`, `kept`). It does not judge the data. |
| `answer` | The answer, from what `load` returned. **Pure**, like the functions of `utils/answers.ts`, and null rather than a number made up: the panel then says `empty`. |
| `present` | How an answer is written: the verdict, the lines under it, the chart, a list of links, a line of small print. |
| `empty`, `actions` | What is said where there is no answer, and the ways into the tools (with their tiles). |
| `credit` | The provider whose credit line, and the note of what wetterdienst did to the data, close the answer; null where it is no provider's data. |
| `i18n` | **Every key of the catalogs the definition uses.** The test holds these to all eleven locales, and holds the file to the list: a key it writes and does not list fails. |
| `explanation` | Not written yet. Typed and left out until step 1b of GH-3764 (how the answer was worked out, its sources). |

## Rules

- **Do not edit the page for a chip.** If a chip needs something the page cannot draw (a new kind of choice, a
  new block in an answer), add it to `chip.ts` as a field every chip can use, and to the page once, for all.
- **The answer is pure.** Put the arithmetic in a function that takes readings and a unit and returns an answer or
  null (`utils/answers.ts` for the four there are; the definition's own file for a new one), and test it with a few
  readings whose answer you know by hand. What a number is judged by (a millimetre, Beaufort 9) is judged in the canonical
  unit of its quantity (`utils/units.ts`), so that a verdict is the same in every unit the reader picks.
- **Use `env`, not the page.** `present` and `question` get the translator, the number and unit formats and the place in
  `env`; `load` and `answer` get the place, the choices, the clock and the language in `context`. A definition imports
  nothing of Nuxt, and its functions can be called by a unit test with plain values.
- **Links keep working.** A choice's name in the link (`&day=`) is the link: do not rename one a link out there may carry.
  The link read gives the choice's own initial value for a missing or wrong value, never an error.
- **The text of a question follows its choices**, and a key takes its numbers, names and days as parameters rather than
  one string per combination.
- **Imports in `utils/ask/` are relative** (`../../answers`), as in the rest of `utils/`, so the unit tests, which run
  in plain Node, can import a chip.
