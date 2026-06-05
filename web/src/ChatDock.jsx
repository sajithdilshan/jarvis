// Persistent chat dock — part of the static shell, NEVER touched by patches, so a
// half-typed message and the streaming reply survive dashboard updates.
import { useState, useRef, useEffect, useLayoutEffect } from "preact/hooks";
import { marked } from "marked";
import { chat, thinking, connected, loadingOlder, pushUserMessage, loadOlderMessages } from "./store.js";
import { sendIntent } from "./socket.js";
import { THINKING_WORDS } from "./thinkingWords.js";

marked.setOptions({ breaks: true, gfm: true });

const pickWord = () => THINKING_WORDS[Math.floor(Math.random() * THINKING_WORDS.length)];

const tsFmt = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const dateFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });

// Animated Jarvis head + a status word that rotates every ~2.5s while waiting.
function ThinkingIndicator() {
  const [word, setWord] = useState(pickWord);

  useEffect(() => {
    const id = setInterval(() => setWord(pickWord()), 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div class="chat-msg assistant thinking-bubble">
      <span class="thinking">
        <svg class="jarvis-head" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
          <rect x="5" y="6" width="14" height="12" rx="3" fill="none" stroke="currentColor" stroke-width="1.6" />
          <line x1="12" y1="2" x2="12" y2="6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
          <circle cx="12" cy="2" r="1.4" fill="currentColor" />
          <circle class="eye" cx="9.5" cy="12" r="1.5" fill="currentColor" />
          <circle class="eye" cx="14.5" cy="12" r="1.5" fill="currentColor" />
        </svg>
        <span class="thinking-word">{word}…</span>
      </span>
    </div>
  );
}

export function ChatDock() {
  const [draft, setDraft] = useState("");
  const threadRef = useRef(null);
  const inputRef = useRef(null);
  const stickToBottom = useRef(true); // user is at the bottom — keep new messages in view
  const prependAnchor = useRef(null); // scrollHeight captured before an older-page prepend

  // Auto-grow the textarea up to a max height as the draft changes.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [draft]);

  // After an older page is prepended, restore the viewport so the anchored message
  // stays put (the thread grew upward). Runs before paint to avoid a visible jump.
  useLayoutEffect(() => {
    const el = threadRef.current;
    if (el && prependAnchor.current != null) {
      el.scrollTop += el.scrollHeight - prependAnchor.current;
      prependAnchor.current = null;
    }
  }, [chat.value]);

  // Keep the newest message / streaming token in view — but only when the user is
  // already at the bottom, so loading older history doesn't yank them down.
  useEffect(() => {
    const el = threadRef.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [chat.value, thinking.value]);

  const onScroll = () => {
    const el = threadRef.current;
    if (!el) return;
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    if (el.scrollTop < 60 && !loadingOlder.value) {
      prependAnchor.current = el.scrollHeight;
      loadOlderMessages().then((n) => {
        if (!n) prependAnchor.current = null; // nothing prepended — skip restore
      });
    }
  };

  const submit = (e) => {
    e.preventDefault();
    if (!connected.value) return; // no socket to carry the reply — drop the send
    const message = draft.trim();
    if (!message) return;
    pushUserMessage(message);
    sendIntent("chat", { message });
    setDraft("");
  };

  return (
    <div class="chat-dock">
      <div class="chat-thread" ref={threadRef} onScroll={onScroll}>
        {loadingOlder.value && (
          <div class="chat-older-spinner" aria-label="Loading older messages">
            <span class="spinner-dot" />
          </div>
        )}
        {chat.value.map((m) => (
          <div key={m.id} class={`chat-ts-wrap ${m.role}`}>
            <div class={`chat-msg ${m.role}`}>
              {m.role === "assistant" ? (
                <div
                  class="markdown-body"
                  dangerouslySetInnerHTML={{ __html: marked.parse(m.text) }}
                />
              ) : (
                m.text
              )}
            </div>
            {m.ts && (
              <span class="chat-ts">
                <span class="date">{dateFmt.format(m.ts)}</span>
                <span class="dot">·</span>
                {tsFmt.format(m.ts)}
              </span>
            )}
          </div>
        ))}
        {thinking.value && <ThinkingIndicator />}
      </div>
      <form class={`chat-input ${connected.value ? "" : "offline"}`} onSubmit={submit}>
        <textarea
          ref={inputRef}
          rows="1"
          value={draft}
          disabled={!connected.value}
          onInput={(e) => setDraft(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit(e);
            }
          }}
          placeholder={connected.value ? "Ask Jarvis anything…" : "Jarvis is offline — reconnecting…"}
          aria-label="Message Jarvis"
        />
        <button type="submit" class="send" aria-label="Send" disabled={!connected.value}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </form>
    </div>
  );
}
