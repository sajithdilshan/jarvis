<!--
  PRIORITY POLICY — the editable harness surface for the self-improving priority loop.

  This file is the ONLY thing the `improve-priority` skill edits. It is composed into the
  synthesize system prompt at build time via the `{priority_policy}` placeholder (see
  agents/core/synthesize/__init__.py). Keep it self-contained: it decides ONLY how a
  briefing entry's `priority` field is set to high / normal / low. Do not put output-format,
  batching, or memory rules here — those live in prompt.md.

  Git history of this file is the harness lineage AND the "last optimization day" marker:
  the skill queries feedback created after this file's last commit. Keep edits minimal and
  tied to a named feedback pattern so each change is auditable and reversible.

  Anti-suppression invariant (do not weaken): nothing is ever hidden or dropped. High-
  priority entries are always shown expanded at the top; normal + low go in a collapsible
  box the user still reviews. So a wrong priority call is at worst a visible mis-sort the
  user can correct by rating — it never silences an item. Never add rules whose effect is
  to suppress, drop, or hide entries.
-->

## Priority policy

Every briefing entry gets a `priority` of `high`, `normal`, or `low`. Choose it as follows:

- **`high`** — truly urgent items that the user would want surfaced immediately: direct
  mentions, blockers, hard deadlines, anything time-sensitive or requiring a prompt
  decision. Be sparing: `high` is a signal, and over-using it makes it meaningless.
- **`low`** — routine, low-stakes, or purely-informational items, and proactive automation
  suggestions. These sort below actionable items and live in the collapsible box.
- **`normal`** — the default for everything else: worth reporting, not urgent.

When genuinely unsure between two bands, prefer the lower-alarm one (`high`→`normal`,
`normal`→`low`) — nothing is hidden either way, and the user corrects mis-sorts by rating.
