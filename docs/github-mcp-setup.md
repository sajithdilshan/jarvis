# GitHub MCP setup (local binary, PAT auth)

Jarvis's `github` MCP server runs GitHub's official
[`github-mcp-server`](https://github.com/github/github-mcp-server) over stdio. Unlike the
OAuth-based servers, this one uses a **Personal Access Token (PAT)** — a single static
token you create once and put in `.env`.

The binary is installed into the image by the Dockerfile (pinned release), so there is no
`npx` download at runtime.

> The PAT is *your* GitHub credential. Anyone holding it can act as you on GitHub within
> its scopes. It lives only in `.env` (gitignored), never in the repo.

## 1. Create a Personal Access Token

1. Go to <https://github.com/settings/tokens>.
2. Create a **fine-grained** token (recommended) or a **classic** token.
3. Grant read access for the toolsets Jarvis uses (`notifications`, `pull_requests`,
   `issues`):
   - **Fine-grained**: repo permissions → *Pull requests: Read*, *Issues: Read*,
     *Contents: Read* (for check runs), and account → *Notifications: Read*. Scope it to
     the org/repos you want Jarvis to watch.
   - **Classic**: `repo` and `notifications` scopes.
4. Copy the token (starts with `github_pat_…` for fine-grained or `ghp_…` for classic).

## 2. Put it in `.env`

```bash
jarvis-auth set GITHUB_TOKEN github_pat_...
```

(or edit `.env` directly):

```bash
GITHUB_TOKEN=github_pat_...
```

`docker-compose.yml` loads `.env` via `env_file`, so the token is forwarded into the
container automatically — no compose edits needed.

## 3. How Jarvis uses it

`mcp/servers.yaml` defines the `github` server:

```yaml
github:
  type: stdio
  command: "github-mcp-server"
  args: ["stdio"]
  env:
    GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
    GITHUB_TOOLSETS: "notifications,pull_requests,issues"
  timeout: 30
  deny_tools:
    - add_issue_comment
    - create_pull_request
    - issue_read
    - issue_write
    - list_issues
    - merge_pull_request
    - pull_request_review_write
    - search_issues
    - sub_issue_write
    - update_pull_request
    - update_pull_request_branch
```

- `GITHUB_TOOLSETS` limits which tool groups load — Jarvis only needs `notifications`,
  `pull_requests`, and `issues`, which keeps the toolset small.
- **Docker**: the Dockerfile downloads the `github-mcp-server` binary into
  `/usr/local/bin`, so the command resolves instantly.
- **Local run**: install `github-mcp-server` and put it on your PATH (see the project's
  releases page), or run via the binary the Dockerfile pins.

## 4. Verify

```bash
jarvis-auth status
```

You should see `✓ github  configured`. Or list the live tools:

```bash
uv run python scripts/list_mcp_tools.py github
```

You should see tools like `search_pull_requests`, `pull_request_read`,
`list_notifications`, and `get_me`.

## 5. Tools Jarvis relies on

The GitHub source agent is **read-only** and centers on:

| Tool | Description |
|------|-------------|
| `get_me` | Resolve the authenticated user's login (cached) |
| `search_pull_requests` | Authoritative snapshot of the user's open PRs |
| `list_notifications` | The "someone needs me" participating feed |
| `pull_request_read` | Reviews, inline review comments, and CI check runs per PR |

Write/mutation tools (`create_pull_request`, `merge_pull_request`, `add_issue_comment`,
issue read/write, etc.) are blocked by default via `deny_tools` in `mcp/servers.yaml`.

## 6. Troubleshooting

### Status shows `✗ github  missing: GITHUB_TOKEN`
Set it: `jarvis-auth set GITHUB_TOKEN <token>`.

### 401 / 403 from the server
The token is invalid, expired, or lacks scope. Regenerate it with the scopes in step 1 and
re-run `jarvis-auth set GITHUB_TOKEN ...`.

### A search returns nothing in an org
Fine-grained tokens are scoped per repo/org — ensure the token has access to the org you're
watching, and that the agent's queries are scoped with `owner`/`org` filters.

## Security note

The PAT grants the access you scope it to. Jarvis only issues read/search/notification
calls, and the mutation tools are denied in `servers.yaml`. The token stays in `.env` on
your machine, never in the repo.
