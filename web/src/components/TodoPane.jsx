// Todo list — fills the right pane when chat is minimized. Cards ordered by due date
// ascending (server + store keep them sorted); complete/edit/delete per card.
import { useState } from "preact/hooks";
import { marked } from "marked";
import { todos, removeTodo } from "../store.js";
import { TodoModal } from "./TodoModal.jsx";
import { Confetti } from "./Confetti.jsx";

const dueFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });

function formatDue(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d)) return null;
  return dueFmt.format(d);
}

export function TodoPane() {
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null); // todo being edited, or null for create
  const [confetti, setConfetti] = useState(0); // bump to replay the burst
  const [leaving, setLeaving] = useState(null); // id of a card mid exit-animation

  const items = todos.value;

  function openCreate() {
    setEditing(null);
    setModalOpen(true);
  }

  function openEdit(todo) {
    setEditing(todo);
    setModalOpen(true);
  }

  async function complete(todo) {
    const res = await fetch(`/todos/${todo.id}/complete`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!data.ok) return;
    setConfetti((n) => n + 1); // matrix-green burst
    setLeaving(todo.id);
    // Let the exit transition play, then drop it from the signal.
    setTimeout(() => {
      removeTodo(todo.id);
      setLeaving((cur) => (cur === todo.id ? null : cur));
    }, 320);
  }

  async function remove(todo) {
    if (!confirm("Delete this todo? This cannot be undone.")) return;
    const res = await fetch(`/todos/${todo.id}`, { method: "DELETE" });
    if (res.ok) removeTodo(todo.id);
  }

  return (
    <div class="todo-pane">
      <Confetti trigger={confetti} />
      <div class="todo-pane-header">
        <span class="todo-pane-title">Todos</span>
        <button class="todo-add-btn" onClick={openCreate} title="Add a todo" aria-label="Add a todo">
          + add
        </button>
      </div>
      <div class="todo-list">
        {items.length === 0 ? (
          <div class="todo-empty">Nothing on the list. Click “add” to create a todo.</div>
        ) : (
          items.map((todo) => {
            const due = formatDue(todo.dueDate);
            return (
              <div
                key={todo.id}
                class={`card todo-card ${leaving === todo.id ? "leaving" : ""}`}
              >
                <div class="todo-card-main">
                  <button
                    class="todo-check"
                    onClick={() => complete(todo)}
                    title="Complete"
                    aria-label="Complete todo"
                  >
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </button>
                  <div class="todo-body">
                    <div class="todo-title-row">
                      <span class="todo-title">{todo.title}</span>
                      {due && <span class="todo-due">{due}</span>}
                    </div>
                    {todo.description && (
                      <div
                        class="todo-md"
                        dangerouslySetInnerHTML={{ __html: marked.parse(todo.description) }}
                      />
                    )}
                  </div>
                </div>
                <div class="todo-actions">
                  <button class="todo-action" onClick={() => openEdit(todo)} title="Edit" aria-label="Edit todo">
                    ✎
                  </button>
                  <button class="todo-action" onClick={() => remove(todo)} title="Delete" aria-label="Delete todo">
                    🗑
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
      <TodoModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        todo={editing}
        onSaved={() => setModalOpen(false)}
      />
    </div>
  );
}
