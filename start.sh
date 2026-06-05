#!/usr/bin/env bash
# Start Jarvis: export AWS SSO creds, load .env, bring up all services via Docker.
#
#   ./start.sh            # build (if needed) + start everything, then tail jarvis logs
#   ./start.sh --build    # force a rebuild of the jarvis image
#   ./start.sh --infra    # only infra (postgres, temporal, temporal-ui) — run app locally
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE="docker compose"

# --- Secrets / tokens -------------------------------------------------------
# Load .env first so flags like AWS_BEDROCK_ENABLED gate the steps below.
# docker-compose reads .env via env_file too, but exporting here lets --infra
# (local) runs and trigger_poll.py inherit the same values.
if [[ -f .env ]]; then
  set -a; # shellcheck disable=SC1091
  source .env; set +a
fi

# --- AWS Bedrock auth (optional) --------------------------------------------
# Only runs when AWS_BEDROCK_ENABLED=1 (set in .env). The container uses the boto3
# standard chain via the static AWS_* env vars that docker-compose forwards. Mint
# short-lived creds from the SSO session so Bedrock works inside the container (SSO
# profiles aren't usable directly in the container). Skip entirely for OpenAI/Ollama.
if [[ "${AWS_BEDROCK_ENABLED:-0}" == "1" ]]; then
  AWS_PROFILE_NAME="${AWS_PROFILE}"
  echo "→ Exporting AWS credentials from profile '$AWS_PROFILE_NAME'…"
  if ! aws sts get-caller-identity --profile "$AWS_PROFILE_NAME" >/dev/null 2>&1; then
    echo "  SSO session expired or missing. Run:  aws sso login --profile $AWS_PROFILE_NAME"
    exit 1
  fi
  eval "$(aws configure export-credentials --profile "$AWS_PROFILE_NAME" --format env)"
else
  echo "→ AWS Bedrock disabled (set AWS_BEDROCK_ENABLED=1 to enable); skipping AWS auth."
fi

# --- Bring services up ------------------------------------------------------
BUILD_FLAG=""
INFRA_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --build) BUILD_FLAG="--build" ;;
    --infra) INFRA_ONLY=1 ;;
    *) echo "unknown flag: $arg"; exit 1 ;;
  esac
done

if [[ "$INFRA_ONLY" == "1" ]]; then
  echo "→ Starting infra only (postgres, temporal, temporal-ui)…"
  $COMPOSE up -d postgres temporal temporal-ui pgweb
  echo
  echo "Infra up. Run the app locally with:"
  echo "    uv run python -m jarvis.main"
  exit 0
fi

echo "→ Starting all services…"
$COMPOSE up -d $BUILD_FLAG postgres temporal temporal-ui pgweb jarvis

echo
echo "✓ Jarvis is up:"
echo "    Dashboard    → http://localhost:4000"
echo "    Temporal UI  → http://localhost:4001"
echo "    DB (pgweb)   → http://localhost:4002"
echo
echo "Trigger a poll:  uv run python scripts/trigger_poll.py"
echo "Tailing jarvis logs (Ctrl-C to stop tailing; services keep running)…"
echo
$COMPOSE logs -f jarvis
