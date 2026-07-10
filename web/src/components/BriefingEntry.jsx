import { useState } from "preact/hooks";
import { marked } from "marked";
import { sendFeedback } from "../socket.js";

const SOURCE_ICON = { gmail: "✉️", slack: "💬", github: "🐙", calendar: "📅" };
const TIER_ICON = { noticed: "⟡", did: "✓" };

// "Mar 4, 2:15 PM" — compact, locale-aware briefing timestamp.
function formatTimestamp(ts) {
  if (!ts) return null;
  const d = new Date(ts);
  if (isNaN(d.getTime())) return null;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function ContextBlock({ context }) {
  if (!context) return null;

  // If context has a "body" or "summary" key, render as markdown
  const text = context.body || context.summary || context.text;
  if (text) {
    return (
      <div
        class="entry-context-md"
        dangerouslySetInnerHTML={{ __html: marked.parse(text, { breaks: true }) }}
      />
    );
  }

  // Fallback: render as formatted key-value pairs
  const entries = Object.entries(context).filter(([_, v]) => v != null);
  if (entries.length === 0) return null;

  return (
    <dl class="entry-context-kv">
      {entries.map(([key, value]) => (
        <div key={key} class="kv-row">
          <dt>{key.replace(/_/g, " ")}</dt>
          <dd>{typeof value === "string" ? value : JSON.stringify(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

// Rate whether THIS entry's priority (high/normal/low) was the right call. 1 = badly
// mis-prioritized, 5 = spot-on. Optional comment behind an expander. This is the verifier
// signal for the self-improving priority harness — kept one-tap-cheap to lift response rate.
function PriorityRating({ briefingId, priority }) {
  const [score, setScore] = useState(null);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");
  const [saved, setSaved] = useState(false);

  const submit = (nextScore, nextComment) => {
    setScore(nextScore);
    sendFeedback(briefingId, nextScore, nextComment || null);
    setSaved(true);
  };

  return (
    <div class="entry-rating" onClick={(e) => e.stopPropagation()}>
      <span class="entry-rating-label">
        {saved ? "Thanks — noted" : `Priority "${priority || "normal"}" right?`}
      </span>
      <div class="entry-rating-stars" role="group" aria-label="Rate priority correctness 1 to 5">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            class={`entry-rating-dot ${score != null && n <= score ? "filled" : ""}`}
            title={`${n} / 5`}
            aria-label={`${n} out of 5`}
            aria-pressed={score === n}
            onClick={() => submit(n, comment)}
          >
            ★
          </button>
        ))}
        <button
          type="button"
          class="entry-rating-note"
          title="Add a comment"
          aria-label="Add a comment"
          onClick={() => setShowComment((v) => !v)}
        >
          {showComment ? "▾" : "💬"}
        </button>
      </div>
      {showComment && (
        <div class="entry-rating-comment">
          <input
            type="text"
            value={comment}
            placeholder="Why? (optional)"
            onInput={(e) => setComment(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && score != null) submit(score, e.currentTarget.value);
            }}
          />
          {score != null && (
            <button type="button" onClick={() => submit(score, comment)}>
              Save
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function BriefingEntry({ narrative, tier, source, priority, category, context, permission_ref, actions, node }) {
  const [expanded, setExpanded] = useState(false);
  const icon = TIER_ICON[tier] || "⟡";
  const sourceEmoji = SOURCE_ICON[source?.toLowerCase()] || "•";
  const refs = actions || [];
  const hasContext = context && Object.keys(context).length > 0;
  const timestamp = formatTimestamp(node?.ts);
  // Only "noticed" entries carry a synthesizer priority decision worth rating; "did"/"ask"
  // activity cards are not part of the priority harness's learning surface.
  const rateable = node?.id && category === "noticed";

  return (
    <div
      class={`briefing-entry ${tier} priority-${priority || "normal"}`}
      onClick={() => hasContext && setExpanded(!expanded)}
      role={hasContext ? "button" : undefined}
      aria-expanded={hasContext ? expanded : undefined}
    >
      <div class="entry-content">
        <span class={`entry-icon ${tier}`}>{icon}</span>
        <div class="entry-body">
          <div
            class="entry-narrative markdown-body"
            dangerouslySetInnerHTML={{ __html: marked.parse(narrative || "", { breaks: true }) }}
          />
          {timestamp && <time class="entry-timestamp" datetime={node.ts}>{timestamp}</time>}
          {tier === "did" && permission_ref && (
            <span class="entry-rule">Per your rule: "{permission_ref}"</span>
          )}
          {refs.length > 0 && (
            <div class="entry-refs">
              {refs.map((ref, i) => (
                <a
                  key={i}
                  class="entry-ref"
                  href={ref.url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  ↗ {ref.label}
                </a>
              ))}
            </div>
          )}
          {expanded && hasContext && (
            <div class="entry-context">
              <ContextBlock context={context} />
            </div>
          )}
          {hasContext && (
            <span class="entry-expand-hint">{expanded ? "▾" : "▸"}</span>
          )}
          {rateable && <PriorityRating briefingId={node.id} priority={priority} />}
        </div>
        <span class="entry-source">{sourceEmoji}</span>
      </div>
    </div>
  );
}
