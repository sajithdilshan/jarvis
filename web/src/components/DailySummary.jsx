import { useEffect, useState } from "preact/hooks";

export function DailySummary() {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    fetch("/briefing-summary")
      .then((r) => r.ok ? r.json() : null)
      .then(setSummary)
      .catch(() => {});
  }, []);

  return (
    <div class="empty-state calm">
      <div class="calm-icon">✦</div>
      <p class="calm-text">All quiet. Jarvis is watching your sources.</p>
      {summary && summary.resolved_today > 0 && (
        <p class="calm-summary">
          {summary.resolved_today} item{summary.resolved_today > 1 ? "s" : ""} handled today.
        </p>
      )}
    </div>
  );
}
