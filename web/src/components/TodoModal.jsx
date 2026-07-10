// Create/edit modal for a todo — reuses the PermissionsPopup shell (.popup-*).
// `todo` null → create mode; an object → edit mode (prefilled).
import { useState, useRef, useEffect } from "preact/hooks";
import { upsertTodo } from "../store.js";

// <input type="date"> wants YYYY-MM-DD; the API stores full ISO timestamps. Convert
// both ways, treating the date as the due day (midnight local).
const toDateInput = (iso) => (iso ? iso.slice(0, 10) : "");
const toIso = (dateStr) => (dateStr ? new Date(`${dateStr}T00:00:00`).toISOString() : null);

export function TodoModal({ open, onClose, todo, onSaved }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [saving, setSaving] = useState(false);
  const descRef = useRef(null);

  // Prefill (or reset) whenever the modal opens or the target todo changes.
  useEffect(() => {
    if (!open) return;
    setTitle(todo?.title || "");
    setDescription(todo?.description || "");
    setDueDate(toDateInput(todo?.dueDate));
    setSaving(false);
  }, [open, todo]);

  // Auto-grow the description textarea to fit its content.
  useEffect(() => {
    const el = descRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 240) + "px";
  }, [description, open]);

  if (!open) return null;

  async function save(e) {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed || saving) return;
    setSaving(true);
    const body = {
      title: trimmed,
      description: description.trim() || null,
      due_date: toIso(dueDate),
    };
    try {
      let record;
      if (todo) {
        const res = await fetch(`/todos/${todo.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || "update failed");
        record = data.todo;
      } else {
        const res = await fetch("/todos", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        record = await res.json();
      }
      upsertTodo(record);
      onSaved?.(record);
      onClose();
    } catch {
      setSaving(false); // leave the modal open so the user can retry
    }
  }

  return (
    <div class="popup-overlay" onClick={onClose}>
      <div class="popup" onClick={(e) => e.stopPropagation()}>
        <div class="popup-header">
          <h2 class="popup-title">{todo ? "Edit todo" : "New todo"}</h2>
          <button class="popup-close" onClick={onClose}>×</button>
        </div>
        <form class="popup-body todo-form" onSubmit={save}>
          <label class="todo-field">
            <span class="todo-field-label">Title</span>
            <input
              class="todo-input"
              type="text"
              value={title}
              onInput={(e) => setTitle(e.currentTarget.value)}
              placeholder="What needs doing?"
              autofocus
            />
          </label>
          <label class="todo-field">
            <span class="todo-field-label">Description</span>
            <textarea
              ref={descRef}
              class="todo-input todo-textarea"
              rows="3"
              value={description}
              onInput={(e) => setDescription(e.currentTarget.value)}
              placeholder="Details (markdown supported)…"
            />
          </label>
          <label class="todo-field">
            <span class="todo-field-label">Due date</span>
            <input
              class="todo-input"
              type="date"
              value={dueDate}
              onInput={(e) => setDueDate(e.currentTarget.value)}
            />
          </label>
          <div class="popup-footer todo-form-footer">
            <button type="button" class="todo-btn todo-btn--ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" class="todo-btn todo-btn--primary" disabled={!title.trim() || saving}>
              {saving ? "Saving…" : todo ? "Save" : "Add todo"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
