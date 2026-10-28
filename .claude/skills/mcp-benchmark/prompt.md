Today's date is {today} (UTC). Answer the question below using ONLY the tools of the wetterdienst MCP server ({tools}). If those tools are deferred, load them with ToolSearch first; loading is not a step. Do not use any other tool, the web, files or your memory of weather facts.

Question: {question}

Rules:
- A step is one call of a wetterdienst tool. You have at most {max_steps} steps. If you have used them and still have no answer, stop and say that you could not answer; give no number you did not read from a tool result.
- Do not invent numbers: every figure in your answer must come from a tool result.
- If a tool returns an error or no rows, say so and decide what to do next; do not hide it.
- Finish with your answer to the question in 1 to 3 sentences (plus the table or CSV block, if the question asks for one). If the question asks for a number, end the answer with one line for each figure you give, exactly in this form and nothing after these lines:
  RESULT: <number> <unit> | <what it is>
  for example `RESULT: -0.7 °C | daily mean air temperature at Kiel-Holtenau on 2025-12-26`. The number is written with digits and a decimal point, the unit is the one of the data or the one the question asks for, never left out. For a forecast give one RESULT line for each temperature you name. If you give a table or CSV block, also add one line for each of its columns that has a unit: `TABLE-UNIT: <column name> | <unit>`. If the question asks for no number, write no RESULT line.
