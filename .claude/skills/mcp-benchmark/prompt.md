Today's date is {today} (UTC). Answer the question below using ONLY the tools of the wetterdienst MCP server ({tools}). If those tools are deferred, load them with ToolSearch first; loading is not a step. Do not use any other tool, the web, files or your memory of weather facts.

Question: {question}

Rules:
- A step is one call of a wetterdienst tool. You have at most {max_steps} steps. If you have used them and still have no answer, stop and say that you could not answer; give no number you did not read from a tool result.
- Do not invent numbers: every figure in your answer must come from a tool result.
- If a tool returns an error or no rows, say so and decide what to do next; do not hide it.
- Finish with your answer to the question in 1 to 3 sentences, and nothing after it.
