---
name: mcp-benchmark
description: Manual benchmark of the Wetterdienst MCP server. Spawns one fresh subagent per question and model tier, lets it answer with the wetterdienst MCP tools only, and judges whether an answer is reached within a number of tool calls, which intermediate steps it took, what it must not do and whether the facts are right. Run by a person only, never by CI or on a schedule. Costs tokens (about 2 subagent runs per case) and calls the live providers.
argument-hint: "[cases=<ids|kind:..|all>] [tiers=small,large] [large=sonnet|opus] [previous=<results.json>] [include_keys=1]"
disable-model-invocation: true
---

# MCP benchmark

You are the **orchestrator and judge**. You test whether a model, given only the Wetterdienst MCP tools,
reaches a correct answer within a number of steps. It is not a test suite: nothing here runs in CI, and
`pytest` never collects it. The cases are data in [cases.json](cases.json); an offline test,
`tests/ui/test_mcp_benchmark_cases.py`, keeps them true to the code without calling a model.

It costs tokens (a subagent per case and tier, plus your own ground-truth calls) and sends requests to the
live providers, so run what you need: a few cases with `cases=glossary-temperature-air-mean-2m,licence-dwd`
is a smoke run, `all` is the full set. Keep the load modest: never more than 4 subagents at once.

## Arguments (`$ARGUMENTS`)

All optional, `key=value`, separated by spaces:

| key | meaning | default |
| --- | --- | --- |
| `cases` | case ids separated by commas, `kind:<kind>` for all cases of a kind, or `all` | `all` |
| `tiers` | `small`, `large` or `small,large` | `small,large` |
| `large` | the model of the large tier: `sonnet` or `opus` | `sonnet` |
| `previous` | path of an earlier results file to compare with | none |
| `include_keys` | `1` to run the cases marked `needs_key` | skipped |

The small tier is `haiku` (`tiers.small` in the cases file). The `model` parameter of the Agent tool takes
`haiku`, `sonnet` or `opus`. A case with `needs_key: true` is skipped unless `include_keys=1`, and then only
if `coverage` reports the network as `configured`. Never set, ask for or pass a credential.

## Protocol

1. **Load.** Read `${CLAUDE_SKILL_DIR}/cases.json`. Select the cases. Make sure you can call the wetterdienst
   MCP tools yourself (`mcp__claude_ai_wetterdienst__*`, or `mcp__wetterdienst__*` on a self-hosted server;
   load them with ToolSearch if they are deferred): you need them for the ground truth. If you cannot, stop
   and say so. Note today's date, as every relative date of a question is judged from it.
2. **Run.** For each selected case and tier spawn **one fresh subagent** (Agent tool, `subagent_type`
   `general-purpose`, `model` of the tier). It gets only the prompt below, with `{today}`, `{question}` and
   `{max_steps}` filled in: nothing else of this skill, the case, the checkpoints or the repository. One
   subagent, one case: never reuse an agent for a second question.
3. **Judge** each returned log yourself, as described below. The tested agent never judges itself.
4. **Report**: the table, the results file, the comparison.

### Prompt of the tested agent

```
Today's date is {today}. Answer this question using ONLY the wetterdienst MCP tools (the tools whose names
contain "wetterdienst": alerts, auth, coverage, glossary, history, interpolate, issues, providers, stations,
stripes_image, stripes_stations, stripes_values, summarize, values). If they are deferred tools, load them with
ToolSearch first; that is not a step. Do not use the web, Bash, file tools, the repository or your memory
of weather facts.

Question: {question}

Rules:
- A step is one call of a wetterdienst tool. You have at most {max_steps} steps. When you have used them
  and still have no answer, stop, say so, and give no number you did not read from a tool result.
- Do not invent numbers. Every figure in your answer must come from a tool result.
- When a tool returns an error or no rows, say so in your log and decide what to do next; do not hide it.
- Finish with a JSON object and nothing after it:
  {"calls": [{"n": 1, "tool": "<tool name without prefix>", "arguments": {<exactly as you sent them>},
              "ok": true|false, "error": "<one line, or null>",
              "note": "<one line of what came back: row or station count, first and last value with timestamp>"}],
   "answer": "<your answer to the question in 1 to 3 sentences, or empty if you reached the limit>",
   "tool_searches": <how many times you called ToolSearch to load tools, 0 if none>,
   "reached_answer": true|false, "stopped_at_limit": true|false}
```

