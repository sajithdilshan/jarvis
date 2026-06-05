// Turn raw progress status strings into human-readable top-bar text.
// e.g. "gmail_checking" -> "Checking gmail…", "synthesizing" -> "Synthesizing…"
export function humanizeStatus(status) {
  if (!status) return "";
  if (status.endsWith("_checking")) return `Checking ${status.replace("_checking", "")}…`;
  if (status.endsWith("_complete")) return `${status.replace("_complete", "")} ✓`;
  if (status === "synthesizing") return "Synthesizing…";
  if (status === "synthesize_complete") return "Up to date ✓";
  return status.replace(/_/g, " ");
}

// Whether the current status represents in-flight work (drives the pulse indicator).
export function isBusy(status) {
  return !!status && (status.endsWith("_checking") || status === "synthesizing");
}
