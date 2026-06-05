# Gmail MCP setup (self-hosted, OAuth2)

Jarvis's `google` MCP server runs the self-hosted
[`@gongrzhe/server-gmail-autoauth-mcp`](https://www.npmjs.com/package/@gongrzhe/server-gmail-autoauth-mcp)
over stdio. There is **no static API token** — Gmail uses OAuth2, so you create a Google
Cloud OAuth client once and run a one-time browser auth that caches a refresh token.

## 1. Create a Google Cloud OAuth client

1. Go to <https://console.cloud.google.com/> and create (or select) a project.
2. **APIs & Services → Library** → search **Gmail API** → **Enable**.
3. **APIs & Services → OAuth consent screen**:
   - User type: **External**.
   - Fill app name / support email.
   - **Add your own Google account as a Test user** (so you can authorize without app
     verification).
   - Scopes: you can leave the default; the server requests Gmail scopes at auth time.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Desktop app**.
   - **Download JSON**. You'll get a file like `client_secret_xxx.json`.

## 2. Place the OAuth client where the server expects it

The server reads credentials from `~/.gmail-mcp/`:

```bash
mkdir -p ~/.gmail-mcp
# rename the downloaded file to gcp-oauth.keys.json
mv ~/Downloads/client_secret_*.json ~/.gmail-mcp/gcp-oauth.keys.json
```

## 3. Run the one-time auth (on the host, opens a browser)

```bash
jarvis-auth gmail
```

This wraps `npx -y @gongrzhe/server-gmail-autoauth-mcp auth` (and first checks that
`~/.gmail-mcp/gcp-oauth.keys.json` exists). You can also run the raw command directly:

```bash
npx -y @gongrzhe/server-gmail-autoauth-mcp auth
```

- A browser opens → pick your Google account → approve.
- On success it writes `~/.gmail-mcp/credentials.json` (the cached **refresh token**).
- This file is what every later run uses — you won't need the browser again.

After this you have:

```
~/.gmail-mcp/
├── gcp-oauth.keys.json     # OAuth client (from Google Cloud)
└── credentials.json        # cached refresh token (created by `auth`)
```

## 4. How Jarvis uses it

`mcp/servers.yaml` already points the `google` server at this command:

```yaml
google:
  type: stdio
  command: "npx"
  args: ["-y", "@gongrzhe/server-gmail-autoauth-mcp"]
```

- **Local run** (`uv run python -m jarvis.main`): works as long as `~/.gmail-mcp/` exists
  and `npx` (Node 18+) is on your PATH.
- **Docker**: the Dockerfile installs Node, and `docker-compose.yml` mounts
  `~/.gmail-mcp` into the container at `/root/.gmail-mcp`. Do the `auth` step on the host
  first; the container reuses the cached token.

## 5. Verify

```bash
jarvis-auth status
```

You should see `✓ google   OAuth token cached`. For a deeper check that the server starts
and lists tools (Ctrl-C to exit):

```bash
npx -y @gongrzhe/server-gmail-autoauth-mcp
```

Then trigger a Jarvis poll — the gmail agent should return real unread emails instead of
failing to connect.

## Security note

This server gets full read/write access to your Gmail (send, modify, delete, filters).
The credentials stay on your machine (`~/.gmail-mcp/`), never in the repo or env files.
Review the package before trusting it. (Jarvis intentionally uses full access so the
assistant can act on mail, not just read it.)
