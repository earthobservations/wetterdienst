---
name: mcp-benchmark
description: Manual benchmark of the Wetterdienst MCP server. Has a model answer questions with the wetterdienst MCP tools only, in a clean headless session or a subagent, and judges whether an answer is reached within a number of tool calls, which intermediate steps it took, what it must not do and whether the facts are right, over repeated runs so that two versions can be compared. Run by a person only, never by CI or on a schedule. Costs tokens (a run per case, tier and repeat) and calls the live providers.
argument-hint: "server=<mcp url | tool prefix> [mode=headless|subagent] [cases=<ids|kind:..|all>] [tiers=small,large] [large=sonnet|opus] [repeats=N] [previous=<results.json>] [reference=<prefix>|python] [include_keys=1]"
disable-model-invocation: true
---

# MCP benchmark

You are the **orchestrator and judge**. You test whether a model, given only the Wetterdienst MCP tools, reaches a
correct answer within a number of steps, and whether a change to the server (a slimmer schema, a smaller answer)
makes that better or worse. It is not a test suite: nothing here runs in CI and `pytest` never collects the runs. The
cases are data in [cases.json](cases.json); `tests/ui/test_mcp_benchmark_cases.py` keeps them true to the code
without calling a model, and `tests/ui/test_mcp_benchmark_scripts.py` tests the counting in
[scripts/bench.py](scripts/bench.py).

It costs tokens (one run per case, tier and repeat, plus your own ground-truth calls) and sends requests to the
live providers: run what you need, and never more than 4 runs at once. A smoke run is
`cases=glossary-temperature-air-mean-2m,licence-dwd repeats=1`; a baseline or a comparison needs `repeats=5` or more,
because one run of a model says little (Haiku passes or fails the same case on different runs).

## Arguments (`$ARGUMENTS`)

`key=value` pairs separated by spaces.

| key | meaning | default |
| --- | --- | --- |
| `server` | **required.** The server under test. `mode=headless`: its streamable-HTTP URL (the hosted one is `https://wetterdienst.eobs.org/mcp/v1`, your own `http://localhost:7890/mcp/v1`). `mode=subagent`: the prefix of its tools in this session (`mcp__claude_ai_wetterdienst__` for the hosted connector). The subject and your own checks never use different servers by accident: you say which. | none |
| `mode` | `headless` or `subagent`, see below | `headless` |
| `cases` | ids separated by commas, `kind:<kind>`, or `all` | `all` |
| `tiers` | `small`, `large` or `small,large` | `small,large` |
| `large` | `sonnet` or `opus`; the small tier is `haiku` (`tiers.small` of the cases file) | `sonnet` |
| `repeats` | runs per case and tier | `1` |
| `previous` | an earlier results file to compare with | none |
| `reference` | where you read ground truth: the prefix of the MCP tools of a pinned server (default: the connector of this session, the released hosted server), or `python` (the library of this checkout, see below) | the connector |
| `include_keys` | `1` to run `needs_key` cases; they run only if `coverage` says the network is `configured`. Never set, ask for or pass a credential. | skipped |

## The two modes, and what each leaves in the tested agent's context

A fair comparison needs a tested agent that knows only the prompt and the tools. Prefer `headless`.

**`mode=headless`** runs `claude -p` through [scripts/run_subject.sh](scripts/run_subject.sh), in a new empty
directory outside the repository, with `--strict-mcp-config` and an `--mcp-config` holding only the server under
test, `--tools ""` (no built-in tool: no Bash, Read, WebFetch, Agent), `--setting-sources ""`,
`--disable-slash-commands` and `--no-session-persistence`, and `--output-format stream-json --verbose`, whose
output is the transcript. The flags were checked against `claude --help` (2.1.308). What it was shown to hold:
the model sees 14 tools directly and no ToolSearch (so the tools are **not deferred**), no CLAUDE.md or AGENTS.md,
no memory index, no git status, no skill. What remains: Claude Code's own system prompt and, injected by the
harness, a block with the user's email address and the note about an empty auto-memory directory of the temporary
directory. It talks to the server by URL, not through the claude.ai connector (`--strict-mcp-config` leaves the
connectors out, and it was not tried whether one can be named headless); it is the same hosted server, over its
own transport, and `server_version` in the results says which version. The login of the person who runs it pays
for the model; no provider credential is passed.

