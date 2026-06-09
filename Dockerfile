# --- Stage 1: build the Preact SPA (Vite -> web/dist) ---
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json ./
RUN npm install
COPY web/ ./
RUN npm run build

# --- Stage 2: Python app ---
FROM python:3.13-slim

WORKDIR /app

# Node.js — needed for the stdio Gmail MCP server (`npx @gongrzhe/server-gmail-autoauth-mcp`)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Pre-install the stdio MCP servers so `npx` resolves them instantly at runtime instead
# of downloading on first use (which blows the MCP stdio init timeout).
RUN npm install -g @gongrzhe/server-gmail-autoauth-mcp slack-mcp-server

# GitHub MCP Server (local binary — has proper notifications toolset)
RUN curl -fsSL https://github.com/github/github-mcp-server/releases/download/v1.1.2/github-mcp-server_Linux_x86_64.tar.gz \
    | tar -xz -C /usr/local/bin github-mcp-server

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies (cached layer — independent of README/source churn)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Copy application
COPY README.md ./
COPY src/ ./src/
COPY config/ ./config/
COPY mcp/ ./mcp/
COPY alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Built SPA from the web stage (served by FastAPI at /)
COPY --from=web /web/dist ./web/dist

EXPOSE 4000

# Runs worker + API server
CMD ["uv", "run", "python", "-m", "jarvis.main"]
