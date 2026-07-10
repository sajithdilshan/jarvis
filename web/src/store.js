// Single source of UI truth on the client. The feed is never patched incrementally:
// the server owns it in briefing_log and pings feed_refresh, after which we refetch
// /view-model and replace the tree wholesale (see setViewModel).
import { signal } from "@preact/signals";

export const viewModel = signal({ regions: {} }); // mirrors server ViewModel
export const chat = signal([]); // chat thread: [{ id, role, text }]
export const progress = signal({}); // region_id -> status string
export const thinking = signal(false); // true between send and first reply token
export const connected = signal(false); // WebSocket live? drives the offline indicator
export const loadingOlder = signal(false); // fetching an older page (drives the spinner)
export const chatMinimized = signal(localStorage.getItem("chatMinimized") === "1"); // chat collapsed to a floating pill
export const todos = signal([]); // todo-list pane: [{ id, title, description, dueDate, completed }]

export function setChatMinimized(v) {
  chatMinimized.value = v;
  localStorage.setItem("chatMinimized", v ? "1" : "0");
}

const toTodo = (t) => ({
  id: t.id,
  title: t.title,
  description: t.description || "",
  dueDate: t.due_date || null,
  completed: t.completed,
});

export async function loadTodos() {
  try {
    const res = await fetch("/todos");
    const rows = await res.json();
    todos.value = rows.map(toTodo);
  } catch { /* server not ready */ }
}

// Merge a created/updated todo record from the server into the signal, re-sorting by
// due date ascending (nulls last) to mirror the server's list ordering.
export function upsertTodo(record) {
  const t = toTodo(record);
  const rest = todos.value.filter((x) => x.id !== t.id);
  todos.value = [...rest, t].sort(sortTodos);
}

export function removeTodo(id) {
  todos.value = todos.value.filter((t) => t.id !== id);
}

function sortTodos(a, b) {
  if (a.dueDate && b.dueDate) return a.dueDate < b.dueDate ? -1 : a.dueDate > b.dueDate ? 1 : 0;
  if (a.dueDate) return -1; // nulls last
  if (b.dueDate) return 1;
  return a.id - b.id;
}

let oldestId = null; // cursor: id of the oldest message currently in the thread

export function setViewModel(vm) {
  viewModel.value = vm && vm.regions ? vm : { regions: {} };
}

// Append a streaming chat token to the active assistant message (create it if new).
export function appendToken(msgId, delta) {
  thinking.value = false; // first token arrived — drop the typing indicator
  const thread = chat.value.slice();
  const i = thread.findIndex((m) => m.id === msgId);
  if (i >= 0) thread[i] = { ...thread[i], text: thread[i].text + delta };
  else thread.push({ id: msgId, role: "assistant", text: delta, ts: Date.now() });
  chat.value = thread;
}

export function pushUserMessage(text) {
  chat.value = [...chat.value, { id: `u-${Date.now()}`, role: "user", text, ts: Date.now() }];
  thinking.value = true; // awaiting Jarvis's reply
}

const toMsg = (m) => ({
  id: `hist-${m.id}`,
  role: m.role,
  text: m.text,
  ts: m.ts ? Date.parse(m.ts) : null,
});

export async function loadChatHistory() {
  try {
    const res = await fetch("/chat-history");
    const messages = await res.json();
    if (messages.length) {
      chat.value = messages.map(toMsg);
      oldestId = messages[0].id;
    }
  } catch { /* server not ready */ }
}

// Fetch the page of messages older than the current cursor and prepend it.
// Returns the number of messages prepended (0 when history is exhausted).
export async function loadOlderMessages() {
  if (loadingOlder.value || oldestId == null) return 0;
  loadingOlder.value = true;
  try {
    const res = await fetch(`/chat-history?before_id=${oldestId}`);
    const messages = await res.json();
    if (messages.length) {
      chat.value = [...messages.map(toMsg), ...chat.value];
      oldestId = messages[0].id;
    }
    return messages.length;
  } catch {
    return 0;
  } finally {
    loadingOlder.value = false;
  }
}
