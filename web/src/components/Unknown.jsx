// Fallback for any node type the client doesn't know how to render.
export function Unknown({ node }) {
  return (
    <div class="card unknown">
      <strong>Unknown component: {node?.type}</strong>
    </div>
  );
}
