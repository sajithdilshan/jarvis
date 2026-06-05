#!/usr/bin/env bash
# Stop Jarvis.
#
#   ./stop.sh          # stop + remove all service containers (data is preserved —
#                      # Postgres lives in the ~/.jarvis/data host bind-mount)
#   ./stop.sh --app    # stop only the jarvis app; leave infra running
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE="docker compose"

if [[ "${1:-}" == "--app" ]]; then
  echo "→ Stopping jarvis app only (infra stays up)…"
  $COMPOSE stop jarvis
  $COMPOSE rm -f jarvis
  exit 0
fi

echo "→ Stopping and removing all Jarvis containers…"
# No -v: named volumes aren't used anyway, and Postgres data is a host bind-mount
# under ~/.jarvis/data, so it survives regardless.
$COMPOSE down

echo "✓ Stopped. Postgres data preserved at ~/.jarvis/data/postgres."
