import { Region } from "../Renderer.jsx";
import { sortByPriority } from "../utils/feedGrouping.js";

export function TimeGroupSection({ label, nodes }) {
  if (nodes.length === 0) return null;
  return (
    <section class="time-group">
      <div class="time-label">{label}</div>
      <Region region="feed" nodes={sortByPriority(nodes)} />
    </section>
  );
}
