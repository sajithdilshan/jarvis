# Google Calendar MCP setup (self-hosted, OAuth2)

Jarvis's `google-calendar` MCP server runs
[`@cocal/google-calendar-mcp`](https://www.npmjs.com/package/@cocal/google-calendar-mcp)
over stdio. There is **no static API token** — Google Calendar uses OAuth2, so you create a Google
Cloud OAuth client once and run a one-time browser auth that caches a refresh token.

> **Already have Gmail MCP set up?** You can reuse the same Google Cloud project — just enable the
> Calendar API (step 1.2) and reuse the same OAuth client JSON. The credentials are stored separately
> from Gmail.

## 1. Create a Google Cloud OAuth client

1. Go to <https://console.cloud.google.com/> and create (or select) a project.
2. **APIs & Services → Library** → search **Google Calendar API** → **Enable**.
3. **APIs & Services → OAuth consent screen** (skip if already configured for Gmail):
   - User type: **External**.
   - Fill app name / support email.
   - **Add your own Google account as a Test user** (so you can authorize without app
     verification).
   - Scopes: you can leave the default; the server requests Calendar scopes at auth time.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Desktop app**.
   - **Download JSON**. You'll get a file like `client_secret_xxx.json`.
   - If you already have one from Gmail setup, you can reuse that same file.

## 2. Place the OAuth client where the server expects it

The server reads the OAuth client credentials via the `GOOGLE_OAUTH_CREDENTIALS` environment
variable. Create the directory and place the file:

```bash
mkdir -p ~/.google-calendar-mcp
# rename the downloaded file to gcp-oauth.keys.json
mv ~/Downloads/client_secret_*.json ~/.google-calendar-mcp/gcp-oauth.keys.json
```

## 3. Run the one-time auth (on the host, opens a browser)

```bash
jarvis-auth calendar
```

This wraps `npx -y @cocal/google-calendar-mcp auth` (and first checks that
`~/.google-calendar-mcp/gcp-oauth.keys.json` exists, passing it via `GOOGLE_OAUTH_CREDENTIALS`).
You can also run the raw command directly:

```bash
GOOGLE_OAUTH_CREDENTIALS=~/.google-calendar-mcp/gcp-oauth.keys.json npx -y @cocal/google-calendar-mcp auth
```

- A browser opens → pick your Google account → approve Calendar access.
- On success it writes the cached **refresh token** to `~/.config/google-calendar-mcp/tokens.json`.
- This file is what every later run uses — you won't need the browser again.

After this you have:

```
~/.google-calendar-mcp/
└── gcp-oauth.keys.json              # OAuth client (from Google Cloud)

~/.config/google-calendar-mcp/
└── tokens.json                      # cached refresh token (created by `auth`)
```

## 4. How Jarvis uses it

`mcp/servers.yaml` defines the `google-calendar` server:

```yaml
google-calendar:
  type: stdio
  command: "npx"
  args: ["-y", "@cocal/google-calendar-mcp"]
  env:
    # $HOME works in both Docker (/root) and local (/Users/xxx)
    GOOGLE_OAUTH_CREDENTIALS: "${HOME}/.google-calendar-mcp/gcp-oauth.keys.json"
  deny_tools:
    - delete-event
    - manage-accounts
```

The `GOOGLE_OAUTH_CREDENTIALS` env var tells the server where to find the OAuth client JSON.
Using `${HOME}` makes it work in both Docker (`/root`) and local environments.

### Docker

`docker-compose.yml` mounts two directories into the container:

```yaml
volumes:
  - ~/.google-calendar-mcp:/root/.google-calendar-mcp           # OAuth client JSON
  - ~/.config/google-calendar-mcp:/root/.config/google-calendar-mcp  # cached tokens
```

Do the `auth` step on the host first; the container reuses the cached token.

## 5. Verify

```bash
jarvis-auth status
```

You should see `✓ google-calendar OAuth token cached` — this checks the cached token at
`~/.config/google-calendar-mcp/tokens.json`. For a deeper check that the server starts and
lists tools (Ctrl-C to exit):

```bash
GOOGLE_OAUTH_CREDENTIALS=~/.google-calendar-mcp/gcp-oauth.keys.json npx -y @cocal/google-calendar-mcp
```

Or use the listing script:

```bash
uv run python scripts/list_mcp_tools.py google-calendar
```

You should see tools like `list-calendars`, `list-events`, `get-event`, `create-event`, etc.

## 6. Available tools

The MCP server exposes these Calendar tools:

| Tool | Description |
|------|-------------|
| `list-calendars` | List all calendars accessible to the account |
| `list-events` | List events from a calendar (with date range filters) |
| `get-event` | Get details of a specific event |
| `create-event` | Create a new calendar event |
| `update-event` | Update an existing event |
| `delete-event` | Delete an event (blocked by default in Jarvis) |
| `manage-accounts` | Manage connected Google accounts (blocked by default) |

## 7. Troubleshooting

### "GOOGLE_OAUTH_CREDENTIALS environment variable is not set"
Ensure you're passing the env var when running the server:
```bash
GOOGLE_OAUTH_CREDENTIALS=~/.google-calendar-mcp/gcp-oauth.keys.json npx -y @cocal/google-calendar-mcp
```

### "Access blocked: This app's request is invalid"
- Ensure your Google account is added as a **Test user** in the OAuth consent screen.
- The OAuth client type must be **Desktop app**, not Web application.

### "Token has been expired or revoked"
Re-run the auth flow:
```bash
rm ~/.config/google-calendar-mcp/tokens.json
jarvis-auth calendar
```

### Server doesn't start in Docker
- Verify both volume mounts exist in `docker-compose.yml`:
  ```yaml
  - ~/.google-calendar-mcp:/root/.google-calendar-mcp
  - ~/.config/google-calendar-mcp:/root/.config/google-calendar-mcp
  ```
- Check that `~/.google-calendar-mcp/gcp-oauth.keys.json` exists on the host.
- Check that `~/.config/google-calendar-mcp/tokens.json` exists on the host.
- Ensure Node 18+ is installed in the container.

## Security note

This server gets read/write access to your Google Calendar (view, create, modify, delete events).
The credentials stay on your machine (`~/.google-calendar-mcp/` and `~/.config/google-calendar-mcp/`),
never in the repo or env files. Review the package before trusting it. Jarvis blocks `delete-event`
and `manage-accounts` by default via `deny_tools` in `mcp/servers.yaml`.
