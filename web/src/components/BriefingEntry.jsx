import { useState } from "preact/hooks";
import { marked } from "marked";

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

export function BriefingEntry({ narrative, tier, source, priority, context, permission_ref, actions, node }) {
  const [expanded, setExpanded] = useState(false);
  const icon = TIER_ICON[tier] || "⟡";
  const sourceEmoji = SOURCE_ICON[source?.toLowerCase()] || "•";
  const refs = actions || [];
  const hasContext = context && Object.keys(context).length > 0;
  const timestamp = formatTimestamp(node?.ts);

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
          <p class="entry-narrative">{narrative}</p>
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
        </div>
        <span class="entry-source">{sourceEmoji}</span>
      </div>
    </div>
  );
}
