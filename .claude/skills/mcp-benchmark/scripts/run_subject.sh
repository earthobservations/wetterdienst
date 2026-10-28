#!/usr/bin/env bash
# Run ONE tested agent of the MCP benchmark headless, outside the repository, with only the MCP server's tools.
#
#   run_subject.sh <model> <mcp-url> <server-name> <prompt-file> <out.jsonl>
#
# model        haiku | sonnet | opus (what `claude --model` takes)
# mcp-url      streamable-HTTP URL of the server under test, e.g. https://wetterdienst.eobs.org/mcp/v1
# server-name  the name the tools get: mcp__<server-name>__<tool>
# prompt-file  the prompt of the tested agent (the question and the rules)
# out.jsonl    where the stream-json transcript is written (every call, every result, the token usage)
#
# The agent runs in a new empty directory (no CLAUDE.md, no memory, no git status of this repository), with no
# settings sources, no skills, no built-in tools (`--tools ""`) and only the one MCP server (`--strict-mcp-config`),
# so what it knows is the prompt and the tools. Credentials of the person's Claude login are used for the model
# only; no provider credential is passed.
set -euo pipefail

model=$1
url=$2
server=$3
prompt_file=$4
out=$5

work=$(mktemp -d "${TMPDIR:-/tmp}/mcpbench-subject.XXXXXX")
trap 'rm -rf "$work"' EXIT
printf '{"mcpServers":{"%s":{"type":"http","url":"%s"}}}\n' "$server" "$url" >"$work/mcp.json"

cd "$work"
claude -p "$(cat "$prompt_file")" \
  --model "$model" \
  --mcp-config "$work/mcp.json" --strict-mcp-config \
  --tools "" \
  --allowedTools "mcp__${server}" \
  --disable-slash-commands \
  --setting-sources "" \
  --no-session-persistence \
  --max-budget-usd "${MCPBENCH_MAX_USD:-0.50}" \
  --output-format stream-json --verbose >"$out"