**`mode=subagent`** spawns the subject with the Agent tool: `subagent_type: mcp-benchmark-subject`
([.claude/agents/mcp-benchmark-subject.md](../../agents/mcp-benchmark-subject.md), `tools:` limited to ToolSearch
and the wetterdienst tools; a new agent file is only picked up when Claude Code is started anew, and if the type is
not found you are told, and may fall back to `general-purpose`, which has **all** tools: say so in the results) and
`model` of the tier. What remains in this mode, because the harness injects it and the skill cannot remove it: the
project's CLAUDE.md and AGENTS.md (which name this benchmark), the user's memory index, the git status, the user's
email, the skill and agent listings, the instructions of every connected MCP server. A subagent also loads the
tools **deferred** with ToolSearch. Use this mode only when headless is not available, and never compare a
subagent-mode results file with a headless one. The transcript is the `output_file` the Agent tool returns, or
`subagents/agent-<id>.jsonl` under the session directory (a detail of the harness, which may change).

The mode, the deferral and the context attachments are recorded in the results file. **A change to the size of the
schemas can only be judged in `mode=headless`**: in subagent mode ToolSearch loads a schema on demand, so a slimmer
one reaches the context only in part.

## Protocol

1. **Load.** Read `cases.json`; select cases and tiers. Make sure you can call the MCP tools of the `reference`
   yourself (load them with ToolSearch if they are deferred), and that `claude` runs (`claude --version`,
   headless). Record today's date in UTC, the model you are, and `python3 -I scripts/bench.py hashes`.
2. **Run**, per case, tier and repeat (at most 4 at once; use `run_in_background` for Bash):
   - write the prompt: `python3 -I .claude/skills/mcp-benchmark/scripts/bench.py prompt <case-id> --today <date>
     > <scratchpad>/mcpbench-<case>-<tier>-<n>.prompt` (add `--tools "the tools named mcp__...__*"` in subagent mode);
   - headless: `.claude/skills/mcp-benchmark/scripts/run_subject.sh <haiku|sonnet|opus> <server url> wetterdienst
     <prompt file> <scratchpad>/mcpbench-<case>-<tier>-<n>.jsonl`; subagent: Agent with the prompt as its prompt.
3. **Analyze** each transcript: `python3 -I .../bench.py analyze <transcript> --case <id> --server <prefix>`, where the
   prefix is `mcp__wetterdienst__` (headless) or the one you gave (subagent). It counts, from the transcript and not
   from what the agent says of itself: `steps` (calls of the server's tools only), `tool_searches` (not a step), any
   other tool called (Bash, WebFetch, Read, Write, Agent, ...: each is a violation), the ordered checkpoints, the
   forbidden calls, repeats and answers, the size of the tool results, the output tokens, the context at the first and
   last request, and the server version. Do not recount these yourself.
4. **Judge** what needs reading, per run (below), then write the results file, print the table with
   `bench.py report`, and the comparison with `bench.py compare <previous> <results>` when `previous` is given.

## What you judge

The script has given `steps`, the checkpoints, the violations and `mechanical_pass` (1 to `max_steps` steps and the
**first checkpoint met**). You add:

1. **`is_answer`**: the final answer answers the question. A refusal, a request for clarification or a hand-off is
   none (for `unanswerable`, saying there is no data is the answer). `passed = mechanical_pass and is_answer`:
   a run with no tool call never passes, even if it is right from memory, and a run that skipped the first
   checkpoint never passes.
2. **`facts_ok`**: every fact of the case, against ground truth **you** obtain with your own calls (not steps of the
   tested agent). Read the ground truth from the `reference`, never from the subject's own answers or the server
   under test alone, so that a change that rounds or drops a value cannot reproduce itself in the judge. Never copy a
   number from the case file: `expected` there only lets you say that the source has drifted.
   - `answer_regex`: the answer matches one of `any_of`.
   - `ground_truth_value`: make the call, pick what `pick` says, and the number in the answer is within `tolerance`.
   - `ground_truth_span`: every figure the answer gives lies in `[min - margin, max + margin]` of the series your call
     returns and inside `sanity`; with `future_only`, it must belong to timestamps after the subject's call (a
     forecast), so an observation fails.
   - `ground_truth_text`: the answer carries what `pick` says, in its own words; `answer_matches_any_of`, if there,
     lists accepted spellings.
   - `ground_truth_subset`: every name the answer gives is in your call's result. `ground_truth_set`: the answer
     names exactly the items your call yields, or says there are none.
   - `unit`: the answer states the value **with its right unit** (see "Units" below). Run
     `python3 -I .../bench.py unit --case <id> --fact <id> --truth <value> | <min> <max> --answer "<text>"` with the value
     (or the span of a forecast) from your own call; it applies the rules and prints which figures passed or failed.
   - `no_measurements`: no figure in the answer that no tool result of the transcript supports, with the exemptions
     below.
