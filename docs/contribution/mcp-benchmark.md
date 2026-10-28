# MCP benchmark

A how-to for the manual benchmark of the [MCP server](../usage/mcp.md): does a model, given only the tools, reach
an answer within a number of steps, and through which steps?

It is **manual and costs tokens**. It runs inside Claude Code, started by a person with `/mcp-benchmark`; no CI job,
schedule or `pytest` run starts it. A run spawns one subagent per question and model tier (about two per case with
the default tiers) and sends requests to the live providers, so run the cases you need.

The skill is `.claude/skills/mcp-benchmark/SKILL.md`, the questions are `.claude/skills/mcp-benchmark/cases.json`.
Both are read by the orchestrating Claude; the schema of a case is documented in the skill.

## Run it

Open Claude Code in the repository, with the wetterdienst MCP server connected (the hosted connector or your own
`wetterdienst restapi`), and type:

```text
/mcp-benchmark cases=glossary-temperature-air-mean-2m,licence-dwd tiers=small
/mcp-benchmark cases=all large=opus previous=/path/to/mcpbench-results-20261028-1200.json
```

| argument | meaning | default |
| --- | --- | --- |
| `cases` | ids separated by commas, `kind:<kind>`, or `all` | `all` |
| `tiers` | `small` (Haiku), `large`, or both | both |
| `large` | `sonnet` or `opus` | `sonnet` |
| `previous` | an earlier results file, to say what changed | none |
| `include_keys` | `1` to run the cases of a network that needs credentials | skipped |

A run asks for a permission per tool the first time. To avoid that, allow `mcp__claude_ai_wetterdienst__*`, `Agent`
and `Write` for the scratchpad in your own `.claude/settings.local.json`; the skill never edits the settings.

## Read the result

The orchestrator judges each log of a tested agent and prints one row per case and tier.

| column | what it is |
| --- | --- |
| `passed` | the headline: an answer was reached within `max_steps` tool calls (a step is one call of a wetterdienst tool) |
| `steps/max` | the calls used against the limit |
| `checkpoints` | `k/n` of the expected intermediate steps, in order but not necessarily one after the other, with the first one missed |
| `violations` | behaviours the case forbids: `interpolate` for a plain weather question, `shape=wide` over a long window, a refusal because the provider is German, the same `values` call more than twice |
| `facts ok` | the answer against ground truth the judge reads with its own calls; a forecast is only held to a plausible span, never to a number |

The full results go to a JSON file in the scratchpad directory, not into the repository. A failed headline with all
checkpoints met usually means a step was spent on a retry; a missed first checkpoint means the model started in the
wrong place, which is the thing to read in the log. A tier that is expected to pass (`tiers` of the case) and does
not is a regression of the tools or their descriptions; one that passes and is not expected to says the case has
become easy.

The tested agent writes its own log of its calls. The judge cannot see the tool calls themselves, so it compares the
length of the log (plus the tool searches the agent says it made to load the tools) with the tool-use count the
harness reports for the agent, and records a difference.

## Add a case

Append an object to `cases.json`: `id`, `question`, `kind`, `max_steps`, `checkpoints`, `forbidden`, `facts`,
`tiers`, `needs_key`, `notes`. Keep to the following.

- Write `max_steps` generous but meaningful: 6 for a forecast by place, 4 for a glossary or licence question.
- A checkpoint is a call, with alternatives for the several right ways to make it; it is checked on the tool and
  its arguments, not on the wording.
- Check facts against a call the judge makes, never against a number written in the case (the source moves);
  an `expected` value only shows that it drifted. A forecast gets a span, not a value.
- Name a provider, network or parameter as a literal when it must exist: the offline test holds them to the code.

Then run `uv run pytest tests/ui/test_mcp_benchmark_cases.py`. It calls no model: it checks that every tool,
argument, provider, network and parameter a case names exists, that the ids, limits and regexes are sound, that
`needs_key` agrees with the networks, and that no credential or personal data is in the files. A renamed parameter
or tool fails it before a run would silently stop meeting a checkpoint. Run the new case once with both tiers
before trusting its `tiers`.
