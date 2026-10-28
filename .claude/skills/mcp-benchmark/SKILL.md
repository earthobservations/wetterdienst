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
| `label` | what tells this side apart when two servers report one version (local `main` and a branch both say 0.178.0): the SHA of the checkout it serves, `+dirty` if it has changes; given to `probe`/`run` and kept in the results; `compare` refuses two sides with one version and one label | none |
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
own transport; `bench.py probe <url>` gives its `serverInfo` (the wetterdienst version) and is run first, which
records the version of the server under test. The login of the person who runs it pays for the model; no provider
credential is passed.

`run_subject.sh` is a wrapper of `bench.py run`, which **fails fast** instead of scoring a dead server as a model failure:
exit 2 for a bad argument (a model, name or URL with characters it will not pass on, a prompt file that is not there, no
`claude` on the PATH), exit 3 when the MCP URL does not answer or lists no tool, 124 after `MCPBENCH_TIMEOUT` seconds
(default 300; `claude` has no `--max-turns`), and `claude`'s own code otherwise. `--max-budget-usd` (`MCPBENCH_MAX_USD`,
default 0.50) was tried with 0.001 USD: the run stops after its first turn with `subtype: error_max_budget_usd` and a
`tool_use` no result answered (a step that reads nothing). The script removes its temporary directory and the project
directory Claude Code makes for it in `~/.claude/projects` (an empty `memory/`, or the file a too large result is saved
in); `bench.py cleanup` sweeps what an interrupted run left. A transcript whose init record shows the server not
connected, or with none of its tools, is **`invalid`**: it is left out of every rate, counted, printed by `report`, and
`compare` refuses a file with more than 3 % of them.

**Results above the limit of Claude Code are saved to a file** the subject cannot open (it has no Read tool): the
transcript holds a notice (`result (358,696 characters) exceeds maximum allowed tokens ... saved to ...`), measured on the
full stations list of DWD. 31,000 characters came through whole; the limit lies between that and 358,000. `bench.py` reads
the real size out of the notice (`result_chars`, `spilled_calls`), so the size metrics are true; the call is `spilled` and `ok: false` whatever `is_error` says, and a run whose answer
depended on such a result failed to read it, which is what happened to it. `report` and `compare` print the spilled
calls; a short result that talks of a saved file in other words is counted as `spill_unrecognised` and **warned about** in the
report: the notice is not a documented format, and a change of it would otherwise make the sizes look small.

