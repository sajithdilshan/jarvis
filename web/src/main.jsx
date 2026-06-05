// Bootstrap: fetch /session, open the WS, load the latest ViewModel for first paint.
import { render } from "preact";
import { Shell } from "./Shell.jsx";
import { initSession, connect } from "./socket.js";
import { setViewModel } from "./store.js";
import "./styles.css";

async function boot() {
  const sessionId = await initSession();
  connect(sessionId);
  try {
    const vm = await (await fetch("/view-model")).json();
    setViewModel(vm);
  } catch {
    // First boot with no sessions yet — start empty.
  }
  render(<Shell />, document.getElementById("app"));
}

boot();