3. A `judge_note` for a near miss (the right tool with a better argument than the one a checkpoint lists): record it,
   do not count it.

**Placeholders** in `ground_truth` arguments: `$answer_station` the station id the answer's value came from;
`$yesterday` yesterday's UTC date; `$last_7_days` the 7 UTC days up to and including yesterday as `A/B`;
`$subject` the argument as the subject sent it (so that the same source is read); `$subject_snapshot` the
`data_updated_at` of the subject's result of the same tool (so that warnings are read from the snapshot the subject
read, not a later one). A source that publishes with a delay may hold fewer days than asked: take the span over
what your own call returns. When the tool's default answer is shallower than the pick needs (a depth option),
ask for the deepest level the tool offers.

**Dates.** All dates are UTC. "Yesterday" is today minus one day; "the last 7 days" is the 7 days ending yesterday. A
fixed date of a case (26 December 2025) is read from whichever period the server serves it in; the value does not
change, and your own call decides.

**An argument a call leaves out counts as its default** (`defaults` in the cases file, which the offline test holds to
the schema): `alerts()` is `alerts(granularity="community")`. A checkpoint on an argument accepts the default too.

**Invented numbers.** A number in the answer is supported if it appears in a tool result of the transcript (to the
precision shown), or it is derived from such numbers (a minimum, maximum, mean, difference or count you can recompute,
a unit conversion). Exempt: numbers of the question (a year, a date, "2 m"), dates and times that the answer takes
from the question's window or from timestamps in the results, station ids and counts of things the answer says
it looked at ("two stations"), identifiers of licences and versions (CC-BY-4.0, 2.0), and the number words of
ordinary phrases. Anything else, such as the year the records begin read from memory, is invented.

