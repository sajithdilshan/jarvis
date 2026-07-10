// One socket per session carries three message kinds; clicks/chat POST intents back.
import { appendToken, progress, connected, setViewModel, loadChatHistory, loadTodos } from "./store.js";
import { isBusy } from "./status.js";

let SESSION_ID = null;

// After a run finishes the header shows its terminal status ("Up to date ✓") briefly,
// then reverts to the idle "Jarvis online". This holds the pending revert timer so a
// new status arriving mid-countdown cancels it.
const STATUS_CLEAR_MS = 4000;
let statusClearTimer = null;

export async function initSession() {
  const res = await fetch("/session");
  const { session_id } = await res.json();
  SESSION_ID = session_id;
  loadChatHistory();
  loadTodos();
  return session_id;
}

async function reloadViewModel() {
  try {
    console.log("[ws] reconnect: re-fetching /view-model for latest briefing");
    const res = await fetch("/view-model");
    if (!res.ok) throw new Error(`/view-model HTTP ${res.status}`);
    const vm = await res.json();
    setViewModel(vm);
    console.log("[ws] view-model reloaded; region sizes:",
      Object.fromEntries(
        Object.entries(vm?.regions || {}).map(([r, n]) => [r, n.length])));
  } catch (err) {
    // Server not ready yet — keep current state and retry shortly so a reconnect
    // that races ahead of the server doesn't leave the briefing stale until refresh.
    console.warn("[ws] view-model reload failed, retrying in 1s:", err);
    setTimeout(reloadViewModel, 1000);
  }
}

// In dev, connect the WebSocket straight to the backend (default :3000) — Vite's WS
// proxy mishandles server keepalive ping/pong, so the socket cycles open/closed. HTTP
// requests still go through the proxy. In prod, same-origin (the FastAPI server serves
// both the SPA and the socket). Override the dev target with VITE_WS_TARGET if needed.
function wsBase() {
  if (import.meta.env.DEV) {
    return import.meta.env.VITE_WS_TARGET || "ws://localhost:4000";
  }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}`;
}

// Keep idle proxies/NAT from reaping the (server->client only) socket: send a tiny
// frame on an interval. The server's reader consumes and ignores it; the traffic
// resets idle timers on both ends. 30s is comfortably under typical 60s idle limits.
const HEARTBEAT_MS = 30000;

export function connect(sessionId, { resync = false } = {}) {
  console.log(`[ws] connecting to ${wsBase()}/ws/${sessionId} (resync=${resync})`);
  const ws = new WebSocket(`${wsBase()}/ws/${sessionId}`);
  let heartbeat = null;
  // On a *reconnect*, patches may have been missed while offline — reload the snapshot.
  ws.onopen = () => {
    console.log("[ws] open", { resync });
    connected.value = true;
    if (resync) reloadViewModel();
    heartbeat = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" }));
    }, HEARTBEAT_MS);
  };
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "feed_refresh") {
      // The feed changed server-side (scheduled run, chat-driven briefing, or a
      // dismiss). The DB is the source of truth — refetch /view-model and redraw.
      console.log("[ws] feed_refresh — reloading /view-model");
      reloadViewModel();
    } else if (msg.type === "chat_token") appendToken(msg.msg_id, msg.delta);
    else if (msg.type === "progress") {
      console.log(`[ws] progress: region=${msg.region || "_"} status=${msg.status}`);
      const region = msg.region || "_";
      progress.value = { ...progress.value, [region]: msg.status };
      // A new status supersedes any pending revert; reschedule below if it's terminal.
      if (statusClearTimer) clearTimeout(statusClearTimer);
      statusClearTimer = null;
      // A non-busy status on the session-wide channel is terminal (e.g. "Up to date ✓"):
      // show it briefly, then revert the header to the idle "Jarvis online".
      if (region === "_" && msg.status && !isBusy(msg.status)) {
        statusClearTimer = setTimeout(() => {
          const { _: _drop, ...rest } = progress.value;
          progress.value = rest;
          statusClearTimer = null;
        }, STATUS_CLEAR_MS);
      }
    } else {
      console.warn("[ws] unknown message type:", msg.type, msg);
    }
  };
  ws.onerror = (e) => {
    console.error("[ws] error", e);
  };
  ws.onclose = (e) => {
    console.warn(`[ws] closed (code=${e.code} reason="${e.reason}" clean=${e.wasClean}) `
      + "— reconnecting in 1s");
    connected.value = false;
    if (heartbeat) clearInterval(heartbeat);
    setTimeout(() => connect(sessionId, { resync: true }), 1000);
  };
  return ws;
}

// Clicks and chat both send intents; results arrive over the socket, not this fetch.
export async function sendIntent(intent, args = {}) {
  await fetch("/agent/invoke", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intent, args, session_id: SESSION_ID }),
  });
}

// Dismiss a card: presentation-layer only, no agent round-trip. The backend marks it
// resolved in briefing_log and broadcasts a feed_refresh (so all tabs redraw live).
export async function resolveItem(region, nodeId) {
  await fetch("/resolve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ region, node_id: nodeId }),
  });
}

// Dismiss every node in a list. Fires the per-item endpoint in parallel; the backend's
// feed_refresh broadcast redraws all tabs once the writes land.
export async function resolveAll(region, nodeIds) {
  await Promise.all(nodeIds.map((id) => resolveItem(region, id)));
}

// Rate whether an entry's priority (high/normal/low) was correct — the verifier signal
// for the self-improving priority harness. score 1..5; comment optional. Fire-and-forget:
// no feed_refresh, the rating doesn't change what's shown, only what the miner learns.
export async function sendFeedback(briefingId, score, comment = null) {
  await fetch("/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ briefing_id: briefingId, score, comment }),
  });
}
