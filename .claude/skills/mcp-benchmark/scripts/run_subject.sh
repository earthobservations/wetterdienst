#!/usr/bin/env bash
# Run ONE tested agent of the MCP benchmark headless, outside the repository, with only the MCP server's tools.
#
#   run_subject.sh <model> <mcp-url> <server-name> <prompt-file> <out.jsonl>
#
# model        haiku | sonnet | opus (what `claude --model` takes)
# mcp-url      streamable-HTTP URL of the server under test, e.g. https://wetterdienst.eobs.org/mcp/v1
# server-name  the name the tools get: mcp__<server-name>__<tool>
# prompt-file  the prompt of the tested agent (the question and the rules); any path, it is made absolute first
# out.jsonl    where the stream-json transcript is written (every call, every result, the token usage)
#
# It is a thin wrapper of `bench.py run`, which does the work in Python: it validates the arguments, probes the MCP
# URL and stops with exit code 3 if the server does not answer (a run against no server says nothing about a model),
# starts `claude -p` in a new empty directory (no CLAUDE.md, no memory, no git status of this repository) with no
# settings sources, no skills, no built-in tools (`--tools ""`) and only the one MCP server (`--strict-mcp-config`),
# stops it after MCPBENCH_TIMEOUT seconds (default 300) or MCPBENCH_MAX_USD dollars (default 0.50), and removes the
# temporary directory and the project directory Claude Code makes for it in ~/.claude/projects (an empty memory
# directory, or the file a too large tool result is saved in). The login of the person who runs it pays for the
# model; no provider credential is passed.
set -euo pipefail
exec python3 -I "$(dirname "$0")/bench.py" run "$@"
