# MCP benchmark

A manual benchmark of the [MCP server](../../docs/usage/mcp.md): does a model, given only the Wetterdienst tools, reach
a correct answer within a number of steps, through which steps, and is that still so after a change to the server (a
slimmer schema, a smaller answer)? It is not a test suite. **It is run by a person (or a Claude Code session the person
tells to), never by CI or on a schedule**, it costs tokens (one tested model per case, tier and repeat) and it sends
requests to the live providers.

This file is the runbook. A fresh Claude Code session that is told only *"follow `benchmarks/mcp/README.md` for the smoke
run"* or *"... for the baseline"* has everything it needs here: do **Parts 1 to 6** in order, and **Part 7** whenever
something is unclear or breaks. Nothing of the benchmark is in `.claude/`: it is no skill and no slash command, and a run
writes nothing into the repository. **Until pull request #3544 is merged the benchmark exists only on its branch
`feat/mcp-benchmark-skill`, not on `main`**: a checkout of `main` does not have this file; Part 2.1 says how to get it.

| file | what it is |
| --- | --- |
| `README.md` | this runbook, and the rules of the judge |
| `cases.json` | the questions, with their steps, forbidden behaviour and facts (`tests/ui/test_mcp_benchmark_cases.py` holds them to the code, without a model) |
| `prompt.md` | what the tested model is told |
| `scripts/bench.py` | everything that is counted: runs the tested model, reads its transcript, aggregates, compares (standard library only; `tests/ui/test_mcp_benchmark_scripts.py` tests it) |
| `scripts/run_subject.sh` | a wrapper of `bench.py run`: one tested model, headless, in an empty directory |

## The two named runs

| | smoke | baseline |
| --- | --- | --- |
| what it is for | does the machinery work, end to end, and is the result worth 5 repeats | the numbers a later change is compared with |
| cases | all 27 that need no key (`--cases all`) | the same |
| tiers | `small` (Haiku) and `large` (Sonnet) | the same, `large` is `sonnet` unless you were told `opus` |
| repeats | 1 | 5 |
| runs | 54 | 270 |
| results file | `$BENCH/mcpbench-results-smoke.json` | `$BENCH/mcpbench-results-baseline.json` |

