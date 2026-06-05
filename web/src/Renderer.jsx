// Maps node.type -> component; the ONLY code that turns ViewModel nodes into DOM.
import { COMPONENTS } from "./components/registry.js";
import { resolveItem } from "./socket.js";

// Types that aren't user-dismissable (system chrome).
const NOT_RESOLVABLE = new Set(["unknown"]);

// Newest-first: sort by `ts` (ISO) descending. Nodes without a ts keep their relative
// order and sit after the timestamped ones. Stable regardless of patch arrival order.
function byRecency(nodes) {
  return nodes
    .map((node, i) => ({ node, i }))
    .sort((a, b) => {
      const ta = a.node.ts || "";
      const tb = b.node.ts || "";
      if (ta && tb) return ta < tb ? 1 : ta > tb ? -1 : a.i - b.i;
      if (ta) return -1;
      if (tb) return 1;
      return a.i - b.i;
    })
    .map((x) => x.node);
}

export function Region({ region, nodes = [] }) {
  return byRecency(nodes).map((node) => {
    const Comp = COMPONENTS[node.type] ?? COMPONENTS.unknown;
    const card = (
      <Comp key={node.id} {...node.props} actions={node.actions} node={node} />
    );
    if (NOT_RESOLVABLE.has(node.type)) return card;
    return (
      <div key={node.id} class="card-wrap">
        {card}
        <button
          class="resolve-btn"
          title="Dismiss"
          aria-label="Dismiss"
          onClick={() => resolveItem(region, node.id)}
        >
          ✓
        </button>
      </div>
    );
  });
}
