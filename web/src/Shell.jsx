// Briefing stream layout: single column feed + persistent chat dock.
import { useState } from "preact/hooks";
import { viewModel, progress, connected, chatMinimized, setChatMinimized } from "./store.js";
import { Region } from "./Renderer.jsx";
import { ChatDock } from "./ChatDock.jsx";
import { PermissionsPopup } from "./components/PermissionsPopup.jsx";
import { ActivityTray } from "./components/ActivityTray.jsx";
import { DailySummary } from "./components/DailySummary.jsx";
import { TimeGroupSection } from "./components/TimeGroupSection.jsx";
import { useSplitter } from "./hooks/useSplitter.js";
import { humanizeStatus, isBusy } from "./status.js";
import { groupVisibleFeed, isActivityNode, isHighPriority, sortByPriority } from "./utils/feedGrouping.js";

export function Shell() {
  const [showPerms, setShowPerms] = useState(false);
  const regions = viewModel.value.regions || {};
  const status = progress.value["_"];
  const allFeed = regions["feed"] || [];

  // Activity (did/ask) is pulled out of the main feed into a compact tray; the rest
  // ("noticed") flows into the briefing below.
  const activity = allFeed.filter(isActivityNode);
  const feed = allFeed.filter((n) => !isActivityNode(n));

  // Anti-suppression split: high-priority entries are ALWAYS shown (time-grouped, at
  // top); normal + low go in a collapsible box below. Nothing is hidden or dropped — the
  // synthesizer can at worst mis-sort, which stays visible and correctable (see the
  // rating control on each entry). The user clears both bands by EOD.
  const high = feed.filter(isHighPriority);
  const rest = feed.filter((n) => !isHighPriority(n));
  const groups = groupVisibleFeed(high);

  const leftW = useSplitter();
  const unread = allFeed.length;

  return (
    <div class="shell">
      <header class="top-bar">
        <span class="brand">
          <span class="header-logo">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <rect x="5" y="6" width="14" height="12" rx="3" />
              <line x1="12" y1="2" x2="12" y2="6" />
              <circle cx="12" cy="2" r="1.4" fill="currentColor" stroke="none" />
              <circle cx="9.5" cy="12" r="1.5" fill="currentColor" stroke="none" />
              <circle cx="14.5" cy="12" r="1.5" fill="currentColor" stroke="none" />
            </svg>
          </span>
          JARVIS
        </span>
        <button
          class="settings-btn"
          onClick={() => setShowPerms(true)}
          title="Permissions & Rules"
        >
          ⚙
        </button>
      </header>
      <div class="workspace">
        <aside class="pane pane--left" style={{ width: `${leftW}px` }}>
          <div class="pane__header">
            <span class="pane__meta">
              <span>{unread}</span> update{unread === 1 ? "" : "s"}
            </span>
          </div>
          <main class="feed pane__body">
            {allFeed.length === 0 ? (
              <DailySummary />
            ) : (
              <>
                <ActivityTray nodes={activity} />
                <TimeGroupSection label="Now" nodes={groups.now} />
                <TimeGroupSection label="Earlier today" nodes={groups.earlier} />
                <TimeGroupSection label="Yesterday" nodes={groups.yesterday} />

                {rest.length > 0 && (
                  <details class="lowprio-group">
                    <summary class="lowprio-toggle">
                      {rest.length} lower-priority update{rest.length > 1 ? "s" : ""}
                    </summary>
                    <Region region="feed" nodes={sortByPriority(rest)} />
                  </details>
                )}
              </>
            )}
          </main>
        </aside>

        <div class="splitter" id="splitter" role="separator" aria-label="Resize panes" />

        <section class={`pane pane--chat ${chatMinimized.value ? "chat-min" : ""}`}>
          <div class="pane__header">
            <span class="pane__status">
              <span class={`pane__status-dot ${
                !connected.value ? "offline" : isBusy(status) ? "busy" : ""
              }`} />
              {!connected.value
                ? "Jarvis offline"
                : status ? humanizeStatus(status) : "Jarvis online"}
            </span>
            <button
              class="chat-min-btn"
              onClick={() => setChatMinimized(true)}
              title="Minimize chat"
              aria-label="Minimize chat"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </button>
          </div>
          <ChatDock />
          {chatMinimized.value && (
            <button class="chat-pill" onClick={() => setChatMinimized(false)} aria-label="Open chat">
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <rect x="5" y="6" width="14" height="12" rx="3" fill="none" stroke="currentColor" stroke-width="1.6" />
                <line x1="12" y1="2" x2="12" y2="6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                <circle cx="12" cy="2" r="1.4" fill="currentColor" />
                <circle cx="9.5" cy="12" r="1.5" fill="currentColor" />
                <circle cx="14.5" cy="12" r="1.5" fill="currentColor" />
              </svg>
              Jarvis
            </button>
          )}
        </section>
      </div>
      <PermissionsPopup open={showPerms} onClose={() => setShowPerms(false)} />
    </div>
  );
}
