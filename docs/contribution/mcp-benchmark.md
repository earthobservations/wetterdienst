# MCP benchmark

A manual benchmark of the [MCP server](../usage/mcp.md): does a model, given only the tools, reach an answer within a
number of steps, through which steps, and is that still so after a change to the server (a slimmer schema, a smaller
answer)?

It is **manual and costs tokens**. A person, or a Claude Code session the person tells to, runs it; no CI job, schedule
or `pytest` run starts it. A run is one tested model per case, model tier and repeat, and sends requests to the live
providers, so run the cases you need. Nothing of it lives in `.claude/`: it is a folder, `benchmarks/mcp/`.

| file | what it is |
| --- | --- |
| `benchmarks/mcp/README.md` | **the runbook**, and the rules of the judge: everything needed to run it |
| `benchmarks/mcp/cases.json` | the questions, with their steps, forbidden behaviour and facts |
| `benchmarks/mcp/prompt.md` | what the tested model is told |
| `benchmarks/mcp/scripts/bench.py` | the counting (standard library only): runs the tested model, reads its transcript, aggregates, compares |
| `benchmarks/mcp/scripts/run_subject.sh` | one tested model, headless, in an empty directory |

## Run it

Open Claude Code in a checkout of the repository and tell it: *"follow `benchmarks/mcp/README.md` for the smoke run"* (all
27 cases that need no key, both tiers, 1 repeat: 54 runs) or *"... for the baseline"* (the same with 5 repeats: 270 runs).
The README is the whole instruction: prerequisites, a local server of `main` in a git worktree, the results file, the runs
(at most 3 at once), how the orchestrating Claude judges what has to be read, how it reports on
[#3546](https://github.com/earthobservations/wetterdienst/issues/3546) with comments and a secret gist of the results, how
to stop, and what to do when something breaks. The script counts everything that can be counted from the transcript of the
tested model, so that two runs are compared on the same arithmetic; the judge reads the rest against ground truth it obtains
itself.

The tested model runs headless (`claude -p` in an empty temporary directory outside the repository, no built-in tool, no
settings, no skills, one MCP server), so what it knows is the prompt and the tools. That also loads the tools directly, not
deferred, which is what makes the **size of the tool schemas** show in the context of the first request
(`context_tokens_first` of the results). Prompts, transcripts and the results file go to a scratch directory outside the
repository.

## Read the result

| column | what it is |
| --- | --- |
| `passed` | the headline, out of the repeats: an answer was reached with at least one and at most `max_steps` calls of the server's tools (counted from the transcript), the first checkpoint was met, and the answer is an answer |
| `steps` | median and maximum of the calls, against the limit |
| `checkpoints` | the expected intermediate steps met, out of possible, in order but not necessarily one after the other |
| `violations` | behaviours the case forbids: `interpolate` for a plain weather question, `shape=wide` over a long window, a refusal for lack of a forecast network, the same call more than twice, and any tool other than the server's |
| `facts ok` | the answer against ground truth the judge reads with its own calls; a forecast is only held to a plausible span of forecast hours, never to a number |
| `format violations` | k/n of the runs of the cases that ask for the `RESULT:` format that left it out or broke it, computed from the final answer; its own rate in `compare` |
| `result chars`, `out tokens` | the median size of the tool results and the output tokens: "shorter but no worse" is measured here |

`passed` does not say that the answer is right or that the model kept to the rules, so `facts ok` and the share of runs
without a violation are compared as metrics of their own. `bench.py compare` is a **non-inferiority** claim on the pooled
rates of a tier (the passes, the facts, the runs without a violation, the runs that follow the format), and refuses when the
two files cannot be compared; not finding a difference is not "no worse", and at a pass rate of 90 % it takes about 140
runs per side to show a margin of 10 points. The runbook has the rules in full.

## Units

A `values` answer in CSV or in the default JSON carries no unit
([#3546](https://github.com/earthobservations/wetterdienst/issues/3546)): it is in `metadata.parameters[].unit` of JSON with
`with_metadata=true`, and in the `glossary` and `coverage` tools. A model that does not look it up can state 0.84 for 84 %
humidity as "0.84 %", seconds as hours, or degrees Celsius as kelvin. The eight cases of kind `units` therefore require the
answer to state the value **with the right unit**, and the prompt asks for the structured part: one line
`RESULT: <number> <unit> | <what it is>` for each figure the question asks for, and `TABLE-UNIT: <column> | <unit>` per column
of a table, which `bench.py` checks strictly and deterministically. An answer without them is read tolerantly and counted as a
**format violation**, a metric of its own. A strategy that drops the unit from the default answer must pass it some other
way, or these cases fail: the CSV case is the guard for it. The prompt is part of the hash, so results files made with
another prompt are not comparable. The runbook has the whole check.

## Known limits

- The benchmark is run on macOS and Linux. `bench.py add-run` locks the results file with `fcntl` (several of them can run at
  once, one per repeat that is filled in, and keep all their records); where there is no `fcntl` (Windows) it takes no lock,
  the write stays whole-or-none, and `add-run` must be run one at a time.
- `add-run` does not check that a record's `tier` is one of the file's `meta.models`, nor that its resolved model id is the
  one of the other runs of that tier (`compare` refuses a tier whose resolved ids differ, later).

- The cases with a fixed date (Kiel and Frankfurt on 26 December 2025) are read from DWD's `recent` period now and from
  `historical` once the date is older than about a year and a half (around mid-2027): the value should not change, and
  the judge's own call decides, but the station list for the date may.
- A benchmark of a model is noisy: one run says little, and the noise differs by case. Use repeats and read the cases that moved.
- The headless runs reach the hosted server by URL, not through the claude.ai connector, and carry what Claude Code puts
  in every session (its system prompt and the user's email).
- The tested agent's results above the limit of Claude Code are saved to a file it cannot open (the notice is not a
  documented format).
- The descriptions that decide whether an extra RESULT line is a claim about the asked quantity are word lists (`asked_descriptions`,
  `ignore_descriptions` of a fact): a wrong figure that a model labels with a word of the ignore list (`RESULT: 5.2 m/s |
  daily mean wind speed, the peak`) is not caught, and a right extra figure labelled with a word no list foresaw is not failed. They are a first judgement: revisit
  them after the first baseline run, against the answers real models give.
- A table is found only if it has a markdown separator row or a header line of names (cells that are no value, that is no signed
  or decimal figure, none that starts the cell, none before a symbol such as `°C` or `%`, and no sentence: five words at most, not
  two words or more ending in `.`, `!` or `?`, unless it is an abbreviation (a stop after a word of fewer than four ASCII letters, and
  an earlier word with a stop: `Temp. max.`, `Daily precip. amt.`); a figure in brackets
  or a whole number before a word, `quality (1-10)`, `Precip. in 24 h (mm)`, belongs to a name, a whole number at the end of a cell
  does not; dates as columns count) and its cells are separated by a pipe, a comma or a tab. A
  semicolon CSV is not a table to the check, and neither are quoted fields (`"precipitation, mm"` is split at the comma); their
  figures still need a RESULT line.
- A table **defers**, failing nothing and passing nothing, when it has no row of the day for the quantity, when two columns may
  be the value (`precipitation_mm` and `precipitation_cm`, with none named `precipitation_amount`), when no column is named like
  the quantity (`rr`, `rain`), and when a unit-less spelling of its column is declared twice with two units; the RESULT line
  decides, so an answer without one fails. A column that a `TABLE-UNIT` line names with a unit of the case is taken for the value
  whatever quantity it is (`snow_cm | cm` next to an unnamed `rr`). A range written with "to" (`2026-10-16 to 2026-10-18`) is not
  recognised as a range: its row also counts as the 16th, and a different figure there makes the day ambiguous.
- A line `value | see parameter` (a unit that is not one of the case) on the value column of a long table fails, whatever the
  per-parameter lines say. A title line of names above an unfenced CSV with the same number of cells (`Hamburg, daily
  precipitation`) becomes the header of the table, which then defers. `_tables` restarts its scan on each line that does not
  start a table, so a long run of two-cell lines without a header is quadratic (2000 lines take about 16 s). The exclusions of the column regex apply at the start of a word (`maximum`, `minutes` and `formula` are excluded too), so an "hours" neighbour (`precipitation_hours`, `precipitation_amount_last_hour`) can match it; and a `TABLE-UNIT` line for one spelling (`precipitation | mm`) can claim a neighbour column (`Precipitation form`) when the precipitation column has no "precip" in its name (`Rainfall (mm)`). A date in a table is read as `2026-10-16`, `2026/10/16`,
  `20261016`, `16.10.2026`, `16.10.26`, `16.10.` (zeros optional), `16/10/2026`, `16-10-2026`, `10/16/2026`, `16 Oct`,
  `Oct 16, 2026` or `16 October 2026`; another year is another day, month names in other languages are not read. A table with no row for the day, or none with a figure in it
  (a station list, a table of other days), fails nothing; one with the day's row and a wrong value does.
- The unit check does not read: units written per time (`mm/day`), a German thousands point (`14.821 s`), a unit before the
  figure in a RESULT line, or a forecast figure in °F or K outside the span (it is ignored, not converted and checked). A
  case whose model writes these is a format violation or a failed fact, and the transcript says which.

The tested agent's log is not asked for: the counts come from the transcript the harness keeps (the stream-json of
`claude -p`).

## Add a case

Append an object to `benchmarks/mcp/cases.json`: `id`, `question`, `kind`, `max_steps`, `checkpoints`, `forbidden`, `facts`,
`tiers`, `needs_key`, `notes`. Keep to the following.

- Write `max_steps` generous but meaningful: 6 for a forecast by place, 4 for a glossary or licence question.
- A checkpoint is a call with an alternative for every valid way to make it (any provider and network that serves the
  question, a name or a point, a window that holds the day); it is checked on the tool and its arguments, not on the
  wording. The first checkpoint is required to pass, so an answer from memory cannot pass.
- Check facts against a call the judge makes, never against a number written in the case (the source moves);
  an `expected` value only shows that it drifted. A forecast gets a span of forecast hours, not a value.
- Name a provider, network, parameter or period as a literal when it must exist: the offline test holds them to the code.

Then run `uv run pytest tests/ui/test_mcp_benchmark_cases.py tests/ui/test_mcp_benchmark_scripts.py`. They call no model:
the first checks that every tool, argument and enum value, provider, network, parameter and period a case names exists,
that the ids, limits, fields and regexes are sound (each regex that decides a verdict is tried against strings it must
and must not match), that `needs_key` agrees with the networks, and that no credential or personal data is in the files;
the second tests the counting. A renamed parameter or tool fails them before a run would silently stop meeting a
checkpoint, and an enum that a slimmer schema moves into a description fails the guard instead of passing vacuously.
Run the new case with 3 repeats (`bench.py init --cases <id> --repeats 3`, then the runbook) before trusting its `tiers`.
