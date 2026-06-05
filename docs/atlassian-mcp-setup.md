# Atlassian MCP setup (remote MCP, OAuth 2.1)

Jarvis's `atlassian` MCP server is Atlassian's **official remote MCP**
(<https://mcp.atlassian.com/v1/mcp>), covering both **Jira** and **Confluence**. It is
HTTP-only and gated behind an interactive OAuth 2.1 browser flow that cannot run inside the
container. We bridge it with
[`mcp-remote`](https://www.npmjs.com/package/mcp-remote) (stdio ↔ remote HTTP): it performs
the OAuth dance on the host and caches the token under `~/.mcp-auth`. `docker-compose.yml`
mounts that directory into the container, so it starts with a warm token.

> There is **no static API token** — auth is OAuth. You log in once in the browser; the
> cached token (and its refresh token) live only under `~/.mcp-auth`, never in the repo.

## 1. Run the one-time auth (on the host, opens a browser)

```bash
jarvis-auth atlassian
```

This runs `npx -y mcp-remote https://mcp.atlassian.com/v1/mcp`:

- A browser opens → log in to Atlassian → approve access to your Jira/Confluence sites.
- On success the OAuth token is cached under `~/.mcp-auth/`.
- Keep the process running until the token is written, then **Ctrl-C** — that's fine.

The first run may also download `mcp-remote` itself, so allow a little extra time.

## 2. How Jarvis uses it

`mcp/servers.yaml` defines the `atlassian` server:

```yaml
atlassian:
  type: stdio
  command: "npx"
  args: ["-y", "mcp-remote", "https://mcp.atlassian.com/v1/mcp"]
  # First run may download mcp-remote and refresh the OAuth token — allow a long init.
  timeout: 120
  deny_tools:
    - addWorklogToJiraIssue
```

- **Local run** (`uv run python -m jarvis.main`): works as long as `~/.mcp-auth/` holds a
  valid token and `npx` (Node 18+) is on your PATH.
- **Docker**: `docker-compose.yml` mounts `~/.mcp-auth` into the container at
  `/root/.mcp-auth`. Do the `jarvis-auth atlassian` step on the host first; the container
  reuses the cached token.

## 3. Verify

```bash
jarvis-auth status
```

You should see `✓ atlassian  OAuth token cached`. Or list the live tools:

```bash
uv run python scripts/list_mcp_tools.py atlassian
```

You should see tools like `atlassianUserInfo`, `getAccessibleAtlassianResources`,
`searchJiraIssuesUsingJql`, `searchConfluenceUsingCql`, and `getJiraIssue`.

## 4. Tools Jarvis relies on

The Atlassian source agent is **read-only** and uses a small subset:

| Tool | Description |
|------|-------------|
| `atlassianUserInfo` | The authenticated user's accountId |
| `getAccessibleAtlassianResources` | The `cloudId` (UUID) required by the search tools |
| `searchJiraIssuesUsingJql` | Jira activity via JQL |
| `searchConfluenceUsingCql` | Confluence activity via CQL |
| `getJiraIssue` + Confluence comment tools | Read new comments for a summary only |

`addWorklogToJiraIssue` is blocked by default via `deny_tools` in `mcp/servers.yaml`.

## 5. Troubleshooting

### "No token" / status shows `✗ atlassian`
Run `jarvis-auth atlassian` and complete the browser flow. The token lands in `~/.mcp-auth`.

### Token expired or sites changed
Re-run the flow; clear the cache first if it's stuck:
```bash
rm -rf ~/.mcp-auth
jarvis-auth atlassian
```

### Server doesn't start in Docker
- Verify the mount in `docker-compose.yml`: `~/.mcp-auth:/root/.mcp-auth`.
- Confirm `~/.mcp-auth/` exists and is non-empty on the host.
- The init can be slow on a cold cache — the server allows up to 120s (`timeout: 120`).

## Security note

This OAuth grant gives read (and, for non-denied tools, write) access to your Jira and
Confluence. The Jarvis agent only issues read/search calls. Tokens stay on your machine
under `~/.mcp-auth/`, never in the repo or env files.
