# MCP benchmark

A how-to for the manual benchmark of the [MCP server](../usage/mcp.md): does a model, given only the tools, reach
an answer within a number of steps, through which steps, and is that still so after a change to the server (a slimmer
schema, a smaller answer)?

It is **manual and costs tokens**. It runs inside Claude Code, started by a person with `/mcp-benchmark`; no CI job,
schedule or `pytest` run starts it. A run is one tested agent per case, model tier and repeat, and sends requests to
the live providers, so run the cases you need.

The skill is `.claude/skills/mcp-benchmark/SKILL.md`, the questions are `.claude/skills/mcp-benchmark/cases.json`, the
counting is `.claude/skills/mcp-benchmark/scripts/bench.py` (standard library only). The orchestrating Claude judges
what has to be read; the script counts everything else from the transcript of the tested agent, so that two runs are
compared on the same arithmetic. The schema of a case and the rules of the judge are in the skill.

## Run it

Open Claude Code in the repository and type, for a smoke run of two cases:

```text
/mcp-benchmark server=https://wetterdienst.eobs.org/mcp/v1 cases=glossary-temperature-air-mean-2m,licence-dwd
```

and, for a baseline or a comparison (one run of a model says little: use `repeats=5` or more):

```text
/mcp-benchmark server=http://localhost:7890/mcp/v1 repeats=5 large=opus previous=/path/to/mcpbench-results-20261028-1200.json
```

| argument | meaning | default |
| --- | --- | --- |
| `server` | **required**, the server under test: its MCP URL (`mode=headless`) or the prefix of its tools in the session (`mode=subagent`) | none |
| `mode` | `headless` runs the tested agent as `claude -p` in an empty directory with only that server's tools; `subagent` uses a subagent of this session | `headless` |
| `cases` | ids separated by commas, `kind:<kind>`, or `all` | `all` |
| `tiers`, `large` | `small` (Haiku), `large` (`sonnet` or `opus`), or both | both, `sonnet` |
| `repeats` | runs per case and tier | `1` |
| `previous` | an earlier results file to compare with | none |
| `reference` | where the judge reads ground truth: a pinned server's tool prefix (default the released hosted server) or `python` (the library) | the connector |
| `include_keys` | `1` to run the cases of a network that needs credentials | skipped |

A run asks for a permission per tool the first time. The skill lists the ones to allow in your own
`.claude/settings.local.json`; it never edits the settings.

## Why headless

A tested agent run as a subagent of a session in this repository is not clean: the harness hands it the project's
CLAUDE.md (which names this benchmark), the user's memory, the git status, the user's email and every tool. The
headless mode runs it in an empty temporary directory outside the repository, with no built-in tool, no settings, no
skills and one MCP server, so what it knows is the prompt and the tools; what remains is Claude Code's system prompt
and the harness's block with the user's email. In the validation of this benchmark the one subagent run of the
Los Angeles forecast failed (the small model read observations of another provider and said it could not give a
forecast), and three headless runs of the same case passed: one run against three says nothing certain, but it is the
kind of difference the clean mode is for.

Headless also loads the tools directly, not deferred behind ToolSearch, which is what makes the **size of the tool
schemas** show in the context of the first request (`context_tokens_first` of the results). In subagent mode the
schemas are loaded on demand, so a slimmer one reaches the context only in part, and the mode is for when `claude`
cannot be run. The results file records the mode, the deferral and what remains in the context, and two files of
different modes are not compared.

## Units

A `values` answer in CSV (long or wide) or in the default JSON carries no unit: it is in `metadata.parameters[].unit` of
JSON with `with_metadata=true` (which CSV ignores), and in the `glossary` and `coverage` tools
([#3546](https://github.com/earthobservations/wetterdienst/issues/3546)). A model that asks for CSV and does not look
the unit up can state 0.84 for 84 % humidity as "0.84 %", seconds as hours, or degrees Celsius as kelvin. The eight cases
of kind `units` (`cases=kind:units`) therefore require the answer to state the value **with the right unit**:
temperature in degrees Celsius (and a correct conversion to Fahrenheit), humidity as 84 % or as the fraction 0.84,
sunshine duration in seconds (or the same time in minutes or hours), wind speed, precipitation, and a case that asks
for a CSV table and the unit of its column. The judge reads value and unit from the reference server's `values` with
`with_metadata=true` and the glossary, and applies the rules of `bench.py unit` (the unit directly after the figure, or in
the header of a table; a unit that belongs to another accepted unit than the one the number is in, or a forbidden unit,
fails). A strategy that drops the unit from the default answer, a compact or columnar `values`, must pass it some
other way, or these cases fail: the CSV case is the guard for it.

## Read the result

| column | what it is |
| --- | --- |
| `passed` | the headline, out of the repeats: an answer was reached with at least one and at most `max_steps` calls of the server's tools (counted from the transcript), the first checkpoint was met, and the answer is an answer |
| `steps` | median and maximum of the calls, against the limit |
| `checkpoints` | the expected intermediate steps met, out of possible, in order but not necessarily one after the other |
| `violations` | behaviours the case forbids: `interpolate` for a plain weather question, `shape=wide` over a long window, a refusal for lack of a forecast network, the same call more than twice, and any tool other than the server's |
| `facts ok` | the answer against ground truth the judge reads with its own calls; a forecast is only held to a plausible span of forecast hours, never to a number |
| `result chars`, `out tokens` | the median size of the tool results and the output tokens: "shorter but no worse" is measured here |

`bench.py compare` flags a change in the pass rate only when Fisher's exact test (two-sided, p < 0.05) says it is
beyond noise, first per tier pooled, then per case; steps and sizes are shown as medians. It compares only the cases
whose hash and the prompt are unchanged and says how many it skipped.

The tested agent's log is not asked for: the counts come from the transcript the harness keeps (the stream-json of
`claude -p`, or for a subagent the `output_file` the Agent tool returns, a detail of the harness).

## Add a case

Append an object to `cases.json`: `id`, `question`, `kind`, `max_steps`, `checkpoints`, `forbidden`, `facts`,
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
Run the new case with `repeats=3` before trusting its `tiers`.
