// Briefing stream layout: single column feed + persistent chat dock.
import { useState } from "preact/hooks";
import { viewModel, progress, connected } from "./store.js";
import { Region } from "./Renderer.jsx";
import { ChatDock } from "./ChatDock.jsx";
import { PermissionsPopup } from "./components/PermissionsPopup.jsx";
import { ActivityTray } from "./components/ActivityTray.jsx";
import { DailySummary } from "./components/DailySummary.jsx";
import { TimeGroupSection } from "./components/TimeGroupSection.jsx";
import { useSplitter } from "./hooks/useSplitter.js";
import { humanizeStatus, isBusy } from "./status.js";
import { groupVisibleFeed, isActivityNode, isStale } from "./utils/feedGrouping.js";

const MAX_VISIBLE = 15;

export function Shell() {
  const [showPerms, setShowPerms] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const regions = viewModel.value.regions || {};
  const status = progress.value["_"];
  const allFeed = regions["feed"] || [];

  // Activity (did/ask) is pulled out of the main feed into a compact tray; the rest
  // ("noticed") flows into the time-grouped briefing below.
  const activity = allFeed.filter(isActivityNode);
  const feed = allFeed.filter((n) => !isActivityNode(n));

  // Split into visible and collapsed (stale 24h+ entries)
  const fresh = feed.filter((n) => !isStale(n.ts));
  const stale = feed.filter((n) => isStale(n.ts));

  // Apply max visible limit to fresh entries
  const visibleFresh = showAll ? fresh : fresh.slice(0, MAX_VISIBLE);
  const hiddenCount = showAll ? 0 : Math.max(0, fresh.length - MAX_VISIBLE);

  const groups = groupVisibleFeed(visibleFresh);

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

                {hiddenCount > 0 && (
                  <button class="show-more" onClick={() => setShowAll(true)}>
                    Show {hiddenCount} more
                  </button>
                )}

                {stale.length > 0 && (
                  <details class="stale-group">
                    <summary class="stale-toggle">
                      {stale.length} older item{stale.length > 1 ? "s" : ""}
                    </summary>
                    <Region region="feed" nodes={stale} />
                  </details>
                )}
              </>
            )}
          </main>
        </aside>

        <div class="splitter" id="splitter" role="separator" aria-label="Resize panes" />

        <section class="pane pane--chat">
          <div class="pane__header">
            <span class="pane__status">
              <span class={`pane__status-dot ${
                !connected.value ? "offline" : isBusy(status) ? "busy" : ""
              }`} />
              {!connected.value
                ? "Jarvis offline"
                : status ? humanizeStatus(status) : "Jarvis online"}
            </span>
          </div>
          <ChatDock />
        </section>
      </div>
      <PermissionsPopup open={showPerms} onClose={() => setShowPerms(false)} />
    </div>
  );
}
