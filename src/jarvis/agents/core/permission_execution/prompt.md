Execute these standing-permission actions. For each item, call EXACTLY the named MCP tools
on it — and no other tools. Do NOT substitute a different tool. The 'intent' tells you what
the rule is meant to achieve — use it to choose the tool's arguments (e.g. which labels to
add/remove), nothing more. If a named tool is not in your toolset, or you are not confident
you can run it safely, SKIP it and report the reason instead of guessing.

## Output format (MANDATORY)

Return a single JSON object with a `results` array holding one entry per (item, tool)
pair you were asked to act on. Emit a result for EVERY pair — never drop one silently.

```json
{
  "results": [
    {
      "item_id": "<string — echo the item_id from the action line verbatim>",
      "tool": "<string — the exact MCP tool name you invoked for this item>",
      "status": "<string — one of: done, skipped, failed>",
      "detail": "<string or null>"
    }
  ]
}
```

Field rules:
- `item_id` (string, required): copy the `item_id=...` value from the matching action
  line exactly — it is how the result is mapped back to the item.
- `tool` (string, required): the named MCP tool this result is about.
- `status` (string, required): exactly one of
  - `"done"` — the tool call succeeded.
  - `"skipped"` — the tool was not in your toolset, or you opted out of running it.
  - `"failed"` — you called the tool and it errored.
- `detail` (string or null): for `skipped`/`failed`, a short reason; for `done`, an
  optional one-line summary, otherwise `null`.

{actions}
