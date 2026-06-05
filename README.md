# Jarvis

Local-first AI agentic personal assistant. Jarvis polls your work sources (Gmail,
Slack, GitHub, Jira/Confluence, Google Calendar) on a schedule, reasons over what
changed, acts autonomously on items you've granted standing permission for, and
surfaces the rest as a live dashboard briefing you can chat with.

Everything runs on your machine via Docker — your data stays in a local Postgres
instance, and LLM calls go to the provider you configure (AWS Bedrock, OpenAI, or a
local Ollama model).

## How it works

```
                    ┌──────────────────────────────────────────────┐
                    │  Temporal Schedule (cron, e.g. every 15 min)   │
                    └───────────────────────┬──────────────────────┘
                                            │ triggers
                                            ▼
                              ┌─────────────────────────┐
                              │   MainAgentWorkflow      │
                              └────────────┬────────────┘
            fan-out (parallel)             │
        ┌───────────────┬──────────────────┼──────────────┬──────────────┐
        ▼               ▼                  ▼               ▼              ▼
   ┌─────────┐   ┌─────────┐        ┌─────────┐     ┌──────────┐   ┌──────────┐
   │ gmail   │   │ slack   │        │ github  │     │atlassian │   │ calendar │   source agents
   │ agent   │   │ agent   │        │ agent   │     │ agent    │   │ agent    │   (LLM + MCP tools)
   └────┬────┘   └────┬────┘        └────┬────┘     └────┬─────┘   └────┬─────┘
        └─────────────┴──────────────────┴───────────────┴─────────────┘
                                         │ aggregated structured results
              ┌──────────────────────────┴───────────────────────────┐
              ▼                                                        ▼
     ┌──────────────────┐                                  ┌──────────────────────┐
     │ Permission engine│  acts autonomously               │  Synthesize agent    │
     │ (deterministic)  │  (archive, mark read…) → "did"    │  (LLM) → "noticed"   │
     └────────┬─────────┘                                  └───────────┬──────────┘
              └──────────────────────┬──────────────────────────────────┘
                                     ▼
                          ┌────────────────────┐      ┌──────────────────┐
                          │  briefing_log (PG)  │─────▶│ Postgres NOTIFY  │
                          └────────────────────┘      └────────┬─────────┘
                                                               │ WebSocket relay
                                                               ▼
                                                    ┌────────────────────┐
                                                    │  Preact dashboard   │◀── user chats
                                                    └────────────────────┘
                                                               │ chat message (signal)
                                                               ▼
                                                  ┌──────────────────────────┐
                                                  │ InteractiveChatWorkflow   │
                                                  │ → interactive agent (LLM) │
                                                  └──────────────────────────┘
```

**Scheduled poll** (`MainAgentWorkflow`): a Temporal cron schedule fans out to every
registered source agent in parallel. Each source agent is a PydanticAI agent backed by
that source's MCP server; it fetches what changed since the last successful poll and
returns a structured summary. Results then flow two ways in parallel:

- The **permission engine** (deterministic, no LLM) matches items against your standing
  rules and acts on them autonomously (e.g. archive, mark-as-read), producing **"did"**
  briefing entries.
- The **synthesize agent** (LLM) reasons over the aggregated data and produces
  **"noticed"** / **"ask"** briefing entries.

Entries are written to `briefing_log`, a Postgres `NOTIFY` fires, and the WebSocket
relay pushes a refresh ping to the browser, which refetches the view model.

**Interactive chat** (`InteractiveChatWorkflow`): a long-lived workflow per browser
session. Each chat message arrives as a Temporal signal and runs the interactive agent,
which can call any connected MCP tool, search memory, and grant/revoke permissions.

## The two workflows

Everything Jarvis does runs as one of two Temporal workflows. The scheduled workflow is
the "always watching" loop; the interactive workflow is the conversation. Both are
durable — they survive process restarts and retry failed steps automatically.

### 1. Scheduled workflow — `MainAgentWorkflow`

The autonomous loop. A Temporal **Schedule** (cron from `config/default.yaml`, default
every 15 min during work hours) starts one workflow run per tick. Each run:

1. **Stamp the window.** Record `workflow.now()` as this run's upper bound (deterministic
   — never wall-clock). Read the **poll watermark** (the start time of the last *clean*
   run) as the lower bound, so the window is exactly "what changed since we last
   succeeded." First run ever → last 24h.