**Units.** `values` answers in CSV (long and wide) and in the default JSON carry **no unit** (GH-3546): it is in
`metadata.parameters[].unit` of a JSON answer with `with_metadata=true` (which CSV ignores), in `glossary` and in
`coverage`. A model that does not look it up may state 0.84 for 84 % humidity as "0.84 %", seconds as minutes, or
degrees Celsius as kelvin, and a change that makes the default answer compact (CSV or columnar) must still hand the
unit over. The cases of kind `units` (`cases=kind:units`, 8 cases) require the answer to state the unit, and the right
one. For a `unit` fact the judge reads the value **and** its unit from the *reference*'s `values` with
`with_metadata=true`, and the glossary as a cross-check (`cross_check`), never from the server under test alone, and runs
`bench.py unit`. The rules it applies: a figure of the answer is the value if it equals the judge's value in one of the
`accepted` units (`value * factor + offset`, within the fact's `tolerance` or `margin`, or the rounding of the figure as
written); the unit must come **directly after the figure** (a sentence's "near" is that: the next word or symbol), or,
for a figure in a table row, stand in the header or in the text of the answer; a unit that belongs to another accepted
unit than the one the number is in (`0.84 %` against 0.84 as a fraction), or one of `forbidden_tokens` (kelvin, whatever
the figure), fails the answer; a figure with no unit next to it neither passes nor fails; a pair marked `required`
(Fahrenheit, when the question asks for it) must be there. The checkpoint `gets-the-unit` (`any_order`: before or after
the values) lists the valid routes to the unit; the first checkpoint, reading the values, is the one required to pass.
A strategy that drops units from the default answer must pass them some other way, or these cases fail.

**Reference `python`.** When you cannot reach a pinned server, read ground truth from the library of this checkout in a
Bash call, e.g. `uv run python -I -c "from wetterdienst import Wetterdienst; ..."` with
`Wetterdienst.resolve(provider, network)(parameters=..., ...).filter_by_station_id(...).values.all()`. It is
independent of the MCP layer (a change to the tools or their answers does not reach it) but not of the library.

## The results file

Write `mcpbench-results-<YYYYMMDD-HHMM>.json` to your scratchpad directory (the one the system prompt names; never
into the repository, never committed). `bench.py report` and `compare` read it.

```json
{"meta": {"date": "2026-10-28", "mode": "headless", "models": {"small": "haiku", "large": "sonnet"},
          "judge_model": "<the model you are>", "server": "<url or prefix>", "server_version": "0.178.0",
          "reference": "<prefix or python>", "reference_version": "0.178.0", "claude_version": "2.1.308",
          "tools_deferred": false, "context_note": "<what remains in the context, per mode above>",
          "repeats": 5, "cases_file": "<hash>", "prompt": "<hash>", "case_hashes": {"<case id>": "<hash>"}},
 "runs": [{"case": "...", "tier": "small", "repeat": 1,
           "...": "everything `bench.py analyze` printed, without `result_head`",
           "is_answer": true, "passed": true, "facts_ok": true,
           "fact_results": {"<fact id>": "ok | fail: <why> | drift: <how>"}, "judge_note": ""}]}
```

## Output

Print `bench.py report`: per (case, tier) `passed k/N`, steps median/max against the limit, checkpoints met out of
possible, violations, `facts ok k/N`, the median size of the tool results (characters) and the median output
tokens, then one pooled row per tier. Under it: the cases that failed their headline, the cases where a tier that
`tiers` expects to pass did not (the model is behind what the case expects) or one that is not expected to did
(the case may be too easy now), and the path of the file.

**Comparison.** `bench.py compare previous results` compares only the (case, tier) whose case hash and prompt are
unchanged, and says how many it skipped. It flags a pass rate as `REGRESSED` or `improved` only when Fisher's exact
test (two-sided) gives p < 0.05 for the passes out of the repeats; otherwise "within noise". Do it per tier
pooled first, since 20 cases at 5 repeats each is where one flag in 20 is chance. Steps, result size and output
tokens are shown as medians, not flagged. The model, mode, server and reference versions that differ are told first. A
token-efficiency change is "no worse" when the pooled pass rate and facts are within noise and the sizes fell.

## Case schema

`cases.json` is `{"schema_version": 1, "tiers": {...}, "defaults": {...}, "cases": [...]}`. A case:

| field | meaning |
| --- | --- |
| `id` | unique, `kebab-case` |
| `question` | exactly what the tested agent is asked; relative dates are UTC |
| `kind` | `forecast`, `observation`, `discovery`, `glossary`, `licence`, `interpolate`, `summarize`, `alerts`, `stripes`, `history`, `coverage`, `unanswerable`, `units` |
| `max_steps` | most calls of the server's tools; generous but meaningful (6 for a forecast by place, 4 for a glossary or licence question) |
| `checkpoints` | ordered `{id, description, match: [alternative, ...], any_order?}`; the first is required to pass; `any_order` is met by any call of the run |
| `forbidden` | `{id, description, kind: call, match, window_days_over?}`, `{kind: repeat, tool, max_identical}`, `{kind: answer, regex}` |
| `facts` | `{id, description, kind, ...}`, the kinds above, each with the fields its kind needs |
| `tiers` | the tiers expected to pass; the first full run calibrates them |
| `needs_key` | true if the network needs credentials; skipped by default |
| `notes` | what the case caught, and traps for the judge |

A **match** is `{"tool": name | [names], "args": {...}, "ok": true | "any"}`. An argument rule is a literal (equal, ignoring
case; a list, or a comma-separated string, matches when any element does), `{"any_of": [...]}`, `{"regex": "..."}`,
`{"between": [lo, hi]}`, `{"contains_date": "YYYY-MM-DD"}` (a `timestamp` whose span holds that day), `{"present":
true}` or `{"absent": true}`. A `window_days_over` rule counts a call without a `timestamp` as unbounded. Provider,
network, parameter and period literals must exist, which the offline test holds to the code: another valid path is a
new alternative with literals, not a regex. A checkpoint accepts every valid path (any provider and network that serves
the question, a name or a point, a window that holds the day), because a case that insists on one path fails a model
that answers well.

## Permissions to add (for the owner)

The skill never edits `.claude/settings.json`. A run asks for each of these the first time; to avoid the prompts, add them
to your own `.claude/settings.local.json` (or user settings), not to the project's:

- `Bash(python3 -I .claude/skills/mcp-benchmark/scripts/bench.py *)` and
  `Bash(.claude/skills/mcp-benchmark/scripts/run_subject.sh *)` (headless; the script starts `claude -p`, which uses
  your login for the model),
- `mcp__claude_ai_wetterdienst__*` (your ground-truth calls; `mcp__wetterdienst__*` for a self-hosted server),
- `Agent` (subagent mode) and `Write` for the scratchpad directory (prompts and the results file).

`allowed-tools` in a skill's header grants a permission for the turn only and is not documented to reach a
subagent, so the skill does not use it.

## Adding a case

Append to `cases.json`, run `uv run pytest tests/ui/test_mcp_benchmark_cases.py`, then run the case with both tiers
and `repeats=3` and read the transcripts before trusting the `tiers` you gave it. A change to a case changes its hash
and takes it out of the next comparison, as it should. Docs: `docs/contribution/mcp-benchmark.md`.