A tested model is stopped after 300 s and after 0.50 USD (`MCPBENCH_TIMEOUT`, `MCPBENCH_MAX_USD`), so a run costs at most
0.50 USD and the smoke run at most 27 USD, the baseline at most 135 USD. The real cost is far lower: a Haiku run costs about
0.005 USD, a Sonnet run about 0.06 USD on average (0.03 to 0.24), and the whole baseline of 270 runs cost about 8.3 USD for the
tested models (measured on 2026-11-12; the judge's own tokens are not included). The report prints the cost. Do **not** start the baseline after a smoke run, or the smoke run
after a baseline, unless your instruction asked for it: report and stop.

## Rules for the whole run

1. **Nothing in the repository changes.** Prompts, transcripts, the results file and the server's checkout go to the
   scratch directory (Part 2), never under `.claude/` and never into the repository. Do not edit settings or permission
   files, do not commit, do not stash. If a command is denied, stop and say which (Part 7).
2. **At most 3 tested models at once** (`bench.py batch` enforces it). This Mac cannot take more.
3. **No credential.** The cases that need a provider key (`needs_key`: one, London) are never run, and you never ask for,
   read or pass a key.
4. **GitHub: only comments on issue #3546 and one secret gist**, all through `gh` on `earthobservations/wetterdienst`
   (Part 5). Never close, label, merge or edit anything: **a comment of yours cannot be edited**; if one is wrong, post a
   short correction comment that says what was wrong and what is right.
5. **Stop processes by PID**, never by name (`pkill`, `killall`): the maintainer may have other servers running.
6. **When something is unclear or breaks, stop and ask** (Part 7); do not guess.

Shell state does not survive between your Bash calls: put the variables in `$BENCH/env.sh` (Part 2) and start each
command with `. "$BENCH/env.sh"`, or write the paths out. **The snippets run in bash and in zsh** (the Bash tool on a Mac
is often zsh): every variable is quoted and holds one word, and none holds several arguments, because zsh does not split an
unquoted `$ARGS` into words (a `judge` call built from `FACTS="--fact a=ok --fact b=ok"` breaks there). Write each argument
out in the command, as the snippets do.

## Part 1. Prerequisites

Check each; if one fails, stop and ask (Part 7).

| need | check | expected |
| --- | --- | --- |
| the `claude` CLI | `claude --version` | `2.1.311` or newer. The flags `run_subject.sh` passes were checked against the `claude --help` of 2.1.311: `--tools ""`, `--strict-mcp-config`, `--mcp-config`, `--allowedTools`, `--disable-slash-commands`, `--setting-sources ""`, `--no-session-persistence`, `--max-budget-usd`, `--output-format stream-json --verbose`. An older version, or a flag missing from `claude --help`, is a stop. |
| `python3` | `python3 --version` | 3.9 or newer (the Mac's own is enough: `bench.py` uses the standard library only and is run as `python3 -I`) |
| `gh`, authenticated | `gh auth status` | logged in to github.com with the scopes `repo` and `gist` |
| the issue | `gh issue view 3546 -R earthobservations/wetterdienst --json state -q .state` | `OPEN` |
| `git`, `uv`, `curl`, `lsof` | `uv --version` | present |
| Python 3.13 for the server | `uv python find 3.13` | a path (it may be the Python of a repository's `.venv`: that is fine). The server runs on **3.13** (`UV_PYTHON=3.13`): the free-threaded 3.14 fails to build polars. |
| a checkout of the repository to start from | `git rev-parse --show-toplevel` | a path; it need not have `benchmarks/mcp` (a checkout of `main` has not, until #3544 is merged): 2.1 makes the copy of the benchmark you use, `$REPO` |
| the port | `lsof -nP -iTCP:7891 -sTCP:LISTEN` | **no output**: if something listens on 7891, it is not yours: stop and ask |

## Part 2. Set up

**2.1 The scratch directory, the benchmark and `env.sh`.** Everything of the run goes under the scratch directory `$BENCH`:
**the one the person who started the run gave you, else `$TMPDIR`** (the user's temporary directory, on this Mac
`/var/folders/...`; fall back to `/tmp`) with the UTC date. It must have no space in its path. Run these from the checkout you
started in (any checkout of the repository):

```bash
BENCH="${TMPDIR:-/tmp}/mcpbench-$(date -u +%Y%m%d)"
mkdir -p "$BENCH"
git fetch origin feat/mcp-benchmark-skill
git worktree add --detach "$BENCH/repo" origin/feat/mcp-benchmark-skill
git -C "$BENCH/repo" rev-parse HEAD
ls "$BENCH/repo/benchmarks/mcp/README.md"
```

Replace `BENCH=...` by the directory you were given, if you were given one. The **detached worktree `$BENCH/repo` of the head
of the pull request is the copy of the benchmark you run**: it is `$REPO` below, and its SHA is "the runbook at ..." in
your comments. Once the pull request is merged, use `origin/main` instead of `origin/feat/mcp-benchmark-skill` (the
branch may be gone: `gh pr view 3544 -R earthobservations/wetterdienst --json state -q .state` says `MERGED`). If your
README is not the one in `$BENCH/repo/benchmarks/mcp/README.md` (you were started from another copy), read that one and follow it.
**`git fetch` can fail transiently (`Connection refused`): retry it once after 10 s; if it fails again, stop and ask.**

Then the variables, in one file (`LABEL` and `SERVER_VERSION` are added in 2.2):

```bash
printf 'export REPO="%s"\nexport BENCH="%s"\nexport UV_PYTHON=3.13\nexport WD_CACHE_DIR="%s"\nexport URL=http://127.0.0.1:7891/mcp/v1\n' "$BENCH/repo" "$BENCH" "$HOME/.cache/wetterdienst-mcpbench" > "$BENCH/env.sh"
cat "$BENCH/env.sh"
```

If `$BENCH` exists already (an earlier run of the same day), **do not reuse it blindly**: read what is in it, and either go
on with the results file in it (Part 3 resumes) or ask. `WD_CACHE_DIR` is the cache of the server under test, its own, so
that two sides of a comparison share one cache and the maintainer's other caches are untouched.

**2.2 The server under test: a local server of current `main`, in a git worktree outside the repository checkout.**

```bash
. "$BENCH/env.sh"
git -C "$REPO" fetch origin main
git -C "$REPO" worktree add --detach "$BENCH/wd-main" origin/main
git -C "$BENCH/wd-main" rev-parse HEAD
git -C "$BENCH/wd-main" status --porcelain
```

`git fetch` can fail transiently (`Connection refused`): **retry it once after 10 s; if it fails again, stop and ask.** The
worktree must be clean (no output from `status`). The SHA is the **label** of the run (add `+dirty` if `status` is not empty,
which it must not be); keep it in `env.sh` with the version of `main` once the server answers: Install, one command (a few minutes, about 800 MB;
if it fails on macOS, run the extras one at a time):

```bash
. "$BENCH/env.sh"
cd "$BENCH/wd-main" && uv sync --python 3.13 --extra restapi --extra mcp --extra export --extra interpolation --extra sql
```

Start it **in the background** (the Bash tool's `run_in_background`, or `nohup ... &` with the output in
`$BENCH/server.log`). The command, from `$BENCH/wd-main`, with `WD_CACHE_DIR` exported:

```bash
. "$BENCH/env.sh"
cd "$BENCH/wd-main" && exec .venv/bin/wetterdienst restapi --listen 127.0.0.1:7891
```

Wait for it (about 10 s), then check and record what you need:

```bash
. "$BENCH/env.sh"
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do curl -fsS http://127.0.0.1:7891/health && break; sleep 2; done
curl -fsS http://127.0.0.1:7891/api/version
lsof -nP -t -iTCP:7891 -sTCP:LISTEN > "$BENCH/server.pid" && cat "$BENCH/server.pid"
printf 'export LABEL="%s"\nexport SERVER_VERSION="%s"\n' "$(git -C "$BENCH/wd-main" rev-parse --short HEAD)" "$(curl -fsS http://127.0.0.1:7891/api/version | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')" >> "$BENCH/env.sh"
. "$BENCH/env.sh"
python3 -I "$REPO/benchmarks/mcp/scripts/bench.py" probe "$URL" --label "$LABEL"
python3 -I "$REPO/benchmarks/mcp/scripts/bench.py" tools-size --server "$URL"
```

`/health` answers `{"status":"OK"}`, `/api/version` the version of `main` (for example `0.186.0`), `probe` says
`"tools": 14`, and `server.pid` holds the one PID that listens: **that PID, and no other, is what you stop at the end**.
Note the SHA (`$LABEL`), the version (`$SERVER_VERSION`), and the `tools-size` table (it is the cost of `tools/list` on the wire, which the tested model's
context does not show: see "What the benchmark cannot see"). A server that does not answer ends the run here, before a model
is paid for.

**2.3 The reference for the ground truth.** The judge reads the true answer from a *reference*, never from the tested
model's own answers or from the server under test alone, so that a change that rounds or drops a value cannot reproduce itself
in the judge. Two choices:

- **`python` (the default, and the one to use unless told otherwise):** the command line and the library of the **same
  checkout** as the server, `"$BENCH/wd-main/.venv/bin/wetterdienst"`. It does not go through the MCP layer. Append
  `2>/dev/null` (the log goes to stderr). Its commands, tool by tool (checked against `--help` on 2026-11-12; a command's
  flags are the tool's arguments in kebab case, `--with-metadata true`, `--periods`, `--stations`, `--timestamp`, with a few extra
  ones such as `--start`/`--end`; `--help` lists them):

  | MCP tool | command of the reference |
  | --- | --- |
  | `glossary`, `providers`, `coverage`, `stations`, `values`, `interpolate`, `summarize`, `history`, `alerts`, `issues`, `auth` | the command of the same name |
  | `stripes_stations` | `stripes stations --kind temperature` (or `precipitation`) |
  | `stripes_image` | `stripes image ...` (a picture: the cases do not judge it) |
  | `stripes_values` | **no command** (there is no `stripes values`). Read the series the server reads, `_get_stripes_data` in `ui/core.py`: DWD observation, period `historical`, **temperature** `annual/climate_summary/temperature_air_mean_2m`, **precipitation** `annual/precipitation_more/precipitation_amount`, with `values` and take the year (or years) the case asks for |

  Examples, tried on 2026-11-12:

  ```bash
  "$BENCH/wd-main/.venv/bin/wetterdienst" glossary --parameter temperature_air_mean_2m --limit 3 2>/dev/null
  "$BENCH/wd-main/.venv/bin/wetterdienst" providers --provider dwd 2>/dev/null
  "$BENCH/wd-main/.venv/bin/wetterdienst" values --provider dwd --network observation --parameters daily/climate_summary/temperature_air_mean_2m --periods recent --stations 02564 --with-metadata true --format json 2>/dev/null
  "$BENCH/wd-main/.venv/bin/wetterdienst" values --provider dwd --network observation --parameters annual/climate_summary/temperature_air_mean_2m --periods historical --stations 03987 --start 1991 --end 1991 --format csv 2>/dev/null
  ```

  The last one is the `stripes_values` truth of Potsdam for 1991 (8.91 on 2026-11-12). The library is the other way
  (`"$BENCH/wd-main/.venv/bin/python" -I -c "from wetterdienst import Wetterdienst; ..."`, with
  `Wetterdienst.resolve(provider, network)(parameters=..., periods=...).filter_by_station_id(...).values().all().df`). The
  `python` reference is independent of the MCP layer, not of the library.
- **The hosted connector** (the tools `mcp__claude_ai_wetterdienst__*` of the released server): only if your instruction
  names it **and** your session lists those tools (a fresh session on this machine has none unless one is configured). The
  hosted server is the released version, which may name or return things differently from `main`; say so in the report.

Pass what you chose as `--reference` in 2.4 (`python` or `hosted`) and its version as `--reference-version`.

**2.4 The results file.** `bench.py init` writes it with its `meta` (server URL, version and label, the models of the tiers,
the repeats, the hashes of the cases, the defaults, the prompt and the counting, the version of `claude`, the size of
`tools/list`) and no runs. Never write that JSON by hand. For the **smoke run**:

```bash
. "$BENCH/env.sh"
python3 -I "$REPO/benchmarks/mcp/scripts/bench.py" init --results "$BENCH/mcpbench-results-smoke.json" --server "$URL" --label "$LABEL" --cases all --tiers small,large --large sonnet --repeats 1 --reference python --reference-version "$SERVER_VERSION" --judge-model "<your own model id>" --today "$(date -u +%F)"
```

For the **baseline**: the same with `--results "$BENCH/mcpbench-results-baseline.json"` and `--repeats 5`. `--large opus` only if
told. The command prints the number of runs (54 or 270); `bench.py todo --results FILE` lists them
(`case tier repeat model`), and what it still lists is what is still to do. `init` never overwrites a file. The date it
records (`--today`) is the date of the prompts, and **the judge's "yesterday" is that date minus one day**, even if the run
goes on past midnight UTC.

**2.5 The initial comment** on #3546 (Part 5 has the posting commands and the shape): the server SHA and version, the
`claude` version, the models, the cases (`all`: 27), the repeats, the reference, the results file name. Post it **before the
first tested model runs**.

## Part 3. Run the cases

One command makes the next runs of the file, at most 3 at a time, and prints for each the verdict of the counting, the calls
and the answer (it also leaves that text in `<dir>/<case>-<tier>-<repeat>.trial.txt`, the transcript as `.jsonl`,
and the analysis as `.analysis.json` next to it). Give each results file **its own directory** (`$BENCH/runs-smoke`,
`$BENCH/runs-baseline`):

```bash
. "$BENCH/env.sh"
python3 -I "$REPO/benchmarks/mcp/scripts/bench.py" batch --results "$BENCH/mcpbench-results-smoke.json" --dir "$BENCH/runs-smoke" --limit 9 --parallel 3
```

A batch of nine runs takes 5 to 8 minutes (at most `timeout` per run, three waves of three), so it **can run in the
foreground** within the Bash tool's 10-minute limit (`timeout: 600000`); the background (`run_in_background`) is for a larger
`--limit`. If you start it in the shell's background (`... &`), wait for it by its PID, never with `pgrep -f "bench.py batch"`
(which matches the `pgrep` itself and never ends):

```bash
python3 -I "$REPO/benchmarks/mcp/scripts/bench.py" batch --results "$BENCH/mcpbench-results-smoke.json" --dir "$BENCH/runs-smoke" --limit 9 --parallel 3 > "$BENCH/batch.out" 2>&1 &
echo $! > "$BENCH/batch.pid"
while kill -0 "$(cat "$BENCH/batch.pid")" 2>/dev/null; do sleep 10; done
cat "$BENCH/batch.out"
```

Use `--limit 9` (three waves of three) for the smoke run and the baseline alike, so that you judge in small batches and
post progress as you go. **The order of the runs is fixed: the whole `small` tier first, then the whole `large` tier** (each
tier by case, a case by repeat), so a tier is done after 27 runs of the smoke run and after 135 of the baseline, and the
"after each tier" comments of Part 5 land there (the baseline: at 135 and at 270). `batch` first prints the order it starts the
runs in; the three that run at once finish in any order, so each prints under its own header,
`=== [k/N] <case> | <tier> | repeat <n> | <model> ===` (k is the order of finishing), and the same header starts its
`<case>-<tier>-<repeat>.trial.txt`. For each run the command does the following, so you need not:

- writes the prompt (`bench.py prompt`, the date of the file), runs the tested model (`run_subject.sh`: Part "The tested
  model"), and analyzes the transcript (`bench.py analyze`);
- a run that **timed out** (exit 124) is recorded by `batch` itself as a *failed* run, and one for which the **server did not
  answer** (exit 3) as an *invalid* run; neither needs your judgement (both are counted by `report`);
- every other run waits for your judgement (Part 4).

**Judge every run of a batch before you start the next `batch`, and never let the two overlap.** A run that was made and is
not judged yet is still in `todo`, so the next `batch` would make it again and pay for it twice. `batch` therefore **refuses to
start** (exit 2, with the names of the runs) while runs of its directory wait for the judge; judge them, or, to make them again
on purpose, pass `--allow-unjudged`. **One run you skipped blocks the next batch, which is correct.** To find it, read the
message (it names the runs), or run `bench.py todo --results "$BENCH/mcpbench-results-smoke.json" --dir "$BENCH/runs-smoke"`, which lists
the runs still to do and marks the ones that were made and wait for the judge with `unjudged`; judge them (Part 4), or put them
aside (`--allow-unjudged` makes them again and pays again).

**You may judge from a condensed digest.** The printed text of `batch` is already one: the counting's verdict, the calls (tool,
arguments, ok, size), the answer and its `RESULT:` lines. To print it again, or to see the first characters of each call's result
next to it, run `bench.py digest "$BENCH/runs-smoke/<case>-<tier>-<repeat>.analysis.json"` (`--heads 300` adds 300 characters
of each result). Open the full transcript (`<case>-<tier>-<repeat>.jsonl`) only where a case needs it: the `no_measurements` fact
(is a figure of the answer in a tool result?), a spilled call, or a fact that a digest cannot settle.

**Resume after an interruption.** Nothing is lost: each judged run is in the results file the moment `judge` returns
(`add-run` writes through a temporary file and takes a lock), so you stop and start at any time. Run `bench.py todo` to see
what is left: a run with a valid record, a failed one (a timeout, a budget stop) included, is not listed again; a run
with no record, or only an invalid one, is. A run that was started and not judged (an `.analysis.json` with no record) is in
`todo` too, and `batch` refuses to start while there is one: look in the directory first, and judge those analyses instead of
paying for them twice. `judge` and `add-run` are
**idempotent only in the sense that they refuse**: a second `judge` of a run that has a valid record exits 2 ("would replace a
valid run") and changes nothing. To replace a record deliberately, pass `--replace-valid` (to `judge`) and say why in the next
comment. Never edit the results file by hand.

When `todo` lists nothing, the run is complete. Repeat `batch` and Part 4 until then.

## Part 4. Judge each run

For each analysis `batch` printed, work through it as below, then record it. The rules of the judge (which fact kinds there are,
the units, the placeholders, what an invented number is) are under "Judging rules" below; **follow them as written**.

1. Read the printed text. The counting already holds: the steps against the limit, the checkpoints, the violations (any tool
   other than the server's, the case's forbidden calls and answers), the spills, and `mechanical_pass`. For some
   facts (`network_serves_place`) it already holds a mechanical verdict. Do not recount.
2. **`is_answer`**: does the final answer answer the question (a refusal, a request for clarification or a hand-off is none; for
   an `unanswerable` case saying there is no data is the answer)?
3. **`facts_ok`**: for each fact of the case in `cases.json`, read the ground truth with your own calls on the reference (2.3),
   never from the subject's results alone, and compare as the fact's kind says. For a `unit` fact run
   `bench.py unit` (below) with the value **as the reference returned it, with its unit**. For `no_measurements`, read the transcript (`<stem>.jsonl`) for what each tool result said.
4. Record the verdict. `--fact` is repeated, one per fact of the case, **each written out in the command** (never in a
   shell variable that holds several arguments: zsh does not split it): `ok`, `"fail: <why>"` or `"drift: <how>"` (the source
   has moved from the `expected` of the case: say so, it is not a failure of the model):

```bash
. "$BENCH/env.sh"
python3 -I "$REPO/benchmarks/mcp/scripts/bench.py" judge --results "$BENCH/mcpbench-results-smoke.json" --analysis "$BENCH/runs-smoke/<case>-<tier>-<repeat>.analysis.json" --is-answer yes --facts ok --fact meaning=ok --fact unit=ok --note "<what is worth remembering, or empty>"
```

`judge` refuses a `--fact` whose id is no fact of the case or whose verdict is not `ok`, `fail: <why>` or `drift: <how>`, a
`fail:` verdict beside `--facts ok`, and any `--facts` or `--is-answer` word other than the choices (exit 2, with the reason).
`judge` computes `passed` (`mechanical_pass` and `is_answer`: never your word alone), drops the large `result_head` of each
call, and puts the record in the file; it exits 2 with the reason if the file refuses it (a missing field, a case that is not
in the file, a record of other conditions than the file's). A run that is `invalid` counts as neither answer nor facts.
A near miss (the right tool with a better argument than the one a checkpoint lists) is a `--note`, not a failure.

If you cannot obtain the ground truth (a provider is down, a call fails): **do not guess a verdict**. Leave the run
unjudged (it stays in `todo`), retry after a few minutes, and if it still fails say so in the next comment and ask (Part 7).

## Part 5. Report on #3546

All of it through `gh`, on `earthobservations/wetterdienst`. Write each comment to `$BENCH/comment-<n>.md` first and check
its size: **each comment stays under 60,000 characters** (`wc -c`). If the report is longer, split it at a heading into
`(1/2)`, `(2/2)`, each its own comment. **Each comment ends with the footer of the run**: first the line
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`, then, **last**, the session link line that **the person who
started the run gave you** (`https://claude.ai/code/session_<id>`), copied exactly. If you were given no link line, **end
with the "Generated with" line alone**: do not ask, and do not invent an id.

```bash
wc -c "$BENCH/comment-1.md"
gh issue comment 3546 -R earthobservations/wetterdienst --body-file "$BENCH/comment-1.md"
```

1. **Initial comment** (2.5), before the first tested model runs: title `MCP benchmark, <smoke|baseline> run: start`; the server
   SHA and version (and that it is a local server of `main` on 127.0.0.1:7891 with its own cache); the `claude` version; the
   models (`small` = haiku, `large` = sonnet or opus; the resolved ids come with the report); the cases (`all`: 27, no key
   case) and the repeats; the number of runs; the reference; the judge model (you); the results file name. Link the
   runbook at the SHA of your checkout.
2. **Intermediate comments** as the run progresses: after each tier is done, and in any case about every 25 judged runs
   (the baseline: each 27 runs, a tier of 135 has five of them). Each has: how many runs are judged of the total; the table of
   `bench.py report` so far (paste it as is); the failed runs (timeouts), the **invalid** runs (no server) and the **spilled**
   calls, with the case and tier of each; the runs you judged `drift` or could not judge; anything surprising (a case
   that every repeat of a tier fails, a sudden rise in steps or cost, a server restart, a violation by a tool that is not
   the server's); the cost so far (the last line of `report`).
3. **Final comment**, when `todo` is empty: title `MCP benchmark, <smoke|baseline> run: result`; the setup of the initial
   comment in two lines; the full `bench.py report` table; for a smoke run **whether it is clean** (clean = `todo` empty, no
   invalid run, no timeout, no spilled call that you cannot explain, no refused `judge`, every run judged; the pass rates are
   data, not a reason to call a smoke run unclean); the cases whose headline or facts failed, each with the one reason you
   found in the transcripts; the failure modes of Part 7 that happened; the total cost and the time it took; the link of the
   gist (below).
4. **The results JSON goes into a secret gist** and is linked from the final comment. Copy it to a descriptive file name
   (the gist takes the file's name), then create the gist. **A gist is secret unless `--public` is given, and `gh` (2.97) has no
   `--secret` flag: never pass `--public`.** Check that it is secret, and put its URL in the comment:

   ```bash
   . "$BENCH/env.sh"
   cp "$BENCH/mcpbench-results-smoke.json" "$BENCH/mcpbench-results-smoke-main-<version>-<sha>-<date>.json"
   gh gist create "$BENCH/mcpbench-results-smoke-main-<version>-<sha>-<date>.json" -d "wetterdienst MCP benchmark, smoke run, main <sha>, <date> (results for bench.py compare)"
   gh api gists/<id of the url it printed> --jq .public
   ```

   The last command must print `false`. The file is what `bench.py compare` reads later; it holds the transcripts' counts, not
   the transcripts, and no credential.

## Part 6. Finish

1. Stop the server **by its PID**: `kill "$(cat "$BENCH/server.pid")"` (the background task then ends with exit code 144: that is the signal), then `lsof -nP -iTCP:7891 -sTCP:LISTEN` shows nothing.
   Stop the background task that started it too (the Bash tool's task list). Check no other process of yours is still running
   (`bench.py batch`, `claude -p`), and wait for it if one is.
2. Remove the two worktrees from the repository you started in (the server's venv is in the first):
   `git worktree remove --force "$BENCH/wd-main"`, `git worktree remove --force "$BENCH/repo"`, then `git worktree prune`. The scratch directory (prompts, transcripts, the results file) **stays**: it is the
   record behind the comments. Say where it is in your last message.
3. Check what a run may have left in `~/.claude/projects`: `python3 -I "$REPO/benchmarks/mcp/scripts/bench.py" cleanup`
   removes the project directories that tested models left (it takes only those older than 10 minutes, and only
   `mcpbench-subject` ones).
4. Say in your last message: the results file, the comments you posted (links), the gist link, what is not clean, and
   what you stopped for. Do not go on to the other named run.

## Part 7. When something is unclear or breaks

**Stop and ask the maintainer; do not guess.** Say what you did, what you saw (the command and its output), and what you
need. Do not edit settings or permission files, do not work around a denied command, do not post anything beyond what Part 5
names. These failures are known; the first column is what you see, the second what it means and what to do:

| you see | it means / do |
| --- | --- |
| `claude -p` is denied, or `claude` is not logged in | the permission system or the login of the person who runs it pays for the models: **stop and report**, never work around it |
| `batch` or `trial`: `the MCP server at ... does not answer`, exit 3, runs recorded as `invalid` | the server is down. Look at `$BENCH/server.log`, check `/health`. If it died, start it again once with the same command (2.2) and the same cache, continue (`todo` lists the invalid runs again), and say so in the next comment. If it dies a second time, stop and ask |
| a run `timed out` (exit 124, recorded as `failed`, `failure: timeout`) | a result of the model, not an error: it counts against the pass rate and is not repeated. The first repeat of a case reads a cold cache and may be slow; many timeouts in a row point to a slow provider or a loaded machine: say so in the next comment |
| `end: error_max_budget_usd` in an analysis | the tested model reached 0.50 USD: a failed headline (`is_answer` no); say so in the report |
| `spilled` calls (a result larger than Claude Code allows is saved to a file the tested model cannot open), or `spill_unrecognised` | a real finding about a tool's answer size, not a fault of the benchmark: report it as it is. `spill_unrecognised` (a short result that mentions a saved file in other words than the two notices of "The tested model") means the notice changed again: say so; do not fix `bench.py` |
| `invalid_reason: the server 'wetterdienst' was 'failed'` / `offered no tool` / `the transcript has no init record` | the tested `claude` did not start or did not connect: check `claude --version`, the server, the transcript's last lines; a few in a row: stop and ask |
| `judge` or `add-run` exits 2 | read the message: it names what the file refuses (the label, version, model, prompt or date of the run differ from the file's; a missing field; a valid run that would be replaced). Fix the cause; **never** `--replace-valid` to get past it without a reason |
| `init` refuses | a bad argument, or the file exists: read it; never delete a results file to make `init` work |
| a ground-truth call fails, or its answer is odd (the source moved, a provider is down) | do not guess: leave the run unjudged, retry later, report it; a `drift` verdict is for a source that has changed from the case's `expected`, with the note saying how |
| the question of a case seems wrong, or a checkpoint is never met by a run that plainly did it right | **do not change `cases.json`**: it changes the hash of the case and takes it out of every comparison. Report the case, the run and why, and ask |
| `uv sync` fails to build polars | the Python is 3.14 (free-threaded): `UV_PYTHON=3.13` |
| the machine is loaded (the fans, load average) or the disk is nearly full | run with `--parallel 2` or `1`, or stop and ask; never more than 3 |
| port 7891 is in use at the start | not yours: ask; do not pick another port without saying, the label and the comment name the server |
| `gh` fails to post or create the gist | keep the comment in `$BENCH/comment-<n>.md`, retry once, then stop and report; the results file is safe in `$BENCH` |
| anything not listed here | stop and ask |

## Known false failures of the reference baseline

The reference baseline (the clean run of 2026-11-12, `main` at `d18a37368`, cases file hash `6b5b33ac5cef`) holds one failure
that is the case's and not the model's, and it stays in the numbers because the cases and the prompt are frozen with it:

- **`observation-vienna-yesterday`**: the first checkpoint `find-station` accepts only `stations` calls (by name or by point).
  A model that finds the station with `values` by name (`name=Wien`) reads the right Vienna station and answers right, and never
  meets it, so the headline fails although the facts hold. It happened in 3 of 135 runs of the `small` tier and in 1 of 135 of
  the `large` tier. Judge such a run as you would any other (`--is-answer yes`, the facts as they are): `passed` is computed
  from the counting and stays `false`; say in the `--note` that it is this one. Do not change `cases.json` for it: the same
  failure is in the baseline a later run is compared with. (`observation-paris-last-week` accepts `values` by name; this case
  does not.)

## The tested model: what `run_subject.sh` runs, and what remains in its context

A fair comparison needs a tested model that knows only the prompt and the tools. `bench.py run` (called by `batch`, `trial`
and `scripts/run_subject.sh`) runs `claude -p` in a **new empty directory outside the repository**, with `--strict-mcp-config` and an
`--mcp-config` holding only the server under test, `--tools ""` (no built-in tool: no Bash, Read, WebFetch, Agent),
`--setting-sources ""`, `--disable-slash-commands`, `--no-session-persistence`, `--max-budget-usd`, and
`--output-format stream-json --verbose`, whose output is the transcript. What the transcript's init record shows
(checked with 2.1.311, 2026-11-12): the 14 tools of the server and nothing else, no skill and no slash command, the
server `connected`. So the model sees the tools **directly (not deferred)**, no CLAUDE.md or AGENTS.md, no memory index, no
git status. What remains: Claude Code's own system prompt and, injected by the harness, a block with the user's email address
and the note about an empty auto-memory directory of the temporary directory. It talks to the server by URL, not through
the claude.ai connector. The login of the person who runs it pays for the model; no provider credential is passed.

The project directory Claude Code makes for that temporary directory in `~/.claude/projects` (an empty `memory/`, or the
file a too large result is saved in) is removed when the run ends, and `bench.py cleanup` sweeps what an interrupted run left.
Verified on 2026-11-12: a headless run left nothing in `~/.claude/projects`, and `--no-session-persistence` writes no
session file.

`run_subject.sh` is a wrapper of `bench.py run MODEL URL NAME PROMPT OUT [--timeout S] [--max-usd N] [--label SHA]`, which
**fails fast** instead of scoring a dead server as a model failure: exit 2 for a bad argument (a model, name or URL with
characters it will not pass on, a prompt file that is not there, no `claude` on the PATH), exit 3 when the MCP URL does not
answer or lists no tool, 124 after `MCPBENCH_TIMEOUT` seconds (default 300, at most 540; `claude` has no `--max-turns`), and
`claude`'s own code otherwise. `--max-budget-usd` (`MCPBENCH_MAX_USD`, default 0.50) stops the run after the turn that reached it with
`subtype: error_max_budget_usd` and a `tool_use` no result answered (a step that reads nothing). A transcript whose init record shows the server not connected, or
with none of its tools, or that has no init record, is **`invalid`**: it is left out of every rate, counted, printed by
`report`, and `compare` refuses a file with more than 3 % of them. A timeout is a *failed* run, not an invalid one, so that a
strategy that makes the model slower shows up as a failure and does not disappear.

**Results above the limit of Claude Code are saved to a file** the subject cannot open (it has no Read tool). The transcript
holds a notice instead, in one of two forms (both seen with Claude Code 2.1.311, 2026-11-12):

- `Error: result (358,696 characters) exceeds maximum allowed tokens. Output has been saved to ...`, the error of a result over
  the token limit (measured on the full stations list of DWD: 31,000 characters came through whole);
- `<persisted-output>` / `Output too large (57.2KB). Full output saved to: ...` / `Preview (first 2KB):` and the first 2 KB
  of the result, which is no error and has **no count of characters**: it is a size with a unit (B, KB, MB), and a result of
  about 58,000 characters (the `noaa/ghcn` `coverage`) was saved this way while one of 40,700 came through whole.

`bench.py` reads the size out of either notice (`result_chars`, `spilled_calls`): the characters of the first, and the size of
the second times 1024 per unit, an estimate a little above the characters when the text is not ASCII. So the size metrics are true
to within the rounding of the notice, and the call is `spilled` and `ok: false` whatever `is_error` says. A run whose answer
depended on such a result failed to read it (the 2 KB preview is no answer), which is what happened to it. `report` and `compare`
print the spilled calls; a short result that talks of a saved file in other words (neither form) is counted as `spill_unrecognised`
and **warned about** in the report: the notice is not a documented format, and a change of it would otherwise make the sizes look small.

**What the benchmark cannot see: the `outputSchema`.** The server's `tools/list` is about 260,000 characters, of which
about 210,000 were `outputSchema`, 39,000 `inputSchema` and 10,000 descriptions (`bench.py tools-size`, measured 2026-10-28,
0.178.0; run it for the server you test). The context of the tested model at its first request only fits if Claude Code does not
send the `outputSchema` to the model. A change that slims the output schemas therefore shows in `tools-size` and not in
`context_tokens_first`; a change to the input schemas or the descriptions shows in both. `init` records the sizes
(`tools_list` in the results file), so the wire cost the benchmark cannot see is on the page.

## Counting: what `bench.py` does for each run

`bench.py analyze` (inside `trial` and `batch`) counts, from the transcript and not from what the model says of itself:
`steps` (calls of the server's tools only), any other tool called (Bash, WebFetch, Read, Write, Agent, ...: each is a violation),
the ordered checkpoints, the forbidden calls, repeats and answers, the size of the tool results (a result saved to a file
counts by its real size), the output tokens, the context at the first and last request, the resolved model id, whether the
run is `invalid`, and the server version read from the results' JSON. A call no result answered is a step, `ok: false`, and meets no
checkpoint; a result saved to a file is `spilled`, `ok: false`. A run leaves `<transcript>.meta.json` (the probe's
`serverInfo`, the wetterdienst version, the label, the `claude` version, the prompt hash and date), which `add-run` holds to
the file's `meta`. **Replacing runs:** `compare` keeps, for every case, only the repeats that are valid on **both** sides and refuses
above 3 % invalid **or missing** (see "Comparison" below); a repeat outside 1..`repeats` or given twice for a (case, tier) is an error.
`add-run` (what `judge` calls) refuses a missing field or one of the wrong type, a repeat above the file's `repeats`, an unjudged
record, a case that is not in the file, a record whose `run_meta` (label, server version, model, prompt template, prompt date) differs
from the file's `meta`, a record that declares `kind` failed or invalid and still claims an answer, and a replacement of a
valid run (unless `--replace-valid`). It takes a lock on `<file>.lock` and writes through a temporary file and `os.replace`, so
several `judge`s at once keep all their records; the lock is `fcntl`, so macOS or Linux (the benchmark is run on those; where
there is no `fcntl`, Windows, no lock is taken and one must be run at a time). The lower-level commands (`prompt`, `run`,
`analyze`, `failed-run`, `add-run`) exist and are what `trial` and `judge` are made of; use them only to repair a single record
(`failed-run --kind failed|invalid` makes the record of a run that timed out or found no server).

## Judging rules

The counting has given `steps`, the checkpoints, the violations and `mechanical_pass` (1 to `max_steps` steps and the
**first checkpoint met**, and the run valid), and for a `network_serves_place` fact its verdict (`mechanical_facts`,
read from the stations the subject itself got listed, not from a call of yours). You add:

1. **`is_answer`**: the final answer answers the question. A refusal, a request for clarification or a hand-off is
   none (for `unanswerable`, saying there is no data is the answer). `passed = mechanical_pass and is_answer`:
   a run with no tool call never passes, even if it is right from memory, and a run that skipped the first
   checkpoint never passes.
2. **`facts_ok`** (the field of the record; the option of `judge` is `--facts ok` when every fact holds against your own
   ground truth, `--facts fail` when any does not: nothing else is accepted, and `--is-answer` is `yes` or `no`): every fact of
   the case, against ground truth **you** obtain with your own calls (not steps of the tested agent). Read the ground truth from the `reference`, never from the subject's own answers or the server
   under test alone, so that a change that rounds or drops a value cannot reproduce itself in the judge. Never copy a
   number from the case file: `expected` there only lets you say that the source has drifted.
   - `answer_regex`: the answer matches one of `any_of`.
   - `ground_truth_value`: make the call, pick what `pick` says, and the number in the answer is within `tolerance`.
   - `ground_truth_span`: every figure the answer gives lies in `[min - margin, max + margin]` of the series your call
     returns and inside `sanity`; with `future_only` (the three `forecast-*` cases), it must belong to timestamps after the
     subject's call (a forecast), so an observation fails. **"After the subject's call"** is a timestamp later than the
     `retrieved_at` of the result of the subject's own `values` call (UTC; the digest prints it per call). The series is your
     own `values` call for the same station and source with `periods=future`, read for **the next 48 hours counted from your
     call**, and the span is its minimum and maximum widened by the case's `margin` (4 K for a forecast) and kept inside
     `sanity`. A figure the answer ties to a time at or before the subject's call (an observation, an hour already past) fails.
     Forecasts change between runs, which the margin absorbs: judge soon after the run, the same day.
   - `ground_truth_text`: the answer carries what `pick` says, in its own words; `answer_matches_any_of`, if there,
     lists accepted spellings.
   - `ground_truth_subset`: every name the answer gives is in your call's result. `ground_truth_set`: the answer
     names exactly the items your call yields, or says there are none.
   - `unit`: the answer states the value **with its right unit** (see "Units" below). **Only the `units-*` cases (kind
     `units`) have a fact of this kind and need `bench.py unit`.** Other facts carry a `unit` field too (`degree_celsius`, and
     `metre` in the `history-*` case) but it only names the unit of the value: their kind (`ground_truth_value`, ...) decides how
     they are judged, plainly, against your own call. Run
     `python3 -I "$REPO/benchmarks/mcp/scripts/bench.py" unit --case <id> --fact <id> --truth <value> [<unit>] --answer "<text>"` (or
     `--truth <min> <max> [<unit>]` for the span of a forecast) with the value from your own call **as the reference returned it,
     followed by its unit**: the command converts it to the unit the fact counts in (`accepted` of the fact), so you do not.
     Example: the reference returns the sunshine as `4.117` with the unit `h`, the fact counts in seconds (14821.2):
     `... unit --case units-sunshine-seconds --fact value-with-its-unit --truth 4.117 h --answer "RESULT: 14821 s | sunshine"`
     passes it, and `--truth 14821.2` (no unit) would mean seconds. A unit the fact does not accept is refused (exit 2) and
     the message lists the ones it does. The command prints which figures passed or failed, and the truth it used.
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

**Dates.** All dates are UTC. "Today" is the `date` of the results file's `meta` (the date in the prompts), whenever you judge; "yesterday" is that date minus one day; "the last 7 days" is the 7 days ending yesterday. A
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
`coverage`. A model that does not look it up may state a number with the wrong unit: the reference returns the daily mean humidity of
Hamburg-Fuhlsbüttel on 2026-10-16 as `84.04` with the unit `%` today (the source and the library hold the fraction 0.8404, and
the fact accepts a fraction or a percent, each with its own unit), so `0.84 %` or `84.04 fraction` is wrong by a factor of 100;
sunshine comes back as `4.117 h` (14821.2 s), and `4.117 min` is wrong; degrees Celsius may be read as kelvin; and a change that makes the default answer compact (CSV or columnar) must still hand the
unit over. The cases of kind `units` (`init --cases kind:units`, 8 cases) require the answer to state the unit, and the right
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
`TABLE-UNIT` must name one of the unit tokens. **A table decides a verdict only when it is unambiguous; otherwise it neither passes nor fails anything, and the RESULT line
decides.** For a fact with `column`, `column_names` and `row` (the CSV case), each table of the answer is read for the value on the
row of the fact's day (`2026-10-16`, `2026/10/16`, `20261016`, `16.10.2026`, `16.10.`, `16/10/2026`, `16-10-2026`, `16 Oct`,
`Oct 16, 2026` ...; another year is another day, and the end of a range such as `15-16 Oct 2026` is not the day):

- *Rows.* A table with the dates as columns is read transposed. A **long** table has a parameter column: a column that holds the
  canonical name (`precipitation_amount`), or one named `parameter`, `name` or `variable` that holds a name matching the
  `column` regex. Only the rows whose cell *there* is the canonical name are read (else those of the one parameter whose name
  matches the regex; two matching parameters, or none, leave no row). A `name` column of station names, and a note column
  that says "precipitation", are no parameter column: the table is read as a wide one.
- *Column.* The fact's first `column_names` entry if it is a header (`precipitation_amount`); else the one header that matches
  the `column` regex, which names the precipitation and not its neighbours (`precip` without form, type, kind, max, min, 1h,
  hourly, per hour, intensity, flag, quality, qn, at the start of a word: `maximum`, `minutes` and `formula` are excluded too; `24-hour total` is a total, `hourly` is not); two headers that match, and none exact, are ambiguous (`precipitation_mm` and
  `precipitation_cm`) and the table decides nothing; else the fact's other entry, `value` (the column of a long table, and of a
  wide one only when nothing matched); else the one column a `TABLE-UNIT` line names (the line of that name, of the name without
  its bracketed unit, `Rainfall | mm` for `Rainfall (mm)`, or the one line that is a spelling of it) with a unit of the case,
  accepted or forbidden (`rain_mm | mm`; `quality | QN` is not one). A column with no such name (`rr`, `rain`) decides nothing. Figures inside
  dates and times are never read.
- *Unit.* Read only on the chosen column: its own `TABLE-UNIT` line (the line of that name, of the name without its bracketed
  unit, or the one line that is a spelling of it: `precipitation` for `precipitation_mm`; two spellings with different units give
  none), else (in a long table) the line that names the parameter in the same ways (`precipitation_amount | mm` or
  `precipitation | mm` for `value`), else a unit of the case in its header (`Precipitation (cm)`), else the unit the tool returns. The units a line declares for any other column (`quality | QN`,
  `date | UTC`, `wind_speed_mean | m/s`) are not read. A forbidden or unknown unit declared for the chosen column fails.
- *Value.* A chosen column that gives the day two different values fails whatever the order; all of them equal the value, the
  table passes. A table that has the chosen column and a wrong value fails the answer beside a right table.

The unit must be stated: by a `TABLE-UNIT` line (or the header) for the chosen column, or by a fitting RESULT line; a RESULT line
for the value is also enough when the answer has no table. When no RESULT line and no table gives the value, the failure says why
each table decided nothing: no row of the day, `n` columns that may be the value (named), no column is the value, or the table
holds the value but states no unit.

**The unit slot** forgives slips: a trailing point, a remark in brackets (`°C (as returned)`, `mm (millimetres)`,
`degrees Celsius (°C)`), `℃`, `ºC`, `m s⁻¹`, `%RH`, bold, bullets, numbered markers, quotes, fences, any case.

**What counts as a malformed line, and what then.** A line that starts `RESULT:` and a number but gives no unit, or does not
parse, or whose unit slot starts with a sign or holds a second figure (`19-21 °C`, `19–21 °C`, `4 h 7 min`: a range or a
compound figure is no one value; a digit inside a unit, `l/m2`, `m s-1`, is part of it), is *malformed*: it is a format violation, and it is ignored. If **any** well-formed RESULT or TABLE-UNIT line exists,
the strict rule applies to those lines alone (a malformed line does not make the rest lenient). Only an answer with **no**
well-formed line is read by the **fallback**.

**The fallback** reads tolerantly: prose (the unit directly after the figure, in brackets, as `(unit °C)`, in brackets before
it on its line, or alone on the line above), real tables (a markdown table, or two or more lines of the same cells with a
separator row or a header line; prose with commas is no table: a header line is names only, that is cells that are no value
(no signed or decimal figure, none that starts the cell) and no sentence (five words at most, not two words or more ending in
`.`, `!` or `?`, unless it is an abbreviation: `Temp. max.`, `Daily precip. amt.`, a stop after a word of fewer than four ASCII
letters and an earlier word with a stop; a whole number in a header cell must be followed by a word, `24 h`)) by column, with the unit in the cell, the header, a
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

**Four rates, not one.** `passed` is the answer-reached headline (an answer within `max_steps`, from at least one call,
after the first checkpoint). It says nothing of whether the answer is right or what the agent did on the way: an answer
from the wrong data can still pass. `facts_ok`, the violations (the share of runs with none) and the format (the share that follow it, over the cases that ask
for it) are therefore compared as rates of their own, and a change is "no worse" only if all four are (see "Comparison").

## The results file

`bench.py init` writes `mcpbench-results-<run>.json` into the scratch directory (never into the repository, never committed), and
`judge` adds one record per run; `bench.py report` and `compare` read it. Do not write it by hand. Its shape, for
reference:

```json
{"meta": {"date": "2026-11-12", "models": {"small": "haiku", "large": "sonnet"}, "judge_model": "<the model that judges>",
          "server": "http://127.0.0.1:7891/mcp/v1", "server_version": "0.186.0", "label": "<sha of the checkout, +dirty>",
          "server_info": {"name": "Wetterdienst", "version": "0.186.0"}, "reference": "python", "reference_version": "0.186.0",
          "claude_version": "2.1.311 (Claude Code)", "tools_deferred": false, "context_note": "<what remains in the context>",
          "repeats": 5, "cases_file": "<hash>", "defaults": "<hash>", "logic": "<LOGIC_VERSION of bench.py>", "prompt": "<hash>",
          "case_hashes": {"<id of each case of THIS run>": "<hash>"},
          "tools_list": {"description": 12036, "inputSchema": 48593, "outputSchema": 256622}},
 "runs": [{"case": "...", "tier": "small", "repeat": 1,
           "...": "everything `bench.py analyze` printed, without `result_head` (`invalid`, `model`, `spilled_calls`, ...)",
           "is_answer": true, "passed": true, "facts_ok": true,
           "fact_results": {"<fact id>": "ok | fail: <why> | drift: <how>"}, "judge_note": ""}]}
```

## The report and the comparison

`bench.py report <results.json>` prints, per (case, tier): `passed k/N`, steps median/max against the limit, checkpoints met out
of possible, violations, `facts ok k/N`, format violations, the median size of the tool results (characters), the median output
tokens, the median context tokens at the first request and the median total tokens, and the spilled calls; then one pooled
row per tier. Under it, when there are any: the number of invalid runs left out (with their reasons), the spilled calls, a
warning for a result that looks saved to a file in words `bench.py` does not know, and the cost of the tested models. It does not
list the failing cases: read them off the table (`passed` below `N`) and your judgement notes.

**Comparison.** `bench.py compare previous results` is a **non-inferiority** claim, not a search for a difference. It
**refuses** (prints why and exits with code 4) when the logic version of `bench.py`, the `defaults` of the cases file, the
prompt, or whether the tools were **deferred** differ, when the two sides cannot be
told apart (one server version and one `label`; `--same-server` compares two runs of one server), when the two files were made
with a different number of `repeats` or hold a repeat outside 1..`repeats` or twice, or when more than 3 % of the runs of the
*compared* cases of one tier are invalid or missing (the verdict is per tier, so is the cap). It compares the (case, tier) of the previous file whose case is named
with the same hash in the current file's `meta.case_hashes` and whose tier is in its `meta.models`: **one of them with no run
in the current file has every repeat missing** and counts toward the 3 % (a strategy that makes a case time out on every
repeat and records none must not look like a smaller suite). `meta.case_hashes` and `meta.models` therefore list exactly the cases and tiers the run was
made with (`init --cases`, `--tiers`), not all of them: a (case, tier) it names and has no run of counts as missing, and the reason gives both causes (it was not selected: drop it from `meta`; it was selected and lost, a timeout or a dead server: record each of its repeats with `bench.py failed-run`); exactly 3 % is allowed; a `models` that
is empty is refused as such. It lists, by name, the cases only in the current file, with a
changed hash, and removed from the current file (or whose tier it no longer has), which stay out; a tier whose
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

## Comparing a change before release

The two named runs are the **baseline** (and its smoke check) of `main`. To judge a change (a branch that slims a schema or
shrinks an answer), run **both sides on local servers in the same environment, with the same limits and cache**, not against the
hosted server: a baseline of the hosted server differs from a local `main` by the host, the network and the deployed settings.
The change goes in its own worktree and on its own port, with the **same** `WD_CACHE_DIR`:

```bash
git worktree add --detach "$BENCH/wd-change" <the branch or SHA>
cd "$BENCH/wd-change" && uv sync --python 3.13 --extra restapi --extra mcp --extra export --extra interpolation --extra sql
cd "$BENCH/wd-change" && exec .venv/bin/wetterdienst restapi --listen 127.0.0.1:7892      # MCP at http://127.0.0.1:7892/mcp/v1
```

Then do Parts 2 to 6 again with `--server http://127.0.0.1:7892/mcp/v1`, the SHA of the branch (`+dirty` if `git status` is not
clean) as `--label`, and the **same** `--cases`, `--tiers`, `--large` and `--repeats` as the baseline; the two servers report one
version, so the labels are what tells the files apart. Keep the reference the same for both (`python` of `main`, so the
judge's ground truth does not move with the change). Then
`python3 -I "$REPO/benchmarks/mcp/scripts/bench.py" compare <the baseline's results file (from the gist)> <the new one>`; it exits 4
and says why if the two cannot be compared. Stop both servers by PID when done.

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

## Adding a case

Append to `cases.json`, run `uv run pytest tests/ui/test_mcp_benchmark_cases.py`, then run the case with both tiers
and 3 repeats (`init --cases <id> --repeats 3`, then Parts 3 and 4) and read the transcripts before trusting the `tiers` you gave it. A change to a case changes its hash
and takes it out of the next comparison, as it should. Docs: `docs/contribution/mcp-benchmark.md`.