2. **Fan out to source agents (parallel).** `list_registered_agents` returns every
   discovered `poll=True` source. Each runs as its own activity (`run_sub_agent`): a
   PydanticAI agent with its MCP toolset, prompted to fetch what changed in the window
   and return a schema-validated summary. Failures are isolated per source.
3. **Act + reason (parallel).** Two activities run on the aggregated results at once:
   - **`execute_permissions`** — the deterministic permission engine matches items
     against your standing rules and performs the allowed actions (archive, mark-read,
     …), emitting **"did"** entries. No LLM.
   - **`run_main_agent_synthesize`** — the synthesize agent (LLM) reasons over everything
     and produces **"noticed" / "ask"** briefing entries, persisting memory as it goes.
4. **Publish.** `publish_briefing` converts all entries into view-model ops and writes
   them to `briefing_log`; a Postgres `NOTIFY` pushes a refresh to connected browsers.
5. **Advance the watermark — only on a clean run.** If any source failed, the watermark
   is left untouched so the next run re-covers that window (no missed data). Failed
   sources are surfaced as error cards via `report_source_failures`.

Trigger one manually with `scripts/trigger_poll.py` (the worker must be running).

### 2. Interactive workflow — `InteractiveChatWorkflow`

The conversation. A **single long-lived workflow** (`jarvis-interactive`) backs the chat
UI — it's started lazily by the API on first `/session` or `/agent/invoke` and stays
alive blocking on signals, so there's no per-message scheduling overhead.

1. **Message in.** A chat message or dashboard click hits `POST /agent/invoke`, which
   **signals** the workflow (`chat_message`). The workflow drains pending messages and
   runs the `run_interactive_chat` activity for each.