**`mode=subagent`** spawns the subject with the Agent tool: `subagent_type: mcp-benchmark-subject`
([.claude/agents/mcp-benchmark-subject.md](../../agents/mcp-benchmark-subject.md), `tools:` limited to ToolSearch
and the wetterdienst tools; the wildcard form `mcp__server__*` in `tools:` is what the Claude Code documentation shows for agents, but no run could try it here; a new agent file is only picked up when Claude Code is started anew, and if the type is
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

**What the benchmark cannot see: the `outputSchema`.** The hosted `tools/list` is about 260,000 characters, of which
about 210,000 are `outputSchema`, 39,000 `inputSchema` and 10,000 descriptions (`bench.py tools-size`, measured 2026-10-28,
0.178.0). The context of the tested agent at its first request is 26.5k tokens, which only fits if Claude Code does not
send the `outputSchema` to the model. A change that slims the output schemas therefore shows in `tools-size` and not in
`context_tokens_first`; a change to the input schemas or the descriptions shows in both. Run `tools-size` for each side
of a comparison and record it (`tools_list` in the results file), so the wire cost the benchmark cannot see is on the page.

## Protocol

1. **Load.** Read `cases.json`; select cases and tiers. Make sure you can call the MCP tools of the `reference`
   yourself (load them with ToolSearch if they are deferred), and that `claude` runs (`claude --version`,
   headless). Record today's date in UTC, the model you are, `python3 -I scripts/bench.py hashes`, and for the server
   under test `bench.py probe <url>` and `bench.py tools-size --server <url>`. A server that does not answer ends the run
   here, before a model is paid for. Pass `--label <sha>` to `probe` and to every `run` for a local server.
2. **Run**, per case, tier and repeat (at most 4 at once; use `run_in_background` for Bash):
   - write the prompt: `python3 -I .claude/skills/mcp-benchmark/scripts/bench.py prompt <case-id> --today <date>
     > <scratchpad>/mcpbench-<case>-<tier>-<n>.prompt` (add `--tools "the tools named mcp__...__*"` in subagent mode);
   - headless: `.claude/skills/mcp-benchmark/scripts/run_subject.sh <haiku|sonnet|opus> <server url> wetterdienst
     <prompt file> <scratchpad>/mcpbench-<case>-<tier>-<n>.jsonl`; subagent: Agent with the prompt as its prompt.
3. **Analyze** each transcript: `python3 -I .../bench.py analyze <transcript> --case <id> --server <prefix>`, where the
   prefix is `mcp__wetterdienst__` (headless) or the one you gave (subagent). It counts, from the transcript and not
   from what the agent says of itself: `steps` (calls of the server's tools only), `tool_searches` (not a step), any
   other tool called (Bash, WebFetch, Read, Write, Agent, ...: each is a violation), the ordered checkpoints, the
   forbidden calls, repeats and answers, the size of the tool results (a result saved to a file counts by its real
   size), the output tokens, the context at the first and last request, the resolved model id, whether the run is
   `invalid` (no server), and the server version read from the results' JSON. A call no result answered is a step,
   `ok: false`, and meets no checkpoint; a result saved to a file is `spilled`, `ok: false`. Headless runs also leave
   `<transcript>.meta.json` (the probe's `serverInfo`, the wetterdienst version, the label, the `claude` version, the
   mode), which `analyze` prints as `run_meta`: copy it into the results `meta`, so that even a run of the glossary (no
   metadata block in its answer) says which server it ran on. A subagent transcript with none of the server's tools in it
   (listed, deferred or called) is `invalid` as well. Do not recount these yourself.
   A run that never ran because the server did not answer or listed no tool (`run_subject.sh` exit 3, or any failure to
   start) is recorded with `bench.py failed-run --case <id> --tier <t> --repeat <n> --reason "..."`: an `invalid` run with
   its reason, which the rates leave out and `report` counts. **A timeout (exit 124) is a failed run, not an invalid one**
   (`--kind failed --reason timeout`): a strategy that makes the model slower must show as a failure, not disappear. The
   timeout is capped at 540 s (`MCPBENCH_TIMEOUT`), under the 10 minutes `cleanup` waits for, since appending to a file does
   not move the mtime of its directory. A budget stop (exit 1, `end: error_max_budget_usd`) is a failed headline, not invalid.
   **Replacing runs.** One invalid run in 140 must not stop a comparison: `compare` keeps, for every case, only the repeats
   that are valid on **both** sides (an invalid or missing cold first repeat on one side takes that repeat out of the other
   too; it says how many runs it left out; a case that keeps under 60 % of the `repeats` makes the tier INCONCLUSIVE and
   names which side lacks them) and refuses above 3 % invalid **or missing** (a repeat of 1..`repeats` with no record at
   all counts as missing, so a timeout that was never recorded cannot shrink a side unseen). Repeats are numbered
   1..`repeats` in the results file; both files must be made with the same `repeats`, and a repeat outside the range or given
   twice for a (case, tier) is an error. To replace a run, do what the protocol does for any run: `bench.py run` with **the same arguments as the others**
   (the prompt from `bench.py prompt`, the model, `server`, `--label`), `analyze` it, judge it, write the judged record as JSON
   and `bench.py add-run --results FILE --run RUN.json` (or the record of `failed-run`, which carries its `kind`, for a run that
   timed out or found no server). `add-run` replaces the record of that (case, tier, repeat) or adds it, exits 2 with a
   message on every refusal, and refuses: a missing field or one of the wrong type (a string for a boolean or a repeat,
   `checkpoints` that is not `{k, n}` of integers, `violations` that is not a list, no `model`), a repeat above the file's
   `repeats`, an unjudged record, a case that is not in the file, a record whose `run_meta` (label, server version, model, mode,
   prompt template, prompt date) differs from the file's `meta`, a record that declares `kind` failed or invalid and still
   claims an answer (`passed`, `facts_ok`, `is_answer` true), and a replacement of a valid run (unless `--replace-valid`).
   It takes a lock on `<file>.lock` and writes through a temporary file and `os.replace`, so several `add-run`s at once (one
   per repeat that is filled in) keep all their records; it needs `fcntl`, that is macOS or Linux (the benchmark is run on
   those; Windows is not supported). There is no automatic re-run: a re-run needs the same prompt, date, model and server as the first, and the judge's verdict.
4. **Judge** what needs reading, per run (below), then write the results file, print the table with
   `bench.py report`, and the comparison with `bench.py compare <previous> <results>` when `previous` is given.

## What you judge

The script has given `steps`, the checkpoints, the violations and `mechanical_pass` (1 to `max_steps` steps and the
**first checkpoint met**, and the run valid), and for a `network_serves_place` fact its verdict (`mechanical_facts`,
read from the stations the subject itself got listed, not from a call of yours). You add:

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
read, not a later one; checked 2026-10-28: `alerts` with `timestamp` set to the `data_updated_at` of a snapshot returned that snapshot's warnings). A source that publishes with a delay may hold fewer days than asked: take the span over
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
`bench.py unit`. **The prompt asks for the structured part**, which is all the check reads: the answer ends with one line
`RESULT: <number> <unit> | <what it is>` for each figure the question asks for (for a forecast, one per temperature named) and
**none for any other figure**, and, for a table or CSV block, `TABLE-UNIT: <column> | <unit>` for each column that has a unit. The example in the prompt is
made up (a wind speed at a place no case asks about); a test holds it to passing no case. The check is strict and
deterministic: no sentence parsing, no table heuristics.

**The rule for a single value.** The prompt asks for a RESULT line for the figure(s) the question asks for, and for no
other; the check does not depend on how many extra figures a model adds (a count of extra lines would otherwise change with
every token strategy that makes the model terser or wordier). The answer passes when a RESULT line gives the value in one of
the fact's accepted units, and fails when a line:
- gives the value in a **forbidden** unit (kelvin: `-0.7 K`, `293 K` where it fits);
- gives the value **in the unit it was read in, written with another accepted unit** (`0.84 %` for 84 %, `15.5 cm` for
  15.5 mm, `-0.7 °F`): whatever it is called, this is the unit error the units cases exist for;
- gives a figure that is not the value in its unit (`value * factor + offset` within the fact's `tolerance`, or within the
  rounding of the figure as written, half a unit of its last digit, in any accepted unit: `2 cm` is 15.5 mm rounded,
  `20 mm` is not, `6 kn` is 3.0 m/s rounded, `7 kn` is not) **and** calls it the asked quantity: its description matches
  one of the fact's `asked_descriptions` (regexes: `mean`, `precip`, `humidity`, the day of the row) and none of its
  `ignore_descriptions` (the same words for another quantity, day or station: a minimum, a dew point, the day before, another
  date, a gust). A fact for a forecast has no `asked_descriptions`: every description is a claim unless it is ignored (a
  minimum, an overnight low, another day).
Any other line is the model's own addition and fails nothing by its wording: `RESULT: 1.2 °C | daily max`, `RESULT: 5 days |
window`, `RESULT: 11 km | distance`, a restatement in another accepted unit (`4.1 h` next to `14821 s`). A line in a unit the
case does not know neither fails nor passes. The answer still needs a line that is the value, and when it has neither a right
line nor a failing one the verdict says so (`no figure of the answer is the value in one of the accepted units`). The lists
are tried against the strings they must and must not match in the tests; a description the lists do not foresee is not a
claim, so the check errs towards passing a hedge that is worded in a way nobody foresaw rather than failing a right
answer for its wording (the 38 answers of the round-7 review are in the tests).
For a **forecast** (a span) a figure with an accepted unit outside the span counts as not the value. A figure of fewer than two
significant digits gets no rounding in the unit the value was read in when the value has two or more digits (`1` is not 0.8404
as a fraction); in another unit or for a one-digit value it is rounding (`4 h` for 4.12 h, `-1 °C` for -0.7). A column's
`TABLE-UNIT` must name one of the unit tokens. **A fact with a `column` and a `row` holds every table of the answer to the
value in the column its `column` regex names (`precip`, which also takes `precipitation`, or `value`, the column of the
tool's own CSV) and in the row of its `row` (a day, found as `2026-10-16`, `16.10.2026`, `16/10/2026`, `16 Oct 2026` ...)**,
with a `TABLE-UNIT` line or without, and with a fitting RESULT line or without; a RESULT line for the value is accepted when
the answer has no table.

**The unit slot** forgives slips: a trailing point, a remark in brackets (`°C (as returned)`, `mm (millimetres)`,
`degrees Celsius (°C)`), `℃`, `ºC`, `m s⁻¹`, `%RH`, bold, bullets, numbered markers, quotes, fences, any case.

**What counts as a malformed line, and what then.** A line that starts `RESULT:` and a number but gives no unit, or does not
parse, is *malformed*: it is a format violation, and it is ignored. If **any** well-formed RESULT or TABLE-UNIT line exists,
the strict rule applies to those lines alone (a malformed line does not make the rest lenient). Only an answer with **no**
well-formed line is read by the **fallback**.

**The fallback** reads tolerantly: prose (the unit directly after the figure, in brackets, as `(unit °C)`, in brackets before
it on its line, or alone on the line above), real tables (a markdown table, or two or more lines of the same cells with a
separator row or a header without a digit; prose with commas is no table) by column, with the unit in the cell, the header, a
`Unit` column, the row label or a sentence around it, and the same span rule for tables. For a fact with a `column` and a
`row` it too reads only the column named (leniently about the header's spelling: if no header matches, any column) and the
row of the date. It is reported as `unit_fallback`.

**`format_violation`** is computed by `bench.py` from the final answer of every run (`analyze` prints it; do not set it by
hand): for a case with a `unit` fact it is true if the answer has no well-formed `RESULT:`/`TABLE-UNIT:` line, or any malformed
one; a case without a unit fact has `null`, and a prose line `Result: yes` is no RESULT line. The rate (printed as `format
violations k/n` over the runs of the cases that ask for the format, and compared as "follows the RESULT format" like the other
rates) is a metric of its own, not a silent pass, so that a token strategy that confuses the model shows up. Because the prompt
changed, **results files from before it are not comparable** (`compare` refuses on the prompt hash).
A pair marked `required` (Fahrenheit, when the question asks for it) must be there. The checkpoint `gets-the-unit`
(`any_order`: before or after the values) lists the valid routes to the unit; the first checkpoint, reading the values, is
the one required to pass.
A strategy that drops units from the default answer must pass them some other way, or these cases fail.

**Reference `python`.** When you cannot reach a pinned server, read ground truth from the library of this checkout in a
Bash call, e.g. `uv run python -I -c "from wetterdienst import Wetterdienst; ..."` with
`Wetterdienst.resolve(provider, network)(parameters=..., ...).filter_by_station_id(...).values.all()`. It is
independent of the MCP layer (a change to the tools or their answers does not reach it) but not of the library.

**Four rates, not one.** `passed` is the answer-reached headline (an answer within `max_steps`, from at least one call,
after the first checkpoint). It says nothing of whether the answer is right or what the agent did on the way: an answer
from the wrong data can still pass. `facts_ok`, the violations (the share of runs with none) and the format (the share that follow it, over the cases that ask
for it) are therefore compared as rates of their own, and a change is "no worse" only if all four are (see "Comparison").

## The results file

Write `mcpbench-results-<YYYYMMDD-HHMM>.json` to your scratchpad directory (the one the system prompt names; never
into the repository, never committed). `bench.py report` and `compare` read it.

```json
{"meta": {"date": "2026-10-28", "mode": "headless", "models": {"small": "haiku", "large": "sonnet"},
          "judge_model": "<the model you are>", "server": "<url or prefix>", "server_version": "0.178.0", "label": "<sha of the checkout, +dirty>",
          "reference": "<prefix or python>", "reference_version": "0.178.0", "claude_version": "2.1.308",
          "tools_deferred": false, "context_note": "<what remains in the context, per mode above>",
          "repeats": 5, "cases_file": "<hash>", "defaults": "<hash>", "logic": "<LOGIC_VERSION of bench.py>", "prompt": "<hash>",
          "case_hashes": {"<case id>": "<hash>"}, "server_info": {"name": "Wetterdienst", "version": "0.178.0"},
          "tools_list": {"description": 9877, "inputSchema": 39311, "outputSchema": 210404}},
 "runs": [{"case": "...", "tier": "small", "repeat": 1,
           "...": "everything `bench.py analyze` printed, without `result_head` (`invalid`, `model`, `spilled_calls`, ...)",
           "is_answer": true, "passed": true, "facts_ok": true,
           "fact_results": {"<fact id>": "ok | fail: <why> | drift: <how>"}, "judge_note": ""}]}
```

## Output

Print `bench.py report`: per (case, tier) `passed k/N`, steps median/max against the limit, checkpoints met out of
possible, violations, `facts ok k/N`, the median size of the tool results (characters), the median output tokens, the
median context tokens at the first request and the median total tokens, then one pooled row per tier, and the number of
invalid runs left out. Under it: the cases that failed their headline, the cases where a tier that `tiers` expects to
pass did not (the model is behind what the case expects) or one that is not expected to did (the case may be too easy
now), and the path of the file.

**Comparison.** `bench.py compare previous results` is a **non-inferiority** claim, not a search for a difference. It
**refuses** (prints why and exits with code 4) when the logic version of `bench.py`, the `defaults` of the cases file, the
prompt, the **mode** (headless or subagent) or whether the tools were **deferred** differ, when the two sides cannot be
told apart (one server version and one `label`; `--same-server` compares two runs of one server), when the two files were made
with a different number of `repeats` or hold a repeat outside 1..`repeats` or twice, or when more than 3 % of the runs of the
*compared* cases are invalid or missing. It compares only the (case, tier) whose case hash is unchanged and
says how many it left out (only in the current file, with a changed case, only in the previous file); a tier whose
resolved model ids differ is not compared; it refuses a file with a run still marked `needs_judging`. Every case is first
cut down to the repeats that are valid on both sides (`_equalise`: paired by `repeat`, no pseudo-counts, so that pooling uses
real counts, weights the cases alike, and an invalid or missing first repeat on one side cannot bias the other); a case that
keeps under 60 % of the `repeats` makes the tier INCONCLUSIVE with the reason (the valid runs of each side, so that it is clear
which side lacks them). Per tier, pooled, it decides for each of four rates (passes, facts, share of runs with no violation,
share that follow the RESULT format) the difference of the new minus the previous with its 95 % Newcombe interval, as **one**
non-inferiority decision: **no worse** if the lower bound is above minus 10 percentage points, **WORSE** if the upper
bound is below minus 10 points (the drop is shown to be larger than tolerated), **inconclusive** otherwise; a drop that is
real but within the margin is "no worse (a drop, lower but within the margin)", and one whose whole interval is below zero
but not beyond the margin says "likely worse, more runs would decide". The tier is `NO WORSE` only if all four are, `WORSE`
if any is. A case whose own rate fell by 40 points or more is printed with its counts whatever the pooled verdict says.
Each decision has a one-sided error of 2.5 %, so about 10 % per tier that one of the four is wrong in the same direction;
the per-case Fisher tests are **hints** only (little power at 5 runs). The format rate is left out, with a line saying so,
when either file has no run of a case that asks for the format.
Not finding a difference is not "no worse": at a pass rate of 90 % it takes about 140 runs per side to show a margin of
10 points (`required_runs`, printed for each rate, the largest decides), and the default full run is 27 cases, 135 runs a side per tier at 5 repeats, 270 in all
(`needs_key` cases are skipped by default, so London is not in it), about enough at 90 % and not enough at 80 %. Steps, tool-result characters, context
tokens at the first request, total and output tokens, and the calls whose result was saved to a file are printed as the
median per case before and after and the paired difference. A token-efficiency change is "no worse and smaller" when
all four rates are `no worse` and the sizes fell; the model, server, reference and Claude Code versions that differ
are told first.

## Local server: comparing a change before release

The hosted server is the released one. To judge a change, run **both sides on local servers in the same environment, with
the same limits and cache**, not only against the hosted one: a baseline of the hosted server differs from a local
`main` by the host, the network and the deployed settings.

```bash
# the same cache for both sides (and warm it with one run before the baseline)
export WD_CACHE_DIR=$HOME/.cache/wetterdienst-mcpbench
# baseline: main, in its own worktree and port
git worktree add ../wd-main main && cd ../wd-main
uv sync --python 3.13 --extra restapi --extra mcp --extra export --extra interpolation --extra sql   # one extra at a time on macOS if it fails
uv run --python 3.13 wetterdienst restapi --listen 127.0.0.1:7891        # MCP at http://127.0.0.1:7891/mcp/v1
# the change: the PR's branch, in another worktree and port
git worktree add ../wd-pr my-branch && cd ../wd-pr
uv sync --python 3.13 --extra restapi --extra mcp --extra export --extra interpolation --extra sql
uv run --python 3.13 wetterdienst restapi --listen 127.0.0.1:7892        # MCP at http://127.0.0.1:7892/mcp/v1
```

Then `/mcp-benchmark server=http://127.0.0.1:7891/mcp/v1 label=$(git -C ../wd-main rev-parse --short HEAD) repeats=5` for the
baseline and the same with `:7892`, the SHA of the branch (`+dirty` if `git status` is not clean) as the `label`, and
`previous=<the baseline's file>` for the change: the two servers report one version, and the labels are what tells the files apart. `server=` takes any such URL in headless mode (the URL is checked
with `bench.py probe` first). Both servers are started with the same `WD_CACHE_DIR` (exported above), since a cold cache
changes the time and sometimes the answer; keep `reference=` the released hosted server for both, so the judge's ground
truth does not move with the change. Tried 2026-10-28: a local `wetterdienst restapi --listen 127.0.0.1:7890` from a
worktree answered `probe` with the same 14 tools and `tools-size` as the hosted 0.178.0, and a headless run of the glossary
case against it passed (1 step, 26.5k context tokens). Stop the servers when done.

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
`{"between": [lo, hi]}`, `{"on_date": "YYYY-MM-DD"}` (a `timestamp`, a date, an instant or an interval of them, that reaches into that day), `{"present":
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
