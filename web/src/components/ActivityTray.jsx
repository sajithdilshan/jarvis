import { useState } from "preact/hooks";
import { Region } from "../Renderer.jsx";
import { sortByPriority } from "../utils/feedGrouping.js";

export function ActivityTray({ nodes }) {
  const askCount = nodes.filter((n) => n.props?.category === "ask").length;
  const [open, setOpen] = useState(true);
  if (nodes.length === 0) return null;

  const total = nodes.length;
  const summary =
    askCount > 0
      ? `${total} action${total === 1 ? "" : "s"} · ${askCount} need${askCount === 1 ? "s" : ""} you`
      : `${total} action${total === 1 ? "" : "s"} taken`;

  return (
    <section class={`activity-tray ${askCount > 0 ? "has-ask" : ""}`}>
      <button
        class="activity-bar"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span class="activity-icon">⚡</span>
        <span class="activity-summary">{summary}</span>
        <span class="activity-chevron">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div class="activity-body">
          <Region region="feed" nodes={sortByPriority(nodes)} />
        </div>
      )}
    </section>
  );
}