### What you judge

For each log, in this order. Read the case's `checkpoints`, `forbidden` and `facts` from the file; the schema
is below.

1. **Answer reached within `max_steps`** (the headline, `passed`). `steps` is the number of entries of `calls`.
   The harness reports a tool-use count for the agent: it should be `steps + tool_searches`. When it is larger
   the agent made calls it did not log: set `log_mismatch` and take `steps` as the count minus `tool_searches`. Passed means `reached_answer` is true, `steps <= max_steps`, and the answer is an answer:
   a refusal, a request for clarification or a hand-off to the person is none, unless the case's `kind` is
   `unanswerable`, where saying there is no data is the answer.
2. **Checkpoints**, ordered, not necessarily contiguous. Walk the checkpoints in order; for each find the first
   call at or after the call of the previous checkpoint that matches one of its `match` alternatives. Count
   `k` of `n`, and name the first checkpoint missed. A missed checkpoint does not stop the walk. A call
   counts only if it was `ok`, unless the match says `"ok": "any"`.
3. **Forbidden behaviours**, each a violation: `call` (a call matches, and, with `window_days_over`, its
   `timestamp` interval is longer than that many days), `repeat` (more than `max_identical` calls of the tool
   with identical arguments), `answer` (the answer matches the regex).
4. **Facts**, checked against ground truth **you** obtain with your own calls (they are not steps of the
   tested agent). Never copy a number from the case file: `expected` there only lets you see that the source
   has drifted, and you say so when your own call differs from it by more than `tolerance`.
   - `answer_regex`: the answer matches one of `any_of`.
   - `ground_truth_value`: make the call of `ground_truth`, pick what `pick` says, and check the number the
     answer gives is within `tolerance` of it.
   - `ground_truth_span`: make the call; every temperature the answer gives lies in `[min - margin, max + margin]`
     of the series it returns, and inside `sanity`. For time-dependent data this is the only check.
   - `ground_truth_text`: make the call; the answer carries what `pick` says, written as one of
     `answer_matches_any_of` (regexes) allows.
   - `ground_truth_subset`: every name the answer gives is in your call's result.
   - `no_measurements`: no figure in the answer that no `note` of the log supports.
   In `ground_truth` arguments, `$answer_station` is the station id the answer names (read it from the log:
   the one the answer's value came from), `$yesterday` is yesterday's date, and `$last_7_days` the 7 days up to
   and including yesterday as `YYYY-MM-DD/YYYY-MM-DD`. Apart from the case's own facts, one rule holds for
   every case: a number in the answer that appears in no `note` of the log counts as invented, and fails
   `facts_ok`.
5. **Tokens and steps used**, as the harness reports them for the agent (tool uses, tokens, duration). Put
   them in as they are, or `null` if it reports none.

Be strict about what is a call match and lenient about wording. When a checkpoint is a near miss (the right
tool with a better argument than the one listed), record it in `judge_note` and do not count it.

### Output

Print a markdown table, one row per case and tier, and nothing that looks like a verdict beyond it:

| case | tier | passed | steps/max | checkpoints | violations | facts ok |
| --- | --- | --- | --- | --- | --- | --- |
| glossary-temperature-air-mean-2m | small | yes | 1/4 | 1/1 | 0 | yes |

`checkpoints` is `k/n`, with the first missed one named in brackets when `k < n`, `violations` the count with
ids when not zero. Below it: pass counts per tier, the cases that failed the headline, and the cases where a
tier that `tiers` expects to pass did not (the model of that tier is behind what the case expects) or one
that is not expected to did (the case may be too easy now).

Write the full results to a JSON file in your scratchpad directory (the one the system prompt names; never in
the repository), named `mcpbench-results-<YYYYMMDD-HHMM>.json`:

```json
{"date": "2026-10-28", "wetterdienst_version": "<from a metadata block>", "models": {"small": "haiku", "large": "sonnet"},
 "results": [{"case": "...", "tier": "small", "passed": true, "steps": 2, "max_steps": 4,
              "checkpoints": {"k": 2, "n": 2, "first_missed": null}, "violations": [], "facts_ok": true,
              "fact_results": {"id": "ok|fail|drift: ..."}, "log_mismatch": false, "judge_note": "",
              "usage": {"tool_uses": 2, "tokens": 18000, "duration_s": 21}, "log": {}}]}
```

Tell the person the path. When `previous` is given, read that file and add one line per difference by
(case, tier): headline flipped, steps changed by 2 or more, checkpoints `k` changed, a violation appeared or
went, facts flipped; and one summary line (`N cases compared: A regressed, B improved, C unchanged`). A model
or version that differs between the two files is said first, as it explains most differences. Do not commit
a results file; do not open a pull request or an issue from a run.

## Case schema

`cases.json` is `{"schema_version": 1, "tiers": {"small": "haiku", "large": "sonnet"}, "cases": [...]}`. A case:

| field | meaning |
| --- | --- |
| `id` | unique, `kebab-case` |
| `question` | exactly what the tested agent is asked; relative dates ("yesterday") are judged from the run's date |
| `kind` | `forecast`, `observation`, `discovery`, `glossary`, `licence`, `interpolate`, `summarize`, `alerts`, `stripes`, `history`, `coverage`, `unanswerable` |
| `max_steps` | most wetterdienst tool calls an answer may take; generous but meaningful (6 for a forecast by place, 4 for a glossary or licence question) |
| `checkpoints` | ordered list of `{id, description, match}`; `match` is a list of alternatives, one of which a call must satisfy |
| `forbidden` | list of `{id, description, kind: call|repeat|answer, ...}` |
| `facts` | list of `{id, description, kind, ...}`, the kinds above |
| `tiers` | the tiers expected to pass (`small`, `large`); the first full run calibrates them |
| `needs_key` | true if the network needs credentials; skipped by default |
| `notes` | what the case caught, and traps for the judge |

A **match** is `{"tool": "<name>" | ["<name>", ...], "args": {...}, "ok": true | "any"}`; `tool` must be a tool
of the server, `args` names only arguments of that tool. An argument rule is a literal (equal, ignoring case;
an argument that is a list, or a comma-separated string, matches when any element does), `{"any_of": [...]}`,
`{"regex": "..."}`, `{"between": [lo, hi]}` (numbers), `{"present": true}` or `{"absent": true}`. `provider`,
`network` and `parameters` rules that are literals name things that must exist, which the offline test holds
to the code: when a case has to name another one, it is a new alternative, not a regex.

## Permissions to add (for the owner)

The skill never edits `.claude/settings.json`. A run asks for a permission per tool the first time; to run it
without those prompts, add to your own `.claude/settings.local.json` (or user settings) an `allow` list with:

- `mcp__claude_ai_wetterdienst__*` (the hosted connector; `mcp__wetterdienst__*` for a self-hosted server),
- `Agent` (the subagents), and
- `Write` for the scratchpad directory (the results file).

`allowed-tools` in a skill's header grants a permission for the turn only, and the documentation does not say
that it reaches a subagent's calls, so the skill does not use it. The tested agent is held to the wetterdienst
tools by its prompt, not by a permission: a call it makes to anything else shows up as a tool-use count above
its logged calls plus `tool_searches`, which you record as `log_mismatch`.

## Adding a case

Append to `cases.json`, run `uv run pytest tests/ui/test_mcp_benchmark_cases.py`, then run the case once with
both tiers and read the log before trusting the `tiers` you gave it. Docs: `docs/contribution/mcp-benchmark.md`.
