# Atlassian MCP setup (remote MCP, OAuth 2.1)

Jarvis's `atlassian` MCP server is Atlassian's **official remote MCP**
(<https://mcp.atlassian.com/v1/mcp>), covering both **Jira** and **Confluence**. It is
HTTP-only and gated behind an interactive OAuth 2.1 browser flow that cannot run inside the
container. We bridge it with
[`mcp-remote`](https://www.npmjs.com/package/mcp-remote) (stdio ↔ remote HTTP): it performs
the OAuth dance on the host and caches the token under `~/.jarvis/mcp-auth/atlassian`.
`docker-compose.yml` mounts the shared `~/.jarvis/mcp-auth` base into the container, so it
starts with a warm token.

> There is **no static API token** — auth is OAuth. You log in once in the browser; the
> cached token (and its refresh token) live only under `~/.jarvis/mcp-auth/atlassian`,
> never in the repo.

## 1. Run the one-time auth (on the host, opens a browser)

```bash
jarvis-auth atlassian
```

This runs `npx -y mcp-remote https://mcp.atlassian.com/v1/mcp`:

- A browser opens → log in to Atlassian → approve access to your Jira/Confluence sites.
- On success the OAuth token is cached under `~/.jarvis/mcp-auth/atlassian/`.
- Keep the process running until the token is written, then **Ctrl-C** — that's fine.
- To force a fresh login after the token is revoked, run `jarvis-auth atlassian --force`.

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
  env:
    # Dedicated config dir so this server's OAuth state is isolated from other
    # mcp-remote servers. $HOME aligns host and container (the ~/.jarvis/mcp-auth mount).
    MCP_REMOTE_CONFIG_DIR: "${HOME}/.jarvis/mcp-auth/atlassian"
  deny_tools:
    - addWorklogToJiraIssue
```

- **Local run** (`uv run python -m jarvis.main`): works as long as
  `~/.jarvis/mcp-auth/atlassian/` holds a valid token and `npx` (Node 18+) is on your PATH.
- **Docker**: `docker-compose.yml` mounts `~/.jarvis/mcp-auth` into the container at
  `/root/.jarvis/mcp-auth`. Do the `jarvis-auth atlassian` step on the host first; the
  container reuses the cached token.

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
Run `jarvis-auth atlassian` and complete the browser flow. The token lands in
`~/.jarvis/mcp-auth/atlassian`.

### Token expired, "Invalid PKCE code_verifier", or sites changed
Force a fresh login. `--force` wipes the cached config dir (all stale `mcp-remote-<ver>/`
state, the usual cause of PKCE errors) before re-running the browser flow:
```bash
jarvis-auth atlassian --force
```

### Server doesn't start in Docker
- Verify the mount in `docker-compose.yml`: `~/.jarvis/mcp-auth:/root/.jarvis/mcp-auth`.
- Confirm `~/.jarvis/mcp-auth/atlassian/` exists and is non-empty on the host.
- The init can be slow on a cold cache — the server allows up to 120s (`timeout: 120`).

## Security note

This OAuth grant gives read (and, for non-denied tools, write) access to your Jira and
Confluence. The Jarvis agent only issues read/search calls. Tokens stay on your machine
under `~/.jarvis/mcp-auth/atlassian/`, never in the repo or env files.
