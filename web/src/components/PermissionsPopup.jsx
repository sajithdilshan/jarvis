import { useState, useEffect } from "preact/hooks";

export function PermissionsPopup({ open, onClose }) {
  const [permissions, setPermissions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    fetch("/permissions")
      .then((r) => r.json())
      .then((data) => { setPermissions(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [open]);

  if (!open) return null;

  async function toggle(id) {
    await fetch(`/permissions/${id}/toggle`, { method: "POST" });
    setPermissions((prev) =>
      prev.map((p) => (p.id === id ? { ...p, active: !p.active } : p))
    );
  }

  async function remove(id) {
    if (!confirm("Delete this rule permanently? This cannot be undone.")) return;
    const res = await fetch(`/permissions/${id}`, { method: "DELETE" });
    if (res.ok) {
      setPermissions((prev) => prev.filter((p) => p.id !== id));
    }
  }

  return (
    <div class="popup-overlay" onClick={onClose}>
      <div class="popup" onClick={(e) => e.stopPropagation()}>
        <div class="popup-header">
          <h2 class="popup-title">Permissions</h2>
          <button class="popup-close" onClick={onClose}>×</button>
        </div>
        <div class="popup-body">
          {loading ? (
            <div class="popup-empty">Loading...</div>
          ) : permissions.length === 0 ? (
            <div class="popup-empty">
              No rules yet. Tell Jarvis in chat what to do automatically.
            </div>
          ) : (
            <ul class="perm-list">
              {permissions.map((perm) => (
                <li key={perm.id} class={`perm-item ${perm.active ? "" : "inactive"}`}>
                  <div class="perm-info">
                    <span class="perm-desc">{perm.description}</span>
                    <span class="perm-meta">
                      {perm.source && <span class="perm-source">{perm.source}</span>}
                      {perm.allowed_actions?.length > 0 && (
                        <span class="perm-actions">
                          {perm.allowed_actions.join(", ")}
                        </span>
                      )}
                    </span>
                  </div>
                  <div class="perm-controls">
                    <button
                      class={`perm-toggle ${perm.active ? "active" : ""}`}
                      onClick={() => toggle(perm.id)}
                      title={perm.active ? "Pause this rule" : "Reactivate this rule"}
                    >
                      <span class="toggle-track">
                        <span class="toggle-thumb" />
                      </span>
                    </button>
                    <button
                      class="perm-delete"
                      onClick={() => remove(perm.id)}
                      title="Delete this rule"
                      aria-label="Delete this rule"
                    >
                      🗑
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div class="popup-footer">
          Manage rules via chat — "archive Jenkins spam automatically"
        </div>
      </div>
    </div>
  );
}
