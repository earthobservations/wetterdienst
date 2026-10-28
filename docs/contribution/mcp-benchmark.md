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

**The answer format.** The prompt asks every answer that gives a number to end with one line
`RESULT: <number> <unit> | <what it is>` per figure (and `TABLE-UNIT: <column> | <unit>` per column of a table), and the
unit check reads only those lines, strictly and deterministically. An answer without them is read tolerantly (prose and
tables) and counted as a **format violation**: whether the model follows the format is a metric of its own, printed and
compared per tier, so that a token strategy that confuses the model shows up. The prompt is part of the hash, so
results files from before the format are not comparable with later ones.

## Read the result

| column | what it is |
| --- | --- |
| `passed` | the headline, out of the repeats: an answer was reached with at least one and at most `max_steps` calls of the server's tools (counted from the transcript), the first checkpoint was met, and the answer is an answer |
| `steps` | median and maximum of the calls, against the limit |
| `checkpoints` | the expected intermediate steps met, out of possible, in order but not necessarily one after the other |
| `violations` | behaviours the case forbids: `interpolate` for a plain weather question, `shape=wide` over a long window, a refusal for lack of a forecast network, the same call more than twice, and any tool other than the server's |
| `facts ok` | the answer against ground truth the judge reads with its own calls; a forecast is only held to a plausible span of forecast hours, never to a number |
| `result chars`, `out tokens` | the median size of the tool results and the output tokens: "shorter but no worse" is measured here |

`passed` is the answer-reached headline; it does not say that the answer is right or that the agent kept to the rules,
so `facts ok` and the share of runs without a violation are compared as metrics of their own. `bench.py compare` is a
**non-inferiority** claim on the pooled rates of a tier: for the passes, the facts, the runs without a violation and the runs that follow the RESULT format it
gives the difference with its 95 % interval and decides it as one test: "no worse" if the lower bound is above minus 10
percentage points, "WORSE" if the upper bound is below minus 10 points, "inconclusive" otherwise (a real drop within the
margin is said as such, and a likely one too). Every case is first cut down to the same number of valid runs on both sides (the first k of
each, k the smaller; an invalid run or an extra repeat leaves runs out, and the output says how many), so that pooling uses
real counts only and weights the cases alike, and a case whose own rate fell by 40 points is named whatever the verdict
says. Not finding a difference is not "no worse": at a pass rate of 90 % it takes about 140 runs per side to show a margin of 10
points, which the output prints for each rate next to the runs there are; the default full run is 27 cases, 135 runs a side per tier at 5 repeats, 270 in all
(the case that needs a key is skipped). The Fisher test per case is a hint only. It **refuses** (exit code 4) when the prompt, the logic
version of `bench.py`, the defaults, the mode (headless or subagent) or the deferral of the tools differ, when the two
sides report one version and carry no differing `label`, or when more than 3 % of the compared runs are invalid (the server
was not connected: those runs are left out of the rates and counted; a run that never ran is recorded with
`bench.py failed-run`; a timeout is a failed run, not an invalid one, with what its partial transcript measured or no metrics at all, never zeros); a tier whose resolved model ids differ is not compared. It compares only cases whose hash is
unchanged and says how many it left out (only in the current file, changed, only in the previous file). Sizes
(tool-result characters, context tokens at the first request, total and output tokens, calls whose result was saved to a
file) are printed as medians per case before and after and the paired difference.

`run_subject.sh` stops with exit code 3 before a model is paid for when the MCP URL does not answer, 124 after a
timeout (`MCPBENCH_TIMEOUT`, default 300 s, at most 540: `cleanup` waits 10 minutes before it takes a directory for a
finished run), and ends a run at `MCPBENCH_MAX_USD` (default 0.50, checked with 0.001: it
stops after the first turn). It removes the temporary directory and the project directory Claude Code makes for it in
`~/.claude/projects`; `bench.py cleanup` removes what an interrupted run left. A tool result above the limit of Claude
Code is saved to a file the tested agent cannot open (it has no Read tool); the transcript then holds a notice, and
`bench.py` reads the real size out of it; such a call is `spilled` and read nothing, and a short result that talks of a saved file in other words is warned about in the report.

**What the benchmark cannot see.** The hosted `tools/list` is about 260,000 characters: 210,000 of `outputSchema`,
39,000 of `inputSchema` and 10,000 of descriptions (`bench.py tools-size`). The context of the tested agent at its first
request is 26.5k tokens, which only fits if Claude Code does not send the `outputSchema` to the model, so slimming the
output schemas shows in `tools-size` and not in `context_tokens_first`. Run `tools-size` for each side of a comparison.

## Compare a change before release

The hosted server is the released one, so a baseline against it differs from local `main` by host, network and settings.
Run both sides on local servers in the same environment, each in its own worktree and port, with the same
`WD_CACHE_DIR`:

```bash
export WD_CACHE_DIR=$HOME/.cache/wetterdienst-mcpbench     # the same for both servers
git worktree add ../wd-main main && cd ../wd-main
uv sync --python 3.13 --extra restapi --extra mcp --extra export --extra interpolation --extra sql
uv run --python 3.13 wetterdienst restapi --listen 127.0.0.1:7891      # MCP at http://127.0.0.1:7891/mcp/v1
# in another terminal, the branch with the change, in its own worktree, on 7892
```

Then `/mcp-benchmark server=http://127.0.0.1:7891/mcp/v1 label=<sha of main> repeats=5` for the baseline, the same with
`:7892`, the SHA of the branch (`+dirty` if it has changes) as the `label`, and `previous=<the baseline's results>` for the
change. Both servers report one version, so the label is what tells the two files apart, and `compare` refuses without it.
`reference=` stays the released hosted server for both. A local server was tried: `probe`, `tools-size` and a headless
glossary run against it worked.

## Known limits

- The cases with a fixed date (Kiel and Frankfurt on 26 December 2025) are read from DWD's `recent` period now and from
  `historical` once the date is older than about a year and a half (around mid-2027): the value should not change, and
  the judge's own call decides, but the station list for the date may.
- A benchmark of a model is noisy: one run says little, and the noise differs by case. Use repeats and read the cases that moved.
- The headless runs reach the hosted server by URL, not through the claude.ai connector, and carry what Claude Code puts
  in every session (its system prompt and the user's email).
- The tested agent's results above the limit of Claude Code are saved to a file it cannot open (the notice is not a
  documented format).

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
