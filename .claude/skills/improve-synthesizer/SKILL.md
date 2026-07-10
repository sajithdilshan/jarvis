---
name: improve-synthesizer
description: Mine briefing-log feedback since the last run and propose minimal edits to the
  synthesizer's personalization overrides — priority ranking and/or narrative/batching/framing.
  Use when the user wants to run the self-improving loop / improve how Jarvis prioritizes or
  writes briefings. Writes gitignored local overrides only; never touches tracked files.
---

# Improve the synthesizer from feedback

You are running the **improvement loop** for Jarvis's self-improving synthesizer. On each
scheduled poll the synthesize agent turns raw source data into briefing entries: it decides
each entry's **priority** (`high`/`normal`/`low`) and writes the **narrative** (wording,
batching, framing). The user rates entries on the dashboard — a 1–5 score (1 = badly
mis-prioritized, 5 = spot-on) plus optional free-text comment — stored in the
`briefing_log_feedback` table.

Your job is the paper's three stages — **mine → propose → gate** — with the **human as the
acceptance gate** (they are in this session with you; they approve before you write).

Read `tmp/harness_improvement_plan.md` first if it exists — it holds the full design and the
anti-suppression invariant you must never weaken.

## CRITICAL: write local overrides only — NEVER edit tracked files, NEVER commit

Learned personalizations can contain **sensitive/personal content** (names, projects,
relationships, private context) and must **never enter version control**. So there are two
layers:

- **Tracked base (read-only for you):** `src/jarvis/agents/core/synthesize/prompt.md` and
  `.../priority_policy.md`. Generic, committed, shared. **You never edit these.** Read them
  only to understand the current baseline you're refining.
- **Local overrides (what you write):** gitignored siblings you create/append to —
  - `src/jarvis/agents/core/synthesize/priority_policy.local.md` — ranking personalizations.
  - `src/jarvis/agents/core/synthesize/prompt.local.md` — narrative/batching/framing ones.

  These are matched by `*.local.md` in `.gitignore`, so they can never be committed. The
  runtime composes `base + local override` into the prompt at build time (see
  `synthesize/__init__.py: _read_surface`), so your edits take effect on the **next poll with
  no commit**.

Never touch `prompt.md`, `priority_policy.md`, the composition code, schemas, or any other
file. Never run `git add`/`git commit`. If you ever find yourself about to edit a tracked
`.md` (not `.local.md`), STOP — that's a bug.

### The hard rule: anti-suppression (applies to BOTH surfaces, non-negotiable)

Nothing is ever suppressed, hidden, dropped, filtered, or skipped. Priority only *sorts*
(high shows at top; normal+low go in a collapsible box the user still reviews); narrative
guidance only decides *how items are written*. **No override may ever reduce what gets
emitted.**

- FORBIDDEN in any override: "skip routine items", "don't emit low-value notifications",
  "omit bot messages", "only surface important things", or anything whose effect is that an
  item the synthesizer saw does not become a briefing entry.
- This matters most for the prompt override: unlike priority (a bad call is a *visible*
  mis-sort the user can rate and correct), a suppression rule makes the item never reach the
  UI — so the user can never see or rate the mistake, silently re-opening the reward-hacking
  hole the design closes. If a pattern seems to want suppression, reframe it as a **ranking**
  change in the priority override (move to `low`), never removal.

### Evidence strength differs — be honest about it

- **Priority edits** are backed by a real verifier: the 1–5 score directly measures priority
  correctness. Solid ground.
- **Narrative/framing edits** have **no measured signal** — only the free-text comments and
  your reading of them. Weaker evidence: require a clearer, more repeated pattern, keep the
  edit smaller, and flag in the audit record that it rests on judgment, not measurement.

## Stage 1 — Mine (scoped to "since the last run")

