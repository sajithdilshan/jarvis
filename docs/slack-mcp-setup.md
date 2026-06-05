# Slack MCP setup (browser-token auth)

Jarvis's `slack` MCP server runs
[`slack-mcp-server`](https://github.com/korotovsky/slack-mcp-server) over stdio. We use
**browser-token auth** — no Slack app to create, no admin approval. You copy two values
out of your already-logged-in Slack web session: the workspace token (`xoxc-…`) and the
session cookie (`xoxd-…`).

> These are *your* session credentials. Anyone holding them can act as you in Slack.
> They live only in `.env` (gitignored), never in the repo.

## 1. Log in to Slack in your browser

Open <https://app.slack.com> and sign in to the workspace you want Jarvis to read.

## 2. Grab the `xoxc` token (workspace token)

1. Open your browser's **DevTools** (⌥⌘I on macOS) → **Console** tab.
2. Paste and run:
   ```js
   JSON.parse(localStorage.localConfig_v2).teams[
     document.location.pathname.match(/\/client\/(T[A-Z0-9]+)/)?.[1] ||
     Object.keys(JSON.parse(localStorage.localConfig_v2).teams)[0]
   ].token
   ```
   It prints a string starting with `xoxc-…`. Copy it.

   *If the console blocks pasting,* type `allow pasting` first, then re-paste.

## 3. Grab the `xoxd` token (session cookie)

1. DevTools → **Application** tab → **Storage → Cookies → `https://app.slack.com`**.
2. Find the cookie named **`d`**. Its value starts with `xoxd-…`. Copy the whole value.

## 4. Put both in `.env`

```bash
SLACK_MCP_XOXC_TOKEN=xoxc-...        # from step 2
SLACK_MCP_XOXD_TOKEN=xoxd-...        # from step 3 (the `d` cookie value)
```

`docker-compose.yml` loads `.env` via `env_file`, so these are forwarded into the
container automatically — no compose edits needed.

## 5. How Jarvis uses it

`mcp/servers.yaml` already points the `slack` server here:

```yaml
slack:
  type: stdio
  command: "npx"
  args: ["-y", "slack-mcp-server@latest", "--transport", "stdio"]
  env:
    SLACK_MCP_XOXC_TOKEN: "${SLACK_MCP_XOXC_TOKEN}"
    SLACK_MCP_XOXD_TOKEN: "${SLACK_MCP_XOXD_TOKEN}"
    # Write tools are off by default upstream for safety; we opt in:
    SLACK_MCP_MARK_TOOL: "true"          # enable conversations_mark (mark as read)
    SLACK_MCP_ADD_MESSAGE_TOOL: "true"   # enable conversations_add_message (post messages)
```

- **Docker**: the Dockerfile pre-installs `slack-mcp-server` so `npx` starts instantly.
- **Local run**: works as long as `npx` (Node 18+) is on your PATH.
- **Message posting**: `conversations_add_message` is gated behind `SLACK_MCP_ADD_MESSAGE_TOOL`.
  `"true"` allows all channels; set a comma-separated list of channel IDs to restrict it.

## 6. Verify

```bash
SLACK_MCP_XOXC_TOKEN=xoxc-... SLACK_MCP_XOXD_TOKEN=xoxd-... \
  npx -y slack-mcp-server@latest --transport stdio
```

It should start and wait on stdio (Ctrl-C to exit). Then trigger a Jarvis poll — the
slack agent should return real channel activity instead of failing to connect.

## Token lifetime

Browser session tokens **rotate** — if you log out of Slack or the session expires,
re-grab both values (steps 2–3) and update `.env`. For a long-lived alternative, switch
to a Slack user OAuth token (`xoxp-…`) via a created Slack app; the server accepts that
too (set `SLACK_MCP_XOXP_TOKEN` instead of the xoxc/xoxd pair).
