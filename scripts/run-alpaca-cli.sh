#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
environment_file="$repository_root/.env"
workspace_binary="$repository_root/.alpaca-cli/alpaca"

if [[ ! -f "$environment_file" ]]; then
  echo "Missing $environment_file. Add paper credentials before using the CLI." >&2
  exit 1
fi

while IFS='=' read -r key value; do
  value="${value%$'\r'}"
  case "$key" in
    ALPACA_API_KEY | ALPACA_SECRET_KEY)
      export "$key=$value"
      ;;
  esac
done < "$environment_file"

: "${ALPACA_API_KEY:?ALPACA_API_KEY is missing from .env}"
: "${ALPACA_SECRET_KEY:?ALPACA_SECRET_KEY is missing from .env}"
export ALPACA_LIVE_TRADE=false
export ALPACA_CONFIG_DIR="$repository_root/.alpaca-cli/config"
export ALPACA_QUIET=true

if [[ -x "$workspace_binary" ]]; then
  exec "$workspace_binary" "$@"
fi
if command -v alpaca >/dev/null 2>&1; then
  exec alpaca "$@"
fi

echo "Alpaca CLI is missing. See README.md for the pinned local install." >&2
exit 127