1. **Find the cutoff = when this loop last ran.** Because local overrides are gitignored,
   git history can't mark it — instead each override file carries a `last_optimized:` stamp
   near the top. Read the stamp from each local file (if it exists):
   ```bash
   grep -h '^last_optimized:' \
     src/jarvis/agents/core/synthesize/priority_policy.local.md \
     src/jarvis/agents/core/synthesize/prompt.local.md 2>/dev/null
   ```
   Use the **earliest** stamp found as the feedback cutoff (so feedback accrued against one
   surface since the other was last updated isn't skipped). If neither file exists / has no
   stamp, this is the first run — use **all** available feedback (no cutoff).

2. **Query feedback created since that cutoff.** DSN defaults to
   `postgresql://temporal:temporal@localhost:4003/jarvis` (override with `$POSTGRES_DSN`).
   Substitute the cutoff for `:since` (drop the `WHERE` entirely on a first run):
   ```bash
   psql "${POSTGRES_DSN:-postgresql://temporal:temporal@localhost:4003/jarvis}" -P pager=off -c "
     SELECT rated_priority, source, category, score, comment, narrative_snapshot, created_at
     FROM briefing_log_feedback
     WHERE created_at > TIMESTAMPTZ ':since'
     ORDER BY score ASC, source, rated_priority;
   "
   ```
   And the aggregate shape, so you reason over counts, not anecdotes:
   ```bash
   psql "${POSTGRES_DSN:-postgresql://temporal:temporal@localhost:4003/jarvis}" -P pager=off -c "
     SELECT source, rated_priority,
            count(*) AS n, round(avg(score),2) AS avg_score,
            count(*) FILTER (WHERE score <= 2) AS bad,
            count(*) FILTER (WHERE comment IS NOT NULL AND comment <> '') AS with_comment
     FROM briefing_log_feedback
     WHERE created_at > TIMESTAMPTZ ':since'
     GROUP BY source, rated_priority
     ORDER BY bad DESC, avg_score ASC;
   "
   ```
   (If `psql` isn't on PATH, run the same SQL however the user's environment reaches
   Postgres — e.g. `docker compose exec postgres psql -U temporal -d jarvis -c "..."`.)

3. **Cluster into two buckets** — each failure signature routes to one override:
   - **Priority patterns → `priority_policy.local.md`.** Low scores grouped by
     `(source, rated_priority)` where the comment (or score-vs-priority mismatch) says the
     *rank* was wrong: "this was buried in low but it was a direct mention", "these
     automation suggestions keep showing as normal, should be low".
   - **Narrative/framing patterns → `prompt.local.md`.** Comments about *how it was written*,
     independent of rank: "these 5 Jenkins emails should've been one entry" (batching), "too
     vague, didn't tell me what changed" (narrative quality), "why is this phrased as urgent"
     (framing). A low score with a wording complaint but a *correct* priority is a prompt
     signal, not a priority signal.

   Ignore one-off gripes. Require **≥3 same-direction ratings** for a priority edit; a
   **clearer/more repeated** pattern for a narrative edit (weaker evidence — see above). Note
   the **sampling bias**: users rate low-prio items they happen to open, so "low gets many
   corrections" does NOT mean the classifier is broadly bad — weigh by count and avg_score,
   not raw correction volume.

## Stage 2 — Propose, then (after approval) write the local override

1. **Read the current baseline** — both the tracked base (`priority_policy.md` /
   `prompt.md`) AND any existing local override, so your addition refines rather than
   duplicates or contradicts what's already there.
2. Choose the **single strongest** pattern per surface (≤2 edits total per run). Draft the
   *smallest* addition that addresses it — a clarified rule or one added condition. Re-check
   every line against the anti-suppression hard rule.
3. **Show the user the proposed addition and the audit record (Stage 3) BEFORE writing.**
   They approve in-session — that is the gate (there's no commit to gate on). If they object,
   revise or drop it.
4. On approval, **write to the `.local.md` file** (create it if missing). Append the new
   guidance under a dated heading, and set/update the `last_optimized:` stamp. Never write to
   the tracked base. Suggested file shape:
   ```markdown
   last_optimized: 2026-07-10T14:30:00Z

   <!-- Local, gitignored personalizations learned by improve-synthesizer. Composed AFTER
        the tracked base at build time. Never commit this file. -->

   ## 2026-07-10 — <short pattern name>
   <the minimal added guidance>
   ```
   Get the timestamp with `date -u +%Y-%m-%dT%H:%M:%SZ`. If the file already exists, update
   the single top `last_optimized:` line in place and append a new dated `##` section.

## Stage 3 — Audit record + close-out (no commit)

1. Show what changed in the local file(s). Since they're gitignored, `git diff` won't show
   them — instead print the appended section(s) directly (e.g. `cat` the new heading block).
2. Write a short **audit record** per edited override:
   - **Surface**: which override file, and why the pattern belongs there.
   - **Pattern**: the clustered failure signature + evidence (counts / avg scores /
     representative comments — but avoid pasting sensitive comment text into anything that
     might be shared; summarize).
   - **Edit**: what you added and why it addresses the pattern.
   - **Expected effect**: which future ratings/behaviors should improve.
   - **Evidence strength & risk**: for a narrative edit, state plainly it rests on comment
     text + judgment, not a measured signal. Confirm the edit cannot suppress any entry.
3. **Do NOT commit and do NOT `git add`.** The edit is already live for the next poll (the
   runtime composes the local override in at build time). Tell the user:
   - it takes effect on the next scheduled poll,
   - to **revert**, delete the dated `##` section from the `.local.md` file (there's no git
     history for it — deletion is the rollback), and
   - the `last_optimized:` stamp is what scopes the next run's feedback window.

## If there's nothing to do

If there's no feedback since the cutoff, or no pattern reaches its threshold, make **no
edit** (do not even bump the stamp — leave the window open for next time). Report what you
saw and say the synthesizer should stand. A no-op is a valid, healthy outcome — never invent
an edit to look productive.
