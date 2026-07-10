const AUTO_COLLAPSE_MS = 24 * 60 * 60 * 1000;

export function timeGroup(ts) {
  if (!ts) return "earlier";
  const now = Date.now();
  const diff = now - new Date(ts).getTime();
  if (diff < 3600000) return "now";
  const today = new Date().setHours(0, 0, 0, 0);
  if (new Date(ts).getTime() >= today) return "earlier";
  return "yesterday";
}

export function isStale(ts) {
  if (!ts) return true;
  return Date.now() - new Date(ts).getTime() > AUTO_COLLAPSE_MS;
}

export function sortByPriority(nodes) {
  const order = { high: 0, normal: 1, low: 2 };
  return [...nodes].sort((a, b) => {
    const pa = order[a.props?.priority] ?? 1;
    const pb = order[b.props?.priority] ?? 1;
    if (pa !== pb) return pa - pb;
    return 0;
  });
}

export function isActivityNode(node) {
  return node.props?.category === "did" || node.props?.category === "ask";
}

// Anti-suppression split: high-priority entries are always shown; normal + low go in a
// collapsible box. Nothing is ever dropped — the worst the synthesizer can do is mis-sort
// (high<->low), which stays visible and correctable via the rating control.
export function isHighPriority(node) {
  return node.props?.priority === "high";
}

export function groupVisibleFeed(nodes) {
  const groups = { now: [], earlier: [], yesterday: [] };
  for (const node of nodes) {
    groups[timeGroup(node.ts)].push(node);
  }
  return groups;
}