2. **Context assembly.** For chat intents, the activity prepends recent conversation
   history and unresolved dashboard alerts so the agent has continuity ("yes, do the
   rest" works).
3. **Run + stream.** The interactive agent runs with **lazy MCP tool loading** — instead
   of attaching every toolset upfront (token bloat), it has tools to list servers, list a
   server's tools, and call any tool on demand. The reply is **streamed token-by-token**
   to the browser over the WebSocket relay; persistence (history, memory, telemetry)
   happens *after* the reply is on screen so time-to-first-token is bounded by the LLM.
4. **Bounded history.** After 50 messages the workflow **continues-as-new** to keep
   Temporal history small; after 2h idle it completes (a fresh one starts on the next
   message).

The interactive agent can call any connected MCP tool, search vector memory, and
**grant / revoke / refine standing permissions** — which is how the scheduled loop learns
what it's allowed to do autonomously.

## Architecture

Jarvis runs as a **single Python process** that hosts both a Temporal worker and a
FastAPI server, sharing one DI container, DB pool, and Temporal client (see
`src/jarvis/main.py`).

| Layer | Tech | Role |
|-------|------|------|
| Orchestration | [Temporal](https://temporal.io) | Durable workflows: scheduled polls + per-session chat. Survives restarts, retries failed activities. |
| Agents | [PydanticAI](https://ai.pydantic.dev) | LLM agents with structured (schema-validated) outputs and tool calling. |
| Tools | [MCP](https://modelcontextprotocol.io) | Each source (Gmail, Slack, …) is an MCP server providing the agent its tools. |
| Storage | Postgres + [pgvector](https://github.com/pgvector/pgvector) | Raw data, briefing stream, permissions, vector memory, telemetry. |
| Embeddings | sentence-transformers (`BAAI/bge-base-en-v1.5`) | In-process, CPU-only, for semantic memory search. |
| API | FastAPI + Uvicorn | REST routes + WebSocket relay (Postgres `NOTIFY` → browser). |
| Frontend | Preact + Vite | Single-page dashboard; built to `web/dist`, served statically by FastAPI. |
| DI | dependency-injector | Single composition root (`config/containers.py`). |
| Migrations | Alembic | Schema versioned in `db/migrations/versions/`. |

### Key design points

- **Agents are plugins.** Each subpackage under `agents/sources/` that exports a `SPEC`
  (`AgentSpec`) is auto-discovered by `AgentRegistry` — no hardcoded list. A source agent
  is just a folder with `__init__.py` (the SPEC), `prompt.md` (system prompt), `schema.py`
  (structured output), and optionally `tools.py`. Adding a source needs no wiring changes.
- **Two model tiers.** Scheduled source agents use a cheap `default_model`; interactive
  chat uses a more capable `interactive_model`. Models are provider-agnostic specs
  (`bedrock:…`, `openai:…`, `ollama:…`) resolved by `agents/model_factory.py`.
- **Poll watermark.** The workflow only advances the "last successful poll" timestamp
  when *no* source failed, so a failed source re-covers its window on the next run.
- **MCP tool gating.** `mcp/servers.yaml` defines each server once; a per-server
  `deny_tools` list blocks dangerous tools (delete, send, etc.) from both exposure and
  invocation.
- **Permissions are deterministic.** The permission engine matches a small constraint DSL
  (exact / `_contains` / `_matches`) against items with a per-rule circuit breaker — no
  LLM in the autonomous-action path.

### Project structure

```
src/jarvis/
├── main.py                  # entry point: boots container, runs worker + API
├── config/
│   ├── settings.py          # YAML + env-var → validated AppSettings
│   ├── containers.py        # dependency-injection composition root
│   └── logging_config.py
├── workflows/               # Temporal workflow definitions
│   ├── main_workflow.py     # scheduled poll fan-out → synthesize
│   ├── interactive_workflow.py  # long-lived per-session chat
│   ├── setup.py             # ensure_schedule()
│   └── activity_options.py  # retry/timeout policies per activity class
├── activities/              # Temporal activities (run outside the sandbox)
│   ├── source_activities.py     # list agents, watermark, run_sub_agent
│   ├── synthesis_activities.py  # run_main_agent_synthesize
│   ├── permission_activities.py # execute_permissions
│   ├── briefing_activities.py   # publish_briefing, report_source_failures
│   └── interactive_activities.py
├── agents/
│   ├── registry.py          # auto-discovers SPECs, builds agents
│   ├── base.py              # AgentSpec contract
│   ├── model_factory.py     # spec string → model (bedrock/openai/ollama)
│   ├── core/                # bespoke agents (not SPEC-discovered)
│   │   ├── synthesize/      # reasons over aggregated data
│   │   ├── interactive/     # chat agent (lazy MCP tool loading)
│   │   └── permission_execution/
│   └── sources/             # plugin agents (gmail, slack, github, atlassian)
│       └── <source>/        # __init__.py(SPEC) + prompt.md + schema.py [+ tools.py]
├── services/                # business logic over repos (memory, permissions, MCP, …)
├── db/
│   ├── engine.py            # async SQLAlchemy engine + notify_pool resources
│   ├── schema.sql           # reference DDL (Alembic is authoritative)
│   ├── repositories/        # one repo per table
│   └── migrations/          # Alembic versions
├── api/                     # FastAPI routes + WebSocket relay
├── models/                  # Pydantic models (agent I/O, view model, session, …)
└── cli/
    └── auth.py              # `jarvis-auth` — manage MCP credentials

web/                         # Preact SPA (Vite) → built to web/dist
config/default.yaml          # base config (env vars override)
mcp/servers.yaml             # MCP server definitions + tool gating
docs/                        # per-source MCP setup guides
scripts/trigger_poll.py      # manually trigger one poll
```

## Adding a new source agent

Source agents are plugins: `AgentRegistry` auto-discovers any subpackage of
`agents/sources/` that exports a `SPEC`. There is no central list to edit — drop in a
folder and it joins the scheduled fan-out.

### 1. Add an MCP server (if the source needs one)

If your source has its own MCP server, declare it once in `mcp/servers.yaml`. Reference
secrets as `${VAR}` (resolved from the environment at startup) and gate dangerous tools
with `deny_tools`:

```yaml
servers:
  linear:
    type: stdio
    command: "npx"
    args: ["-y", "linear-mcp-server"]
    env:
      LINEAR_API_KEY: "${LINEAR_API_KEY}"
    deny_tools:
      - delete_issue
```

`jarvis-auth status` will automatically pick up the new `${VAR}` requirement. If the
server is a stdio binary that needs pre-installing, add it to the `Dockerfile`.

### 2. Create the agent folder

Add `src/jarvis/agents/sources/<name>/` with these files. **The folder name must match
`SPEC.name`** (the registry enforces this).

```
agents/sources/linear/
├── __init__.py    # exports SPEC (the plugin contract)
├── prompt.md      # the agent's system prompt
├── schema.py      # the structured result type (Pydantic)
└── tools.py       # optional — extra Python tools beyond the MCP server
```

**`schema.py`** — define the structured output. The `items_key` field (below) must hold
a `list[ItemModel]`; the per-item fields become the match-fields the permission engine
and interactive agent can target, so name them well:

```python
from pydantic import BaseModel

class LinearIssue(BaseModel):
    title: str
    state: str
    url: str
    requires_action: bool = False
    raw_data_id: str          # link back to the stored raw payload

class LinearSummary(BaseModel):
    issues: list[LinearIssue] = []
```

**`__init__.py`** — export the `SPEC`:

```python
from jarvis.agents.base import AgentSpec, load_prompt
from jarvis.agents.sources.linear.schema import LinearSummary

SPEC = AgentSpec(
    name="linear",                 # MUST equal the folder name
    prompt=load_prompt(__file__),  # reads prompt.md next to this file
    result_type=LinearSummary,
    items_key="issues",            # which result field holds the actionable list
    mcp_servers=["linear"],        # names from mcp/servers.yaml
    model_env="JARVIS_TOOL_AGENT_MODEL",  # optional per-agent model override
    # poll=True (default) → included in the scheduled fan-out
)
```

`AgentSpec` fields: `name`, `prompt`, `result_type` (required); `items_key` (default
`"items"`), `mcp_servers`, `register_tools`, `model`, `model_env`, and `poll`
(set `poll=False` to exclude from scheduled runs).

**`prompt.md`** — the system prompt. Tell the agent what to fetch, which MCP tools to
use, and how to map results into the schema. The poll window arrives in the task as a
"since" phrase bundling ISO-8601, epoch seconds, and JQL/CQL datetime — pick the format
your source's API wants (see existing prompts for examples).

### 3. (Optional) add custom tools

If the agent needs Python tools beyond its MCP server, add `tools.py` with a
`register(agent)` function and point `SPEC.register_tools` at it.

### 4. Run

Restart the app. The new agent is discovered automatically, joins the scheduled poll,
its output schema is exposed to the synthesize and interactive agents, and standing
permissions can target its item fields — no other code changes required.

## Prerequisites

- **Docker** (Docker Desktop on macOS) — runs Postgres, Temporal, and the app.
- **[uv](https://github.com/astral-sh/uv)** — Python 3.13 package/dependency manager,
  for running the app or scripts locally.
- **Node.js 22+** — only if you want to develop the frontend locally (the Docker build
  handles it otherwise).
- An **LLM provider**: AWS Bedrock access (the default), an OpenAI API key, or a local
  Ollama install.
- **Tokens / OAuth** for whichever sources you want to enable (see *MCP credentials* below).

## Setup

### 1. Configure environment

```bash
cp .env.example .env
```

Fill in `.env` with at least one LLM provider and the source tokens you want. See
**Environment variables** below for the full list.

### 2. Configure MCP credentials

Tokens and OAuth flows are managed with the `jarvis-auth` CLI (discovers requirements
from `mcp/servers.yaml`):

```bash
uv run jarvis-auth status            # show which sources are configured
uv run jarvis-auth set GITHUB_TOKEN ghp_...   # write a token to .env
uv run jarvis-auth gmail             # one-time Gmail OAuth (browser)
uv run jarvis-auth calendar          # one-time Google Calendar OAuth (browser)
uv run jarvis-auth atlassian         # one-time Atlassian OAuth (browser)
```

Per-source setup details live in `docs/`:
- `docs/gmail-mcp-setup.md`
- `docs/slack-mcp-setup.md`
- `docs/github-mcp-setup.md`
- `docs/google-calendar-mcp-setup.md`
- `docs/atlassian-mcp-setup.md`

> OAuth flows must run on the **host** (they open a browser). The resulting tokens are
> cached under `~/.gmail-mcp`, `~/.config/google-calendar-mcp`, `~/.mcp-auth`, etc., and
> docker-compose mounts those directories into the container.

### 3. AWS Bedrock auth (only if using Bedrock)

AWS auth is **opt-in**, gated by `AWS_BEDROCK_ENABLED`. If you use OpenAI or Ollama,
leave it at `0` (the default) and skip this step entirely — `start.sh` won't touch AWS.

To use Bedrock, set these in `.env`:

```bash
AWS_BEDROCK_ENABLED=1
AWS_PROFILE=your-sso-profile
```

Then log in before running — `start.sh` mints short-lived credentials from your SSO
session and forwards them to the container:

```bash
aws sso login --profile your-sso-profile
```

## Running

### Everything in Docker (recommended)

```bash
./start.sh            # build (if needed) + start all services, then tail app logs
./start.sh --build    # force a rebuild of the jarvis image
./stop.sh             # stop + remove containers (Postgres data is preserved)
./stop.sh --app       # stop only the app, leave infra running
```

Once up:

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:4000 |
| Temporal UI | http://localhost:4001 |
| Postgres browser (pgweb) | http://localhost:4002 |
| Postgres (host port) | `localhost:4003` |
| Temporal gRPC (host port) | `localhost:4004` |

### Infra in Docker, app locally (for development)

Run Postgres/Temporal in containers but the Python app on the host (faster iterate):

```bash
./start.sh --infra            # postgres + temporal + temporal-ui + pgweb only
uv run python -m jarvis.main  # run worker + API locally
```

When running locally, `settings.py` defaults point at the host-published ports
(`localhost:4003` for Postgres, `localhost:4004` for Temporal).

### Frontend development

```bash
cd web
npm install
npm run dev      # Vite dev server with HMR
npm run build    # production build → web/dist (what FastAPI serves)
```

### Manually trigger a poll

The scheduled poll runs on the cron in `default.yaml`. To trigger one immediately
(worker must be running):

```bash
uv run python scripts/trigger_poll.py
```

## Database & migrations

Schema is managed by Alembic (`src/jarvis/db/migrations/`). The engine resource applies
migrations automatically on startup, so normal runs need no manual step. To work with
migrations directly:

```bash
uv run alembic upgrade head             # apply all migrations
uv run alembic revision -m "describe"   # create a new migration
```

`src/jarvis/db/schema.sql` is reference DDL only (do not run it directly — Alembic is
authoritative).

### Data persistence

Even though Postgres runs inside Docker, **its data lives on your host machine and
survives container teardown.** docker-compose bind-mounts the Postgres data directory to
`~/.jarvis/data/postgres` on the host (not a Docker named volume), so:

- `./stop.sh` / `docker compose down` removes the containers but **keeps all your data** —
  raw data, memory, briefings, permissions, and chat history persist across restarts.
- The mount is a host path, so it also survives Docker Desktop VM resets.
- To truly start fresh, delete the host directory: `rm -rf ~/.jarvis/data/postgres`.

Other host-mounted state under `~/.jarvis/`: the cached embedding model
(`~/.jarvis/data/models`) and MCP OAuth tokens (`~/.gmail-mcp`, `~/.mcp-auth`, etc.).

### Schema

All tables live in one Postgres database (shared with Temporal's own backend). The
`vector` (pgvector) extension powers semantic memory search.

| Table | Purpose |
|-------|---------|
| `raw_data` | **Source of truth.** Full raw payloads from MCP tools, keyed `"{source}:{source_id}"`. Everything else can be rebuilt from here. |
| `memory_chunks` | Rebuildable **vector index** over `raw_data`. Stores the embedded `content` (so it can be re-embedded if the model changes), a `VECTOR(768)` embedding, plus `category` (communication/task/decision/preference), `entities`, `importance`, and `confidence` (for learned preferences). HNSW cosine index. |
| `briefing_log` | The **primary UI content.** One row per briefing entry — `tier` (`noticed`/`did`), `category` (`did`/`ask`/`noticed`), `narrative`, `source`, `refs`, expandable `context`, `priority`, and `permission_ref`. Entries are never deleted, only **resolved** (`resolved_at` set); the active feed is `WHERE resolved_at IS NULL`. |
| `permissions` | **Standing rules** the scheduled loop may execute autonomously. Natural-language `description`, a `source`, structured `constraints` (the match DSL), `allowed_actions`, and `active`. Managed via chat (grant/revoke/refine). |
| `poll_watermark` | Single row. Start time of the last scheduled poll that finished with **no source failures** — read as the next run's "since", advanced only on a clean run. |
| `interactions` | Chat **conversation history** — one row per turn (`role` = user/assistant, `content`), used to give the interactive agent continuity. |
| `token_usage` | **Telemetry.** One row per LLM-running activity: resolved `model`, `agent`, `trigger`, and input/output/cache token counts + tool calls. Dollar cost is computed at query time. |
| `progress` | Transient per-session **progress events** (e.g. `gmail_checking` → `gmail_complete`) streamed to the UI during a run. |

The reference DDL with full column definitions and indexes is in
`src/jarvis/db/schema.sql`; the authoritative, versioned schema is the Alembic migration
chain in `src/jarvis/db/migrations/versions/`. Each table has a matching repository in
`src/jarvis/db/repositories/`.

## Testing & linting

```bash
uv run pytest          # run the test suite (unit + integration)
uv run ruff check      # lint
uv run ruff format     # format
```

Integration tests use testcontainers, which require Docker to be running.

## Environment variables

Set in `.env` (copy from `.env.example`). docker-compose loads it via `env_file`, and
`start.sh` also sources it so local and `--infra` runs share the same values.

### LLM providers

| Var | Description |
|-----|-------------|
| `OPENAI_API_KEY` | Required for `openai:` models. |
| `AWS_BEDROCK_ENABLED` | `1` to enable Bedrock auth in `start.sh`; `0` (default) skips all AWS steps. |
| `AWS_PROFILE` | SSO profile `start.sh` exports credentials from (when Bedrock is enabled). |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` | Bedrock auth (boto3 chain). `start.sh` populates these from your SSO profile. |
| `AWS_REGION` | Bedrock region (default `eu-central-1`). |
| `OLLAMA_BASE_URL` | For `ollama:` models. Default `http://host.docker.internal:11434/v1` (container → host Mac). |

### Model selection

Configured in `config/default.yaml` under `llm:`; override via env without editing YAML:

| Var | Description |
|-----|-------------|
| `JARVIS_DEFAULT_MODEL` | Model for scheduled source agents (cheap tier). |
| `JARVIS_INTERACTIVE_MODEL` | Model for chat (advanced tier); falls back to default. |
| `JARVIS_TOOL_AGENT_MODEL` | Optional per-source override (referenced by some SPECs via `model_env`). |
| `JARVIS_MODEL_OVERRIDE` | Global override; wins over everything. |

Model specs are strings: `openai:gpt-5.5`, `bedrock:<arn-or-model-id>`, `ollama:<name>`.

### MCP / source tokens

| Var | Source |
|-----|--------|
| `GITHUB_TOKEN` | GitHub PAT (scopes: repo, notifications, user). |
| `SLACK_MCP_XOXC_TOKEN` / `SLACK_MCP_XOXD_TOKEN` | Slack browser session tokens (see `docs/slack-mcp-setup.md`). |
| *(Gmail)* | OAuth via `~/.gmail-mcp/` — not an env var. Run `jarvis-auth gmail`. |
| *(Calendar)* | OAuth via `~/.config/google-calendar-mcp/` — run `jarvis-auth calendar`. |
| *(Atlassian)* | OAuth via `~/.mcp-auth/` — run `jarvis-auth atlassian`. |

### Schedule

| Var | Default | Description |
|-----|---------|-------------|
| `JARVIS_SCHEDULE_CRON` | `*/15 8-17 * * 1-5` | Poll cron (every 15 min, 8am–6pm, Mon–Fri). |
| `JARVIS_SCHEDULE_TIMEZONE` | `Europe/Berlin` | Cron timezone. |
| `JARVIS_SCHEDULE_ENABLED` | `true` | Enable/disable the scheduled poll. |

### Infrastructure (usually set by docker-compose)

| Var | Description |
|-----|-------------|
| `JARVIS_PORT` | API/dashboard port (default 4000). |
| `TEMPORAL_HOST` | Temporal gRPC address (`temporal:7233` in Docker). |
| `POSTGRES_DSN` | Postgres connection string. |
| `JARVIS_MCP_CONFIG` | Path to `servers.yaml`. |
| `JARVIS_UI_STATIC_DIR` | Path to the built SPA (`web/dist`). |
| `HF_HUB_OFFLINE` | `1` in Docker — load the cached embedding model from disk, skip Hub calls. |

### Configuration files

- `config/default.yaml` — base config (app, temporal, schedule, llm, postgres, embedding).
  Env vars override these; see `src/jarvis/config/settings.py` for the mapping.
- `mcp/servers.yaml` — MCP server definitions, `${VAR}` secret references, timeouts, and
  per-server `deny_tools` gating.
